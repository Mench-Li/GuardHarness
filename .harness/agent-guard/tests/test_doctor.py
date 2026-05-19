"""Tests for doctor consistency check command."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure imports resolve from the parent directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from doctor import Doctor
from state_machine import State, StateMachine


class TestDoctorChecks(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["GUARDHARNESS_ROOT"] = self.tmpdir.name
        self.sm = StateMachine(self.tmpdir.name)
        self.doc = Doctor(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()
        os.environ.pop("GUARDHARNESS_ROOT", None)

    def test_detects_archived_state_mismatch(self):
        """Doctor reports error when archived registry entry has state != Done."""
        self.sm.init_task("T-DOC-001")
        registry_path = self.sm._registry_file()
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
        registry["T-DOC-001"]["archived"] = True
        registry["T-DOC-001"]["state"] = "Inbox"
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump(registry, f)

        results = self.doc.check_all("T-DOC-001")
        errors = [r for r in results if r["level"] == "error"]
        self.assertTrue(any("archived_state_mismatch" in r["check"] for r in errors))

    def test_fix_updates_registry_state(self):
        """Doctor --fix corrects archived state mismatch to Done."""
        self.sm.init_task("T-DOC-002")
        registry_path = self.sm._registry_file()
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
        registry["T-DOC-002"]["archived"] = True
        registry["T-DOC-002"]["state"] = "Inbox"
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump(registry, f)

        results = self.doc.check_all("T-DOC-002", fix=True)
        fixed = [r for r in results if r.get("fixed")]
        self.assertTrue(any("archived_state_mismatch" in r["check"] for r in fixed))

        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
        self.assertEqual(registry["T-DOC-002"]["state"], "Done")

    def test_detects_lease_orphan(self):
        """Doctor reports warning when lease file exists for Done task."""
        from lease import LeaseManager
        self.sm.init_task("T-DOC-003")
        # Transition through valid states to Done
        self.sm.transition("T-DOC-003", State.PLAN_READY, skip_gates=True)
        self.sm.transition("T-DOC-003", State.EXECUTING, skip_gates=True)
        self.sm.transition("T-DOC-003", State.PATCH_READY, skip_gates=True)
        self.sm.transition("T-DOC-003", State.ENTROPY_REVIEW, skip_gates=True)
        self.sm.transition("T-DOC-003", State.DONE, skip_gates=True)
        lm = LeaseManager(self.tmpdir.name)
        # LeaseManager rejects acquiring for Done tasks; simulate orphan by writing lease file directly
        lease_path = lm._lease_file("T-DOC-003")
        lease_path.write_text(json.dumps({
            "task_id": "T-DOC-003",
            "holder": "test",
            "acquired_at": "2024-01-01T00:00:00+08:00",
            "expires_at": "2099-12-31T23:59:59+08:00",
            "heartbeat_interval": 300,
            "duration_seconds": 600,
        }), encoding="utf-8")

        results = self.doc.check_all("T-DOC-003")
        warnings = [r for r in results if r["level"] == "warning"]
        self.assertTrue(any("lease_orphan" in r["check"] for r in warnings))

    def test_fix_deletes_lease_orphan(self):
        """Doctor --fix deletes orphaned lease files."""
        from lease import LeaseManager
        self.sm.init_task("T-DOC-004")
        # Transition through valid states to Done
        self.sm.transition("T-DOC-004", State.PLAN_READY, skip_gates=True)
        self.sm.transition("T-DOC-004", State.EXECUTING, skip_gates=True)
        self.sm.transition("T-DOC-004", State.PATCH_READY, skip_gates=True)
        self.sm.transition("T-DOC-004", State.ENTROPY_REVIEW, skip_gates=True)
        self.sm.transition("T-DOC-004", State.DONE, skip_gates=True)
        lm = LeaseManager(self.tmpdir.name)
        # Simulate orphan lease file directly
        lease_path = lm._lease_file("T-DOC-004")
        lease_path.write_text(json.dumps({
            "task_id": "T-DOC-004",
            "holder": "test",
            "acquired_at": "2024-01-01T00:00:00+08:00",
            "expires_at": "2099-12-31T23:59:59+08:00",
            "heartbeat_interval": 300,
            "duration_seconds": 600,
        }), encoding="utf-8")

        results = self.doc.check_all("T-DOC-004", fix=True)
        fixed = [r for r in results if r.get("fixed")]
        self.assertTrue(any("lease_orphan" in r["check"] for r in fixed))

        lease = lm.get_lease("T-DOC-004")
        self.assertIsNone(lease)

    def test_detects_missing_proof_of_work_tool(self):
        """Doctor reports warning when finishing-policy.yaml tools are missing."""
        self.sm.init_task("T-DOC-005")
        policy_dir = Path(self.tmpdir.name) / "superpowers"
        policy_dir.mkdir(parents=True, exist_ok=True)
        policy_path = policy_dir / "finishing-policy.yaml"
        policy_path.write_text("""
proof_of_work:
  - name: complexity_analysis
    command: "radon cc . -a -nc"
""", encoding="utf-8")

        import shutil
        original_which = shutil.which
        def mock_which(cmd, *args, **kwargs):
            if cmd == "radon":
                return None
            return original_which(cmd, *args, **kwargs)

        try:
            shutil.which = mock_which
            results = self.doc.check_all("T-DOC-005")
            warnings = [r for r in results if r["level"] == "warning"]
            self.assertTrue(any("missing_proof_of_work_tool" in r["check"] for r in warnings))
            self.assertTrue(any("radon" in r["message"] for r in warnings))
        finally:
            shutil.which = original_which

    def test_detects_parent_children_state_sync(self):
        """Doctor reports warning when parent state lags behind completed children."""
        self.sm.init_task("T-PARENT-001")
        self.sm.init_task("T-CHILD-001")
        registry_path = self.sm._registry_file()
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
        registry["T-PARENT-001"]["children"] = ["T-CHILD-001"]
        registry["T-CHILD-001"]["state"] = "Done"
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump(registry, f)

        results = self.doc.check_all("T-PARENT-001")
        warnings = [r for r in results if r["level"] == "warning"]
        self.assertTrue(any("parent_children_state_sync" in r["check"] for r in warnings))
        self.assertIn("T-PARENT-001", [r["message"] for r in warnings][0])

    def test_fix_parent_children_state_sync(self):
        """Doctor --fix advances parent state when all children are Done."""
        self.sm.init_task("T-PARENT-002")
        self.sm.init_task("T-CHILD-002")
        registry_path = self.sm._registry_file()
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
        registry["T-PARENT-002"]["children"] = ["T-CHILD-002"]
        registry["T-CHILD-002"]["state"] = "Done"
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump(registry, f)

        results = self.doc.check_all("T-PARENT-002", fix=True)
        fixed = [r for r in results if r.get("fixed")]
        self.assertTrue(any("parent_children_state_sync" in r["check"] for r in fixed))

        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
        self.assertEqual(registry["T-PARENT-002"]["state"], "Done")


if __name__ == "__main__":
    unittest.main()
