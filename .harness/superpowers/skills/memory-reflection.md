---
name: superpowers:memory-reflection
description: |
  Run weekly or after milestone to scan observations, extract stable patterns,
  and upgrade them into project-level axioms (CLAUDE.md) or global user memory.
  Also manages the 5-layer memory system: decisions, failures, entropy, invariants, taste.
triggers: ["reflect", "memory-reflection", "weekly-review", "milestone-review"]
type: skill
version: "2.0"
---

# Memory Reflection Skill v2.0

## When to Use

- At the end of a milestone or sprint
- Weekly, if the project is actively developed
- Before starting a major new feature (to load lessons learned)
- When explicitly requested by the user via `/reflect` or similar
- When `session_start` hook indicates reflection is overdue

## Core Principle

**Auto Memory accumulates; Reflection distills.**

Raw observations are noise. Only patterns that appear consistently across multiple scenes deserve to be injected into future context.

## The 5-Layer Memory Architecture

This skill manages 5 specialized memory layers in addition to the existing observations → patterns pipeline:

| Layer | Directory | Captures | Checked Before Generation? |
|:---|:---|:---|:---|
| **Decisions** | `.claude/memory/decisions/` | Why designs were chosen | Yes (constrains design space) |
| **Failures** | `.claude/memory/failures/` | Organizational trauma / incidents | Yes (prevents recurrence) |
| **Entropy** | `.claude/memory/entropy/` | AI complexity anti-patterns | Yes (prevents shit mountains) |
| **Invariants** | `.claude/memory/invariants/` | Hard architectural constraints | **Always** (constitutional rules) |
| **Taste** | `.claude/memory/taste/` | Human coding preferences | Yes (style guidance) |

## The Process

### Phase 0: Invariant Pre-Check (Pre-Generation Gate)

**This phase runs BEFORE any code generation skill loads context.**

1. Identify domain from current task (payment, inventory, auth, general)
2. Load `.claude/memory/invariants/<domain>-*.md`
3. Load `.claude/memory/invariants/general-*.md`
4. Inject into skill context as non-negotiable rules
5. If any invariant has `enforcement: pre-generation`, prepend to prompt:
   "Before generating code, you MUST respect the following architectural invariants..."

**Invariants are NEVER auto-promoted from observations.** They must be explicitly declared.

### Phase 1: Scan

1. List all files in `.claude/memory/observations/` within the last 30 days
   - Separate **auto-generated** observations (`generated_by: auto-observe` in frontmatter) from **manual** observations
   - Auto-generated observations usually contain git context but lack root cause analysis
   - **Check `needs_compaction: true` in frontmatter**: These observations have truncated file lists (>20 files). Load only the summary sections (`## Commit Summary`, `## Change Pattern Analysis`), skip the raw `## File Breakdown` block to avoid token bloat.
2. List all files in `.claude/memory/patterns/`
3. **NEW**: List all files in `.claude/memory/decisions/` (active status)
4. **NEW**: List all files in `.claude/memory/failures/`
5. **NEW**: List all files in `.claude/memory/entropy/`
6. **NEW**: List all files in `.claude/memory/invariants/`
7. **NEW**: List all files in `.claude/memory/taste/` (confirmed + tentative)
8. Read `.claude/memory/MEMORY.md` for current index state
9. Read `.claude/memory/user/axioms.md` for existing global axioms
10. Read `.claude/memory/user/preferences.md` for existing taste preferences

### Phase 2: Extract (5-Layer Extraction)

#### Step 2a: Semantic Clustering (辅助聚类 — 自动运行)

在人工提取之前，skill 会自动运行聚类工具。用户不需要手动执行此脚本：

1. 自动运行 `bash .claude/scripts/cluster-observations.sh 30`
2. 分析聚类报告：
   - **Cluster（≥2 文件）**：这些 observation 在 tags 或关键词上高度相似，提示潜在模式
   - **Similarity Pairs**：成对关联，帮助发现跨场景的模式
   - **Singletons**：未聚类的孤立观察，可能是独特事件或需要补充 tags
