# Project Context

**重要：当用户消息以 `/` 开头时，表示触发 Superpowers 工作流命令，禁止当作普通聊天回复。详见下方「Slash Command 处理规则」。**

## Superpowers Workflow
本项目使用 Superpowers × Harness Engineering 工作流。
完整配置位于 `.harness/` 目录。

## Quick Commands
- 开始新功能设计: `/init-feature <描述>`
- 创建实现计划: `/plan-feature <spec-path>`
- 执行计划: `/execute-plan <plan-path>`
- 完成分支: `/finish-branch`
- 记忆反思: `/reflect`

### Scrum / 迭代管理用法
支持在命令中显式指定文档路径，便于按迭代或功能模块组织：

```
/init-feature 把设计文档写到 docs/superpowers/specs/sprint-3/oauth2-login-design.md，设计OAuth2登录
/plan-feature docs/superpowers/specs/sprint-3/oauth2-login-design.md --output docs/superpowers/plans/sprint-3/oauth2-login.md
/execute-plan docs/superpowers/plans/sprint-3/oauth2-login.md
```

### Slash Command 处理规则（重要）
当用户消息以 `/` 开头时，必须按以下规则处理，不得当作普通聊天回复：

| 命令 | 必须执行的操作 |
|------|----------------|
| `/init-feature` | **前置：读取** `.harness/team/shared-axioms.md`、`.harness/team/standards.md`、`.claude/memory/MEMORY.md`（如存在），将约束注入上下文。**然后**加载 `superpowers:brainstorming` skill，严格按照其工作流执行。一次只问一个澄清问题，提出 2-3 种方案并标记最简单方案，最终 spec 保存到 `docs/superpowers/specs/`。**然后**运行 `python .harness/agent-guard/cli.py init TASK-xxx --spec <spec-path>` 初始化任务。完成后提醒用户运行 `/plan-feature`。 |
| `/plan-feature` | **前置：读取** `.harness/team/shared-axioms.md`、`.harness/team/standards.md`、`.claude/memory/MEMORY.md`（如存在），将约束注入上下文。**然后**加载 `superpowers:writing-plans` skill，读取提供的 spec，严格按照 `plan-schema.yaml` 创建计划。每个任务必须是可验证目标（Goal + Verify），禁止 TODO/占位符/模糊词。计划必须包含 Agent-Guard 状态图（Mermaid/PlantUML）和每个 Task 的 Gate 检查点标注。计划保存到 `docs/superpowers/plans/`。**然后**运行 `python .harness/agent-guard/cli.py plan TASK-xxx --approve` 执行 G1/G2 Gate 检查，状态进入 Plan Ready。 |
| `/execute-plan` | **前置：读取** `.harness/team/shared-axioms.md`、`.harness/team/standards.md`、`.claude/memory/MEMORY.md`（如存在），将约束注入上下文。**然后**根据任务复杂度选择技能：任务多且独立 → 加载 `superpowers:subagent-driven-development` skill；否则加载 `superpowers:executing-plans` skill。执行前运行 `python .harness/agent-guard/cli.py execute TASK-xxx` 做 G3 Entropy Check（Plan Ready → Executing）。逐步执行，每步后运行测试，失败立即停止，确认 diff 只修改计划内文件。全部完成后运行 `python .harness/agent-guard/cli.py patch TASK-xxx`（G4 Surgical Check，Executing → Patch Ready）和 `python .harness/agent-guard/cli.py review TASK-xxx`（Patch Ready → Entropy Review）。 |
| `/finish-branch` | **前置：读取** `.harness/team/shared-axioms.md`、`.harness/team/standards.md`、`.claude/memory/MEMORY.md`（如存在），将约束注入上下文。**然后**加载 `superpowers:finishing-a-development-branch` skill。运行完整测试套件、检查覆盖率（默认 80%）、运行 linter、读取 `finishing-policy.yaml` 决策（auto_merge / create_pr / keep_branch）。**最后**运行 `python .harness/agent-guard/cli.py finish TASK-xxx` 执行 G5 Verification Proof（Entropy Review → Done），然后写 observation 并更新 CLAUDE.md 动态区块。 |
| `/fix-bug` | **前置：读取** `.harness/team/shared-axioms.md`、`.harness/team/standards.md`、`.claude/memory/MEMORY.md`（如存在），将约束注入上下文。**然后**先加载 `superpowers:systematic-debugging` skill 找根因，再加载 `superpowers:test-driven-development` skill 写失败测试。最简修复，禁止过度设计，提交修复和回归测试，最后写 failure observation。 |
| `/reflect` | **前置：读取** `.harness/team/shared-axioms.md`、`.harness/team/standards.md`、`.claude/memory/MEMORY.md`（如存在），将约束注入上下文。**然后**加载 `superpowers:memory-reflection` skill。扫描所有 observations，提取稳定模式，更新 CLAUDE.md 动态区块，检测跨项目模式升级为全局公理，记录 reflection 成本指标。 |

