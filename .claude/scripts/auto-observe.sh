#!/bin/bash
# Auto-observation generator for Memory × Harness
# Generates structured observations from various development artifacts
# Usage: auto-observe.sh [commit-summary|test-failure|lint-failure|review-feedback]

# Note: removed 'set -e' for better error visibility in Windows PowerShell + bash

MODE=${1:-commit-summary}
OBS_DIR=".claude/memory/observations"
mkdir -p "$OBS_DIR"

TIMESTAMP=$(date +%Y-%m-%d-%H%M%S 2>/dev/null || date +%Y%m%d%H%M%S 2>/dev/null || echo "unknown")
DATE=$(date +%Y-%m-%d 2>/dev/null || echo "unknown")

echo "[auto-observe] Starting mode: $MODE"

generate_frontmatter() {
    local type=$1
    local tags=$2
    local compact=$3
    local compact_line=""
    if [ "$compact" = "true" ]; then
        compact_line="needs_compaction: true"
    fi
    cat >> "$OUTPUT_FILE" <<EOF
---
date: $DATE
type: $type
generated_by: auto-observe
mode: $MODE
tags: [$tags]
$compact_line
---

EOF
}

# Helper: extract decision keywords from commit message or spec
extract_decision_context() {
    local msg="$1"
    if echo "$msg" | grep -qiE "(decide|decision|choose|opt for|select|prefer|avoid|instead of|rather than)"; then
        echo "true"
    else
        echo "false"
    fi
}

# Helper: detect entropy indicators in changed files
detect_entropy_indicators() {
    local files="$1"
    local entropy_flags=""
    local manager_count=$(echo "$files" | grep -iEc "(manager|handler|processor|coordinator)" || echo "0")
    local interface_count=$(echo "$files" | grep -iEc "(interface|abstract|protocol|base)" || echo "0")
    local config_count=$(echo "$files" | grep -iEc "\.(json|yaml|yml|toml)$" || echo "0")

    if [ "$manager_count" -gt 2 ]; then
        entropy_flags="$entropy_flags, manager-proliferation($manager_count)"
    fi
    if [ "$interface_count" -gt 2 ]; then
        entropy_flags="$entropy_flags, abstraction-explosion($interface_count)"
    fi
    if [ "$config_count" -gt 3 ]; then
        entropy_flags="$entropy_flags, config-nesting($config_count)"
    fi

    echo "$entropy_flags" | sed 's/^, *//'
}

# Mode 1: Analyze recent commits for change patterns
mode_commit_summary() {
    OUTPUT_FILE="$OBS_DIR/${DATE}-commit-summary-${TIMESTAMP}.md"
    echo "[auto-observe] Generating commit-summary observation..."

    # Get last commit message and changed files (scoped to current directory only)
    LAST_COMMIT_MSG=$(git log -1 --pretty=format:"%s" 2>/dev/null || echo "No commits")
    # Use HEAD~1..HEAD to diff between commits, not working tree
    CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD -- . 2>/dev/null || echo "")
    FILE_COUNT=$(echo "$CHANGED_FILES" | grep -v "^$" | wc -l)

    # Detect change patterns
    DOCS_CHANGED=$(echo "$CHANGED_FILES" | grep -c "\.md$\|docs/" || true)
    TESTS_CHANGED=$(echo "$CHANGED_FILES" | grep -c "test\|spec" || true)
    CONFIG_CHANGED=$(echo "$CHANGED_FILES" | grep -c "\.json$\|\.yaml$\|\.toml$\|config" || true)

    # Size guard: if too many files, truncate and mark for compaction
    NEEDS_COMPACTION="false"
    FILE_LIST="$CHANGED_FILES"
    if [ "$FILE_COUNT" -gt 20 ]; then
        NEEDS_COMPACTION="true"
        TRUNCATED=$(echo "$CHANGED_FILES" | grep -v "^$" | head -20)
        REMAINING=$((FILE_COUNT - 20))
        FILE_LIST="${TRUNCATED}