3. 将聚类结果作为 Extract 的输入参考

**聚类原理**：基于 frontmatter tags 重叠（权重 0.6）+ 正文关键词重叠（权重 0.4），相似度 ≥0.30 的文件归入同一 cluster。

**按类型提取关键词**：
- `type: decision` → 提取 `## Options Considered`, `## Decision`, `## Rationale`
- `type: failure` → 提取 `## What Failed`, `## Root Cause`, `## What We Learned`
- `type: entropy` → 提取 `## The Smell`, `## Prevention Rule`, category
- `type: taste` → 提取 `## The Preference`, `## Source Context`

#### Step 2b: 5-Layer Extraction

For each observation（优先处理有 cluster 关联的文件）:

**Layer 1 — Decision Extraction:**
- From `type: decision` observations and `## 决策记录` sections
- Extract: Context, Options Considered, Decision, Rationale, Consequences
- If a decision has been `active` for 2+ weeks, mark as permanent

**Layer 2 — Failure Extraction:**
- From `type: test-failure` + `type: bug-fix` observations with systemic impact
- Distinguish from routine bugs: Does this reveal an organizational blind spot?
- Extract: What Failed, Impact, Root Cause, What We Learned, Mitigation

**Layer 3 — Entropy Extraction:**
- From observations mentioning complexity, abstraction, "too clever", over-engineering
- Extract: The Smell, Before/After examples, Why AI Creates This, Prevention Rule
- Run `bash .claude/scripts/detect-entropy.sh` for automated detection

**Layer 4 — Invariant Detection:**
- **Invariants are NOT extracted from observations.** They must be explicitly declared.
- However, if multiple failures share the same root cause, flag as "candidate invariant"
- Example: 3 failures all caused by bypassing payment state machine → suggest declaring invariant

**Layer 5 — Taste Extraction:**
- From `type: code-review` observations and human corrections
- Extract: The Preference, Source Context, Examples
- Count occurrences: Same preference from 2+ sources → `confidence: confirmed`

**Existing extraction (Patterns):**
- **Decision**: What choice was made and why?
- **Pitfall**: What went wrong?
- **Correction**: How was it fixed?
- **Pattern**: Is there a reusable principle?

**参考聚类结果**：
- 如果多个 observation 被聚到同一 cluster，检查它们是否描述同一模式的不同表现
- 跨 cluster 的 observation 可能暗示更通用的模式
- Singleton 如果内容重要但缺少 tags，考虑在 extraction 中补充 tag 建议

**Special handling for auto-generated observations:**
- If an auto-generated observation has NOT been manually enhanced (still contains `[Auto-generated]` markers):
  - Extract only the objective facts (files changed, commit messages, error types)
  - Flag it as "needs manual enrichment" if the pattern looks significant
  - Do NOT promote patterns based solely on auto-generated content without manual validation
- If an auto-generated observation HAS been manually enhanced:
  - Treat it the same as manual observations
  - The manual additions (root cause, fix approach) are the valuable parts
- **If `needs_compaction: true` is set in frontmatter**:
  - The raw file list has been truncated (>20 files). Do NOT load the full `## File Breakdown` block.
  - Read only: frontmatter, `## Commit Summary`, and `## Change Pattern Analysis`
  - Use the summary metadata (file count, doc/test/config flags) for pattern detection
  - If the observation looks significant, prompt the user to compact it into a pattern rather than reading the raw diff

Group by similarity. Count frequency of each pattern.

### Phase 2.5: Entropy Scan (NEW — 自动运行)

在人工提取之后，skill 会自动运行熵检测。用户不需要手动执行此脚本：

1. 自动运行 `bash .claude/scripts/detect-entropy.sh 7`
2. 分析近期 git diff 的复杂度指标：
   - 新增文件数量
   - Manager/Handler/Processor/Coordinator 文件数量
   - 接口/抽象类数量 vs 实现数量
   - 配置文件变更数量
3. 与 `.claude/memory/entropy/` 中的已知模式对比
4. 如果发现新熵模式：
   - 生成 entropy observation 到 `.claude/memory/observations/`
   - 在 reflection 报告中标记
