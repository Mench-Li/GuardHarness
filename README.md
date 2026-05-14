# GuardHarness

> **AI 原生开发工作流模板** —— 基于 Superpowers × Harness Engineering，让 Claude Code 越用越聪明。
>
> 版本: 2.5 | 日期: 2026-05-13
> 新增: G2 语义感知拆分 + 多 Agent 并行认领 + 子任务进度追踪 + 记忆系统全自动沉淀 + 技能自动驱动完整状态生命周期（execute → patch → review → finish）

---

## 目录

1. [项目简介](#项目简介)
2. [核心特性](#核心特性)
3. [工程流转全景图](#工程流转全景图)
4. [目录结构](#目录结构)
5. [快速开始](#快速开始)
6. [四阶段工作流详解](#四阶段工作流详解)
7. [记忆系统（越用越聪明）](#记忆系统越用越聪明)
8. [命令与脚本参考](#命令与脚本参考)
9. [配置体系](#配置体系)
10. [故障排除](#故障排除)
11. [相关文档](#相关文档)

---

## 项目简介

GuardHarness 是一套完整的 **AI 原生软件开发工作流模板**，将 [OpenAI Harness Engineering](https://openai.com/zh-Hans-CN/index/harness-engineering/)、[Anthropic 三角色架构](https://www.anthropic.com/engineering/harness-design-long-running-apps)、[Cursor 递归 Planner-Worker](https://cursor.com/cn/blog/self-driving-codebases) 和 [Superpowers 插件](https://github.com/anthropics/superpowers) 整合为一个可直接落地的工程体系。

**核心目标**：
- 让 AI Agent 能够**长时间自主运行**（数小时保持方向和质量）
- 让 AI Agent 能够**大规模并行协作**（子代理自动执行任务）
- 让项目**越用越聪明**（自动沉淀记忆、动态更新上下文）
- 让开发者从"写 prompt 监督 AI"转变为"设计 AI 的工作环境"

**本项目是什么**：
- 这是一个**模板工程**，你可以将其核心配置复制到任何新项目，立即获得完整的 AI 驱动开发工作流
- 包含 17 个 Superpowers 技能定义、结构化记忆系统、自动化脚本、约束配置
- 自带示例数据，演示记忆系统如何运转

---

## 核心特性

### 1. 八状态闭环工作流（含旁路）

Agent-Guard 状态机将传统四阶段升级为 **8 状态控制平面**：

**主线（6 状态）：**

```
/init-feature     →  /plan-feature     →  /execute-plan
     ↓                    ↓                    ↓
   Inbox             Plan Ready          Executing
     ↓                    ↓                    ↓
  (设计)               (计划)              (执行)
   spec.md             plan.md            代码+测试
                                              ↓
                                         Patch Ready
                                              ↓
                                       (代码完成)
                                              ↓
                                        Entropy Review
                                              ↓
                                          /finish-branch
                                               ↓
                                              Done
                                           (完成)
                                         merge/PR
```

**旁路（2 状态）：**

```
Blocked               — 外部依赖/等待人工输入（可从任意状态进入）
Needs Simplification  — 熵审查失败后的回流状态（G3/G5 失败后进入）
```

**每个状态转换都有硬 Gate 把关**：G1 Plan Valid → G2 Complexity Budget → G3 Entropy Check → G4 Surgical Check → G5 Verification Proof。Gate 未通过则**物理阻断**，不会进入下一状态。

每个阶段都有对应的 Superpowers Skill 驱动，AI 自动加载相关上下文、遵循约束、产出标准化产物。

### 2. 结构化记忆系统（Memory × Harness）

本项目最大的差异化能力：**自动沉淀 + 智能复用**。

```
每次交互
    │
    ▼
┌─────────────────┐
│  observations/  │  原始观察（自动/手动写入）
│  （观察层 L1）   │
└────────┬────────┘
         │ 每周 /reflect
         ▼
┌─────────────────┐
│   patterns/     │  稳定模式（≥3 次出现提炼）
│  （反射层 L2）   │
└────────┬────────┘
         │ 跨项目验证
         ▼
┌─────────────────┐
│  user/axioms.md │  全局公理（跨项目通用）
│  （公理层 L3）   │
└─────────────────┘
         │
         ▼
    下次工作流更聪明
```

**新增 5 层记忆类型**（v2.0）及自动化状态：

| 层级 | 目录 | 写入触发 | 自动化程度 |
|:---|:---|:---|:---|
| **Observations** | `observations/` | `finish-branch` / `fix-bug` 后自动 `auto-observe` | **全自动** |
| **Patterns** | `patterns/` | `/reflect` 中从 observations 提炼 | **需手动触发 `/reflect`** |
| **Decisions** | `decisions/` | `/reflect` 中提取，或变更架构文件时自动 `auto-observe decision` | **半自动** |
| **Failures** | `failures/` | `/reflect` 中提取系统性失败 | **需手动触发 `/reflect`** |
| **Entropy** | `entropy/` | `/reflect` 中自动 `detect-entropy` + 人工确认 | **半自动** |
| **Invariants** | `invariants/` | **显式声明，永不自动升级** | **必须人工写入** |
| **Taste** | `taste/` | `/reflect` 中提取，或收到 review feedback 时自动 `auto-observe taste` | **半自动** |

> **注意**：`load-memory-context` 脚本供人类快速浏览，AI 执行 skill 时会直接读取各层文件，无需你手动运行。

### 3. 17 个 Superpowers 技能

覆盖完整开发生命周期：

| 类别 | 技能 | 作用 |
|:---|:---|:---|
| **流程** | `brainstorming` | 设计阶段：头脑风暴 → spec |
| **流程** | `writing-plans` | 计划阶段：spec → 实现计划 |
| **流程** | `executing-plans` | 执行阶段：手动逐步执行 |
| **流程** | `subagent-driven-development` | 执行阶段：子代理自动执行 |
| **流程** | `finishing-a-development-branch` | 完成阶段：测试 → merge/PR |
| **流程** | `memory-reflection` | 记忆提炼：observation → pattern → axiom |
| **纪律** | `test-driven-development` | 无失败测试不写生产代码 |
| **纪律** | `systematic-debugging` | 先找根因再修复 |
| **纪律** | `verification-before-completion` | 声称完成前必须有验证证据 |
| **协作** | `requesting-code-review` | 分派审查代理 |
| **协作** | `receiving-code-review` | 验证再实施，不盲从 |
| **效率** | `dispatching-parallel-agents` | 并行分派代理修复多个 bug |
| **效率** | `using-git-worktrees` | 创建隔离工作区 |
| **效率** | `writing-skills` | TDD 方式编写新技能 |
| **基础设施** | `using-superpowers` | 每次会话强制检查并加载适用技能 |
| **子代理** | `planner-prompt` | Planner 角色提示词 |
| **子代理** | `evaluator-prompt` | Evaluator 角色提示词 |

### 4. 自动化脚本工具链

| 脚本 | 功能 |
|:---|:---|
| `auto-observe.sh` | 从 git diff / test output / lint output 自动生成观察记录 |
| `cluster-observations.sh` | 基于 tags + 关键词重叠自动聚类 observation |
| `detect-memory-conflicts.sh` | 检测新项目模式与全局公理的冲突 |
| `check-reflection-due.sh` | 每周检查 reflection 是否到期 |
| `check-invariants.sh` | 按领域加载架构不变量 |
| `detect-entropy.sh` | 分析最近 git diff 检测复杂度反模式 |
| `load-memory-context.sh` | 统一加载全部 5 层记忆 + 现有模式 |

### 5. Karpathy 编码四原则（内置约束）

将 Andrej Karpathy 的 AI 辅助编码理念编码为**可执行约束**，融入每个工作流阶段：

| 原则 | 作用阶段 | 执行方式 |
|:---|:---|:---|
| **Think Before Coding** | 设计阶段 | 暴露假设、呈现多解、对模糊需求 push back |
| **Simplicity First** | 全阶段 | 最小代码解决问题；禁止推测性功能；禁止单用抽象 |
| **Surgical Changes** | 执行阶段 | 只碰任务要求的文件；不改相邻代码/注释/格式；只删自己引入的未使用代码 |
| **Goal-Driven Execution** | 计划+执行 | 任务描述必须是可验证目标（Goal + Verify），而非命令式语句 |

这两个原则被提升为**架构不变量**：`general-simplicity-first`（high）和 `general-surgical-changes`（medium），在**代码生成前强制加载**。

### 6. Agent-Guard 状态管控与中断恢复

Agent-Guard 是本项目的**状态驱动控制平面**，将原本基于 prompt 的工作流升级为**状态机 + 硬 Gate + 恢复协议**。

**核心能力：**

| 能力 | 说明 |
|:---|:---|
| **状态透明** | 每个任务在任何时刻都有明确状态：主线 6 态 + 旁路 2 态 |
| **硬 Gate** | 5 个否决权式状态转换检查，未通过则**物理阻断**进度 |
| **旁路状态** | `Blocked`（外部依赖）、`Needs Simplification`（熵审查失败回流）|
| **中断恢复** | 任务中断后通过 Snapshot 机制恢复，只加载必要上下文（目标 `< 30 秒`）|
| **Lease 互斥** | 非终端状态自动持有 Lease，防止多 Agent 竞争同一任务 |

**状态机（8 状态）：**

```
主线:
  Inbox → Plan Ready → Executing → Patch Ready → Entropy Review → Done

旁路:
  Blocked                  # 外部依赖 / 等待人工输入（可从任意状态进入）
  Needs Simplification     # Entropy Review 失败后的回流状态
```

**5 个硬 Gate：**

| Gate | 转换点 | 检查内容 | 阻断方式 |
|:---|:---|:---|:---|
| G1 Plan Valid | Inbox → Plan Ready | Plan 无占位符、无模糊词、包含必要章节 | **硬阻断** |
| G2 Complexity Budget | Inbox → Plan Ready | 预估文件/步骤数不超预算 | 警告（Phase 1）|
| G3 Entropy Check | Plan Ready → Executing / Needs Simplification → Executing | 运行 `detect-entropy.sh`，无新增复杂度反模式 | **硬阻断** |
| G4 Surgical Check | Executing → Patch Ready | Diff 只修改相关文件，无 drive-by refactoring | 建议（Phase 1）|
| G5 Verification Proof | Entropy Review → Done | 测试通过 + lint 通过 + 覆盖率达标 | **硬阻断** |

**Agent-Guard 命令：**
```bash
# 主线生命周期
python .harness/agent-guard/cli.py init TASK-001 --spec <spec-path>
python .harness/agent-guard/cli.py plan TASK-001 --approve
python .harness/agent-guard/cli.py execute TASK-001
python .harness/agent-guard/cli.py patch TASK-001
python .harness/agent-guard/cli.py review TASK-001
python .harness/agent-guard/cli.py finish TASK-001

# 旁路命令
python .harness/agent-guard/cli.py simplify TASK-001   # Entropy Review → Needs Simplification
python .harness/agent-guard/cli.py block TASK-001      # 任意状态 → Blocked
python .harness/agent-guard/cli.py unblock TASK-001    # Blocked → 之前状态

# 查询与恢复
python .harness/agent-guard/cli.py status TASK-001
python .harness/agent-guard/cli.py resume TASK-001
```

### 7. 三层配置架构

```
L1 项目级: .harness/superpowers/    —— 每个项目必须有的核心配置
L2 团队级: .harness/team/           —— 通过 git submodule 共享
L3 组织级: .harness/workflows/      —— 工作流定义和模型路由
```

---

## 工程流转全景图

### 单次功能开发的完整流转

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         阶段一：设计（Brainstorming）                        │
│  Agent-Guard: Inbox                                                        │
│                                                                             │
│  用户指令: /init-feature "为用户添加 OAuth2 登录"                             │
│  Agent-Guard: python .harness/agent-guard/cli.py init TASK-001 --spec ...   │
│                                                                             │
│  Gate: G1 Plan Valid —— 验证 spec 无占位符、无模糊词                         │
│                                                                             │
│  加载技能: brainstorming + using-superpowers                                │
│  加载约束: Think Before Coding, Simplicity First                            │
│  加载记忆: patterns + decisions + invariants + taste + CLAUDE.md 动态区块   │
│                                                                             │
│  人机交互:                                                                  │
│    你提供描述 → AI 暴露假设 → AI 提问（一次一个）→ 你回答 → AI 呈现设计     │
│                                                                             │
│  产出: docs/superpowers/specs/2026-05-07-oauth2-login-design.md             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         阶段二：计划（Writing Plans）                        │
│  Agent-Guard: Inbox → Plan Ready                                           │
│                                                                             │
│  用户指令: /plan-feature docs/superpowers/specs/...-design.md               │
│  Agent-Guard: python .harness/agent-guard/cli.py plan TASK-001 --approve    │
│                                                                             │
│  Gate: G1 Plan Valid —— plan 符合 schema，无 placeholders、无 TODOs        │
│  Gate: G2 Complexity Budget —— 预估文件数≤20、步骤数≤15（Phase 1 警告模式） │
│                                                                             │
│  加载技能: writing-plans                                                    │
│  加载约束: plan-schema.yaml（禁止 TODO、测试先行、5 分钟步长、验证命令）     │
│  加载记忆: 历史估算偏差 + entropy 反模式 + patterns/文件命名约定             │
│                                                                             │
│  产出: docs/superpowers/plans/2026-05-07-oauth2-login.md                    │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         阶段三：执行（Executing Plans）                      │
│  Agent-Guard: Plan Ready → Executing → Patch Ready → Entropy Review        │
│                                                                             │
│  用户指令: /execute-plan docs/superpowers/plans/...-.md                     │
│  Agent-Guard:                                                            │
│    execute  → Plan Ready → Executing（技能自动执行）                       │
│    patch    → Executing → Patch Ready（所有任务完成后自动调用）            │
│    review   → Patch Ready → Entropy Review（patch 通过后自动调用）         │
│                                                                             │
│  Gate: G3 Entropy Check —— 运行 detect-entropy.sh，阻断复杂度爆炸          │
│  Gate: G4 Surgical Check —— 每步完成后验证 diff 只改相关文件               │
│                                                                             │
│  加载技能: executing-plans / subagent-driven-development                    │
│  加载约束: general-simplicity-first（high，预生成检查）                      │
│            general-surgical-changes（medium，预生成检查）                    │
│  加载记忆: failures + entropy + invariants + taste                          │
│  自动行为: 获取 Lease（防止多 Agent 竞争）、生成 Snapshot                   │
│                                                                             │
│  执行方式 A：子代理驱动（推荐）                                              │
│    - 每个任务分派独立子代理（implementer）                                  │
│    - 两阶段审查：spec 合规性 → 代码质量                                      │
│    - 子代理自审：Surgical Review + Diff Self-Check（确认只改必要文件）      │
│    - 同一会话内完成，无需人工介入                                            │
│                                                                             │
│  执行方式 B：本会话逐步执行                                                  │
│    - 在当前会话中逐步执行                                                   │
│    - 适合需要频繁人工确认的任务                                             │
│                                                                             │
│  产出: 代码文件 + 测试文件 + 多次 git commit（每个任务一次）                │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         阶段四：完成（Finishing）                            │
│  Agent-Guard: Entropy Review → Done                                        │
│                                                                             │
│  用户指令: /finish-branch                                                   │
│  Agent-Guard: python .harness/agent-guard/cli.py finish TASK-001            │
│                                                                             │
│  Gate: G5 Verification Proof —— 测试通过 + lint 通过 + 覆盖率≥80%          │
│                                                                             │
│  加载技能: finishing-a-development-branch + verification-before-completion  │
│  加载约束: finishing-policy.yaml（auto_merge / create_pr / keep_branch）     │
│  自动行为:                                                                  │
│    - 运行完整测试套件                                                       │
│    - 检查覆盖率（默认阈值 80%）                                             │
│    - 运行 linter                                                            │
│    - Diff 审查（verification-before-completion skill）                       │
│    - 读取 finishing-policy.yaml 自动决策: merge / PR / 保留分支             │
│                                                                             │
│  自动沉淀记忆:                                                              │
│    - 写 observation（commit-summary / decision / entropy / taste）          │
│    - 自动运行 detect-entropy.sh（扫描最近 7 天复杂度）                      │
│    - 自动运行 cluster-observations.sh（聚类最近 30 天观察）                 │
│    - 更新 CLAUDE.md 动态区块: recent-decisions, architecture                │
│                                                                             │
│  决策规则:                                                                  │
│    - 测试通过 + 覆盖率≥80% + 无严重 lint 错误 + 分支未落后 → auto_merge     │
│    - 测试通过 + 复杂度评分<high → create_pr                                 │
│    - 测试失败 → keep_branch + 创建 observation（即使失败也要记录教训）      │
│                                                                             │
│  旁路: Blocked / Needs Simplification                                       │
│    - Blocked: 外部依赖时 `agent-guard block TASK-001 --reason "等待API"`     │
│    - Needs Simplification: G3/G5 失败后 `agent-guard simplify TASK-001`     │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  │ 每周或里程碑
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         记忆提炼（Reflection）                               │
│  用户指令: /reflect                                                         │
│                                                                             │
│  Agent-Guard: 可在任意状态运行，不影响任务生命周期                           │
│                                                                             │
│  加载技能: memory-reflection                                                │
│  加载记忆: 全部 5 层记忆 + CLAUDE.md 动态区块                                │
│                                                                             │
│  七阶段工作流:                                                              │
│    Phase 1: Scan      —— 扫描 observations、patterns、axioms                │
│    Phase 2: Extract   —— 提取决策、陷阱、纠正、模式（聚类辅助）              │
│    Phase 3: Filter    —— 稳定性检查 + 冲突检测 + 条件化升级判断              │
│    Phase 4: Write     —— 写入 patterns/ + 更新 CLAUDE.md 动态区块           │
│    Phase 5: Cross-Prj —— 检测跨项目模式 → 升级为全局公理                     │
│    Phase 6: Compact   —— 归档旧观察 + 更新 .last-reflection                  │
│    Phase 7: Metrics   —— 记录 reflection 成本、pattern 命中率、转化率        │
│                                                                             │
│  产出:                                                                      │
│    - 新的 pattern 文件（如 patterns/api-client-pattern.md）                 │
│    - 更新的 CLAUDE.md 动态区块                                              │
│    - 全局公理候选（写入 ~/.claude/memory/user/axioms.md）                   │
│    - metrics 更新（reflection-costs.json, pattern-hit-rate.json）           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 记忆闭环流转

```
        用户输入
           │
           ▼
   ┌───────────────┐    加载：全局公理 + 本项目历史架构模式
   │  brainstorming │    设计时参考历史决策 → 产出 spec.md
   └───────┬───────┘
           ▼
   ┌───────────────┐    加载：过往 plan 估算偏差 + 文件命名约定
   │  writing-plans │    参考历史模式 → 产出 plan.md
   └───────┬───────┘
           ▼
   ┌───────────────┐    加载：常见陷阱 + 测试模式 + 架构不变量
   │  executing-    │    编码避坑 → 产出代码 + 测试
   │  plans         │
   └───────┬───────┘
           ▼
   ┌───────────────┐    自动写 observation（commit-summary / decision /
   │  finish-branch │    entropy / taste）+ 自动 detect-entropy +
   │               │    自动 cluster-observations + 更新 CLAUDE.md
   └───────────────┘
           │
           ▼
      /reflect    ──────→  memory-reflection skill（自动运行
           │                cluster-observations / detect-entropy /
           │                detect-memory-conflicts，无需手动执行）
           │
           ▼
      下次循环更聪明
```

---

## 目录结构

```
.
├── .claude/                              # Claude Code 配置 + 记忆系统
│   ├── memory/                           # 结构化记忆存储
│   │   ├── MEMORY.md                     # 记忆索引和使用规范
│   │   ├── observations/                 # 原始观察记录（自动/手动写入）
│   │   ├── patterns/                     # 已提炼的稳定模式（≥3 次出现）
│   │   ├── retro/                        # 迭代回顾汇总
│   │   ├── decisions/                    # 架构决策记忆（v2.0 新增）
│   │   ├── failures/                     # 事故/教训记忆（v2.0 新增）
│   │   ├── entropy/                      # 复杂度反模式（v2.0 新增）
│   │   ├── invariants/                   # 架构不变量（v2.0 新增）
│   │   ├── taste/                        # 编码偏好（v2.0 新增）
│   │   ├── metrics/                      # 成本与质量仪表板
│   │   │   ├── METRICS.md                # 指标定义
│   │   │   ├── reflection-costs.json     # Reflection 成本追踪
│   │   │   ├── pattern-hit-rate.json     # Pattern 命中率
│   │   │   └── observation-conversion.csv # 转化率追踪
│   │   └── user/                         # 全局级记忆备份
│   │       ├── role.md                   # 用户角色、目标
│   │       ├── preferences.md            # 工作习惯、偏好
│   │       └── axioms.md                 # 跨项目公理
│   ├── skills/                           # Slash Command 技能（Claude Code 自动识别）
│   │   ├── init-feature/SKILL.md         # /init-feature 命令
│   │   ├── plan-feature/SKILL.md         # /plan-feature 命令
│   │   ├── execute-plan/SKILL.md         # /execute-plan 命令
│   │   ├── finish-branch/SKILL.md        # /finish-branch 命令
│   │   ├── fix-bug/SKILL.md              # /fix-bug 命令
│   │   └── reflect/SKILL.md              # /reflect 命令
│   ├── scripts/                          # 自动化脚本
│   │   ├── auto-observe.sh               # 自动化观察生成器
│   │   ├── auto-observe.ps1              # PowerShell 版本
│   │   ├── cluster-observations.sh       # Observation 自动聚类
│   │   ├── detect-memory-conflicts.sh    # 记忆冲突检测
│   │   ├── check-reflection-due.sh       # Reflection 到期检查
│   │   ├── check-invariants.sh           # 架构不变量加载（v2.0）
│   │   ├── detect-entropy.sh             # 复杂度反模式检测（v2.0）
│   │   └── load-memory-context.sh        # 统一记忆加载器（v2.0）
│   ├── settings.json                     # Claude Code 配置（技能、钩子、权限）
│   └── settings.local.json               # 本地权限覆盖
│
├── .harness/                             # Harness Engineering 配置
│   ├── agent-guard/                      # 状态驱动控制平面
│   │   ├── state_machine.py              # 8 状态机核心
│   │   ├── snapshot.py                   # Snapshot 恢复协议
│   │   ├── lease.py                      # Lease + Heartbeat
│   │   ├── gates.py                      # 5 个硬 Gate 实现
│   │   ├── cli.py                        # CLI 入口
│   │   ├── test_agent_guard.py           # 单元测试
│   │   ├── test_e2e.py                   # E2E 测试
│   │   ├── state/                        # 状态持久化
│   │   ├── snapshots/                    # Snapshot 文件
│   │   └── leases/                       # Lease 文件
│   ├── superpowers/                      # L1: 项目级配置（必需）
│   │   ├── skills/                       # 17 个 Superpowers 技能定义
│   │   │   ├── memory-reflection.md      # 记忆提炼核心技能
│   │   │   ├── brainstorming.md          # 设计阶段
│   │   │   ├── writing-plans.md          # 计划阶段
│   │   │   ├── executing-plans.md        # 执行阶段（手动）
│   │   │   ├── subagent-driven-development/
│   │   │   │   ├── SKILL.md              # 子代理驱动开发
│   │   │   │   ├── implementer-prompt.md # 实现者提示词
│   │   │   │   ├── spec-reviewer-prompt.md
│   │   │   │   └── code-quality-reviewer-prompt.md
│   │   │   ├── finishing-a-development-branch.md
│   │   │   ├── test-driven-development.md
│   │   │   ├── systematic-debugging.md
│   │   │   ├── verification-before-completion.md
│   │   │   ├── requesting-code-review/
│   │   │   │   ├── SKILL.md
│   │   │   │   └── code-reviewer.md
│   │   │   ├── receiving-code-review.md
│   │   │   ├── dispatching-parallel-agents.md
│   │   │   ├── using-git-worktrees.md
│   │   │   ├── writing-skills.md
│   │   │   ├── using-superpowers.md
│   │   │   ├── planner-prompt.md
│   │   │   └── evaluator-prompt.md
│   │   ├── plan-schema.yaml              # 计划约束验证规则
│   │   ├── finishing-policy.yaml         # 完成阶段自动决策 + 记忆写入
│   │   └── design-harness.yaml           # Planner-Evaluator 循环配置
│   ├── workflows/                        # L3: 组织级配置
│   │   ├── feature-development.md        # 特性开发工作流模板
│   │   ├── bug-fix.md                    # Bug 修复工作流模板
│   │   ├── manual-mode.yaml              # 手动触发命令映射（含 /reflect）
│   │   └── model-routing.yaml            # 角色-模型映射配置
│   ├── team/                             # L2: 团队级配置（git submodule）
│   │   ├── shared-axioms.md              # 团队公理
│   │   ├── standards.md                  # 编码/测试/文档标准
│   │   └── reviewer-pool.yaml            # Reviewer 代理分配规则
│   └── HERMES_COMPAT.md                  # Hermes 兼容指南
│
├── docs/superpowers/                     # 设计文档和实现计划
│   ├── specs/                            # 设计规格
│   │   ├── 2026-04-20-guardharness-design.md
│   │   ├── 2026-04-20-guardharness-architecture-visual.md
│   │   ├── architecture-visual.html      # 架构可视化（在线）
│   │   └── architecture-visual-offline.html
│   └── plans/                            # 实现计划
│       └── 2026-04-20-guardharness.md
│
├── examples/                             # 示例配置
│   └── team-harness/                     # 团队模板示例
│       ├── shared-axioms.md
│       ├── standards.md
│       └── reviewer-pool.yaml
│
├── CLAUDE.md                             # 项目上下文（含动态区块标记）
├── HARNESS_USAGE_GUIDE.md                # 详细使用手册
├── MEMORY_HARNESS_GUIDE.md               # 记忆系统完整指南
├── harness-engineering-guide.md          # Harness Engineering 深度指南
└── README.md                             # 本文档
```

---

## 快速开始

### 前提条件

- [Claude Code](https://claude.ai/code) 已安装并配置
- [Superpowers 插件](https://github.com/anthropics/superpowers) 已安装（`claude plugins install superpowers`）
- Git 仓库已初始化
- Bash 环境（Git Bash / WSL / Linux / macOS）

### 方式 A：一行命令安装（推荐）

前提：已安装 Python 3.10+ 和 Git

一行命令自动从远程仓库克隆 Harness 模板并安装到当前目录：

**Bash / Git Bash / WSL / macOS / Linux：**
```bash
curl -fsSL https://raw.githubusercontent.com/Mench-Li/GuardHarness/main/install.sh | bash
```

**Windows PowerShell：**
```powershell
irm https://raw.githubusercontent.com/Mench-Li/GuardHarness/main/install.ps1 | iex
```

install.sh / install.ps1 会自动 `git clone --depth 1` 仓库到临时目录，然后执行安装。

**本地模板安装（已下载 harness 仓库）：**
```bash
# 在 harness 模板目录内直接运行
python install.py --export ./harness-template
# 然后将 harness-template/ 内容复制到新项目

# 或直接安装到目标项目
python install.py --target /path/to/your-project
```

安装脚本会自动完成：复制核心文件（含 `README.md`）、创建目录结构、更新 `.gitignore`。

**本地导出（不发布 GitHub 时分发模板）：**
```bash
# 列出所有需要复制的文件
python install.py --list

# 导出干净模板到指定目录
python install.py --export ./harness-template -y

# 直接打包成 ZIP
python install.py --zip ./harness-template.zip -y
```

### 方式 B：Git 远程仓库安装（已有远程仓库）

如果你已将 Harness 发布到 Git 远程仓库，可在目标项目中直接克隆并安装：

```bash
# 在目标项目根目录执行
git clone --depth 1 https://github.com/Mench-Li/GuardHarness.git /tmp/harness
python /tmp/harness/install.py --target .

# 或导出模板后手动复制
git clone --depth 1 https://github.com/Mench-Li/GuardHarness.git /tmp/harness
python /tmp/harness/install.py --export ./harness-template -y
cp -r ./harness-template/* ./
```

### 方式 C：手工复制

```bash
# 从本模板复制到目标项目
cp -r /path/to/harness/.harness ./
cp -r /path/to/harness/.claude ./
cp /path/to/harness/CLAUDE.md ./
```

### 第二步：初始化项目配置

编辑 `CLAUDE.md`，填入你的项目特定信息（保留所有 `<!-- DYNAMIC-BLOCK: xxx -->` 标记）：

```markdown
# Project Context

## 项目简介
[一句话描述你的项目是做什么的]

## 技术栈
- 语言: Python 3.11
- 框架: FastAPI
- 数据库: PostgreSQL
- ...

## Superpowers Workflow
本项目使用 Superpowers × Harness Engineering 工作流。
完整配置位于 `.harness/` 目录。

## Quick Commands
- 开始新功能设计: `/init-feature <描述>`
- 创建实现计划: `/plan-feature <spec-path>`
- 执行计划: `/execute-plan <plan-path>`
- 完成分支: `/finish-branch`
- 记忆反思: `/reflect`

### 显式指定文档路径（Scrum / 迭代管理）
```
/init-feature 把设计文档写到 docs/superpowers/specs/sprint-3/oauth2-login-design.md，设计OAuth2登录
/plan-feature docs/superpowers/specs/sprint-3/oauth2-login-design.md --output docs/superpowers/plans/sprint-3/oauth2-login.md
/execute-plan docs/superpowers/plans/sprint-3/oauth2-login.md
```

## Project Standards
- 所有设计文档存放于 `docs/superpowers/specs/`
- 所有实现计划存放于 `docs/superpowers/plans/`
- 隔离工作区使用 `.worktrees/`

## Skill 覆盖与约束加载机制

### 本地 Skill 覆盖官方插件

Harness 通过 `.claude/settings.json` 注册本地 skill 路径。为了让本地增强版 skill 覆盖 Superpowers 官方插件中的同名 skill，**所有本地 skill 的 `name` 必须使用 `superpowers:` 前缀**（如 `superpowers:writing-plans`）。

当输入 `/plan-feature` 等 slash command 时，系统会定向到 `superpowers:writing-plans`。若本地 skill 的 name 与之完全匹配，则本地版本生效，否则回退到官方插件版本。

### 约束与记忆自动加载

每个 slash command（`/init-feature`、`/plan-feature`、`/execute-plan`、`/finish-branch`、`/fix-bug`、`/reflect`）执行前，AI **必须先读取**以下文件并将约束注入上下文：

1. `.harness/team/shared-axioms.md` — 团队级公理与原则
2. `.harness/team/standards.md` — 编码/测试/文档标准
3. `.claude/memory/MEMORY.md` — 项目记忆索引（如存在）

这意味着每次使用 Harness 工作流时，团队规范和项目历史记忆都会自动参与决策，避免重复踩坑。

## Memory System
本项目启用结构化记忆系统，越用越聪明。
...
```

### 第三步：添加到 .gitignore

```bash
# .gitignore
.worktrees/
```

### 第四步：验证 Agent-Guard

```bash
# 验证 Agent-Guard 可用
python .harness/agent-guard/cli.py --help

# 快速测试完整生命周期
python .harness/agent-guard/cli.py init TEST-001
python .harness/agent-guard/cli.py plan TEST-001 --approve
python .harness/agent-guard/cli.py status TEST-001
```

### 第五步：验证 Claude Code 配置

**Claude Code 桌面/终端应用：**

打开项目后，输入 `/init-feature '测试功能'`。如果看到技能加载提示并进入设计工作流，说明 `.claude/skills/` 已被自动识别：

```
Skill(init-feature)
  Successfully loaded skill
```

**VS Code 聊天会话：**

VS Code 中的 Claude 聊天不会自动扫描 `.claude/skills/`，而是通过 `CLAUDE.md` 上下文识别命令。

1. 如果刚修改过 `CLAUDE.md`，先输入 `/clear` 清空上下文，让系统重新加载
2. 然后输入 `/init-feature '测试功能'`
3. AI 会按照 `CLAUDE.md` 中的 Slash Command 规则加载 `brainstorming` skill

**验证 `session_start` hook：**

如果启用了 `session_start` hook，还会看到 reflection 状态提醒：

```
[Harness] Memory reflection up to date (last run: 2026-05-06, 3 days ago).
```

---

## 四阶段工作流详解

### 阶段一：设计（Brainstorming）

**状态：** `Inbox`

**用户指令：** `/init-feature <功能描述>`

**Agent-Guard 命令：**
```bash
python .harness/agent-guard/cli.py init TASK-001 --spec docs/superpowers/specs/feature.md
```

**Gate（进入 Plan Ready 时执行）：**
- **G1 Plan Valid** —— 验证 plan 无占位符、无模糊词、包含必要章节（含 state_diagram、gate_checkpoints）
- **G2 Complexity Budget** —— 检查预估文件数≤20、步骤数≤15

**加载技能：**
1. `brainstorming`（设计阶段核心技能）
2. `using-superpowers`（强制检查并加载适用技能）

**加载约束：**
- `Think Before Coding` —— 暴露假设、呈现多解、对模糊需求 push back
- `Simplicity First` —— 设计阶段即避免过度复杂

**加载记忆：**
- `.claude/memory/patterns/` —— 已稳定模式
- `.claude/memory/decisions/` —— 活跃架构决策
- `.claude/memory/invariants/` —— 架构不变量
- `.claude/memory/taste/` —— 已确认编码偏好
- `CLAUDE.md` 动态区块 —— recent-decisions, common-pitfalls, patterns

**AI 自动执行：**
1. 加载上述技能和记忆
2. 分析需求，提出澄清问题（一次一个）
3. 探索项目上下文（文件、文档、近期提交）
4. 提出 2-3 种方案及权衡，**明确标记最简单方案**
5. 逐节呈现设计，获取你的批准
6. 自审 spec，修复 TBD/TODO，**检查是否违反 simplicity-first 不变量**
7. 保存设计规格书
8. **运行 `python .harness/agent-guard/cli.py init TASK-xxx --spec <spec-path>` 初始化 Agent-Guard 任务**

**产出物：** `docs/superpowers/specs/YYYY-MM-DD-<feature>-design.md`

**示例对话：**
```
你: /init-feature 为用户添加 OAuth2 登录
AI: [加载 brainstorming skill，自动读取 .claude/memory/patterns/]
    为了设计 OAuth2 登录，我需要了解几个问题：
    1. 你期望支持哪些提供商？（A）仅 GitHub （B）GitHub + Google （C）自定义
你: B
AI: 了解。接下来是架构设计...
    [...多轮交互后...]
    设计文档已保存到 docs/superpowers/specs/2026-04-21-oauth2-login-design.md
    请审阅，确认无误后我们将进入计划阶段。
```

### 阶段二：计划（Writing Plans）

**状态：** `Inbox → Plan Ready`

**用户指令：** `/plan-feature <spec路径>`

**Agent-Guard 命令：**
```bash
python .harness/agent-guard/cli.py plan TASK-001 --approve
```

**Gate（转换前自动执行）：**
- **G1 Plan Valid** —— 验证 plan 符合 schema，无 placeholders、无 TODOs
- **G2 Complexity Budget** —— 检查预估文件数≤20、步骤数≤15（Phase 1 警告模式，不阻断）。**超出预算时自动语义感知拆分**：识别 `## Phase X` / `## Task X` 等 section 边界，按语义分组生成子 plan；拆分前检测语义重复（避免 P1 与 phase1 重复）；子任务名从 section 标题自动提取（如 `FACTORY-AI-EventCenter`）

**加载技能：**
1. `writing-plans`（计划阶段核心技能）

**加载记忆：**
- 已批准的 spec
- 过往 plan 估算偏差（来自 observations/）
- `.claude/memory/entropy/` —— 复杂度反模式（避免在计划中引入）
- `patterns/` —— 文件命名约定

**加载约束（plan-schema.yaml）：**
- 禁止 TODO、占位符
- 测试先行：每个任务必须有测试步骤
- 最大步骤时长：5 分钟
- 必须包含验证命令
- **任务描述必须是可验证成功标准（Goal + Verify），禁止命令式语句**
- **必须包含 Agent-Guard 状态图**：Mermaid 或 PlantUML 格式，展示本功能在 8 状态机中的流转路径
- **必须标注 Gate 检查点**：每个 Task 头部/尾部标注对应 Gate（G1-G5）

**AI 自动执行：**
1. 读取已批准的 spec
2. 映射文件结构（创建/修改/删除哪些文件）
3. 分解为 2-5 分钟的任务
4. 每个任务包含：**可验证目标（Goal + Verify）**、文件变更、测试计划、验证命令
5. 自审：扫描 TBD/占位符/类型不一致
6. 保存计划文档
7. **运行 `python .harness/agent-guard/cli.py plan TASK-xxx --approve` 执行 G1/G2 Gate 检查并将状态推进到 Plan Ready**（G2 超预算时自动语义感知拆分，避免与已有 plan 重复）

**产出物：** `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`

### 阶段三：执行（Executing Plans）

**状态：** `Plan Ready → Executing → Patch Ready → Entropy Review`

**用户指令：** `/execute-plan <plan路径>`

**Agent-Guard 命令（技能自动调用）：**
```bash
python .harness/agent-guard/cli.py execute TASK-001   # Plan Ready → Executing (G3)
# ... 执行代码 ...
python .harness/agent-guard/cli.py patch TASK-001     # Executing → Patch Ready (G4) — 技能自动调用
python .harness/agent-guard/cli.py review TASK-001    # Patch Ready → Entropy Review — 技能自动调用
```

**注意**：`patch` 和 `review` 由 `executing-plans` / `subagent-driven-development` / `execute-plan` 技能在全部任务完成后**自动调用**，无需手动执行。

**Gate（转换前自动执行）：**
- **G3 Entropy Check** —— 运行 `detect-entropy.sh`，检测新增复杂度反模式（manager-proliferation、config-nesting、abstraction-explosion）
  - **如果失败**：任务进入 `Needs Simplification`，需简化后重新 `execute`
- **G4 Surgical Check** —— 验证 git diff 只修改计划内文件，无 drive-by refactoring（Phase 1 建议模式）

**加载技能：**
1. `executing-plans`（手动执行）或 `subagent-driven-development`（子代理自动执行）
2. `verification-before-completion`（每步完成后验证）

**加载记忆：**
- `.claude/memory/failures/` —— 相关事故教训
- `.claude/memory/entropy/` —— 复杂度反模式
- `.claude/memory/invariants/` —— 领域不变量（**代码生成前强制检查**）
  - **必载**：`general-simplicity-first`（禁止过度设计）
  - **必载**：`general-surgical-changes`（禁止 drive-by refactoring）
- `.claude/memory/taste/` —— 编码偏好

**加载约束：**
- `general-simplicity-first`（high severity，预生成阻断）
- `general-surgical-changes`（medium severity，预生成阻断）

**自动行为：**
- 获取 Lease（防止多 Agent 同时操作同一任务）
- 每 5 分钟发送 Heartbeat（Lease 续约）
- 状态转换后自动生成 Snapshot（用于中断恢复）

**执行方式：**

**方式 A：子代理驱动（推荐）**
- 每个任务分派独立子代理（implementer）
- 两阶段审查：spec 合规性审查 → 代码质量审查
- 子代理自审：Surgical Review + Diff Self-Check（确认只修改必要文件，无 drive-by refactoring）
- 同一会话内完成，无需人工介入
- 使用技能：`subagent-driven-development`

**方式 B：本会话执行**
- 在当前会话中逐步执行
- 适合需要频繁人工确认的任务
- 使用技能：`executing-plans`

**方式 C：多 Agent 并行认领（v2.4 新增）**
- 多个 Agent 同时从 backlog 中抢单式认领不同任务
- 每个 Agent 独立获取 Lease，互不干扰
- 适用于批量处理拆分后的子任务
- 用法：`python .harness/agent-guard/cli.py execute`（省略 task-id 自动认领）
- 或先 `claim` 再 `execute`：
  ```bash
  # 终端 1
  python .harness/agent-guard/cli.py execute   # 自动认领 TASK-001
  # 终端 2
  python .harness/agent-guard/cli.py execute   # 自动认领 TASK-002
  # 终端 3
  python .harness/agent-guard/cli.py claim --execute   # 认领并立即执行 TASK-003
  ```

**AI 自动执行：**
1. **运行 `python .harness/agent-guard/cli.py execute TASK-xxx` 做门票检查**：G3 Entropy Check + 状态转换 Plan Ready → Executing + 获取 Lease
   - **系统自动**：`execute` 命令会自动将 plan 第 1 步标记为 `in_progress`（写入 snapshot）
2. 加载执行记忆（常见陷阱、测试模式、架构不变量、编码偏好）
   - **必载**：`general-simplicity-first`（禁止过度设计）
   - **必载**：`general-surgical-changes`（禁止 drive-by refactoring）
3. 按顺序执行任务
4. 每个任务后：运行测试、提交代码
5. **Diff 审查**：确认只修改了计划中的文件，无相邻代码改动
6. **更新进度（强制）**：每完成一个子任务，**必须**运行 `agent-guard progress TASK-xxx --step N --status done --evidence "commit SHA"`
   - 禁止批量更新（不可将多步合并为一次 progress）
   - 子代理驱动模式下，父 agent 在收到 implementer DONE 后**必须**先更新 progress，再进入审查
7. 测试失败则停止并报告

**产出物：** 代码文件 + 测试文件 + 多次 git commit

### 阶段四：完成（Finishing）

**状态：** `Entropy Review → Done`

**用户指令：** `/finish-branch`

**Agent-Guard 命令：**
```bash
python .harness/agent-guard/cli.py finish TASK-001   # Entropy Review → Done (G5)
```

**Gate（转换前自动执行）：**
- **G5 Verification Proof** —— 运行 plan 中定义的 verification_command，确认测试通过、lint 通过、覆盖率≥80%
  - **如果失败**：任务进入 `Needs Simplification`，需修复后重新进入 `Executing`

**加载技能：**
1. `finishing-a-development-branch`（完成阶段核心技能）
2. `verification-before-completion`（验证后才允许声称完成）

**加载约束：**
- `finishing-policy.yaml` —— auto_merge / create_pr / keep_branch 决策规则
- `proof_of_work` —— CI 状态、覆盖率阈值（80%）、复杂度分析（max cyclomatic: 10）

**AI 自动执行：**
1. 运行完整测试套件
2. 检查覆盖率（默认阈值 80%）
3. 运行 linter
4. **Diff 审查**（verification-before-completion skill）
5. 读取 `finishing-policy.yaml` 自动决策
6. **运行 `python .harness/agent-guard/cli.py finish TASK-xxx` 执行 G5 Verification Proof 并将状态推进到 Done**
7. 自动写 observation（commit-summary / test-failure / lint-failure / decision / entropy / taste）
8. 自动运行 `detect-entropy.sh`（扫描最近 7 天复杂度）
9. 自动运行 `cluster-observations.sh`（聚类最近 30 天观察）
10. 更新 CLAUDE.md 动态区块
11. **释放 Lease**（任务完成，其他 Agent 可获取）

**决策规则：**

| 条件 | 动作 |
|------|------|
| 测试通过 + 覆盖率≥80% + 无严重 lint 错误 + 分支未落后 | `auto_merge` |
| 测试通过 + 复杂度评分<high | `create_pr` |
| 测试失败 | `keep_branch` + 创建 issue observation |

**产出：** 任务状态变为 `Done`，生命周期结束

### 旁路状态详解

#### Blocked（阻塞）

**进入时机：** 任意非终端状态下，遇到外部依赖或需要人工输入

**Agent-Guard 命令：**
```bash
python .harness/agent-guard/cli.py block TASK-001 --reason "等待第三方 API 文档"
```

**自动行为：**
- 记录 `blocked_from`（进入 Blocked 前的状态）
- 释放 Lease
- 任务标记为不可恢复（需 unblock 后恢复）

**退出：**
```bash
python .harness/agent-guard/cli.py unblock TASK-001
# 自动恢复到之前的状态
```

#### Needs Simplification（需要简化）

**进入时机：**
- G3 Entropy Check 失败（Plan Ready → Executing）
- G5 Verification Proof 失败（Entropy Review → Done）

**Agent-Guard 命令：**
```bash
python .harness/agent-guard/cli.py simplify TASK-001
```

**自动行为：**
- 记录失败原因到任务历史
- 输出简化指导（如 "减少抽象类数量"、"合并过度拆分的文件"）

**退出路径：**
```bash
# 路径 A: 简化后重新执行
python .harness/agent-guard/cli.py execute TASK-001  # 重新经过 G3

# 路径 B: 需要重新设计
python .harness/agent-guard/cli.py plan TASK-001 --approve  # 回到 Plan Ready
```

---

## 记忆系统（越用越聪明）

### 记忆层级架构

```
┌─────────────────────────────────────────────────────────────┐
│  L4: 全局级 Global Context (跨项目，越用越聪明)              │
│  ~/.claude/memory/user/ + /memory User Memory               │
│  - 用户角色、跨项目公理、技术栈倾向、沟通风格                  │
│  - 从所有项目提炼的通用模式（稳定性过滤后升级）                │
├─────────────────────────────────────────────────────────────┤
│  L3: 项目级 Project Context (本项目，随迭代演进)             │
│  <project>/CLAUDE.md + .claude/memory/project/              │
│  - 架构快照、目录结构、近期重大决策                            │
│  - 项目专属陷阱、测试习惯、文件命名模式                        │
│  - 每次 /finish-branch 后自动刷新                            │
├─────────────────────────────────────────────────────────────┤
│  L2: 工作流级 Harness Context (规则驱动)                     │
│  .harness/superpowers/ + .harness/workflows/                │
│  - Skills、Plan Schema、Finishing Policy、Model Routing      │
│  - 工作流定义，控制何时读写记忆                                │
├─────────────────────────────────────────────────────────────┤
│  L1: 会话级 Session Context (用完即走)                       │
│  当前对话 + 按需加载 Skill + Hooks 注入的短期上下文           │
│  - 从 L2/L3/L4 按需加载，会话结束后不保留                     │
└─────────────────────────────────────────────────────────────┘
```

### 5 层新记忆类型（v2.0）

| 层级 | 目录 | 用途 | 写入触发 | 读取时机 |
|:---|:---|:---|:---|:---|
| **决策记忆** | `decisions/` | 为什么这样设计，记录决策上下文 | `/reflect` 提炼 | brainstorming、writing-plans |
| **失败记忆** | `failures/` | 组织级创伤/事故教训，永不遗忘 | 系统性 bug 修复后 | systematic-debugging |
| **熵记忆** | `entropy/` | AI 容易重复的复杂度反模式 | `detect-entropy.sh` 扫描 | executing-plans（代码生成前）|
| **不变量** | `invariants/` | 不可违反的架构硬约束（如 simplicity-first、surgical-changes） | 显式声明 | **ALL 生成技能（预生成检查）**|
| **品味** | `taste/` | 团队编码品味/风格偏好 | code-review 反馈提炼 | ALL 代码生成技能 |

### 记忆沉淀流程

```
工作流执行
    │
    ├── /finish-branch ──→ 自动写 observation
    ├── /fix-bug ────────→ 自动写 observation
    └── code-review ─────→ 自动写 observation / taste
             │
             ▼
    ┌─────────────────┐
    │  observations/  │  ← 原始数据（自动 + 手动）
    └────────┬────────┘
             │ 每周 /reflect
             ▼
    ┌─────────────────┐
    │  cluster-obs.   │  ← 自动聚类（tags + 关键词）
    │  .sh            │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  memory-reflect │  ← 人工辅助提炼
    │  ion skill      │
    └────────┬────────┘
             │
        ┌────┴────┐
        ▼         ▼
   patterns/   decisions/   invariants/   taste/
        │
        │ 跨项目验证
        ▼
   user/axioms.md（全局公理）
```

### 手动管理记忆

**查看当前记忆状态：**

```bash
# 查看所有观察记录
ls -la .claude/memory/observations/

# 查看已提炼的模式
ls -la .claude/memory/patterns/

# 查看全局公理
cat .claude/memory/user/axioms.md

# 查看记忆索引
cat .claude/memory/MEMORY.md

# 查看指标仪表板
cat .claude/memory/metrics/reflection-costs.json
```

**手动添加观察记录：**

创建文件 `.claude/memory/observations/YYYY-MM-DD-<event>.md`：

```markdown
---
date: 2026-05-06
type: bug-fix | feature-retro | code-review | decision | failure | entropy | taste
tags: [tag1, tag2]
generated_by: manual | auto-observe
---

## 决策记录
- 选择了 X 而非 Y，因为 Z

## 遇到的陷阱
- **问题描述**：具体现象
- **影响范围**：哪些模块/用户受影响

## 纠正
- 最初想 A，后来改为 B

## 模式发现
- 可以复用的经验
- 反例：什么情况下不要这样做
```

**强制触发 reflection：**

```
你: /reflect
```

或在 Claude Code 中直接调用 skill：

```
/skill memory-reflection
```

---

## 命令与脚本参考

### 主要命令

| 命令 | 状态转换 | 对应技能 | 硬 Gate | 记忆动作 | 产出 |
|:---|:---|:---|:---|:---|:---|
| `/init-feature <描述>` | Inbox | brainstorming | G1 + G2 | **读取** patterns + decisions + invariants + taste | spec.md |
| `/plan-feature <spec>` | Inbox → Plan Ready | writing-plans | G1 + G2 | **读取** 历史估算偏差 + entropy | plan.md |
| `/execute-plan <plan>` | Plan Ready → Executing → Patch Ready → Entropy Review | executing-plans / subagent-driven | G3 + G4 | **读取** failures + entropy + invariants + taste | 代码 + 测试 |
| `/finish-branch` | Entropy Review → Done | finishing | G5 | **写入** observation + 更新 CLAUDE.md | merge / PR |
| `/fix-bug <issue>` | Inbox → Executing | test-driven + systematic-debugging | G3 | **读取** 历史 bug 模式；**写入** observation | 修复 + 回归测试 |
| `/reflect` | 不影响状态 | memory-reflection | 无 | **扫描** → **提炼** → **升级** | patterns/ + axioms.md |

### Agent-Guard CLI 命令

**主线命令：**

| 命令 | 状态转换 | Gate | 用途 |
|:---|:---|:---|:---|
| `init <task-id> [--spec <path>]` | → Inbox | 无 | 创建新任务 |
| `plan <task-id> --approve` | Inbox → Plan Ready | G1 + G2 | 批准 plan（G2 超预算时自动语义感知拆分，检测重复；拆分后父任务 snapshot 自动记录子任务列表与进度） |
| `execute [<task-id>]` | Plan Ready → Executing | G3 | 开始执行，获取 Lease，**自动标记 plan 第 1 步为 in_progress**（省略 task-id 则自动认领） |
| `claim [--execute]` | — | — | 从 backlog 认领下一个 Plan Ready 任务 |
| `patch <task-id>` | Executing → Patch Ready | G4 | 标记代码完成 |
| `review <task-id>` | Patch Ready → Entropy Review | 无 | 进入熵审查 |
| `finish <task-id>` | Entropy Review → Done | G5 | 完成验证，释放 Lease |
| `progress <task-id> --step N --status done` | — | — | 更新 plan 步骤完成进度到 snapshot（**强制**：每个 step 完成后必须更新，禁止批量）；**子任务自动同步进度到父任务** |

**旁路命令：**

| 命令 | 状态转换 | Gate | 用途 |
|:---|:---|:---|:---|
| `simplify <task-id>` | → Needs Simplification | 无 | 标记需要简化 |
| `block <task-id> --reason <msg>` | → Blocked | 无 | 标记阻塞 |
| `unblock <task-id>` | Blocked → 之前状态 | 无 | 解除阻塞 |

**运维命令：**

| 命令 | 用途 |
|:---|:---|
| `status <task-id>` | 查看任务状态和转换历史 |
| `list [--state <s>] [--recoverable] [--flat] [--no-children]` | 列出任务（默认树形，子任务缩进显示） |
| `resume <task-id>` | 中断后恢复，加载 Snapshot |
| `heartbeat <task-id>` | 发送 Lease 心跳 |
| `gate-check <gate> <task-id>` | 手动触发 Gate 验证 |

### 辅助脚本

| 脚本 | 用法 | 作用 | 执行方式 |
|:---|:---|:---|:---|
| `auto-observe.sh` / `auto-observe.ps1` | `bash .claude/scripts/auto-observe.sh <mode>` | 自动生成观察记录。mode: `commit-summary` / `test-failure` / `lint-failure` / `review-feedback` / `decision` / `entropy` / `taste` | **自动**（`/finish-branch` / `/fix-bug` 后触发） |
| `cluster-observations.sh` | `bash .claude/scripts/cluster-observations.sh [days]` | 对最近 N 天的 observations 进行关键词聚类，辅助 pattern 提炼 | **自动**（`/finish-branch` 后触发；`/reflect` 内部自动运行） |
| `detect-memory-conflicts.sh` | `bash .claude/scripts/detect-memory-conflicts.sh` | 检测新项目模式与全局公理的冲突 | **自动**（`/reflect` 内部自动运行） |
| `check-reflection-due.sh` | `bash .claude/scripts/check-reflection-due.sh` | 检查 reflection 是否到期（默认 7 天）| **自动**（session_start hook） |
| `check-invariants.sh` | `bash .claude/scripts/check-invariants.sh [domain]` | 按领域加载架构不变量 | **自动**（执行计划前 skill 内加载） |
| `detect-entropy.sh` | `bash .claude/scripts/detect-entropy.sh [days]` | 分析最近 git diff 检测复杂度反模式 | **自动**（`/finish-branch` 后 + `/reflect` 内部 + `execute-plan` 前） |
| `load-memory-context.sh` | `bash .claude/scripts/load-memory-context.sh <skill> [domain]` | 统一加载全部 5 层记忆 + 现有模式 | **按需**（供人类快速浏览；AI skill 自动读取各层文件） |

### 辅助命令

| 命令 | 作用 |
|:---|:---|
| `git worktree add .worktrees/<branch> -b <branch>` | 创建隔离工作区 |
| `pytest` | 运行测试 |
| `ruff check .` | 代码检查 |
| `ruff format .` | 代码格式化 |
| `mypy` | 类型检查 |

---

## 配置体系

Harness 采用三层配置架构：

### L1：项目级（必需）

**位置：** `.harness/superpowers/`

每个项目必须有自己的 L1 配置，直接驱动 Claude Code 工作。

| 文件 | 作用 |
|------|------|
| `skills/*.md` | 17 个 Superpowers 技能定义 |
| `plan-schema.yaml` | 计划约束验证规则 |
| `finishing-policy.yaml` | 完成阶段自动决策规则 + 记忆写入配置 |
| `design-harness.yaml` | Planner-Evaluator 循环配置 |

### L2：团队级（可选，推荐）

**位置：** `.harness/team/`（git submodule）

团队共享规范，通过 `git submodule` 在多个项目间共享。

| 文件 | 作用 |
|------|------|
| `shared-axioms.md` | 团队公理（API 设计、测试、Python 规范等）|
| `standards.md` | 编码/测试/文档标准 |
| `reviewer-pool.yaml` | Reviewer 代理分配规则 |

**设置方法：**
```bash
git submodule add https://github.com/your-org/team-harness.git .harness/team
git submodule update --remote .harness/team
```

### L3：组织级（预留）

**位置：** `.harness/workflows/`

工作流定义和模型路由配置。

| 文件 | 作用 |
|------|------|
| `feature-development.md` | 特性开发工作流模板 |
| `bug-fix.md` | Bug 修复工作流模板 |
| `manual-mode.yaml` | 手动触发命令映射（含 `/reflect`）|
| `model-routing.yaml` | 角色-模型映射配置 |

**模型路由示例：**

| 角色 | 主模型 | 备选模型 |
|------|--------|----------|
| Planner | claude-opus-4-7 | claude-sonnet-4-6 |
| Generator | claude-sonnet-4-6 | claude-haiku-4-5-20251001 |
| Evaluator | claude-opus-4-7 | gpt-4o |

---

## 故障排除

### 问题：技能未加载

**症状：** AI 没有按照技能流程工作（比如没有先提问就写代码）

**排查：**
1. **Claude Code 应用**：检查 `.claude/skills/` 下是否有对应的 `SKILL.md` 文件（如 `init-feature/SKILL.md`）
2. **VS Code 聊天**：检查 `CLAUDE.md` 是否包含 Slash Command 处理规则；如刚修改过，先运行 `/clear` 重新加载上下文
3. 检查技能文件是否存在且 frontmatter 正确（以 `---` 开头，包含 `name` 和 `description`）
4. 在 Claude Code 中尝试手动调用：`/skill <skill-name>`

### 问题：plan-schema.yaml 验证失败

**症状：** AI 提示计划不符合约束

**常见原因：**
- 任务缺少测试步骤
- 包含 TODO/TBD 占位符
- 文件路径不规范

**修复：** 根据 AI 提示的具体违规项修改 plan。

### 问题：worktree 创建失败

**症状：** `git worktree add` 报错

**排查：**
1. 确认 `.worktrees/` 目录已被 git ignore
2. 确认分支名不存在
3. 检查是否有未提交的变更

### 问题：子代理阻塞

**症状：** `subagent-driven-development` 中 implementer 报告 BLOCKED

**处理：**
1. 阅读阻塞原因
2. 提供更多上下文
3. 用更强模型重新分派
4. 或将任务拆分为更小的子任务

### 问题：测试覆盖率不足

**症状：** `/finish-branch` 时 coverage < 80%

**处理：**
1. 检查哪些代码未被覆盖
2. 补充测试（非 mock 测试优先）
3. 如果确实无法覆盖（如外部 API 调用），在 plan 中说明

### 问题：observation 未自动写入

**症状：** `/finish-branch` 后 `.claude/memory/observations/` 没有新文件

**排查：**
1. 确认 `finishing-policy.yaml` 中对应决策规则有 `post_action.write_observation: true`
2. 确认 tests_pass 条件满足（失败时只写入 observation，不更新 CLAUDE.md）
3. 检查是否有权限问题（脚本需要写 `.claude/memory/` 目录）

### 问题：Agent-Guard 命令未找到

**症状：** `python .harness/agent-guard/cli.py` 报错 `ModuleNotFoundError: No module named 'yaml'`

**解决：**
```bash
pip install pyyaml
```

### 问题：Gate 阻断导致无法继续

**症状：** `agent-guard plan TASK-001 --approve` 报错 `Gate g1_plan_valid blocked transition`

**排查：**
1. 检查 plan 文件是否包含 TODO/TBD/FIXME/XXX
2. 检查是否包含模糊词（适当、可能、考虑、稍后、大概、尽量）
3. 检查是否缺少必要章节（task_description、file_changes、test_plan、verification_command、success_criteria、state_diagram、gate_checkpoints）
4. 修复后重新运行 `agent-guard plan TASK-001 --approve`

### 问题：resume 失败显示 Lease 仍有效

**症状：** `agent-guard resume TASK-001` 报错 `Lease held by agent-xxx until ...`

**原因：** 原 Agent 仍在持有 Lease（未正常释放或心跳仍在）

**解决：**
1. 等待 Lease 过期（默认 10 分钟）
2. 或手动强制释放：`rm .harness/agent-guard/leases/TASK-001-lease.json`
3. 重新运行 `agent-guard resume TASK-001`

### 问题：任务中断后 context 加载不完整

**症状：** resume 后部分文件显示 `[MISSING]`

**解决：**
1. 检查 Snapshot 中的 `required_context.files` 路径是否正确
2. 确保路径相对于项目根目录
3. 手动补充缺失文件到 snapshot 后重新 resume

### 问题：/reflect 没有提炼出 patterns

**症状：** 运行 `/reflect` 后报告 "No new patterns"

**原因：**
- 当前 observations 数量不足（需要 ≥3 次出现才能升级为项目 pattern）
- 或者所有模式已在现有 patterns/ 中

**解决：** 继续使用 Harness 工作流完成更多迭代，积累足够观察数据。

### 问题：Windows 下 bash 脚本无法运行

**症状：** 在 Windows PowerShell/CMD 中运行 `.sh` 脚本报错

**解决：**
1. 使用 Git Bash 或 WSL
2. 部分脚本提供 `.ps1` 版本（如 `auto-observe.ps1`）
3. 在 Claude Code 中直接运行，Claude Code 内置 bash 支持

---

## 文档维护规则（Harness 项目自身迭代）

> **注意**：本节规则仅适用于 **harness 模板项目自身的功能迭代维护**，不是使用 harness 的其他项目需要遵循的流程。

**规则：每次对 harness 工作流进行功能迭代后，必须同步更新 README.md 和 HARNESS_USAGE_GUIDE.md**

### 为什么

README.md 和 HARNESS_USAGE_GUIDE.md 是用户接触本项目的第一入口。harness 自身的功能迭代（如新增状态、修改 skill、调整 Gate 逻辑等）后如果文档不同步，会导致：
- 用户看到的版本号与实际功能不匹配
- 新特性无说明，老特性已废弃但文档仍在
- 两个文档之间出现内容矛盾

### 检查方式

维护者可手动运行检查脚本：

```bash
python .claude/scripts/check-doc-sync.py
```

**检查内容：**
1. README.md 与 HARNESS_USAGE_GUIDE.md 版本号是否一致
2. 若当前分支修改了 harness 配置/技能/策略/Agent-Guard，文档是否同步更新

### 更新清单（每次迭代后自检）

- [ ] 版本号同步更新（README.md 和 HARNESS_USAGE_GUIDE.md 保持一致）
- [ ] 新功能在「核心特性」或「工作流详解」中说明
- [ ] 新命令/脚本在「命令参考」中登记
- [ ] 故障排除章节补充新增常见问题
- [ ] 如有破坏性变更，添加迁移说明

---

## 相关文档

| 文档 | 位置 | 说明 |
|------|------|------|
| **详细使用手册** | [HARNESS_USAGE_GUIDE.md](HARNESS_USAGE_GUIDE.md) | 完整的命令参考、最佳实践、故障排除 |
| **记忆系统完整指南** | [MEMORY_HARNESS_GUIDE.md](MEMORY_HARNESS_GUIDE.md) | 记忆系统架构、使用教程、Phase 2.1-2.4 详解 |
| **Harness Engineering 深度指南** | [harness-engineering-guide.md](harness-engineering-guide.md) | 8 篇核心文章总结、三大扩展维度、架构设计模式 |
| **架构设计规格** | [docs/superpowers/specs/2026-04-20-guardharness-design.md](docs/superpowers/specs/2026-04-20-guardharness-design.md) | 本项目的架构设计文档 |
| **架构可视化** | [docs/superpowers/specs/architecture-visual.html](docs/superpowers/specs/architecture-visual.html) | 在线架构图 |
| **实现计划** | [docs/superpowers/plans/2026-04-20-guardharness.md](docs/superpowers/plans/2026-04-20-guardharness.md) | 本项目的实现计划 |
| **Hermes 兼容指南** | [.harness/HERMES_COMPAT.md](.harness/HERMES_COMPAT.md) | Hermes 工具兼容性说明 |
| **团队模板示例** | [examples/team-harness/](examples/team-harness/) | 团队共享配置示例 |

---

## Agent-Guard 快速参考

### 什么时候用什么命令？

**主线：**

| 场景 | 命令 | 状态变化 | Gate |
|:---|:---|:---|:---|
| 开始新功能 | `init TASK-xxx --spec <path>` | → Inbox | 无 |
| Plan 已写好，准备执行 | `plan TASK-xxx --approve` | Inbox → Plan Ready | G1 + G2 |
| 开始写代码 | `execute TASK-xxx` | Plan Ready → Executing | G3 |
| 代码写完了 | `patch TASK-xxx` | Executing → Patch Ready | G4 |
| 进入熵审查 | `review TASK-xxx` | Patch Ready → Entropy Review | 无 |
| 验证通过，完成 | `finish TASK-xxx` | Entropy Review → Done | G5 |

> **注意**：在使用 `/execute-plan` 时，`patch` 和 `review` 由技能在全部任务完成后**自动调用**，无需手动执行。只有在手动执行或中断恢复时才需要单独运行这些命令。

**旁路：**

| 场景 | 命令 | 状态变化 |
|:---|:---|:---|
| Entropy 失败，需要简化 | `simplify TASK-xxx` | → Needs Simplification |
| 简化后重新执行 | `execute TASK-xxx` | Needs Simplification → Executing | G3 |
| 遇到外部依赖，暂停 | `block TASK-xxx --reason "..."` | → Blocked |
| 依赖解决，恢复 | `unblock TASK-xxx` | Blocked → 之前状态 |
| 会话中断，恢复继续 | `resume TASK-xxx` | 保持当前状态 | Lease 检查 |

**运维：**

| 场景 | 命令 |
|:---|:---|
| 查看任务进度 | `status TASK-xxx` |
| 手动检查 Gate | `gate-check g3_entropy_check TASK-xxx` |
| 发送心跳 | `heartbeat TASK-xxx` |

### 完整命令速查

```bash
# 主线生命周期
python .harness/agent-guard/cli.py init     <task-id> [--spec <path>]
python .harness/agent-guard/cli.py plan     <task-id> [--approve]
python .harness/agent-guard/cli.py execute  [<task-id>]           # 省略则自动认领
python .harness/agent-guard/cli.py claim    [--execute]            # 单独认领任务
python .harness/agent-guard/cli.py patch    <task-id>
python .harness/agent-guard/cli.py review   <task-id>
python .harness/agent-guard/cli.py finish   <task-id>
python .harness/agent-guard/cli.py progress <task-id> --step N --status {pending|in_progress|done} [--evidence "..."]

# 旁路
python .harness/agent-guard/cli.py simplify <task-id>
python .harness/agent-guard/cli.py block    <task-id> [--reason <msg>]
python .harness/agent-guard/cli.py unblock  <task-id>

# 查询与恢复
python .harness/agent-guard/cli.py status   <task-id>
python .harness/agent-guard/cli.py list     [--state <state>] [--recoverable] [--flat] [--no-children]
python .harness/agent-guard/cli.py resume   <task-id>
python .harness/agent-guard/cli.py heartbeat <task-id> [--holder <id>]

# 调试
python .harness/agent-guard/cli.py gate-check <gate-name> <task-id>
```

### 5 个 Gate 速查

| Gate | 触发时机 | 检查内容 | 失败后果 |
|:---|:---|:---|:---|
| G1 Plan Valid | Inbox → Plan Ready | 无占位符、无模糊词、必要章节齐全 | **阻断** |
| G2 Complexity Budget | Inbox → Plan Ready | 文件数≤20、步骤数≤15 | 警告（不阻断），自动语义感知拆分并记录子任务到父 snapshot，检测重复 |
| G3 Entropy Check | Plan Ready → Executing / Needs Simplification → Executing | 无新增复杂度反模式 | **阻断** |
| G4 Surgical Check | Executing → Patch Ready | Diff 只改相关文件 | 建议（不阻断）|
| G5 Verification Proof | Entropy Review → Done | 测试+lint+覆盖率全部通过 | **阻断** |

### 中断恢复流程

```
1. 任务在 Executing / Patch Ready / Entropy Review 状态中断
2. 下一次启动时：
   python .harness/agent-guard/cli.py resume TASK-xxx
3. Agent-Guard 自动：
   - 读取 TASK-xxx-snapshot.yaml
   - 加载 required_context（精确文件，非全部历史）
   - 加载 plan_progress（Task 1-7 的完成/进行中/待处理状态）
   - 注入 recovery_prompt
   - 从 in_progress 步骤继续（精确到 plan 中的子任务级别）
```

### 子任务进度追踪

当 G2 复杂度预算触发自动拆分时，系统会自动建立父子任务追踪关系：

1. **拆分记录**：父任务的 snapshot 自动记录 `sub_tasks` 列表，以及每个子任务对应的 plan 文件路径
2. **进度映射**：父任务的 `plan_progress` 以子任务为粒度重新组织（每个子任务视为一个"大步骤"）
3. **自动同步**：子任务运行 `agent-guard progress` 更新自身进度时，系统**自动**将子任务整体状态（pending / in_progress / done）同步回父任务的 snapshot
4. **树形查看**：`agent-guard list` 默认以树形展示父子关系，子任务缩进显示在父任务下方

```
父任务 TASK-001 (Plan Ready)
  ├─ 子任务 TASK-001-sub1 (Executing)
  └─ 子任务 TASK-001-sub2 (Plan Ready)
```

### 回流路径（Needs Simplification）

```
Entropy Review 或 Executing 中 G3 失败
    │
    ▼
Needs Simplification
    │
    ├──→ execute TASK-xxx  (G3 重检，回到 Executing)
    │
    └──→ plan TASK-xxx --approve  (需重新设计，回到 Plan Ready)
```

---

## 设计原则

本项目基于以下核心原则构建：

| 原则 | 说明 |
|:---|:---|
| **约束优于指令** | 可执行的约束（linter、schema）比模糊的指令更有效 |
| **环境即代码** | 所有配置、流程、上下文都版本化，存在于 repo 中 |
| **隔离与重启** | 定期干净重启对抗漂移，每个功能在独立 worktree 中开发 |
| **工作证明** | Agent 必须提供可验证的完成证据（CI、测试、评审） |
| **渐进式披露** | 按需加载上下文，避免信息过载（Skill-based 加载）|
| **越用越聪明** | 每次交互沉淀记忆，每周提炼模式，跨项目升级公理 |

### Karpathy 编码四原则（v2.1 内置）

| 原则 | 核心要求 | 违规后果 |
|:---|:---|:---|
| **Think Before Coding** | 暴露假设、呈现多解、对模糊需求 push back | 产生不符合预期的方案，返工 |
| **Simplicity First** | 最小代码解决问题；禁止推测性功能；禁止单用抽象 | 过度设计、技术债务、维护成本上升 |
| **Surgical Changes** | 只碰任务要求的文件；不改相邻代码；只删自己引入的未使用代码 | diff 噪音、审查困难、引入无关变更 |
| **Goal-Driven Execution** | 任务描述必须是可验证目标（Goal + Verify），禁止命令式语句 | 无法验证完成状态、范围蔓延 |

---

*本 README 基于 HARNESS_USAGE_GUIDE.md 和 MEMORY_HARNESS_GUIDE.md 融合生成。*
*完整使用细节请参阅上述两个文档。*
