#!/usr/bin/env python3
"""Parse slash commands from user input and inject systemMessage.

Hook into Claude Code's user_prompt_submit to intercept commands like
/init-feature, /plan-feature, etc.

Usage in .claude/settings.json:
  "hooks": {
    "user_prompt_submit": [
      ".claude/scripts/parse-slash-command.ps1"
    ]
  }
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_CONSTRAINT_PREFIX = (
    "Before loading any skill, you MUST read: "
    "1. .harness/team/shared-axioms.md "
    "2. .harness/team/standards.md "
    "3. .claude/memory/MEMORY.md (if exists). "
)

COMMANDS: dict[str, str] = {
    "/init-feature": (
        "[Harness] /init-feature detected. "
        + _CONSTRAINT_PREFIX
        + "You MUST invoke the brainstorming skill via the Skill tool and follow its workflow exactly. "
        "Ask clarifying questions one at a time, propose 2-3 solutions with trade-offs, "
        "clearly mark the simplest option, and save the final spec to docs/superpowers/specs/. "
        "After completion, run: python .harness/agent-guard/cli.py init TASK-001 --spec docs/superpowers/specs/feature.md"
    ),
    "/plan-feature": (
        "[Harness] /plan-feature detected. "
        + _CONSTRAINT_PREFIX
        + "You MUST invoke the writing-plans skill via the Skill tool. "
        "Read the provided spec, create an implementation plan following plan-schema.yaml constraints, "
        "ensure every task has a verifiable goal (Goal + Verify), no 待办占位符 or placeholders, "
        "and save the plan to docs/superpowers/plans/. "
        "After completion, run: python .harness/agent-guard/cli.py plan TASK-001 --approve"
    ),
    "/execute-plan": (
        "[Harness] /execute-plan detected. "
        + _CONSTRAINT_PREFIX
        + "Determine complexity: if many independent tasks, invoke subagent-driven-development skill; "
        "otherwise invoke executing-plans skill. Execute step by step, run tests after each task, "
        "stop and report on failure, and verify diff only touches planned files (no drive-by refactoring). "
        "After completion, run: python .harness/agent-guard/cli.py execute TASK-001"
    ),
    "/finish-branch": (
        "[Harness] /finish-branch detected. "
        + _CONSTRAINT_PREFIX
        + "You MUST invoke the finishing-a-development-branch skill. "
        "Run full test suite, check coverage (threshold 80%), run linter, read finishing-policy.yaml, "
        "and auto-decide merge / PR / keep_branch. Then write observation and update CLAUDE.md. "
        "After completion, run: python .harness/agent-guard/cli.py finish TASK-001"
    ),
    "/fix-bug": (
        "[Harness] /fix-bug detected. "
        + _CONSTRAINT_PREFIX
        + "First invoke systematic-debugging skill to find root cause, "
        "then invoke test-driven-development skill to write a failing test before fixing. "
        "Keep the fix minimal, no over-engineering, and write a failure observation afterwards. "
        "After completion, run: python .harness/agent-guard/cli.py finish TASK-001"
    ),
    "/reflect": (
        "[Harness] /reflect detected. "
        + _CONSTRAINT_PREFIX
        + "You MUST invoke the memory-reflection skill. "
        "Scan all observations, extract stable patterns, update CLAUDE.md dynamic blocks, "
        "detect cross-project patterns to upgrade to global axioms, and record reflection cost metrics."
    ),
}


def _debug_log(msg: str) -> None:
    script_dir = Path(__file__).resolve().parent
    log_file = script_dir / "hook-debug.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{__import__('datetime').datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def main() -> int:
    _debug_log("Hook invoked")

    # Claude Code passes user message via env var or stdin
    msg = os.environ.get("CLAUDE_USER_MESSAGE", "")
    source = "env"
    if not msg:
        try:
            msg = sys.stdin.read()
            source = "stdin"
        except Exception as e:
            _debug_log(f"stdin read error: {e}")
            msg = ""

    msg_stripped = msg.strip()
    _debug_log(f"Message source={source}, len={len(msg_stripped)}, content={msg_stripped[:80]!r}")

    for cmd, system_msg in COMMANDS.items():
        if msg_stripped.startswith(cmd):
            payload = json.dumps({"systemMessage": system_msg}, ensure_ascii=False)
            _debug_log(f"Matched {cmd}, injecting systemMessage")
            print(payload)
            return 0

    _debug_log("No command matched, emitting empty JSON")
    print("{}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        _debug_log(f"Unhandled exception: {e}")
        print("{}")
        sys.exit(0)
