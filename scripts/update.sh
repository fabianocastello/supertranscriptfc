#!/usr/bin/env bash
# Atualiza o codigo (git pull) e ja roda o voxelfc com os
# argumentos passados, para nao esquecer de atualizar antes de cada uso.
#
# Uso: scripts/update.sh --source /caminho/ou/pasta --model-size large-v3 --language pt
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "== Atualizando codigo (git pull) =="
git pull

if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

echo "== Rodando: voxelfc $* =="
voxelfc "$@"
