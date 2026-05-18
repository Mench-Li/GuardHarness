"""Agent-Guard state machine core.

Implements an 8-state finite state machine for controlling AI agent execution.

Mainline states:
  Inbox → Plan Ready → Executing → Patch Ready → Entropy Review → Done

Bypass states:
  Blocked        — external dependency / waiting for human input
  Needs Simplification — Entropy Review failed, needs rework
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class State(enum.Enum):
    INBOX = "Inbox"
    PLAN_READY = "Plan Ready"
    EXECUTING = "Executing"
    PATCH_READY = "Patch Ready"
    ENTROPY_REVIEW = "Entropy Review"
    DONE = "Done"
    BLOCKED = "Blocked"
    NEEDS_SIMPLIFICATION = "Needs Simplification"


# Terminal states cannot be resumed from; they end the task lifecycle.
TERMINAL_STATES = {State.DONE}

# Valid transitions: current_state -> {allowed_next_states}
VALID_TRANSITIONS: dict[State, set[State]] = {
    State.INBOX: {State.PLAN_READY, State.BLOCKED},
    State.PLAN_READY: {State.EXECUTING, State.NEEDS_SIMPLIFICATION, State.BLOCKED, State.INBOX},
    State.EXECUTING: {State.PATCH_READY, State.BLOCKED},
    State.PATCH_READY: {State.ENTROPY_REVIEW, State.BLOCKED},
    State.ENTROPY_REVIEW: {State.DONE, State.NEEDS_SIMPLIFICATION, State.BLOCKED},
    State.NEEDS_SIMPLIFICATION: {State.EXECUTING, State.PLAN_READY},
    State.BLOCKED: {
        State.INBOX,
        State.PLAN_READY,
        State.EXECUTING,
        State.PATCH_READY,
        State.ENTROPY_REVIEW,
        State.DONE,
        State.NEEDS_SIMPLIFICATION,
    },
    State.DONE: set(),
}

# Gate mapping: (from_state, to_state) -> list of gate names
GATE_REQUIREMENTS: dict[tuple[State, State], list[str]] = {
    (State.INBOX, State.PLAN_READY): ["g1_plan_valid", "g2_complexity_budget"],
    (State.PLAN_READY, State.EXECUTING): ["g3_entropy_check"],
    (State.EXECUTING, State.PATCH_READY): ["g4_surgical_check"],
    (State.ENTROPY_REVIEW, State.DONE): ["g5_verification_proof"],
    (State.NEEDS_SIMPLIFICATION, State.EXECUTING): ["g3_entropy_check"],
}

# Gate severity: True = hard blocking (transition rejected), False = advisory (warning logged)
GATE_BLOCKING: dict[str, bool] = {
    "g1_plan_valid": True,
    "g2_complexity_budget": False,
    "g3_entropy_check": True,
    "g4_surgical_check": True,
    "g5_verification_proof": True,
}


@dataclass
class StateTransition:
    from_state: State
    to_state: State
    timestamp: str
    gate_results: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class TaskState:
    task_id: str
    current_state: State
    history: list[StateTransition] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone(timedelta(hours=8))).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class StateMachineError(Exception):
    pass


class StateMachine:
    """Manages task state transitions with gate enforcement."""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(".harness/agent-guard")
        self.state_dir = self.base_dir / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _task_file(self, task_id: str) -> Path:
        return self.state_dir / f"{task_id}-state.json"

    def _registry_file(self) -> Path:
        return self.state_dir / "registry.json"

    def init_task(self, task_id: str, metadata: dict[str, Any] | None = None) -> TaskState:
        """Create a new task in Inbox state."""
        if self._task_file(task_id).exists():
            raise StateMachineError(f"Task {task_id} already exists")

        task = TaskState(
            task_id=task_id,
            current_state=State.INBOX,
            metadata=metadata or {},
        )
        self._save_task(task)
        self._update_registry(task_id, State.INBOX)
        return task

    def get_task(self, task_id: str) -> TaskState:
        """Load task state from disk."""
        path = self._task_file(task_id)
        if not path.exists():
            raise StateMachineError(f"Task {task_id} not found")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return TaskState(
            task_id=data["task_id"],
            current_state=State(data["current_state"]),
            history=[
                StateTransition(
                    from_state=State(t["from_state"]),
                    to_state=State(t["to_state"]),
                    timestamp=t["timestamp"],
                    gate_results=t.get("gate_results", {}),
                    reason=t.get("reason", ""),
                )
                for t in data.get("history", [])
            ],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            metadata=data.get("metadata", {}),
        )

    def transition(
        self,
        task_id: str,
        to_state: State,
        gate_results: dict[str, Any] | None = None,
        reason: str = "",
        skip_gates: bool = False,
    ) -> TaskState:
        """Attempt to transition a task to a new state."""
        task = self.get_task(task_id)
        from_state = task.current_state

        # Check transition validity
        if to_state not in VALID_TRANSITIONS.get(from_state, set()):
            allowed = ", ".join(s.value for s in VALID_TRANSITIONS.get(from_state, set()))
            raise StateMachineError(
                f"Invalid transition from {from_state.value} to {to_state.value}. "
                f"Allowed: {allowed}"
            )

        # Check gates unless skipped
        if not skip_gates:
            required = GATE_REQUIREMENTS.get((from_state, to_state), [])
            for gate_name in required:
                result = (gate_results or {}).get(gate_name)
                if not result or not result.get("passed", False):
                    is_blocking = GATE_BLOCKING.get(gate_name, True)
                    detail = result.get("message", "") if result else "Gate not executed"
                    if is_blocking:
                        raise StateMachineError(
                            f"Gate {gate_name} blocked transition {from_state.value} -> {to_state.value}: {detail}"
                        )
                    # Advisory gate failure is recorded but does not block transition

        # Record transition
        transition = StateTransition(
            from_state=from_state,
            to_state=to_state,
            timestamp=datetime.now(timezone(timedelta(hours=8))).isoformat(),
            gate_results=gate_results or {},
            reason=reason,
        )
        task.history.append(transition)
        task.current_state = to_state
        task.updated_at = transition.timestamp

        # Track pre-blocked state for unblock recovery
        if to_state == State.BLOCKED:
            task.metadata["blocked_from"] = from_state.value
        elif from_state == State.BLOCKED and "blocked_from" in task.metadata:
            del task.metadata["blocked_from"]

        self._save_task(task)
        self._update_registry(task_id, to_state)
        return task

    def _save_task(self, task: TaskState) -> None:
        path = self._task_file(task.task_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "task_id": task.task_id,
                    "current_state": task.current_state.value,
                    "history": [
                        {
                            "from_state": t.from_state.value,
                            "to_state": t.to_state.value,
                            "timestamp": t.timestamp,
                            "gate_results": t.gate_results,
                            "reason": t.reason,
                        }
                        for t in task.history
                    ],
                    "created_at": task.created_at,
                    "updated_at": task.updated_at,
                    "metadata": task.metadata,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

    def _update_registry(self, task_id: str, state: State) -> None:
        registry: dict[str, Any] = {}
        path = self._registry_file()
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                registry = json.load(f)

        entry = registry.get(task_id, {})
        if isinstance(entry, str):
            entry = {"state": entry}
        entry["state"] = state.value

        # Store parent-child relationships
        task = self.get_task(task_id)
        parent = task.metadata.get("parent")
        if parent:
            entry["parent"] = parent
            # Update parent's children list
            parent_entry = registry.get(parent, {})
            if isinstance(parent_entry, str):
                parent_entry = {"state": parent_entry}
            children = set(parent_entry.get("children", []))
            children.add(task_id)
            parent_entry["children"] = sorted(children)
            registry[parent] = parent_entry

        registry[task_id] = entry
        with open(path, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)

    def list_tasks(self, state_filter: State | None = None) -> list[TaskState]:
        """List all tasks, optionally filtered by state."""
        tasks = []
        for path in self.state_dir.glob("*-state.json"):
            if path.name == "registry.json":
                continue
            task = self.get_task(path.stem.replace("-state", ""))
            if state_filter is None or task.current_state == state_filter:
                tasks.append(task)
        return sorted(tasks, key=lambda t: t.updated_at, reverse=True)

    def get_children(self, parent_id: str) -> list[str]:
        """Return child task IDs for a given parent from registry."""
        path = self._registry_file()
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            registry = json.load(f)
        parent_entry = registry.get(parent_id, {})
        if isinstance(parent_entry, str):
            parent_entry = {"state": parent_entry}
        return parent_entry.get("children", [])

    def is_recoverable(self, task_id: str) -> bool:
        """Check if a task can be resumed after interruption."""
        try:
            task = self.get_task(task_id)
            return task.current_state not in TERMINAL_STATES
        except StateMachineError:
            return False
