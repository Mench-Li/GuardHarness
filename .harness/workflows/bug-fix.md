---
name: Bug Fix
version: "1.0"
description: Bug 修复工作流

trigger:
  manual:
    commands:
      - "/fix-bug <issue-link>"

  ticket:
    source: linear
    status: ready_for_fix
---

## Context
{{ ticket.title }}
{{ ticket.description }}

## Steps
1. 复现 bug（编写失败测试）
2. 定位根因
3. 实现最小修复
4. 验证测试通过
5. 验证无回归
6. 完成分支（auto_merge if small change）

## Constraints
- 必须包含复现测试
- 修复必须最小化
- 必须验证周边功能未受影响
