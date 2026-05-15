---
name: superpowers:writing-plans
description: Use when you have a written spec or requirements for a multi-step task, before touching code
triggers: ["plan", "writing-plans", "plan-feature"]
type: skill
version: "1.0"
---

# Writing Plans

## When to Use
After a spec is approved and you need to create an implementation plan.

## Constraints (from plan-schema.yaml)
- No TODOs, no placeholders
- Test-first: every task must have a test step
- Max step duration: 5 minutes
- Required sections: task_description, file_changes, test_plan, verification_command

## Steps

0. **Load Constraints & Team Standards**
   - Read `.harness/team/shared-axioms.md` for team-level axioms and principles
   - Read `.harness/team/standards.md` for coding, testing, and documentation standards
   - Read `.claude/memory/MEMORY.md` (if exists) as the index to locate relevant memories
   - **These constraints are implicit preconditions for all subsequent tasks.**

1. **Load historical plan memory**
   - Read `.claude/memory/observations/` for past plan deviations
   - Read `.claude/memory/decisions/` for **active decisions** that constrain implementation choices
   - Read `.claude/memory/entropy/` to avoid over-engineering in plan decomposition
   - Read `.claude/memory/invariants/` for **non-negotiable architectural constraints** that must be reflected in tasks
   - Read `.claude/memory/taste/` for confirmed human preferences on code organization
   - Check `CLAUDE.md` dynamic block `patterns` for file naming conventions
   - Check `CLAUDE.md` dynamic blocks: `invariants`, `decisions`, `taste`
   - Note any recurring estimation biases from past retros
   - **Respect invariants** — if a planned task would violate an invariant, redesign the task
   - **Metrics**: For each pattern loaded, increment its hit count in `.claude/memory/metrics/pattern-hit-rate.json` under `hits_by_skill.writing-plans`

2. **Map file structure**
   - List all files to create/modify/delete
   - Note exact paths
   - Follow established patterns from project memory

3. **Decompose into 2-5 minute tasks with verifiable success criteria**
   - Each step is one action
   - DRY, YAGNI, TDD, frequent commits
   - Account for known pitfalls from project memory
   - **Goal-Driven Execution**: Write each task description as a verifiable goal, not an imperative command
     - Instead of: "Add validation"
     - Use: "Goal: Reject invalid inputs. Verify: tests/test_api.py::test_invalid_input passes."
   - For multi-step sub-tasks: `[Step] → verify: [check]`
   - Reference `simplicity-first` invariant: each task should produce minimal, non-speculative code

4. **Write actual test code in plan steps**
   - Never write "write tests for the above"
   - Include exact assertions

5. **Include exact commands and expected output**
   - Run commands, expected pass/fail

6. **Self-review before saving**
   - No placeholders, no TBD
   - Type consistency across tasks
   - Cross-check with `plan-schema.yaml` constraints
   - Verify plan contains Mermaid/PlantUML state diagram
   - Verify each Task has Gate checkpoint annotations (G1-G5)

7. **Agent-Guard Gate check**
   - Run: `python .harness/agent-guard/cli.py plan TASK-xxx --approve`
   - Expected: G1 Plan Valid ✓, G2 Complexity Budget ✓
   - If G2 exceeds budget (files > 20 or steps > 15), perform semantic-aware splitting before retrying
   - State transitions: Inbox → Plan Ready

## Output Format
```markdown
# <Feature> Implementation Plan

## File Structure Map

## Tasks

### Task 1: <Component>

**Files:**
- Create: `path/to/file.py`
- Modify: `path/to/existing.py:10-20`
- Test: `tests/path/test.py`

- [ ] **Step 1: Write failing test**
  ```python
  def test_behavior():
      assert function(input) == expected
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/path/test.py::test_behavior -v`
  Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
  ```python
  def function(input):
      return expected
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/path/test.py::test_behavior -v`
  Expected: PASS

- [ ] **Step 5: Commit**
```
