"""Tests for SandboxManager."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sandbox import SandboxError, SandboxManager


class TestSandboxManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmpdir.name) / "agent-guard"
        self.repo_root = Path(self.tmpdir.name) / "repo"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        self.worktrees_base = self.repo_root / ".worktrees"
        self.mgr = SandboxManager(base_dir=str(self.base_dir), repo_root=str(self.repo_root))

    def tearDown(self):
        self.tmpdir.cleanup()

    @patch("sandbox.subprocess.run")
    def test_create_worktree(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
        result = self.mgr.create("TASK_001")

        self.assertEqual(result["task_id"], "TASK_001")
        self.assertEqual(result["worktree_path"], str(self.worktrees_base / "TASK_001"))
        self.assertEqual(result["branch"], "task/task-001")
        self.assertIn("created_at", result)

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0][:4], ["git", "worktree", "add", str(self.worktrees_base / "TASK_001")])
        self.assertEqual(args[0][4:6], ["-b", "task/task-001"])
        self.assertEqual(kwargs["cwd"], str(self.repo_root))

    @patch("sandbox.subprocess.run")
    def test_create_gitignore_not_exists(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
        result = self.mgr.create("TASK_002")

        self.assertEqual(result["task_id"], "TASK_002")
        gitignore = self.repo_root / ".gitignore"
        self.assertFalse(gitignore.exists())
        mock_run.assert_called_once()

    @patch("sandbox.subprocess.run")
    def test_create_gitignore_idempotent(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        gitignore = self.repo_root / ".gitignore"
        gitignore.write_text("*.pyc\n", encoding="utf-8")

        self.mgr.create("TASK_002")
        self.mgr.create("TASK_003")

        content = gitignore.read_text(encoding="utf-8")
        self.assertEqual(content.count(".worktrees/"), 1)

    @patch("sandbox.subprocess.run")
    def test_create_git_worktree_fails(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="fatal: invalid reference", stdout="")
        with self.assertRaises(SandboxError) as ctx:
            self.mgr.create("TASK_002")
        self.assertIn("git worktree add failed", str(ctx.exception))
        self.assertIn("fatal: invalid reference", str(ctx.exception))

    def test_create_duplicate_raises(self):
        worktree = self.worktrees_base / "TASK_002"
        worktree.mkdir(parents=True, exist_ok=True)
        with self.assertRaises(SandboxError) as ctx:
            self.mgr.create("TASK_002")
        self.assertIn("Worktree already exists", str(ctx.exception))

    @patch("sandbox.subprocess.run")
    def test_destroy_extracts_patch(self, mock_run):
        worktree = self.worktrees_base / "TASK_003"
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".git").mkdir(parents=True, exist_ok=True)

        diff_output = "diff --git a/file.txt b/file.txt\n+hello"
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout=diff_output)

        result = self.mgr.destroy("TASK_003", extract_patch_first=True)

        self.assertEqual(result["task_id"], "TASK_003")
        self.assertIsNotNone(result["patch_path"])
        self.assertIn("destroyed_at", result)

        patch_file = Path(result["patch_path"])
        self.assertTrue(patch_file.exists())
        self.assertEqual(patch_file.read_text(encoding="utf-8"), diff_output)

    @patch("sandbox.subprocess.run")
    def test_destroy_without_patch(self, mock_run):
        worktree = self.worktrees_base / "TASK_004"
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".git").mkdir(parents=True, exist_ok=True)

        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        result = self.mgr.destroy("TASK_004", extract_patch_first=False)

        self.assertEqual(result["task_id"], "TASK_004")
        self.assertIsNone(result["patch_path"])
        self.assertIn("destroyed_at", result)

    @patch("sandbox.subprocess.run")
    def test_extract_patch_git_diff_fails(self, mock_run):
        worktree = self.worktrees_base / "TASK_005"
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".git").mkdir(parents=True, exist_ok=True)

        mock_run.return_value = MagicMock(returncode=1, stderr="fatal: bad revision 'HEAD'", stdout="")
        with self.assertRaises(SandboxError) as ctx:
            self.mgr.extract_patch("TASK_005")
        self.assertIn("git diff failed", str(ctx.exception))
        self.assertIn("fatal: bad revision 'HEAD'", str(ctx.exception))

    @patch("sandbox.subprocess.run")
    def test_destroy_git_worktree_remove_fails(self, mock_run):
        worktree = self.worktrees_base / "TASK_006"
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".git").mkdir(parents=True, exist_ok=True)

        mock_run.return_value = MagicMock(returncode=1, stderr="fatal: 'TASK_006' is not a working tree", stdout="")
        with self.assertRaises(SandboxError) as ctx:
            self.mgr.destroy("TASK_006", extract_patch_first=False)
        self.assertIn("git worktree remove failed", str(ctx.exception))
        self.assertIn("fatal: 'TASK_006' is not a working tree", str(ctx.exception))

    def test_get_sandbox_none(self):
        result = self.mgr.get_sandbox("NONEXISTENT")
        self.assertIsNone(result)

    @patch("sandbox.subprocess.run")
    def test_detect_current_worktree_none(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="not a git repo", stdout="")
        result = self.mgr.detect_current_worktree()
        self.assertIsNone(result)

    @patch("sandbox.subprocess.run")
    def test_detect_current_worktree_detected(self, mock_run):
        def side_effect(cmd, **kwargs):
            if "--show-toplevel" in cmd:
                return MagicMock(returncode=0, stdout="/repo/wt1\n", stderr="")
            if "--git-common-dir" in cmd:
                return MagicMock(returncode=0, stdout="/repo/.git\n", stderr="")
            if "--git-dir" in cmd:
                return MagicMock(returncode=0, stdout="/repo/.git/worktrees/wt1\n", stderr="")
            return MagicMock(returncode=1, stdout="", stderr="")

        mock_run.side_effect = side_effect
        result = self.mgr.detect_current_worktree()
        self.assertIsNotNone(result)
        self.assertEqual(result, Path("/repo/wt1"))


if __name__ == "__main__":
    unittest.main()
