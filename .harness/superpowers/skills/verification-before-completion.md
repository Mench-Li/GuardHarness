---
name: superpowers:verification-before-completion
description: Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims
triggers: ["verify", "complete", "done", "pass", "test"]
type: skill
version: "1.0"
---

# Verification Before Completion

## Overview

Claiming work is complete without verification is dishonesty, not efficiency.

**Core principle:** Evidence before claims, always.

**Violating the letter of this rule is violating the spirit of this rule.**

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If you haven't run the verification command in this message, you cannot claim it passes.

## The Gate Function

```
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim

Skip any step = lying, not verifying
```

## Common Failures

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test command output: 0 failures | Previous run, "should pass" |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing, logs look good |
| Bug fixed | Test original symptom: passes | Code changed, assumed fixed |
| Regression test works | Red-green cycle verified | Test passes once |
| Agent completed | VCS diff shows changes | Agent reports "success" |
| Requirements met | Line-by-line checklist | Tests passing |

## Red Flags - STOP

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!", etc.)
- About to commit/push/PR without verification
- Trusting agent success reports
- Relying on partial verification
- Thinking "just this once"
- Tired and wanting work over
- **ANY wording implying success without having run verification**

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Linter passed" | Linter ≠ compiler |
| "Agent said success" | Verify independently |
| "I'm tired" | Exhaustion ≠ excuse |
| "Partial check is enough" | Partial proves nothing |
| "Different words so rule doesn't apply" | Spirit over letter |

## Key Patterns

**Tests:**
```
[Run test command] [See: 34/34 pass] "All tests pass"
"Should pass now" / "Looks correct" ← WRONG
```

**Regression tests (TDD Red-Green):**
```
Write → Run (pass) → Revert fix → Run (MUST FAIL) → Restore → Run (pass)
"I've written a regression test" (without red-green verification) ← WRONG
```

**Build:**
```
[Run build] [See: exit 0] "Build passes"
"Linter passed" (linter doesn't check compilation) ← WRONG
```

**Requirements:**
```
Re-read plan → Create checklist → Verify each → Report gaps or completion
"Tests pass, phase complete" ← WRONG
```

**Agent delegation:**
```
Agent reports success → Check VCS diff → Verify changes → Report actual state
Trust agent report ← WRONG
```

## When To Apply

**ALWAYS before:**
- ANY variation of success/completion claims
- ANY expression of satisfaction
- ANY positive statement about work state
- Committing, PR creation, task completion
- Moving to next task
- Delegating to agents

## Diff Review for Surgical Changes

Before claiming completion, review the VCS diff to enforce **surgical changes**:

```
BEFORE claiming DONE:

1. RUN: git diff (or equivalent)
2. CHECK:
   - Only planned files modified?
   - No adjacent code refactored, reformatted, or "improved"?
   - No comments/docstrings changed unless directly related?
   - No imports/variables removed that your changes didn't make unused?
   - Diff is minimal and focused?
3. IF unrelated changes present → REVERT them
4. ONLY THEN → claim completion
```

**Red flags in diff review:**
- File modified that wasn't in the task scope
- Formatting-only changes (quote style, indentation, line breaks)
- Variable renames in unrelated functions
- "Improved" comments or docstrings outside task scope
- Deleted "unused" code you didn't make unused

**Excuse vs Reality:**
| Excuse | Reality |
|--------|---------|
| "I was just cleaning up" | Revert it. Cleanup is its own task. |
| "It was a small improvement" | Revert it. Small improvements belong in separate commits. |
| "The linter complained" | Only fix linter issues in files you directly modified. |
| "It made the code better" | Revert it. "Better" is subjective and unreviewed. |

## The Bottom Line

**No shortcuts for verification. No drive-by refactoring. No excuses.**

Run the command. Read the output. Review the diff. THEN claim the result.

This is non-negotiable.
