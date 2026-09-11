#!/usr/bin/env python3
"""Renames legacy transcript files on Dropbox to the current suffix.

Usage:
    python ./tools/rename_transcripts.py /_AudioMemosFC/MamyCalls --dry-run
    python ./tools/rename_transcripts.py /_AudioMemosFC/MamyCalls

Finds every file ending in a legacy transcript suffix (.voxel.txt or
.transcriptFC.txt, recursively under the given folder) and renames it to
the current suffix (.voxel.md), keeping the rest of the filename. Files
already named .voxel.md are left untouched.

This is optional cleanup: the pipeline already recognizes legacy names as
"already done" without renaming them, so files aren't reprocessed either
way. If a file with the destination name already exists, that rename is
skipped (reported, not overwritten) rather than risking data loss.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dropbox_lock_utils import (  # noqa: E402
    HelpfulArgumentParser,
    LEGACY_TRANSCRIPT_SUFFIXES,
    TRANSCRIPT_SUFFIX,
    connect_from_env,
    list_files,
)


def main() -> int:
    parser = HelpfulArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("root", help="Absolute path of the Dropbox folder (must start with '/')")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be renamed without renaming anything",
    )
    args = parser.parse_args()

    try:
        dbx = connect_from_env()
        entries = list_files(dbx, args.root)
    except Exception as exc:
        print(f"Error querying Dropbox: {exc}", file=sys.stderr)
        return 1

    existing_paths = {entry.path_display for entry in entries}
    candidates: list[tuple[str, str]] = []
    for entry in entries:
        for suffix in LEGACY_TRANSCRIPT_SUFFIXES:
            if entry.name.endswith(suffix):
                new_path = entry.path_display[: -len(suffix)] + TRANSCRIPT_SUFFIX
                candidates.append((entry.path_display, new_path))
                break

    prefix = "DRY RUN - " if args.dry_run else ""
    print(f"{prefix}Dropbox folder: {args.root}")
    print(f"Legacy transcripts found: {len(candidates)}")

    conflicts = [(old, new) for old, new in candidates if new in existing_paths]
    safe = [(old, new) for old, new in candidates if new not in existing_paths]

    if conflicts:
        print(f"\nSkipped ({len(conflicts)}) - destination already exists:")
        for old, new in conflicts:
            print(f"- {old} -> {new} (already exists, not overwritten)")

    if safe:
        print(f"\n{'Would rename' if args.dry_run else 'Renaming'} ({len(safe)}):")
        for old, new in safe:
            print(f"- {old} -> {new}")
    else:
        print("\nNothing to rename.")

    if args.dry_run or not safe:
        return 0

    renamed = []
    failures = []
    for old, new in safe:
        try:
            dbx.files_move_v2(old, new)
            renamed.append((old, new))
        except Exception as exc:
            failures.append((old, str(exc)))

    print(f"\nRenamed: {len(renamed)}")
    if failures:
        print(f"Failures: {len(failures)}", file=sys.stderr)
        for path, error in failures:
            print(f"- {path}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
