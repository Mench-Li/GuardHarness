#!/usr/bin/env python3
"""GuardHarness 安装脚本。

支持三种使用方式：
1. 本地安装: python /path/to/harness/install.py
2. 远程安装: curl -fsSL <url>/install.sh | bash
3. 远程安装: irm <url>/install.ps1 | iex

远程安装时脚本会自动从 GitHub 下载模板到临时目录，再复制到目标项目。
"""

from __future__ import annotations

# Windows 终端 UTF-8 编码修复
import io
import sys

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass

import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

# --- 配置：发布到 GitHub 后修改为你的仓库地址 ---
GITHUB_REPO = "https://github.com/Mench-Li/GuardHarness"
GITHUB_RAW = "https://raw.githubusercontent.com/Mench-Li/GuardHarness/main"

EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "state",          # .harness/agent-guard/state (runtime生成)
    "leases",         # .harness/agent-guard/leases (运行时租约)
    "snapshots",      # .harness/agent-guard/snapshots (运行时快照)
    "patches",        # .harness/agent-guard/patches (运行时补丁)
    ".git",           # .harness/team/.git (submodule)
]

EXCLUDE_PATHS = {
    ".harness/agent-guard/state",
    ".harness/agent-guard/leases",
    ".harness/agent-guard/snapshots",
    ".harness/agent-guard/patches",
}

COPY_ITEMS: list[tuple[str, str]] = [
    (".harness", "Harness 配置（Agent-Guard + Superpowers + Workflows）"),
    ("CLAUDE.md", "项目上下文模板"),
    ("README.md", "项目说明文档"),
    ("HARNESS_USAGE_GUIDE.md", "详细使用手册"),
    (".claude/settings.json", "Claude Code 配置"),
    (".claude/scripts", "自动化脚本（.sh + .ps1）"),
    (".claude/skills", "Claude Code Slash Command Skills"),
]

# 文档重定向：避免覆盖目标项目根目录的 README.md / CLAUDE.md，放到 .harness/ 下
DOC_RELOCATIONS: dict[str, str] = {
    "CLAUDE.md": ".harness/CLAUDE.md",
    "README.md": ".harness/README.md",
}

DIRS_TO_CREATE = [
    "docs/superpowers/specs",
    "docs/superpowers/plans",
    ".worktrees",
    ".claude/memory/observations",
    ".claude/memory/patterns",
    ".claude/memory/retro",
    ".claude/memory/decisions",
    ".claude/memory/failures",
    ".claude/memory/entropy",
    ".claude/memory/invariants",
    ".claude/memory/taste",
    ".claude/memory/metrics",
    ".claude/memory/user",
]

GITIGNORE_LINES = [
    "",
    "# GuardHarness",
    ".worktrees/",
    ".claude/memory/user/",
    ".harness/agent-guard/leases/",
    ".harness/agent-guard/snapshots/",
    ".harness/agent-guard/state/",
    ".harness/agent-guard/patches/",
    ".claude/scripts/hook-debug.log",
    "__pycache__/",
    "*.pyc",
]


def _info(msg: str) -> None:
    print(f"  [INFO] {msg}")


def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}", file=sys.stderr)


def _error(msg: str) -> None:
    print(f"  [ERR]  {msg}", file=sys.stderr)


def is_local_mode() -> bool:
    """判断脚本是否从本地模板目录运行。"""
    script_dir = Path(__file__).resolve().parent
    return (script_dir / ".harness").exists() and (script_dir / "CLAUDE.md").exists()


def get_harness_root() -> Path:
    """获取 Harness 模板根目录。"""
    return Path(__file__).resolve().parent


def download_remote_template(temp_dir: Path) -> Path:
    """从 GitHub 下载模板到临时目录。"""
    _info("从 GitHub 下载 Harness 模板...")
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", GITHUB_REPO, str(temp_dir / "repo")],
            check=True,
            capture_output=True,
            text=True,
        )
        return temp_dir / "repo"
    except Exception:
        _warn("git clone 失败，尝试下载 ZIP...")
        zip_url = f"{GITHUB_REPO}/archive/refs/heads/main.zip"
        zip_path = temp_dir / "harness.zip"
        urllib.request.urlretrieve(zip_url, zip_path)
        shutil.unpack_archive(zip_path, temp_dir)
        # 解压后目录名是 <repo-name>-main
        for child in temp_dir.iterdir():
            if child.is_dir() and child.name.endswith("-main"):
                return child
        raise RuntimeError("ZIP 解压后未找到模板目录")


