---
name: superpowers:subagent-driven-development
description: Use when executing implementation plans with independent tasks in the current session
triggers: ["subagent", "implement", "execute-plan", "development"]
type: skill
version: "1.0"
---

# Subagent-Driven Development

Execute plan by dispatching fresh subagent per task, with two-stage review after each: spec compliance review first, then code quality review.

**Why subagents:** You delegate tasks to specialized agents with isolated context. By precisely crafting their instructions and context, you ensure they stay focused and succeed at their task. They should never inherit your session's context or history — you construct exactly what they need. This also preserves your own context for coordination work.

**Core principle:** Fresh subagent per task + two-stage review (spec then quality) = high quality, fast iteration

## When to Use

**Use when:**
- Have implementation plan with independent tasks
- Staying in same session
- Want fast iteration without human-in-loop between tasks

**vs. Executing Plans (inline session):**
- Same session (no context switch)
- Fresh subagent per task (no context pollution)
- Two-stage review after each task: spec compliance first, then code quality
- Faster iteration (no human-in-loop between tasks)

## Execution Modes (Choose One)

**Mode A: Subagent-Driven (This skill — Recommended for independent tasks)**
- Fresh subagent per task + two-stage review
- No human-in-loop between tasks
- Use: load this skill (`superpowers:subagent-driven-development`)

**Mode B: Inline Execution**
- Execute tasks step-by-step in current session
- Best for tightly-coupled tasks or frequent human confirmation
- Use skill: `superpowers:executing-plans`

**Mode C: Multi-Agent Parallel Claim**
- Multiple agents auto-claim different tasks from the same backlog simultaneously
- Each agent runs independently with its own Lease
- To use: omit task-id when running `execute` — Agent-Guard auto-claims next available Plan Ready task
- Combine with Mode A (this skill) or Mode B as the per-task execution strategy

**How to choose:**
- Single agent, tasks independent → Mode A
- Single agent, tasks coupled or need human check → Mode B
- Multiple agents available, backlog has many tasks → Mode C + (A or B)

## The Process

### Per Task Loop

1. **Dispatch implementer subagent** (./implementer-prompt.md)
2. Implementer asks questions? → Answer, provide context → Re-dispatch
3. Implementer implements, tests, commits, self-reviews
4. **Parent agent MUST update progress** (before any review)
   - Run `python .harness/agent-guard/cli.py progress TASK-xxx --step N --status done --evidence "commit SHA, tests passing"`
   - **This is NOT optional.** If the implementer returned DONE, progress MUST be updated before proceeding to review.
   - Do NOT proceed to review if progress update fails.
5. **Dispatch spec reviewer subagent** (./spec-reviewer-prompt.md)
6. Spec reviewer confirms code matches spec?
   - No → Implementer fixes spec gaps → Re-review
   - Yes → Proceed
7. **Dispatch code quality reviewer subagent** (./code-quality-reviewer-prompt.md)
8. Code quality reviewer approves?
   - No → Implementer fixes quality issues → Re-review
   - Yes → Mark task complete in TodoWrite
   - **Update Agent-Guard progress** (re-run with final evidence if changed)

### Overall Flow

1. **Agent-Guard state transition (MUST)**
   - Extract `task_id` from the plan (or ask user)
   - Run `python .harness/agent-guard/cli.py execute <task-id>` before any code is written
   - This performs G3 Entropy Check, transitions state Plan Ready → Executing, and acquires Lease
   - If transition fails, STOP and report — do not dispatch any subagents

2. **Load execution memory** (Auto-loaded — no manual script execution needed)
   - Read `.harness/team/shared-axioms.md` for team-level axioms and principles
   - Read `.harness/team/standards.md` for coding, testing, and documentation standards
   - Read `.claude/memory/MEMORY.md` (if exists) as the index to locate relevant memories
   - Then read specific memory layers:
     - `.claude/memory/invariants/` (highest priority), `.claude/memory/decisions/`, `.claude/memory/failures/`, `.claude/memory/entropy/`, `.claude/memory/taste/`, `.claude/memory/patterns/`
   - Review `CLAUDE.md` dynamic blocks for constraints
   - Subagents receive loaded memory context in their prompts; they do not need to run `load-memory-context` scripts manually

3. Read plan, extract all tasks with full text, note context, create TodoWrite
4. For each task: run per-task loop above
   - `execute` command auto-marks step 1 as `in_progress`
   - After implementer DONE: parent agent **must** update progress before review
