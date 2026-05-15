---
name: superpowers:executing-plans
description: Use when implementing any feature or bugfix with a written plan
triggers: ["execute", "execute-plan", "implement"]
type: skill
version: "1.0"
---

# Executing Plans

## When to Use
When a plan exists and you need to implement it task-by-task.

## Execution Modes (Choose One)

**Mode A: Subagent-Driven (Recommended for independent tasks)**
- Fresh subagent per task + two-stage review (spec compliance → code quality)
- No human-in-loop between tasks, fastest iteration
- Use skill: `superpowers:subagent-driven-development`

**Mode B: Inline Execution (Current session)**
- Execute tasks step-by-step in this session
- Best for tightly-coupled tasks or when frequent human confirmation is needed
- Use skill: `superpowers:executing-plans` (this file)

**Mode C: Multi-Agent Parallel Claim**
- Multiple agents auto-claim different tasks from the same backlog simultaneously
- Each agent runs independently with its own Lease
- To use: omit task-id when running `execute` — Agent-Guard auto-claims next available Plan Ready task
- Works with either Mode A or B as the per-task execution strategy

**How to choose:**
- Single agent, tasks independent → Mode A
- Single agent, tasks coupled or need human check → Mode B
- Multiple agents available, backlog has many tasks → Mode C + (A or B)

## Steps

1. **Read the plan**
   - Load `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`
   - Understand all tasks before starting
   - Extract the `task_id` from the plan context (or ask user if ambiguous)

2. **State transition (Agent-Guard ticket check)**
   - **MUST** run `python .harness/agent-guard/cli.py execute <task-id>` before writing any code
   - This performs G3 Entropy Check, transitions state Plan Ready → Executing, and acquires Lease
   - If the task is already in Executing state with an active Lease, this step can be skipped
   - If transition fails (G3 blocked, wrong state, etc.), STOP and report to user — do not proceed

3. **Load execution memory** (Auto-loaded — no manual script execution needed)
   - Read `.harness/team/shared-axioms.md` for team-level axioms and principles
   - Read `.harness/team/standards.md` for coding, testing, and documentation standards
   - Read `.claude/memory/MEMORY.md` (if exists) as the index to locate relevant memories
   - Then read specific memory layers:
     - `.claude/memory/patterns/` — coding patterns and testing strategies
     - `.claude/memory/observations/` — common pitfalls (last 30 days)
     - `.claude/memory/failures/` — relevant incident lessons in this domain/component
     - `.claude/memory/entropy/` — complexity anti-patterns to avoid
     - `.claude/memory/taste/` — confirmed human style preferences
     - `.claude/memory/invariants/` — domain constraints that must never be violated
     - `.claude/memory/decisions/` — active design constraints in this area
   - Explicitly load `general-simplicity-first` and `general-surgical-changes` invariants
   - Review `CLAUDE.md` dynamic blocks: `common-pitfalls`, `invariants`, `decisions`, `taste`, `entropy`
   - **Pre-generation invariant check**: Before writing any code, verify your approach does not violate loaded invariants. If it does, STOP and redesign.
   - **Pre-generation entropy check**: Run `bash .claude/scripts/detect-entropy.sh` (or `.claude/scripts/detect-entropy.ps1` on Windows) to scan recent changes for complexity spikes. If entropy is elevated, flag it before proceeding.
   - **Metrics**: For each pattern loaded, increment its hit count in `.claude/memory/metrics/pattern-hit-rate.json` under `hits_by_skill.executing-plans`

4. **Execute tasks in order**
   - Follow each checkbox step exactly
   - Do not skip steps
   - Run verification commands after each implementation step

4. **Checkpoint after each task — MANDATORY**
   - Run full test suite for affected area
   - Commit before moving to next task
   - **MUST update Agent-Guard progress**: Run `python .harness/agent-guard/cli.py progress TASK-xxx --step N --status done --evidence "tests passing, commit SHA"`
     - **This is NOT optional.** If progress is not updated, the snapshot will lie about task state.
     - Do NOT batch multiple steps into a single progress update.
   - If starting a new task, mark it in_progress: `python .harness/agent-guard/cli.py progress TASK-xxx --step N --status in_progress`
     - Note: `execute` command already auto-marks step 1 as in_progress. Only needed for subsequent steps.

5. **Handle blockers**
   - If a step cannot be completed as written, stop and report
   - Do not invent alternative approaches without approval
   - If you encounter a new pitfall, note it for future observation

6. **Update plan if needed**
   - If reality diverges from plan, update the plan file to reflect actual changes

7. **State transition: patch (MANDATORY)**
   - After ALL tasks are complete, run `python .harness/agent-guard/cli.py patch TASK-xxx`
   - This triggers G4 Surgical Check (diff 范围审查) and transitions Executing → Patch Ready
   - If G4 fails (修改了计划外文件), STOP and revert extraneous changes before retrying
   - **Do NOT skip this step.** Snapshot 不会自动进入 Patch Ready。

8. **State transition: review (MANDATORY)**
   - After patch succeeds, run `python .harness/agent-guard/cli.py review TASK-xxx`
   - This transitions Patch Ready → Entropy Review
   - If review fails, fix issues and re-run `review`
   - **Do NOT skip this step.**

9. **State transition: finish (G5 Verification Proof)**
   - Run `python .harness/agent-guard/cli.py finish TASK-xxx`
   - This triggers G5 Verification Proof（运行验证命令并确认通过）并转换 Entropy Review → Done
   - G5 runs inside the worktree sandbox if one exists

## Rules
- One task at a time
- Commit after every task
- Tests must pass before next task
- No speculative changes beyond the plan
- **Surgical Changes** (invariant: `general-surgical-changes`):
  - Do not modify files not listed in the current task's `file_changes`
  - Do not restructure, refactor, or improve adjacent code outside the task scope
  - Do not change formatting, comments, or style of code you are not directly modifying
  - Match existing style of the file you are editing
  - If you remove code, only remove imports/variables/functions that your changes made unused
- **Simplicity First** (invariant: `general-simplicity-first`):
  - Minimum code that solves the problem. Nothing speculative.
  - No features beyond what the task requests
  - No abstractions for single-use code
