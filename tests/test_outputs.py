from pathlib import Path

from voxelfc.merge import LabeledSegment
from voxelfc.outputs import format_front_matter, write_srt, write_txt, write_vtt


def make_segments():
    return [
        LabeledSegment(start=0.0, end=1.5, text="Hi, how are you?", speaker="Person 1"),
        LabeledSegment(start=1.6, end=3.0, text="I'm good, and you?", speaker="Person 2"),
        LabeledSegment(start=3.1, end=4.0, text="I'm good too.", speaker="Person 2"),
    ]


def test_write_txt_groups_consecutive_same_speaker(tmp_path: Path):
    out = write_txt(make_segments(), tmp_path / "out.txt")
    content = out.read_text(encoding="utf-8")
    assert content == (
        "Person 1: Hi, how are you?\n\n"
        "Person 2: I'm good, and you? I'm good too.\n"
    )


def test_write_txt_without_metadata_has_no_front_matter(tmp_path: Path):
    out = write_txt(make_segments(), tmp_path / "out.txt")
    content = out.read_text(encoding="utf-8")
    assert not content.startswith("---")


def test_write_txt_with_metadata_prepends_yaml_front_matter(tmp_path: Path):
    metadata = {
        "system": "VOXEL FC",
        "audio_file": "audio.mp3",
        "processed_date": "2026-09-07",
        "running_on": "thor25",
        "speakers_detected": 2,
    }
    out = write_txt(make_segments(), tmp_path / "out.txt", metadata=metadata)
    content = out.read_text(encoding="utf-8")

    lines = content.splitlines()
    assert lines[0] == "---"
    assert lines[1] == 'system: "VOXEL FC"'
    assert 'audio_file: "audio.mp3"' in content
    assert 'running_on: "thor25"' in content
    assert "speakers_detected: 2" in content
    assert content.count("---") == 2
    assert "Person 1: Hi, how are you?" in content


def test_format_front_matter_preserves_dict_insertion_order():
    # "system" comes first because the caller (pipeline.py) inserts it
    # first; format_front_matter only preserves order, it doesn't reorder.
    front_matter = format_front_matter({"system": "VOXEL FC", "other": "x"})
    lines = front_matter.splitlines()
    assert lines[0] == "---"
    assert lines[1] == 'system: "VOXEL FC"'
    assert lines[2] == 'other: "x"'


def test_write_srt_format(tmp_path: Path):
    out = write_srt(make_segments(), tmp_path / "out.srt")
    content = out.read_text(encoding="utf-8")
    assert "1\n00:00:00,000 --> 00:00:01,500\nPerson 1: Hi, how are you?" in content
    assert "2\n00:00:01,600 --> 00:00:03,000\nPerson 2: I'm good, and you?" in content


def test_write_vtt_format(tmp_path: Path):
    out = write_vtt(make_segments(), tmp_path / "out.vtt")
    content = out.read_text(encoding="utf-8")
    assert content.startswith("WEBVTT\n")
    assert "00:00:00.000 --> 00:00:01.500\nPerson 1: Hi, how are you?" in content