5. After all tasks: dispatch final code reviewer for entire implementation
6. **State transition: patch (MANDATORY)**
   - Run `python .harness/agent-guard/cli.py patch TASK-xxx`
   - Triggers G4 Surgical Check (diff 范围审查) and transitions Executing → Patch Ready
   - If G4 fails (修改了计划外文件), STOP and revert extraneous changes before retrying
   - **Do NOT skip this step.** Snapshot 不会自动进入 Patch Ready。
7. **State transition: review (MANDATORY)**
   - Run `python .harness/agent-guard/cli.py review TASK-xxx`
   - Triggers G5 Verification Proof（运行验证命令并确认通过）并转换 Patch Ready → Entropy Review
   - If review fails, fix issues and re-run `review`
   - **Do NOT skip this step.**
8. Use superpowers:finishing-a-development-branch (calls `finish TASK-xxx` to reach Done)

## Model Selection

Use the least powerful model that can handle each role to conserve cost and increase speed.

**Mechanical implementation tasks** (isolated functions, clear specs, 1-2 files): use a fast, cheap model.

**Integration and judgment tasks** (multi-file coordination, pattern matching, debugging): use a standard model.

**Architecture, design, and review tasks**: use the most capable available model.

## Handling Implementer Status

Implementer subagents report one of four statuses. Handle each appropriately:

**DONE:** Proceed to spec compliance review.

**DONE_WITH_CONCERNS:** The implementer completed the work but flagged doubts. Read the concerns before proceeding. If the concerns are about correctness or scope, address them before review. If they're observations (e.g., "this file is getting large"), note them and proceed to review.

**NEEDS_CONTEXT:** The implementer needs information that wasn't provided. Provide the missing context and re-dispatch.

**BLOCKED:** The implementer cannot complete the task. Assess the blocker:
1. If it's a context problem, provide more context and re-dispatch with the same model
2. If the task requires more reasoning, re-dispatch with a more capable model
3. If the task is too large, break it into smaller pieces
4. If the plan itself is wrong, escalate to the human

**Never** ignore an escalation or force the same model to retry without changes. If the implementer said it's stuck, something needs to change.

## Example Workflow

```
You: I'm using Subagent-Driven Development to execute this plan.

[Read plan file once: docs/superpowers/plans/feature-plan.md]
[Extract all 5 tasks with full text and context]
[Create TodoWrite with all tasks]

Task 1: Hook installation script

[Get Task 1 text and context (already extracted)]
[Dispatch implementation subagent with full task text + context]

Implementer: "Before I begin - should the hook be installed at user or system level?"

You: "User level (~/.config/superpowers/hooks/)"

Implementer: "Got it. Implementing now..."
[Later] Implementer:
  - Implemented install-hook command
  - Added tests, 5/5 passing
  - Self-review: Found I missed --force flag, added it
  - Committed

[Dispatch spec compliance reviewer]
Spec reviewer: Spec compliant - all requirements met, nothing extra

[Get git SHAs, dispatch code quality reviewer]
Code reviewer: Strengths: Good test coverage, clean. Issues: None. Approved.

[Mark Task 1 complete]

Task 2: Recovery modes
...
```

## Red Flags

**Never:**
- Start implementation on main/master branch without explicit user consent
- Skip reviews (spec compliance OR code quality)
- Proceed with unfixed issues
- Dispatch multiple implementation subagents in parallel (conflicts)
- Make subagent read plan file (provide full text instead)
- Skip scene-setting context (subagent needs to understand where task fits)
- Ignore subagent questions (answer before letting them proceed)
- Accept "close enough" on spec compliance (spec reviewer found issues = not done)
- Skip review loops (reviewer found issues = implementer fixes = review again)
- Let implementer self-review replace actual review (both are needed)
- **Start code quality review before spec compliance is passing** (wrong order)
- **Skip progress updates** (implementer DONE → MUST update progress before review)
- Move to next task while either review has open issues

## Integration

**Required workflow skills:**
- **superpowers:using-git-worktrees** - REQUIRED: Set up isolated workspace before starting
- **superpowers:writing-plans** - Creates the plan this skill executes
- **superpowers:requesting-code-review** - Code review template for reviewer subagents
- **superpowers:finishing-a-development-branch** - Complete development after all tasks

**Subagents should use:**
- **superpowers:test-driven-development** - Subagents follow TDD for each task

**Alternative workflow:**
- **superpowers:executing-plans** - Use for parallel session instead of same-session execution
