#!/usr/bin/env python3
# check-doc-sync.py
# 检查 README.md 和 HARNESS_USAGE_GUIDE.md 是否需要同步更新
# 用法: python .claude/scripts/check-doc-sync.py

import os
import re
import sys
from pathlib import Path


def get_version_from_file(path):
    """从 markdown 文件提取版本号（支持 版本: X.Y 或 **版本:** X.Y 格式）"""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # 匹配 "版本: 2.4" 或 "**版本:** 2.4"
    match = re.search(r"版本[:：]\s*\*?\*?\s*(\d+\.\d+)", content)
    if match:
        return match.group(1)
    return None


def check_branch_affects_docs():
    """检查当前分支是否有影响文档的变更未同步到 README/USAGE_GUIDE"""
    try:
        import subprocess

        # 获取当前分支与 main/master 的差异文件
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD", "origin/main"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # 尝试与 main 比较
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD", "main"],
                capture_output=True,
                text=True,
            )

        changed_files = result.stdout.strip().split("\n") if result.stdout else []

        # 检查是否有配置、技能、策略、Agent-Guard 变更
        doc_relevant_patterns = [
            ".harness/",
            ".harness/superpowers/skills/",
            ".claude/skills/",
            ".claude/scripts/",
            ".claude/settings.json",
            "plan-schema.yaml",
            "finishing-policy.yaml",
            "design-harness.yaml",
            "agent-guard/",
        ]

        has_relevant_change = any(
            any(p in f for p in doc_relevant_patterns) for f in changed_files if f
        )

        # 检查 README/USAGE_GUIDE 是否在本分支被修改
        readme_changed = any("README.md" in f for f in changed_files)
        usage_changed = any("HARNESS_USAGE_GUIDE.md" in f for f in changed_files)

        return {
            "has_relevant_change": has_relevant_change,
            "readme_changed": readme_changed,
            "usage_changed": usage_changed,
            "changed_files": changed_files,
        }
    except Exception as e:
        return {"error": str(e)}


def main():
    root = Path(__file__).parent.parent.parent
    readme = root / "README.md"
    usage = root / "HARNESS_USAGE_GUIDE.md"

    readme_ver = get_version_from_file(readme)
    usage_ver = get_version_from_file(usage)

    print("=== Documentation Sync Check ===")
    print(f"README.md version: {readme_ver or 'NOT FOUND'}")
    print(f"HARNESS_USAGE_GUIDE.md version: {usage_ver or 'NOT FOUND'}")

    exit_code = 0

    if readme_ver and usage_ver and readme_ver != usage_ver:
        print(f"\n[WARNING] Version mismatch: README={readme_ver}, USAGE_GUIDE={usage_ver}")
        exit_code = 1

    branch_info = check_branch_affects_docs()
    if "error" in branch_info:
        print(f"\n[INFO] Could not check git diff: {branch_info['error']}")
    elif branch_info.get("has_relevant_change"):
        if not branch_info["readme_changed"] or not branch_info["usage_changed"]:
            print("\n[WARNING] This branch changes harness configuration/skills, but README.md or HARNESS_USAGE_GUIDE.md was NOT updated.")
            print("Rule: After every feature iteration, update README.md and HARNESS_USAGE_GUIDE.md to reflect the latest changes.")
            exit_code = 1
        else:
            print("\n[OK] Documentation files were updated along with harness changes.")
    else:
        print("\n[OK] No harness-relevant changes detected in this branch.")

    if exit_code == 0:
        print("\nResult: PASS")
    else:
        print("\nResult: FAIL — Please sync README.md and HARNESS_USAGE_GUIDE.md before finishing.")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