5. 如果现有熵模式被重复触发：
   - 标记为 "entropy reinforcement needed"
   - 建议在相关 skill 中加强 Prevention Rule 的强调

### Phase 3: Filter (Stability Check + Conflict Detection)

#### Step 3a: Stability Check

| Frequency | Action | Target |
|:---|:---|:---|
| ≥ 3 times in this project, across different features | Upgrade to project pattern | `patterns/*.md` + `CLAUDE.md` dynamic block |
| ≥ 2 times across different projects | Upgrade to global axiom | `/memory` User Memory + `~/.claude/memory/user/axioms.md` |
| < 3 times or only in one scene | Keep in observations | No action |
| Contradicts existing pattern | Flag for review | Log conflict, ask user |

**5-Layer 过滤规则（新增）：**

| Layer | 稳定性标准 | 写入目标 |
|:---|:---|:---|
| **Decision** | active 状态持续 2+ 周 | `decisions/*.md`（永久保留，标记 superseded） |
| **Failure** | 任何系统性失败 | `failures/*.md`（**永不归档**） |
| **Entropy** | 同一模式被检测 2+ 次 | `entropy/*.md` |
| **Invariant** | **从不**从 observation 自动升级 | `invariants/*.md`（必须显式声明） |
| **Taste** | 同一偏好被观察 2+ 次 | `taste/*.md`（`confidence: confirmed`） |

#### Step 3b: Automated Conflict Detection (自动运行)

在人工判断之前，skill 会自动运行冲突检测。用户不需要手动执行此脚本：

1. 自动运行 `bash .claude/scripts/detect-memory-conflicts.sh`
2. 分析报告中的多类结果：

**⚠️ Pattern vs Axiom Conflicts（原有）**
- 同一技术对象，pattern 和 axiom 给出相反建议
- 处理策略：区分真正矛盾 vs 条件化差异 → Conditional Upgrade

**🛡️ Invariant Violations（新增）**
- Pattern 或 Decision 可能违反不变量
- 处理策略：**阻止升级**，要求修改 pattern/decision 或重新评估 invariant

**🎭 Taste vs Axiom Conflicts（新增）**
- 品味偏好与架构规则冲突
- 处理策略：Taste 不覆盖 Axiom，但可以在 Axiom 边界内细化风格

**🔥 Entropy Reinforcement（新增）**
- 新 pattern 实际上是已知的熵反模式
- 处理策略：**拒绝该 pattern**，引导至 Prevention Rule

**✅ Alignments（一致）**
- Pattern 和 axiom 方向一致
- 处理策略：标记 `implements_axiom` 或归档重复

**Coverage Gaps（覆盖缺口）**
- Objects in patterns but not covered by axioms
- 处理策略：候选全局公理，进入 Phase 5

#### Step 3c: Conditional Upgrade Proposal

对于条件化差异（非真正矛盾），提出条件化升级方案：

```markdown
# 原始全局公理
所有外部 API 调用必须有超时 + 重试机制

# 新项目模式（条件化差异）
Feishu API 调用避免重试，因为平台有频率限制

# 条件化升级方案
所有外部 API 调用必须有超时 + 重试机制，
**除非**平台明确禁止重试（如 Feishu、Stripe 等 rate-limit 严格的 API）
```

**规则**：
- 用 `**除非**` 或 `**当...时**` 引出条件
- 条件必须具体（技术栈、平台特性、业务场景）
- 不要过度泛化：如果一个例外只在特定项目中成立，保持为项目 pattern，不升级为全局公理

### Phase 4: Write Memory Layers

**Write targets now include 5 new directories:**

1. **Patterns** → `.claude/memory/patterns/<topic>.md`
2. **Decisions** → `.claude/memory/decisions/YYYY-MM-DD-<slug>.md`
3. **Failures** → `.claude/memory/failures/YYYY-MM-DD-<slug>.md`
4. **Entropy** → `.claude/memory/entropy/YYYY-MM-DD-<slug>.md`
5. **Invariants** → `.claude/memory/invariants/<domain>-<slug>.md` (requires manual review)
6. **Taste** → `.claude/memory/taste/YYYY-MM-DD-<slug>.md`

