#!/bin/bash
# detect-entropy.sh
# 检测近期代码变更中的复杂度/熵模式
# 用法: bash .claude/scripts/detect-entropy.sh [days]

DAYS=${1:-7}
ENTROPY_DIR=".claude/memory/entropy"
TMP_DIR=".claude/memory/.tmp"
mkdir -p "$ENTROPY_DIR" "$TMP_DIR"

echo "=== Entropy Detection Report ($(date +%Y-%m-%d)) ==="
echo "Analyzing last $DAYS days of changes"
echo ""

# 检查 git 是否可用
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Not a git repository. Skipping entropy detection."
    exit 0
fi

# 收集近期变更文件
CUTOFF=$(date -d "$DAYS days ago" +%Y-%m-%d 2>/dev/null || date -v-${DAYS}d +%Y-%m-%d)
CHANGED_FILES=$(git log --since="$CUTOFF" --name-only --pretty=format: -- . 2>/dev/null | grep -v '^$' | sort -u)

if [ -z "$CHANGED_FILES" ]; then
    echo "No changes found in the last $DAYS days."
    exit 0
fi

FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l)
echo "Found $FILE_COUNT changed files"
echo ""

# 启发式 1: Manager/Handler/Processor/Coordinator 泛滥
MANAGER_COUNT=$(echo "$CHANGED_FILES" | grep -iE "(manager|handler|processor|coordinator|service)" | wc -l | xargs)
UNIQUE_MANAGERS=$(echo "$CHANGED_FILES" | grep -iE "(manager|handler|processor|coordinator)" | sort -u | wc -l | xargs)

# 启发式 2: 新增抽象类/接口（推测性接口）
if [ "$UNIQUE_MANAGERS" -gt 2 ]; then
    echo "⚠️  manager-proliferation detected"
    echo "   Found $UNIQUE_MANAGERS unique manager/handler/processor/coordinator files"
    echo "   Indicators:"
    echo "$CHANGED_FILES" | grep -iE "(manager|handler|processor|coordinator)" | sed 's/^/     - /'
    echo ""
fi

# 启发式 3: 配置嵌套深度
CONFIG_FILES=$(echo "$CHANGED_FILES" | grep -iE "\.(json|yaml|yml|toml)$" || true)
if [ -n "$CONFIG_FILES" ]; then
    CONFIG_COUNT=$(echo "$CONFIG_FILES" | wc -l | xargs)
    echo "ℹ️  Config files changed: $CONFIG_COUNT"
    echo "$CONFIG_FILES" | head -5 | sed 's/^/     - /'
    if [ "$CONFIG_COUNT" -gt 5 ]; then
        echo "   ⚠️  High config churn detected — check for config-nesting entropy"
    fi
    echo ""
fi

# 启发式 4: 文件数量激增但平均行数下降（碎片化）
NEW_FILES=$(git log --since="$CUTOFF" --diff-filter=A --name-only --pretty=format: -- . 2>/dev/null | grep -v '^$' | sort -u)
if [ -n "$NEW_FILES" ]; then
    NEW_COUNT=$(echo "$NEW_FILES" | wc -l | xargs)
    if [ "$NEW_COUNT" -gt 10 ]; then
        echo "⚠️  abstraction-explosion indicator"
        echo "   $NEW_COUNT new files created in $DAYS days"
        echo "   Check if these are speculative abstractions (interfaces with one implementation)"
        echo ""
    fi
fi

# 启发式 5: 与现有熵模式对比
EXISTING=$(find "$ENTROPY_DIR" -name "*.md" -type f 2>/dev/null | wc -l | xargs)
if [ "$EXISTING" -gt 0 ]; then
    echo "Existing entropy patterns: $EXISTING"
    echo "Comparing against known patterns..."
    # 简单匹配：如果新文件路径包含已知熵模式的关键词
    find "$ENTROPY_DIR" -name "*.md" -type f | while read -r ef; do
        category=$(sed -n '/^---$/,/^---$/p' "$ef" | grep "^category:" | sed 's/category: *//;s/["'"'"']//g' | xargs)
        keywords=""
        case "$category" in
            manager-proliferation) keywords="manager|handler|processor|coordinator" ;;
            config-nesting) keywords="config|settings|yaml|json" ;;
            abstraction-explosion) keywords="abstract|interface|base|factory" ;;
            speculative-interface) keywords="interface|protocol|abstract" ;;
            indirection-creep) keywords="proxy|wrapper|adapter|delegate" ;;
        esac
        if [ -n "$keywords" ]; then
            matches=$(echo "$CHANGED_FILES" | grep -iE "$keywords" | wc -l | xargs)
            if [ "$matches" -gt 0 ]; then
                echo "   🔁 Matches existing entropy pattern: $category ($matches files)"
            fi
        fi
    done
    echo ""
fi

echo "=== End of Report ==="
