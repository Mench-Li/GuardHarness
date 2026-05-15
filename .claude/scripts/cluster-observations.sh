#!/bin/bash
# cluster-observations.sh
# 对最近 N 天的 observations 进行关键词聚类，辅助 pattern 提炼
# 用法: bash .claude/scripts/cluster-observations.sh [days]

DAYS=${1:-30}
OBS_DIR=".claude/memory/observations"
TMP_DIR=".claude/memory/.tmp"
mkdir -p "$TMP_DIR"

echo "=== Observation Clustering Report ($(date +%Y-%m-%d)) ==="
echo "Scanning last $DAYS days in $OBS_DIR"
echo ""

# 收集文件列表（最近 N 天）
CUTOFF=$(date -d "$DAYS days ago" +%Y-%m-%d 2>/dev/null || date -v-${DAYS}d +%Y-%m-%d)
FILES=$(find "$OBS_DIR" -name "*.md" -type f -newermt "$CUTOFF" 2>/dev/null | sort)

if [ -z "$FILES" ]; then
    echo "No observations found in the last $DAYS days."
    exit 0
fi

TOTAL=$(echo "$FILES" | wc -l)
echo "Found $TOTAL observation files"
echo ""

# 解析每个文件的元数据
# 输出格式: filename|date|type|tags|keywords
PARSED="$TMP_DIR/obs_parsed.txt"
> "$PARSED"

for f in $FILES; do
    fname=$(basename "$f")
    # 提取 frontmatter 中的 date
    date_str=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^date:" | head -1 | sed 's/date: *//;s/["'"'"']//g' | xargs)
    # 提取 type
    type_str=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^type:" | head -1 | sed 's/type: *//;s/["'"'"']//g' | xargs)
    # 提取 tags（多行或单行数组格式）
    tags_str=$(sed -n '/^---$/,/^---$/p' "$f" | sed -n '/^tags:/,/^[^- ]/p' | grep '^  -' | sed 's/^  - *//' | tr '\n' ',' | sed 's/,$//')
    if [ -z "$tags_str" ]; then
        tags_str=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^tags:" | sed 's/tags: *\[//;s/\]//;s/["'"'"']//g' | xargs | tr ', ' ',')
    fi

    # 提取正文关键词（根据 type 提取不同段落）
    keywords=""
    case "$type_str" in
        decision)
            keywords=$(grep -oE '^## (Options Considered|Decision|Rationale|Consequences)$' "$f" | sed 's/^## *//' | tr '\n' ',' | sed 's/,$//')
            ;;
        failure)
            keywords=$(grep -oE '^## (What Failed|Root Cause|What We Learned|Mitigation)$' "$f" | sed 's/^## *//' | tr '\n' ',' | sed 's/,$//')
            ;;
        entropy)
            keywords=$(grep -oE '^## (The Smell|Prevention Rule|Detection Heuristic)$' "$f" | sed 's/^## *//' | tr '\n' ',' | sed 's/,$//')
            # 也提取 category
            category=$(sed -n '/^---$/,/^---$/p' "$f" | grep "^category:" | sed 's/category: *//;s/["'"'"']//g' | xargs)
            [ -n "$category" ] && keywords="$keywords,$category"
            ;;
        taste)
            keywords=$(grep -oE '^## (The Preference|Source Context|When It Applies)$' "$f" | sed 's/^## *//' | tr '\n' ',' | sed 's/,$//')
            ;;
        *)
            keywords=$(grep -oE '^##[ ]+[^ ]+' "$f" | sed 's/^##[ ]*//' | tr '\n' ',' | sed 's/,$//')
            ;;
    esac

    # 提取加粗词作为补充关键词
    bold_words=$(grep -oE '\*\*[^*]+\*\*' "$f" | sed 's/\*\*//g' | tr '\n' ',' | sed 's/,$//')
    if [ -n "$bold_words" ]; then
        keywords="${keywords},${bold_words}"
    fi

    echo "$fname|$date_str|$type_str|$tags_str|$keywords" >> "$PARSED"
done

# 相似度计算：基于 tag 重叠 + keyword 重叠
# 输出格式: file1|file2|similarity_score|shared_tags|shared_keywords
SIM_MATRIX="$TMP_DIR/sim_matrix.txt"
> "$SIM_MATRIX"

