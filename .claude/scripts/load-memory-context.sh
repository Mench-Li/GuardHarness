#!/bin/bash
# load-memory-context.sh
# 统一加载全部 5 层记忆 + 现有模式，按优先级排序
# 用法: bash .claude/scripts/load-memory-context.sh <skill-name> [domain]

SKILL=${1:-general}
DOMAIN=${2:-general}

echo "=== Loading Memory Context for: $SKILL (domain: $DOMAIN) ==="
echo ""

# 1. 不变量（宪法级规则 first）
if [ -d ".claude/memory/invariants" ]; then
    INVARIANT_COUNT=0
    for f in .claude/memory/invariants/general-*.md; do
        [ -e "$f" ] || continue
        INVARIANT_COUNT=$((INVARIANT_COUNT + 1))
    done
    if [ "$DOMAIN" != "general" ]; then
        for f in .claude/memory/invariants/${DOMAIN}-*.md; do
            [ -e "$f" ] || continue
            INVARIANT_COUNT=$((INVARIANT_COUNT + 1))
        done
    fi
    if [ "$INVARIANT_COUNT" -gt 0 ]; then
        echo "## Architectural Invariants ($INVARIANT_COUNT)"
        echo "These rules MUST NOT be violated under any circumstances."
        echo ""
        for f in .claude/memory/invariants/general-*.md; do
            [ -e "$f" ] || continue
            name=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^name:" | head -1 | sed 's/name: *//;s/["'"'"']//g' | xargs)
            rule=$(sed -n '/^## The Rule$/,/^## /p' "$f" | head -n -1 | tail -n +2 | sed 's/^[[:space:]]*//')
            severity=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^violation_severity:" | sed 's/violation_severity: *//;s/["'"'"']//g' | xargs)
            echo "### [$severity] $name"
            echo "$rule"
            echo ""
        done
        if [ "$DOMAIN" != "general" ]; then
            for f in .claude/memory/invariants/${DOMAIN}-*.md; do
                [ -e "$f" ] || continue
                name=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^name:" | head -1 | sed 's/name: *//;s/["'"'"']//g' | xargs)
                rule=$(sed -n '/^## The Rule$/,/^## /p' "$f" | head -n -1 | tail -n +2 | sed 's/^[[:space:]]*//')
                severity=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^violation_severity:" | sed 's/violation_severity: *//;s/["'"'"']//g' | xargs)
                echo "### [$severity] $name"
                echo "$rule"
                echo ""
            done
        fi
    fi
fi

# 2. 活跃决策
if [ -d ".claude/memory/decisions" ]; then
    DECISION_COUNT=$(find ".claude/memory/decisions" -name "*.md" -type f 2>/dev/null | wc -l | xargs)
    if [ "$DECISION_COUNT" -gt 0 ]; then
        echo "## Active Decisions ($DECISION_COUNT total)"
        echo "These decisions constrain the design space."
        echo ""
        find ".claude/memory/decisions" -name "*.md" -type f | while read -r f; do
            status=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^status:" | sed 's/status: *//;s/["'"'"']//g' | xargs)
            if [ "$status" = "active" ]; then
                title=$(grep "^# Decision:" "$f" | sed 's/# Decision: *//')
                echo "### $title"
                grep "^## 决策$" -A 5 "$f" 2>/dev/null | tail -n +2 | head -5
                echo ""
            fi
        done
    fi
fi

# 3. 相关失败教训
if [ -d ".claude/memory/failures" ]; then
    FAILURE_COUNT=$(find ".claude/memory/failures" -name "*.md" -type f 2>/dev/null | wc -l | xargs)
    if [ "$FAILURE_COUNT" -gt 0 ]; then
        echo "## Failure Lessons ($FAILURE_COUNT total)"
        echo "Learn from past incidents to avoid recurrence."
        echo ""
        find ".claude/memory/failures" -name "*.md" -type f | head -5 | while read -r f; do
            title=$(grep "^# Failure:" "$f" | sed 's/# Failure: *//')
            echo "### $title"
            grep "^## 我们学到了什么$" -A 5 "$f" 2>/dev/null | tail -n +2 | head -5
            echo ""
        done
    fi
fi

# 4. 熵模式（需要避免的）
if [ -d ".claude/memory/entropy" ]; then
    ENTROPY_COUNT=$(find ".claude/memory/entropy" -name "*.md" -type f 2>/dev/null | wc -l | xargs)
    if [ "$ENTROPY_COUNT" -gt 0 ]; then
        echo "## Entropy Patterns to Avoid ($ENTROPY_COUNT)"
        echo "These complexity anti-patterns have been observed before."
        echo ""
        find ".claude/memory/entropy" -name "*.md" -type f | while read -r f; do
            title=$(grep "^# Entropy Pattern:" "$f" | sed 's/# Entropy Pattern: *//')
            smell=$(grep "^## 臭味$" -A 3 "$f" 2>/dev/null | tail -n +2 | head -3)
            echo "### $title"
            echo "$smell"
            echo ""
        done
    fi
fi

# 5. 确认品味
if [ -d ".claude/memory/taste" ]; then
    TASTE_COUNT=$(find ".claude/memory/taste" -name "*.md" -type f 2>/dev/null | wc -l | xargs)
    CONFIRMED_COUNT=$(grep -l "confidence: confirmed" .claude/memory/taste/*.md 2>/dev/null | wc -l | xargs)
    if [ "$CONFIRMED_COUNT" -gt 0 ]; then
        echo "## Confirmed Taste Preferences ($CONFIRMED_COUNT)"
        echo "These preferences have been observed multiple times."
        echo ""
        grep -l "confidence: confirmed" .claude/memory/taste/*.md 2>/dev/null | while read -r f; do
            title=$(grep "^# Taste:" "$f" | sed 's/# Taste: *//')
            pref=$(grep "^## 偏好$" -A 3 "$f" 2>/dev/null | tail -n +2 | head -3)
            echo "### $title"
            echo "$pref"
            echo ""
        done
    fi
fi

# 6. 现有模式
if [ -d ".claude/memory/patterns" ]; then
    PATTERN_COUNT=$(find ".claude/memory/patterns" -name "*.md" -type f 2>/dev/null | wc -l | xargs)
    if [ "$PATTERN_COUNT" -gt 0 ]; then
        echo "## Established Patterns ($PATTERN_COUNT)"
        echo ""
        find ".claude/memory/patterns" -name "*.md" -type f | head -5 | while read -r f; do
            title=$(grep "^# " "$f" | head -1 | sed 's/^# *//')
            echo "### $title"
            grep "^## Pattern$" -A 3 "$f" 2>/dev/null | tail -n +2 | head -5
            echo ""
        done
    fi
fi

echo "=== End of Memory Context ==="
