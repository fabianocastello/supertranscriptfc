#!/usr/bin/env python3
"""Copy VOXEL FC state from a legacy home to a canonical home."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="source", required=True, type=Path)
    parser.add_argument("--to", dest="destination", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def iter_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file()) if root.exists() else []


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    if source == destination:
        raise SystemExit("source and destination must be different")
    if not source.exists():
        raise SystemExit(f"source does not exist: {source}")
    if destination.exists() and any(destination.iterdir()):
        raise SystemExit(f"destination must be absent or empty: {destination}")

    files = iter_files(source)
    print(f"Source:      {source}")
    print(f"Destination: {destination}")
    print(f"Files:       {len(files)}")
    for path in files:
        print(f"  {path.relative_to(source)}")
    if args.dry_run:
        print("Dry-run only; nothing copied.")
        return 0

    destination.mkdir(parents=True, exist_ok=True)
    for path in files:
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    copied = iter_files(destination)
    if len(copied) != len(files):
        raise SystemExit(f"verification failed: copied {len(copied)} of {len(files)} files")
    print("Copy completed and file-count verification passed.")
    print(f"Rollback: set VOXELFC_HOME={source}")
    print(f"The source was preserved: {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
