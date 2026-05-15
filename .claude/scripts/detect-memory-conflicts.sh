#!/bin/bash
# detect-memory-conflicts.sh
# 检测项目级 patterns 与全局级 axioms 之间的潜在冲突
# 用法: bash .claude/scripts/detect-memory-conflicts.sh

PATTERNS_DIR=".claude/memory/patterns"
INVARIANTS_DIR=".claude/memory/invariants"
DECISIONS_DIR=".claude/memory/decisions"
TASTE_DIR=".claude/memory/taste"
ENTROPY_DIR=".claude/memory/entropy"
AXIOMS_FILE=".claude/memory/user/axioms.md"
TMP_DIR=".claude/memory/.tmp"
mkdir -p "$TMP_DIR"

echo "=== Memory Conflict Detection Report ($(date +%Y-%m-%d)) ==="
echo ""

# 收集所有记忆层
PATTERN_FILES=$(find "$PATTERNS_DIR" -name "*.md" -type f 2>/dev/null | sort)
PATTERN_COUNT=$(find "$PATTERNS_DIR" -name "*.md" -type f 2>/dev/null | wc -l)

INVARIANT_FILES=$(find "$INVARIANTS_DIR" -name "*.md" -type f 2>/dev/null | sort)
INVARIANT_COUNT=$(find "$INVARIANTS_DIR" -name "*.md" -type f 2>/dev/null | wc -l)

DECISION_FILES=$(find "$DECISIONS_DIR" -name "*.md" -type f 2>/dev/null | sort)
DECISION_COUNT=$(find "$DECISIONS_DIR" -name "*.md" -type f 2>/dev/null | wc -l)

TASTE_FILES=$(find "$TASTE_DIR" -name "*.md" -type f 2>/dev/null | sort)
TASTE_COUNT=$(find "$TASTE_DIR" -name "*.md" -type f 2>/dev/null | wc -l)

ENTROPY_FILES=$(find "$ENTROPY_DIR" -name "*.md" -type f 2>/dev/null | sort)
ENTROPY_COUNT=$(find "$ENTROPY_DIR" -name "*.md" -type f 2>/dev/null | wc -l)

# 收集 axioms
if [ -f "$AXIOMS_FILE" ]; then
    AXIOM_COUNT=$(grep -c "^## " "$AXIOMS_FILE" || echo "0")
else
    AXIOM_COUNT=0
fi

echo "Patterns scanned: $PATTERN_COUNT"
echo "Invariants scanned: $INVARIANT_COUNT"
echo "Decisions scanned: $DECISION_COUNT"
echo "Taste scanned: $TASTE_COUNT"
echo "Entropy scanned: $ENTROPY_COUNT"
echo "Axioms scanned: $AXIOM_COUNT"
echo ""

if [ "$PATTERN_COUNT" -eq 0 ] && [ "$AXIOM_COUNT" -eq 0 ] && [ "$INVARIANT_COUNT" -eq 0 ]; then
    echo "No patterns, axioms, or invariants found. Nothing to check."
    exit 0
fi

# 提取每个 pattern/axiom 的核心语义
# 格式: source|name|action|objects|full_text_hash
SEMANTICS="$TMP_DIR/semantics.txt"
> "$SEMANTICS"

# 辅助函数：提取动作和对象
extract_semantics() {
    local text="$1"
    local source="$2"
    local name="$3"

    # 将文本转为小写
    local lower_text=$(echo "$text" | tr '[:upper:]' '[:lower:]')

    # 检测动作词（正向/负向）
    local action="neutral"
    if echo "$lower_text" | grep -qE "(必须|应该|推荐|使用|采用|选择|优先|总是|所有)"; then
        action="positive"
    elif echo "$lower_text" | grep -qE "(避免|不要|禁止|不|禁用|从不|切勿)"; then
        action="negative"
    fi

    # 提取对象关键词（技术术语、工具名、模式名）
    # 通过常见技术关键词匹配
    local objects=""
    local tech_keywords="mock|test|database|api|rest|graphql|grpc|oauth|jwt|session|cache|redis|docker|kubernetes|sql|nosql|mongo|postgres|mysql|typescript|javascript|python|go|rust|java|react|vue|angular|svelte|fastapi|django|flask|spring|express|nestjs"
    objects=$(echo "$lower_text" | grep -oE "$tech_keywords" | sort -u | tr '\n' ',' | sed 's/,$//')

    # 生成简单哈希（前 80 个字符）用于去重
    local hash=$(echo "$text" | head -c 80 | md5sum | cut -d' ' -f1)

    echo "$source|$name|$action|$objects|$hash"
}