def copy_item(src: Path, dst: Path, yes: bool) -> bool:
    """复制单个文件或目录，支持覆盖确认。"""
    if not src.exists():
        _info(f"跳过（不存在）: {src.name}")
        return False

    if dst.exists():
        if not yes:
            resp = input(f"  {src.name} 已存在，是否覆盖？[y/N] ")
            if resp.lower() != "y":
                _info(f"跳过: {src.name}")
                return False
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()

    if src.is_dir():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*EXCLUDE_PATTERNS))
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return True


def update_gitignore(target_dir: Path) -> None:
    """向 .gitignore 追加 Harness 相关规则。"""
    gitignore = target_dir / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    to_add = [line for line in GITIGNORE_LINES if line not in existing]
    if to_add:
        with open(gitignore, "a", encoding="utf-8") as f:
            f.write("\n".join(to_add) + "\n")
        _ok(f"已更新 {gitignore}")
    else:
        _info(".gitignore 已包含必要规则，跳过")


def collect_files(harness_root: Path) -> list[tuple[Path, Path]]:
    """收集所有需要复制的文件清单（用于 --list）。

    返回 (源相对路径, 目标相对路径) 列表，目标路径已应用重定向。
    """
    files: list[tuple[Path, Path]] = []
    for rel_path, _ in COPY_ITEMS:
        src = harness_root / rel_path
        if not src.exists():
            continue
        dst_rel = DOC_RELOCATIONS.get(rel_path, rel_path)
        if src.is_dir():
            for item in src.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(harness_root)
                    if not should_exclude_file(rel):
                        files.append((rel, rel))
        else:
            files.append((Path(rel_path), Path(dst_rel)))
    return sorted(files, key=lambda x: x[0])


def should_exclude_file(rel_path: Path) -> bool:
    """Return true for generated/runtime files that should not ship in manifests."""
    rel = rel_path.as_posix()
    parts = set(rel_path.parts)
    if "__pycache__" in parts or ".git" in parts:
        return True
    if rel_path.suffix == ".pyc":
        return True
    return any(rel == path or rel.startswith(f"{path}/") for path in EXCLUDE_PATHS)


def _rmtree_onerror(func, path, exc_info):
    """Windows 上删除只读文件（如 .git/objects）时的错误处理。"""
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)


def export_template(harness_root: Path, export_dir: Path, yes: bool = False) -> int:
    """导出干净模板到指定目录。"""
    print(f"\nHarness 模板: {harness_root}")
    print(f"导出目录:   {export_dir}")
    print()

    if export_dir.exists():
        if not yes:
            resp = input(f"  {export_dir} 已存在，是否清空后重新导出？[y/N] ")
            if resp.lower() != "y":
                return 0
        shutil.rmtree(export_dir, onerror=_rmtree_onerror)

    export_dir.mkdir(parents=True, exist_ok=True)

    print("复制文件...")
    for rel_path, desc in COPY_ITEMS:
        src = harness_root / rel_path
        dst_rel = DOC_RELOCATIONS.get(rel_path, rel_path)
        dst = export_dir / dst_rel
        if copy_item(src, dst, yes=True):
            _ok(f"{rel_path} -> {dst_rel} ({desc})")

    print("\n创建目录结构...")
    for d in DIRS_TO_CREATE:
        (export_dir / d).mkdir(parents=True, exist_ok=True)
        _ok(f"{d}/")

    print()
    update_gitignore(export_dir)

    # 同时写入清单文件
    manifest = export_dir / "MANIFEST.txt"
    manifest_files = collect_files(harness_root)
    with open(manifest, "w", encoding="utf-8") as f:
        f.write("# GuardHarness 文件清单\n")
        f.write(f"# 生成时间: {__import__('datetime').datetime.now().isoformat()}\n\n")
        for src_rel, dst_rel in manifest_files:
            if src_rel != dst_rel:
                f.write(f"{src_rel.as_posix()} -> {dst_rel.as_posix()}\n")
            else:
                f.write(f"{src_rel.as_posix()}\n")
    _ok(f"已生成文件清单: {manifest}")

    print(f"""
========================================
模板导出完成！
========================================

导出路径: {export_dir}

你可以直接复制此目录下的全部内容到新项目：
  cp -r {export_dir}/* /path/to/your-project/

或打包后分发：
  cd {export_dir.parent}
  zip -r harness-template.zip harness-template/
""")
    return 0


