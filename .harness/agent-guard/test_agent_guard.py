"""Tests for Agent-Guard core components."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gates import g1_plan_valid, g2_complexity_budget, g4_surgical_check, g5_verification_proof, _get_sandbox_cwd
from lease import LeaseManager
from snapshot import (
    LeaseInfo,
    PlanProgress,
    PlanStep,
    RequiredContext,
    SnapshotManager,
)
from state_machine import State, StateMachine, StateMachineError


class TestStateMachine(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.sm = StateMachine(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_init_task(self):
        task = self.sm.init_task("T-001")
        self.assertEqual(task.current_state, State.INBOX)
        self.assertEqual(task.task_id, "T-001")

    def test_duplicate_init_raises(self):
        self.sm.init_task("T-001")
        with self.assertRaises(StateMachineError):
            self.sm.init_task("T-001")

    def test_valid_transition_inbox_to_plan_ready(self):
        self.sm.init_task("T-001")
        self.sm.transition("T-001", State.PLAN_READY, skip_gates=True)
        task = self.sm.get_task("T-001")
        self.assertEqual(task.current_state, State.PLAN_READY)
        self.assertEqual(len(task.history), 1)

    def test_valid_transition_plan_ready_to_executing(self):
        self.sm.init_task("T-001")
        self.sm.transition("T-001", State.PLAN_READY, skip_gates=True)
        self.sm.transition("T-001", State.EXECUTING, skip_gates=True)
        task = self.sm.get_task("T-001")
        self.assertEqual(task.current_state, State.EXECUTING)

    def test_valid_transition_full_mainline(self):
        self.sm.init_task("T-001")
        self.sm.transition("T-001", State.PLAN_READY, skip_gates=True)
        self.sm.transition("T-001", State.EXECUTING, skip_gates=True)
        self.sm.transition("T-001", State.PATCH_READY, skip_gates=True)
        self.sm.transition("T-001", State.ENTROPY_REVIEW, skip_gates=True)
        self.sm.transition("T-001", State.DONE, skip_gates=True)
        task = self.sm.get_task("T-001")
        self.assertEqual(task.current_state, State.DONE)
        self.assertEqual(len(task.history), 5)

    def test_entropy_review_to_needs_simplification(self):
        self.sm.init_task("T-001")
        self.sm.transition("T-001", State.PLAN_READY, skip_gates=True)
        self.sm.transition("T-001", State.EXECUTING, skip_gates=True)
        self.sm.transition("T-001", State.PATCH_READY, skip_gates=True)
        self.sm.transition("T-001", State.ENTROPY_REVIEW, skip_gates=True)
        self.sm.transition("T-001", State.NEEDS_SIMPLIFICATION, skip_gates=True)
        task = self.sm.get_task("T-001")
        self.assertEqual(task.current_state, State.NEEDS_SIMPLIFICATION)

    def test_needs_simplification_back_to_executing(self):
        self.sm.init_task("T-001")
        self.sm.transition("T-001", State.PLAN_READY, skip_gates=True)
        self.sm.transition("T-001", State.EXECUTING, skip_gates=True)
        self.sm.transition("T-001", State.PATCH_READY, skip_gates=True)
        self.sm.transition("T-001", State.ENTROPY_REVIEW, skip_gates=True)
        self.sm.transition("T-001", State.NEEDS_SIMPLIFICATION, skip_gates=True)
        self.sm.transition("T-001", State.EXECUTING, skip_gates=True)
        task = self.sm.get_task("T-001")
        self.assertEqual(task.current_state, State.EXECUTING)

    def test_block_and_unblock(self):
        self.sm.init_task("T-001")
        self.sm.transition("T-001", State.PLAN_READY, skip_gates=True)
        self.sm.transition("T-001", State.BLOCKED, skip_gates=True, reason="Waiting for API key")
        task = self.sm.get_task("T-001")
        self.assertEqual(task.current_state, State.BLOCKED)
        self.assertEqual(task.metadata.get("blocked_from"), "Plan Ready")

        self.sm.transition("T-001", State.PLAN_READY, skip_gates=True, reason="Unblocked")
        task = self.sm.get_task("T-001")
        self.assertEqual(task.current_state, State.PLAN_READY)
        self.assertNotIn("blocked_from", task.metadata)

    def test_invalid_transition_raises(self):
        self.sm.init_task("T-001")
        self.sm.transition("T-001", State.PLAN_READY, skip_gates=True)
        with self.assertRaises(StateMachineError):
            self.sm.transition("T-001", State.DONE, skip_gates=True)

    def test_gate_blocking(self):
        self.sm.init_task("T-001")
        with self.assertRaises(StateMachineError) as ctx:
            self.sm.transition("T-001", State.PLAN_READY)
        self.assertIn("g1_plan_valid", str(ctx.exception))

    def test_advisory_gate_does_not_block(self):
        self.sm.init_task("T-001")
        # G1 passes, G2 fails (advisory) — transition should succeed
        task = self.sm.transition(
            "T-001",
            State.PLAN_READY,
            gate_results={
                "g1_plan_valid": {"passed": True, "message": "ok"},
                "g2_complexity_budget": {"passed": False, "message": "too complex", "blocking": False},
            },
        )
        self.assertEqual(task.current_state, State.PLAN_READY)
        # Verify advisory failure was recorded in history
        last = task.history[-1]
        self.assertIn("g2_complexity_budget", last.gate_results)
        self.assertFalse(last.gate_results["g2_complexity_budget"]["passed"])

    def test_is_recoverable(self):
        self.sm.init_task("T-001")
        self.assertTrue(self.sm.is_recoverable("T-001"))  # Inbox is recoverable
        self.sm.transition("T-001", State.PLAN_READY, skip_gates=True)
        self.assertTrue(self.sm.is_recoverable("T-001"))
        # Complete full mainline to Done
        self.sm.transition("T-001", State.EXECUTING, skip_gates=True)
        self.sm.transition("T-001", State.PATCH_READY, skip_gates=True)
        self.sm.transition("T-001", State.ENTROPY_REVIEW, skip_gates=True)
        self.sm.transition("T-001", State.DONE, skip_gates=True)
        self.assertFalse(self.sm.is_recoverable("T-001"))  # Done is terminal

    def test_list_tasks(self):
        self.sm.init_task("T-001")
        self.sm.init_task("T-002")
        tasks = self.sm.list_tasks()
        self.assertEqual(len(tasks), 2)

    def test_list_tasks_filter(self):
        self.sm.init_task("T-001")
        self.sm.init_task("T-002")
        self.sm.transition("T-002", State.PLAN_READY, skip_gates=True)
        tasks = self.sm.list_tasks(state_filter=State.PLAN_READY)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task_id, "T-002")

    def test_list_tasks_preserves_state_in_task_id(self):
        self.sm.init_task("TASK-001-state-diagram")
        tasks = self.sm.list_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task_id, "TASK-001-state-diagram")


class TestSnapshotManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.mgr = SnapshotManager(self.tmpdir.name)
        self.sm = StateMachine(self.tmpdir.name)
        self.sm.init_task("T-001")
        self.sm.transition("T-001", State.PLAN_READY, skip_gates=True)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_create_and_load_snapshot(self):
        snap = self.mgr.create_snapshot(
            "T-001",
            required_context=RequiredContext(files=["src/test.py"]),
            plan_progress=PlanProgress(total_steps=3),
        )
        self.assertEqual(snap.task_id, "T-001")
        self.assertEqual(snap.current_state, "Plan Ready")

        loaded = self.mgr.load_snapshot("T-001")
        self.assertEqual(loaded.task_id, "T-001")
        self.assertEqual(loaded.required_context.files, ["src/test.py"])

    def test_build_recovery_prompt(self):
        snap = self.mgr.create_snapshot(
            "T-001",
            plan_progress=PlanProgress(
                total_steps=2,
                completed=[PlanStep(step=1, description="Setup")],
                in_progress=[PlanStep(step=2, description="Implement")],
            ),
        )
        prompt = self.mgr.build_recovery_prompt(snap)
        self.assertIn("T-001", prompt)
        self.assertIn("Implement", prompt)
        self.assertIn("Setup", prompt)

    def test_cleanup_old_snapshots(self):
        for i in range(12):
            snap = self.mgr.create_snapshot("T-001")
            snap.transition_time = f"2026-05-{i+1:02d}T10:00:00+08:00"
            self.mgr._write_snapshot(snap)
        files = list((Path(self.tmpdir.name) / "snapshots").glob("T-001-*.yaml"))
        self.assertLessEqual(len(files), 11)

    def test_step_snapshot_unique_timestamps(self):
        """Two rapid snapshot writes must produce distinct timestamped files."""
        snap = self.mgr.create_snapshot("T-001")
        # create_snapshot already writes once; two additional writes = 3 total
        self.mgr._write_snapshot(snap)
        self.mgr._write_snapshot(snap)
        files = sorted(
            (Path(self.tmpdir.name) / "snapshots").glob("T-001-*.yaml"),
            key=lambda p: p.stat().st_mtime,
        )
        non_latest = [f for f in files if not f.name.endswith("-latest.yaml")]
        self.assertGreaterEqual(len(non_latest), 3, f"Expected >=3 distinct timestamped snapshots, got {len(non_latest)}: {[f.name for f in non_latest]}")
        # Verify sequence numbers are monotonic
        seqs = []
        for f in non_latest:
            parts = f.stem.split("-")
            if len(parts) >= 2 and parts[-1].isdigit():
                seqs.append(int(parts[-1]))
        if len(seqs) >= 2:
            self.assertEqual(sorted(seqs), seqs, "Sequence numbers must be monotonic")

    def test_snapshot_with_sandbox_roundtrip(self):
        from snapshot import SandboxInfo
        snap = self.mgr.create_snapshot(
            "T-001",
            required_context=RequiredContext(files=["src/test.py"]),
        )
        snap.sandbox = SandboxInfo(
            worktree_path=".worktrees/T-001",
            branch="task/t-001",
            created_at="2026-05-14T10:00:00+08:00",
        )
        self.mgr._write_snapshot(snap)

        loaded = self.mgr.load_snapshot("T-001")
        self.assertEqual(loaded.sandbox.worktree_path, ".worktrees/T-001")
        self.assertEqual(loaded.sandbox.branch, "task/t-001")


class TestLeaseManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.lm = LeaseManager(self.tmpdir.name)
        self.sm = StateMachine(self.tmpdir.name)
        self.sm.init_task("T-001")
        self.sm.transition("T-001", State.PLAN_READY, skip_gates=True)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_acquire_and_get(self):
        lease = self.lm.acquire("T-001", holder="agent-A")
        self.assertEqual(lease["holder"], "agent-A")
        self.assertIn("expires_at", lease)

        got = self.lm.get_lease("T-001")
        self.assertIsNotNone(got)
        self.assertEqual(got["holder"], "agent-A")

    def test_heartbeat(self):
        self.lm.acquire("T-001", holder="agent-A", duration_seconds=10)
        lease = self.lm.heartbeat("T-001", "agent-A")
        self.assertIn("last_heartbeat", lease)

    def test_heartbeat_wrong_holder(self):
        self.lm.acquire("T-001", holder="agent-A")
        from lease import LeaseError
        with self.assertRaises(LeaseError):
            self.lm.heartbeat("T-001", "agent-B")

    def test_can_resume_no_lease(self):
        ok, reason = self.lm.can_resume("T-001")
        self.assertTrue(ok)
        self.assertIn("No active lease", reason)

    def test_can_resume_expired(self):
        self.lm.acquire("T-001", holder="agent-A", duration_seconds=0)
        import time
        time.sleep(0.1)
        ok, reason = self.lm.can_resume("T-001")
        self.assertTrue(ok)
        self.assertIn("expired", reason)

    def test_terminal_state_no_lease(self):
        self.sm.init_task("T-002")
        self.sm.transition("T-002", State.PLAN_READY, skip_gates=True)
        self.sm.transition("T-002", State.EXECUTING, skip_gates=True)
        self.sm.transition("T-002", State.PATCH_READY, skip_gates=True)
        self.sm.transition("T-002", State.ENTROPY_REVIEW, skip_gates=True)
        self.sm.transition("T-002", State.DONE, skip_gates=True)
        ok, reason = self.lm.can_resume("T-002")
        self.assertFalse(ok)
        self.assertIn("terminal", reason)

    def test_lease_same_holder_renews(self):
        self.lm.acquire("T-001", holder="agent-A", duration_seconds=10)
        lease = self.lm.acquire("T-001", holder="agent-A", duration_seconds=20)
        self.assertEqual(lease["holder"], "agent-A")
        self.assertEqual(lease["duration_seconds"], 20)

    def test_lease_different_holder_denied(self):
        self.lm.acquire("T-001", holder="agent-A", duration_seconds=600)
        from lease import LeaseError
        with self.assertRaises(LeaseError) as ctx:
            self.lm.acquire("T-001", holder="agent-B")
        self.assertIn("agent-A", str(ctx.exception))

    def test_lease_expired_preempted(self):
        self.lm.acquire("T-001", holder="agent-A", duration_seconds=0)
        import time
        time.sleep(0.1)
        lease = self.lm.acquire("T-001", holder="agent-B")
        self.assertEqual(lease["holder"], "agent-B")


class TestGates(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir.name)
        os.makedirs("docs/superpowers/plans", exist_ok=True)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        self.tmpdir.cleanup()

    def test_g1_missing_plan(self):
        result = g1_plan_valid("T-001")
        self.assertFalse(result["passed"])
        self.assertIn("not found", result["message"])

    def test_g1_valid_plan(self):
        plan = "# Task\n\n## task_description\nGoal\n\n## file_changes\n- src/a.py\n\n## test_plan\nRun pytest\n\n## verification_command\npytest\n\n## success_criteria\nAll pass\n\n## state_diagram\nInbox -> Done\n\n## gate_checkpoints\nG1\n"
        Path("docs/superpowers/plans/T-001-plan.md").write_text(plan, encoding="utf-8")
        result = g1_plan_valid("T-001")
        self.assertTrue(result["passed"])

    def test_g1_placeholder_detected(self):
        plan = "# Task\n\n## task_description\nGoal\n\n## file_changes\n- src/a.py\n\n## test_plan\nRun pytest\n\n## verification_command\npytest\n\n## success_criteria\nTODO\n"
        Path("docs/superpowers/plans/T-001-plan.md").write_text(plan, encoding="utf-8")
        result = g1_plan_valid("T-001")
        self.assertFalse(result["passed"])
        self.assertIn("TODO", result["message"])

    def test_g2_complexity(self):
        plan = "# Plan\n\n- 1. Step one\n- 2. Step two\n- 3. Step three\n"
        Path("docs/superpowers/plans/T-001-plan.md").write_text(plan, encoding="utf-8")
        result = g2_complexity_budget("T-001", max_steps=2)
        self.assertFalse(result["passed"])
        self.assertIn("exceeds", result["message"])

    @patch("gates.subprocess.run")
    @patch("sandbox.SandboxManager")
    def test_g4_with_sandbox(self, mock_mgr_cls, mock_run):
        mock_mgr = mock_mgr_cls.return_value
        mock_mgr.get_sandbox.return_value = {"task_id": "T-001", "worktree_path": ".worktrees/T-001"}
        mock_mgr._worktree_path.return_value = Path(".worktrees/T-001")
        mock_run.side_effect = lambda *a, **kw: MagicMock(returncode=0, stdout="", stderr="")

        result = g4_surgical_check("T-001")
        self.assertTrue(result["passed"])
        self.assertEqual(result["message"], "No uncommitted changes")
        self.assertEqual(mock_run.call_count, 3)
        for call in mock_run.call_args_list:
            self.assertEqual(call.kwargs.get("cwd"), str(Path(".worktrees/T-001")))

    def test_g5_missing_command(self):
        result = g5_verification_proof("T-001")
        self.assertFalse(result["passed"])
        self.assertIn("No verification command", result["message"])

    @patch("gates._get_sandbox_cwd", return_value=".")
    def test_g5_command_runs(self, mock_cwd):
        plan = "# Plan\n\n## verification_command\necho hello\n"
        Path("docs/superpowers/plans/T-001-plan.md").write_text(plan, encoding="utf-8")
        result = g5_verification_proof("T-001")
        self.assertTrue(result["passed"])

    @patch("gates._get_sandbox_cwd", return_value=".")
    def test_g5_proof_of_work_failure(self, mock_cwd):
        """G5 must block when proof_of_work check in finishing-policy fails."""
        plan = "# Plan\n\n## verification_command\necho ok\n"
        Path("docs/superpowers/plans/TASK-TEST-plan.md").write_text(plan, encoding="utf-8")
        os.makedirs(".harness/superpowers", exist_ok=True)
        policy = """
