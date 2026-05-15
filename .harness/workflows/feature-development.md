---
name: Feature Development
version: "1.0"
description: 标准特性开发工作流

trigger:
  manual:
    commands:
      - "/init-feature <描述>"
      - "/plan-feature <spec-path>"
      - "/execute-plan <plan-path>"
      - "/finish-branch"

  ticket:
    source: linear
    status: ready_for_dev
    webhook: .harness/workflows/webhooks/linear-handler.py
---

## Context
{{ ticket.title }}
{{ ticket.description }}

## Agent Roles

| 角色 | 模型 | 职责 |
|:---|:---|:---|
| Planner | claude-opus-4-7 | 需求分析、规格扩展、验收标准定义 |
| Generator | claude-sonnet-4-6 | 代码实现、测试编写 |
| Evaluator | claude-opus-4-7 | 质量评估、测试验证、反馈循环 |

## Steps
1. [Planner] 分析需求 → 生成 spec
2. [Planner] 评审迭代（最多 3 轮）
3. [Generator] 读取 spec → 生成 plan
4. [Generator] 按 plan 执行任务
5. [Evaluator] 运行测试 → 质量评分
6. 通过 → PR；失败 → 反馈给 Generator

## Constraints
- No TODOs
- Must include test
- Follow .harness/team/standards.md
