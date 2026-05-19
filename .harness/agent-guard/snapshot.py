"""Snapshot manager for task recovery protocol.

Generates, reads, and validates TASK-xxx-snapshot.yaml files
that enable fast task resumption after interruption.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from state_machine import State, StateMachine, StateMachineError


@dataclass
class LeaseInfo:
    holder: str = ""
    expires_at: str = ""
    heartbeat_interval: int = 300  # seconds


@dataclass
class RequiredContext:
    files: list[str] = field(default_factory=list)
    memories: list[str] = field(default_factory=list)
    plans: list[str] = field(default_factory=list)


@dataclass
class PlanStep:
    step: int
    description: str
    evidence: str = ""
    started_at: str = ""
    completed_at: str = ""


@dataclass
class PlanProgress:
    total_steps: int = 0
    completed: list[PlanStep] = field(default_factory=list)
    in_progress: list[PlanStep] = field(default_factory=list)
    pending: list[PlanStep] = field(default_factory=list)


@dataclass
class SandboxInfo:
    worktree_path: str = ""
    branch: str = ""
    created_at: str = ""
    destroyed_at: str = ""


@dataclass
class Snapshot:
    task_id: str
    current_state: str
    previous_state: str
    transition_time: str
    lease: LeaseInfo = field(default_factory=LeaseInfo)
    required_context: RequiredContext = field(default_factory=RequiredContext)
    plan_progress: PlanProgress = field(default_factory=PlanProgress)
    recovery_prompt: str = ""
    sub_tasks: list[str] = field(default_factory=list)
    sandbox: SandboxInfo = field(default_factory=SandboxInfo)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        lease = LeaseInfo(**data.get("lease", {}))
        req_ctx = RequiredContext(**data.get("required_context", {}))
        sandbox = SandboxInfo(**data.get("sandbox", {}))

        pp_data = data.get("plan_progress", {})
        plan_progress = PlanProgress(
            total_steps=pp_data.get("total_steps", 0),
            completed=[PlanStep(**s) for s in pp_data.get("completed", [])],
            in_progress=[PlanStep(**s) for s in pp_data.get("in_progress", [])],
            pending=[PlanStep(**s) for s in pp_data.get("pending", [])],
        )

        return cls(
            task_id=data["task_id"],
            current_state=data["current_state"],
            previous_state=data.get("previous_state", ""),
            transition_time=data.get("transition_time", ""),
            lease=lease,
            required_context=req_ctx,
            plan_progress=plan_progress,
            recovery_prompt=data.get("recovery_prompt", ""),
            sub_tasks=data.get("sub_tasks", []),
            sandbox=sandbox,
        )


class SnapshotManager:
    """Manages snapshot lifecycle for task recovery."""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(".harness/agent-guard")
        self.snapshots_dir = self.base_dir / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.state_machine = StateMachine(str(self.base_dir))

    def _snapshot_path(self, task_id: str, timestamp: str | None = None) -> Path:
        if timestamp:
            return self.snapshots_dir / f"{task_id}-{timestamp}.yaml"
        return self.snapshots_dir / f"{task_id}-latest.yaml"

    def create_snapshot(
        self,
        task_id: str,
        required_context: RequiredContext | None = None,
        plan_progress: PlanProgress | None = None,
        recovery_prompt: str = "",
        lease: LeaseInfo | None = None,
        sub_tasks: list[str] | None = None,
        sandbox: SandboxInfo | None = None,
    ) -> Snapshot:
        """Create a new snapshot after a state transition."""
        task = self.state_machine.get_task(task_id)

        # Determine previous state from history
        previous_state = ""
        if task.history:
            previous_state = task.history[-1].from_state.value

        snapshot = Snapshot(
            task_id=task_id,
            current_state=task.current_state.value,
            previous_state=previous_state,
            transition_time=datetime.now(timezone(timedelta(hours=8))).isoformat(),
            lease=lease or LeaseInfo(),
            required_context=required_context or RequiredContext(),
            plan_progress=plan_progress or PlanProgress(),
            recovery_prompt=recovery_prompt,
            sub_tasks=sub_tasks or [],
            sandbox=sandbox or SandboxInfo(),
        )

        self._write_snapshot(snapshot)
        return snapshot

    def create_step_snapshot(
        self,
        task_id: str,
        plan_progress: PlanProgress,
    ) -> Snapshot:
        """Create a step-level snapshot with a fresh timestamp, preserving existing context."""
        task = self.state_machine.get_task(task_id)
        previous_state = ""
        if task.history:
            previous_state = task.history[-1].from_state.value

        # Preserve existing snapshot context
        old_lease = None
        old_sub_tasks = None
        old_sandbox = None
        old_req_ctx = None
        old_recovery = ""
        try:
            old = self.load_snapshot(task_id)
            old_lease = old.lease
            old_sub_tasks = old.sub_tasks
            old_sandbox = old.sandbox
            old_req_ctx = old.required_context
            old_recovery = old.recovery_prompt
        except Exception:
            pass

        snapshot = Snapshot(
            task_id=task_id,
            current_state=task.current_state.value,
            previous_state=previous_state,
            transition_time=datetime.now(timezone(timedelta(hours=8))).isoformat(),
            lease=old_lease or LeaseInfo(),
            required_context=old_req_ctx or RequiredContext(),
            plan_progress=plan_progress,
            recovery_prompt=old_recovery,
            sub_tasks=old_sub_tasks or [],
            sandbox=old_sandbox or SandboxInfo(),
        )
        self._write_snapshot(snapshot)
        return snapshot

    def _write_snapshot(self, snapshot: Snapshot) -> None:
        ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d-%H%M%S-%f")
        seq = self._next_sequence_number(snapshot.task_id)
        ts_seq = f"{ts}-{seq:03d}"
        path_ts = self._snapshot_path(snapshot.task_id, ts_seq)
        with open(path_ts, "w", encoding="utf-8") as f:
            yaml.dump(snapshot.to_dict(), f, allow_unicode=True, sort_keys=False)

        path_latest = self._snapshot_path(snapshot.task_id)
        with open(path_latest, "w", encoding="utf-8") as f:
            yaml.dump(snapshot.to_dict(), f, allow_unicode=True, sort_keys=False)

        self._cleanup_old_snapshots(snapshot.task_id)

    def _cleanup_old_snapshots(self, task_id: str, keep: int = 10) -> None:
        files = sorted(
            self.snapshots_dir.glob(f"{task_id}-*.yaml"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        # Exclude the -latest.yaml file from count
        to_delete = []
        non_latest = [f for f in files if not f.name.endswith("-latest.yaml")]
        if len(non_latest) > keep:
            to_delete = non_latest[keep:]
        for f in to_delete:
            f.unlink()

    def _next_sequence_number(self, task_id: str) -> int:
        prefix = f"{task_id}-"
        max_seq = 0
        for f in self.snapshots_dir.glob(f"{task_id}-*.yaml"):
            if f.name.endswith("-latest.yaml"):
                continue
            stem = f.name[:-5]  # remove .yaml
            if not stem.startswith(prefix):
                continue
            rest = stem[len(prefix):]
            parts = rest.rsplit("-", 1)
            if len(parts) == 2 and parts[1].isdigit():
                max_seq = max(max_seq, int(parts[1]))
        return max_seq + 1

    def load_snapshot(self, task_id: str) -> Snapshot:
        """Load the latest snapshot for a task."""
        path = self._snapshot_path(task_id)
        if not path.exists():
            raise StateMachineError(f"No snapshot found for task {task_id}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return Snapshot.from_dict(data)

    def build_recovery_prompt(self, snapshot: Snapshot) -> str:
        """Build a recovery prompt from snapshot data."""
        if snapshot.recovery_prompt:
            return snapshot.recovery_prompt

        lines = [
            f"You are resuming task {snapshot.task_id}.",
            f"Current state: {snapshot.current_state}",
        ]

        if snapshot.sandbox and snapshot.sandbox.worktree_path:
            lines.append(f"Sandbox: {snapshot.sandbox.worktree_path}")
            lines.append("You are inside a git worktree sandbox. Run git commands here.")

        lines.append("")

        pp = snapshot.plan_progress
        if pp.in_progress:
            step = pp.in_progress[0]
            lines.append(f"Current step ({step.step}/{pp.total_steps}): {step.description}")
            if step.started_at:
                lines.append(f"Started at: {step.started_at}")

        if pp.completed:
            lines.append("")
            lines.append("Completed steps:")
            for s in pp.completed:
                evidence = f" ({s.evidence})" if s.evidence else ""
                lines.append(f"  - Step {s.step}: {s.description}{evidence}")

        if pp.pending:
            lines.append("")
            lines.append("Pending steps:")
            for s in pp.pending:
                lines.append(f"  - Step {s.step}: {s.description}")

        lines.extend([
            "",
            "Key constraints: Follow simplicity-first and surgical-changes invariants.",
            "Do NOT re-execute completed steps. Continue from the current step.",
        ])

        return "\n".join(lines)

    def load_required_context(self, snapshot: Snapshot, repo_root: str | None = None) -> dict[str, Any]:
        """Load files, memories, and plans referenced in snapshot."""
        root = Path(repo_root) if repo_root else Path(".")
        result: dict[str, Any] = {"files": {}, "memories": {}, "plans": {}}

        for rel_path in snapshot.required_context.files:
            path = root / rel_path
            if path.exists():
                result["files"][rel_path] = path.read_text(encoding="utf-8")
            else:
                result["files"][rel_path] = None

        for rel_path in snapshot.required_context.memories:
            path = root / rel_path
            if path.exists():
                result["memories"][rel_path] = path.read_text(encoding="utf-8")
            else:
                result["memories"][rel_path] = None

        for rel_path in snapshot.required_context.plans:
            path = root / rel_path
            if path.exists():
                result["plans"][rel_path] = path.read_text(encoding="utf-8")
            else:
                result["plans"][rel_path] = None

        return result