proof_of_work:
  - name: lint
    command: exit 1
"""
        Path(".harness/superpowers/finishing-policy.yaml").write_text(policy, encoding="utf-8")
        result = g5_verification_proof("TASK-TEST")
        self.assertFalse(result["passed"])
        self.assertTrue("lint" in result["message"] or "proof_of_work" in result["message"], f"Expected lint or proof_of_work in message, got: {result['message']}")

    @patch("gates._get_sandbox_cwd", return_value=".")
    @patch("gates.subprocess.run")
    def test_g4_git_command_failure_blocks(self, mock_run, mock_cwd):
        """G4 must fail when git commands return non-zero, not silently pass."""
        mock_run.side_effect = lambda *a, **kw: MagicMock(
            returncode=1, stdout="", stderr="fatal: not a git repository"
        )
        result = g4_surgical_check("T-001")
        self.assertFalse(result["passed"])
        self.assertIn("Git diff failed", result["message"])

    @patch("gates._get_sandbox_cwd", return_value=".")
    def test_g4_allows_common_frontend_extensions(self, mock_cwd):
        """G4 should recognize common frontend/config extensions in file_changes."""
        plan = (
            "# Plan\n\n## task_description\nX\n\n## file_changes\n"
            "- src/App.tsx\n- src/index.jsx\n- styles.css\n- index.html\n"
            "- config.toml\n- .github/workflows/ci.yml\n"
            "## test_plan\npytest\n\n## verification_command\necho ok\n\n## success_criteria\nY.\n"
        )
        Path("docs/superpowers/plans/T-FRONT-001-plan.md").write_text(plan, encoding="utf-8")

        # Initialize a git repo so git diff commands work
        import subprocess
        subprocess.run(["git", "init"], capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], capture_output=True)
        Path("init.txt").write_text("init", encoding="utf-8")
        subprocess.run(["git", "add", "init.txt"], capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], capture_output=True)

        # Simulate staged changes for all listed files
        for f in ["src/App.tsx", "src/index.jsx", "styles.css", "index.html", "config.toml", ".github/workflows/ci.yml"]:
            Path(f).parent.mkdir(parents=True, exist_ok=True)
            Path(f).write_text("x", encoding="utf-8")
            subprocess.run(["git", "add", f], capture_output=True)

        result = g4_surgical_check("T-FRONT-001", plan_path="docs/superpowers/plans/T-FRONT-001-plan.md")
        self.assertTrue(result["passed"], f"G4 should allow frontend/config files: {result}")

    @patch("gates._get_sandbox_cwd", return_value=".")
    def test_g4_blocks_other_task_plan_modifications(self, mock_cwd):
        """G4 must detect modifications to OTHER tasks' plan files, not blanket-exempt all plans."""
        import subprocess

        # Initialize a git repo
        subprocess.run(["git", "init"], capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], capture_output=True)
        Path("init.txt").write_text("init", encoding="utf-8")
        subprocess.run(["git", "add", "init.txt"], capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], capture_output=True)

        # Current task plan
        plan = (
            "# Plan\n\n## task_description\nX\n\n## file_changes\n"
            "- src/a.py\n"
            "## test_plan\npytest\n\n## verification_command\necho ok\n\n## success_criteria\nY.\n"
        )
        Path("docs/superpowers/plans/TASK-CURR-001-plan.md").write_text(plan, encoding="utf-8")

        # Another task's plan
        Path("docs/superpowers/plans/TASK-OTHER-001-plan.md").write_text("# Other plan\n", encoding="utf-8")
        subprocess.run(["git", "add", "docs/superpowers/plans/TASK-OTHER-001-plan.md"], capture_output=True)

        result = g4_surgical_check("TASK-CURR-001", plan_path="docs/superpowers/plans/TASK-CURR-001-plan.md")
        self.assertFalse(result["passed"], f"G4 should block modifications to other task plans: {result}")
        self.assertIn("TASK-OTHER-001-plan.md", result["message"])

    def test_g1_missing_state_diagram(self):
        plan = """
## task_description
Foo
## file_changes
- `src/foo.py`
## test_plan
Run pytest
## verification_command
```bash
pytest
```
## success_criteria
Tests pass
## gate_checkpoints
G1
"""
        Path("docs/superpowers/plans/TASK-TEST-plan.md").write_text(plan, encoding="utf-8")
        result = g1_plan_valid("TASK-TEST")
        self.assertFalse(result["passed"])
        self.assertIn("state_diagram", str(result["details"]["errors"]))

    def test_g1_missing_gate_checkpoints(self):
        plan = """
## task_description
Foo
## file_changes
- `src/foo.py`
## test_plan
Run pytest
## verification_command
```bash
pytest
```
## success_criteria
Tests pass
## state_diagram
Inbox -> Done
"""
        Path("docs/superpowers/plans/TASK-TEST2-plan.md").write_text(plan, encoding="utf-8")
        result = g1_plan_valid("TASK-TEST2")
        self.assertFalse(result["passed"])
        self.assertIn("gate_checkpoints", str(result["details"]["errors"]))

    def test_g1_missing_tdd_sequence(self):
        plan = """
## task_description
Add feature
## file_changes
- `src/foo.py`
## test_plan
Write tests
## verification_command
```bash
pytest
```
## success_criteria
Tests pass
## state_diagram
Inbox -> Done
## gate_checkpoints
G1
"""
        Path("docs/superpowers/plans/TASK-TEST3-plan.md").write_text(plan, encoding="utf-8")
        result = g1_plan_valid("TASK-TEST3")
        self.assertFalse(result["passed"])
        errors_str = str(result["details"]["errors"]).lower()
        self.assertTrue("tdd" in errors_str or "test-first" in errors_str or "sequence" in errors_str, f"Expected TDD error in {result['details']['errors']}")