... and ${REMAINING} more files"
    fi

    generate_frontmatter "commit-summary" "git,automation" "$NEEDS_COMPACTION"

    cat >> "$OUTPUT_FILE" <<EOF
## Commit Summary
- Message: $LAST_COMMIT_MSG
- Files changed: $FILE_COUNT

## Change Pattern Analysis
EOF

    if [ "$DOCS_CHANGED" -gt 0 ]; then
        echo "- Documentation updated alongside code changes" >> "$OUTPUT_FILE"
    fi
    if [ "$TESTS_CHANGED" -gt 0 ]; then
        echo "- Tests updated/modified in this commit" >> "$OUTPUT_FILE"
    else
        echo "- No test files changed (potential gap)" >> "$OUTPUT_FILE"
    fi
    if [ "$CONFIG_CHANGED" -gt 0 ]; then
        echo "- Configuration files modified" >> "$OUTPUT_FILE"
    fi

    cat >> "$OUTPUT_FILE" <<EOF

## File Breakdown
\`\`\`
$FILE_LIST
\`\`\`

## Pattern Notes
- [Auto-generated] Review if this commit introduces a reusable pattern
- [Auto-generated] Check if commit scope aligns with plan task boundaries
EOF

    echo "[auto-observe] Generated: $OUTPUT_FILE"
}

# Mode 2: Analyze test failures
mode_test_failure() {
    OUTPUT_FILE="$OBS_DIR/${DATE}-test-failure-${TIMESTAMP}.md"
    echo "[auto-observe] Generating test-failure observation..."

    # Try to find pytest output or recent test results
    TEST_OUTPUT=""
    if [ -f ".pytest_cache/v/cache/nodeids" ]; then
        TEST_OUTPUT="pytest cache exists"
    fi

    # Get recent git changes scoped to current directory
    RECENT_FILES=$(git diff --name-only HEAD~1 HEAD -- . 2>/dev/null || echo "unknown")

    generate_frontmatter "test-failure" "testing,automation"

    cat >> "$OUTPUT_FILE" <<EOF
## Test Failure Context
- Trigger: Automated detection after test run
- Recent changes:
\`\`\`
$RECENT_FILES
\`\`\`

## Potential Patterns
- [Auto-generated] Check if failure is in same area as recent changes
- [Auto-generated] Note if this is a recurring test failure pattern

## Manual Input Required
> Please review this observation and add:
> - Actual error message/output
> - Root cause analysis
> - Fix approach
EOF

    echo "[auto-observe] Generated: $OUTPUT_FILE"
}

# Mode 3: Analyze lint failures
mode_lint_failure() {
    OUTPUT_FILE="$OBS_DIR/${DATE}-lint-failure-${TIMESTAMP}.md"
    echo "[auto-observe] Generating lint-failure observation..."

    RECENT_FILES=$(git diff --name-only HEAD~1 HEAD -- . 2>/dev/null || echo "unknown")

    generate_frontmatter "lint-failure" "quality,automation"

    cat >> "$OUTPUT_FILE" <<EOF
## Lint/Quality Failure Context
- Trigger: Automated detection after lint run
- Recent changes:
\`\`\`
$RECENT_FILES
\`\`\`

## Potential Patterns
- [Auto-generated] Check if same lint rule is repeatedly violated
- [Auto-generated] Note if new files consistently miss lint standards

## Manual Input Required
> Please review this observation and add:
> - Specific lint errors
> - Whether pre-commit hooks could prevent this
EOF

    echo "[auto-observe] Generated: $OUTPUT_FILE"
}

# Mode 4: Review feedback analysis
mode_review_feedback() {
    OUTPUT_FILE="$OBS_DIR/${DATE}-review-feedback-${TIMESTAMP}.md"
    echo "[auto-observe] Generating review-feedback observation..."

    generate_frontmatter "code-review" "review,automation"

    cat >> "$OUTPUT_FILE" <<EOF
## Code Review Feedback
- Trigger: Post-review automated capture

## Capture Template
> Please fill in after review:
> - Review focus areas
> - Recurring issues flagged
> - Positive patterns noted
> - Suggestions for process improvement
EOF

    echo "[auto-observe] Generated: $OUTPUT_FILE"
}

# Mode 5: Decision capture (from commit messages or spec files)
mode_decision() {
    OUTPUT_FILE="$OBS_DIR/${DATE}-decision-${TIMESTAMP}.md"
    echo "[auto-observe] Generating decision observation..."

    LAST_COMMIT_MSG=$(git log -1 --pretty=format:"%s" 2>/dev/null || echo "No commits")

    generate_frontmatter "decision" "architecture,decision"

    cat >> "$OUTPUT_FILE" <<EOF
## Decision Context
- Commit: $LAST_COMMIT_MSG

## Options Considered
> [Auto-generated] Please fill in:
> - What options were considered?
> - What constraints existed?

## Decision
> [Auto-generated] What was chosen?

## Rationale
> [Auto-generated] Why was this option chosen over alternatives?

## Consequences
> [Auto-generated] What are the positive/negative consequences?
EOF

    echo "[auto-observe] Generated: $OUTPUT_FILE"
}

# Mode 6: Entropy detection
mode_entropy() {
    OUTPUT_FILE="$OBS_DIR/${DATE}-entropy-${TIMESTAMP}.md"
    echo "[auto-observe] Generating entropy observation..."

    RECENT_FILES=$(git log --since="7 days ago" --name-only --pretty=format: -- . 2>/dev/null | grep -v '^$' | sort -u)
    ENTROPY_FLAGS=$(detect_entropy_indicators "$RECENT_FILES")

    generate_frontmatter "entropy" "complexity,refactoring"

    cat >> "$OUTPUT_FILE" <<EOF
## Entropy Detection
- Trigger: Automated complexity analysis
- Period: Last 7 days

## Detected Indicators
EOF

    if [ -n "$ENTROPY_FLAGS" ]; then
        echo "- $ENTROPY_FLAGS" >> "$OUTPUT_FILE"
    else
        echo "- No significant entropy indicators detected" >> "$OUTPUT_FILE"
    fi

    cat >> "$OUTPUT_FILE" <<EOF

## The Smell
> [Auto-generated] What complexity pattern was introduced?

## Before / After
> [Auto-generated] Provide code examples if applicable

## Prevention Rule
> [Auto-generated] How to avoid this pattern in the future?
EOF

    echo "[auto-observe] Generated: $OUTPUT_FILE"
}

# Mode 7: Taste preference capture (from review corrections)
mode_taste() {
    OUTPUT_FILE="$OBS_DIR/${DATE}-taste-${TIMESTAMP}.md"
    echo "[auto-observe] Generating taste observation..."

    generate_frontmatter "taste" "style,review"

    cat >> "$OUTPUT_FILE" <<EOF
## Taste Preference
- Trigger: Human correction or code review feedback

## The Preference
> [Auto-generated] What style preference was expressed?

## Source Context
> [Auto-generated] Where did this preference come from?
> - PR comment
> - Direct human correction
> - Explicit statement

## Examples
### Preferred
```
> [Auto-generated] Fill in preferred style
```

### Dispreferred
```
> [Auto-generated] Fill in dispreferred style
```

## When It Applies
> [Auto-generated] Always? Only in certain contexts?
EOF

    echo "[auto-observe] Generated: $OUTPUT_FILE"
}

# Main dispatch
case "$MODE" in
    commit-summary)
        mode_commit_summary
        ;;
    test-failure)
        mode_test_failure
        ;;
    lint-failure)
        mode_lint_failure
        ;;
    review-feedback)
        mode_review_feedback
        ;;
    decision)
        mode_decision
        ;;
    entropy)
        mode_entropy
        ;;
    taste)
        mode_taste
        ;;
    *)
        echo "[auto-observe] Usage: $0 [commit-summary|test-failure|lint-failure|review-feedback|decision|entropy|taste]"
        exit 1
        ;;
esac

echo "[auto-observe] Done."
