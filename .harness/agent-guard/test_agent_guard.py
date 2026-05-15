"""Tests for Agent-Guard core components."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gates import g1_plan_valid, g2_complexity_budget, g4_surgical_check, g5_verification_proof
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
        plan = "# Task\n\n## task_description\nGoal\n\n## file_changes\n- src/a.py\n\n## test_plan\nRun pytest\n\n## verification_command\npytest\n\n## success_criteria\nAll pass\n"
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
        mock_run.return_value = MagicMock(returncode=0, stdout="src/a.py\n", stderr="")

        result = g4_surgical_check("T-001")
        self.assertTrue(result["passed"])
        self.assertIn("sandbox_used", result["details"])
        self.assertTrue(result["details"]["sandbox_used"])
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        self.assertEqual(call_args.kwargs.get("cwd"), str(Path(".worktrees/T-001")))

    def test_g5_missing_command(self):
        result = g5_verification_proof("T-001")
        self.assertFalse(result["passed"])
        self.assertIn("No verification command", result["message"])

    def test_g5_command_runs(self):
        plan = "# Plan\n\n## verification_command\necho hello\n"
        Path("docs/superpowers/plans/T-001-plan.md").write_text(plan, encoding="utf-8")
        result = g5_verification_proof("T-001")
        self.assertTrue(result["passed"])


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


if __name__ == "__main__":
    unittest.main()
