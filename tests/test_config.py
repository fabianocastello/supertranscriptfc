from pathlib import Path

import pytest

from voxelfc.config import resolve_home_dir


def test_explicit_voxelfc_home_wins(monkeypatch, tmp_path: Path):
    explicit = tmp_path / "explicit"
    monkeypatch.setenv("VOXELFC_HOME", str(explicit))
    monkeypatch.setenv("SUPERTRANSCRIPTFC_HOME", str(tmp_path / "legacy-explicit"))
    assert resolve_home_dir() == explicit


def test_legacy_environment_is_supported(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("VOXELFC_HOME", raising=False)
    legacy = tmp_path / "legacy-explicit"
    monkeypatch.setenv("SUPERTRANSCRIPTFC_HOME", str(legacy))
    with pytest.warns(DeprecationWarning):
        assert resolve_home_dir() == legacy


def test_existing_legacy_default_is_preserved(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("VOXELFC_HOME", raising=False)
    monkeypatch.delenv("SUPERTRANSCRIPTFC_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".supertranscriptfc").mkdir()
    with pytest.warns(UserWarning, match="legacy"):
        assert resolve_home_dir() == tmp_path / ".supertranscriptfc"


def test_new_default_is_voxelfc(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("VOXELFC_HOME", raising=False)
    monkeypatch.delenv("SUPERTRANSCRIPTFC_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert resolve_home_dir() == tmp_path / ".voxelfc"


def test_canonical_wins_when_both_defaults_exist(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("VOXELFC_HOME", raising=False)
    monkeypatch.delenv("SUPERTRANSCRIPTFC_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".voxelfc").mkdir()
    (tmp_path / ".supertranscriptfc").mkdir()
    with pytest.warns(UserWarning, match="Both"):
        assert resolve_home_dir() == tmp_path / ".voxelfc"
