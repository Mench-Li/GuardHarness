"""Doctor: consistency check and repair for Agent-Guard state."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from state_machine import State, StateMachine


class Doctor:
    def __init__(self, base_dir: str = ".harness/agent-guard"):
        self.base_dir = Path(base_dir)
        self.sm = StateMachine(str(self.base_dir))

    def check_all(self, task_id: str | None = None, fix: bool = False) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        registry = self._load_registry()
        task_ids = [task_id] if task_id else list(registry.keys())

        r = self._check_missing_proof_of_work_tool()
        if r:
            results.append(r)

        for tid in task_ids:
            entry = registry.get(tid, {})
            r = self._check_archived_state_mismatch(tid, entry, fix)
            if r:
                results.append(r)
            r = self._check_lease_orphan(tid, fix)
            if r:
                results.append(r)
            r = self._check_task_file_registry_divergence(tid, entry)
            if r:
                results.append(r)
            r = self._check_snapshot_sandbox_stale(tid)
            if r:
                results.append(r)
            r = self._check_parent_children_state_sync(tid, entry, registry, fix)
            if r:
                results.append(r)

        return results

    def _load_registry(self) -> dict[str, Any]:
        path = self.sm._registry_file()
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_registry(self, registry: dict[str, Any]) -> None:
        path = self.sm._registry_file()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)

    def _check_archived_state_mismatch(self, task_id: str, entry: dict[str, Any], fix: bool) -> dict[str, Any] | None:
        if not entry.get("archived"):
            return None
        if entry.get("state") == "Done":
            return None
        result = {
            "task_id": task_id,
            "check": "archived_state_mismatch",
            "level": "error",
            "message": f"Registry state is {entry.get('state')} but task is archived; expected Done",
            "fixed": False,
        }
        if fix:
            registry = self._load_registry()
            if task_id in registry:
                registry[task_id]["state"] = "Done"
                self._save_registry(registry)
                result["fixed"] = True
                result["message"] += " [FIXED]"
        return result

    def _check_lease_orphan(self, task_id: str, fix: bool) -> dict[str, Any] | None:
        from lease import LeaseManager
        lm = LeaseManager(str(self.base_dir))
        lease = lm.get_lease(task_id)
        if not lease:
            return None
        try:
            task = self.sm.get_task(task_id)
            if task.current_state not in (State.DONE,):
                return None
        except Exception:
            pass
        result = {
            "task_id": task_id,
            "check": "lease_orphan",
            "level": "warning",
            "message": f"Lease exists for task {task_id} but task is Done",
            "fixed": False,
        }
        if fix:
            lm.force_release(task_id)
            result["fixed"] = True
            result["message"] += " [FIXED]"
        return result

    def _check_task_file_registry_divergence(self, task_id: str, entry: dict[str, Any]) -> dict[str, Any] | None:
        task_file = self.sm._task_file(task_id)
        has_registry = bool(entry)
        has_file = task_file.exists()
        if has_registry and has_file:
            return None
        if not has_registry and not has_file:
            return None
        return {
            "task_id": task_id,
            "check": "task_file_registry_divergence",
            "level": "error",
            "message": f"Registry={has_registry}, task_file={has_file}; mismatch detected",
            "fixed": False,
        }

    def _check_snapshot_sandbox_stale(self, task_id: str) -> dict[str, Any] | None:
        from snapshot import SnapshotManager
        snap_mgr = SnapshotManager(str(self.base_dir))
        try:
            snap = snap_mgr.load_snapshot(task_id)
        except Exception:
            return None
        if not snap.sandbox or not snap.sandbox.worktree_path:
            return None
        if snap.sandbox.no_sandbox:
            return None
        path = Path(snap.sandbox.worktree_path)
        if path.exists():
            return None
        try:
            task = self.sm.get_task(task_id)
            if task.current_state == State.DONE:
                return None
        except Exception:
            pass
        return {
            "task_id": task_id,
            "check": "snapshot_sandbox_stale",
            "level": "warning",
            "message": f"Snapshot sandbox path {snap.sandbox.worktree_path} does not exist",
            "fixed": False,
        }

    def _check_missing_proof_of_work_tool(self) -> dict[str, Any] | None:
        policy_path = self.base_dir.parent / "superpowers" / "finishing-policy.yaml"
        if not policy_path.exists():
            policy_path = self.base_dir / "superpowers" / "finishing-policy.yaml"
        if not policy_path.exists():
            return None
        try:
            import yaml
            policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        proof_of_work = policy.get("proof_of_work", [])
        missing: list[str] = []
        for item in proof_of_work:
            cmd = item.get("command", "")
            if "radon cc" in cmd and not shutil.which("radon"):
                missing.append("radon")
            if "--cov" in cmd:
                try:
                    import importlib.util
                    if importlib.util.find_spec("pytest_cov") is None:
                        missing.append("pytest-cov")
                except Exception:
                    missing.append("pytest-cov")
        if missing:
            unique_missing = sorted(set(missing))
            return {
                "task_id": "project",
                "check": "missing_proof_of_work_tool",
                "level": "warning",
                "message": f"Missing tools: {', '.join(unique_missing)}; install with: pip install {' '.join(unique_missing)}",
                "fixed": False,
            }
        return None

    def _check_parent_children_state_sync(
        self,
        task_id: str,
        entry: dict[str, Any],
        registry: dict[str, Any],
        fix: bool = False,
    ) -> dict[str, Any] | None:
        children = entry.get("children", [])
        if not children:
            return None
        children_states = [registry.get(cid, {}).get("state") for cid in children]
        if all(s == "Done" for s in children_states) and entry.get("state") != "Done":
            result = {
                "task_id": task_id,
                "check": "parent_children_state_sync",
                "level": "warning",
                "message": f"Children are all Done, but parent {task_id} is {entry.get('state')}",
                "fixed": False,
            }
            if fix:
                registry[task_id]["state"] = "Done"
                self._save_registry(registry)
                result["fixed"] = True
                result["message"] += " [FIXED]"
            return result
        return None
