#!/usr/bin/env python3
"""一次性脚本：归档 TASK-018 历史伪子任务。"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from state_machine import StateMachine


def main() -> None:
    sm = StateMachine()
    registry_path = sm._registry_file()
    if not registry_path.exists():
        print("Registry not found.")
        return

    with open(registry_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    archived_count = 0
    for task_id, entry in list(registry.items()):
        if (
            task_id.startswith("TASK-018-")
            and isinstance(entry, dict)
            and entry.get("parent") == "TASK-018"
        ):
            # Update registry
            entry["archived"] = True
            entry["archived_reason"] = "legacy_pseudo_task"
            registry[task_id] = entry

            # Update task state file if it exists
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
                        task_data["history"].append(
                            {
                                "from_state": from_state,
                                "to_state": "Done",
                                "timestamp": now,
                                "gate_results": {},
                                "reason": "Legacy pseudo task archived",
                            }
                        )
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
