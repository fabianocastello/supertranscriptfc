# Instalação rápida — SuperTranscriptFC

Guia direto ao ponto para instalar em Linux, macOS ou Windows. Para detalhes,
uso avançado e solução de problemas mais a fundo, veja o [README](README.md).

Em qualquer plataforma, ao final você deve conseguir rodar:

```
supertranscriptfc --source /caminho/ou/pasta/de/audio --local --model-size small --language pt
```

---

## Linux (Debian/Ubuntu, ex: thor25, leno18)

```bash
sudo apt install -y python3-venv ffmpeg git
git clone https://github.com/fabianocastello/supertranscriptfc.git ~/supertranscriptfc
cd ~/supertranscriptfc
./scripts/install.sh
```

O `install.sh` detecta automaticamente se há GPU NVIDIA (`nvidia-smi`) e
instala o `torch` com CUDA nesse caso, ou a variante CPU-only caso contrário.

**Uso diário:**
```bash
source .venv/bin/activate
supertranscriptfc --source /caminho/audio.mp3 --local
```

---

## macOS (Apple Silicon, ex: MacBook Air M1)

**Antes de tudo**, confirme que o Homebrew é nativo arm64 (não uma instalação
x86_64 rodando via Rosetta 2 — isso já causou dor de cabeça real neste
projeto):

```bash
arch                          # deve mostrar "arm64"
ls /opt/homebrew/bin/brew     # deve existir
```

Se `/opt/homebrew/bin/brew` não existir, instale o Homebrew primeiro:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Se existir **outro** Homebrew em `/usr/local` com apps que você usa (iTerm2,
etc), **não o remova** — apenas ignore-o e use sempre o caminho completo
`/opt/homebrew/bin/brew` abaixo, para não misturar as duas instalações.

```bash
xcode-select --install                     # Command Line Tools, se ainda nao tiver
/opt/homebrew/bin/brew install python@3.12 ffmpeg
git clone https://github.com/fabianocastello/supertranscriptfc.git ~/supertranscriptfc
cd ~/supertranscriptfc
PYTHON_BIN=/opt/homebrew/bin/python3.12 ./scripts/install.sh
```

O `PYTHON_BIN` explícito garante que o ambiente virtual use o Python nativo
do Homebrew, e não uma instalação x86_64 ou do miniconda/Anaconda que
porventura já esteja ativa no seu shell.

**Uso diário:**
```bash
source .venv/bin/activate
supertranscriptfc --source ./audio.mp3 --local
```

A diarização (`pyannote.audio`) usa aceleração **MPS** automaticamente. A
transcrição (`faster-whisper`) roda em **CPU**, pois seu motor (`ctranslate2`)
não suporta MPS.

---

## Windows (ex: ps20)

**1. Python de verdade (não o alias da Microsoft Store):**
```powershell
winget install Python.Python.3.12
```
Depois, em **Configurações → Aplicativos → Configurações avançadas do
aplicativo → Aliases de execução do aplicativo**, desligue `python.exe` e
`python3.exe`. Feche e reabra o terminal, e confirme com `python --version`.

**2. Git:**
```powershell
winget install Git.Git
```

**3. Clonar e instalar:**
```powershell
git clone https://github.com/fabianocastello/supertranscriptfc.git C:\supertranscriptfc
cd C:\supertranscriptfc
scripts\install.bat
```
(`install.bat` funciona tanto no `cmd` quanto no PowerShell — é só um atalho
que chama `install.ps1` contornando a política de execução padrão.)

**Máquina antiga ou com PowerShell bloqueado por política?** Use
`scripts\install-legacy.bat` no lugar do passo acima — faz a mesma coisa,
mas em `cmd.exe` puro, sem chamar PowerShell em nenhum momento:
```cmd
scripts\install-legacy.bat
```

**Uso diário:**
```cmd
.venv\Scripts\activate.bat
```
```powershell
.venv\Scripts\Activate.ps1
```
```
supertranscriptfc --source .\audio.mp3 --local
```

---

## Configurar o `.env` (igual em todas as plataformas)

O instalador cria um `.env` a partir do `.env.example`. Preencha:

- **`DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN`** —
  credenciais do seu App Dropbox. Para gerar o `DROPBOX_REFRESH_TOKEN` (sem
  expiração), preencha primeiro `APP_KEY`/`APP_SECRET` e rode:
  ```bash
  python scripts/dropbox_oauth.py
  ```
  Ele abre uma URL de autorização, você aprova e cola o código de volta —
  o script já grava o refresh token no `.env` sozinho.

- **`HF_TOKEN`** — token do Hugging Face (fine-grained, preset **Read-Only**
  já basta). Antes de usar, aceite os termos de uso, logado com a mesma
  conta, em **todos** estes modelos (são gated):
  - `huggingface.co/pyannote/speaker-diarization-3.1`
  - `huggingface.co/pyannote/segmentation-3.0`
  - `huggingface.co/pyannote/speaker-diarization-community-1`

O mesmo `.env` (mesmas credenciais) deve ser copiado para todas as máquinas
onde o projeto for instalado — é o mesmo App Dropbox e a mesma conta
Hugging Face compartilhados entre elas.

## Testando

```bash
supertranscriptfc --source /caminho/audio_curto.mp3 --local --model-size small --language pt
```

Comece com `--model-size small` para validar rápido que tudo está
funcionando antes de usar `large-v3` (mais lento, principalmente sem GPU).
