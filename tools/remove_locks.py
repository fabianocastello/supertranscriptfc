#!/usr/bin/env python3
"""Removes locks from a Dropbox folder.

Usage:
    Remove locks older than a threshold (the normal case):
        python ./tools/remove_locks.py /_AudioMemosFC/MamyCalls --older_than 10m
        python ./tools/remove_locks.py /_AudioMemosFC/MamyCalls --older_than 1h --dry-run

    Remove every lock, regardless of age (use with care - see Safety below):
        python ./tools/remove_locks.py /_AudioMemosFC/MamyCalls --remove_all
        python ./tools/remove_locks.py /_AudioMemosFC/MamyCalls --remove_all --dry-run

Exactly one of --older_than or --remove_all is required.

--older_than THRESHOLD
    The comparison is strict: only locks older than THRESHOLD are removed.
    THRESHOLD must be a positive integer immediately followed by a single
    unit letter, with no space: 30s, 10m, 1h, 2h. Forms like "10", "10 m",
    "1 hour", or "1d" are all rejected.
    Locks with no parseable start date are never touched by --older_than,
    no matter how old the lock file itself is (Dropbox's own modified
    date is not used as a fallback, since a lock could have been rewritten
    without changing its recorded start time) - use --remove_all if you
    need those gone too.

--remove_all
    Removes every lock found in the folder, including ones with no
    parseable start date. There is no age filtering at all - this is for
    situations like "I know every machine has stopped, just clear
    everything" rather than routine stale-lock cleanup.

--dry-run
    Lists exactly what would be removed, for either mode, without
    deleting anything. Always run this first.

Safety: before deleting a lock, confirm on the indicated machine that
there's no real run actually corresponding to it. Removing an active
lock can let another process start the same audio file in parallel.
--remove_all in particular does not check whether a lock looks active -
it removes literally everything, so only use it when you are sure no
machine is currently mid-job on this folder.
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
    format_age_limit,
    format_elapsed,
    list_files,
    parse_age,
)


def main() -> int:
    parser = HelpfulArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("root", help="Absolute path of the Dropbox folder")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--older_than", help="Minimum age: 1h, 10m, or 30s (see examples above)")
    mode.add_argument(
        "--remove_all",
        action="store_true",
        help="Remove every lock regardless of age, including ones with no parseable date",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be removed without deleting any locks",
    )
    args = parser.parse_args()

    threshold_seconds = None
    if args.older_than is not None:
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

    prefix = "DRY RUN - " if args.dry_run else ""
    print(f"{prefix}Dropbox folder: {args.root}")
    print(f"Query performed at: {now.isoformat(timespec='seconds')}")

    if args.remove_all:
        print("Criterion: ALL locks, regardless of age")
        candidates = list(locks)
        unknown: list = []
    else:
        print(f"Criterion: locks older than {format_age_limit(threshold_seconds)}")
        candidates = [
            lock for lock in locks if lock.age_seconds is not None and lock.age_seconds > threshold_seconds
        ]
        unknown = [lock for lock in locks if lock.age_seconds is None]

    print(f"Locks found: {len(locks)}")
    print(f"Candidate locks: {len(candidates)}")

    if candidates:
        print("\nSelected locks:")
        for lock in candidates:
            age = "unknown age" if lock.age_seconds is None else format_elapsed(lock.age_seconds)
            print(f"- {lock.machine} | {lock.name} | {age}")
    else:
        print("\nNo lock matches the criterion.")

    if unknown:
        print(
            f"\nNot removed for safety ({len(unknown)} without a parseable date; "
            "use --remove_all to remove these too): " + ", ".join(lock.name for lock in unknown)
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
