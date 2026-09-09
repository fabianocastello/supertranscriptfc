from __future__ import annotations

import re

_LEADING_NUMBER_RE = re.compile(r"^(\d+)([_\-\s].*)$")

EPISODE_NUMBER_WIDTH = 4


def _zero_pad_leading_number(name: str, width: int = EPISODE_NUMBER_WIDTH) -> str:
    match = _LEADING_NUMBER_RE.match(name)
    if not match:
        return name
    number, rest = match.groups()
    return f"{number.zfill(width)}{rest}"


def build_output_stem(file_stem: str, parent_folder_name: str | None) -> str:
    """Base filename for the output files (.txt/.srt/.vtt).

    Many podcast audio files are saved as 'audio.mp3' inside a folder named
    with the episode number and title (e.g. '28_20260117 Title'). In that
    case the folder name is used instead of the generic filename. Either
    way, a leading episode number is always zero-padded (e.g. 28 -> 0028)
    so files sort correctly."""
    base = file_stem
    if parent_folder_name and _LEADING_NUMBER_RE.match(parent_folder_name):
        base = parent_folder_name
    return _zero_pad_leading_number(base)
