# Hermes 兼容指南

## 技能映射

| Superpowers Skill | Claude Code | Hermes |
|:---|:---|:---|
| brainstorming | `.harness/superpowers/skills/brainstorming.md` | `skills/software-development/brainstorming.md` |
| writing-plans | `.harness/superpowers/skills/writing-plans.md` | `skills/software-development/writing-plans.md` |
| executing-plans | `.harness/superpowers/skills/executing-plans.md` | `skills/software-development/executing-plans.md` |
| finishing | `.harness/superpowers/skills/finishing-a-development-branch.md` | `skills/software-development/finishing.md` |
| tdd | `.harness/superpowers/skills/tdd.md` | `skills/software-development/tdd.md` |

## 配置映射

| 配置项 | Claude Code | Hermes |
|:---|:---|:---|
| 项目上下文 | `CLAUDE.md` | `.hermes.md` / `HERMES.md` |
| 团队规范 | `.harness/team/` | `~/.hermes/team/` |
| 技能目录 | `.harness/superpowers/skills/` | `~/.hermes/skills/` |
| 工作流定义 | `.harness/workflows/` | `~/.hermes/workflows/` |

## 工具映射

| 工具 | Claude Code | Hermes |
|:---|:---|:---|
| 文件读写 | 内置 Read/Edit | `read_file` / `write_file` |
| Shell | 内置 Bash | `terminal` |
| Git | 内置 + bash | `git_*` 系列 |
| Web | 内置 WebFetch/WebSearch | `web_search` / `web_extract` |

## 迁移步骤

1. 将 `.harness/superpowers/skills/*.md` 复制到 `~/.hermes/skills/`
2. 将 `CLAUDE.md` 内容合并至 `.hermes.md`
3. 将 `.harness/team/` 复制到 `~/.hermes/team/`
4. 将 `.harness/workflows/` 复制到 `~/.hermes/workflows/`
5. Hermes 自动加载技能并兼容 YAML frontmatter
