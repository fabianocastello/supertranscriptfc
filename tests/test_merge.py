from voxelfc.diarize import SpeakerTurn
from voxelfc.merge import UNKNOWN_SPEAKER_LABEL, assign_speakers
from voxelfc.transcribe import TranscriptSegment


def test_assign_speakers_maps_to_generic_labels_in_order_of_appearance():
    segments = [
        TranscriptSegment(start=0.0, end=1.0, text="oi"),
        TranscriptSegment(start=1.0, end=2.0, text="tudo bem"),
        TranscriptSegment(start=2.0, end=3.0, text="sim e voce"),
    ]
    turns = [
        SpeakerTurn(start=0.0, end=1.0, speaker="SPEAKER_01"),
        SpeakerTurn(start=1.0, end=2.0, speaker="SPEAKER_00"),
        SpeakerTurn(start=2.0, end=3.0, speaker="SPEAKER_01"),
    ]
    labeled = assign_speakers(segments, turns)
    assert [s.speaker for s in labeled] == ["Pessoa 1", "Pessoa 2", "Pessoa 1"]


def test_assign_speakers_handles_no_overlap():
    segments = [TranscriptSegment(start=10.0, end=11.0, text="oi")]
    turns = [SpeakerTurn(start=0.0, end=1.0, speaker="SPEAKER_00")]
    labeled = assign_speakers(segments, turns)
    assert labeled[0].speaker == UNKNOWN_SPEAKER_LABEL


def test_assign_speakers_skips_empty_text():
    segments = [TranscriptSegment(start=0.0, end=1.0, text="")]
    turns = [SpeakerTurn(start=0.0, end=1.0, speaker="SPEAKER_00")]
    assert assign_speakers(segments, turns) == []
