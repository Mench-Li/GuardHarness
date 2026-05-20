"""Tests for install.py manifest exclusions."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from install import should_exclude_file


class TestInstallExclusions(unittest.TestCase):
    def test_hook_debug_log_excluded(self):
        """hook-debug.log must be excluded from manifests."""
        self.assertTrue(should_exclude_file(Path(".claude/scripts/hook-debug.log")))

    def test_normal_scripts_not_excluded(self):
        """Regular scripts must not be excluded."""
        self.assertFalse(should_exclude_file(Path(".claude/scripts/auto-observe.sh")))


if __name__ == "__main__":
    unittest.main()
