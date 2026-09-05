# Instalador do SuperTranscriptFC para Windows (ex: ps20).
# Cada maquina roda de forma totalmente independente: venv proprio, modelos
# proprios em $HOME\.supertranscriptfc\models. Nada e' compartilhado pela rede.

$ErrorActionPreference = "Stop"

$RepoDir = Split-Path -Parent $PSScriptRoot
Set-Location $RepoDir

Write-Host "== SuperTranscriptFC: instalacao (Windows) =="

# --- 1. Verificar Python 3.10+ ---
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python nao encontrado no PATH. Instale o Python 3.10+ (python.org ou winget install Python.Python.3.12) antes de continuar."
    exit 1
}

# --- 2. Verificar FFmpeg ---
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
    Write-Warning "FFmpeg nao encontrado."
    Write-Host "Instale com: winget install Gyan.FFmpeg   (ou choco install ffmpeg)"
    exit 1
}

# --- 3. Criar venv ---
if (-not (Test-Path ".venv")) {
    Write-Host "Criando ambiente virtual em .venv ..."
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip -q

# --- 4. Detectar GPU NVIDIA (CUDA) ---
$Extras = "dropbox,transcribe,diarize"
$hasNvidia = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($hasNvidia) {
    Write-Host "GPU NVIDIA detectada: instalando com suporte a CUDA."
    $Extras = "$Extras,cuda"
} else {
    Write-Host "Nenhuma GPU NVIDIA detectada (ex: ps20): instalando torch/torchaudio/torchcodec CPU-only (menor download)."
    pip install -q --index-url https://download.pytorch.org/whl/cpu torch torchaudio torchcodec
}

Write-Host "Instalando o pacote (extras: $Extras) ..."
pip install -q -e ".[$Extras]"

# --- 5. Criar .env a partir do exemplo, se necessario ---
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Arquivo .env criado a partir de .env.example. Preencha DROPBOX_ACCESS_TOKEN e HF_TOKEN."
}

Write-Host ""
Write-Host "Instalacao concluida nesta maquina."
Write-Host "Modelos e cache ficarao em: $HOME\.supertranscriptfc\models"
Write-Host "Para usar:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  supertranscriptfc --source C:\caminho\audio.mp3 --local"
