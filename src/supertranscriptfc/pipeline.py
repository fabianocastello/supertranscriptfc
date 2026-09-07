from __future__ import annotations

import logging
import shutil
import socket
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath

from .audio import convert_to_wav, probe_duration_seconds
from .config import AUDIO_EXTENSIONS, Config
from .diarize import diarize_audio
from .merge import assign_speakers
from .naming import build_output_stem
from .outputs import write_srt, write_txt, write_vtt
from .progress import format_duration
from .state import JobState, ProcessedRegistry, compute_job_id
from .transcribe import transcribe_audio

logger = logging.getLogger("supertranscriptfc")

# Um processamento longo (audio de varias horas em CPU) pode legitimamente
# levar mais de um dia; alem disso consideramos o lock abandonado (ex: a
# maquina foi desligada no meio do processo) e deixamos outra maquina assumir.
LOCK_STALE_AFTER = timedelta(hours=36)


def _make_lock_content() -> str:
    hostname = socket.gethostname()
    started_at = datetime.now().isoformat()
    return f"Processando por: {hostname}\nIniciado em: {started_at}\n"


def _is_lock_stale(lock_content: str) -> bool:
    try:
        iso_timestamp = lock_content.splitlines()[1].split("Iniciado em: ", 1)[1]
        locked_at = datetime.fromisoformat(iso_timestamp)
    except (IndexError, ValueError):
        return True
    return datetime.now() - locked_at > LOCK_STALE_AFTER


