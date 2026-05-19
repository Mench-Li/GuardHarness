"""Tests for archive-legacy-tasks script."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from state_machine import StateMachine


class TestArchiveLegacyTasks(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["GUARDHARNESS_ROOT"] = self.tmpdir.name
        self.sm = StateMachine(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()
        os.environ.pop("GUARDHARNESS_ROOT", None)

    def test_archive_updates_registry_state(self):
        """Archive script must set registry state to Done for archived tasks."""
        self.sm.init_task("TASK-ARCH-001")
        # Create pseudo child tasks
        for i in range(3):
            tid = f"TASK-ARCH-001-Step-{i}"
            self.sm.init_task(tid)
            registry_path = self.sm._registry_file()
            with open(registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
            registry[tid]["parent"] = "TASK-ARCH-001"
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump(registry, f)

        script = Path(".harness/agent-guard/scripts/archive-legacy-tasks.py")
        result = subprocess.run(
            ["python", str(script), "--task", "TASK-ARCH-001", "--apply"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")

        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)

        for i in range(3):
            tid = f"TASK-ARCH-001-Step-{i}"
            self.assertEqual(registry[tid]["state"], "Done", f"{tid} should be Done after archive")
            self.assertTrue(registry[tid]["archived"])
