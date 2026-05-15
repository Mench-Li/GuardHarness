"""Sandbox manager for isolated worktree execution."""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class SandboxError(Exception):
    pass


class SandboxManager:
    """Manages git worktree-based sandboxes for task isolation."""

    def __init__(self, base_dir: str | None = None, repo_root: str | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(".harness/agent-guard")
        self.patches_dir = self.base_dir / "patches"
        self.patches_dir.mkdir(parents=True, exist_ok=True)
        self.repo_root = Path(repo_root) if repo_root else Path(".")
        self.worktrees_base = self.repo_root / ".worktrees"

    def _worktree_path(self, task_id: str) -> Path:
        return self.worktrees_base / task_id

    def _patch_file(self, task_id: str) -> Path:
        return self.patches_dir / f"{task_id}.patch"

    def _branch_name(self, task_id: str) -> str:
        return f"task/{task_id.lower().replace('_', '-')}"

    def _is_git_worktree(self, path: Path) -> bool:
        """Check if a directory is a valid git worktree."""
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            cwd=str(path),
        )
        return result.returncode == 0

    def create(self, task_id: str) -> dict[str, Any]:
        """Create a new worktree sandbox for the task."""
        worktree = self._worktree_path(task_id)
        branch = self._branch_name(task_id)

        if worktree.exists():
            if worktree.is_dir() and self._is_git_worktree(worktree):
                # Reuse existing valid worktree
                return {
                    "task_id": task_id,
                    "worktree_path": str(worktree),
                    "branch": branch,
                    "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                    "created": False,
                }
            raise SandboxError(f"Worktree already exists for task {task_id}: {worktree}")

        gitignore = self.repo_root / ".gitignore"
        if gitignore.exists():
            lines = gitignore.read_text(encoding="utf-8").splitlines()
            if ".worktrees/" not in lines and ".worktrees" not in lines:
                with open(gitignore, "a", encoding="utf-8") as f:
                    f.write("\n.worktrees/\n")

        result = subprocess.run(
            ["git", "worktree", "add", str(worktree), "-b", branch],
            capture_output=True,
            text=True,
            cwd=str(self.repo_root),
        )
        if result.returncode != 0:
            raise SandboxError(f"git worktree add failed: {result.stderr}")

        return {
            "task_id": task_id,
            "worktree_path": str(worktree),
            "branch": branch,
            "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "created": True,
        }

    def destroy(self, task_id: str, extract_patch_first: bool = True) -> dict[str, Any]:
        """Destroy a worktree sandbox, optionally extracting a patch first."""
        worktree = self._worktree_path(task_id)

        if not worktree.exists():
            raise SandboxError(f"Worktree not found for task {task_id}: {worktree}")

        patch_path = None
        if extract_patch_first:
            patch_path = str(self.extract_patch(task_id))

        result = subprocess.run(
            ["git", "worktree", "remove", str(worktree)],
            capture_output=True,
            text=True,
            cwd=str(self.repo_root),
        )
        if result.returncode != 0:
            raise SandboxError(f"git worktree remove failed: {result.stderr}")

        return {
            "task_id": task_id,
            "patch_path": patch_path,
            "destroyed_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        }

    def extract_patch(self, task_id: str) -> Path:
        """Extract git diff + untracked files from worktree as a patch file."""
        worktree = self._worktree_path(task_id)
        patch_file = self._patch_file(task_id)

        # Stage untracked files with intent-to-add so git diff HEAD formats them properly
        untracked_result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            cwd=str(worktree),
        )
        if untracked_result.returncode != 0:
            raise SandboxError(f"git ls-files failed: {untracked_result.stderr}")
        untracked = [line.strip() for line in untracked_result.stdout.splitlines() if line.strip()]
        for ufile in untracked:
            add_result = subprocess.run(
                ["git", "add", "-N", ufile],
                capture_output=True,
                text=True,
                cwd=str(worktree),
            )
            if add_result.returncode != 0:
                raise SandboxError(f"git add -N failed: {add_result.stderr}")

        result = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(worktree),
        )
        if result.returncode != 0:
            raise SandboxError(f"git diff failed: {result.stderr}")

        patch_file.write_text(result.stdout, encoding="utf-8")

        # Reset intent-to-add entries so they don't pollute the index
        if untracked:
            reset_result = subprocess.run(
                ["git", "reset", "HEAD"] + untracked,
                capture_output=True,
                text=True,
                cwd=str(worktree),
            )
            if reset_result.returncode != 0:
                raise SandboxError(f"git reset failed: {reset_result.stderr}")

        return patch_file

    def get_sandbox(self, task_id: str) -> dict[str, Any] | None:
        """Get sandbox info if it exists."""
        worktree = self._worktree_path(task_id)
        if not worktree.exists():
            return None
        return {"task_id": task_id, "worktree_path": str(worktree)}

    def detect_current_worktree(self) -> Path | None:
        """Detect if current directory is inside a linked git worktree."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return None
            toplevel = Path(result.stdout.strip())

            common_dir = subprocess.run(
                ["git", "rev-parse", "--git-common-dir"],
                capture_output=True,
                text=True,
            )
            git_dir = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
            )
            if common_dir.returncode != 0 or git_dir.returncode != 0:
                return None

            if Path(common_dir.stdout.strip()).resolve() != Path(git_dir.stdout.strip()).resolve():
                return toplevel
        except Exception:
            pass
        return None
