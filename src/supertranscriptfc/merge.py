from __future__ import annotations

from dataclasses import dataclass

from .diarize import SpeakerTurn
from .transcribe import TranscriptSegment

UNKNOWN_SPEAKER_LABEL = "Pessoa ?"


@dataclass
class LabeledSegment:
    start: float
    end: float
    text: str
    speaker: str  # rotulo amigavel, ex: "Pessoa 1"


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def _best_speaker_for_segment(
    segment: TranscriptSegment, turns: list[SpeakerTurn]
) -> str | None:
    best_turn = None
    best_overlap = 0.0
    for turn in turns:
        ov = _overlap(segment.start, segment.end, turn.start, turn.end)
        if ov > best_overlap:
            best_overlap = ov
            best_turn = turn
    return best_turn.speaker if best_turn else None


def assign_speakers(
    transcript_segments: list[TranscriptSegment],
    diarization_turns: list[SpeakerTurn],
) -> list[LabeledSegment]:
    """Atribui a cada segmento transcrito o locutor com maior sobreposicao
    temporal, e renomeia os rotulos brutos do pyannote (SPEAKER_00, ...) para
    identificadores genericos e estaveis (Pessoa 1, Pessoa 2, ...) na ordem em
    que aparecem na fala."""
    friendly_names: dict[str, str] = {}

    def friendly(raw_label: str) -> str:
        if raw_label not in friendly_names:
            friendly_names[raw_label] = f"Pessoa {len(friendly_names) + 1}"
        return friendly_names[raw_label]

    labeled: list[LabeledSegment] = []
    for seg in transcript_segments:
        if not seg.text:
            continue
        raw_speaker = _best_speaker_for_segment(seg, diarization_turns)
        speaker = friendly(raw_speaker) if raw_speaker is not None else UNKNOWN_SPEAKER_LABEL
        labeled.append(LabeledSegment(start=seg.start, end=seg.end, text=seg.text, speaker=speaker))
    return labeled
