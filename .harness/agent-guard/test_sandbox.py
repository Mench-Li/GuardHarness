"""Tests for SandboxManager."""

import subprocess
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
        self.assertTrue(result.get("created"), "new worktree should report created=True")

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0][:4], ["git", "worktree", "add", str(self.worktrees_base / "TASK_001")])
        self.assertEqual(args[0][4:6], ["-b", "task/task-001"])
        self.assertEqual(kwargs["cwd"], str(self.repo_root))

    @patch("sandbox.subprocess.run")
    def test_create_reuse_returns_created_false(self, mock_run):
        """Reusing an existing valid worktree should report created=False."""
        worktree = self.worktrees_base / "TASK_REUSE"
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".git").write_text("gitdir: /fake/path", encoding="utf-8")

        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
        result = self.mgr.create("TASK_REUSE")

        self.assertFalse(result.get("created"), "reused worktree should report created=False")
        # No git worktree add should be called for reuse
        for call in mock_run.call_args_list:
            self.assertNotEqual(call.args[0][:3], ["git", "worktree", "add"])

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

    def test_extract_patch_does_not_pollute_index(self):
        """After extract_patch, untracked files must not remain as intent-to-add in the index."""
        worktree = self.worktrees_base / "TASK_008"
        worktree.mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "init"], capture_output=True, cwd=str(worktree))
        subprocess.run(["git", "config", "user.email", "t@t.com"], capture_output=True, cwd=str(worktree))
        subprocess.run(["git", "config", "user.name", "T"], capture_output=True, cwd=str(worktree))
        Path(worktree / "init.txt").write_text("init", encoding="utf-8")
        subprocess.run(["git", "add", "init.txt"], capture_output=True, cwd=str(worktree))
        subprocess.run(["git", "commit", "-m", "init"], capture_output=True, cwd=str(worktree))

        untracked_file = worktree / "new_feature.py"
        untracked_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

        self.mgr.extract_patch("TASK_008")

        # Verify no intent-to-add entries remain
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=str(worktree),
        )
        self.assertNotIn("new_feature.py", result.stdout, "extract_patch must not leave intent-to-add in index")

    @patch("sandbox.subprocess.run")
    def test_extract_patch_ls_files_failure_blocks(self, mock_run):
        """If git ls-files fails, extract_patch must raise SandboxError."""
        worktree = self.worktrees_base / "TASK_010"
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".git").mkdir(parents=True, exist_ok=True)

        mock_run.return_value = MagicMock(returncode=1, stderr="fatal: not a git repository", stdout="")
        with self.assertRaises(SandboxError) as ctx:
            self.mgr.extract_patch("TASK_010")
        self.assertIn("git ls-files failed", str(ctx.exception))

    @patch("sandbox.subprocess.run")
    def test_extract_patch_git_add_n_failure_blocks(self, mock_run):
        """If git add -N fails, extract_patch must raise SandboxError."""
        worktree = self.worktrees_base / "TASK_011"
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".git").mkdir(parents=True, exist_ok=True)

        def side_effect(cmd, **kwargs):
            if "ls-files" in cmd:
                return MagicMock(returncode=0, stdout="new.py\n", stderr="")
            if "add" in cmd and "-N" in cmd:
                return MagicMock(returncode=1, stderr="fatal: pathspec 'new.py' did not match", stdout="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect
        with self.assertRaises(SandboxError) as ctx:
            self.mgr.extract_patch("TASK_011")
        self.assertIn("git add -N failed", str(ctx.exception))

    @patch("sandbox.subprocess.run")
    def test_extract_patch_git_reset_failure_blocks(self, mock_run):
        """If git reset HEAD fails, extract_patch must raise SandboxError."""
        worktree = self.worktrees_base / "TASK_012"
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".git").mkdir(parents=True, exist_ok=True)

        def side_effect(cmd, **kwargs):
            if "ls-files" in cmd:
                return MagicMock(returncode=0, stdout="new.py\n", stderr="")
            if "add" in cmd and "-N" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if "diff" in cmd and "HEAD" in cmd:
                return MagicMock(returncode=0, stdout="diff content", stderr="")
            if "reset" in cmd:
                return MagicMock(returncode=1, stderr="fatal: Unable to create", stdout="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect
        with self.assertRaises(SandboxError) as ctx:
            self.mgr.extract_patch("TASK_012")
        self.assertIn("git reset failed", str(ctx.exception))

    def test_create_rejects_fake_git_directory(self):
        """A directory with a plain .git file but no actual repo should not be reused."""
        worktree = self.worktrees_base / "TASK_009"
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".git").write_text("gitdir: /nonexistent", encoding="utf-8")

        with self.assertRaises(SandboxError) as ctx:
            self.mgr.create("TASK_009")
        self.assertIn("Worktree already exists", str(ctx.exception))

    @patch("sandbox.subprocess.run")
    def test_extract_patch_git_diff_fails(self, mock_run):
        worktree = self.worktrees_base / "TASK_005"
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".git").mkdir(parents=True, exist_ok=True)

        def side_effect(cmd, **kwargs):
            if "ls-files" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=1, stderr="fatal: bad revision 'HEAD'", stdout="")

        mock_run.side_effect = side_effect
        with self.assertRaises(SandboxError) as ctx:
            self.mgr.extract_patch("TASK_005")
        self.assertIn("git diff failed", str(ctx.exception))
        self.assertIn("fatal: bad revision 'HEAD'", str(ctx.exception))

    def test_extract_patch_untracked_produces_valid_diff(self):
        """Untracked files must appear as valid git diff output (diff --git + --- /dev/null)."""
        worktree = self.worktrees_base / "TASK_007"
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".git").mkdir(parents=True, exist_ok=True)

        untracked_file = worktree / "new_feature.py"
        untracked_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

        # Initialize a real git repo so git diff HEAD works
        subprocess.run(["git", "init"], capture_output=True, cwd=str(worktree))
        subprocess.run(["git", "config", "user.email", "t@t.com"], capture_output=True, cwd=str(worktree))
        subprocess.run(["git", "config", "user.name", "T"], capture_output=True, cwd=str(worktree))
        Path(worktree / "init.txt").write_text("init", encoding="utf-8")
        subprocess.run(["git", "add", "init.txt"], capture_output=True, cwd=str(worktree))
        subprocess.run(["git", "commit", "-m", "init"], capture_output=True, cwd=str(worktree))

        patch_path = self.mgr.extract_patch("TASK_007")
        patch_content = patch_path.read_text(encoding="utf-8")

        self.assertIn("diff --git", patch_content)
        self.assertIn("--- /dev/null", patch_content)
        self.assertIn("+++ b/new_feature.py", patch_content)
        self.assertIn("+def hello():", patch_content)

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