# 解析 patterns
for f in $PATTERN_FILES; do
    # 读取 frontmatter 中的 name
    name=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^name:" | head -1 | sed 's/name: *//;s/["'"'"']//g' | xargs)
    if [ -z "$name" ]; then
        name=$(basename "$f" .md)
    fi

    # 读取 Pattern 段落的文本（## Pattern 到下一个 ## 之间）
    pattern_text=$(sed -n '/^## Pattern/,/^## /p' "$f" | head -n -1 | sed 's/^## Pattern//')
    if [ -z "$pattern_text" ]; then
        # 如果没有 ## Pattern，读取整个文件除 frontmatter 外
        pattern_text=$(sed '1,/^---$/d;/^---$/d' "$f")
    fi

    extract_semantics "$pattern_text" "pattern:$f" "$name" >> "$SEMANTICS"
done

# 解析 axioms
if [ -f "$AXIOMS_FILE" ] && [ "$AXIOM_COUNT" -gt 0 ]; then
    # 按 ## 标题分割 axioms
    awk '/^## /{if(buf) print buf; buf=$0; next} {buf=buf"\n"$0} END{print buf}' "$AXIOMS_FILE" | \
    while IFS= read -r block; do
        [ -z "$block" ] && continue
        axiom_name=$(echo "$block" | head -1 | sed 's/^## *//')
        axiom_text=$(echo "$block" | tail -n +2)
        [ -z "$axiom_name" ] && continue
        extract_semantics "$axiom_text" "axiom:$AXIOMS_FILE" "$axiom_name" >> "$SEMANTICS"
    done
fi

# 冲突检测逻辑
# 1. 同一对象，相反动作（pattern vs axiom）
# 2. 同一对象，同一动作但不同细节（建议升级/合并）
CONFLICTS="$TMP_DIR/conflicts.txt"
> "$CONFLICTS"

while IFS='|' read -r source1 name1 action1 objs1 hash1; do
    while IFS='|' read -r source2 name2 action2 objs2 hash2; do
        # 只比较 pattern vs axiom，且避免重复比较
        if [[ "$source1" == pattern:* ]] && [[ "$source2" == axiom:* ]]; then
            # 检查对象重叠
            shared_objs=""
            IFS=',' read -ra OA <<< "$objs1"
            IFS=',' read -ra OB <<< "$objs2"
            for a in "${OA[@]}"; do
                for b in "${OB[@]}"; do
                    if [ "$a" = "$b" ] && [ -n "$a" ]; then
                        shared_objs="$shared_objs,$a"
                    fi
                done
            done
            shared_objs=$(echo "$shared_objs" | sed 's/^,//')

            if [ -n "$shared_objs" ]; then
                # 检测冲突类型
                if [ "$action1" != "$action2" ] && [ "$action1" != "neutral" ] && [ "$action2" != "neutral" ]; then
                    # 相反动作 → 冲突
                    echo "CONFLICT|$name1|$source1|$action1|$name2|$source2|$action2|$shared_objs|相反动作" >> "$CONFLICTS"
                elif [ "$action1" = "$action2" ] && [ "$action1" != "neutral" ]; then
                    # 相同动作 → 可能冗余或互补
                    echo "ALIGN|$name1|$source1|$action1|$name2|$source2|$action2|$shared_objs|方向一致" >> "$CONFLICTS"
                fi
            fi
        fi
    done < "$SEMANTICS"
done < "$SEMANTICS"