**Update CLAUDE.md dynamic blocks:**
- `<!-- DYNAMIC-BLOCK: patterns -->` (existing)
- `<!-- DYNAMIC-BLOCK: recent-decisions -->` (existing)
- `<!-- DYNAMIC-BLOCK: common-pitfalls -->` (existing)
- `<!-- DYNAMIC-BLOCK: architecture -->` (existing)
- **`<!-- DYNAMIC-BLOCK: invariants -->`** (NEW)
- **`<!-- DYNAMIC-BLOCK: decisions -->`** (NEW)
- **`<!-- DYNAMIC-BLOCK: taste -->`** (NEW)

**Pattern file format:**
```markdown
---
name: <topic>
discovered: YYYY-MM-DD
occurrences: N
confidence: high | medium
---

## Pattern
[Concrete description]

## Scenes Where Observed
- [feature/date]: [brief context]

## When to Apply
[Conditions]

## When NOT to Apply
[Exceptions]
```

**Decision file format:**
```markdown
---
date: YYYY-MM-DD
type: decision
status: active | superseded
decision_id: DEC-YYYY-NNN
scope: project | domain | global
supersedes: []
---

# Decision: <Title>

## Context
## Options Considered
## Decision
## Rationale
## Consequences
## Related
```

**Failure file format:**
```markdown
---
date: YYYY-MM-DD
type: failure
severity: incident | near-miss | lesson
failure_id: FAIL-YYYY-NNN
---

# Failure: <Title>

## What Failed
## Impact
## Root Cause
## What We Learned
## Mitigation
## Detection
## Related Patterns
```

**Entropy file format:**
```markdown
---
date: YYYY-MM-DD
type: entropy
category: abstraction-explosion | manager-proliferation | config-nesting | speculative-interface | over-engineering | indirection-creep
detected_by: code-analysis | human-review
---

# Entropy Pattern: <Title>

## The Smell
## Before / After
## Why AI Tends to Create This
## Prevention Rule
## Detection Heuristic
## Related Observations
```

**Invariant file format:**
```markdown
---
name: <slug>
domain: payment | inventory | auth | general
type: invariant
enforcement: pre-generation | compile-time | runtime | review
violation_severity: critical | high | medium
---

# Invariant: <Title>

## The Rule
## Why This Is Invariant
## What Happens If Violated
## How to Verify Compliance
## Examples (Compliant / Violation)
## Related Decisions
```

**Taste file format:**
```markdown
---
date: YYYY-MM-DD
type: taste
source: code-review | human-correction | explicit-statement
confidence: confirmed | tentative
domain: general | python | javascript | api-design
---

# Taste: <Title>

## The Preference
## Source Context
## Examples (Preferred / Dispreferred)
## When It Applies
## Conflicts
```

### Phase 5: Cross-Project Upgrade (Global Memory)

**5-Layer Cross-Project Rules:**

| Layer | Cross-Project Trigger | Global Target |
|:---|:---|:---|
| **Patterns** | Same principle in 2+ projects, stable ≥2 weeks | `~/.claude/memory/user/axioms.md` |
| **Decisions** | Same architectural decision in 2+ projects | `~/.claude/memory/user/decisions.md` |
| **Failures** | Same root cause category in 2+ projects | `~/.claude/memory/user/failures.md` |
| **Taste** | Same preference confirmed in 2+ projects | `~/.claude/memory/user/preferences.md` |
| **Entropy** | Same anti-pattern in 2+ projects | `~/.claude/memory/user/entropy.md` |
| **Invariants** | Same hard constraint in 2+ projects | `~/.claude/memory/user/invariants.md` |

**Upgrade process for each layer:**

1. **Detect cross-project patterns**
   - Scan global memory files in `~/.claude/memory/user/`
   - Compare current project memory against other projects' `.claude/memory/`
   - A pattern is "cross-project" if the same principle appears in 2+ projects with similar wording