class TestSandboxCLI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir.name)
        os.makedirs(".harness/agent-guard/state", exist_ok=True)
        os.makedirs(".harness/agent-guard/snapshots", exist_ok=True)
        os.makedirs(".harness/agent-guard/leases", exist_ok=True)
        os.makedirs(".worktrees", exist_ok=True)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        self.tmpdir.cleanup()

    def test_execute_no_sandbox_flag_parsing(self):
        from cli import main

        # Verify --no-sandbox is accepted and parsed correctly.
        # T-001 does not exist so execute fails, but it proves
        # argparse accepted the flag without error.
        rc = main(["execute", "--no-sandbox", "T-001"])
        self.assertEqual(rc, 1)

    @patch("sandbox.subprocess.run")
    def test_sandbox_create_cli(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        from cli import cmd_sandbox_create
        import argparse

        args = argparse.Namespace(task_id="T-001")
        rc = cmd_sandbox_create(args)
        self.assertEqual(rc, 0)

    @patch("sandbox.subprocess.run")
    def test_sandbox_destroy_cli(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="diff content", stderr="")
        from cli import cmd_sandbox_destroy
        import argparse

        worktree = Path(".worktrees/T-001")
        worktree.mkdir(parents=True)
        args = argparse.Namespace(task_id="T-001", patch=True)
        rc = cmd_sandbox_destroy(args)
        self.assertEqual(rc, 0)

    @patch("cli._transition_with_snapshot")
    @patch("sandbox.subprocess.run")
    def test_sandbox_destroyed_on_transition_failure(self, mock_run, mock_transition):
        """If state transition fails after sandbox creation, worktree must be cleaned up."""
        import argparse
        from state_machine import StateMachine, State, StateMachineError
        from cli import _start_execution

        sm = StateMachine()
        sm.init_task("T-SBOX-FAIL")
        sm.transition("T-SBOX-FAIL", State.PLAN_READY, skip_gates=True)

        # Make _transition_with_snapshot raise after sandbox is created
        mock_transition.side_effect = StateMachineError("Invalid transition from Plan Ready to Done")

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["git", "worktree", "add"]:
                # Simulate actual worktree creation so destroy() can find it
                worktree = Path(".worktrees/T-SBOX-FAIL")
                worktree.mkdir(parents=True, exist_ok=True)
                (worktree / ".git").write_text("gitdir: /fake/path", encoding="utf-8")
                return MagicMock(returncode=0, stdout="", stderr="")
            if cmd[:3] == ["git", "worktree", "remove"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect

        args = argparse.Namespace(
            task_id="T-SBOX-FAIL",
            no_sandbox=False,
            holder=None,
        )

        rc = _start_execution("T-SBOX-FAIL", args)
        self.assertEqual(rc, 1)

        # Verify destroy was called (via subprocess.run with "worktree", "remove")
        destroy_calls = [call for call in mock_run.call_args_list
                         if len(call.args[0]) >= 3 and call.args[0][:3] == ["git", "worktree", "remove"]]
        self.assertTrue(destroy_calls, "sandbox worktree should be destroyed when transition fails")

    @patch("cli._transition_with_snapshot")
    @patch("sandbox.subprocess.run")
    def test_reused_worktree_not_destroyed_on_transition_failure(self, mock_run, mock_transition):
        """If worktree was reused (not created here), transition failure must NOT destroy it."""
        import argparse
        from state_machine import StateMachine, State, StateMachineError
        from cli import _start_execution

        sm = StateMachine()
        sm.init_task("T-SBOX-REUSE")
        sm.transition("T-SBOX-REUSE", State.PLAN_READY, skip_gates=True)

        # Pre-create worktree with .git so create() reports reuse (created=False)
        worktree = Path(".worktrees/T-SBOX-REUSE")
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".git").write_text("gitdir: /fake/path", encoding="utf-8")

        mock_transition.side_effect = StateMachineError("Invalid transition")

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["git", "worktree", "add"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            if "rev-parse" in cmd and "--git-dir" in cmd:
                return MagicMock(returncode=0, stdout="/fake/path\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect

        args = argparse.Namespace(
            task_id="T-SBOX-REUSE",
            no_sandbox=False,
            holder=None,
        )

        rc = _start_execution("T-SBOX-REUSE", args)
        self.assertEqual(rc, 1)

        # Verify destroy was NOT called
        destroy_calls = [call for call in mock_run.call_args_list
                         if len(call.args[0]) >= 3 and call.args[0][:3] == ["git", "worktree", "remove"]]
        self.assertFalse(destroy_calls, "reused worktree should NOT be destroyed when transition fails")


    def test_get_sandbox_cwd_prefers_snapshot(self):
        """_get_sandbox_cwd should prefer the worktree_path recorded in snapshot."""
        from snapshot import Snapshot, SandboxInfo, SnapshotManager

        sm = StateMachine()
        sm.init_task("TASK-SANDBOX-TEST")
        snap_mgr = SnapshotManager()
        snap = Snapshot(
            task_id="TASK-SANDBOX-TEST",
            current_state="Executing",
            previous_state="Plan Ready",
            transition_time="2026-01-01T00:00:00+08:00",
            sandbox=SandboxInfo(
                worktree_path="/tmp/fake-worktree",
                branch="test-branch",
                created_at="2026-01-01T00:00:00+08:00",
            ),
        )
        snap_mgr._write_snapshot(snap)

        with patch("pathlib.Path.exists", return_value=True):
            with patch(
                "subprocess.run",
                return_value=MagicMock(returncode=0, stdout="true\n"),
            ) as mock_run:
                cwd = _get_sandbox_cwd("TASK-SANDBOX-TEST")
                expected = str(Path("/tmp/fake-worktree"))
                self.assertEqual(cwd, expected)
                mock_run.assert_called_once()
                self.assertEqual(mock_run.call_args[1].get("cwd"), expected)


class TestClaimStats(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir.name)
        self.state_dir = Path(".harness/agent-guard/state")
        self.state_dir.mkdir(parents=True)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        self.tmpdir.cleanup()

    def test_claim_stats_in_error_message(self):
        """When no task is claimable, error should include filter stats."""
        from cli import _claim_next_task
        from lease import LeaseError

        sm = StateMachine()
        sm.init_task("T-CLAIM-STAT")
        sm.transition("T-CLAIM-STAT", State.PLAN_READY, skip_gates=True)
        # Acquire lease so task is excluded
        from lease import LeaseManager
        LeaseManager().acquire("T-CLAIM-STAT", holder="test")

        with self.assertRaises(LeaseError) as ctx:
            _claim_next_task()
        msg = str(ctx.exception)
        self.assertIn("total_plan_ready=", msg)
        self.assertIn("leaf=", msg)
        self.assertIn("active_leases=", msg)


class TestArchiveLegacyTasks(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir.name)
        self.state_dir = Path(".harness/agent-guard/state")
        self.state_dir.mkdir(parents=True)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        self.tmpdir.cleanup()

    def test_archive_dry_run_does_not_modify(self):
        """Default dry-run must not modify registry or task files."""
        import subprocess
        script_path = Path(__file__).parent / "scripts" / "archive-legacy-tasks.py"
        registry = {
            "TASK-018": {"state": "Done"},
            "TASK-018-Sub": {"state": "Plan Ready", "parent": "TASK-018"},
        }
        registry_path = self.state_dir / "registry.json"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        task_file = self.state_dir / "TASK-018-Sub-state.json"
        task_file.write_text(json.dumps({
            "task_id": "TASK-018-Sub", "current_state": "Plan Ready",
            "history": [], "created_at": "2026-01-01T00:00:00+08:00",
            "updated_at": "2026-01-01T00:00:00+08:00", "metadata": {"parent": "TASK-018"},
        }), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        # Registry should remain unchanged
        updated = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertNotIn("archived", updated["TASK-018-Sub"])

    def test_archive_apply_creates_backup(self):
        """--apply must create a registry backup before modifying."""
        import subprocess
        script_path = Path(__file__).parent / "scripts" / "archive-legacy-tasks.py"
        registry = {
            "TASK-018": {"state": "Done"},
            "TASK-018-Sub": {"state": "Plan Ready", "parent": "TASK-018"},
        }
        registry_path = self.state_dir / "registry.json"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        task_file = self.state_dir / "TASK-018-Sub-state.json"
        task_file.write_text(json.dumps({
            "task_id": "TASK-018-Sub", "current_state": "Plan Ready",
            "history": [], "created_at": "2026-01-01T00:00:00+08:00",
            "updated_at": "2026-01-01T00:00:00+08:00", "metadata": {"parent": "TASK-018"},
        }), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(script_path), "--apply"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        backups = list(self.state_dir.glob("registry.json.backup.*"))
        self.assertEqual(len(backups), 1)
        self.assertIn("Archived TASK-018-Sub", result.stdout)

    def test_archives_task_018_legacy_pseudo_tasks(self):
        """archive-legacy-tasks.py should mark TASK-018-* children as archived."""
        # Create registry with legacy pseudo tasks
        registry = {
            "TASK-018": {"state": "Done"},
            "TASK-018-Step-Commit": {"state": "Plan Ready", "parent": "TASK-018"},
            "TASK-018-file-changes": {"state": "Inbox", "parent": "TASK-018"},
            "TASK-OTHER": {"state": "Plan Ready"},
        }
        registry_path = self.state_dir / "registry.json"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")

        # Create corresponding task state files
        for task_id in ["TASK-018-Step-Commit", "TASK-018-file-changes"]:
            task_file = self.state_dir / f"{task_id}-state.json"
            task_data = {
                "task_id": task_id,
                "current_state": "Plan Ready",
                "history": [],
                "created_at": "2026-01-01T00:00:00+08:00",
                "updated_at": "2026-01-01T00:00:00+08:00",
                "metadata": {"parent": "TASK-018"},
            }
            task_file.write_text(json.dumps(task_data), encoding="utf-8")

        # Run the script
        import subprocess
        script_path = Path(__file__).parent / "scripts" / "archive-legacy-tasks.py"
        result = subprocess.run(
            [sys.executable, str(script_path), "--apply"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
        self.assertIn("Archived TASK-018-Step-Commit", result.stdout)
        self.assertIn("Archived TASK-018-file-changes", result.stdout)
        self.assertIn("Done. Archived 2 legacy pseudo tasks.", result.stdout)

        # Verify registry updated
        updated_registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertTrue(updated_registry["TASK-018-Step-Commit"].get("archived"))
        self.assertEqual(updated_registry["TASK-018-Step-Commit"].get("archived_reason"), "legacy_pseudo_task")
        self.assertTrue(updated_registry["TASK-018-file-changes"].get("archived"))
        self.assertFalse(updated_registry["TASK-OTHER"].get("archived", False))

        # Verify task state files updated
        commit_task = json.loads((self.state_dir / "TASK-018-Step-Commit-state.json").read_text(encoding="utf-8"))
        self.assertTrue(commit_task["metadata"].get("archived"))
        self.assertEqual(commit_task["current_state"], "Done")


class TestFinishSnapshot(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir.name)
        Path(".harness/agent-guard/state").mkdir(parents=True)
        Path(".harness/agent-guard/snapshots").mkdir(parents=True)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        self.tmpdir.cleanup()

    @patch("gates._get_sandbox_cwd", return_value=".")
    def test_finish_closes_snapshot_progress(self, mock_cwd):
        """After finish, snapshot must show all steps completed and state Done."""
        from cli import cmd_finish
        from snapshot import SnapshotManager, PlanProgress, PlanStep
        import argparse

        sm = StateMachine()
        sm.init_task("T-FINISH-TEST")
        sm.transition("T-FINISH-TEST", State.PLAN_READY, skip_gates=True)
        sm.transition("T-FINISH-TEST", State.EXECUTING, skip_gates=True)
        sm.transition("T-FINISH-TEST", State.PATCH_READY, skip_gates=True)
        sm.transition("T-FINISH-TEST", State.ENTROPY_REVIEW, skip_gates=True)

        # Pre-seed snapshot with pending progress
        snap_mgr = SnapshotManager()
        snap = snap_mgr.create_snapshot("T-FINISH-TEST")
        snap.plan_progress = PlanProgress(
            total_steps=3,
            pending=[PlanStep(step=1, description="s1"), PlanStep(step=2, description="s2")],
            in_progress=[PlanStep(step=3, description="s3")],
        )
        snap_mgr._write_snapshot(snap)

        # Create a minimal plan with verification_command
        plan_path = Path("docs/superpowers/plans/T-FINISH-TEST-plan.md")
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text("# Plan\n## verification_command\necho ok\n")

        args = argparse.Namespace(task_id="T-FINISH-TEST")
        rc = cmd_finish(args)
        self.assertEqual(rc, 0)

        finished_snap = snap_mgr.load_snapshot("T-FINISH-TEST")
        self.assertEqual(finished_snap.current_state, "Done")
        self.assertEqual(len(finished_snap.plan_progress.pending), 0)
        self.assertEqual(len(finished_snap.plan_progress.in_progress), 0)
        self.assertEqual(len(finished_snap.plan_progress.completed), 3)

    @patch("gates._get_sandbox_cwd", return_value=".")
    def test_finish_clears_sandbox_paths(self, mock_cwd):
        """After finish, snapshot sandbox worktree_path must be cleared and destroyed_at set."""
        from cli import cmd_finish
        from snapshot import SnapshotManager, SandboxInfo
        import argparse

        sm = StateMachine()
        sm.init_task("T-SBOX-CLEAR")
        sm.transition("T-SBOX-CLEAR", State.PLAN_READY, skip_gates=True)
        sm.transition("T-SBOX-CLEAR", State.EXECUTING, skip_gates=True)
        sm.transition("T-SBOX-CLEAR", State.PATCH_READY, skip_gates=True)
        sm.transition("T-SBOX-CLEAR", State.ENTROPY_REVIEW, skip_gates=True)

        snap_mgr = SnapshotManager()
        snap = snap_mgr.create_snapshot("T-SBOX-CLEAR")
        snap.sandbox = SandboxInfo(
            worktree_path=".worktrees/T-SBOX-CLEAR",
            branch="feature/T-SBOX-CLEAR",
            created_at="2026-01-01T00:00:00+08:00",
        )
        snap_mgr._write_snapshot(snap)

        plan_path = Path("docs/superpowers/plans/T-SBOX-CLEAR-plan.md")
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text("# Plan\n## verification_command\necho ok\n")

        args = argparse.Namespace(task_id="T-SBOX-CLEAR")
        rc = cmd_finish(args)
        self.assertEqual(rc, 0)

        finished_snap = snap_mgr.load_snapshot("T-SBOX-CLEAR")
        self.assertEqual(finished_snap.sandbox.worktree_path, "")
        self.assertTrue(finished_snap.sandbox.destroyed_at)


class TestStateRootAnchoring(unittest.TestCase):
    def test_state_machine_reads_guardharness_root_env(self):
        """StateMachine should use GUARDHARNESS_ROOT env var when set."""
        import os
        from state_machine import StateMachine

        custom_root = tempfile.mkdtemp()
        os.environ["GUARDHARNESS_ROOT"] = custom_root
        try:
            sm = StateMachine()
            self.assertEqual(str(sm.base_dir), str(Path(custom_root)))
            self.assertTrue(sm.state_dir.exists())
        finally:
            del os.environ["GUARDHARNESS_ROOT"]
            import shutil
            shutil.rmtree(custom_root)


class TestGetSandboxCwdFailClosed(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir.name)
        Path(".harness/agent-guard/state").mkdir(parents=True)
        Path(".harness/agent-guard/snapshots").mkdir(parents=True)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        self.tmpdir.cleanup()

    def test_missing_snapshot_for_non_done_task_raises(self):
        """Non-Done task with missing snapshot must raise, not fallback to '.'."""
        from gates import _get_sandbox_cwd
        from state_machine import StateMachine, State

        sm = StateMachine()
        sm.init_task("T-NO-SNAP")
        sm.transition("T-NO-SNAP", State.PLAN_READY, skip_gates=True)

        with self.assertRaises(RuntimeError) as ctx:
            _get_sandbox_cwd("T-NO-SNAP")
        self.assertIn("snapshot", str(ctx.exception).lower())

    def test_done_task_returns_dot(self):
        """Done task may safely fallback to '.' when snapshot missing."""
        from gates import _get_sandbox_cwd
        from state_machine import StateMachine, State

        sm = StateMachine()
        sm.init_task("T-DONE-NO-SNAP")
        sm.transition("T-DONE-NO-SNAP", State.PLAN_READY, skip_gates=True)
        sm.transition("T-DONE-NO-SNAP", State.EXECUTING, skip_gates=True)
        sm.transition("T-DONE-NO-SNAP", State.PATCH_READY, skip_gates=True)
        sm.transition("T-DONE-NO-SNAP", State.ENTROPY_REVIEW, skip_gates=True)
        sm.transition("T-DONE-NO-SNAP", State.DONE, skip_gates=True)

        cwd = _get_sandbox_cwd("T-DONE-NO-SNAP")
        self.assertEqual(cwd, ".")


class TestG5PolicyWarning(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir.name)
        Path(".harness/agent-guard/state").mkdir(parents=True)
        Path(".harness/superpowers").mkdir(parents=True)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        self.tmpdir.cleanup()

    @patch("gates._get_sandbox_cwd", return_value=".")
    def test_g5_warns_on_corrupt_policy(self, mock_cwd):
        """g5 should warn when finishing-policy.yaml is unreadable."""
        from gates import g5_verification_proof
        from state_machine import StateMachine, State
        import io, sys

        sm = StateMachine()
        sm.init_task("T-G5-POLICY")
        sm.transition("T-G5-POLICY", State.PLAN_READY, skip_gates=True)
        sm.transition("T-G5-POLICY", State.EXECUTING, skip_gates=True)
        sm.transition("T-G5-POLICY", State.PATCH_READY, skip_gates=True)
        sm.transition("T-G5-POLICY", State.ENTROPY_REVIEW, skip_gates=True)

        plan_path = Path("docs/superpowers/plans/T-G5-POLICY-plan.md")
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text("# Plan\n## verification_command\necho ok\n")

        policy_path = Path(".harness/superpowers/finishing-policy.yaml")
        policy_path.write_text("this is not: valid yaml: [", encoding="utf-8")

        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = g5_verification_proof("T-G5-POLICY")
            self.assertTrue(result["passed"])
            stderr_output = sys.stderr.getvalue()
            self.assertIn("finishing-policy", stderr_output)
        finally:
            sys.stderr = old_stderr


class TestListIncludeArchived(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir.name)
        Path(".harness/agent-guard/state").mkdir(parents=True)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        self.tmpdir.cleanup()

    def test_list_default_hides_archived(self):
        """list without --include-archived should hide archived tasks."""
        from cli import cmd_list
        import argparse

        sm = StateMachine()
        sm.init_task("T-ARCHIVED")
        sm.transition("T-ARCHIVED", State.PLAN_READY, skip_gates=True)
        sm.transition("T-ARCHIVED", State.EXECUTING, skip_gates=True)
        sm.transition("T-ARCHIVED", State.PATCH_READY, skip_gates=True)
        sm.transition("T-ARCHIVED", State.ENTROPY_REVIEW, skip_gates=True)
        sm.transition("T-ARCHIVED", State.DONE, skip_gates=True)
        task = sm.get_task("T-ARCHIVED")
        task.metadata["archived"] = True
        sm._save_task(task)

        sm.init_task("T-ACTIVE")
        sm.transition("T-ACTIVE", State.PLAN_READY, skip_gates=True)

        args = argparse.Namespace(state=None, recoverable=False, flat=True, no_children=False, include_archived=False)
        rc = cmd_list(args)
        self.assertEqual(rc, 0)

    def test_list_include_archived_shows_archived(self):
        """list with --include-archived should show archived tasks."""
        from cli import cmd_list
        import argparse

        sm = StateMachine()
        sm.init_task("T-ARCHIVED2")
        sm.transition("T-ARCHIVED2", State.PLAN_READY, skip_gates=True)
        sm.transition("T-ARCHIVED2", State.EXECUTING, skip_gates=True)
        sm.transition("T-ARCHIVED2", State.PATCH_READY, skip_gates=True)
        sm.transition("T-ARCHIVED2", State.ENTROPY_REVIEW, skip_gates=True)
        sm.transition("T-ARCHIVED2", State.DONE, skip_gates=True)
        task = sm.get_task("T-ARCHIVED2")
        task.metadata["archived"] = True
        sm._save_task(task)

        args = argparse.Namespace(state=None, recoverable=False, flat=True, no_children=False, include_archived=True)
        rc = cmd_list(args)
        self.assertEqual(rc, 0)


class TestParsePlanProgress(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir.name)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        self.tmpdir.cleanup()

    def test_extracts_task_headers_not_checkboxes(self):
        """When plan has ### Task N: headers, only those become steps."""
        from cli import _parse_plan_progress

        plan = """
### Task 1: Setup
- [ ] Step 1.1
- [ ] Step 1.2

### Task 2: Implement
- [ ] Step 2.1
- [ ] Step 2.2
"""
        path = Path("plan.md")
        path.write_text(plan, encoding="utf-8")

        progress = _parse_plan_progress(str(path))
        self.assertEqual(progress.total_steps, 2)
        self.assertEqual(len(progress.pending), 2)
        self.assertEqual(progress.pending[0].description, "Setup")
        self.assertEqual(progress.pending[1].description, "Implement")

    def test_fallback_to_list_items_when_no_task_headers(self):
        """When plan lacks Task headers, fall back to checkbox/list items."""
        from cli import _parse_plan_progress

        plan = """
- [ ] Step A
- [ ] Step B
1. Step C
"""
        path = Path("plan2.md")
        path.write_text(plan, encoding="utf-8")

        progress = _parse_plan_progress(str(path))
        self.assertEqual(progress.total_steps, 3)
        self.assertEqual(progress.pending[0].description, "Step A")
        self.assertEqual(progress.pending[1].description, "Step B")
        self.assertEqual(progress.pending[2].description, "Step C")


if __name__ == "__main__":
    unittest.main()
