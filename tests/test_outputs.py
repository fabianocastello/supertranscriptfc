from pathlib import Path

from supertranscriptfc.merge import LabeledSegment
from supertranscriptfc.outputs import format_front_matter, write_srt, write_txt, write_vtt


def make_segments():
    return [
        LabeledSegment(start=0.0, end=1.5, text="Ola, tudo bem?", speaker="Pessoa 1"),
        LabeledSegment(start=1.6, end=3.0, text="Tudo bem, e voce?", speaker="Pessoa 2"),
        LabeledSegment(start=3.1, end=4.0, text="Tambem estou bem.", speaker="Pessoa 2"),
    ]


def test_write_txt_groups_consecutive_same_speaker(tmp_path: Path):
    out = write_txt(make_segments(), tmp_path / "out.txt")
    content = out.read_text(encoding="utf-8")
    assert content == (
        "Pessoa 1: Ola, tudo bem?\n\n"
        "Pessoa 2: Tudo bem, e voce? Tambem estou bem.\n"
    )


def test_write_txt_without_metadata_has_no_front_matter(tmp_path: Path):
    out = write_txt(make_segments(), tmp_path / "out.txt")
    content = out.read_text(encoding="utf-8")
    assert not content.startswith("---")


def test_write_txt_with_metadata_prepends_yaml_front_matter(tmp_path: Path):
    metadata = {
        "system": "SuperTranscriptFC",
        "audio_file": "audio.mp3",
        "processado": "2026-09-07",
        "running_on": "thor25",
        "locutores_detectados": 2,
    }
    out = write_txt(make_segments(), tmp_path / "out.txt", metadata=metadata)
    content = out.read_text(encoding="utf-8")

    lines = content.splitlines()
    assert lines[0] == "---"
    assert lines[1] == 'system: "SuperTranscriptFC"'
    assert 'audio_file: "audio.mp3"' in content
    assert 'running_on: "thor25"' in content
    assert "locutores_detectados: 2" in content
    assert content.count("---") == 2
    assert "Pessoa 1: Ola, tudo bem?" in content


def test_format_front_matter_preserves_dict_insertion_order():
    # "system" deve vir primeiro porque quem monta o dict (pipeline.py) o
    # insere primeiro; format_front_matter so' preserva a ordem, nao reordena.
    front_matter = format_front_matter({"system": "SuperTranscriptFC", "other": "x"})
    lines = front_matter.splitlines()
    assert lines[0] == "---"
    assert lines[1] == 'system: "SuperTranscriptFC"'
    assert lines[2] == 'other: "x"'


def test_write_srt_format(tmp_path: Path):
    out = write_srt(make_segments(), tmp_path / "out.srt")
    content = out.read_text(encoding="utf-8")
    assert "1\n00:00:00,000 --> 00:00:01,500\nPessoa 1: Ola, tudo bem?" in content
    assert "2\n00:00:01,600 --> 00:00:03,000\nPessoa 2: Tudo bem, e voce?" in content


def test_write_vtt_format(tmp_path: Path):
    out = write_vtt(make_segments(), tmp_path / "out.vtt")
    content = out.read_text(encoding="utf-8")
    assert content.startswith("WEBVTT\n")
    assert "00:00:00.000 --> 00:00:01.500\nPessoa 1: Ola, tudo bem?" in content
