"""Gate implementations for Agent-Guard.

Each gate is a veto-powered state transition check.
A gate returns {"passed": bool, "message": str, "details": dict}.
If passed is False, the transition is physically blocked.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from state_machine import GATE_BLOCKING, StateMachine, StateMachineError


def g1_plan_valid(task_id: str, plan_path: str | None = None, **kwargs: Any) -> dict[str, Any]:
    """G1: Validate plan against plan-schema.yaml constraints.

    Checks:
    - Required sections present (task_description, file_changes, test_plan, verification_command, success_criteria)
    - No TODO/FIXME/TBD/XXX placeholders
    - No vague words (适当, 可能, 考虑, 稍后, 大概, 尽量)
    """
    errors: list[str] = []
    warnings: list[str] = []

    if plan_path is None:
        # Guess plan path from conventions
        candidates = [
            f"docs/superpowers/plans/{task_id}-plan.md",
            f"docs/superpowers/plans/{task_id}.md",
        ]
        for c in candidates:
            if Path(c).exists():
                plan_path = c
                break

    if not plan_path or not Path(plan_path).exists():
        return {
            "passed": False,
            "message": f"Plan file not found for task {task_id}. Expected one of: {candidates}",
            "details": {"errors": ["missing_plan"]},
            "blocking": GATE_BLOCKING.get("g1_plan_valid", True),
        }

    content = Path(plan_path).read_text(encoding="utf-8")
    lower = content.lower()

    # Required sections
    required_sections = [
        "task_description",
        "file_changes",
        "test_plan",
        "verification_command",
        "success_criteria",
        "state_diagram",
        "gate_checkpoints",
    ]
    for sec in required_sections:
        if sec not in lower and sec.replace("_", " ") not in lower:
            errors.append(f"Missing required section: {sec}")

    # Placeholder check
    # Require a non-word, non-hyphen char before the marker to avoid
    # false positives on patterns like TASK-xxx (a common task-id placeholder).
    placeholders = re.findall(r"(?<![-\w])(TODO|TBD|FIXME|XXX)\b", content, re.IGNORECASE)
    if placeholders:
        errors.append(f"Found placeholders: {set(placeholders)}")

    # Vague words check
    vague_pattern = r"(适当|可能|考虑|稍后|大概|尽量|maybe|perhaps|later|sometime)"
    vague_matches = re.findall(vague_pattern, content, re.IGNORECASE)
    if vague_matches:
        errors.append(f"Found vague words: {set(vague_matches)}")

    # TDD sequence check (heuristic)
    has_code_files = bool(re.search(r"`[^`]+\.(py|js|ts|go|rs|java|md|sh)`", content))
    if has_code_files:
        tdd_stages = [
            r"(?:写|write).{0,10}(?:测试|test)",
            r"(?:运行|run|确认).{0,10}(?:失败|fail)",
            r"(?:写|write|最小).{0,10}(?:实现|implement)",
            r"(?:运行|run|确认).{0,10}(?:通过|pass)",
        ]
        missing_stages = []
        for i, pattern in enumerate(tdd_stages, 1):
            if not re.search(pattern, content, re.IGNORECASE):
                missing_stages.append(f"stage_{i}")
        if missing_stages:
            errors.append(f"TDD sequence incomplete: missing {missing_stages}")

    passed = len(errors) == 0
    return {
        "passed": passed,
        "message": "Plan validation passed" if passed else f"Plan validation failed: {'; '.join(errors)}",
        "details": {
            "errors": errors,
            "warnings": warnings,
            "plan_path": plan_path,
        },
        "blocking": GATE_BLOCKING.get("g1_plan_valid", True),
    }


def g2_complexity_budget(task_id: str, plan_path: str | None = None, **kwargs: Any) -> dict[str, Any]:
    """G2: Check complexity budget before execution.

    Phase 1 simplified: counts estimated file changes and steps.
    Full version would parse plan structure for precise metrics.
    """
    warnings: list[str] = []

    if plan_path is None:
        candidates = [
            f"docs/superpowers/plans/{task_id}-plan.md",
            f"docs/superpowers/plans/{task_id}.md",
        ]
        for c in candidates:
            if Path(c).exists():
                plan_path = c
                break

    if not plan_path or not Path(plan_path).exists():
        return {
            "passed": True,  # Soft gate in phase 1
            "message": "Plan file not found; skipping complexity check",
            "details": {"warnings": ["missing_plan"]},
            "blocking": GATE_BLOCKING.get("g2_complexity_budget", False),
        }

    content = Path(plan_path).read_text(encoding="utf-8")

    # Count file references (heuristic)
    file_refs = set(re.findall(r"`([^`]+\.(tsx|jsx|yaml|yml|html|toml|json|java|css|py|js|ts|go|rs|md|sh))`", content))
    step_count = len(re.findall(r"^\s*[-*]\s+\d+\.", content, re.MULTILINE))
    if step_count == 0:
        step_count = len(re.findall(r"^\s*[-*]\s+", content, re.MULTILINE))

    max_files = kwargs.get("max_files", 20)
    max_steps = kwargs.get("max_steps", 15)

    if len(file_refs) > max_files:
        warnings.append(f"Estimated file changes ({len(file_refs)}) exceeds budget ({max_files})")
    if step_count > max_steps:
        warnings.append(f"Estimated steps ({step_count}) exceeds budget ({max_steps})")

    # Phase 1: warn but don't block
    passed = len(warnings) == 0
    return {
        "passed": passed,
        "message": "Complexity within budget" if passed else f"Complexity warnings: {'; '.join(warnings)}",
        "details": {
            "estimated_files": len(file_refs),
            "estimated_steps": step_count,
            "warnings": warnings,
        },
        "blocking": GATE_BLOCKING.get("g2_complexity_budget", False),
    }


def g3_entropy_check(task_id: str, **kwargs: Any) -> dict[str, Any]:
    """G3: Run detect-entropy.sh and block if new entropy patterns found."""
    script_path = ".claude/scripts/detect-entropy.sh"
    if not Path(script_path).exists():
        return {
            "passed": True,
            "message": "detect-entropy.sh not found; skipping entropy check",
            "details": {"warnings": ["missing_script"]},
            "blocking": GATE_BLOCKING.get("g3_entropy_check", True),
        }

    try:
        result = subprocess.run(
            ["bash", script_path, "1"],  # Check last 1 day for current task scope
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as e:
        return {
            "passed": False,
            "message": f"Entropy check script failed: {e}",
            "details": {"error": str(e)},
            "blocking": GATE_BLOCKING.get("g3_entropy_check", True),
        }

    output = result.stdout + result.stderr

    # Look for warning indicators in output
    warnings = re.findall(r"⚠️\s+(.+)", output)
    matches = re.findall(r"🔁\s+(.+)", output)

    passed = len(warnings) == 0 and len(matches) == 0
    return {
        "passed": passed,
        "message": "No entropy detected" if passed else f"Entropy detected: {'; '.join(warnings + matches)}",
        "details": {
            "warnings": warnings,
            "pattern_matches": matches,
            "raw_output": output[:2000],  # Truncate for storage
        },
        "blocking": GATE_BLOCKING.get("g3_entropy_check", True),
    }


def _get_sandbox_cwd(task_id: str) -> str:
    """获取任务对应的 sandbox 工作目录，优先使用 snapshot 中记录的路径。

    对非 Done 任务，若 snapshot 缺失或路径无效，抛出 RuntimeError 而非静默回退到 "."。
    """
    import os
    from snapshot import SnapshotManager
    from state_machine import StateMachine, State

    sm = StateMachine()
    try:
        task = sm.get_task(task_id)
        is_done = task.current_state == State.DONE
    except Exception:
        is_done = False

    snap_mgr = SnapshotManager()
    try:
        snap = snap_mgr.load_snapshot(task_id)
        if snap.sandbox and snap.sandbox.no_sandbox:
            return os.getcwd()
        if snap.sandbox and snap.sandbox.worktree_path:
            path = Path(snap.sandbox.worktree_path)
            if path.exists():
                result = subprocess.run(
                    ["git", "rev-parse", "--is-inside-work-tree"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=str(path),
                )
                if result.returncode == 0 and result.stdout.strip() == "true":
                    return str(path)
    except Exception:
        pass

    from sandbox import SandboxManager
    mgr = SandboxManager()
    sandbox = mgr.get_sandbox(task_id)
    if sandbox:
        return str(mgr._worktree_path(task_id))

    if is_done:
        return os.getcwd()

    raise RuntimeError(
        f"Task {task_id} is not Done and has no valid sandbox snapshot or worktree. "
        f"Cannot determine working directory."
    )


def g4_surgical_check(task_id: str, plan_path: str | None = None, **kwargs: Any) -> dict[str, Any]:
    cwd = _get_sandbox_cwd(task_id)

    try:
        # Collect modified files: staged + unstaged + untracked
        modified: set[str] = set()

        for diff_cmd in (["git", "diff", "--name-only", "--cached"], ["git", "diff", "--name-only"]):
            result = subprocess.run(
                diff_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=cwd if cwd != "." else None,
            )
            if result.returncode != 0:
                return {
                    "passed": False,
                    "message": f"Git diff failed: {result.stderr}",
                    "details": {"error": result.stderr},
                    "blocking": True,
                }
            modified.update(line.strip() for line in result.stdout.splitlines() if line.strip())

        # Untracked files
        untracked_result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd if cwd != "." else None,
        )
        if untracked_result.returncode != 0:
            return {
                "passed": False,
                "message": f"Git ls-files failed: {untracked_result.stderr}",
                "details": {"error": untracked_result.stderr},
                "blocking": True,
            }
        modified.update(line.strip() for line in untracked_result.stdout.splitlines() if line.strip())

        # Filter out Agent-Guard internal runtime artifacts and current task plan metadata
        runtime_prefixes = (
            ".harness/agent-guard/state/",
            ".harness/agent-guard/snapshots/",
            ".harness/agent-guard/leases/",
        )
        modified = {f for f in modified if not f.startswith(runtime_prefixes)}
        # Only exempt the current task's own plan files, not all plans
        own_plan_prefixes = (
            f"docs/superpowers/plans/{task_id}-plan.md",
            f"docs/superpowers/plans/{task_id}.md",
        )
        modified = {f for f in modified if not f.startswith(own_plan_prefixes)}

    except Exception as e:
        return {
            "passed": False,
            "message": f"Git diff failed: {e}",
            "details": {"error": str(e)},
            "blocking": True,
        }

    if not modified:
        return {
            "passed": True,
            "message": "No uncommitted changes",
            "details": {"modified_files": []},
            "blocking": True,
        }

    # Load allowed files from plan (strictly within file_changes section)
    allowed_files: set[str] = set()
    if plan_path is None:
        candidates = [
            f"docs/superpowers/plans/{task_id}-plan.md",
            f"docs/superpowers/plans/{task_id}.md",
        ]
        for c in candidates:
            if Path(c).exists():
                plan_path = c
                break

    if plan_path and Path(plan_path).exists():
        content = Path(plan_path).read_text(encoding="utf-8")
        in_file_changes = False
        for line in content.splitlines():
            lower = line.lower()
            if "file_changes" in lower or "file changes" in lower:
                in_file_changes = True
                continue
            if in_file_changes:
                # Stop at next section header
                if line.startswith("## ") or line.startswith("# "):
                    break
                m = re.search(r"[-*]\s+`?([^`\n]+\.(tsx|jsx|yaml|yml|html|toml|json|java|css|py|js|ts|go|rs|md|sh))`?", line)
                if m:
                    allowed_files.add(m.group(1))

    off_plan = [f for f in sorted(modified) if f not in allowed_files]

    if off_plan:
        return {
            "passed": False,
            "message": f"Off-plan file modifications detected: {off_plan}",
            "details": {"modified_files": sorted(modified), "off_plan": off_plan, "allowed_files": list(allowed_files)},
            "blocking": True,
        }

    return {
        "passed": True,
        "message": "All modified files are within plan scope",
        "details": {"modified_files": sorted(modified), "allowed_files": list(allowed_files)},
        "blocking": True,
    }


def g5_verification_proof(task_id: str, verification_command: str | None = None, cwd: str | None = None, **kwargs: Any) -> dict[str, Any]:
    """G5: Run verification command and verify success.

    Expects verification_command from plan or kwargs.
    """
    if verification_command is None:
        # Try to extract from plan
        candidates = [
            f"docs/superpowers/plans/{task_id}-plan.md",
            f"docs/superpowers/plans/{task_id}.md",
        ]
        for c in candidates:
            if Path(c).exists():
                content = Path(c).read_text(encoding="utf-8")
                # Prefer explicit header-style verification_command (last occurrence wins)
                matches = list(re.finditer(r"##\s*verification_command\s*\n+(.+?)(?:\n\n|\n##|$)", content, re.DOTALL))
                match = matches[-1] if matches else None
                if not match:
                    # Fallback: fenced code block after verification section
                    match = re.search(r"[Vv]erification[^\n]*[\n\r]+```[^\n]*\n([^`]+)```", content)
                if not match:
                    # Fallback: inline command after Run:
                    match = re.search(r"[Rr]un:\s*`?([^`\n]+)`?", content)
                if match:
                    verification_command = match.group(1).strip()
                    # Strip fenced code block markers if present
                    verification_command = re.sub(r"^```\w*\s*", "", verification_command)
                    verification_command = re.sub(r"\s*```$", "", verification_command)
                    verification_command = verification_command.strip()
                break

    if not verification_command:
        return {
            "passed": False,
            "message": "No verification command found in plan",
            "details": {"errors": ["missing_verification_command"]},
            "blocking": GATE_BLOCKING.get("g5_verification_proof", True),
        }

    if cwd is None:
        cwd = _get_sandbox_cwd(task_id)

    try:
        result = subprocess.run(
            verification_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=cwd if cwd != "." else None,
        )
    except Exception as e:
        return {
            "passed": False,
            "message": f"Verification command failed to execute: {e}",
            "details": {"error": str(e), "command": verification_command},
            "blocking": GATE_BLOCKING.get("g5_verification_proof", True),
        }

    passed = result.returncode == 0
    if not passed:
        return {
            "passed": False,
            "message": f"Verification failed (exit {result.returncode})",
            "details": {
                "command": verification_command,
                "exit_code": result.returncode,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:2000],
            },
            "blocking": GATE_BLOCKING.get("g5_verification_proof", True),
        }

    # Proof of work checks from finishing-policy.yaml
    policy_path = Path(".harness/superpowers/finishing-policy.yaml")
    if policy_path.exists():
        try:
            import yaml
            policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
            pow_checks = policy.get("proof_of_work", [])
            for check in pow_checks:
                check_cmd = check.get("command", "")
                check_name = check.get("name", "unnamed")
                check_type = check.get("type", "")

                if not check_cmd and check_type == "ci_status":
                    check_cmd = "python -c \"import os, sys; sys.exit(0 if (os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS')) else 1)\""

                if not check_cmd:
                    continue

                check_result = subprocess.run(
                    check_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    cwd=cwd if cwd and cwd != "." else None,
                )

                # Parse type-specific results
                if check_type == "test_coverage":
                    match = re.search(r'(\d+)%', check_result.stdout + check_result.stderr)
                    if match:
                        coverage = int(match.group(1))
                        threshold = check.get("threshold", 80)
                        if coverage < threshold:
                            return {
                                "passed": False,
                                "message": f"Proof of work '{check_name}' failed: coverage {coverage}% < threshold {threshold}%",
                                "details": {
                                    "command": check_cmd,
                                    "coverage": coverage,
                                    "threshold": threshold,
                                    "stdout": check_result.stdout[:2000],
                                    "stderr": check_result.stderr[:2000],
                                },
                                "blocking": GATE_BLOCKING.get("g5_verification_proof", True),
                            }
                    elif check_result.returncode != 0:
                        return {
                            "passed": False,
                            "message": f"Proof of work '{check_name}' failed (exit {check_result.returncode})",
                            "details": {"command": check_cmd, "stdout": check_result.stdout[:2000], "stderr": check_result.stderr[:2000]},
                            "blocking": GATE_BLOCKING.get("g5_verification_proof", True),
                        }
                elif check_type == "complexity_analysis":
                    match = re.search(r'Average complexity:\s*(\d+\.?\d*)', check_result.stdout + check_result.stderr)
                    if match:
                        avg_cc = float(match.group(1))
                        max_cc = check.get("max_cyclomatic", 10)
                        if avg_cc > max_cc:
                            return {
                                "passed": False,
                                "message": f"Proof of work '{check_name}' failed: avg complexity {avg_cc} > max {max_cc}",
                                "details": {
                                    "command": check_cmd,
                                    "average_complexity": avg_cc,
                                    "max_cyclomatic": max_cc,
                                    "stdout": check_result.stdout[:2000],
                                    "stderr": check_result.stderr[:2000],
                                },
                                "blocking": GATE_BLOCKING.get("g5_verification_proof", True),
                            }
                    elif check_result.returncode != 0:
                        return {
                            "passed": False,
                            "message": f"Proof of work '{check_name}' failed (exit {check_result.returncode})",
                            "details": {"command": check_cmd, "stdout": check_result.stdout[:2000], "stderr": check_result.stderr[:2000]},
                            "blocking": GATE_BLOCKING.get("g5_verification_proof", True),
                        }
                elif check_result.returncode != 0:
                    return {
                        "passed": False,
                        "message": f"Proof of work '{check_name}' failed (exit {check_result.returncode})",
                        "details": {"command": check_cmd, "stdout": check_result.stdout[:2000], "stderr": check_result.stderr[:2000]},
                        "blocking": GATE_BLOCKING.get("g5_verification_proof", True),
                    }
        except Exception as e:
            print(f"[WARN] finishing-policy.yaml unreadable ({e}); degrading to default policy.", file=sys.stderr)

    return {
        "passed": True,
        "message": "Verification passed",
        "details": {
            "command": verification_command,
            "exit_code": result.returncode,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:2000],
        },
        "blocking": GATE_BLOCKING.get("g5_verification_proof", True),
    }


GATE_REGISTRY: dict[str, Any] = {
    "g1_plan_valid": g1_plan_valid,
    "g2_complexity_budget": g2_complexity_budget,
    "g3_entropy_check": g3_entropy_check,
    "g4_surgical_check": g4_surgical_check,
    "g5_verification_proof": g5_verification_proof,
}


def run_gate(gate_name: str, task_id: str, **kwargs: Any) -> dict[str, Any]:
    """Run a single gate by name."""
    if gate_name not in GATE_REGISTRY:
        return {
            "passed": False,
            "message": f"Unknown gate: {gate_name}",
            "details": {},
            "blocking": GATE_BLOCKING.get(gate_name, True),
        }
    try:
        return GATE_REGISTRY[gate_name](task_id, **kwargs)
    except Exception as exc:
        import traceback
        return {
            "gate": gate_name,
            "passed": False,
            "message": f"Gate execution failed: {exc}",
            "details": {"traceback": traceback.format_exc()},
            "blocking": GATE_BLOCKING.get(gate_name, True),
        }
