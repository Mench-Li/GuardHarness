---
name: superpowers:finishing-a-development-branch
description: Use when implementation is complete, all tests pass, and you need to decide how to integrate the work
triggers: ["finish", "finish-branch", "merge", "pr"]
type: skill
version: "1.0"
---

# Finishing a Development Branch

## When to Use
When all tasks in the plan are complete and tests pass.

## Steps

1. **Load Constraints & Team Standards**
   - Read `.harness/team/shared-axioms.md` for team-level axioms and principles
   - Read `.harness/team/standards.md` for coding, testing, and documentation standards
   - Read `.claude/memory/MEMORY.md` (if exists) as the index to locate relevant memories
   - **These constraints inform merge/PR decisions and observation quality.**

2. **Verify tests pass**
   - Run full test suite: `pytest`
   - Run lint: `ruff check .`
   - Check coverage meets threshold (default 80%)

3. **Determine base branch**
   - Check current branch vs main/master
   - Check branch is behind main (should be 0 for auto-merge)

3. **Read finishing policy**
   - Load `.harness/superpowers/finishing-policy.yaml`
   - Evaluate conditions against current state

4. **Present 4 options**
   - **Local merge**: merge to base branch locally
   - **Push and create PR**: push branch, open PR
   - **Keep branch**: leave as-is (tests fail or human wants review)
   - **Discard**: abandon changes

5. **Auto-decision if applicable**
   - If policy matches auto_merge conditions, propose merge
   - If policy matches create_pr conditions, propose PR
   - Always ask for human confirmation on destructive actions

6. **Execute chosen option**
   - Clean up worktree if applicable
   - Update ticket/issue if applicable

7. **Agent-Guard 状态转换：finish（必须）**
   - 运行 `python .harness/agent-guard/cli.py finish TASK-xxx`
   - 将任务状态从 Entropy Review → Done
   - 如果之前未运行过 `review`，`finish` 会自动执行 review（G5 Verification Proof）
   - **不要跳过此步骤。** 任务只有到达 Done 才算正式完成。

8. **Diff 审查（Surgical Check 确认）**
   - 运行 `git diff`（或等效命令）
   - 确认只修改了计划中的文件，无 drive-by refactoring
   - 无相邻代码格式化、注释"改进"、变量重命名等无关变更
   - 如有无关变更，立即 revert

9. **自动观察与记忆更新**
   - 运行 `.claude/scripts/auto-observe.sh commit-summary`
   - 运行 `.claude/scripts/detect-entropy.sh 7`（扫描最近 7 天复杂度）
   - 运行 `.claude/scripts/cluster-observations.sh 30`（聚类最近 30 天观察）
   - 更新 `CLAUDE.md` 动态区块：`recent-decisions`、`architecture`

10. **释放 Lease**
    - 任务到达 Done 状态后 Lease 自动释放
    - 其他 Agent 可认领此任务槽位

## Proof of Work Checklist
- [ ] All tests pass
- [ ] Coverage >= 80%
- [ ] No critical lint errors
- [ ] Commit messages follow convention
