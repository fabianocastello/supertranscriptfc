from pathlib import Path

from supertranscriptfc.state import JobState, ProcessedRegistry, compute_job_id


def test_compute_job_id_is_stable_and_deterministic():
    assert compute_job_id("dropbox:/a/b.mp3") == compute_job_id("dropbox:/a/b.mp3")
    assert compute_job_id("dropbox:/a/b.mp3") != compute_job_id("dropbox:/a/c.mp3")


def test_job_state_persists_and_reloads(tmp_path: Path):
    work_dir = tmp_path / "job1"
    state = JobState(job_id="job1", source_ref="local:/x.mp3", work_dir=work_dir)
    state.mark_done("converted")
    state.mark_done("transcribed", transcript=[{"start": 0, "end": 1, "text": "oi"}])

    reloaded = JobState(job_id="job1", source_ref="local:/x.mp3", work_dir=work_dir)
    reloaded.load()
    assert reloaded.is_done("converted")
    assert reloaded.is_done("transcribed")
    assert not reloaded.is_done("diarized")
    assert reloaded.data["transcript"][0]["text"] == "oi"


def test_processed_registry_round_trip(tmp_path: Path):
    registry = ProcessedRegistry(tmp_path / "processed.json")
    assert not registry.is_processed("job1")
    registry.mark_processed("job1", "local:/x.mp3", ["/out/x.txt"])
    assert registry.is_processed("job1")
    assert not registry.is_processed("job2")
