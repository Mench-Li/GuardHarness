"""E2E test for Agent-Guard complete lifecycle + interruption recovery + bypass states."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


class TestAgentGuardE2E(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir.name)

        self.ag_dir = Path(self.tmpdir.name) / ".harness" / "agent-guard"
        self.ag_dir.mkdir(parents=True)
        harness_root = Path(__file__).parent
        for f in ["state_machine.py", "snapshot.py", "lease.py", "gates.py", "cli.py"]:
            src = harness_root / f
            if src.exists():
                (self.ag_dir / f).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

        subprocess.run(["git", "init"], capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], capture_output=True)

        os.makedirs("docs/superpowers/plans", exist_ok=True)
        plan = (
            "# Plan\n\n"
            "## task_description\n"
            "Add greeting function.\n\n"
            "## file_changes\n"
            "- src/greet.py\n\n"
            "## test_plan\n"
            "Run pytest\n\n"
            "## verification_command\n"
            "echo 'All tests pass'\n\n"
            "## success_criteria\n"
            "Function returns expected greeting.\n"
        )
        Path("docs/superpowers/plans/TASK-E2E-001-plan.md").write_text(plan, encoding="utf-8")

        self.cli = [sys.executable, str(self.ag_dir / "cli.py")]

    def tearDown(self):
        os.chdir(self.orig_cwd)
        self.tmpdir.cleanup()

    def _run(self, *args):
        result = subprocess.run(
            self.cli + list(args),
            capture_output=True,
            text=True,
        )
        return result

    def test_full_mainline_lifecycle(self):
        # 1. Init
        r = self._run("init", "TASK-E2E-001", "--spec", "docs/superpowers/specs/test.md")
        self.assertEqual(r.returncode, 0, f"init failed: {r.stderr}")

        # 2. Plan
        r = self._run("plan", "TASK-E2E-001", "--approve")
        self.assertEqual(r.returncode, 0, f"plan failed: {r.stderr}")
        self.assertIn("G1 PASSED", r.stdout)
        self.assertIn("Task TASK-E2E-001 -> Plan Ready", r.stdout)

        # 3. Execute
        r = self._run("execute", "TASK-E2E-001")
        self.assertEqual(r.returncode, 0, f"execute failed: {r.stderr}")
        self.assertIn("G3", r.stdout)
        self.assertIn("Task TASK-E2E-001 -> Executing", r.stdout)

        # 4. Patch
        r = self._run("patch", "TASK-E2E-001")
        self.assertEqual(r.returncode, 0, f"patch failed: {r.stderr}")
        self.assertIn("Task TASK-E2E-001 -> Patch Ready", r.stdout)

        # 5. Review
        r = self._run("review", "TASK-E2E-001")
        self.assertEqual(r.returncode, 0, f"review failed: {r.stderr}")
        self.assertIn("Task TASK-E2E-001 -> Entropy Review", r.stdout)

        # 6. Finish
        r = self._run("finish", "TASK-E2E-001")
        self.assertEqual(r.returncode, 0, f"finish failed: {r.stderr}")
        self.assertIn("G5 PASSED", r.stdout)
        self.assertIn("Task TASK-E2E-001 -> Done", r.stdout)

        # 7. Status
        r = self._run("status", "TASK-E2E-001")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Done", r.stdout)

    def test_needs_simplification_bypass(self):
        # Run to Entropy Review
        self._run("init", "TASK-E2E-001")
        self._run("plan", "TASK-E2E-001", "--approve")
        self._run("execute", "TASK-E2E-001")
        self._run("patch", "TASK-E2E-001")
        self._run("review", "TASK-E2E-001")

        # Simulate entropy failure by sending to simplification
        r = self._run("simplify", "TASK-E2E-001")
        self.assertEqual(r.returncode, 0, f"simplify failed: {r.stderr}")
        self.assertIn("Needs Simplification", r.stdout)
        self.assertIn("agent-guard execute", r.stdout)

        # Check status
        r = self._run("status", "TASK-E2E-001")
        self.assertIn("Needs Simplification", r.stdout)

        # Return to Executing after simplification
        r = self._run("execute", "TASK-E2E-001")
        self.assertEqual(r.returncode, 0, f"re-execute failed: {r.stderr}")
        self.assertIn("Task TASK-E2E-001 -> Executing", r.stdout)

    def test_block_and_unblock(self):
        self._run("init", "TASK-E2E-001")
        self._run("plan", "TASK-E2E-001", "--approve")

        # Block
        r = self._run("block", "TASK-E2E-001", "--reason", "Waiting for API key")
        self.assertEqual(r.returncode, 0, f"block failed: {r.stderr}")
        self.assertIn("Blocked", r.stdout)
        self.assertIn("Previous state: Plan Ready", r.stdout)

        # Unblock
        r = self._run("unblock", "TASK-E2E-001")
        self.assertEqual(r.returncode, 0, f"unblock failed: {r.stderr}")
        self.assertIn("Plan Ready", r.stdout)

    def test_interruption_and_resume(self):
        # Start task and interrupt after execute
        self._run("init", "TASK-E2E-001")
        self._run("plan", "TASK-E2E-001", "--approve")
        self._run("execute", "TASK-E2E-001")

        # Simulate lease loss
        lease_file = Path(".harness/agent-guard/leases/TASK-E2E-001-lease.json")
        if lease_file.exists():
            lease_file.unlink()

        # Create snapshot
        snap_dir = Path(".harness/agent-guard/snapshots")
        snap_dir.mkdir(parents=True, exist_ok=True)
        snapshot = (
            "task_id: TASK-E2E-001\n"
            "current_state: Executing\n"
            "previous_state: Plan Ready\n"
            "transition_time: 2026-05-08T10:00:00+08:00\n"
            "lease:\n"
            "  holder: agent-old\n"
            "  expires_at: 2026-05-08T10:05:00+08:00\n"
            "  heartbeat_interval: 300\n"
            "required_context:\n"
            "  files:\n"
            "    - docs/superpowers/plans/TASK-E2E-001-plan.md\n"
            "  memories: []\n"
            "  plans:\n"
            "    - docs/superpowers/plans/TASK-E2E-001-plan.md\n"
            "plan_progress:\n"
            "  total_steps: 3\n"
            "  completed:\n"
            "    - step: 1\n"
            "      description: Setup\n"
            "      evidence: commit abc\n"
            "      completed_at: 2026-05-08T09:50:00+00:00\n"
            "  in_progress:\n"
            "    - step: 2\n"
            "      description: Implement feature\n"
            "      started_at: 2026-05-08T10:00:00+00:00\n"
            "  pending:\n"
            "    - step: 3\n"
            "      description: Verify\n"
            "recovery_prompt: ''\n"
        )
        (snap_dir / "TASK-E2E-001-latest.yaml").write_text(snapshot, encoding="utf-8")

        # Resume
        r = self._run("resume", "TASK-E2E-001")
        self.assertEqual(r.returncode, 0, f"resume failed: {r.stderr}")
        self.assertIn("Resume check: No active lease", r.stdout)
        self.assertIn("State: Executing", r.stdout)
        self.assertIn("Implement feature", r.stdout)
        self.assertIn("[loaded] docs/superpowers/plans/TASK-E2E-001-plan.md", r.stdout)

    def test_list_and_recoverable(self):
        self._run("init", "TASK-A")
        self._run("init", "TASK-B")
        self._run("plan", "TASK-B", "--approve")

        r = self._run("list")
        self.assertEqual(r.returncode, 0)
        self.assertIn("TASK-A", r.stdout)
        self.assertIn("TASK-B", r.stdout)

        r = self._run("list", "--recoverable")
        self.assertEqual(r.returncode, 0)
        self.assertIn("TASK-B", r.stdout)


if __name__ == "__main__":
    unittest.main()
