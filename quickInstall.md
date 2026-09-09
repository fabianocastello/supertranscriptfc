# Quick guide — VOXEL FC

Este guia cobre a instalação mínima e os comandos operacionais do projeto:

- processar áudios e gerar transcripts;
- consultar locks ativos no Dropbox;
- remover locks antigos com segurança.

Para a descrição completa do pipeline, veja o [README.md](README.md).

---

## 1. Pré-requisitos

### Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg git
```

### macOS (Apple Silicon)

Confirme que o terminal está usando o Homebrew nativo arm64:

```bash
arch
/opt/homebrew/bin/brew --version
```

Instale as dependências:

```bash
/opt/homebrew/bin/brew install python@3.12 ffmpeg git
```

### Windows

Instale Python 3.12 e Git:

```powershell
winget install Python.Python.3.12
winget install Git.Git
```

Confirme que `python` não é o alias da Microsoft Store:

```powershell
python --version
git --version
```

---

## 2. Instalar o projeto

### Linux/macOS

```bash
git clone https://github.com/fabianocastello/voxelfc.git ~/voxelfc
cd ~/voxelfc
./scripts/install.sh
source .venv/bin/activate
```

No macOS Apple Silicon, se houver mais de um Python instalado:

```bash
PYTHON_BIN=/opt/homebrew/bin/python3.12 ./scripts/install.sh
source .venv/bin/activate
```

### Windows

```powershell
git clone https://github.com/fabianocastello/voxelfc.git C:\voxelfc
cd C:\voxelfc
scripts\install.bat
.venv\Scripts\Activate.ps1
```

---

## 3. Configurar o `.env`

O instalador cria `.env` a partir de `.env.example`. Preencha estes campos:

```dotenv
DROPBOX_APP_KEY=...
DROPBOX_APP_SECRET=...
DROPBOX_REFRESH_TOKEN=...
HF_TOKEN=...
```

O `DROPBOX_REFRESH_TOKEN` é usado pelos comandos de auditoria e pelo pipeline.
Para gerar ou renovar o token:

```bash
python scripts/dropbox_oauth.py
```

Mantenha o `.env` local, fora do Git, e não coloque credenciais em logs ou relatórios.

---

## 4. Processar um áudio

Ative o ambiente virtual antes dos comandos:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Processar um arquivo local:

```bash
voxelfc --source /caminho/audio.mp3 --local
```

Processar um arquivo no Dropbox:

```bash
voxelfc --source /Gravacoes/reuniao.mp3
```

Teste inicial recomendado:

```bash
voxelfc \
  --source /caminho/audio_curto.mp3 \
  --local \
  --model-size small \
  --language pt
```

---

## 5. Consultar locks no Dropbox

O comando abaixo usa o `.env`, acessa a pasta remota e lista os locks com máquina,
arquivo, início e tempo decorrido:

```bash
python ./tools/status.py /_AudioMemosFC/MamyCalls
```

No Windows PowerShell, use o mesmo comando:

```powershell
python .\tools\status.py /_AudioMemosFC/MamyCalls
```

A consulta é somente leitura no Dropbox. Ela lê os locks e, quando a duração não está no
front matter do transcript, baixa temporariamente o áudio correspondente para medir a
duração com `ffprobe`; o arquivo temporário local é removido ao fim. Nenhum arquivo no
Dropbox é criado, alterado ou removido.

Exemplo de outra pasta:

```bash
python ./tools/status.py /Outra/Pasta
```

O caminho da pasta Dropbox deve começar com `/`.

---

## 6. Remover locks antigos

### Primeiro: simular

Sempre confira os candidatos antes de remover:

```bash
python ./tools/remove_locks.py \
  /_AudioMemosFC/MamyCalls \
  --older_than 10m \
  --dry-run
```

### Depois: remover

Se confirmar que os locks não correspondem a processos ainda executando:

```bash
python ./tools/remove_locks.py \
  /_AudioMemosFC/MamyCalls \
  --older_than 10m
```

A comparação é estrita: só são removidos locks com idade **maior** que o limite.
Locks sem data interpretável nunca são removidos automaticamente.

### Formatos aceitos

```text
30s    30 segundos
10m    10 minutos
1h     1 hora
2h     2 horas
```

### Formatos rejeitados

```text
10
10 m
1 hour
1d
```

O argumento precisa ser um número inteiro positivo seguido imediatamente por `s`, `m`
ou `h`:

```text
--older_than 30s
--older_than 10m
--older_than 1h
```

> Segurança: antes de apagar um lock, confirme na máquina indicada que não existe
> uma execução real correspondente. Remover um lock ativo pode permitir que outro
> processo inicie o mesmo áudio em paralelo.

---

## 7. Auditoria completa

Para gerar o relatório completo — front matter, métricas de conversão, lista de
transcripts e locks — use:

```bash
python ./tools/audit.py /_AudioMemosFC/MamyCalls
```

O relatório é salvo localmente em:

```text
tools/YYYY-MM-DD-HH-MM__AudioMemosFC_MamyCalls.md
```

Esse comando também é somente leitura em relação ao Dropbox. Durante a consulta, ele
mostra o progresso na mesma linha — conexão, listagem, leitura dos transcripts, análise
dos locks e medição dos áudios — para deixar claro que continua executando. Para medir
a duração dos áudios associados aos locks, pode baixá-los temporariamente e usar
`ffprobe`; os temporários locais são removidos ao fim. As métricas de conversão
consideram somente áudios com pelo menos 1 minuto; os demais continuam listados, mas
não entram nos cálculos.

---

## 8. Validar a instalação

```bash
python -m py_compile \
  tools/dropbox_lock_utils.py \
  tools/status.py \
  tools/remove_locks.py \
  tools/audit.py
```

Testar a ajuda sem acessar o Dropbox:

```bash
python ./tools/status.py --help
python ./tools/remove_locks.py --help
```

Testar a validação de formato sem remover nada:

```bash
python ./tools/remove_locks.py \
  /_AudioMemosFC/MamyCalls \
  --older_than 10m \
  --dry-run
```
