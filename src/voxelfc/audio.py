from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class FFmpegNotFoundError(RuntimeError):
    pass


def _require_ffmpeg(binary: str) -> None:
    if shutil.which(binary) is None:
        raise FFmpegNotFoundError(
            f"'{binary}' not found in PATH. Install FFmpeg before continuing."
        )


def convert_to_wav(input_path: Path, output_path: Path, sample_rate: int = 16000) -> Path:
    """Converts any audio/video format supported by FFmpeg into mono PCM16
    WAV, the format expected by faster-whisper and pyannote.audio."""
    _require_ffmpeg("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to convert audio with ffmpeg:\n{result.stderr}")
    return output_path


def probe_duration_seconds(path: Path) -> float:
    _require_ffmpeg("ffprobe")
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to inspect audio with ffprobe:\n{result.stderr}")
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])
