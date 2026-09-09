from __future__ import annotations

import logging
import wave
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("voxelfc")


@dataclass
class SpeakerTurn:
    start: float
    end: float
    speaker: str  # raw pyannote label, e.g. "SPEAKER_00"


def _load_wav_as_waveform(wav_path: Path):
    """Reads a mono PCM16 WAV (the format convert_to_wav always produces)
    and returns (waveform, sample_rate) ready for pyannote. Uses only the
    stdlib 'wave' module to avoid depending on torchcodec, which
    pyannote.audio/torchaudio would otherwise require to open the file
    themselves and which tends to fail from FFmpeg version incompatibility
    on the host system (seen on leno18)."""
    import numpy as np
    import torch

    with wave.open(str(wav_path), "rb") as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    if sample_width != 2:
        raise RuntimeError(
            f"Unexpected audio format (sample_width={sample_width} bytes); "
            "expected PCM16 (what convert_to_wav always produces)."
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
    """Runs diarization with pyannote.audio. Imported here rather than at
    module level so importing this module doesn't require torch/pyannote
    just to load the package."""
    if not hf_token:
        raise RuntimeError(
            "HF_TOKEN not configured. A Hugging Face token with access to the "
            "pyannote/speaker-diarization-3.1 and pyannote/segmentation-3.0 models is required."
        )

    from pyannote.audio import Pipeline
    from pyannote.audio.pipelines.utils.hook import ProgressHook
    import torch

    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"  # Apple Silicon (e.g. MacBook Air M1)
    else:
        device = "cpu"
    logger.info("Running diarization with pyannote.audio (device=%s)", device)

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
    # pyannote.audio >= 4 returns a DiarizeOutput with the Annotation in
    # .speaker_diarization; earlier versions return the Annotation directly.
    annotation = getattr(result, "speaker_diarization", result)

    turns = [
        SpeakerTurn(start=turn.start, end=turn.end, speaker=speaker)
        for turn, _, speaker in annotation.itertracks(yield_label=True)
    ]
    n_speakers = len({t.speaker for t in turns})
    logger.info("Diarization complete: %d turns, %d speakers detected", len(turns), n_speakers)
    return turns
