from __future__ import annotations

import re
from pathlib import Path

from .merge import LabeledSegment

_TIMESTAMP_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})")


def _parse_timestamp(text: str) -> float | None:
    match = _TIMESTAMP_RE.search(text)
    if not match:
        return None
    hours, minutes, seconds, millis = (int(g) for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


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


def _format_yaml_value(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def format_front_matter(metadata: dict) -> str:
    """YAML front-matter block, with 'system' always as the first field
    (dict insertion order is preserved)."""
    lines = ["---"]
    lines.extend(f"{key}: {_format_yaml_value(value)}" for key, value in metadata.items())
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def write_txt(segments: list[LabeledSegment], path: Path, metadata: dict | None = None) -> Path:
    """Running text, grouping consecutive lines from the same speaker. If
    'metadata' is given, prefixes the file with a YAML front-matter block."""
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

    front_matter = format_front_matter(metadata) if metadata else ""
    path.write_text(front_matter + "\n\n".join(lines) + "\n", encoding="utf-8")
    return path


def parse_subtitle_text(text: str) -> list[tuple[float, float, str]]:
    """Parses SRT or WebVTT content into a list of (start, end, text)
    segments. Tolerant of both formats: numeric cue indexes (SRT) and the
    'WEBVTT' header line (if present) are simply skipped, since neither
    contains a '-->' timestamp arrow."""
    segments: list[tuple[float, float, str]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            start_str, _, end_str = line.partition("-->")
            start = _parse_timestamp(start_str)
            end = _parse_timestamp(end_str)
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            if start is not None and end is not None and text_lines:
                segments.append((start, end, " ".join(text_lines)))
        else:
            i += 1
    return segments


def write_plain_txt(
    segments: list[tuple[float, float, str]], path: Path, metadata: dict | None = None
) -> Path:
    """Writes plain running text from (start, end, text) segments with no
    speaker attribution - used when reusing a pre-existing transcript (e.g.
    Dropbox's own automatic transcription) that carries no diarization
    info to attach to each line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = " ".join(text for _, _, text in segments if text)
    front_matter = format_front_matter(metadata) if metadata else ""
    path.write_text(front_matter + body + "\n", encoding="utf-8")
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
