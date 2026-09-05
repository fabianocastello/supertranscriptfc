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
    """Nome base para os arquivos de saida (.txt/.srt/.vtt).

    Muitos audios de podcast estao salvos como 'audio.mp3' dentro de uma
    pasta com o numero e titulo do episodio (ex: '28_20260117 Titulo').
    Nesse caso usamos o nome da pasta em vez do nome generico do arquivo.
    Em qualquer caso, um numero de episodio no inicio do nome e' sempre
    zero-preenchido (ex: 28 -> 0028), para ordenar corretamente."""
    base = file_stem
    if parent_folder_name and _LEADING_NUMBER_RE.match(parent_folder_name):
        base = parent_folder_name
    return _zero_pad_leading_number(base)
