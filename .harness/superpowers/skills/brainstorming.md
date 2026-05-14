---
name: superpowers:brainstorming
description: Use before any creative work or feature implementation
triggers: ["brainstorm", "design", "plan", "idea", "init-feature"]
type: skill
version: "1.0"
---

# Brainstorming Workflow

## When to Use
Before implementing any feature, creating any component, or modifying existing behavior.

## Steps

1. **Load Constraints & Team Standards**
   - Read `.harness/team/shared-axioms.md` for team-level axioms and principles
   - Read `.harness/team/standards.md` for coding, testing, and documentation standards
   - Read `.claude/memory/MEMORY.md` (if exists) as the index to locate relevant memories
   - **These constraints bound the design space — respect them before exploring.**

2. **Explore project context**
   - Check files, docs, recent commits
   - Understand current architecture

3. **Load project memory**
   - Read `.claude/memory/patterns/` for established patterns
   - Read `.claude/memory/observations/` for recent lessons (last 30 days)
   - Read `.claude/memory/decisions/` for **active decisions** that constrain design space
   - Read `.claude/memory/failures/` for relevant incident lessons in this domain
   - Read `.claude/memory/invariants/` for **non-negotiable architectural rules**
   - Read `.claude/memory/taste/` for confirmed human coding preferences
   - Review `CLAUDE.md` dynamic blocks: `recent-decisions`, `common-pitfalls`, `patterns`, `invariants`, `taste`
   - Incorporate relevant patterns into design rationale
   - **Respect invariants first** — if your design violates an invariant, redesign before proposing
   - **Metrics**: For each pattern loaded, increment its hit count in `.claude/memory/metrics/pattern-hit-rate.json` under `hits_by_skill.brainstorming`

3. **Expose Assumptions (Think Before Coding)**
   - Before proposing any design, list all implicit assumptions you are making about the user's request
   - Present multiple interpretations when ambiguity exists ("This could mean X, Y, or Z — which do you intend?")
   - Flag areas where the simplest approach might be sufficient
   - **Push back** if the request seems overcomplicated for the stated goal — propose a simpler alternative
   - Stop when confused: name what's unclear and ask for clarification rather than guessing

4. **Ask clarifying questions one at a time**
   - Understand purpose/constraints/success criteria
   - Prefer multiple choice when possible

5. **Propose 2-3 approaches with trade-offs**
   - Present options conversationally
   - **Explicitly mark which option is the simplest** and why
   - Lead with your recommendation and reasoning
   - Reference historical patterns if they inform the decision
   - If one approach violates `simplicity-first` or `surgical-changes` invariants, flag it as non-compliant

6. **Present design sections and get approval**
   - Architecture, components, data flow
   - Error handling, testing
   - Ask after each section

7. **Write design doc**
   - Save to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`

8. **Spec self-review**
   - Scan for TBD, TODO, contradictions, ambiguity
   - Check against `simplicity-first` invariant: is this the minimum design that solves the problem?
   - Fix inline

9. **Initialize Agent-Guard ticket**
   - Run: `python .harness/agent-guard/cli.py init TASK-xxx --spec docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
   - 创建任务并关联已保存的 spec 文件
   - 状态机进入 `Inbox`

10. **User reviews spec**
    - Wait for approval before proceeding

## Output Format
```markdown
---
name: <feature-name>
description: <one-line description>
type: spec
---

# <Feature Name> Design

## Overview

## Architecture

## Components

## Data Flow

## Error Handling

## Testing Strategy

## Open Questions
```