**注意**：以上命令触发后，禁止闲聊或要求用户确认，直接进入对应 skill 的工作流。

## Agent-Guard (State-Driven Control Plane)

Agent-Guard 为 AI 任务执行提供状态机管控、硬 Gate 拦截和中断恢复能力。

### 核心命令
```bash
# 主线生命周期
python .harness/agent-guard/cli.py init TASK-001 --spec docs/superpowers/specs/feature.md
python .harness/agent-guard/cli.py plan TASK-001 --approve
python .harness/agent-guard/cli.py execute TASK-001
python .harness/agent-guard/cli.py patch TASK-001
python .harness/agent-guard/cli.py review TASK-001
python .harness/agent-guard/cli.py finish TASK-001

# 旁路命令
python .harness/agent-guard/cli.py simplify TASK-001
python .harness/agent-guard/cli.py block TASK-001 --reason "..."
python .harness/agent-guard/cli.py unblock TASK-001

# 状态查询与恢复
python .harness/agent-guard/cli.py status TASK-001
python .harness/agent-guard/cli.py list --recoverable
python .harness/agent-guard/cli.py resume TASK-001

# 手动 Gate 检查
python .harness/agent-guard/cli.py gate-check g3_entropy_check TASK-001
```

### 状态机（8 状态）
主线: `Inbox -> Plan Ready -> Executing -> Patch Ready -> Entropy Review -> Done`
旁路: `Blocked`（外部依赖）、`Needs Simplification`（熵审查失败回流）

### 硬 Gate（否决权式检查）
| Gate | 转换点 | 作用 |
|------|--------|------|
| G1 Plan Valid | Inbox -> Plan Ready | 验证 plan 无占位符、无模糊词、包含必要章节 |
| G2 Complexity Budget | Inbox -> Plan Ready | 检查文件/步骤数是否超预算（Phase 1 警告）|
| G3 Entropy Check | Plan Ready -> Executing / Needs Simplification -> Executing | 运行 detect-entropy.sh，阻断复杂度爆炸 |
| G4 Surgical Check | Executing -> Patch Ready | 确认 diff 只修改相关文件 |
| G5 Verification Proof | Entropy Review -> Done | 运行验证命令并确认通过 |

### 旁路状态
- **Blocked**: 外部依赖/等待人工输入时 `block TASK-001`，解除时 `unblock TASK-001` 自动恢复之前状态
- **Needs Simplification**: Entropy 审查失败后 `simplify TASK-001`，简化后可 `execute` 重新进入主线

### 中断恢复
任务在非终端状态中断后，通过 Snapshot 机制快速恢复：
1. `python .harness/agent-guard/cli.py resume TASK-001`
2. 自动加载 `required_context`（精确文件 + 记忆，非全部历史）
3. 注入 `recovery_prompt`，Agent 从当前步骤继续
4. Resume 目标时间 < 30 秒

