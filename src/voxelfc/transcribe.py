from __future__ import annotations

import logging
import os
import platform
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

from .progress import ProgressPrinter

logger = logging.getLogger("voxelfc")

# faster-whisper's ctranslate2 backend only supports CPU/CUDA, not Metal, so
# transcription on Apple Silicon normally falls back to CPU. mlx-whisper
# (Apple's own MLX framework) runs the model on the GPU/Neural Engine
# instead and is reportedly 2-4x faster there - used automatically when
# installed on macOS arm64, with a safe fallback to faster-whisper on any
# failure (this path is NOT tested on real Apple Silicon hardware yet).
MLX_MODEL_REPOS = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v2": "mlx-community/whisper-large-v2-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
}


_MLX_MODEL_PATH_CACHE: dict[str, str] = {}


def _resolve_mlx_model_path(model_repo: str) -> str:
    """Resolves a HF repo id to its local cache directory once per process
    and reuses it, instead of passing the repo id straight to
    mlx_whisper.transcribe() on every call - which re-checks the Hub (a
    'Fetching files'/'Download complete' round-trip, even when nothing new
    needs downloading) on every single file in a batch."""
    if model_repo not in _MLX_MODEL_PATH_CACHE:
        from huggingface_hub import snapshot_download

        _MLX_MODEL_PATH_CACHE[model_repo] = snapshot_download(repo_id=model_repo)
    return _MLX_MODEL_PATH_CACHE[model_repo]


def _is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _mlx_available() -> bool:
    if not _is_apple_silicon():
        return False
    try:
        import_module("mlx_whisper")
        return True
    except ImportError:
        return False

# Whisper language codes that use a non-Latin script. When auto-detected
# (i.e. --language wasn't forced), these are translated straight to English
# instead of transcribed in the original script - see transcribe_audio().
NON_LATIN_LANGUAGES = frozenset(
    {
        "zh", "ja", "ko", "ar", "ru", "uk", "el", "he", "hi", "th", "bn", "fa", "ur",
        "hy", "ka", "am", "si", "km", "lo", "my", "bo", "gu", "pa", "ta", "te", "kn",
        "ml", "mr", "ne", "sa", "yi", "mk", "bg", "sr", "kk", "mn", "tg", "tt", "ba",
        "ps", "as",
    }
)


def _ensure_cuda_libs_on_path() -> None:
    """ctranslate2 (faster-whisper's backend) dlopens libcublas/libcudnn at
    runtime; the torch wheel doesn't expose these libs on the default PATH.
    If the nvidia-cublas-cu12/nvidia-cudnn-cu12 packages are installed (the
    'cuda' extra), adds their lib directories to LD_LIBRARY_PATH before
    importing the backend, so no manual configuration is required."""
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


def _transcribe_with_mlx(
    wav_path: Path, model_size: str, language: str | None
) -> tuple[list[TranscriptSegment], str, float | None, bool]:
    """Transcribes using mlx-whisper (Apple's MLX framework), which runs on
    the GPU/Neural Engine instead of CPU on Apple Silicon. Raises on any
    failure so the caller falls back to faster-whisper.

    UNTESTED on real Apple Silicon hardware as of this writing - this
    session has no access to a Mac. Needs validation before being trusted;
    the caller wraps this in a try/except specifically so a bug here can't
    break transcription, only forfeit the speedup.

    Unlike faster-whisper, mlx_whisper.transcribe() has no cheap
    detection-only mode (no lazy generator to leave unconsumed) - a
    language=None call already runs the full transcription. So the common
    case (no forced language, Latin script) costs a single pass, but a
    forced --language or a non-Latin auto-translate currently costs two
    full passes here (one to learn the real language, one for the actual
    output) - a possible follow-up optimization if mlx_whisper turns out to
    expose a lighter-weight detection call."""
    import mlx_whisper

    model_repo = MLX_MODEL_REPOS.get(model_size, model_size)  # a full HF repo can be passed directly
    logger.info("Transcribing with mlx-whisper (model=%s, device=Apple GPU/Neural Engine)", model_repo)
    model_path = _resolve_mlx_model_path(model_repo)

    # verbose=True prints each decoded segment to the console as it happens -
    # mlx_whisper.transcribe() otherwise blocks silently until the whole
    # file is done, with no progress feedback like faster-whisper's
    # segment-by-segment ProgressPrinter.
    detect_result = mlx_whisper.transcribe(
        str(wav_path), path_or_hf_repo=model_path, language=None, task="transcribe", verbose=True
    )
    detected_language = detect_result.get("language")
    # mlx_whisper doesn't expose a detection confidence the way
    # faster-whisper's language_probability does.
    detected_language_probability = None

    translated_to_english = False
    if language is not None:
        logger.info(
            "Forced language for transcription: %s (actual detected language: %s)",
            language,
            detected_language,
        )
        result = (
            detect_result
            if language == detected_language
            else mlx_whisper.transcribe(
                str(wav_path),
                path_or_hf_repo=model_path,
                language=language,
                task="transcribe",
                verbose=True,
            )
        )
    elif detected_language in NON_LATIN_LANGUAGES:
        translated_to_english = True
        logger.info(
            "Detected language %s uses a non-Latin script; translating to English instead of transcribing.",
            detected_language,
        )
        result = mlx_whisper.transcribe(
            str(wav_path),
            path_or_hf_repo=model_path,
            language=detected_language,
            task="translate",
            verbose=True,
        )
    else:
        logger.info("Detected language: %s", detected_language)
        result = detect_result

    segments = [
        TranscriptSegment(start=seg["start"], end=seg["end"], text=seg["text"].strip())
        for seg in result.get("segments", [])
    ]
    logger.info("Transcription complete: %d segments", len(segments))
    return segments, detected_language, detected_language_probability, translated_to_english


