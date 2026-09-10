# Shared by install.sh and update.sh: detects which optional-dependency
# extras this machine needs and sets $EXTRAS accordingly. Must be sourced
# (not executed) - relies on the caller having already set EXTRAS_PYTHON
# to a working "python -m pip" (defaults to bare "python", which is only
# correct once the venv is active on PATH).
#
# Only relevant on Linux/Windows: on macOS, torch from PyPI already ships
# without CUDA (runs on CPU, with MPS acceleration where supported) and the
# /whl/cpu index doesn't publish wheels for macOS/arm64.
EXTRAS_PYTHON="${EXTRAS_PYTHON:-python}"
OS="$(uname -s)"

EXTRAS="dropbox,transcribe,diarize"
if [ "$OS" = "Darwin" ]; then
    echo "macOS detected: torch already runs on CPU/MPS, no special index needed."
    if [ "$(uname -m)" = "arm64" ]; then
        echo "Apple Silicon detected: adding mlx-whisper (GPU/Neural Engine transcription)."
        EXTRAS="${EXTRAS},mlx"
    fi
elif command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    echo "NVIDIA GPU detected: installing with CUDA support."
    EXTRAS="${EXTRAS},cuda"
else
    echo "No NVIDIA GPU detected: installing CPU-only torch/torchaudio (smaller download)."
    # torchaudio (a pyannote.audio dependency) also needs to come from the CPU
    # variant: the default PyPI wheel loads a native extension linked against
    # libcudart, which fails to import on machines without CUDA installed.
    "$EXTRAS_PYTHON" -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch torchaudio || true
fi
