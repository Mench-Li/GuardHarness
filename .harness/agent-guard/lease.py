"""Lease and heartbeat manager for interruption safety.

Ensures that only one agent holds the lease for a non-terminal task.
Lease expiry marks the task as Interrupted, allowing another agent to resume.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from state_machine import State, StateMachine, StateMachineError


class LeaseError(Exception):
    pass


class LeaseManager:
    """Manages lease lifecycle for tasks."""

    DEFAULT_HEARTBEAT_INTERVAL = 300  # 5 minutes
    DEFAULT_LEASE_DURATION = 600  # 10 minutes

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(".harness/agent-guard")
        self.leases_dir = self.base_dir / "leases"
        self.leases_dir.mkdir(parents=True, exist_ok=True)
        self.state_machine = StateMachine(str(self.base_dir))

    def _lease_file(self, task_id: str) -> Path:
        return self.leases_dir / f"{task_id}-lease.json"

    def _atomic_write_lease(self, task_id: str, lease: dict[str, Any]) -> None:
        """Write lease atomically: temp file + rename (atomic on POSIX and Windows Vista+)."""
        lease_path = self._lease_file(task_id)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(lease_path.parent), delete=False, suffix=".tmp"
        ) as f:
            json.dump(lease, f, indent=2, ensure_ascii=False)
            tmp_path = f.name
        try:
            Path(tmp_path).replace(lease_path)
        except OSError:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def acquire(
        self,
        task_id: str,
        holder: str | None = None,
        duration_seconds: int = DEFAULT_LEASE_DURATION,
    ) -> dict[str, Any]:
        """Acquire or renew a lease for a task.

        Rules:
        - No active lease: create new
        - Same holder with active lease: renew
        - Different holder with active lease: raise LeaseError
        - Expired lease: allow preemption (create new)
        """
        task = self.state_machine.get_task(task_id)
        if task.current_state in {State.DONE}:
            raise LeaseError(f"Cannot acquire lease for terminal state {task.current_state.value}")

        holder = holder or f"agent-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone(timedelta(hours=8)))

        existing = self.get_lease(task_id)
        if existing:
            existing_expires = datetime.fromisoformat(existing["expires_at"])
            if now < existing_expires:
                # Active lease exists
                if existing["holder"] == holder:
                    # Same holder: renew
                    existing["expires_at"] = (now + timedelta(seconds=duration_seconds)).isoformat()
                    existing["acquired_at"] = now.isoformat()
                    existing["duration_seconds"] = duration_seconds
                    self._atomic_write_lease(task_id, existing)
                    return existing
                # Different holder: deny
                raise LeaseError(
                    f"Lease held by {existing['holder']} until {existing['expires_at']}; "
                    f"cannot acquire as {holder}"
                )
            # Expired lease falls through to create new

        lease = {
            "task_id": task_id,
            "holder": holder,
            "acquired_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=duration_seconds)).isoformat(),
            "heartbeat_interval": self.DEFAULT_HEARTBEAT_INTERVAL,
            "duration_seconds": duration_seconds,
        }

        self._atomic_write_lease(task_id, lease)

        return lease

    def get_lease(self, task_id: str) -> dict[str, Any] | None:
        """Read current lease for a task, or None if no lease exists."""
        path = self._lease_file(task_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def is_expired(self, task_id: str) -> bool:
        """Check if the current lease has expired."""
        lease = self.get_lease(task_id)
        if lease is None:
            return True
        expires = datetime.fromisoformat(lease["expires_at"])
        return datetime.now(timezone(timedelta(hours=8))) > expires

    def heartbeat(self, task_id: str, holder: str, extend_seconds: int | None = None) -> dict[str, Any]:
        """Renew lease by extending expiry time."""
        lease = self.get_lease(task_id)
        if lease is None:
            raise LeaseError(f"No active lease for task {task_id}")

        if lease["holder"] != holder:
            raise LeaseError(
                f"Lease held by {lease['holder']}; cannot heartbeat as {holder}"
            )

        if self.is_expired(task_id):
            raise LeaseError(f"Lease for task {task_id} has already expired")

        duration = extend_seconds or lease.get("duration_seconds", self.DEFAULT_LEASE_DURATION)
        now = datetime.now(timezone(timedelta(hours=8)))
        lease["expires_at"] = (now + timedelta(seconds=duration)).isoformat()
        lease["last_heartbeat"] = now.isoformat()

        self._atomic_write_lease(task_id, lease)

        return lease

    def release(self, task_id: str, holder: str) -> None:
        """Explicitly release a lease."""
        lease = self.get_lease(task_id)
        if lease and lease["holder"] == holder:
            self._lease_file(task_id).unlink(missing_ok=True)

    def force_release(self, task_id: str) -> None:
        """Forcefully release a lease (admin only)."""
        self._lease_file(task_id).unlink(missing_ok=True)

    def can_resume(self, task_id: str) -> tuple[bool, str]:
        """Check if a task can be resumed by a new holder."""
        try:
            task = self.state_machine.get_task(task_id)
        except StateMachineError as e:
            return False, str(e)

        if task.current_state in {State.DONE}:
            return False, f"Task is in terminal state {task.current_state.value}"

        lease = self.get_lease(task_id)
        if lease is None:
            return True, "No active lease"

        if self.is_expired(task_id):
            return True, "Lease expired"

        return False, f"Lease held by {lease['holder']} until {lease['expires_at']}"