# 不变量冲突检测（新增）
echo "=== Invariant Violations ==="
echo ""
if [ "$INVARIANT_COUNT" -gt 0 ]; then
    # 检查 patterns 是否违反不变量
    for inv_f in $INVARIANT_FILES; do
        inv_name=$(sed -n '/^---$/,/^---$/p' "$inv_f" | grep "^name:" | head -1 | sed 's/name: *//;s/["'"'"']//g' | xargs)
        inv_rule=$(sed -n '/^## The Rule$/,/^## /p' "$inv_f" | head -n -1 | tail -n +2)
        inv_domain=$(sed -n '/^---$/,/^---$/p' "$inv_f" | grep "^domain:" | sed 's/domain: *//;s/["'"'"']//g' | xargs)

        for pat_f in $PATTERN_FILES; do
            pat_text=$(sed '1,/^---$/d;/^---$/d' "$pat_f")
            # 简单启发式：如果 pattern 文本包含与不变量相反的关键词
            # 这里只标记需要人工审查
            echo "🛡️  Invariant check: $inv_name (domain: $inv_domain)"
            echo "   Rule: $inv_rule"
            echo "   Review pattern: $(basename "$pat_f")"
            echo "   Action: Verify pattern does not violate invariant"
            echo ""
        done
    done
else
    echo "No invariants to check against."
fi

echo "=== Taste vs Axiom Conflicts ==="
echo ""
if [ "$TASTE_COUNT" -gt 0 ] && [ "$AXIOM_COUNT" -gt 0 ]; then
    echo "ℹ️  Taste preferences should not override axioms."
    echo "   Manual review recommended if taste contradicts architectural rules."
    echo ""
else
    echo "No taste/axiom conflicts to check."
fi

echo "=== Entropy Pattern Warnings ==="
echo ""
if [ "$ENTROPY_COUNT" -gt 0 ]; then
    for ent_f in $ENTROPY_FILES; do
        ent_category=$(sed -n '/^---$/,/^---$/p' "$ent_f" | grep "^category:" | sed 's/category: *//;s/["'"'"']//g' | xargs)
        ent_title=$(grep "^# Entropy Pattern:" "$ent_f" | sed 's/# Entropy Pattern: *//')
        echo "⚠️  Entropy pattern registered: $ent_title ($ent_category)"
        echo "   New patterns should be checked against this anti-pattern."
        echo ""
    done
else
    echo "No entropy patterns registered."
fi

# 原有冲突检测输出
echo "=== Pattern vs Axiom Conflicts ==="
echo ""
if [ -s "$CONFLICTS" ]; then
    grep "^CONFLICT|" "$CONFLICTS" | sort -t'|' -k8 | while IFS='|' read -r typ p1 s1 a1 p2 s2 a2 objs note; do
        echo "⚠️  Conflict: $p1 <-> $p2"
        echo "   Shared objects: $objs"
        echo "   Pattern action: $a1 | Axiom action: $a2"
        echo "   Files: $(echo $s1 | sed 's/pattern://') vs $(echo $s2 | sed 's/axiom://')"
        echo ""
    done
else
    echo "No pattern-vs-axiom conflicts detected."
fi

echo "=== Alignments Found ==="
echo ""
if [ -s "$CONFLICTS" ]; then
    grep "^ALIGN|" "$CONFLICTS" | sort -t'|' -k8 | while IFS='|' read -r typ p1 s1 a1 p2 s2 a2 objs note; do
        echo "✅ Alignment: $p1 <-> $p2"
        echo "   Shared objects: $objs"
        echo "   Action: $a1"
        echo ""
    done
else
    echo "No alignments detected."
fi

# 对象覆盖率分析（哪些技术对象被覆盖/未被覆盖）
echo "=== Object Coverage Analysis ==="
echo ""
all_pattern_objs=$(cut -d'|' -f4 "$SEMANTICS" | grep "^pattern:" -v | tr ',' '\n' | sort -u | grep -v '^$')
all_axiom_objs=$(cut -d'|' -f4 "$SEMANTICS" | grep "^axiom:" -v | tr ',' '\n' | sort -u | grep -v '^$')

if [ -n "$all_pattern_objs" ] && [ -n "$all_axiom_objs" ]; then
    uncovered=$(comm -23 <(echo "$all_pattern_objs") <(echo "$all_axiom_objs") | tr '\n' ',' | sed 's/,$//')
    if [ -n "$uncovered" ]; then
        echo "Objects in patterns but not covered by axioms: $uncovered"
        echo "Suggestion: Consider upgrading patterns covering these objects to global axioms."
    else
        echo "All pattern objects are covered by axioms."
    fi
else
    echo "Insufficient data for coverage analysis."
fi

# 清理
rm -rf "$TMP_DIR"

echo ""
echo "=== End of Report ==="
