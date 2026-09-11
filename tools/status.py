#!/usr/bin/env python3
"""Quick status check of the locks in a Dropbox folder.

Usage:
    python ./tools/status.py /_AudioMemosFC/MamyCalls
    python ./tools/status.py /Other/Folder

The only argument is the absolute Dropbox folder path to check (must
start with '/'). The query uses the .env file at the project root, lists
the remote locks (machine, file, start time, elapsed time), and does not
modify any file on Dropbox - it's fully read-only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dropbox_lock_utils import (  # noqa: E402
    HelpfulArgumentParser,
    collect_locks,
    connect_from_env,
    display_start,
    format_elapsed,
    format_seconds,
    list_files,
    md_cell,
    summarize_entries,
)


def main() -> int:
    parser = HelpfulArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("root", help="Absolute path of the Dropbox folder (must start with '/')")
    args = parser.parse_args()

    try:
        dbx = connect_from_env()
        now = datetime.now().astimezone()
        entries = list_files(dbx, args.root)
        audio_count, transcript_count = summarize_entries(entries)
        locks = collect_locks(dbx, args.root, entries, now=now, include_audio_duration=True)
    except Exception as exc:
        print(f"Error querying Dropbox: {exc}", file=sys.stderr)
        return 1

    print(f"Dropbox folder: {args.root}")
    print(f"Query performed at: {now.isoformat(timespec='seconds')}")
    print(f"Audio files found: {audio_count}")
    print(f"Transcripts (.voxel.md + legacy .voxel.txt/.transcriptFC.txt): {transcript_count}")
    print(f"Locks found: {len(locks)}")
    print("\nLocks and current runs")

    if locks:
        rows = [
            [
                lock.machine,
                lock.name,
                display_start(lock, now.tzinfo),
                format_seconds(lock.audio_duration_seconds),
                format_elapsed(lock.age_seconds),
            ]
            for lock in locks
        ]
        headers = ["Machine", "File", "Since", "Audio duration", "Elapsed time"]
        widths = [
            max(len(headers[index]), *(len(row[index]) for row in rows))
            for index in range(len(headers))
        ]
        print("  ".join(headers[index].ljust(widths[index]) for index in range(len(headers))))
        for lock in locks:
            row = [
                lock.machine,
                lock.name,
                display_start(lock, now.tzinfo),
                format_seconds(lock.audio_duration_seconds),
                format_elapsed(lock.age_seconds),
            ]
            print("  ".join(row[index].ljust(widths[index]) for index in range(len(row))))
        distribution = Counter(lock.machine for lock in locks)
        print(
            "\nDistribution by machine: "
            + ", ".join(f"{md_cell(machine)} ({count})" for machine, count in sorted(distribution.items()))
            + "."
        )
    else:
        print("No lock found.")

    stale = [lock for lock in locks if not lock.is_active]
    if stale:
        print(
            f"\nWarning: {len(stale)} lock(s) are outside the 36h window or have an unknown age. "
            "Use remove_locks only after confirming that no process is running."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
