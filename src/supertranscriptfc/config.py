from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma", ".mp4", ".mov")


@dataclass
class Config:
    home_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("SUPERTRANSCRIPTFC_HOME") or Path.home() / ".supertranscriptfc"
        )
    )
    dropbox_app_key: str | None = field(default_factory=lambda: os.environ.get("DROPBOX_APP_KEY"))
    dropbox_app_secret: str | None = field(default_factory=lambda: os.environ.get("DROPBOX_APP_SECRET"))
    dropbox_refresh_token: str | None = field(
        default_factory=lambda: os.environ.get("DROPBOX_REFRESH_TOKEN")
    )
    hf_token: str | None = field(default_factory=lambda: os.environ.get("HF_TOKEN"))

    @property
    def has_dropbox_credentials(self) -> bool:
        return bool(self.dropbox_app_key and self.dropbox_app_secret and self.dropbox_refresh_token)

    model_size: str = "large-v3"
    device: str = "auto"  # auto | cpu | cuda
    compute_type: str = "auto"
    language: str | None = None  # None = deteccao automatica

    min_speakers: int | None = None
    max_speakers: int | None = None

    min_minutes: float | None = None  # ignora audios mais curtos que isso
    max_minutes: float | None = None  # ignora audios mais longos que isso

    write_txt: bool = True
    write_srt: bool = True
    write_vtt: bool = False

    keep_temp: bool = False
    force: bool = False

    @property
    def tmp_dir(self) -> Path:
        return self.home_dir / "tmp"

    @property
    def logs_dir(self) -> Path:
        return self.home_dir / "logs"

    @property
    def models_dir(self) -> Path:
        return self.home_dir / "models"

    @property
    def state_file(self) -> Path:
        return self.home_dir / "processed_files.json"

    def ensure_dirs(self) -> None:
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._pin_model_cache_dirs()

    def _pin_model_cache_dirs(self) -> None:
        """Forca todo download de modelo (faster-whisper via huggingface_hub,
        pyannote/torch) a ficar dentro de home_dir/models. Cada maquina baixa
        e mantem sua propria copia local, sem nada compartilhado pela rede."""
        hf_cache = self.models_dir / "huggingface"
        torch_cache = self.models_dir / "torch"
        hf_cache.mkdir(parents=True, exist_ok=True)
        torch_cache.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(hf_cache))
        os.environ.setdefault("HF_HUB_CACHE", str(hf_cache / "hub"))
        os.environ.setdefault("TORCH_HOME", str(torch_cache))
