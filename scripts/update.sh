#!/usr/bin/env bash
# Updates the code and runs VOXEL FC using the project's virtual environment.
#
# Usage: scripts/update.sh --source /path/or/folder --model-size large-v3 --language pt
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

# When git pull updates this very file, Bash may keep running the old
# version already loaded. Re-executing the file guarantees the rest of the
# flow uses the new version and avoids failures from a package/entry-point
# rename.
if [ "${VOXELFC_UPDATE_REEXEC:-0}" != "1" ]; then
    echo "== Updating code (git pull) =="
    git pull
    exec env VOXELFC_UPDATE_REEXEC=1 bash "$0" "$@"
fi

VENV_PYTHON="$REPO_DIR/.venv/bin/python"
VOXELFC_BIN="$REPO_DIR/.venv/bin/voxelfc"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "Virtual environment not found at $REPO_DIR/.venv." >&2
    echo "Run: ./scripts/install.sh" >&2
    exit 1
fi

# We don't rely on PATH, which may mix .venv with Miniconda.
echo "== Installing the updated code into the virtual environment =="
"$VENV_PYTHON" -m pip install -q -e .

if [ ! -x "$VOXELFC_BIN" ]; then
    echo "Executable not found after installation: $VOXELFC_BIN" >&2
    exit 1
fi

echo "== Running: voxelfc $* =="
"$VOXELFC_BIN" "$@"
