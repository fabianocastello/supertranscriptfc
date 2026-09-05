from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("supertranscriptfc")


@dataclass
class SpeakerTurn:
    start: float
    end: float
    speaker: str  # rotulo bruto do pyannote, ex: "SPEAKER_00"


def diarize_audio(
    wav_path: Path,
    hf_token: str | None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> list[SpeakerTurn]:
    """Executa diarizacao com pyannote.audio. Import feito aqui dentro para nao
    exigir torch/pyannote so' para importar o pacote."""
    if not hf_token:
        raise RuntimeError(
            "HF_TOKEN nao configurado. E' necessario um token do Hugging Face com acesso "
            "aos modelos pyannote/speaker-diarization-3.1 e pyannote/segmentation-3.0."
        )

    from pyannote.audio import Pipeline
    import torch

    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"  # Apple Silicon (ex: MacBook Air M1)
    else:
        device = "cpu"
    logger.info("Executando diarizacao com pyannote.audio (device=%s)", device)

    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=hf_token)
    pipeline.to(torch.device(device))

    kwargs = {}
    if min_speakers is not None:
        kwargs["min_speakers"] = min_speakers
    if max_speakers is not None:
        kwargs["max_speakers"] = max_speakers

    result = pipeline(str(wav_path), **kwargs)
    # pyannote.audio >= 4 retorna um DiarizeOutput com o Annotation em
    # .speaker_diarization; versoes anteriores retornam o Annotation direto.
    annotation = getattr(result, "speaker_diarization", result)

    turns = [
        SpeakerTurn(start=turn.start, end=turn.end, speaker=speaker)
        for turn, _, speaker in annotation.itertracks(yield_label=True)
    ]
    n_speakers = len({t.speaker for t in turns})
    logger.info("Diarizacao concluida: %d turnos, %d locutores detectados", len(turns), n_speakers)
    return turns
