#!/bin/bash
lockPath="/Users/fcastell/voxelfc/.update.lock"

if ! /usr/bin/pmset -g batt | /usr/bin/grep -q "AC Power"; then
    exit 0
fi

if [ -f "$lockPath" ]; then
    existingPid=$(cat "$lockPath" 2>/dev/null)
    if [ -n "$existingPid" ] && kill -0 "$existingPid" 2>/dev/null; then
        echo "Already running (pid $existingPid), skipping."
        exit 0
    fi
    echo "Stale lock found (pid ${existingPid:-unknown} not running); removing."
fi

echo $$ > "$lockPath"
trap 'rm -f "$lockPath"' EXIT

cd /Users/fcastell/voxelfc || exit 1
source .venv/bin/activate
bash scripts/update.sh --source "/_AudioMemosFC/_Inbox.AudioZapDownFC" --model-size large-v3 --vtt --max-minutes 1 --archive "/_AudioMemosFC/_Inbox.AudioZapDownFC.Ready" --recursive
