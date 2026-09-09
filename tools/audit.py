#!/usr/bin/env python3
"""Auditoria somente leitura dos transcripts/locks de uma pasta Dropbox.

Pode baixar temporariamente áudios associados a locks para obter a duração com ffprobe;
não cria arquivos no Dropbox e não altera nenhum dado remoto.
Lê somente metadados e conteúdo remoto; arquivos temporários locais são removidos ao fim.

Uso:
    python ./tools/audit.py /_AudioMemosFC/MamyCalls
    python ./tools/audit.py /Outra/Pasta --output tools/relatorio.md
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

from dotenv import dotenv_values

from dropbox_lock_utils import probe_remote_audio_duration

AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma", ".mp4", ".mov")
TRANSCRIPT_SUFFIX = ".transcriptFC.txt"
LOCK_SUFFIX = ".transcriptFC.lock"
MIN_AUDIO_FOR_METRICS_SECONDS = 60

_DURATION_RE = re.compile(r"^(?:(?P<h>\d+)h)?(?:(?P<m>\d+)m)?(?:(?P<s>\d+)s)?$")
_FRONT_MATTER_RE = re.compile(r"^---\s*\n(?P<body>.*?)\n---(?:\s*\n|$)", re.DOTALL)
_PROGRESS_WIDTH = 0


def progress(message: str, *, done: bool = False) -> None:
    """Mostra progresso sem criar uma linha nova a cada etapa."""
    global _PROGRESS_WIDTH
    text = f"[audit] {message}"
    padding = max(0, _PROGRESS_WIDTH - len(text))
    end = "\n" if done else ""
    print("\r" + text + (" " * padding), end=end, file=sys.stderr, flush=True)
    _PROGRESS_WIDTH = 0 if done else len(text)


def parse_duration(value: str | None) -> float | None:
    if not value:
        return None
    match = _DURATION_RE.match(value.strip())
    if not match:
        return None
    return (
        int(match.group("h") or 0) * 3600
        + int(match.group("m") or 0) * 60
        + int(match.group("s") or 0)
    )


def format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return "n/d"
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def format_elapsed_humanized(seconds: float | None) -> str:
    if seconds is None:
        return "n/d"
    total = max(0, int(round(seconds)))
    if total < 10:
        return "há alguns segundos"
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} hora" if hours == 1 else f"{hours} horas")
    if minutes:
        parts.append(f"{minutes} minuto" if minutes == 1 else f"{minutes} minutos")
    if not hours and not minutes:
        parts.append(f"{secs} segundo" if secs == 1 else f"{secs} segundos")
    elif secs >= 30:
        parts.append(f"{secs} segundo" if secs == 1 else f"{secs} segundos")
    if len(parts) == 1:
        return "há " + parts[0]
    return "há " + ", ".join(parts[:-1]) + " e " + parts[-1]


def parse_front_matter(text: str) -> tuple[bool, dict[str, str]]:
    normalized = text.lstrip("\ufeff \t\r\n")
    match = _FRONT_MATTER_RE.match(normalized)
    if not match:
        return False, {}
    fields: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        fields[key.strip()] = value
    return True, fields


def remote_entries(dbx, root: str):
    from dropbox.files import FileMetadata

    result = dbx.files_list_folder(root, recursive=True)
    entries = list(result.entries)
    while result.has_more:
        result = dbx.files_list_folder_continue(result.cursor)
        entries.extend(result.entries)
    return [entry for entry in entries if isinstance(entry, FileMetadata)]


def read_remote_text(dbx, path: str) -> str:
    _metadata, response = dbx.files_download(path)
    return response.content.decode("utf-8", errors="replace")


def relative_name(path: str, root: str) -> str:
    prefix = root.rstrip("/") + "/"
    return path[len(prefix) :] if path.startswith(prefix) else path


def normalize_lock_start(started_at: datetime, server_modified: datetime) -> tuple[datetime, str]:
    """Converte o horario local sem fuso do lock para UTC.

    O pipeline grava datetime.now().isoformat() sem offset. O Dropbox fornece
    server_modified em UTC, tambem sem tzinfo nesta versao do SDK. A diferenca
    entre ambos permite inferir o fuso da maquina, arredondando para a hora
    mais proxima; isso corrige, por exemplo, vpsfc01 em UTC+02 e hosts em UTC-03.
    """
    if started_at.tzinfo is not None:
        return started_at.astimezone(timezone.utc), "explicito"
    server_utc = server_modified.replace(tzinfo=timezone.utc)
    delta_hours = (server_utc.replace(tzinfo=None) - started_at).total_seconds() / 3600
    offset_hours = round(-delta_hours)
    offset = timezone(timedelta(hours=offset_hours))
    return started_at.replace(tzinfo=offset).astimezone(timezone.utc), format_offset(offset_hours)


def format_offset(offset_hours: int) -> str:
    if offset_hours == 0:
        return "UTC"
    sign = "+" if offset_hours > 0 else "-"
    absolute = abs(offset_hours)
    return f"UTC{sign}{absolute:02d}:00"


def age_seconds(started_utc: datetime, now_utc: datetime) -> float:
    return max(0.0, (now_utc - started_utc).total_seconds())


def audit(root: str, env_path: Path) -> dict:
    import dropbox

    progress("lendo credenciais do .env")
    cfg = dotenv_values(env_path)
    required = ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN")
    missing = [key for key in required if not cfg.get(key)]
    if missing:
        raise RuntimeError(f"Variaveis ausentes no .env: {', '.join(missing)}")

    dbx = dropbox.Dropbox(
        oauth2_refresh_token=cfg["DROPBOX_REFRESH_TOKEN"],
        app_key=cfg["DROPBOX_APP_KEY"],
        app_secret=cfg["DROPBOX_APP_SECRET"],
    )
    progress("conectando ao Dropbox")
    now = datetime.now().astimezone()
    now_utc = now.astimezone(timezone.utc)
    progress("listando arquivos da pasta")
    entries = remote_entries(dbx, root)

    files = {entry.path_display: entry for entry in entries}
    audio_paths = sorted(
        path for path, entry in files.items() if PurePosixPath(entry.name).suffix.lower() in AUDIO_EXTENSIONS
    )
    transcript_paths = sorted(path for path in files if path.endswith(TRANSCRIPT_SUFFIX))
    lock_paths = sorted(path for path in files if path.endswith(LOCK_SUFFIX))
    progress(
        f"Dropbox listado: {len(audio_paths)} áudios, {len(transcript_paths)} transcripts e {len(lock_paths)} locks"
    )

    transcripts = []
    for index, path in enumerate(transcript_paths, start=1):
        progress(f"lendo transcript {index}/{len(transcript_paths)}")
        text = read_remote_text(dbx, path)
        has_front_matter, fields = parse_front_matter(text)
        stem = path[: -len(TRANSCRIPT_SUFFIX)]
        audio_path = next((f"{stem}{ext}" for ext in AUDIO_EXTENSIONS if f"{stem}{ext}" in files), None)
        audio_duration = parse_duration(fields.get("duracao_audio"))
        conversion_seconds = parse_duration(fields.get("tempo_conversao"))
        rtf = conversion_seconds / audio_duration if audio_duration and conversion_seconds is not None else None
        transcripts.append(
            {
                "path": path,
                "name": relative_name(path, root),
                "audio_path": audio_path,
                "has_front_matter": has_front_matter,
                "fields": fields,
                "audio_duration_seconds": audio_duration,
                "conversion_seconds": conversion_seconds,
                "conversion_rtf": rtf,
                "server_modified_utc": files[path].server_modified.replace(tzinfo=timezone.utc).isoformat(timespec="seconds"),
            }
        )

    transcript_by_stem = {
        item["path"][: -len(TRANSCRIPT_SUFFIX)]: item for item in transcripts
    }
    locks = []
    for index, path in enumerate(lock_paths, start=1):
        progress(f"analisando lock {index}/{len(lock_paths)}")
        text = read_remote_text(dbx, path)
        fields = {}
        for line in text.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip()] = value.strip()
        started_at = None
        started_raw = fields.get("Iniciado em")
        if started_raw:
            try:
                started_at = datetime.fromisoformat(started_raw)
            except ValueError:
                pass
        server_modified = files[path].server_modified
        started_utc = None
        start_timezone = "n/d"
        if started_at:
            started_utc, start_timezone = normalize_lock_start(started_at, server_modified)
        age = age_seconds(started_utc, now_utc) if started_utc else None
        transcript = transcript_by_stem.get(path[: -len(LOCK_SUFFIX)])
        audio_duration = transcript["audio_duration_seconds"] if transcript else None
        if audio_duration is None:
            for extension in AUDIO_EXTENSIONS:
                audio_path = path[: -len(LOCK_SUFFIX)] + extension
                if audio_path in files:
                    progress(f"medindo áudio do lock {index}/{len(lock_paths)}")
                    audio_duration = probe_remote_audio_duration(dbx, audio_path)
                    break
        locks.append(
            {
                "path": path,
                "name": relative_name(path, root),
                "machine": fields.get("Processando por", "desconhecida"),
                "started_at": started_raw,
                "started_at_utc": started_utc.isoformat(timespec="seconds") if started_utc else None,
                "start_timezone": start_timezone,
                "server_modified": server_modified.isoformat(timespec="seconds"),
                "age_seconds": age,
                "audio_duration_seconds": audio_duration,
                "active_by_36h_rule": age is not None and age <= 36 * 3600,
                "content": text.strip(),
            }
        )

    progress("consulta concluída", done=True)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "root": root,
        "audio_count": len(audio_paths),
        "transcript_count": len(transcripts),
        "lock_count": len(locks),
        "transcripts": transcripts,
        "locks": locks,
    }


def md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def make_report(data: dict) -> str:
    transcripts = data["transcripts"]
    locks = data["locks"]
    with_front = [item for item in transcripts if item["has_front_matter"]]
    without_front = [item for item in transcripts if not item["has_front_matter"]]
    valid_metrics = [
        item for item in with_front
        if item["audio_duration_seconds"] is not None
        and item["audio_duration_seconds"] >= MIN_AUDIO_FOR_METRICS_SECONDS
        and item["conversion_seconds"] is not None
    ]
    below_threshold = [
        item for item in with_front
        if item["audio_duration_seconds"] is not None
        and item["audio_duration_seconds"] < MIN_AUDIO_FOR_METRICS_SECONDS
    ]
    total_audio = sum(item["audio_duration_seconds"] for item in valid_metrics)
    total_conversion = sum(item["conversion_seconds"] for item in valid_metrics)
    weighted_rtf = total_conversion / total_audio if total_audio else None
    ratios = [item["conversion_rtf"] for item in valid_metrics if item["conversion_rtf"] is not None]
    simple_mean_rtf = sum(ratios) / len(ratios) if ratios else None
    active_locks = [item for item in locks if item["active_by_36h_rule"]]
    stale_or_unparsed = [item for item in locks if not item["active_by_36h_rule"]]
    machines = Counter(item["machine"] for item in active_locks)

    recent_cutoff_utc = datetime.fromisoformat(data["generated_at"]).astimezone(timezone.utc) - timedelta(hours=12)
    recent_12h = [
        item for item in with_front
        if item["audio_duration_seconds"] is not None
        and item["audio_duration_seconds"] >= MIN_AUDIO_FOR_METRICS_SECONDS
        and item["conversion_seconds"] is not None
        and datetime.fromisoformat(item["server_modified_utc"]) >= recent_cutoff_utc
    ]
    recent_by_machine: dict[str, list[dict]] = {}
    for item in recent_12h:
        recent_by_machine.setdefault(item["fields"].get("running_on", "n/d"), []).append(item)

    report_tz = datetime.fromisoformat(data["generated_at"]).tzinfo or timezone.utc

    def lock_started_display(item: dict) -> str:
        if not item.get("started_at_utc"):
            return "n/d"
        started = datetime.fromisoformat(item["started_at_utc"])
        return started.astimezone(report_tz).strftime("%Y-%m-%d %H:%M:%S")

    def metric_text(item: dict) -> tuple[str, str, str]:
        duration = item["audio_duration_seconds"]
        if duration is None:
            return "n/d (sem front matter)", "n/d (sem front matter)", "n/d (sem front matter)"
        if duration < MIN_AUDIO_FOR_METRICS_SECONDS:
            return "não calculado (<1 min)", "não calculado (<1 min)", "não calculado (<1 min)"
        conversion = item["conversion_seconds"]
        rtf = item["conversion_rtf"]
        if conversion is None or rtf is None:
            return "n/d", "n/d", "n/d"
        rtf_text = f"{rtf:.3f}x"
        inverse = f"{1 / rtf:.2f} min/min" if rtf > 0 else "n/d (conversão arredondada para 0s)"
        return format_seconds(conversion), rtf_text, inverse

    lines = [
        "# Auditoria VOXEL FC — MamyCalls",
        "",
        f"- **Pasta Dropbox:** `{data['root']}`",
        f"- **Consulta realizada em:** `{data['generated_at']}`",
        f"- **Áudios encontrados:** {data['audio_count']}",
        f"- **Transcripts `.transcriptFC.txt`:** {data['transcript_count']}",
        f"- **Locks encontrados:** {data['lock_count']}",
        "",
        "## Locks e execuções atuais",
        "",
    ]
    if active_locks:
        lines.append("| Máquina | Arquivo | Desde | Duração do áudio | Tempo decorrido |")
        lines.append("|---|---|---:|---:|---:|")
        for item in active_locks:
            lines.append(
                f"| {md_cell(item['machine'])} | {md_cell(item['name'])} | "
                f"{lock_started_display(item)} | {format_seconds(item['audio_duration_seconds'])} | "
                f"{format_elapsed_humanized(item['age_seconds'])} |"
            )
        lines.append("")
        lines.append("Distribuição por máquina: " + ", ".join(f"`{machine}` ({count})" for machine, count in sorted(machines.items())) + ".")
    else:
        lines.append("Nenhum lock dentro da janela de 36h foi encontrado.")

    lines += [
        "",
        "## Métricas médias por máquina — últimas 12 horas",
        "",
        f"Considera transcripts com front matter modificados no Dropbox desde `{(recent_cutoff_utc.astimezone(report_tz)).strftime('%Y-%m-%d %H:%M:%S')}` até a consulta, com áudio de pelo menos 1 minuto. O horário de modificação do transcript é usado como aproximação de conclusão.",
        "",
    ]
    if recent_by_machine:
        lines.append("| Máquina | Arquivos | Áudio médio | Conversão média | RTF médio | Áudio/min conversão ponderado |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for machine, items in sorted(recent_by_machine.items()):
            audio_total = sum(item["audio_duration_seconds"] for item in items)
            conversion_total = sum(item["conversion_seconds"] for item in items)
            avg_audio = audio_total / len(items)
            avg_conversion = conversion_total / len(items)
            rtf_values = [item["conversion_rtf"] for item in items if item["conversion_rtf"] is not None]
            avg_rtf = sum(rtf_values) / len(rtf_values) if rtf_values else None
            throughput = audio_total / conversion_total if conversion_total > 0 else None
            lines.append(
                f"| {md_cell(machine)} | {len(items)} | {format_seconds(avg_audio)} | "
                f"{format_seconds(avg_conversion)} | "
                f"{f'{avg_rtf:.3f}x' if avg_rtf is not None else 'n/d'} | "
                f"{f'{throughput:.2f} min/min' if throughput is not None else 'n/d (conversão arredondada para 0s)'} |"
            )
    else:
        lines.append("Nenhum transcript com front matter e áudio de pelo menos 1 minuto foi concluído nas últimas 12 horas.")

    lines += [
        "",
        "## Resumo",
        "",
        f"- Com front matter: **{len(with_front)}**",
        f"- Sem front matter: **{len(without_front)}**",
        f"- Locks considerados ativos pela regra de 36h: **{len(active_locks)}**",
        f"- Locks antigos ou sem data interpretável: **{len(stale_or_unparsed)}**",
        "",
        "## Métrica de conversão",
        "",
        "Foram considerados para os cálculos somente os arquivos com **1 minuto ou mais de áudio**. Arquivos menores continuam listados, mas aparecem como `não calculado (<1 min)`. ",
        "",
        "O **RTF (real-time factor)** é `tempo de conversão ÷ duração do áudio`. Quanto menor, melhor: `0,10x` significa que converter 1 hora de áudio levou 6 minutos.",
        "",
        "**Áudio/min de conversão** é o inverso, `duração do áudio ÷ tempo de conversão`. Ele responde quantos minutos de áudio a máquina processou por cada minuto gasto na conversão. Por exemplo: `30 min/min` significa que 30 minutos de áudio foram convertidos em 1 minuto. Quanto maior, melhor.",
        "",
        "",
        f"- Registros com duração e tempo de conversão válidos: **{len(valid_metrics)}**",
        f"- Registros abaixo de 1 minuto, excluídos das métricas: **{len(below_threshold)}**",
        f"- Áudio total considerado: **{format_seconds(total_audio)}**",
        f"- Conversão total considerada: **{format_seconds(total_conversion)}**",
        f"- RTF ponderado pelo total de áudio: **{weighted_rtf:.3f}x**" if weighted_rtf is not None else "- RTF ponderado: **n/d**",
        f"- Áudio/min de conversão ponderado: **{1 / weighted_rtf:.2f} min/min**" if weighted_rtf else "- Áudio/min de conversão ponderado: **n/d**",
        f"- RTF médio simples por arquivo: **{simple_mean_rtf:.3f}x**" if simple_mean_rtf is not None else "- RTF médio simples: **n/d**",
        "",
        "## Todos os transcripts",
        "",
        "A coluna `Áudio/min de conversão` usa a unidade **minutos de áudio por minuto de conversão**. `não calculado (<1 min)` é intencional e segue o corte solicitado.",
        "",
        "| Transcript | Front matter | Máquina registrada | Áudio | Conversão | RTF | Áudio/min de conversão |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for item in transcripts:
        conversion_text, rtf_text, inverse = metric_text(item)
        lines.append(
            f"| {md_cell(item['name'])} | {'sim' if item['has_front_matter'] else 'não'} | "
            f"{md_cell(item['fields'].get('running_on', 'n/d'))} | {format_seconds(item['audio_duration_seconds'])} | "
            f"{conversion_text} | {rtf_text} | {inverse} |"
        )
    lines += [
        "",
        "## Transcripts sem front matter — lista completa",
        "",
    ]
    if without_front:
        lines.extend(f"- `{md_cell(item['name'])}`" for item in without_front)
    else:
        lines.append("Nenhum.")

    lines += ["", "## Transcripts com front matter — lista completa", ""]
    if with_front:
        lines.extend(f"- `{md_cell(item['name'])}`" for item in with_front)
    else:
        lines.append("Nenhum.")

    lines += ["", "## Locks antigos ou sem data interpretável", ""]
    if stale_or_unparsed:
        lines.append("| Arquivo | Máquina | Início | Idade | Conteúdo |")
        lines.append("|---|---|---:|---:|---|")
        for item in stale_or_unparsed:
            lines.append(
                f"| {md_cell(item['name'])} | {md_cell(item['machine'])} | "
                f"{md_cell(item['started_at'] or 'n/d')} | {format_seconds(item['age_seconds'])} | "
                f"{md_cell(item['content'])} |"
            )
    else:
        lines.append("Nenhum.")
    lines += [
        "",
        "## Critério",
        "",
        "- Front matter foi considerado presente quando o arquivo começa com um bloco delimitado por `---` e `---`.",
        "- Um lock foi considerado execução atual quando contém `Iniciado em:` interpretável e tem no máximo 36 horas, mesma regra documentada no pipeline do projeto.",
        "- Como o pipeline grava o início sem fuso, o relatório infere o fuso comparando `Iniciado em` com `server_modified` do Dropbox; o tempo decorrido é calculado em UTC.",
        "- Métricas individuais e agregadas excluem arquivos com duração inferior a 1 minuto; esses arquivos continuam visíveis na tabela completa.",
        "- A consulta foi somente leitura; nenhum arquivo remoto foi criado, atualizado ou removido.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="Caminho absoluto da pasta no Dropbox")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    data = audit(args.root, Path(args.env).resolve())
    report = make_report(data)
    generated_at = datetime.fromisoformat(data["generated_at"])
    root_label = re.sub(r"[^A-Za-z0-9._-]+", "_", args.root.strip("/")).lstrip("_") or "DropboxRoot"
    default_name = f"{generated_at:%Y-%m-%d-%H-%M}__{root_label}.md"
    output = Path(args.output) if args.output else Path("tools") / default_name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nRelatório salvo em: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
