---
name: superpowers:test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code
triggers: ["tdd", "test-first", "red-green-refactor"]
type: skill
version: "1.0"
---

# Test-Driven Development

## The Law
No failing test, no production code.

## The Cycle

### RED
- Write a failing test that describes one behavior
- Run it, confirm it fails for the right reason

### GREEN
- Write the minimal production code to make the test pass
- Run it, confirm it passes
- No more code than necessary

### REFACTOR
- Clean up the code while keeping tests green
- Run tests after each change

### NEXT
- Write the next failing test

## Memory Integration

Before starting implementation:
- Read `.harness/team/shared-axioms.md` for team-level principles
- Read `.harness/team/standards.md` for testing and coding standards
- Read `.claude/memory/MEMORY.md` (if exists) as the index to locate relevant memories
- Load `.claude/memory/invariants/` for domain-specific constraints
- Ensure test plan validates **invariants**, not just functional correctness
- If a test would require violating an invariant, redesign the test and implementation

After completing a feature or bugfix using TDD:
- Note any unexpected test behavior or edge cases discovered
- If the fix resolves a recurring issue, flag it for `.claude/memory/observations/`
- Reference `CLAUDE.md` dynamic blocks `common-pitfalls`, `invariants` when similar issues arise

### Auto-observation on Test Failure

When a test fails during development:
1. Capture the test output and failing file names
2. Run: `bash .claude/scripts/auto-observe.sh test-failure`
3. This generates a structured observation template in `.claude/memory/observations/`
4. Fill in the manual sections (root cause, fix approach) after investigation
5. If the failure reveals a systemic issue, also write to `.claude/memory/failures/`

## Rules
- One behavior at a time
- Tests must fail before implementation exists
- Tests must pass before refactoring
- Commit after each green phase
