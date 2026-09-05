from __future__ import annotations

import logging
import wave
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("supertranscriptfc")


@dataclass
class SpeakerTurn:
    start: float
    end: float
    speaker: str  # rotulo bruto do pyannote, ex: "SPEAKER_00"


def _load_wav_as_waveform(wav_path: Path):
    """Le um WAV mono PCM16 (o formato que convert_to_wav sempre gera) e
    devolve (waveform, sample_rate) prontos para o pyannote. Usa so' o
    modulo 'wave' da biblioteca padrao para evitar depender do torchcodec,
    que o proprio pyannote.audio/torchaudio exigiriam para abrir o arquivo
    sozinhos e que costuma falhar por incompatibilidade com o FFmpeg do
    sistema (visto na leno18)."""
    import numpy as np
    import torch

    with wave.open(str(wav_path), "rb") as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    if sample_width != 2:
        raise RuntimeError(
            f"Formato de audio inesperado (sample_width={sample_width} bytes); "
            "esperado PCM16 (o que convert_to_wav sempre gera)."
        )

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels > 1:
        samples = samples.reshape(-1, n_channels).T
    else:
        samples = samples.reshape(1, -1)

    waveform = torch.from_numpy(samples.copy())
    return waveform, sample_rate


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
    from pyannote.audio.pipelines.utils.hook import ProgressHook
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

    waveform, sample_rate = _load_wav_as_waveform(wav_path)
    audio_input = {"waveform": waveform, "sample_rate": sample_rate}

    with ProgressHook() as hook:
        result = pipeline(audio_input, hook=hook, **kwargs)
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
