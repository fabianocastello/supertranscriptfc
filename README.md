# SuperTranscriptFC

Baixa um audio de uma pasta do Dropbox, transcreve, diariza as vozes por
locutor (`Pessoa 1`, `Pessoa 2`, ...) e envia `.transcriptFC.txt` / `.srt` /
`.transcriptFC.vtt` de volta ao Dropbox.

Cada maquina onde o projeto for instalado roda **de forma totalmente
independente**: ambiente virtual proprio, modelos proprios baixados e
armazenados em `~/.supertranscriptfc/models` (Linux/macOS) ou
`%USERPROFILE%\.supertranscriptfc\models` (Windows). Nao ha nenhum modelo ou
cache compartilhado entre maquinas.

Para instalar rapido em Linux, macOS ou Windows, veja o
[quickInstall.md](quickInstall.md).

## Instalacao

Pre-requisitos em qualquer maquina: Python 3.10+ e FFmpeg no PATH.

### Linux (thor25, leno18) e macOS (MacBook Air M1)

```bash
./scripts/install.sh
```

- Detecta GPU NVIDIA automaticamente (thor25) e instala o `torch` com CUDA;
  nas demais (leno18, MacBook) instala a variante CPU-only.
- No MacBook Air M1, a diarizacao (`pyannote.audio`/torch) usa aceleracao MPS
  automaticamente quando disponivel; a transcricao (`faster-whisper`) roda em
  CPU, pois o `ctranslate2` nao suporta MPS.

### Windows (ps20)

No PowerShell:

```powershell
.\scripts\install.ps1
```

Ou de' duplo-clique em `scripts\install.bat` (wrapper que chama o script acima
contornando a politica de execucao padrao do PowerShell).

Instala `torch` CPU-only (ps20 nao tem GPU dedicada).

Depois de instalar em qualquer plataforma, edite o arquivo `.env` criado a
partir de `.env.example` e preencha:

- `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN` — credenciais
  OAuth2 do App Dropbox (fluxo de refresh token, sem expiracao — o SDK renova
  o access token automaticamente a cada chamada).
- `HF_TOKEN` — token do Hugging Face com acesso aos modelos
  `pyannote/speaker-diarization-3.1` e `pyannote/segmentation-3.0` (aceite os
  termos de uso de cada um no site do Hugging Face antes de usar).

## Uso

Antes de qualquer comando abaixo, ative o ambiente virtual:

```bash
source .venv/bin/activate          # Linux/macOS
```
```cmd
.venv\Scripts\activate.bat         :: Windows, no cmd.exe
```
```powershell
.venv\Scripts\Activate.ps1         # Windows, no PowerShell
```

Processar um arquivo local (sem tocar no Dropbox — util para testar):

```bash
supertranscriptfc --source /caminho/audio.mp3 --local
```

Processar um arquivo do Dropbox (baixa, processa e envia de volta para a
mesma pasta de origem):

```bash
supertranscriptfc --source /Gravacoes/reuniao.mp3
```

Especificando uma pasta de destino diferente no Dropbox:

```bash
supertranscriptfc --source /Gravacoes/reuniao.mp3 --dest /Gravacoes/Transcricoes
```

Outras opcoes uteis: `--model-size`, `--device {auto,cpu,cuda}`,
`--language pt`, `--min-speakers`, `--max-speakers`, `--min-minutes` /
`--max-minutes` (ignora audios fora dessa faixa de duracao — pode usar um,
outro ou ambos), `--vtt` (gera `.vtt` tambem), `--keep-temp` (nao apaga
temporarios), `--force` (reprocessa mesmo se ja tiver sido concluido antes).

## Retomada e idempotencia

Cada etapa (download, conversao, transcricao, diarizacao, saidas, upload) e'
marcada em `~/.supertranscriptfc/tmp/<job_id>/progress.json`. Se o processo
for interrompido, rodar o mesmo comando novamente retoma de onde parou, sem
refazer etapas concluidas.

Arquivos ja processados com sucesso ficam registrados em
`~/.supertranscriptfc/processed_files.json` e nao sao reprocessados nas
execucoes seguintes (a menos que `--force` seja usado), mesmo depois que os
temporarios daquele job forem removidos.

## Espaco em disco esperado

- ~20 GB permanentes em `~/.supertranscriptfc/models` para os modelos.
- ~10 GB temporarios por processamento em `~/.supertranscriptfc/tmp`
  (audio original + WAV intermediario), removidos automaticamente ao final
  a menos que `--keep-temp` seja usado.

## Limitacoes conhecidas

A diarizacao (separacao por locutor) nao e' perfeita: audios com ruido de
fundo, vozes muito parecidas ou falas simultaneas podem gerar atribuicoes
incorretas de locutor.
