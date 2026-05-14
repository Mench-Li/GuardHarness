#!/bin/bash
# check-invariants.sh
# 加载指定领域的架构不变量，输出规则列表供注入 skill 上下文
# 用法: bash .claude/scripts/check-invariants.sh <domain>

DOMAIN=${1:-general}
INVARIANTS_DIR=".claude/memory/invariants"

echo "=== Invariant Check for domain: $DOMAIN ==="
echo ""

if [ ! -d "$INVARIANTS_DIR" ]; then
    echo "No invariants directory found."
    exit 0
fi

# 加载 general 不变量（所有领域通用）
GENERAL_COUNT=0
for f in "$INVARIANTS_DIR"/general-*.md; do
    [ -e "$f" ] || continue
    GENERAL_COUNT=$((GENERAL_COUNT + 1))
    name=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^name:" | head -1 | sed 's/name: *//;s/["'"'"']//g' | xargs)
    rule=$(sed -n '/^## The Rule$/,/^## /p' "$f" | head -n -1 | tail -n +2 | sed 's/^[[:space:]]*//' | head -3)
    severity=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^violation_severity:" | sed 's/violation_severity: *//;s/["'"'"']//g' | xargs)
    echo "[$severity] $name"
    echo "$rule"
    echo ""
done

# 加载领域特定不变量
DOMAIN_COUNT=0
for f in "$INVARIANTS_DIR"/${DOMAIN}-*.md; do
    [ -e "$f" ] || continue
    # 跳过已经计数的 general 文件
    [[ $(basename "$f") == general-* ]] && continue
    DOMAIN_COUNT=$((DOMAIN_COUNT + 1))
    name=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^name:" | head -1 | sed 's/name: *//;s/["'"'"']//g' | xargs)
    rule=$(sed -n '/^## The Rule$/,/^## /p' "$f" | head -n -1 | tail -n +2 | sed 's/^[[:space:]]*//' | head -3)
    severity=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^violation_severity:" | sed 's/violation_severity: *//;s/["'"'"']//g' | xargs)
    echo "[$severity] $name"
    echo "$rule"
    echo ""
done

echo "Loaded $GENERAL_COUNT general invariants, $DOMAIN_COUNT domain invariants."
