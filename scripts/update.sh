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

# O pull pode alterar pyproject.toml, o nome do pacote ou os entry points.
# Reinstalar o pacote atualiza .venv/bin/voxelfc e o alias legado.
echo "== Instalando codigo atualizado no ambiente virtual =="
python -m pip install -q -e .

if ! command -v voxelfc >/dev/null 2>&1; then
    echo "Executavel voxelfc nao encontrado apos a instalacao." >&2
    exit 1
fi

echo "== Rodando: voxelfc $* =="
voxelfc "$@"
