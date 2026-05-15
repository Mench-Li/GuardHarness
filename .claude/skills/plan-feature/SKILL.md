---
name: plan-feature
description: 基于 spec 创建实现计划（加载 writing-plans skill）
---

# plan-feature

## Usage

```
/plan-feature <spec-path>

# 显式指定输出路径
/plan-feature docs/superpowers/specs/sprint-3/oauth2-login-design.md --output docs/superpowers/plans/sprint-3/oauth2-login.md
```

## Workflow

1. 使用 Skill 工具加载 `writing-plans` skill
2. 读取用户提供的 `spec-path` 文件
3. 严格按照 `plan-schema.yaml` 约束创建计划
4. 每个任务必须是可验证目标（Goal + Verify），禁止命令式语句
5. 禁止 TODO、占位符、模糊词
6. **必须包含 Agent-Guard 状态图**：在计划文档中嵌入 Mermaid 或 PlantUML 状态流图，展示本功能在 8 状态机中的流转路径（Inbox → Plan Ready → Executing → Patch Ready → Entropy Review → Done，以及 Blocked / Needs Simplification 旁路）
7. **必须标注 Gate 检查点**：每个 Task 的头部或尾部标注对应的 Gate 检查点（G1 Plan Valid / G2 Complexity Budget / G3 Entropy Check / G4 Surgical Check / G5 Verification Proof），说明该 Task 完成后需要触发哪个 Gate
8. 将计划保存到指定路径（未指定则默认 `docs/superpowers/plans/`）
9. **Agent-Guard 状态转换**：运行 `python .harness/agent-guard/cli.py plan TASK-xxx --approve` 将任务推进到 Plan Ready（task_id 从 plan 文件名或用户输入提取）