#!/usr/bin/env python3
"""Archive legacy pseudo tasks with dry-run safety gate."""

import argparse
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from state_machine import StateMachine


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive legacy pseudo tasks")
    parser.add_argument("--task", default="TASK-018", help="Task prefix to archive (default: TASK-018)")
    parser.add_argument("--dry-run", action="store_true", help="Alias for default dry-run mode (no --apply)")
    parser.add_argument("--apply", action="store_true", help="Actually perform archive (default is dry-run)")
    parser.add_argument("--include-archived", action="store_true", help="Include already-archived tasks")
    args = parser.parse_args()

    if args.dry_run and args.apply:
        parser.error("--dry-run and --apply are mutually exclusive")

    sm = StateMachine()
    registry_path = sm._registry_file()
    if not registry_path.exists():
        print("Registry not found.")
        return

    with open(registry_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    targets = [
        (tid, entry) for tid, entry in registry.items()
        if tid.startswith(f"{args.task}-")
        and isinstance(entry, dict)
        and entry.get("parent") == args.task
        and (args.include_archived or not entry.get("archived"))
    ]

    if not args.apply:
        print(f"[DRY-RUN] Would archive {len(targets)} legacy pseudo task(s) for {args.task}")
        for tid, _ in targets:
            print(f"  - {tid}")
        print("Pass --apply to execute.")
        return

    # Backup registry before modification
    backup_path = registry_path.parent / f"registry.json.backup.{datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d%H%M%S')}"
    shutil.copy2(registry_path, backup_path)
    print(f"Backup created: {backup_path}")

    archived_count = 0
    for task_id, entry in targets:
        entry["archived"] = True
        entry["archived_reason"] = "legacy_pseudo_task"
        if entry.get("state") != "Done":
            entry["state"] = "Done"
        registry[task_id] = entry

        task_file = sm._task_file(task_id)
        if task_file.exists():
            try:
                with open(task_file, "r", encoding="utf-8") as f:
                    task_data = json.load(f)
                task_data["metadata"] = task_data.get("metadata", {})
                task_data["metadata"]["archived"] = True
                now = datetime.now(timezone(timedelta(hours=8))).isoformat()
                task_data["updated_at"] = now
                if task_data.get("current_state") != "Done":
                    from_state = task_data.get("current_state", "Inbox")
                    task_data["current_state"] = "Done"
                    task_data["history"] = task_data.get("history", [])
                    task_data["history"].append({
                        "from_state": from_state,
                        "to_state": "Done",
                        "timestamp": now,
                        "gate_results": {},
                        "reason": "Legacy pseudo task archived",
                    })
                with open(task_file, "w", encoding="utf-8") as f:
                    json.dump(task_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Warning: Could not update task file for {task_id}: {e}")

        archived_count += 1
        print(f"Archived {task_id}")

    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Archived {archived_count} legacy pseudo tasks.")


if __name__ == "__main__":
    main()
