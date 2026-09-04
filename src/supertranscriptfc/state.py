from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

STAGES = (
    "downloaded",
    "converted",
    "transcribed",
    "diarized",
    "merged",
    "outputs_written",
    "uploaded",
    "cleaned",
)

_registry_lock = threading.Lock()


def compute_job_id(source_ref: str) -> str:
    """ID estavel derivado do caminho de origem (Dropbox ou local)."""
    return hashlib.sha256(source_ref.encode("utf-8")).hexdigest()[:16]


@dataclass
class JobState:
    job_id: str
    source_ref: str
    work_dir: Path
    completed_stages: set[str] = field(default_factory=set)
    data: dict = field(default_factory=dict)

    @property
    def progress_file(self) -> Path:
        return self.work_dir / "progress.json"

    def load(self) -> None:
        if self.progress_file.exists():
            raw = json.loads(self.progress_file.read_text(encoding="utf-8"))
            self.completed_stages = set(raw.get("completed_stages", []))
            self.data = raw.get("data", {})

    def save(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file.write_text(
            json.dumps(
                {
                    "job_id": self.job_id,
                    "source_ref": self.source_ref,
                    "completed_stages": sorted(self.completed_stages),
                    "data": self.data,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def is_done(self, stage: str) -> bool:
        return stage in self.completed_stages

    def mark_done(self, stage: str, **extra) -> None:
        self.completed_stages.add(stage)
        if extra:
            self.data.update(extra)
        self.save()


class ProcessedRegistry:
    """Registro persistente (fora do tmp_dir) dos arquivos ja concluidos,
    para nao reprocessar mesmo depois da limpeza dos temporarios."""

    def __init__(self, state_file: Path):
        self.state_file = state_file

    def _read(self) -> dict:
        if not self.state_file.exists():
            return {}
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def is_processed(self, job_id: str) -> bool:
        return job_id in self._read()

    def mark_processed(self, job_id: str, source_ref: str, outputs: list[str]) -> None:
        with _registry_lock:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            data = self._read()
            data[job_id] = {
                "source_ref": source_ref,
                "outputs": outputs,
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            self.state_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
