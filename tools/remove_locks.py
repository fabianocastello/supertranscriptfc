#!/usr/bin/env python3
"""Remove locks antigos de uma pasta Dropbox.

Uso:
    python ./tools/remove_locks.py /_AudioMemosFC/MamyCalls --older_than 10m
    python ./tools/remove_locks.py /_AudioMemosFC/MamyCalls --older_than 1h --dry-run

O limite é estrito: um lock é removido somente quando está há MAIS tempo que
 o limite informado. São aceitos somente valores como 1h, 10m ou 30s, sem
 espaço entre número e unidade. Locks sem data interpretável nunca são removidos.
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
    parser.add_argument("root", help="Caminho absoluto da pasta no Dropbox")
    parser.add_argument("--older_than", required=True, help="Idade mínima: 1h, 10m ou 30s")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lista o que seria removido sem apagar locks",
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
        print(f"Erro ao consultar o Dropbox: {exc}", file=sys.stderr)
        return 1

    candidates = [
        lock
        for lock in locks
        if lock.age_seconds is not None and lock.age_seconds > threshold_seconds
    ]
    unknown = [lock for lock in locks if lock.age_seconds is None]
    prefix = "SIMULAÇÃO — " if args.dry_run else ""
    print(f"{prefix}Pasta Dropbox: {args.root}")
    print(f"Consulta realizada em: {now.isoformat(timespec='seconds')}")
    print(f"Critério: locks com mais de {format_age_limit(threshold_seconds)}")
    print(f"Locks encontrados: {len(locks)}")
    print(f"Locks candidatos: {len(candidates)}")

    if candidates:
        print("\nLocks selecionados:")
        for lock in candidates:
            print(f"- {lock.machine} | {lock.name} | {format_elapsed(lock.age_seconds)}")
    else:
        print("\nNenhum lock atende ao critério.")

    if unknown:
        print(
            f"\nNão removidos por segurança ({len(unknown)} sem data interpretável): "
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

    print(f"\nLocks removidos: {len(removed)}")
    if removed:
        distribution = Counter(lock.machine for lock in removed)
        print("Removidos por máquina: " + ", ".join(f"{machine} ({count})" for machine, count in sorted(distribution.items())))
    if failures:
        print(f"Falhas ao remover: {len(failures)}", file=sys.stderr)
        for lock, error in failures:
            print(f"- {lock.name}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
