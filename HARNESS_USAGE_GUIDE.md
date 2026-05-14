# GuardHarness 使用手册

> **版本:** 2.5 | **日期:** 2026-05-13 | **基于:** Superpowers 5.0.7 + Harness Engineering + Agent-Guard
>
> **更新内容**: G2 语义感知拆分 + 多 Agent 并行认领 + 子任务进度追踪 + 记忆系统全自动沉淀 + 技能自动驱动完整状态生命周期（execute → patch → review → finish）
>
> 本文档面向** Windows 开发者**优化，包含完整的跨项目迁移步骤。

---

## 目录

1. [快速开始](#快速开始)
2. [迁移到新项目（复刻清单）](#迁移到新项目复刻清单)
3. [Agent-Guard 状态驱动工作流](#agent-guard-状态驱动工作流)
4. [核心工作流详解](#核心工作流详解)
5. [配置体系说明](#配置体系说明)
6. [技能速查表](#技能速查表)
7. [命令参考](#命令参考)
8. [Windows 环境专项](#windows-环境专项)
9. [最佳实践](#最佳实践)
10. [故障排除](#故障排除)

---

## 快速开始

### 第一步：安装前提

| 组件 | 版本/要求 | 验证命令 |
|:---|:---|:---|
| Claude Code | 最新版 | `claude --version` |
| Superpowers 插件 | 5.0.7+ | `claude plugins list` |
| Git | 2.30+ | `git --version` |
| Python | 3.10+（Agent-Guard 需要）| `python --version` |
| PyYAML | Agent-Guard 依赖 | `pip install pyyaml` |

安装 Superpowers 插件：
```bash
claude plugins install superpowers
```

### 第二步：复制配置模板

**方式 A：一行命令安装（推荐）**

前提：已安装 Python 3.10+ 和 Git

=== "Bash / Git Bash / WSL / macOS / Linux"
```bash
curl -fsSL https://raw.githubusercontent.com/Mench-Li/GuardHarness/main/install.sh | bash
```

=== "PowerShell (Windows)"
```powershell
irm https://raw.githubusercontent.com/Mench-Li/GuardHarness/main/install.ps1 | iex
```

=== "本地模板（已下载仓库）"
```bash
cd /path/to/your-project
python /path/to/harness/install.py
```

安装脚本会自动完成：复制核心文件（含 `README.md`）、创建目录结构、更新 `.gitignore`、验证安装。

**方式 B：手工复制**

=== "Bash (Git Bash / WSL / macOS / Linux)"
```bash
cp -r /path/to/harness/.harness ./
cp /path/to/harness/CLAUDE.md ./
cp -r /path/to/harness/.claude ./
```

=== "PowerShell (Windows)"
```powershell
Copy-Item -Recurse E:\path\to\harness\.harness .\ -Force
Copy-Item E:\path\to\harness\CLAUDE.md .\ -Force
Copy-Item -Recurse E:\path\to\harness\.claude .\ -Force
```

**方式 C：作为 git subtree/submodule 引入（团队场景）**

```bash
# 将 harness 模板作为 subtree 引入，后续可拉取更新
git subtree add --prefix=.harness-template \
  https://github.com/your-org/guardharness.git main --squash

# 复制到项目位置
cp -r .harness-template/.harness ./
cp -r .harness-template/.claude ./
cp .harness-template/CLAUDE.md ./
```

### 第三步：初始化项目配置

编辑 `CLAUDE.md`，填入你的项目特定信息（**保留所有 `<!-- DYNAMIC-BLOCK: xxx -->` 标记**）：

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

## Agent-Guard
以下命令在使用 `/init-feature`、`/plan-feature`、`/execute-plan`、`/finish-branch` 时由 AI **自动执行**，通常无需手动输入：
```bash
# 初始化任务（/init-feature 后自动执行）
python .harness/agent-guard/cli.py init TASK-001 --spec docs/superpowers/specs/feature.md
# 批准计划（/plan-feature 后自动执行）
python .harness/agent-guard/cli.py plan TASK-001 --approve
# 开始执行（/execute-plan 前自动执行，门票检查）
python .harness/agent-guard/cli.py execute TASK-001
# 完成任务（/finish-branch 后自动执行）
python .harness/agent-guard/cli.py finish TASK-001
```
手动使用场景：多 Agent 并行时直接运行 CLI，或需要单独检查任务状态。

## Project Standards
- 所有设计文档存放于 `docs/superpowers/specs/`
- 所有实现计划存放于 `docs/superpowers/plans/`
- 隔离工作区使用 `.worktrees/`

## Memory System
本项目启用结构化记忆系统，越用越聪明。
```

### 第四步：创建必要目录

```bash
# Bash
mkdir -p docs/superpowers/specs docs/superpowers/plans .worktrees

# PowerShell
New-Item -ItemType Directory -Force -Path docs\superpowers\specs,docs\superpowers\plans,.worktrees
```

### 第五步：添加到 .gitignore

```gitignore
# .gitignore
.worktrees/
.claude/memory/user/          # 全局级记忆（跨项目共享，不应提交）
.harness/agent-guard/state/   # 任务状态（可提交，也可忽略）
.harness/agent-guard/leases/  # 活跃租约（不应提交）
.harness/agent-guard/snapshots/  # 快照（可选提交）
```

### 第六步：验证安装

**1. 验证 Agent-Guard CLI：**
```bash
python .harness/agent-guard/cli.py --help
```

**2. 快速测试完整生命周期：**
```bash
python .harness/agent-guard/cli.py init TEST-001
python .harness/agent-guard/cli.py plan TEST-001 --approve
python .harness/agent-guard/cli.py status TEST-001
```

**3. 验证 Claude Code 配置加载：**

**Claude Code 桌面/终端应用：**
- 打开项目后，输入 `/init-feature '测试功能'`
- 确认自动加载 `brainstorming` skill 并进入设计工作流

**VS Code 聊天会话：**
- VS Code 聊天不自动扫描 `.claude/skills/`，依赖 `CLAUDE.md` 上下文
- 如刚修改过 `CLAUDE.md`，先输入 `/clear` 清空上下文
- 然后输入 `/init-feature '测试功能'`，确认 AI 按规则加载 skill

---

## 迁移到新项目（复刻清单）

将 Harness 从一个项目迁移到另一个项目的**完整检查清单**：

### Phase 1：安装（四种方式任选）

**方式 A：一行命令（推荐）**

脚本会自动 `git clone --depth 1` 你的 Harness 远程仓库到临时目录，然后执行安装。

=== "Bash / Git Bash / WSL / macOS / Linux"
```bash
curl -fsSL https://raw.githubusercontent.com/Mench-Li/GuardHarness/main/install.sh | bash
```

=== "PowerShell (Windows)"
```powershell
irm https://raw.githubusercontent.com/Mench-Li/GuardHarness/main/install.ps1 | iex
```

**注意：** Windows 环境若未安装 Git，install.ps1 会自动回退到 ZIP 下载模式。

**方式 B：本地安装（已下载 harness 仓库）**

```bash
# 导出干净模板到当前目录
python install.py --export ./harness-template -y
# 然后手动复制 harness-template/ 下的内容到新项目

# 或直接安装到目标项目
python install.py --target /path/to/your-project -y
```

**方式 C：Git 远程仓库安装（已有远程仓库）**

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

**方式 D：手工复制**
```bash
cp -r /path/to/harness/.harness ./
cp -r /path/to/harness/.claude ./
cp /path/to/harness/CLAUDE.md ./
mkdir -p docs/superpowers/specs docs/superpowers/plans .worktrees
```

安装脚本会自动完成：复制核心文件（含 `README.md`）、创建目录结构、更新 `.gitignore`、验证安装。

**本地导出（不发布 GitHub 时分发模板）：**
```bash
# 列出所有需要复制的文件
python install.py --list

# 导出干净模板到指定目录
python install.py --export ./harness-template -y

# 直接打包成 ZIP
python install.py --zip ./harness-template.zip -y
```

### Phase 2：项目定制

- [ ] 编辑 `CLAUDE.md`：填入项目简介、技术栈、团队信息
- [ ] 检查 `.claude/settings.json`：确认技能路径指向正确位置
- [ ] 检查 `.claude/skills/`：确认命令技能文件已复制（如 `init-feature/SKILL.md`）
- [ ] 安装 Python 依赖：`pip install pyyaml`（Agent-Guard 需要）
- [ ] 确认 `.gitignore` 已包含：`.worktrees/`、`.harness/agent-guard/leases/`

### Phase 3：验证

- [ ] 运行 `python .harness/agent-guard/cli.py init TEST-001`
- [ ] 运行 `python .harness/agent-guard/cli.py status TEST-001`
- [ ] **Claude Code 应用**：测试 `/init-feature '测试功能'`，确认自动加载 skill
- [ ] **VS Code 聊天**：如刚修改过 `CLAUDE.md`，先 `/clear`，再测试 `/init-feature`
- [ ] 验证 `docs/superpowers/specs/` 能正常生成 spec 文件
- [ ] 验证 `docs/superpowers/plans/` 能正常生成 plan 文件

### Phase 4：团队适配（可选）

- [ ] 创建团队共享仓库：`team-harness.git`
- [ ] 注册为 submodule：`git submodule add <url> .harness/team`
- [ ] 定制 `.harness/team/shared-axioms.md` 和 `standards.md`
- [ ] 配置 `.harness/workflows/model-routing.yaml` 中的模型选择

---

## Skill 覆盖与约束加载机制

### 为什么需要本地 Skill 覆盖

Superpowers 插件提供了官方 skill（如 `superpowers:writing-plans`），但官方版本不会自动读取你项目的 `.harness/team/standards.md` 或 `.claude/memory/`。Harness 通过**本地同名覆盖**机制解决这个问题。

**核心规则：本地 skill 的 `name` 必须与官方 skill 完全匹配。**

Harness 所有本地 skill 的 `name` 均使用 `superpowers:` 前缀（如 `superpowers:writing-plans`）。当输入 `/plan-feature` 时，系统定向到 `superpowers:writing-plans`，本地版本优先于插件缓存版本生效。

**配置位置：** `.claude/settings.json`

```json
{
  "skills": {
    "local": {
      "paths": [
        ".harness/superpowers/skills/writing-plans.md",
        ".harness/superpowers/skills/brainstorming.md"
      ]
    }
  }
}
```

### 约束与记忆自动加载流程

每个 slash command 执行时，AI 在加载 skill 之前**必须**完成以下步骤：

1. **读取 `.harness/team/shared-axioms.md`**
   - 团队级公理与原则（如 "Simplicity First"、"Surgical Changes"）
   - 这些是不可违反的高层约束

2. **读取 `.harness/team/standards.md`**
   - 编码规范（命名约定、类型注解要求）
   - 测试标准（覆盖率门槛、测试命名规范）
   - 文档标准（注释规范、CHANGELOG 格式）

3. **读取 `.claude/memory/MEMORY.md`**（如存在）
   - 项目记忆索引，指向具体的 observations、patterns、decisions
   - 根据索引按需加载相关记忆文件

**加载顺序的意义：**
- 团队标准（L2） > 项目记忆（L3） > Skill 工作流
- 这意味着每次使用 `/init-feature`、`/plan-feature`、`/execute-plan`、`/finish-branch`、`/fix-bug`、`/reflect` 时，团队规范和项目历史都会自动参与决策，避免重复踩坑。

**故障排查：**
- 如果发现 AI 没有加载记忆/约束，检查本地 skill 的 `name` 是否为 `superpowers:xxx` 格式
- 检查 `.claude/settings.json` 中的 `skills.local.paths` 是否包含对应文件
- 检查目标项目中 `.harness/superpowers/skills/` 下的文件是否与 Harness 模板同步

---

## Agent-Guard 状态驱动工作流

Agent-Guard 是本模板的**状态驱动控制平面**，将传统四阶段升级为 **8 状态机 + 硬 Gate + 恢复协议**。

### 8 状态机

```
主线：
  Inbox → Plan Ready → Executing → Patch Ready → Entropy Review → Done

旁路：
  Blocked               # 外部依赖 / 等待人工输入（可从任意状态进入）
  Needs Simplification  # 熵审查失败后的回流状态
```

### 硬 Gate（否决权式检查）

| Gate | 转换点 | 检查内容 | 阻断方式 |
|:---|:---|:---|:---|
| G1 Plan Valid | Inbox → Plan Ready | Plan 无占位符、无模糊词、包含必要章节 | **硬阻断** |
| G2 Complexity Budget | Inbox → Plan Ready | 预估文件数≤20、步骤数≤15 | 警告（不阻断），自动语义感知拆分并记录子任务到父 snapshot，检测重复 |
| G3 Entropy Check | Plan Ready → Executing / Needs Simplification → Executing | 运行 `detect-entropy.sh`，无新增复杂度反模式 | **硬阻断** |
| G4 Surgical Check | Executing → Patch Ready | Diff 只修改相关文件，无 drive-by refactoring | 建议（不阻断） |
| G5 Verification Proof | Entropy Review → Done | 测试通过 + lint 通过 + 覆盖率达标 | **硬阻断** |

### Agent-Guard CLI 命令

**主线生命周期：**
```bash
python .harness/agent-guard/cli.py init     <task-id> [--spec <path>]
python .harness/agent-guard/cli.py plan     <task-id> [--approve]
python .harness/agent-guard/cli.py execute  [<task-id>]         # 省略则自动认领
python .harness/agent-guard/cli.py claim    [--execute]            # 单独认领任务
python .harness/agent-guard/cli.py patch    <task-id>
python .harness/agent-guard/cli.py review   <task-id>
python .harness/agent-guard/cli.py finish   <task-id>
python .harness/agent-guard/cli.py progress <task-id> --step N --status {pending|in_progress|done} [--evidence "..."]
```

**旁路命令：**
```bash
python .harness/agent-guard/cli.py simplify <task-id>   # Entropy Review → Needs Simplification
python .harness/agent-guard/cli.py block    <task-id> --reason "..."
python .harness/agent-guard/cli.py unblock  <task-id>
```

**查询与恢复：**
```bash
python .harness/agent-guard/cli.py status   <task-id>
python .harness/agent-guard/cli.py list     [--state <state>] [--recoverable] [--flat] [--no-children]
python .harness/agent-guard/cli.py resume   <task-id>    # 中断后恢复
python .harness/agent-guard/cli.py heartbeat <task-id>   # Lease 续约
```

### 中断恢复流程

任务在非终端状态中断后：
```bash
# 1. 查看可恢复的任务
python .harness/agent-guard/cli.py list --recoverable

# 2. 恢复指定任务（自动加载 Snapshot + required_context）
python .harness/agent-guard/cli.py resume TASK-001

# 3. Agent 自动接续当前步骤继续执行
#    resume 会加载 snapshot 中的 plan_progress，精确知道 Task 1-7 哪些已完成、哪些在进行中
```

---

## 核心工作流详解

Harness 采用四阶段工作流，对应 Superpowers 的核心技能：

```
/init-feature     →   /plan-feature     →   /execute-plan     →   /finish-branch
   (设计)              (计划)                (执行)                (完成)
   brainstorming       writing-plans         executing-plans       finishing
   |
   v
产出: spec.md        产出: plan.md         产出: 代码 + 测试       产出: merge/PR
```

### 阶段一：设计（Brainstorming）

**触发命令：** `/init-feature <功能描述>`

**显式指定输出路径（Scrum / 迭代管理）：**
```
/init-feature 把设计文档写到 docs/superpowers/specs/sprint-3/oauth2-login-design.md，设计OAuth2登录
```

**Agent-Guard 状态：** `Inbox`

**做什么：**
- 分析需求，提出澄清问题（一次一个）
- 探索项目上下文（文件、文档、近期提交）
- 提出 2-3 种方案及权衡，**明确标记最简单方案**
- 逐节呈现设计，获取你的批准
- 编写设计规格书（spec），修复 TBD/TODO
- **运行 `python .harness/agent-guard/cli.py init TASK-xxx --spec <path>` 初始化 Agent-Guard 任务**

**产出物：**
- `docs/superpowers/specs/YYYY-MM-DD-<feature>-design.md`（默认）
- 或命令中显式指定的路径

**示例对话：**
```
你: /init-feature 为用户添加 OAuth2 登录
AI: [加载 brainstorming 技能]
AI: 为了设计 OAuth2 登录，我需要了解几个问题：
     1. 你期望支持哪些提供商？（A）仅 GitHub （B）GitHub + Google （C）自定义
你: B
AI: 了解。接下来是架构设计...
[...多轮交互后...]
AI: 设计文档已保存到 docs/superpowers/specs/2026-04-21-oauth2-login-design.md
     请审阅，确认无误后我们将进入计划阶段。
```

### 阶段二：计划（Writing Plans）

**触发命令：** `/plan-feature <spec路径>`

**Agent-Guard 状态：** `Inbox → Plan Ready`（自动执行 G1 + G2，G2 超预算时自动语义感知拆分为子任务）

**做什么：**
- 读取已批准的 spec
- 映射文件结构（创建/修改/删除哪些文件）
- 分解为 2-5 分钟的任务
- 每个任务包含：**可验证目标（Goal + Verify）**、文件变更、测试计划、验证命令
- 自审：扫描 TBD/占位符/类型不一致
- **运行 `python .harness/agent-guard/cli.py plan TASK-xxx --approve` 执行 G1/G2 并将状态推进到 Plan Ready**（G2 超预算时自动语义感知拆分：识别 section 边界、检测语义重复、自动命名；拆分后父任务 snapshot 自动记录子任务列表与进度）

**产出物：**
- `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`

**约束（来自 plan-schema.yaml）：**
- 禁止 TODO、占位符、模糊词（适当/可能/考虑/稍后/大概/尽量）
- 测试先行：每个任务必须有测试步骤
- 最大步骤时长：5 分钟
- 必须包含验证命令
- **任务描述必须是可验证成功标准（Goal + Verify），禁止命令式语句**
- **必须包含 Agent-Guard 状态图**：Mermaid 或 PlantUML 格式，展示本功能在 8 状态机中的流转路径
- **必须标注 Gate 检查点**：每个 Task 头部/尾部标注对应 Gate（G1-G5）

### 阶段三：执行（Executing Plans）

**触发命令：** `/execute-plan <plan路径>`

**Agent-Guard 状态：** `Plan Ready → Executing → Patch Ready → Entropy Review`

**做什么：**
- **运行 `python .harness/agent-guard/cli.py execute TASK-xxx` 做门票检查**：G3 Entropy Check + 状态转换 Plan Ready → Executing + 获取 Lease
  - **系统自动**：`execute` 命令会自动将 plan 第 1 步标记为 `in_progress`（写入 snapshot，无需手动操作）
- 按顺序执行任务
- 每个任务后：运行测试、提交代码
- **更新进度（强制）**：每完成一个子任务，**必须**运行 `python .harness/agent-guard/cli.py progress TASK-xxx --step N --status done --evidence "commit SHA"`
  - 禁止批量更新（不可将多步合并为一次 progress）
  - 子代理驱动模式下，父 agent 在收到 implementer DONE 后**必须**先更新 progress，再进入审查
  - 中断恢复时，`resume` 会读取 snapshot 中的 `plan_progress`，精确知道哪些 step 已完成、哪些在进行中
  - **子任务自动同步**：子任务更新 progress 时，系统自动将整体状态同步回父任务的 snapshot
- 测试失败则停止并报告
- Diff 审查：确认只修改了计划中的文件，无 drive-by refactoring
- **全部任务完成后自动状态转换**：
  - 技能自动调用 `python .harness/agent-guard/cli.py patch TASK-xxx` —— Executing → Patch Ready（G4 Surgical Check）
  - 技能自动调用 `python .harness/agent-guard/cli.py review TASK-xxx` —— Patch Ready → Entropy Review
  - **不要跳过**：patch/review 是技能工作流的强制步骤，Snapshot 不会自动进入 Patch Ready

**Gate：**
- **G3 Entropy Check**（硬阻断）：运行 `detect-entropy.sh`，阻断复杂度爆炸
- **G4 Surgical Check**（建议）：验证 git diff 只修改计划内文件

**执行方式二选一：**

**方式 A：子代理驱动（推荐）**
- 每个任务分派独立子代理（implementer）
- 两阶段审查：spec 合规性审查 → 代码质量审查
- 同一会话内完成，无需人工介入
- 使用技能：`subagent-driven-development`

**方式 B：本会话执行**
- 在当前会话中逐步执行
- 适合需要频繁人工确认的任务
- 使用技能：`executing-plans`

**自动行为：**
- 获取 Lease（防止多 Agent 同时操作同一任务）
- 每 5 分钟发送 Heartbeat（Lease 续约）
- 状态转换后自动生成 Snapshot（用于中断恢复）

**多 Agent 并行执行（v2.4 新增）：**
- 多个 Agent 可同时从 backlog 中抢单式认领不同任务
- `execute` 省略 task-id 时自动认领：`python .harness/agent-guard/cli.py execute`
- `claim [--execute]` 可单独认领或认领后立即执行
- 每个 Agent 独立持有 Lease，互不干扰

**产出物：**
- 代码文件
- 测试文件
- 多次 git commit（每个任务一次）

### 阶段四：完成（Finishing）

**触发命令：** `/finish-branch`

**Agent-Guard 状态：** `Entropy Review → Done`（自动执行 G5）

**做什么：**
- 运行完整测试套件
- 检查覆盖率（默认阈值 80%）
- 运行 linter
- 读取 finishing-policy.yaml
- 根据策略自动决策：merge / PR / 保留分支
- **运行 `python .harness/agent-guard/cli.py finish TASK-xxx` 执行 G5 Verification Proof 并将状态推进到 Done**
- 自动写 observation（commit-summary / test-failure / lint-failure / decision / entropy / taste）
- 自动运行 `detect-entropy.sh`（扫描最近 7 天复杂度）
- 自动运行 `cluster-observations.sh`（聚类最近 30 天观察）
- 更新 CLAUDE.md 动态区块

**Gate：**
- **G5 Verification Proof**（硬阻断）：运行 plan 中定义的 verification_command，确认测试通过

**决策规则（来自 finishing-policy.yaml）：**

| 条件 | 动作 |
|:---|:---|
| 测试通过 + 覆盖率≥80% + 无严重 lint 错误 + 分支未落后 | `auto_merge` |
| 测试通过 + 复杂度评分<high | `create_pr` |
| 测试失败 | `keep_branch` + 创建 observation |

### 旁路状态详解

#### Blocked（阻塞）

**进入时机：** 任意非终端状态下，遇到外部依赖或需要人工输入

```bash
python .harness/agent-guard/cli.py block TASK-001 --reason "等待第三方 API 文档"
```

**自动行为：**
- 记录 `blocked_from`（进入 Blocked 前的状态）
- 释放 Lease
- 解除后自动恢复到之前的状态

#### Needs Simplification（需要简化）

**进入时机：** G3 Entropy Check 失败或 G5 Verification Proof 失败

```bash
python .harness/agent-guard/cli.py simplify TASK-001
```

**退出路径：**
```bash
# 路径 A: 简化后重新执行（重新经过 G3）
python .harness/agent-guard/cli.py execute TASK-001

# 路径 B: 需要重新设计（回到 Plan Ready）
python .harness/agent-guard/cli.py plan TASK-001 --approve
```

---

## 配置体系说明

Harness 采用三层架构，所有配置集中在 `.harness/` 目录：

### L1：项目级（必需）

**位置：** `.harness/superpowers/`

每个项目必须有自己的 L1 配置，直接驱动 Claude Code 工作。

| 文件 | 作用 |
|:---|:---|
| `skills/*.md` | 17 个 Superpowers 技能定义 |
| `plan-schema.yaml` | 计划约束验证规则 |
| `finishing-policy.yaml` | 完成阶段自动决策规则 + 记忆写入配置 |
| `design-harness.yaml` | Planner-Evaluator 循环配置 |

### L2：团队级（可选，推荐）

**位置：** `.harness/team/`（git submodule）

团队共享规范，通过 `git submodule` 在多个项目间共享。

| 文件 | 作用 |
|:---|:---|
| `shared-axioms.md` | 团队公理（API 设计、测试、Python 规范等）|
| `standards.md` | 编码/测试/文档标准 |
| `reviewer-pool.yaml` | Reviewer 代理分配规则 |

**设置方法：**
```bash
# 在项目根目录
git submodule add https://github.com/your-org/team-harness.git .harness/team

# 更新共享配置
git submodule update --remote .harness/team
```

### L3：组织级（预留）

**位置：** `.harness/workflows/`

工作流定义和模型路由配置。

| 文件 | 作用 |
|:---|:---|
| `feature-development.md` | 特性开发工作流模板 |
| `bug-fix.md` | Bug 修复工作流模板 |
| `manual-mode.yaml` | 手动触发命令映射（含 `/reflect`）|
| `model-routing.yaml` | 角色-模型映射配置 |

**模型路由示例：**

| 角色 | 主模型 | 备选模型 |
|:---|:---|:---|
| Planner | claude-opus-4-7 | claude-sonnet-4-6 |
| Generator | claude-sonnet-4-6 | claude-haiku-4-5-20251001 |
| Evaluator | claude-opus-4-7 | gpt-4o |

---

## 技能速查表

Harness 包含 17 个官方 Superpowers 技能，覆盖完整开发生命周期：

### 流程技能（何时调用）

| 技能 | 触发时机 | 一句话说明 |
|:---|:---|:---|
| `using-superpowers` | **每次会话开始** | 强制检查并加载适用的技能 |
| `brainstorming` | `/init-feature` | 设计阶段：头脑风暴 → spec |
| `writing-plans` | `/plan-feature` | 计划阶段：spec → 实现计划 |
| `executing-plans` | `/execute-plan` | 执行阶段：手动逐步执行计划 |
| `subagent-driven-development` | `/execute-plan` | 执行阶段：子代理自动执行任务 |
| `finishing-a-development-branch` | `/finish-branch` | 完成阶段：测试 → merge/PR |
| `memory-reflection` | `/reflect` | 记忆提炼：observation → pattern → axiom |

### 纪律技能（开发约束）

| 技能 | 触发时机 | 一句话说明 |
|:---|:---|:---|
| `test-driven-development` | 写代码前 | 无失败测试不写生产代码 |
| `systematic-debugging` | 遇到 bug | 先找根因再修复 |
| `verification-before-completion` | 声称完成前 | 必须有验证证据 |

### 协作技能（代码审查）

| 技能 | 触发时机 | 一句话说明 |
|:---|:---|:---|
| `requesting-code-review` | 完成任务后 | 分派审查代理 |
| `receiving-code-review` | 收到反馈后 | 验证再实施，不盲从 |

### 效率技能（工具方法）

| 技能 | 触发时机 | 一句话说明 |
|:---|:---|:---|
| `dispatching-parallel-agents` | 多个独立 bug | 并行分派代理修复 |
| `using-git-worktrees` | 开始新功能 | 创建隔离工作区 |
| `writing-skills` | 编写新技能 | TDD 方式写技能文档 |

---

## 命令参考

### Harness 主命令

| 命令 | Agent-Guard 状态 | 对应技能 | 产出物 |
|:---|:---|:---|:---|
| `/init-feature <描述>` | Inbox | brainstorming | `docs/superpowers/specs/YYYY-MM-DD-<feature>-design.md` |
| `/plan-feature <spec>` | Inbox → Plan Ready | writing-plans | `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` |
| `/execute-plan <plan>` | Plan Ready → Executing → Patch Ready → Entropy Review | executing-plans / subagent-driven-development | 代码 + 测试 |
| `/finish-branch` | Entropy Review → Done | finishing-a-development-branch | merge / PR |
| `/fix-bug <issue>` | Inbox → Executing | test-driven-development + systematic-debugging | 修复 + 回归测试 |
| `/reflect` | 不影响状态 | memory-reflection | patterns/ + axioms.md |

### Agent-Guard CLI 命令

| 命令 | 状态转换 | Gate | 用途 |
|:---|:---|:---|:---|
| `init <task-id> [--spec <path>]` | → Inbox | 无 | 创建新任务 |
| `plan <task-id> --approve` | Inbox → Plan Ready | G1 + G2 | 批准 plan（G2 超预算时自动语义感知拆分并记录子任务到父 snapshot，检测重复） |
| `execute [<task-id>]` | Plan Ready → Executing | G3 | 开始执行，获取 Lease，**自动标记 plan 第 1 步为 in_progress**（省略则自动认领） |
| `claim [--execute]` | — | — | 从 backlog 认领下一个 Plan Ready 任务 |
| `patch <task-id>` | Executing → Patch Ready | G4 | 标记代码完成 |
| `review <task-id>` | Patch Ready → Entropy Review | 无 | 进入熵审查 |
| `finish <task-id>` | Entropy Review → Done | G5 | 完成验证，释放 Lease |
| `progress <task-id> --step N --status done` | — | — | 更新 plan 步骤完成进度到 snapshot（**强制**：每个 step 完成后必须更新，禁止批量）；**子任务自动同步进度到父任务** |
| `simplify <task-id>` | → Needs Simplification | 无 | 标记需要简化 |
| `block <task-id> --reason <msg>` | → Blocked | 无 | 标记阻塞 |
| `unblock <task-id>` | Blocked → 之前状态 | 无 | 解除阻塞 |
| `status <task-id>` | — | — | 查看任务状态和历史 |
| `list [--state <s>] [--recoverable] [--flat] [--no-children]` | — | — | 列出任务（默认树形） |
| `resume <task-id>` | — | — | 中断后恢复，加载 Snapshot |
| `heartbeat <task-id>` | — | — | 发送 Lease 心跳 |
| `gate-check <gate> <task-id>` | — | — | 手动触发 Gate 验证 |

### 辅助脚本

| 脚本 | 用法 | 作用 | 执行方式 |
|:---|:---|:---|:---|
| `auto-observe.sh` / `auto-observe.ps1` | `bash .claude/scripts/auto-observe.sh <mode>` | 自动生成观察记录 | **自动**（finish-branch / fix-bug 后触发） |
| `cluster-observations.sh` | `bash .claude/scripts/cluster-observations.sh [days]` | 自动聚类 observation | **自动**（finish-branch 后触发；/reflect 内部自动运行） |
| `detect-memory-conflicts.sh` | `bash .claude/scripts/detect-memory-conflicts.sh` | 检测记忆冲突 | **自动**（/reflect 内部自动运行） |
| `check-reflection-due.sh` | `bash .claude/scripts/check-reflection-due.sh` | 检查 reflection 是否到期 | **自动**（session_start hook） |
| `check-invariants.sh` | `bash .claude/scripts/check-invariants.sh [domain]` | 加载架构不变量 | **自动**（执行计划前 skill 内加载） |
| `detect-entropy.sh` | `bash .claude/scripts/detect-entropy.sh [days]` | 检测复杂度反模式 | **自动**（finish-branch 后 + /reflect 内部 + execute-plan 前） |
| `load-memory-context.sh` | `bash .claude/scripts/load-memory-context.sh <skill> [domain]` | 统一加载全部 5 层记忆 | **按需**（供人类快速浏览；AI skill 自动读取各层文件） |

---

## Windows 环境专项

### PowerShell 替代命令

| Bash 命令 | PowerShell 等效命令 |
|:---|:---|
| `cp -r src dest` | `Copy-Item -Recurse src dest` |
| `mkdir -p path` | `New-Item -ItemType Directory -Force -Path path` |
| `rm file` | `Remove-Item file` |
| `cat file` | `Get-Content file` |
| `export VAR=value` | `$env:VAR = "value"` |

### Bash 脚本执行

本项目部分脚本为 `.sh` 格式。Windows 用户有以下选择：

1. **Git Bash**（推荐）：安装 Git for Windows 后自带，可在 Git Bash 终端直接运行所有脚本
2. **WSL**：在 WSL 环境中运行，与 Linux 体验一致
3. **Claude Code 内置**：Claude Code 自带 bash 解释器，可直接执行 `.sh` 脚本
4. **PowerShell 替代**：部分脚本提供 `.ps1` 版本（如 `auto-observe.ps1`）

### Python 与 Agent-Guard

Agent-Guard CLI 基于 Python，Windows 下需确保：

```powershell
# 验证 Python 版本（需 3.10+）
python --version

# 安装依赖
pip install pyyaml

# 验证 CLI
python .harness/agent-guard/cli.py --help
```

### Git Worktree（Windows）

```powershell
# 创建隔离工作区
git worktree add .worktrees/feature-oauth2 -b feature/oauth2

# 进入工作区
cd .worktrees/feature-oauth2

# 开发完成后清理
git worktree remove .worktrees/feature-oauth2
```

**注意事项：**
- `.worktrees/` 目录必须在 `.gitignore` 中
- 分支名不能已存在
- 清理前确保所有变更已提交或 stash

### 路径分隔符

所有配置文件（`CLAUDE.md`、`.harness/workflows/*.yaml`、Agent-Guard snapshot）使用**正斜杠 `/`** 作为路径分隔符，这在 Windows Python 和 Git Bash 中均可正常解析。请勿使用反斜杠 `\`。

---

## 最佳实践

### 1. 总是使用 Git Worktrees

每个功能/bugfix 在独立 worktree 中开发，避免污染主工作区：

```bash
# 创建 worktree
git worktree add .worktrees/feature-oauth2 -b feature/oauth2

# 进入 worktree
cd .worktrees/feature-oauth2

# 开发完成后清理
git worktree remove .worktrees/feature-oauth2
```

### 2. 遵循 TDD 循环

```
RED   →  GREEN  →  REFACTOR
写失败测试 → 最简实现通过 → 重构保持通过
```

每个任务必须包含测试步骤，没有失败测试不写生产代码。

### 3. 频繁提交

每个任务完成后立即提交，保持 commit 历史清晰：

```bash
git add .
git commit -m "feat: add OAuth2 config models (Task 1/8)"
```

### 4. 利用模型路由优化成本

- **Planner（Opus 4.7）**：架构设计、复杂推理
- **Generator（Sonnet 4.6）**：代码实现、常规任务
- **Evaluator（Opus 4.7）**：质量评估、审查
- **简单任务（Haiku 4.5）**：短消息、非代码工作

### 5. 保持 spec 和 plan 同步

如果执行过程中发现计划与实际情况不符，更新 plan 文件反映实际变更，而不是默默偏离。

### 6. 审查循环不可跳过

在 `subagent-driven-development` 中：
- 必须先通过 **spec 合规性审查**
- 再通过 **代码质量审查**
- 才能标记任务完成

### 7. 每周运行 /reflect

```
你: /reflect
AI: [加载 memory-reflection 技能]
AI: 自动运行 cluster-observations + detect-entropy + detect-memory-conflicts...
AI: 扫描 observations、提炼 patterns、更新 CLAUDE.md...
```

> **你不需要手动运行 `cluster-observations.sh`、`detect-entropy.sh` 或 `detect-memory-conflicts.sh`。** 这些脚本已在 `/reflect` 流程内自动执行。
>
> **唯一需要手动触发的是 `/reflect` 本身**，因为 pattern/decision/failure/taste 的提炼需要 AI 判断和潜在的人工确认（特别是 invariant 不可自动升级）。

定期 reflection 让项目越用越聪明。session_start hook 会在每周首次启动时提醒你 reflection 是否到期。

### 8. Harness 维护者：每次迭代后同步文档

> **注意**：本条仅适用于 **harness 模板项目自身的维护者**。使用 harness 的其他项目无需遵循。

**规则：每次对 harness 工作流进行功能迭代后，更新 README.md 和 HARNESS_USAGE_GUIDE.md**

检查方式：
```bash
python .claude/scripts/check-doc-sync.py
```

**自检清单：**
- [ ] 两个文档版本号一致
- [ ] 新功能在「核心特性」或「工作流详解」中有说明
- [ ] 新命令/脚本在「命令参考」中登记
- [ ] 故障排除章节补充新增常见问题

---

## 故障排除

### 问题：技能未加载

**症状：** AI 没有按照技能流程工作（比如没有先提问就写代码）

**排查：**
1. **Claude Code 应用**：检查 `.claude/skills/` 下是否有对应的 `SKILL.md` 文件（如 `init-feature/SKILL.md`）
2. **VS Code 聊天**：检查 `CLAUDE.md` 是否包含 Slash Command 处理规则；如刚修改过，先运行 `/clear` 重新加载上下文
3. 检查技能文件是否存在且 frontmatter 正确（以 `---` 开头，包含 `name` 和 `description`）
4. 在 Claude Code 中尝试手动调用：`/skill <skill-name>`

### 问题：VS Code 聊天中 `/init-feature` 无响应

**症状：** 在 VS Code Claude 聊天中输入 `/init-feature`，AI 当作普通聊天回复

**原因：** VS Code 聊天不自动扫描 `.claude/skills/`，依赖 `CLAUDE.md` 上下文。如果 `CLAUDE.md` 刚修改过或会话未刷新，规则未生效。

**解决：**
1. 输入 `/clear` 清空当前上下文
2. 重新输入 `/init-feature '测试功能'`
3. 确认 `CLAUDE.md` 中包含「Slash Command 处理规则」章节

### 问题：plan-schema.yaml 验证失败

**症状：** AI 提示计划不符合约束

**常见原因：**
- 任务缺少测试步骤
- 包含 TODO/TBD 占位符
- 包含模糊词（适当/可能/考虑/稍后/大概/尽量）
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
2. 或手动强制释放：`rm .harness/agent-guard/leases/TASK-001-lease.json`（Bash）/ `del .harness\agent-guard\leases\TASK-001-lease.json`（CMD）
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

## 进阶：自定义技能

如果你想为团队创建自定义技能：

1. 在 `.harness/superpowers/skills/` 下创建新文件
2. 使用标准 frontmatter：
   ```yaml
   ---
   name: my-custom-skill
   description: Use when [触发条件]
   triggers: ["keyword1", "keyword2"]
   type: skill
   version: "1.0"
   ---
   ```
3. 使用 `writing-skills` 技能的 RED-GREEN-REFACTOR 方法测试
4. 添加到 `.claude/settings.json` 的 paths 中

---

## 相关文档

| 文档 | 位置 | 说明 |
|:---|:---|:---|
| 项目总览 | [README.md](README.md) | 核心特性、目录结构、快速参考 |
| 记忆系统完整指南 | [MEMORY_HARNESS_GUIDE.md](MEMORY_HARNESS_GUIDE.md) | 记忆系统架构、使用教程 |
| Harness Engineering 深度指南 | [harness-engineering-guide.md](harness-engineering-guide.md) | 8 篇核心文章总结、三大扩展维度 |
| 架构设计规格 | [docs/superpowers/specs/2026-04-20-guardharness-design.md](docs/superpowers/specs/2026-04-20-guardharness-design.md) | 本项目的架构设计文档 |
| 架构可视化（在线）| [docs/superpowers/specs/architecture-visual.html](docs/superpowers/specs/architecture-visual.html) | 在线架构图 |
| 架构可视化（离线）| [docs/superpowers/specs/architecture-visual-offline.html](docs/superpowers/specs/architecture-visual-offline.html) | 离线架构图 |
| 实现计划 | [docs/superpowers/plans/2026-04-20-guardharness.md](docs/superpowers/plans/2026-04-20-guardharness.md) | 本项目的实现计划 |
| Hermes 兼容指南 | [.harness/HERMES_COMPAT.md](.harness/HERMES_COMPAT.md) | Hermes 工具兼容性说明 |
| 团队模板示例 | [examples/team-harness/](examples/team-harness/) | 团队共享配置示例 |

---

*本手册配合 `CLAUDE.md` 和 `.harness/superpowers/skills/using-superpowers.md` 使用效果更佳。*
