---
name: finish-branch
description: 完成当前功能分支（加载 finishing-a-development-branch skill）
---

# finish-branch

## Usage

```
/finish-branch
```

## Workflow

1. 使用 Skill 工具加载 `finishing-a-development-branch` skill
2. 运行完整测试套件
3. 检查覆盖率（默认阈值 80%）
4. 运行 linter
5. 读取 `finishing-policy.yaml` 做出决策
6. 根据策略执行：auto_merge / create_pr / keep_branch
7. **Agent-Guard 状态转换**：运行 `python .harness/agent-guard/cli.py finish TASK-xxx` 将任务推进到 Done
8. 自动写 observation（commit-summary / test-failure / lint-failure / decision / entropy / taste）
9. 自动运行 `detect-entropy.sh` 和 `cluster-observations.sh`
10. 更新 CLAUDE.md 动态区块