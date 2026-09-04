from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("supertranscriptfc")


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


def _pick_device_and_compute_type(device: str, compute_type: str) -> tuple[str, str]:
    if device != "auto":
        resolved_device = device
    else:
        # ctranslate2 (usado pelo faster-whisper) so' suporta CPU e CUDA, sem
        # MPS: em Apple Silicon (ex: MacBook Air M1) o resultado cai para CPU.
        try:
            import torch

            resolved_device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            resolved_device = "cpu"

    if compute_type != "auto":
        resolved_compute_type = compute_type
    else:
        resolved_compute_type = "float16" if resolved_device == "cuda" else "int8"

    return resolved_device, resolved_compute_type


def transcribe_audio(
    wav_path: Path,
    model_size: str = "large-v3",
    device: str = "auto",
    compute_type: str = "auto",
    language: str | None = None,
) -> list[TranscriptSegment]:
    """Transcreve um WAV usando faster-whisper. Import de faster_whisper e' feito
    aqui dentro para nao exigir a dependencia pesada so' para importar o pacote."""
    from faster_whisper import WhisperModel

    resolved_device, resolved_compute_type = _pick_device_and_compute_type(device, compute_type)
    logger.info(
        "Transcrevendo com faster-whisper (model=%s, device=%s, compute_type=%s)",
        model_size,
        resolved_device,
        resolved_compute_type,
    )

    model = WhisperModel(model_size, device=resolved_device, compute_type=resolved_compute_type)
    segments_iter, info = model.transcribe(
        str(wav_path),
        language=language,
        vad_filter=True,
    )
    logger.info(
        "Idioma detectado: %s (probabilidade %.2f)",
        info.language,
        getattr(info, "language_probability", 0.0),
    )

    segments = [
        TranscriptSegment(start=seg.start, end=seg.end, text=seg.text.strip())
        for seg in segments_iter
    ]
    logger.info("Transcricao concluida: %d segmentos", len(segments))
    return segments
