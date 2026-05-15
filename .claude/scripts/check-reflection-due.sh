#!/bin/bash
# Check if weekly memory reflection is due
# This script is called by the session_start hook in settings.json

LAST_REFLECTION_FILE=".claude/memory/.last-reflection"
DAYS_BETWEEN_REFLECTIONS=7

if [ ! -f "$LAST_REFLECTION_FILE" ]; then
    echo "[Harness] Memory reflection has never been run. Consider running /reflect to initialize."
    exit 0
fi

LAST_DATE=$(cat "$LAST_REFLECTION_FILE")
LAST_EPOCH=$(date -d "$LAST_DATE" +%s 2>/dev/null || date -j -f "%Y-%m-%d" "$LAST_DATE" +%s 2>/dev/null)
NOW_EPOCH=$(date +%s)

if [ -z "$LAST_EPOCH" ]; then
    echo "[Harness] Could not parse last reflection date. Consider running /reflect."
    exit 0
fi

DIFF_DAYS=$(( (NOW_EPOCH - LAST_EPOCH) / 86400 ))

if [ "$DIFF_DAYS" -ge "$DAYS_BETWEEN_REFLECTIONS" ]; then
    echo "[Harness] Weekly memory reflection is due (last run: $LAST_DATE, $DIFF_DAYS days ago). Run /reflect to update patterns."
else
    echo "[Harness] Memory reflection up to date (last run: $LAST_DATE, $DIFF_DAYS days ago)."
fi
