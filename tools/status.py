#!/usr/bin/env python3
"""Consulta rápida dos locks de uma pasta Dropbox.

Uso:
    python ./tools/status.py /_AudioMemosFC/MamyCalls

A consulta usa o .env na raiz do projeto, lista os locks remotos e não altera
nenhum arquivo do Dropbox.
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
    display_start,
    format_elapsed,
    format_seconds,
    list_files,
    md_cell,
    summarize_entries,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="Caminho absoluto da pasta no Dropbox")
    args = parser.parse_args()

    try:
        dbx = connect_from_env()
        now = datetime.now().astimezone()
        entries = list_files(dbx, args.root)
        audio_count, transcript_count = summarize_entries(entries)
        locks = collect_locks(dbx, args.root, entries, now=now, include_audio_duration=True)
    except Exception as exc:
        print(f"Erro ao consultar o Dropbox: {exc}", file=sys.stderr)
        return 1

    print(f"Pasta Dropbox: {args.root}")
    print(f"Consulta realizada em: {now.isoformat(timespec='seconds')}")
    print(f"Áudios encontrados: {audio_count}")
    print(f"Transcripts .transcriptFC.txt: {transcript_count}")
    print(f"Locks encontrados: {len(locks)}")
    print("\nLocks e execuções atuais")

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
        headers = ["Máquina", "Arquivo", "Desde", "Duração do áudio", "Tempo decorrido"]
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
            "\nDistribuição por máquina: "
            + ", ".join(f"{md_cell(machine)} ({count})" for machine, count in sorted(distribution.items()))
            + "."
        )
    else:
        print("Nenhum lock encontrado.")

    stale = [lock for lock in locks if not lock.is_active]
    if stale:
        print(
            f"\nAtenção: {len(stale)} lock(s) estão fora da janela de 36h ou têm tempo desconhecido. "
            "Use remove_locks somente após confirmar que não há processo executando."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
