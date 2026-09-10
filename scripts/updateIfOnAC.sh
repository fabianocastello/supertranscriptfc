#!/bin/bash
if ! /usr/bin/pmset -g batt | /usr/bin/grep -q "AC Power"; then
    exit 0
fi
cd /Users/fcastell/voxelfc || exit 1
source .venv/bin/activate
exec bash scripts/update.sh --source "/_AudioMemosFC/_Inbox.AudioZapDownFC" --model-size large-v3 --vtt --max-minutes 1 --archive "/_AudioMemosFC/_Inbox.AudioZapDownFC.Ready" --recursive