def process_file(
    config: Config,
    input_path: Path,
    output_stem: str,
    work_dir: Path,
    source_ref: str,
) -> list[Path]:
    """Roda o pipeline completo (conversao -> transcricao -> diarizacao ->
    merge -> geracao de saidas) sobre um arquivo de audio ja disponivel em
    disco. Retorna a lista de arquivos de saida gerados em work_dir/output.

    E' resumivel: cada etapa e' marcada em progress.json dentro de work_dir,
    e reexecucoes pulam etapas ja concluidas (a menos que config.force)."""
    job_id = compute_job_id(source_ref)
    state = JobState(job_id=job_id, source_ref=source_ref, work_dir=work_dir)
    state.load()
    if config.force:
        state.completed_stages.clear()

    wav_path = work_dir / "audio_16k_mono.wav"
    output_dir = work_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    input_size_mb = input_path.stat().st_size / 1_000_000
    logger.info(
        "[%s] Arquivo de origem: %s (%.1f MB, modificado em %s)",
        job_id,
        input_path.name,
        input_size_mb,
        datetime.fromtimestamp(input_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
    )

    if not state.is_done("converted"):
        convert_to_wav(input_path, wav_path)
        state.mark_done("converted")
    else:
        logger.info("[%s] Conversao ja concluida, pulando.", job_id)

    audio_duration = probe_duration_seconds(wav_path)
    logger.info("[%s] Duracao do audio: %s", job_id, format_duration(audio_duration))

    if not state.is_done("transcribed"):
        segments = transcribe_audio(
            wav_path,
            model_size=config.model_size,
            device=config.device,
            compute_type=config.compute_type,
            language=config.language,
        )
        transcript_data = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
        state.mark_done("transcribed", transcript=transcript_data)
    else:
        logger.info("[%s] Transcricao ja concluida, pulando.", job_id)
        transcript_data = state.data["transcript"]

    if not state.is_done("diarized"):
        turns = diarize_audio(
            wav_path,
            hf_token=config.hf_token,
            min_speakers=config.min_speakers,
            max_speakers=config.max_speakers,
        )
        turns_data = [{"start": t.start, "end": t.end, "speaker": t.speaker} for t in turns]
        state.mark_done("diarized", turns=turns_data)
    else:
        logger.info("[%s] Diarizacao ja concluida, pulando.", job_id)
        turns_data = state.data["turns"]

    from .diarize import SpeakerTurn
    from .transcribe import TranscriptSegment

    segments = [TranscriptSegment(**s) for s in transcript_data]
    turns = [SpeakerTurn(**t) for t in turns_data]
    labeled_segments = assign_speakers(segments, turns)

    output_paths: list[Path] = []
    if config.write_txt:
        output_paths.append(write_txt(labeled_segments, output_dir / f"{output_stem}.transcriptFC.txt"))
    if config.write_srt:
        output_paths.append(write_srt(labeled_segments, output_dir / f"{output_stem}.srt"))
    if config.write_vtt:
        output_paths.append(write_vtt(labeled_segments, output_dir / f"{output_stem}.transcriptFC.vtt"))

    state.mark_done("outputs_written", outputs=[str(p) for p in output_paths])
    logger.info("[%s] Saidas geradas: %s", job_id, [p.name for p in output_paths])
    return output_paths


def cleanup_work_dir(work_dir: Path, keep_temp: bool) -> None:
    if keep_temp:
        logger.info("keep_temp ativo, mantendo %s", work_dir)
        return
    logger.info("Limpando temporarios: %s", work_dir)
    shutil.rmtree(work_dir, ignore_errors=True)


def run_local_job(config: Config, source: Path, dest_dir: Path | None) -> list[Path]:
    """Processa um arquivo de audio local e copia as saidas para dest_dir
    (ou para a pasta do arquivo de origem, se dest_dir nao for informado).
    O arquivo de origem nunca e' removido."""
    config.ensure_dirs()
    source = source.resolve()
    dest_dir = (dest_dir or source.parent).resolve()
    source_ref = f"local:{source}"
    job_id = compute_job_id(source_ref)
    registry = ProcessedRegistry(config.state_file)

    output_stem = build_output_stem(source.stem, source.parent.name)
    transcript_path = dest_dir / f"{output_stem}.transcriptFC.txt"
    if transcript_path.exists() and not config.force:
        logger.info("Transcricao ja existe (%s), pulando: %s", transcript_path.name, source)
        return []

    work_dir = config.tmp_dir / job_id
    output_paths = process_file(
        config, input_path=source, output_stem=output_stem, work_dir=work_dir, source_ref=source_ref
    )

    dest_dir.mkdir(parents=True, exist_ok=True)
    final_paths = []
    for p in output_paths:
        dest_path = dest_dir / p.name
        shutil.copy2(p, dest_path)
        final_paths.append(dest_path)

    registry.mark_processed(job_id, source_ref, [str(p) for p in final_paths])
    cleanup_work_dir(work_dir, config.keep_temp)
    return final_paths


def run_dropbox_job(config: Config, dropbox_client, source_path: str, dest_folder: str | None) -> list[str]:
    """Processa um arquivo de audio no Dropbox: download -> pipeline -> upload
    das saidas -> limpeza dos temporarios. dest_folder default = mesma pasta
    do arquivo de origem."""
    config.ensure_dirs()
    source_ref = f"dropbox:{source_path}"
    job_id = compute_job_id(source_ref)
    registry = ProcessedRegistry(config.state_file)

    source_purepath = PurePosixPath(source_path)
    stem = build_output_stem(source_purepath.stem, source_purepath.parent.name)
    dest_folder = dest_folder or str(source_purepath.parent)
    if dest_folder != "/":
        dest_folder = dest_folder.rstrip("/")

    transcript_remote_path = f"{dest_folder}/{stem}.transcriptFC.txt"
    if not config.force and dropbox_client.file_exists(transcript_remote_path):
        logger.info("Transcricao ja existe (%s), pulando: %s", transcript_remote_path, source_path)
        return []

    lock_remote_path = f"{dest_folder}/{stem}.transcriptFC.lock"
    if not config.force:
        lock_content = dropbox_client.read_text_file(lock_remote_path)
        if lock_content and not _is_lock_stale(lock_content):
            logger.info(
                "Ja esta sendo processado por outra maquina (%s), pulando: %s",
                lock_content,
                source_path,
            )
            return []
        if lock_content:
            logger.warning(
                "Lock antigo encontrado (%s) - assumindo abandonado e prosseguindo: %s",
                lock_content,
                source_path,
            )

    dropbox_client.ensure_folder(dest_folder)
    dropbox_client.write_text_file(lock_remote_path, _make_lock_content())
    try:
        work_dir = config.tmp_dir / job_id
        state = JobState(job_id=job_id, source_ref=source_ref, work_dir=work_dir)
        state.load()

        local_input = work_dir / Path(source_path).name
        if not state.is_done("downloaded"):
            dropbox_client.download_file(source_path, local_input)
            state.mark_done("downloaded")
        else:
            logger.info("[%s] Download ja concluido, pulando.", job_id)

        output_paths = process_file(
            config, input_path=local_input, output_stem=stem, work_dir=work_dir, source_ref=source_ref
        )

        if not state.is_done("uploaded"):
            uploaded = []
            for p in output_paths:
                remote_path = f"{dest_folder}/{p.name}"
                dropbox_client.upload_file(p, remote_path)
                uploaded.append(remote_path)
            state.mark_done("uploaded", uploaded=uploaded)
        else:
            uploaded = state.data["uploaded"]
            logger.info("[%s] Upload ja concluido, pulando.", job_id)

        registry.mark_processed(job_id, source_ref, uploaded)
        cleanup_work_dir(work_dir, config.keep_temp)
        return uploaded
    finally:
        dropbox_client.delete_file(lock_remote_path)


def _iter_local_audio_files(source_dir: Path, recursive: bool) -> list[Path]:
    pattern_fn = source_dir.rglob if recursive else source_dir.glob
    files = [
        p for p in pattern_fn("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    ]
    return sorted(files)


def run_local_batch(
    config: Config, source_dir: Path, dest_dir: Path | None, recursive: bool = False
) -> dict[str, list]:
    """Processa todos os arquivos de audio de um diretorio local. Continua
    para o proximo arquivo mesmo se um deles falhar; retorna um resumo com
    os arquivos processados, pulados (ja concluidos) e com erro."""
    source_dir = source_dir.resolve()
    files = _iter_local_audio_files(source_dir, recursive)
    logger.info("Encontrados %d arquivo(s) de audio em %s", len(files), source_dir)

    summary: dict[str, list] = {"processed": [], "skipped": [], "failed": []}
    for i, audio_path in enumerate(files, start=1):
        logger.info("--- Arquivo %d/%d: %s ---", i, len(files), audio_path.name)
        try:
            outputs = run_local_job(config, audio_path, dest_dir)
        except Exception:
            logger.exception("Falha ao processar %s, continuando com os demais.", audio_path)
            summary["failed"].append(str(audio_path))
            continue
        if outputs:
            summary["processed"].append(str(audio_path))
        else:
            summary["skipped"].append(str(audio_path))
    return summary


def run_dropbox_batch(
    config: Config,
    dropbox_client,
    source_folder: str,
    dest_folder: str | None,
    recursive: bool = False,
) -> dict[str, list]:
    """Processa todos os arquivos de audio de uma pasta do Dropbox. Continua
    para o proximo arquivo mesmo se um deles falhar; retorna um resumo com
    os arquivos processados, pulados (ja concluidos) e com erro."""
    files = dropbox_client.list_audio_files(source_folder, recursive=recursive)
    logger.info("Encontrados %d arquivo(s) de audio em %s", len(files), source_folder)

    summary: dict[str, list] = {"processed": [], "skipped": [], "failed": []}
    for i, audio_path in enumerate(files, start=1):
        logger.info("--- Arquivo %d/%d: %s ---", i, len(files), audio_path)
        try:
            outputs = run_dropbox_job(config, dropbox_client, audio_path, dest_folder)
        except Exception:
            logger.exception("Falha ao processar %s, continuando com os demais.", audio_path)
            summary["failed"].append(audio_path)
            continue
        if outputs:
            summary["processed"].append(audio_path)
        else:
            summary["skipped"].append(audio_path)
    return summary
