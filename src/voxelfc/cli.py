from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

from .config import Config
from .logging_setup import setup_logging
from .pipeline import run_dropbox_batch, run_dropbox_job, run_local_batch, run_local_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="voxelfc",
        description="Downloads audio, transcribes it, diarizes speakers, and delivers the results.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Path to the source file OR folder (local or Dropbox). If a folder, "
        "processes every audio file in it.",
    )
    parser.add_argument(
        "--dest",
        default=None,
        help="Destination folder (local or Dropbox). Default: same folder as the source.",
    )
    parser.add_argument(
        "--archive",
        default=None,
        help="If processing finishes OK, move (not copy) the original audio and the "
        "generated outputs into this folder (local or Dropbox, per --local).",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Treat --source/--dest as local paths instead of Dropbox paths.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="When processing a folder, also descend into subfolders (useful for "
        "podcast series with one subfolder per episode).",
    )
    parser.add_argument("--model-size", default="large-v3", help="faster-whisper model (default: large-v3).")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--compute-type", default="auto")
    parser.add_argument("--language", default=None, help="Language code (e.g. pt). Default: auto-detect.")
    parser.add_argument("--min-speakers", type=int, default=None)
    parser.add_argument("--max-speakers", type=int, default=None)
    parser.add_argument(
        "--min-minutes",
        type=float,
        default=None,
        help="Skip audio files shorter than this (in minutes).",
    )
    parser.add_argument(
        "--max-minutes",
        type=float,
        default=None,
        help="Skip audio files longer than this (in minutes).",
    )
    parser.add_argument("--vtt", action="store_true", help="Also generate a .vtt file.")
    parser.add_argument("--no-txt", action="store_true", help="Don't generate a .txt file.")
    parser.add_argument("--no-srt", action="store_true", help="Don't generate a .srt file.")
    parser.add_argument("--keep-temp", action="store_true", help="Don't delete temporary files at the end.")
    parser.add_argument("--force", action="store_true", help="Reprocess even if already completed before.")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    invoked_as = Path(sys.argv[0]).stem.lower()
    if invoked_as == "supertranscriptfc":
        warnings.warn(
            "The 'supertranscriptfc' command is deprecated; use 'voxelfc' instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    parser = build_parser()
    args = parser.parse_args(argv)

    config = Config(
        model_size=args.model_size,
        device=args.device,
        compute_type=args.compute_type,
        language=args.language,
        min_speakers=args.min_speakers,
        max_speakers=args.max_speakers,
        min_minutes=args.min_minutes,
        max_minutes=args.max_minutes,
        write_txt=not args.no_txt,
        write_srt=not args.no_srt,
        write_vtt=args.vtt,
        keep_temp=args.keep_temp,
        force=args.force,
    )
    config.ensure_dirs()
    logger = setup_logging(config.logs_dir, verbose=args.verbose)

    if not config.hf_token:
        logger.error(
            "HF_TOKEN not configured (required for diarization with pyannote.audio). "
            "Set it in .env before running (see .env.example)."
        )
        return 1

    try:
        if args.local:
            dest_dir = Path(args.dest) if args.dest else None
            archive_dir = Path(args.archive) if args.archive else None
            source_path = Path(args.source)
            if source_path.is_dir():
                summary = run_local_batch(
                    config, source_path, dest_dir, recursive=args.recursive, archive_dir=archive_dir
                )
                _log_batch_summary(logger, summary)
            else:
                outputs = run_local_job(config, source_path, dest_dir, archive_dir=archive_dir)
                if outputs:
                    logger.info("Done. Files generated: %s", [str(p) for p in outputs])
                else:
                    logger.info(
                        "Nothing to do (already processed, in progress on another machine, "
                        "or outside the configured duration limits)."
                    )
        else:
            if not args.source.startswith("/"):
                logger.error(
                    "'--source %s' doesn't look like a Dropbox path (must start with '/'). "
                    "If it's a local file, use --local.",
                    args.source,
                )
                return 1
            if not config.has_dropbox_credentials:
                logger.error(
                    "DROPBOX_APP_KEY / DROPBOX_APP_SECRET / DROPBOX_REFRESH_TOKEN "
                    "not configured (see .env.example)."
                )
                return 1
            from .dropbox_client import DropboxClient

            client = DropboxClient(
                config.dropbox_app_key, config.dropbox_app_secret, config.dropbox_refresh_token
            )
            if client.is_folder(args.source):
                summary = run_dropbox_batch(
                    config,
                    client,
                    args.source,
                    args.dest,
                    recursive=args.recursive,
                    archive_folder=args.archive,
                )
                _log_batch_summary(logger, summary)
            else:
                outputs = run_dropbox_job(
                    config, client, args.source, args.dest, archive_folder=args.archive
                )
                if outputs:
                    logger.info("Done. Files uploaded to Dropbox: %s", outputs)
                else:
                    logger.info(
                        "Nothing to do (already processed, in progress on another machine, "
                        "or outside the configured duration limits)."
                    )
        return 0
    except Exception:
        logger.exception("Failed to process %s", args.source)
        return 1


def _log_batch_summary(logger, summary: dict[str, list]) -> None:
    logger.info(
        "Batch complete: %d processed, %d skipped (already done), %d failed.",
        len(summary["processed"]),
        len(summary["skipped"]),
        len(summary["failed"]),
    )
    if summary["failed"]:
        logger.warning("Files with failures: %s", summary["failed"])


if __name__ == "__main__":
    sys.exit(main())
