from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

from .progress import ProgressPrinter

logger = logging.getLogger("supertranscriptfc")


def _ensure_cuda_libs_on_path() -> None:
    """O ctranslate2 (motor do faster-whisper) carrega libcublas/libcudnn via
    dlopen em runtime; o wheel do torch nao expõe essas libs no PATH padrao.
    Se os pacotes nvidia-cublas-cu12/nvidia-cudnn-cu12 estiverem instalados
    (extra 'cuda'), adiciona seus diretorios de lib ao LD_LIBRARY_PATH antes
    de importar o backend, para nao exigir nenhuma configuracao manual."""
    lib_dirs = []
    for module_name in ("nvidia.cublas.lib", "nvidia.cudnn.lib"):
        try:
            module = import_module(module_name)
        except ImportError:
            continue
        if hasattr(module, "__path__"):
            module_dir = Path(module.__path__[0])
        else:
            module_dir = Path(module.__file__).parent
        lib_dirs.append(str(module_dir))

    if not lib_dirs:
        return
    current = os.environ.get("LD_LIBRARY_PATH", "")
    combined = ":".join(lib_dirs + ([current] if current else []))
    os.environ["LD_LIBRARY_PATH"] = combined


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
    _ensure_cuda_libs_on_path()
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

    total_duration = getattr(info, "duration", None) or 0.0
    progress = ProgressPrinter("Transcrevendo", total_duration)
    segments = []
    for seg in segments_iter:
        segments.append(TranscriptSegment(start=seg.start, end=seg.end, text=seg.text.strip()))
        progress.update(seg.end)
    progress.finish()

    logger.info("Transcricao concluida: %d segmentos", len(segments))
    return segments
