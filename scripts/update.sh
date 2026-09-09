#!/usr/bin/env bash
# Atualiza o codigo e executa o VOXEL FC usando o ambiente virtual do projeto.
#
# Uso: scripts/update.sh --source /caminho/ou/pasta --model-size large-v3 --language pt
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

# Quando o git pull atualiza este proprio arquivo, o Bash pode continuar com a
# versao antiga ja carregada. Reexecutar o arquivo garante que o restante do
# fluxo use a versao nova e evita a falha do rename de pacote/entry point.
if [ "${VOXELFC_UPDATE_REEXEC:-0}" != "1" ]; then
    echo "== Atualizando codigo (git pull) =="
    git pull
    exec env VOXELFC_UPDATE_REEXEC=1 bash "$0" "$@"
fi

VENV_PYTHON="$REPO_DIR/.venv/bin/python"
VOXELFC_BIN="$REPO_DIR/.venv/bin/voxelfc"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "Ambiente virtual nao encontrado em $REPO_DIR/.venv." >&2
    echo "Execute: ./scripts/install.sh" >&2
    exit 1
fi

# Nao dependemos do PATH, que pode misturar .venv com Miniconda.
echo "== Instalando codigo atualizado no ambiente virtual =="
"$VENV_PYTHON" -m pip install -q -e .

if [ ! -x "$VOXELFC_BIN" ]; then
    echo "Executavel nao encontrado apos a instalacao: $VOXELFC_BIN" >&2
    exit 1
fi

echo "== Rodando: voxelfc $* =="
"$VOXELFC_BIN" "$@"
