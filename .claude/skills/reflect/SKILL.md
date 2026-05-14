---
name: reflect
description: 记忆反思（加载 memory-reflection skill）
---

# reflect

## Usage

```
/reflect
```

## Workflow

1. 使用 Skill 工具加载 `memory-reflection` skill
2. 自动运行 `cluster-observations.sh`、`detect-entropy.sh`、`detect-memory-conflicts.sh`
3. 扫描所有 observations、patterns、axioms
4. 提取稳定模式，更新 CLAUDE.md 动态区块
5. 检测跨项目模式并升级为全局公理
6. 记录 reflection 成本指标