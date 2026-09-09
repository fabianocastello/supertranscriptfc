from voxelfc.diarize import SpeakerTurn
from voxelfc.merge import UNKNOWN_SPEAKER_LABEL, assign_speakers
from voxelfc.transcribe import TranscriptSegment


def test_assign_speakers_maps_to_generic_labels_in_order_of_appearance():
    segments = [
        TranscriptSegment(start=0.0, end=1.0, text="hi"),
        TranscriptSegment(start=1.0, end=2.0, text="how are you"),
        TranscriptSegment(start=2.0, end=3.0, text="good and you"),
    ]
    turns = [
        SpeakerTurn(start=0.0, end=1.0, speaker="SPEAKER_01"),
        SpeakerTurn(start=1.0, end=2.0, speaker="SPEAKER_00"),
        SpeakerTurn(start=2.0, end=3.0, speaker="SPEAKER_01"),
    ]
    labeled = assign_speakers(segments, turns)
    assert [s.speaker for s in labeled] == ["Person 1", "Person 2", "Person 1"]


def test_assign_speakers_handles_no_overlap():
    segments = [TranscriptSegment(start=10.0, end=11.0, text="hi")]
    turns = [SpeakerTurn(start=0.0, end=1.0, speaker="SPEAKER_00")]
    labeled = assign_speakers(segments, turns)
    assert labeled[0].speaker == UNKNOWN_SPEAKER_LABEL


def test_assign_speakers_skips_empty_text():
    segments = [TranscriptSegment(start=0.0, end=1.0, text="")]
    turns = [SpeakerTurn(start=0.0, end=1.0, speaker="SPEAKER_00")]
    assert assign_speakers(segments, turns) == []