def verify_install(target_dir: Path) -> bool:
    """验证安装结果。"""
    _info("验证安装...")
    ok = True

    cli = target_dir / ".harness" / "agent-guard" / "cli.py"
    if cli.exists():
        _ok("Agent-Guard CLI 存在")
    else:
        _error("Agent-Guard CLI 不存在")
        ok = False

    settings = target_dir / ".claude" / "settings.json"
    if settings.exists():
        _ok("Claude Code 配置存在")
    else:
        _error("Claude Code 配置不存在")
        ok = False

    if (target_dir / "docs" / "superpowers" / "specs").exists():
        _ok(" specs 目录存在")
    else:
        _error("specs 目录不存在")
        ok = False

    if (target_dir / "docs" / "superpowers" / "plans").exists():
        _ok("plans 目录存在")
    else:
        _error("plans 目录不存在")
        ok = False

    return ok


def install(harness_root: Path, target_dir: Path, yes: bool = False) -> int:
    """执行安装。"""
    print(f"\nHarness 模板: {harness_root}")
    print(f"目标项目:   {target_dir}")
    print()

    if target_dir.resolve() == harness_root.resolve():
        _error("不能在 Harness 模板自身目录内运行安装")
        return 1

    if not (target_dir / ".git").exists():
        _warn("目标目录不是 Git 仓库，建议先运行: git init")
        if not yes:
            resp = input("是否继续？[y/N] ")
            if resp.lower() != "y":
                return 0

    print("复制文件...")
    for rel_path, desc in COPY_ITEMS:
        src = harness_root / rel_path
        dst_rel = DOC_RELOCATIONS.get(rel_path, rel_path)
        dst = target_dir / dst_rel
        if copy_item(src, dst, yes):
            _ok(f"{rel_path} -> {dst_rel} ({desc})")

    print("\n创建目录结构...")
    for d in DIRS_TO_CREATE:
        (target_dir / d).mkdir(parents=True, exist_ok=True)
        _ok(f"{d}/")

    print()
    update_gitignore(target_dir)

    if not verify_install(target_dir):
        return 1

    print("""
========================================
Harness 安装完成！
========================================

下一步操作：

1. 编辑 CLAUDE.md，填入你的项目信息
   - 项目简介、技术栈、团队信息

2. 安装 Python 依赖
   pip install pyyaml

3. 验证 Agent-Guard
   python .harness/agent-guard/cli.py --help

4. 在 Claude Code 中打开项目，测试：
   /init-feature "测试功能"
""")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="harness-install",
        description="GuardHarness 项目初始化安装器",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="自动确认覆盖，不提示",
    )
    parser.add_argument(
        "--target", "-t",
        default=".",
        help="目标项目目录（默认当前目录）",
    )
    parser.add_argument(
        "--export", "-e",
        default=None,
        metavar="DIR",
        help="导出干净模板到指定目录（不执行安装，仅复制文件）",
    )
    parser.add_argument(
        "--zip", "-z",
        default=None,
        metavar="FILE",
        help="导出并打包为 ZIP 文件",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出所有需要复制的文件清单",
    )
    args = parser.parse_args(argv)

    # 本地模式检测
    if is_local_mode():
        harness_root = get_harness_root()
    else:
        _error("--export / --list / --zip 必须在本地模板目录运行")
        return 1

    # 列出清单
    if args.list:
        print("\n需要复制的文件清单：\n")
        manifest_files = collect_files(harness_root)
        for src_rel, dst_rel in manifest_files:
            if src_rel != dst_rel:
                print(f"  {src_rel.as_posix()} -> {dst_rel.as_posix()}")
            else:
                print(f"  {src_rel.as_posix()}")
        print(f"\n共计 {len(manifest_files)} 个文件")
        return 0

    # 导出到目录
    if args.export:
        export_dir = Path(args.export).resolve()
        return export_template(harness_root, export_dir, yes=args.yes)

    # 导出为 ZIP
    if args.zip:
        zip_path = Path(args.zip).resolve()
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp) / "harness-template"
            ret = export_template(harness_root, export_dir, yes=args.yes)
            if ret != 0:
                return ret
            # 创建 ZIP
            archive = shutil.make_archive(
                str(zip_path.with_suffix("")),
                "zip",
                root_dir=export_dir.parent,
                base_dir=export_dir.name,
            )
            _ok(f"已打包: {archive}")
        return 0

    # 默认：安装到目标项目
    target_dir = Path(args.target).resolve()
    return install(harness_root, target_dir, yes=args.yes)


if __name__ == "__main__":
    sys.exit(main())
