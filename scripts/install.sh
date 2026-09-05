#!/usr/bin/env bash
# Instalador do SuperTranscriptFC para Linux (thor25, leno18) e macOS (MacBook Air M1).
# Cada maquina roda de forma totalmente independente: venv proprio, modelos
# proprios em ~/.supertranscriptfc/models. Nada e' compartilhado pela rede.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

OS="$(uname -s)"

echo "== SuperTranscriptFC: instalacao (${OS}) =="

# --- 1. Verificar Python 3.10+ ---
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python3 nao encontrado no PATH. Instale o Python 3.10+ antes de continuar." >&2
    exit 1
fi

# --- 2. Verificar FFmpeg ---
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "FFmpeg nao encontrado."
    if [ "$OS" = "Darwin" ]; then
        echo "Instale com: brew install ffmpeg"
    else
        echo "Instale com: sudo apt install ffmpeg   (ou o gerenciador de pacotes da sua distro)"
    fi
    exit 1
fi

# --- 3. Criar venv ---
if [ ! -d ".venv" ]; then
    echo "Criando ambiente virtual em .venv ..."
    "$PYTHON_BIN" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q

# --- 4. Detectar GPU NVIDIA (CUDA) ---
EXTRAS="dropbox,transcribe,diarize"
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    echo "GPU NVIDIA detectada: instalando com suporte a CUDA."
    EXTRAS="${EXTRAS},cuda"
else
    echo "Nenhuma GPU NVIDIA detectada: instalando torch CPU-only (menor download)."
    pip install -q --index-url https://download.pytorch.org/whl/cpu torch || true
fi

echo "Instalando o pacote (extras: ${EXTRAS}) ..."
pip install -q -e ".[${EXTRAS}]"

# --- 5. Criar .env a partir do exemplo, se necessario ---
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Arquivo .env criado a partir de .env.example. Preencha DROPBOX_ACCESS_TOKEN e HF_TOKEN."
fi

echo ""
echo "Instalacao concluida nesta maquina."
echo "Modelos e cache ficarao em: ~/.supertranscriptfc/models"
echo "Para usar:"
echo "  source .venv/bin/activate"
echo "  supertranscriptfc --source /caminho/audio.mp3 --local"
