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
        description="Baixa audio, transcreve, diariza por locutor e envia os resultados.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Caminho do arquivo OU pasta de origem (local ou Dropbox). Se for uma pasta, "
        "processa todos os audios nela.",
    )
    parser.add_argument(
        "--dest",
        default=None,
        help="Pasta de destino (local ou Dropbox). Default: mesma pasta da origem.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Trata --source/--dest como caminhos locais em vez de caminhos do Dropbox.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Ao processar uma pasta, tambem desce em subpastas (util para series de podcast "
        "com uma subpasta por episodio).",
    )
    parser.add_argument("--model-size", default="large-v3", help="Modelo faster-whisper (default: large-v3).")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--compute-type", default="auto")
    parser.add_argument("--language", default=None, help="Codigo do idioma (ex: pt). Default: deteccao automatica.")
    parser.add_argument("--min-speakers", type=int, default=None)
    parser.add_argument("--max-speakers", type=int, default=None)
    parser.add_argument(
        "--min-minutes",
        type=float,
        default=None,
        help="Ignora audios com duracao menor que isso (em minutos).",
    )
    parser.add_argument(
        "--max-minutes",
        type=float,
        default=None,
        help="Ignora audios com duracao maior que isso (em minutos).",
    )
    parser.add_argument("--vtt", action="store_true", help="Tambem gerar arquivo .vtt.")
    parser.add_argument("--no-txt", action="store_true", help="Nao gerar arquivo .txt.")
    parser.add_argument("--no-srt", action="store_true", help="Nao gerar arquivo .srt.")
    parser.add_argument("--keep-temp", action="store_true", help="Nao apagar arquivos temporarios ao final.")
    parser.add_argument("--force", action="store_true", help="Reprocessar mesmo se ja concluido anteriormente.")
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
            "HF_TOKEN nao configurado (necessario para a diarizacao com pyannote.audio). "
            "Preencha-o no .env antes de rodar (veja .env.example)."
        )
        return 1

    try:
        if args.local:
            dest_dir = Path(args.dest) if args.dest else None
            source_path = Path(args.source)
            if source_path.is_dir():
                summary = run_local_batch(config, source_path, dest_dir, recursive=args.recursive)
                _log_batch_summary(logger, summary)
            else:
                outputs = run_local_job(config, source_path, dest_dir)
                if outputs:
                    logger.info("Concluido. Arquivos gerados: %s", [str(p) for p in outputs])
                else:
                    logger.info("Nada a fazer (ja processado, em andamento em outra maquina, ou fora dos limites de duracao configurados).")
        else:
            if not args.source.startswith("/"):
                logger.error(
                    "'--source %s' nao parece um caminho do Dropbox (precisa comecar com '/'). "
                    "Se e' um arquivo local, use --local.",
                    args.source,
                )
                return 1
            if not config.has_dropbox_credentials:
                logger.error(
                    "DROPBOX_APP_KEY / DROPBOX_APP_SECRET / DROPBOX_REFRESH_TOKEN "
                    "nao configurados (veja .env.example)."
                )
                return 1
            from .dropbox_client import DropboxClient

            client = DropboxClient(
                config.dropbox_app_key, config.dropbox_app_secret, config.dropbox_refresh_token
            )
            if client.is_folder(args.source):
                summary = run_dropbox_batch(
                    config, client, args.source, args.dest, recursive=args.recursive
                )
                _log_batch_summary(logger, summary)
            else:
                outputs = run_dropbox_job(config, client, args.source, args.dest)
                if outputs:
                    logger.info("Concluido. Arquivos enviados ao Dropbox: %s", outputs)
                else:
                    logger.info("Nada a fazer (ja processado, em andamento em outra maquina, ou fora dos limites de duracao configurados).")
        return 0
    except Exception:
        logger.exception("Falha ao processar %s", args.source)
        return 1


def _log_batch_summary(logger, summary: dict[str, list]) -> None:
    logger.info(
        "Lote concluido: %d processado(s), %d pulado(s) (ja concluidos), %d com falha.",
        len(summary["processed"]),
        len(summary["skipped"]),
        len(summary["failed"]),
    )
    if summary["failed"]:
        logger.warning("Arquivos com falha: %s", summary["failed"])


if __name__ == "__main__":
    sys.exit(main())
