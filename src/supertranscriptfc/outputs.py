from __future__ import annotations

from pathlib import Path

from .merge import LabeledSegment


def _format_srt_timestamp(seconds: float) -> str:
    millis_total = round(seconds * 1000)
    hours, rem = divmod(millis_total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_vtt_timestamp(seconds: float) -> str:
    millis_total = round(seconds * 1000)
    hours, rem = divmod(millis_total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def write_txt(segments: list[LabeledSegment], path: Path) -> Path:
    """Texto corrido, agrupando linhas consecutivas do mesmo locutor."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    current_speaker = None
    buffer: list[str] = []

    def flush() -> None:
        if current_speaker is not None and buffer:
            lines.append(f"{current_speaker}: {' '.join(buffer)}")

    for seg in segments:
        if seg.speaker != current_speaker:
            flush()
            buffer = []
            current_speaker = seg.speaker
        buffer.append(seg.text)
    flush()

    path.write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_srt(segments: list[LabeledSegment], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks: list[str] = []
    for i, seg in enumerate(segments, start=1):
        start = _format_srt_timestamp(seg.start)
        end = _format_srt_timestamp(seg.end)
        blocks.append(f"{i}\n{start} --> {end}\n{seg.speaker}: {seg.text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def write_vtt(segments: list[LabeledSegment], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks: list[str] = ["WEBVTT\n"]
    for seg in segments:
        start = _format_vtt_timestamp(seg.start)
        end = _format_vtt_timestamp(seg.end)
        blocks.append(f"{start} --> {end}\n{seg.speaker}: {seg.text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path