def _pick_device_and_compute_type(device: str, compute_type: str) -> tuple[str, str]:
    if device != "auto":
        resolved_device = device
    else:
        # ctranslate2 (used by faster-whisper) only supports CPU and CUDA,
        # no MPS: on Apple Silicon (e.g. MacBook Air M1) this falls back to CPU.
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


def _transcribe_with_faster_whisper(
    wav_path: Path,
    model_size: str,
    device: str,
    compute_type: str,
    language: str | None,
) -> tuple[list[TranscriptSegment], str, float | None, bool]:
    """Transcribes a WAV file with faster-whisper. faster_whisper is imported
    here rather than at module level so importing this module doesn't
    require the heavy dependency just to be loaded.

    Returns (segments, detected_language, detected_language_probability,
    translated_to_english).

    The detected language/probability always reflect the actual spoken
    language identified by the model - even when `language` forces a
    specific transcription language, since in that case faster-whisper
    skips detection entirely and hardcodes language_probability=1, which
    would be misleading to report as a real confidence value.

    When `language` is not forced and the detected language uses a
    non-Latin script (NON_LATIN_LANGUAGES), the audio is translated straight
    to English (Whisper's built-in translate task) instead of transcribed in
    the original script; translated_to_english reports whether this
    happened."""
    _ensure_cuda_libs_on_path()
    from faster_whisper import WhisperModel

    resolved_device, resolved_compute_type = _pick_device_and_compute_type(device, compute_type)
    logger.info(
        "Transcribing with faster-whisper (model=%s, device=%s, compute_type=%s)",
        model_size,
        resolved_device,
        resolved_compute_type,
    )

    model = WhisperModel(model_size, device=resolved_device, compute_type=resolved_compute_type)

    # Always run a cheap detection-only pass first: its segments are never
    # iterated, so this only pays for language identification, not a full
    # transcription. Needed both to report an honest language_probability
    # when a language is forced (see docstring) and, in auto mode, to decide
    # the task (transcribe vs translate) before the real call starts - a
    # single generation call can't switch task partway through.
    _, detect_info = model.transcribe(str(wav_path), language=None, vad_filter=True)
    detected_language = detect_info.language
    detected_language_probability = getattr(detect_info, "language_probability", None)

    translated_to_english = False
    if language is not None:
        transcribe_language = language
        task = "transcribe"
        logger.info(
            "Forced language for transcription: %s (actual detected language: %s, probability %.2f)",
            language,
            detected_language,
            detected_language_probability or 0.0,
        )
    elif detected_language in NON_LATIN_LANGUAGES:
        transcribe_language = detected_language
        task = "translate"
        translated_to_english = True
        logger.info(
            "Detected language %s uses a non-Latin script (probability %.2f); "
            "translating to English instead of transcribing.",
            detected_language,
            detected_language_probability or 0.0,
        )
    else:
        transcribe_language = detected_language
        task = "transcribe"
        logger.info(
            "Detected language: %s (probability %.2f)",
            detected_language,
            detected_language_probability or 0.0,
        )

    segments_iter, info = model.transcribe(
        str(wav_path),
        language=transcribe_language,
        task=task,
        vad_filter=True,
    )

    total_duration = getattr(info, "duration", None) or 0.0
    progress = ProgressPrinter("Transcribing", total_duration)
    segments = []
    for seg in segments_iter:
        segments.append(TranscriptSegment(start=seg.start, end=seg.end, text=seg.text.strip()))
        progress.update(seg.end)
    progress.finish()

    logger.info("Transcription complete: %d segments", len(segments))
    return segments, detected_language, detected_language_probability, translated_to_english


def transcribe_audio(
    wav_path: Path,
    model_size: str = "large-v3",
    device: str = "auto",
    compute_type: str = "auto",
    language: str | None = None,
) -> tuple[list[TranscriptSegment], str, float | None, bool]:
    """Transcribes a WAV file, returning (segments, detected_language,
    detected_language_probability, translated_to_english).

    On macOS/Apple Silicon with mlx-whisper installed, uses that instead of
    faster-whisper (GPU/Neural Engine instead of CPU-only, reportedly
    2-4x faster there) - falling back to faster-whisper automatically if
    mlx-whisper raises anything, so a problem with the MLX path costs the
    speedup, not correctness. device/compute_type are ignored on the MLX
    path (mlx-whisper always uses the GPU)."""
    if device == "auto" and compute_type == "auto" and _mlx_available():
        try:
            return _transcribe_with_mlx(wav_path, model_size, language)
        except Exception:
            logger.exception(
                "mlx-whisper failed, falling back to faster-whisper (CPU) for this file."
            )

    return _transcribe_with_faster_whisper(wav_path, model_size, device, compute_type, language)