2. **Candidate validation**
   - Verify the pattern is domain-agnostic (not tied to a specific tech stack)
   - Verify it has been stable for at least 2 weeks
   - Check for contradictions with existing global memory

3. **Upgrade to global memory**
   - Append to appropriate global file with source attribution
   - Prompt user to update `/memory` User Memory via Claude Code native command
   - Tag with `global: true` and `source_projects: [project1, project2]`

4. **Propagate back**
   - Mark the item in each project's local memory as `upgraded_to_global: true`
   - This prevents duplicate global entries across projects

### Phase 6: Compact

**Archive Rules by Layer:**

| Layer | Archive Rule | Destination |
|:---|:---|:---|
| **Observations** | Archive >90 days | `.claude/memory/retro/YYYY-MM.md` |
| **Patterns** | Never archive | Keep in `patterns/` permanently |
| **Decisions** | Never archive | Keep in `decisions/` permanently; mark `superseded` instead |
| **Failures** | **NEVER archive** | Permanent organizational trauma memory |
| **Entropy** | Never archive | Keep as active anti-pattern reference |
| **Invariants** | Never archive | Constitutional rules are permanent |
| **Taste** | Never archive | Keep as active style reference |

**Compaction steps:**
1. Archive observations older than 90 days to `.claude/memory/retro/YYYY-MM.md`
2. Verify no failures/decisions were accidentally moved
3. Update `MEMORY.md` index
4. Write `.claude/memory/.last-reflection` with today's date (YYYY-MM-DD)
5. Update `.claude/memory/.last-compact` timestamp

### Phase 7: Record Metrics

**记录本次 reflection 的成本与产出数据：**

1. **Update `reflection-costs.json`**
   - 追加新记录，包含：
     - `date`: 今天
     - `reflection_type`: weekly / milestone / manual
     - `observations_scanned`: Phase 1 扫描的数量
     - `patterns_existing`: 扫描前已有 patterns 数量
     - `patterns_new`: 本次新提炼 patterns 数量
     - `decisions_made`: 本次提取/确认 decisions 数量
     - `failures_logged`: 本次提取 failures 数量
     - `entropy_detected`: 本次检测 entropy 模式数量
     - `invariants_checked`: 本次检查 invariants 数量
     - `taste_confirmed`: 本次 confirmed taste 数量
     - `axioms_candidates`: 全局公理候选数量
     - `archived_count`: 归档 observation 数量
     - `estimated_tokens_input`: 估算输入 token（observation 总字数 × 1.3）
     - `estimated_tokens_output`: 估算输出 token（报告字数 × 1.3）
     - `duration_seconds`: 本次 reflection 耗时（从开始到结束）
     - `model_used`: 使用的模型

2. **Update `observation-conversion.csv`**
   - 如果是 weekly reflection，追加本周数据：
     - `week_start`, `week_end`
     - `observations_created`: 本周新建 observation 数
     - `observations_auto`: 其中 auto-generated 数量
     - `observations_manual`: 其中 manual 数量
     - `upgraded_to_patterns`: 本周升级为 patterns 的数量
     - `upgraded_to_decisions`: 本周升级为 decisions 的数量
     - `upgraded_to_failures`: 本周升级为 failures 的数量
     - `upgraded_to_entropy`: 本周升级为 entropy 的数量
     - `upgraded_to_taste`: 本周升级为 taste 的数量
     - `conversion_rate`: upgraded / created × 100%
     - `avg_enrichment_days`: 平均从 observation 创建到升级为 pattern 的天数

3. **Update `pattern-hit-rate.json`**
   - 对于每个新提炼的 pattern/decision/entropy/taste，初始化 entry：
     - `name`, `file`, `discovered_date`, `layer` (pattern/decision/entropy/taste)
     - `total_hits`: 0
     - `hits_by_skill`: {brainstorming: 0, writing-plans: 0, executing-plans: 0, subagent-driven-development: 0, systematic-debugging: 0}
     - `effectiveness_score`: 0.0