## Project Standards
- 所有设计文档存放于 `docs/superpowers/specs/`
- 所有实现计划存放于 `docs/superpowers/plans/`
- 隔离工作区使用 `.worktrees/`
- **计划文档必须包含**：Agent-Guard 状态图（Mermaid/PlantUML）+ 每个 Task 的 Gate 检查点标注
- 详见 `.harness/superpowers/plan-schema.yaml`

## Memory System
本项目启用结构化记忆系统，越用越聪明。

### 项目级记忆（本项目内）
- 观察记录: `.claude/memory/observations/`
- 提炼模式: `.claude/memory/patterns/`
- 迭代回顾: `.claude/memory/retro/`
- 记忆索引: `.claude/memory/MEMORY.md`

### 全局级记忆（跨项目）
- 用户角色: `.claude/memory/user/role.md`
- 工作偏好: `.claude/memory/user/preferences.md`
- 跨项目公理: `.claude/memory/user/axioms.md`
- 同步目标: `~/.claude/memory/user/`（Claude Code 原生 `/memory` 的备份）

### 使用方式
- 手动触发: `/reflect`
- 自动提醒: 每周 session_start 时检查，逾期会提示
- 自动沉淀: `/finish-branch` 和 `/fix-bug` 后自动写 observation
- 跨项目升级: 同一模式在 2+ 项目出现 → 升级为全局公理

## Team Shared Config
团队共享规范: `.harness/team/` (独立 git 仓库，可提取为 git submodule)

已包含文件：
- `shared-axioms.md` — 团队级公理与原则
- `standards.md` — 编码、测试与文档标准
- `reviewer-pool.yaml` — Reviewer Agent 分配规则

如需作为跨项目共享配置，创建远程仓库后注册为 submodule：
```bash
git submodule add <your-org>/team-harness.git .harness/team
```

---

<!-- DYNAMIC-BLOCK: architecture -->
## 当前架构快照
<!-- AUTO-GENERATED: 基于最近 specs 和代码结构自动生成 -->
<!-- 当前为空，完成首次 /finish-branch 后将自动填充 -->
<!-- END-DYNAMIC -->

---

<!-- DYNAMIC-BLOCK: recent-decisions -->
## 近期重大决策
<!-- AUTO-GENERATED: 从最近 3 次 finish-branch 的 retro 中提取 -->
<!-- 当前为空，完成首次 /finish-branch 后将自动填充 -->
<!-- END-DYNAMIC -->

---

<!-- DYNAMIC-BLOCK: common-pitfalls -->
## 本项目常见陷阱
<!-- AUTO-GENERATED: 从 fix-bug observations 中提取高频根因 -->
<!-- 当前为空，首次 bug 修复后将自动填充 -->
<!-- END-DYNAMIC -->

---

<!-- DYNAMIC-BLOCK: invariants -->
## 架构不变量（不可违反）
<!-- AUTO-GENERATED: 从 `.claude/memory/invariants/` 加载 -->
<!-- 当前为空，声明首个 invariant 后将自动填充 -->
<!-- END-DYNAMIC -->

---

<!-- DYNAMIC-BLOCK: decisions -->
## 活跃架构决策
<!-- AUTO-GENERATED: 从 `.claude/memory/decisions/` 加载 active 状态 -->
<!-- 当前为空，首次 /reflect 后将自动填充 -->
<!-- END-DYNAMIC -->

---

<!-- DYNAMIC-BLOCK: taste -->
## 已确认编码偏好
<!-- AUTO-GENERATED: 从 `.claude/memory/taste/` 加载 confidence: confirmed -->
<!-- 当前为空，首次 /reflect 后将自动填充 -->
<!-- END-DYNAMIC -->

---

<!-- DYNAMIC-BLOCK: patterns -->
## 已稳定的编码模式
<!-- AUTO-GENERATED: 出现 3 次以上的模式，由 memory-reflection 提炼 -->
<!-- 当前为空，运行 /reflect 后将自动填充 -->
<!-- END-DYNAMIC -->