while IFS='|' read -r f1 d1 t1 tags1 kws1; do
    while IFS='|' read -r f2 d2 t2 tags2 kws2 <&3; do
        # 只处理单向比较避免重复
        if [ "$f1" != "$f2" ] && [ "$(printf '%s\n%s\n' "$f1" "$f2" | sort | head -n1)" = "$f1" ]; then
            # 计算 tag 重叠
            tag1_list=$(echo "$tags1" | tr ',' '\n' | sed 's/^[ ]*//' | sort -u)
            tag2_list=$(echo "$tags2" | tr ',' '\n' | sed 's/^[ ]*//' | sort -u)
            tag_shared=$(printf '%s\n%s\n' "$tag1_list" "$tag2_list" | sort | uniq -d | wc -l)
            tag_total=$(printf '%s\n%s\n' "$tag1_list" "$tag2_list" | sort -u | wc -l)

            # 计算 keyword 重叠
            kw1_list=$(echo "$kws1" | tr ',' '\n' | sed 's/^[ ]*//' | tr '[:upper:]' '[:lower:]' | sort -u)
            kw2_list=$(echo "$kws2" | tr ',' '\n' | sed 's/^[ ]*//' | tr '[:upper:]' '[:lower:]' | sort -u)
            kw_shared=$(printf '%s\n%s\n' "$kw1_list" "$kw2_list" | sort | uniq -d | wc -l)
            kw_total=$(printf '%s\n%s\n' "$kw1_list" "$kw2_list" | sort -u | wc -l)

            # 综合相似度（tag 权重 0.6，keyword 权重 0.4）
            if [ "$tag_total" -gt 0 ]; then
                tag_sim=$(awk "BEGIN {printf \"%.3f\", $tag_shared / $tag_total}" 2>/dev/null || echo "0")
            else
                tag_sim="0"
            fi
            if [ "$kw_total" -gt 0 ]; then
                kw_sim=$(awk "BEGIN {printf \"%.3f\", $kw_shared / $kw_total}" 2>/dev/null || echo "0")
            else
                kw_sim="0"
            fi

            # 如果任一维度有重叠，计算综合分数
            if [ "$tag_shared" -gt 0 ] || [ "$kw_shared" -gt 0 ]; then
                score=$(awk "BEGIN {printf \"%.3f\", 0.6 * $tag_sim + 0.4 * $kw_sim}" 2>/dev/null || echo "0")
                # 四舍五入到两位小数用于阈值判断
                score_rounded=$(printf "%.2f" "$score")
                # 阈值：0.3 以上认为相关
                if awk "BEGIN {exit ($score_rounded >= 0.30) ? 0 : 1}"; then
                    shared_tags_str=$(printf '%s\n%s\n' "$tag1_list" "$tag2_list" | sort | uniq -d | tr '\n' ',' | sed 's/,$//')
                    shared_kws_str=$(printf '%s\n%s\n' "$kw1_list" "$kw2_list" | sort | uniq -d | tr '\n' ',' | sed 's/,$//')
                    echo "$f1|$f2|$score|$shared_tags_str|$shared_kws_str" >> "$SIM_MATRIX"
                fi
            fi
        fi
    done 3< "$PARSED"
done < "$PARSED"

# 聚类：使用连通分量（并查集简化版）
# 为每个文件分配一个 cluster ID
CLUSTERS="$TMP_DIR/clusters.txt"
> "$CLUSTERS"

# 初始化：每个文件一个 cluster
cid=0
while IFS='|' read -r f1 rest; do
    echo "$f1|$cid" >> "$CLUSTERS"
    cid=$((cid + 1))
done < "$PARSED"

# 合并相似文件到同一 cluster
while IFS='|' read -r f1 f2 score stags skws; do
    c1=$(grep "^$f1|" "$CLUSTERS" | cut -d'|' -f2)
    c2=$(grep "^$f2|" "$CLUSTERS" | cut -d'|' -f2)
    if [ "$c1" != "$c2" ]; then
        # 将 c2 的所有文件合并到 c1
        sed -i "s/|$c2\$/|$c1/" "$CLUSTERS"
    fi
done < "$SIM_MATRIX"

# 输出聚类结果
echo "=== Clusters Found ==="
echo ""

# 按 cluster ID 分组
sort -t'|' -k2 -n "$CLUSTERS" | awk -F'|' '
    { clusters[$2] = clusters[$2] "," $1 }
    END {
        for (c in clusters) {
            sub(/^,/, "", clusters[c])
            n = split(clusters[c], files, ",")
            if (n >= 2) {
                print "Cluster " c " (" n " files):"
                for (i=1; i<=n; i++) print "  - " files[i]
                print ""
            }
        }
    }
'

# 输出孤立文件（未聚类）
echo "=== Unclustered (singletons) ==="
echo ""
sort -t'|' -k2 -n "$CLUSTERS" | awk -F'|' '
    { clusters[$2] = clusters[$2] "," $1 }
    END {
        for (c in clusters) {
            sub(/^,/, "", clusters[c])
            n = split(clusters[c], files, ",")
            if (n == 1) {
                print "  - " files[1]
            }
        }
    }
'
echo ""

# 输出相似度矩阵摘要
echo "=== Similarity Pairs (score >= 0.30) ==="
echo ""
if [ -s "$SIM_MATRIX" ]; then
    sort -t'|' -k3 -nr "$SIM_MATRIX" | while IFS='|' read -r f1 f2 score stags skws; do
        echo "$f1 <-> $f2 (score: $score)"
        [ -n "$stags" ] && echo "  Shared tags: $stags"
        [ -n "$skws" ] && echo "  Shared keywords: $skws"
        echo ""
    done
else
    echo "No significant similarities found (threshold: 0.30)."
fi

# 清理临时文件
rm -rf "$TMP_DIR"

echo "=== End of Report ==="