4. **Update `memory-layer-distribution.json`**
   - 记录各层记忆的数量分布：
     - `observations_active`, `patterns`, `decisions_active`, `decisions_superseded`
     - `failures`, `entropy`, `invariants`, `taste_confirmed`, `taste_tentative`
     - `global_axioms`, `global_preferences`

5. **Generate weekly report** (if weekly reflection)
   - 写入 `.claude/memory/metrics/weekly-report-YYYY-MM-DD.md`
   - 包含：转化率趋势、pattern 命中概览、**5-layer 健康度**、成本分析、建议

## Output Format

```
## Reflection Report (YYYY-MM-DD)

### Scanned
- N observations in last 30 days (A auto-generated, M manual)
- P existing patterns
- D active decisions, F failures logged, E entropy patterns, I invariants, T taste preferences
- G global axioms currently tracked

### Auto-Generated Observations Needing Enrichment
1. **[YYYY-MM-DD-commit-summary]**: Contains interesting pattern but lacks root cause
   - Action: Prompt user to enhance or skip

### New Project Patterns (stable, ≥3 occurrences)
1. **[Topic]**: [Description] → Written to `patterns/<topic>.md`
   - Updated CLAUDE.md block: [patterns | recent-decisions | common-pitfalls | architecture]

### New Decisions Extracted
1. **[DEC-YYYY-NNN]**: [Title] → Written to `decisions/YYYY-MM-DD-<slug>.md`
   - Status: active | superseded
   - Consequences noted: [yes/no]

### New Failures Logged
1. **[FAIL-YYYY-NNN]**: [Title] → Written to `failures/YYYY-MM-DD-<slug>.md`
   - Severity: [incident | near-miss | lesson]
   - Root cause captured: [yes/no]

### New Entropy Patterns Detected
1. **[Category]**: [Title] → Written to `entropy/YYYY-MM-DD-<slug>.md`
   - Detection method: [code-analysis | human-review]
   - Prevention rule documented: [yes/no]

### Taste Preferences Updated
1. **[Title]**: [Preference summary] → Written to `taste/YYYY-MM-DD-<slug>.md`
   - Confidence: [confirmed | tentative]
   - Occurrences observed: N

### Invariant Checks
- Invariants checked: N (domain: [list])
- Violations detected: [yes/no, details]
- Candidate invariants flagged: [list]

### Global Memory Candidates (≥2 projects)
1. **[Type: pattern/decision/failure/taste/entropy/invariant]**: [Description]
   - Source projects: [project1, project2]
   - Suggested action: Append to appropriate global file + update `/memory` User Memory

### Archived
- N observations moved to retro/YYYY-MM.md
- **0 failures archived** (permanent memory rule)
- **0 decisions archived** (permanent audit trail)

### Conflicts
- None / [List contradictions with existing patterns, axioms, or invariants]
- Invariant violations: [list or "none"]
- Taste vs axiom conflicts: [list or "none"]
- Entropy reinforcement needed: [list or "none"]

### Metrics Summary
- Duration: N seconds | Input tokens: ~N | Output tokens: ~N
- New patterns: N | Decisions: N | Failures: N | Entropy: N | Taste: N
- Conversion rate: N%
```

## Rules

- Never overwrite existing patterns without noting the change
- Never promote a pattern based on a single data point
- Always preserve the original observations (archive, don't delete)
- **NEVER archive failures** — organizational trauma memory is permanent
- **NEVER auto-promote observations to invariants** — invariants must be explicitly declared
- **Taste preferences require 2+ observations** to reach `confirmed` confidence
- If a pattern contradicts an existing axiom, stop and ask the user
- If a pattern or decision violates an invariant, **block the upgrade** and flag for review
- If a new pattern matches a known entropy anti-pattern, **reject the pattern** and reference the Prevention Rule
- Keep pattern descriptions concrete and actionable, not vague platitudes
- Global axioms must be domain-agnostic; project-specific patterns stay local
- Always update `.last-reflection` timestamp after completion
- Always update memory layer distribution metrics after compaction
