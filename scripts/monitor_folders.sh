#!/usr/bin/env bash
# Monitora varias pastas do Dropbox na mesma maquina, chamando
# voxelfc para cada uma em sequencia. E' seguro reiniciar do zero
# a qualquer momento (apos um crash, por exemplo): cada arquivo so' e'
# considerado concluido com base na existencia real do .transcriptFC.txt no
# proprio Dropbox, entao pastas/arquivos ja prontos sao pulados rapido em
# vez de reprocessados.
#
# Configuracao: liste as pastas em scripts/folders.txt (uma por linha,
# comecando com "/"; linhas em branco ou com "#" sao ignoradas). Copie
# scripts/folders.txt.example para comecar.
#
# Uso:
#   scripts/monitor_folders.sh [--loop SEGUNDOS] [-- <args extras>]
#
# Exemplos:
#   scripts/monitor_folders.sh -- --model-size large-v3 --language pt --vtt
#   scripts/monitor_folders.sh --loop 1800 -- --model-size large-v3 --vtt
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"
FOLDERS_FILE="${FOLDERS_FILE:-scripts/folders.txt}"

if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

if [ ! -f "$FOLDERS_FILE" ]; then
    echo "Arquivo de pastas nao encontrado: $FOLDERS_FILE" >&2
    echo "Copie scripts/folders.txt.example para $FOLDERS_FILE e edite com suas pastas do Dropbox." >&2
    exit 1
fi

LOOP_INTERVAL=""
EXTRA_ARGS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --loop)
            LOOP_INTERVAL="$2"
            shift 2
            ;;
        --)
            shift
            EXTRA_ARGS=("$@")
            break
            ;;
        *)
            echo "Argumento desconhecido: $1" >&2
            exit 1
            ;;
    esac
done

run_one_pass() {
    local total=0 ok=0 fail=0

    while IFS= read -r line || [ -n "$line" ]; do
        line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -z "$line" ] && continue
        case "$line" in \#*) continue ;; esac

        total=$((total + 1))
        echo ""
        echo "=== [$total] Pasta: $line ==="
        if voxelfc --source "$line" "${EXTRA_ARGS[@]}"; then
            ok=$((ok + 1))
        else
            fail=$((fail + 1))
            echo "AVISO: falha ao processar a pasta '$line', continuando com as demais." >&2
        fi
    done < "$FOLDERS_FILE"

    echo ""
    echo "=== Passada concluida: $ok/$total pastas OK, $fail com falha ==="
}

if [ -n "$LOOP_INTERVAL" ]; then
    echo "Monitorando em loop, a cada ${LOOP_INTERVAL}s (Ctrl+C para parar)."
    while true; do
        run_one_pass
        echo "Aguardando ${LOOP_INTERVAL}s ate a proxima passada..."
        sleep "$LOOP_INTERVAL"
    done
else
    run_one_pass
fi
