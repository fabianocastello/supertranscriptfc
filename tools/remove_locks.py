#!/usr/bin/env python3
"""Removes stale locks from a Dropbox folder.

Usage:
    python ./tools/remove_locks.py /_AudioMemosFC/MamyCalls --older_than 10m
    python ./tools/remove_locks.py /_AudioMemosFC/MamyCalls --older_than 1h --dry-run

The threshold is strict: a lock is only removed when it has been around for
MORE time than the given threshold. Only values like 1h, 10m, or 30s are
accepted, with no space between the number and the unit. Locks without a
parseable date are never removed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dropbox_lock_utils import (  # noqa: E402
    collect_locks,
    connect_from_env,
    format_age_limit,
    format_elapsed,
    list_files,
    parse_age,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="Absolute path of the Dropbox folder")
    parser.add_argument("--older_than", required=True, help="Minimum age: 1h, 10m, or 30s")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be removed without deleting any locks",
    )
    args = parser.parse_args()

    try:
        threshold_seconds = parse_age(args.older_than)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        dbx = connect_from_env()
        now = datetime.now().astimezone()
        entries = list_files(dbx, args.root)
        locks = collect_locks(dbx, args.root, entries, now=now)
    except Exception as exc:
        print(f"Error querying Dropbox: {exc}", file=sys.stderr)
        return 1

    candidates = [
        lock
        for lock in locks
        if lock.age_seconds is not None and lock.age_seconds > threshold_seconds
    ]
    unknown = [lock for lock in locks if lock.age_seconds is None]
    prefix = "DRY RUN — " if args.dry_run else ""
    print(f"{prefix}Dropbox folder: {args.root}")
    print(f"Query performed at: {now.isoformat(timespec='seconds')}")
    print(f"Criterion: locks older than {format_age_limit(threshold_seconds)}")
    print(f"Locks found: {len(locks)}")
    print(f"Candidate locks: {len(candidates)}")

    if candidates:
        print("\nSelected locks:")
        for lock in candidates:
            print(f"- {lock.machine} | {lock.name} | {format_elapsed(lock.age_seconds)}")
    else:
        print("\nNo lock matches the criterion.")

    if unknown:
        print(
            f"\nNot removed for safety ({len(unknown)} without a parseable date): "
            + ", ".join(lock.name for lock in unknown)
        )

    if args.dry_run or not candidates:
        return 0

    removed = []
    failures = []
    for lock in candidates:
        try:
            dbx.files_delete_v2(lock.path)
            removed.append(lock)
        except Exception as exc:
            failures.append((lock, str(exc)))

    print(f"\nLocks removed: {len(removed)}")
    if removed:
        distribution = Counter(lock.machine for lock in removed)
        print("Removed by machine: " + ", ".join(f"{machine} ({count})" for machine, count in sorted(distribution.items())))
    if failures:
        print(f"Failures while removing: {len(failures)}", file=sys.stderr)
        for lock, error in failures:
            print(f"- {lock.name}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
