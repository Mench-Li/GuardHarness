"""E2E test for Agent-Guard complete lifecycle + interruption recovery + bypass states."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from state_machine import State, StateMachine


class TestAgentGuardE2E(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir.name)

        self.ag_dir = Path(self.tmpdir.name) / ".harness" / "agent-guard"
        self.ag_dir.mkdir(parents=True)
        harness_root = Path(__file__).parent
        for f in ["state_machine.py", "snapshot.py", "lease.py", "gates.py", "cli.py", "sandbox.py"]:
            src = harness_root / f
            if src.exists():
                (self.ag_dir / f).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

        subprocess.run(["git", "init"], capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], capture_output=True)
        Path(".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore"], capture_output=True)

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
            "Function returns expected greeting.\n\n"
            "## state_diagram\n"
            "Inbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done\n\n"
            "## gate_checkpoints\n"
            "G1: Plan Valid\n"
        )
        Path("docs/superpowers/plans/TASK-E2E-001-plan.md").write_text(plan, encoding="utf-8")
        Path("docs/superpowers/plans/TASK-SNAP-001-plan.md").write_text(plan, encoding="utf-8")

        # Track all initial files so G4 only sees real task modifications
        subprocess.run(["git", "add", "."], capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], capture_output=True)

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

    def test_parent_child_sync(self):
        """Child task completion should mark parent's step as completed in snapshot."""
        # Init parent
        r = self._run("init", "TASK-PARENT-001")
        self.assertEqual(r.returncode, 0, f"init failed: {r.stderr}")

        # Create a plan that exceeds G2 complexity budget to trigger auto-split on plan --approve
        files = "\n".join([f"- src/file{i}.py" for i in range(21)])
        plan = (
            "# Plan\n\n"
            "## task_description\n"
            "Add feature.\n\n"
            "## file_changes\n"
            f"{files}\n\n"
            "## test_plan\n"
            "Run pytest\n\n"
            "## verification_command\n"
            "echo ok\n\n"
            "## success_criteria\n"
            "Works.\n\n"
            "## state_diagram\n"
            "Inbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done\n\n"
            "## gate_checkpoints\n"
            "G1: Plan Valid\n\n"
            "## Alpha-Feature\n"
            "Step 1.\n\n"
            "## Beta-Feature\n"
            "Step 2.\n"
        )
        Path("docs/superpowers/plans/TASK-PARENT-001-plan.md").write_text(plan, encoding="utf-8")

        # Plan and approve parent (G2 fails -> auto-split into child tasks)
        r = self._run("plan", "TASK-PARENT-001", "--approve", "--auto-split")
        self.assertEqual(r.returncode, 0, f"plan failed: {r.stderr}")
        self.assertIn("G1 PASSED", r.stdout)

        # Baseline plan files so G4 doesn't flag them as off-plan modifications
        subprocess.run(["git", "add", "docs/superpowers/plans/"], capture_output=True)
        subprocess.run(["git", "commit", "-m", "baseline plans"], capture_output=True)

        # Execute parent
        r = self._run("execute", "TASK-PARENT-001", "--no-sandbox")
        self.assertEqual(r.returncode, 0, f"execute failed: {r.stderr}")

        # List tasks to find the child task ID
        r = self._run("list")
        self.assertEqual(r.returncode, 0, f"list failed: {r.stderr}")
        child_id = None
        for line in r.stdout.splitlines():
            # Child tasks appear indented on separate lines
            if "TASK-PARENT-001-" in line and "TASK-PARENT-001-plan" not in line:
                # Extract task ID from line (handles indented output format)
                parts = line.strip().split()
                for p in parts:
                    if p.startswith("TASK-PARENT-001-") and "-plan" not in p:
                        child_id = p
                        break
        self.assertTrue(child_id, f"Could not find child task in list output: {r.stdout}")

        # Child should exist and be in Inbox
        r = self._run("status", child_id)
        self.assertIn("Inbox", r.stdout, f"{child_id} should be in Inbox, got: {r.stdout}")

        # Plan and execute child with a minimal plan
        child_plan = (
            "# Plan\n\n"
            "## task_description\nX\n\n"
            "## file_changes\n- a.py\n\n"
            "## test_plan\npytest\n\n"
            "## verification_command\necho ok\n\n"
            "## success_criteria\nY.\n\n"
            "## state_diagram\n"
            "Inbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done\n\n"
            "## gate_checkpoints\n"
            "G1: Plan Valid\n"
        )
        Path(f"docs/superpowers/plans/{child_id}-plan.md").write_text(child_plan, encoding="utf-8")
        self._run("plan", child_id, "--approve")
        self._run("execute", child_id, "--no-sandbox")
        self._run("progress", child_id, "--step", "1", "--status", "done")
        self._run("patch", child_id)
        self._run("review", child_id)
        r = self._run("finish", child_id)
        self.assertEqual(r.returncode, 0, f"finish failed: {r.stderr}")

        # Parent snapshot should show child step completed
        sys.path.insert(0, str(self.ag_dir))
        from snapshot import SnapshotManager
        from state_machine import StateMachineError
        sm = SnapshotManager()
        try:
            parent_snap = sm.load_snapshot("TASK-PARENT-001")
        except StateMachineError:
            self.fail("Parent snapshot should exist after child finish")

        child_step = [s for s in parent_snap.plan_progress.completed
                      if child_id in s.description]
        self.assertTrue(child_step, f"parent snapshot should mark child step as completed, got completed={parent_snap.plan_progress.completed}")

    def test_parent_auto_transition_when_all_children_done(self):
        """When all child tasks reach Done, parent should auto-transition from Plan Ready to Executing."""
        self._run("init", "TASK-PARENT-AUTO")
        files = "\n".join([f"- src/file{i}.py" for i in range(21)])
        plan = (
            "# Plan\n\n"
            "## task_description\nAdd feature.\n\n"
            "## file_changes\n"
            f"{files}\n\n"
            "## test_plan\nRun pytest\n\n"
            "## verification_command\necho ok\n\n"
            "## success_criteria\nWorks.\n\n"
            "## state_diagram\n"
            "Inbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done\n\n"
            "## gate_checkpoints\nG1: Plan Valid\n\n"
            "### Task 1: Alpha\nStep 1.\n\n"
            "### Task 2: Beta\nStep 2.\n"
        )
        Path("docs/superpowers/plans/TASK-PARENT-AUTO-plan.md").write_text(plan, encoding="utf-8")

        # Plan and auto-split into Task-level subtasks
        r = self._run("plan", "TASK-PARENT-AUTO", "--approve", "--auto-split")
        self.assertEqual(r.returncode, 0, f"plan failed: {r.stderr}")
        self.assertIn("G1 PASSED", r.stdout)

        # Parent should be in Plan Ready after split
        r = self._run("status", "TASK-PARENT-AUTO")
        self.assertIn("Plan Ready", r.stdout, "parent should stay in Plan Ready after split")

        # Baseline plan files so G4 doesn't flag them
        subprocess.run(["git", "add", "docs/superpowers/plans/"], capture_output=True)
        subprocess.run(["git", "commit", "-m", "baseline plans"], capture_output=True)

        # Find both child task IDs
        r = self._run("list")
        self.assertEqual(r.returncode, 0, f"list failed: {r.stderr}")
        child_ids = []
        for line in r.stdout.splitlines():
            if "TASK-PARENT-AUTO-Task-" in line:
                parts = line.strip().split()
                for p in parts:
                    if p.startswith("TASK-PARENT-AUTO-Task-"):
                        child_ids.append(p)
                        break
        self.assertEqual(len(child_ids), 2, f"Expected 2 child tasks, got: {child_ids} in {r.stdout}")

        # Complete each child task
        child_plan = (
            "# Plan\n\n"
            "## task_description\nX\n\n"
            "## file_changes\n- a.py\n\n"
            "## test_plan\npytest\n\n"
            "## verification_command\necho ok\n\n"
            "## success_criteria\nY.\n\n"
            "## state_diagram\nInbox -> Done\n\n"
            "## gate_checkpoints\nG1\n"
        )
        # Write all child plans and baseline them before any child lifecycle starts
        for child_id in child_ids:
            Path(f"docs/superpowers/plans/{child_id}-plan.md").write_text(child_plan, encoding="utf-8")
        subprocess.run(["git", "add", "docs/superpowers/plans/"], capture_output=True)
        subprocess.run(["git", "commit", "-m", "baseline child plans"], capture_output=True)

        for i, child_id in enumerate(child_ids):
            r = self._run("plan", child_id, "--approve")
            self.assertEqual(r.returncode, 0, f"plan {child_id} failed: {r.stderr}")
            r = self._run("execute", child_id, "--no-sandbox")
            self.assertEqual(r.returncode, 0, f"execute {child_id} failed: {r.stderr}")

            # After first child starts executing, parent should auto-transition to Executing
            if i == 0:
                r = self._run("status", "TASK-PARENT-AUTO")
                self.assertIn("Executing", r.stdout, f"parent should auto-transition to Executing when first child starts, got: {r.stdout}")

            r = self._run("progress", child_id, "--step", "1", "--status", "done")
            self.assertEqual(r.returncode, 0, f"progress {child_id} failed: {r.stderr}")
            r = self._run("patch", child_id)
            self.assertEqual(r.returncode, 0, f"patch {child_id} failed: {r.stdout} {r.stderr}")
            r = self._run("review", child_id)
            self.assertEqual(r.returncode, 0, f"review {child_id} failed: {r.stderr}")
            r = self._run("finish", child_id)
            self.assertEqual(r.returncode, 0, f"finish {child_id} failed: {r.stderr}")

        # After the last child finishes, parent should auto-transition to Done
        r = self._run("status", "TASK-PARENT-AUTO")
        self.assertIn("Done", r.stdout, f"parent should auto-transition to Done after all children Done, got: {r.stdout}")

    def test_claim_execute_holder_consistency(self):
        """claim --execute creates a specific holder; execute TASK should reuse it without conflict."""
        self._run("init", "TASK-LEASE-001")
        plan = (
            "# Plan\n\n## task_description\nX\n\n## file_changes\n- a.py\n\n"
            "## test_plan\npytest\n\n## verification_command\necho ok\n\n## success_criteria\nY.\n\n## state_diagram\nInbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done\n\n## gate_checkpoints\nG1: Plan Valid\n"
        )
        Path("docs/superpowers/plans/TASK-LEASE-001-plan.md").write_text(plan, encoding="utf-8")
        self._run("plan", "TASK-LEASE-001", "--approve")

        r = self._run("claim", "--execute", "--holder", "agent-abc")
        self.assertEqual(r.returncode, 0, f"claim --execute failed: {r.stderr}")
        self.assertIn("agent-abc", r.stdout, f"holder agent-abc not in claim output: {r.stdout}")

        # Second execute with same task should reuse or at least not conflict
        r = self._run("execute", "TASK-LEASE-001", "--holder", "agent-abc")
        self.assertEqual(r.returncode, 0, f"execute with --holder failed: {r.stderr}")
        self.assertIn("agent-abc", r.stdout, f"holder agent-abc not in second execute output: {r.stdout}")

    def test_execute_auto_claim_without_task_id(self):
        """execute --no-sandbox (without task-id) should auto-claim and succeed."""
        self._run("init", "TASK-AUTO-001")
        plan = (
            "# Plan\n\n## task_description\nX\n\n## file_changes\n- a.py\n\n"
            "## test_plan\npytest\n\n## verification_command\necho ok\n\n## success_criteria\nY.\n\n## state_diagram\nInbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done\n\n## gate_checkpoints\nG1: Plan Valid\n"
        )
        Path("docs/superpowers/plans/TASK-AUTO-001-plan.md").write_text(plan, encoding="utf-8")
        self._run("plan", "TASK-AUTO-001", "--approve")

        r = self._run("execute", "--no-sandbox")
        self.assertEqual(r.returncode, 0, f"execute auto-claim failed: {r.stderr}")
        self.assertIn("Auto-claimed task: TASK-AUTO-001", r.stdout)
        self.assertIn("Task TASK-AUTO-001 -> Executing", r.stdout)

    def test_claim_execute_without_holder(self):
        """claim --execute without --holder should succeed using the claimed lease."""
        self._run("init", "TASK-CLAIM-001")
        plan = (
            "# Plan\n\n## task_description\nX\n\n## file_changes\n- a.py\n\n"
            "## test_plan\npytest\n\n## verification_command\necho ok\n\n## success_criteria\nY.\n\n## state_diagram\nInbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done\n\n## gate_checkpoints\nG1: Plan Valid\n"
        )
        Path("docs/superpowers/plans/TASK-CLAIM-001-plan.md").write_text(plan, encoding="utf-8")
        self._run("plan", "TASK-CLAIM-001", "--approve")

        r = self._run("claim", "--execute")
        self.assertEqual(r.returncode, 0, f"claim --execute failed: {r.stderr}")
        self.assertIn("Task TASK-CLAIM-001 -> Executing", r.stdout)

    def test_progress_creates_timestamped_snapshot(self):
        """Every progress call should create a new timestamped snapshot file."""
        self._run("init", "TASK-SNAP-001")
        r_plan = self._run("plan", "TASK-SNAP-001", "--approve")
        self.assertEqual(r_plan.returncode, 0, f"plan failed: {r_plan.stderr}")
        r_exec = self._run("execute", "TASK-SNAP-001", "--no-sandbox")
        self.assertEqual(r_exec.returncode, 0, f"execute failed: {r_exec.stderr}")

        snap_dir = Path(".harness/agent-guard/snapshots")
        snap_dir.mkdir(parents=True, exist_ok=True)
        before = list(snap_dir.glob("TASK-SNAP-001-*.yaml"))

        time.sleep(1.1)  # Ensure timestamp changes for new snapshot file
        r_prog = self._run("progress", "TASK-SNAP-001", "--step", "1", "--status", "done", "--evidence", "ok")
        self.assertEqual(r_prog.returncode, 0, f"progress failed: {r_prog.stderr}")

        after = list(snap_dir.glob("TASK-SNAP-001-*.yaml"))
        self.assertGreater(
            len(after), len(before),
            f"progress should create a new timestamped snapshot. before={len(before)}, after={len(after)}"
        )

    def test_g4_blocks_off_plan_files(self):
        self._run("init", "TASK-G4-001")
        plan = (
            "# Plan\n\n## task_description\nX\n\n## file_changes\n- src/allowed.py\n\n"
            "## test_plan\npytest\n\n## verification_command\necho ok\n\n## success_criteria\nY.\n\n## state_diagram\nInbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done\n\n## gate_checkpoints\nG1: Plan Valid\n"
        )
        Path("docs/superpowers/plans/TASK-G4-001-plan.md").write_text(plan, encoding="utf-8")
        self._run("plan", "TASK-G4-001", "--approve")
        # Use --no-sandbox so g4 checks the current directory, not a worktree
        self._run("execute", "TASK-G4-001", "--no-sandbox")

        # Create an off-plan file
        Path("src").mkdir(exist_ok=True)
        Path("src/off_plan.py").write_text("x=1", encoding="utf-8")
        subprocess.run(["git", "add", "src/off_plan.py"], capture_output=True)

        r = self._run("patch", "TASK-G4-001")
        self.assertNotEqual(r.returncode, 0, "G4 should block off-plan file changes")
        self.assertIn("off_plan", r.stdout + r.stderr)

    def test_sandbox_failure_blocks_execution(self):
        self._run("init", "TASK-SBOX-001")
        plan = (
            "# Plan\n\n## task_description\nX\n\n## file_changes\n- a.py\n\n"
            "## test_plan\npytest\n\n## verification_command\necho ok\n\n## success_criteria\nY.\n\n## state_diagram\nInbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done\n\n## gate_checkpoints\nG1: Plan Valid\n"
        )
        Path("docs/superpowers/plans/TASK-SBOX-001-plan.md").write_text(plan, encoding="utf-8")
        self._run("plan", "TASK-SBOX-001", "--approve")

        # Pre-create worktree directory so sandbox creation will be reused
        (Path(".worktrees") / "TASK-SBOX-001").mkdir(parents=True)
        r = self._run("execute", "TASK-SBOX-001", "--no-sandbox")
        self.assertEqual(r.returncode, 0, "--no-sandbox should allow fallback")

        # Without --no-sandbox it should fail if worktree path is a file
        self._run("init", "TASK-SBOX-002")
        Path("docs/superpowers/plans/TASK-SBOX-002-plan.md").write_text(plan, encoding="utf-8")
        self._run("plan", "TASK-SBOX-002", "--approve")
        (Path(".worktrees") / "TASK-SBOX-002").parent.mkdir(parents=True, exist_ok=True)
        (Path(".worktrees") / "TASK-SBOX-002").write_text("not a directory")
        r = self._run("execute", "TASK-SBOX-002")
        self.assertNotEqual(r.returncode, 0, "sandbox failure should block execution")


    def test_sandbox_written_to_snapshot(self):
        self._run("init", "TASK-SBOX-Snap-001")
        plan = (
            "# Plan\n\n## task_description\nX\n\n## file_changes\n- a.py\n\n"
            "## test_plan\npytest\n\n## verification_command\necho ok\n\n## success_criteria\nY.\n\n## state_diagram\nInbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done\n\n## gate_checkpoints\nG1: Plan Valid\n"
        )
        Path("docs/superpowers/plans/TASK-SBOX-Snap-001-plan.md").write_text(plan, encoding="utf-8")
        self._run("plan", "TASK-SBOX-Snap-001", "--approve")
        self._run("execute", "TASK-SBOX-Snap-001")

        from snapshot import SnapshotManager
        sm = SnapshotManager()
        snap = sm.load_snapshot("TASK-SBOX-Snap-001")
        self.assertTrue(snap.sandbox.worktree_path, "sandbox should be written to snapshot")

    def test_execute_transition_after_lease_and_sandbox(self):
        self._run("init", "TASK-ORD-001")
        plan = (
            "# Plan\n\n## task_description\nX\n\n## file_changes\n- a.py\n\n"
            "## test_plan\npytest\n\n## verification_command\necho ok\n\n## success_criteria\nY.\n\n## state_diagram\nInbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done\n\n## gate_checkpoints\nG1: Plan Valid\n"
        )
        Path("docs/superpowers/plans/TASK-ORD-001-plan.md").write_text(plan, encoding="utf-8")
        self._run("plan", "TASK-ORD-001", "--approve")

        # Pre-create worktree path as a file so sandbox creation fails
        (Path(".worktrees") / "TASK-ORD-001").parent.mkdir(parents=True, exist_ok=True)
        (Path(".worktrees") / "TASK-ORD-001").write_text("not a directory")
        r = self._run("execute", "TASK-ORD-001")
        self.assertNotEqual(r.returncode, 0)

        # Task should still be Plan Ready, not Executing
        r = self._run("status", "TASK-ORD-001")
        self.assertIn("Plan Ready", r.stdout)

    def test_execute_requires_holder_when_lease_exists(self):
        """If an active lease exists, execute without --holder must be rejected."""
        self._run("init", "TASK-HOLDER-001")
        plan = (
            "# Plan\n\n## task_description\nX\n\n## file_changes\n- a.py\n\n"
            "## test_plan\npytest\n\n## verification_command\necho ok\n\n## success_criteria\nY.\n\n## state_diagram\nInbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done\n\n## gate_checkpoints\nG1: Plan Valid\n"
        )
        Path("docs/superpowers/plans/TASK-HOLDER-001-plan.md").write_text(plan, encoding="utf-8")
        self._run("plan", "TASK-HOLDER-001", "--approve")

        # Claim with a specific holder
        r = self._run("claim", "--execute", "--holder", "agent-abc")
        self.assertEqual(r.returncode, 0, f"claim failed: {r.stderr}")

        # Execute without --holder should fail because lease exists
        r = self._run("execute", "TASK-HOLDER-001")
        self.assertNotEqual(r.returncode, 0, "execute without --holder should fail when active lease exists")
        self.assertIn("agent-abc", r.stdout + r.stderr)

    def test_execute_replaces_expired_lease(self):
        """An expired lease should be replaced by a new acquisition on execute."""
        self._run("init", "TASK-EXP-001")
        plan = (
            "# Plan\n\n## task_description\nX\n\n## file_changes\n- a.py\n\n"
            "## test_plan\npytest\n\n## verification_command\necho ok\n\n## success_criteria\nY.\n\n## state_diagram\nInbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done\n\n## gate_checkpoints\nG1: Plan Valid\n"
        )
        Path("docs/superpowers/plans/TASK-EXP-001-plan.md").write_text(plan, encoding="utf-8")
        self._run("plan", "TASK-EXP-001", "--approve")

        # Acquire a lease with 0-second duration so it expires immediately
        sys.path.insert(0, str(self.ag_dir))
        from lease import LeaseManager
        lm = LeaseManager()
        old = lm.acquire("TASK-EXP-001", holder="agent-old", duration_seconds=0)
        import time
        time.sleep(0.2)

        # Execute should succeed by replacing the expired lease
        r = self._run("execute", "TASK-EXP-001", "--no-sandbox")
        self.assertEqual(r.returncode, 0, f"execute failed: {r.stderr}")

        # A new lease with a different holder should have been created
        new = lm.get_lease("TASK-EXP-001")
        self.assertNotEqual(new["holder"], "agent-old", "expired lease should be replaced with new holder")

    def test_auto_split_only_creates_task_level_subtasks(self):
        """Auto-split should only create subtasks for Task-level sections, not Step-level."""
        self._run("init", "TASK-SPLIT-001")
        files = "\n".join([f"- src/file{i}.py" for i in range(21)])
        plan = (
            "# Plan\n\n"
            "## task_description\nAdd feature.\n\n"
            "## file_changes\n"
            f"{files}\n\n"
            "## test_plan\nRun pytest\n\n"
            "## verification_command\necho ok\n\n"
            "## success_criteria\nWorks.\n\n"
            "## state_diagram\nInbox -> Done\n\n"
            "## gate_checkpoints\nG1\n\n"
            "### Task 1: Alpha\n"
            "Step 1.\n\n"
            "### Task 2: Beta\n"
            "Step 2.\n\n"
            "- [ ] **Step 1: Setup**\n"
            "Do setup.\n\n"
            "- [ ] **Step 2: Implement**\n"
            "Do implement.\n"
        )
        Path("docs/superpowers/plans/TASK-SPLIT-001-plan.md").write_text(plan, encoding="utf-8")

        r = self._run("plan", "TASK-SPLIT-001", "--approve", "--auto-split")
        self.assertEqual(r.returncode, 0, f"plan failed: {r.stderr}")
        self.assertIn("G1 PASSED", r.stdout)

        # List tasks to verify only Task-level subtasks were created
        r = self._run("list")
        self.assertEqual(r.returncode, 0, f"list failed: {r.stderr}")

        # Should contain Task 1 and Task 2 subtasks
        self.assertIn("TASK-SPLIT-001-Task-Alpha", r.stdout, "Task 1 subtask should exist")
        self.assertIn("TASK-SPLIT-001-Task-Beta", r.stdout, "Task 2 subtask should exist")

        # Should NOT contain Step-level subtasks
        self.assertNotIn("TASK-SPLIT-001-Setup", r.stdout, "Step-level subtask should NOT exist")
        self.assertNotIn("TASK-SPLIT-001-Implement", r.stdout, "Step-level subtask should NOT exist")

    def test_claim_skips_pseudo_tasks(self):
        self._run("init", "TASK-PARENT-FILTER")
        plan = (
            "# Plan\n\n## task_description\nX\n\n## file_changes\n- a.py\n\n"
            "## test_plan\npytest\n\n## verification_command\necho ok\n\n"
            "## success_criteria\nY.\n\n## state_diagram\n"
            "Inbox -> Plan Ready -> Executing -> Done\n\n"
            "## gate_checkpoints\nG1: Plan Valid\n"
        )
        Path("docs/superpowers/plans/TASK-PARENT-FILTER-plan.md").write_text(plan, encoding="utf-8")
        self._run("plan", "TASK-PARENT-FILTER", "--approve")

        # Manually create a pseudo child task in Plan Ready without source_plan
        sm = StateMachine()
        sm.init_task("TASK-PARENT-FILTER-Step-Commit", metadata={"parent": "TASK-PARENT-FILTER"})
        sm.transition("TASK-PARENT-FILTER-Step-Commit", State.PLAN_READY, skip_gates=True)

        # claim should raise LeaseError because the only Plan Ready task is a pseudo task
        r = self._run("claim")
        self.assertEqual(r.returncode, 1, f"claim should fail when only pseudo tasks are available: {r.stdout}")
        self.assertIn("No available tasks", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
