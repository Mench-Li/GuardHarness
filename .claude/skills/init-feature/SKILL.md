---
name: init-feature
description: 开始新功能设计（加载 brainstorming skill）
---

# init-feature

## Usage

```
/init-feature <功能描述>

# 显式指定输出路径（推荐用于 Scrum/迭代管理）
/init-feature 把设计文档写到 docs/superpowers/specs/sprint-3/oauth2-login-design.md，设计OAuth2登录
```

## Workflow

1. 使用 Skill 工具加载 `brainstorming` skill
2. 将 `<功能描述>` 作为设计主题传入
3. 严格按照 brainstorming skill 的工作流执行
4. 一次只问一个澄清问题
5. 提出 2-3 种方案并明确标记最简单方案
6. 将最终 spec 保存到指定路径（未指定则默认 `docs/superpowers/specs/`）
7. **初始化 Agent-Guard 任务**：运行 `python .harness/agent-guard/cli.py init TASK-xxx --spec <spec-path>`（task_id 从 spec 文件名或用户输入提取）
8. 完成后提醒用户运行 `/plan-feature`