#!/usr/bin/env bash
# Monitors several Dropbox folders on the same machine, calling
# voxelfc for each one in sequence. It's safe to restart from scratch
# at any time (after a crash, for example): each file is only considered
# complete based on the real existence of .transcriptFC.txt on Dropbox
# itself, so folders/files that are already done are skipped quickly
# instead of being reprocessed.
#
# Configuration: list the folders in scripts/folders.txt (one per line,
# starting with "/"; blank lines or lines starting with "#" are ignored).
# Copy scripts/folders.txt.example to get started.
#
# Usage:
#   scripts/monitor_folders.sh [--loop SECONDS] [-- <extra args>]
#
# Examples:
#   scripts/monitor_folders.sh -- --model-size large-v3 --language pt --vtt
#   scripts/monitor_folders.sh --loop 1800 -- --model-size large-v3 --vtt
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"
FOLDERS_FILE="${FOLDERS_FILE:-scripts/folders.txt}"

if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

if [ ! -f "$FOLDERS_FILE" ]; then
    echo "Folders file not found: $FOLDERS_FILE" >&2
    echo "Copy scripts/folders.txt.example to $FOLDERS_FILE and edit it with your Dropbox folders." >&2
    exit 1
fi

LOOP_INTERVAL=""
EXTRA_ARGS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --loop)
            LOOP_INTERVAL="$2"
            shift 2
            ;;
        --)
            shift
            EXTRA_ARGS=("$@")
            break
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

run_one_pass() {
    local total=0 ok=0 fail=0

    while IFS= read -r line || [ -n "$line" ]; do
        line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -z "$line" ] && continue
        case "$line" in \#*) continue ;; esac

        total=$((total + 1))
        echo ""
        echo "=== [$total] Folder: $line ==="
        if voxelfc --source "$line" "${EXTRA_ARGS[@]}"; then
            ok=$((ok + 1))
        else
            fail=$((fail + 1))
            echo "WARNING: failed to process folder '$line', continuing with the rest." >&2
        fi
    done < "$FOLDERS_FILE"

    echo ""
    echo "=== Pass complete: $ok/$total folders OK, $fail failed ==="
}

if [ -n "$LOOP_INTERVAL" ]; then
    echo "Monitoring in a loop, every ${LOOP_INTERVAL}s (Ctrl+C to stop)."
    while true; do
        run_one_pass
        echo "Waiting ${LOOP_INTERVAL}s until the next pass..."
        sleep "$LOOP_INTERVAL"
    done
else
    run_one_pass
fi
