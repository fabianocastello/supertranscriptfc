#!/usr/bin/env python3
"""Read-only audit of the transcripts/locks in a Dropbox folder.

May temporarily download audio files associated with locks to measure their
duration with ffprobe; it does not create files on Dropbox and does not
change any remote data.
Only reads remote metadata and content; local temporary files are removed
at the end.

Usage:
    python ./tools/audit.py /_AudioMemosFC/MamyCalls
    python ./tools/audit.py /Other/Folder --output tools/report.md
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
    """Shows progress without creating a new line on every step."""
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
        return "n/a"
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
        return "n/a"
    total = max(0, int(round(seconds)))
    if total < 10:
        return "a few seconds ago"
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} hour" if hours == 1 else f"{hours} hours")
    if minutes:
        parts.append(f"{minutes} minute" if minutes == 1 else f"{minutes} minutes")
    if not hours and not minutes:
        parts.append(f"{secs} second" if secs == 1 else f"{secs} seconds")
    elif secs >= 30:
        parts.append(f"{secs} second" if secs == 1 else f"{secs} seconds")
    if len(parts) == 1:
        return parts[0] + " ago"
    return ", ".join(parts[:-1]) + " and " + parts[-1] + " ago"


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
    """Converts the lock's local, offset-less timestamp to UTC.

    The pipeline records datetime.now().isoformat() without an offset. Dropbox
    provides server_modified in UTC, also without tzinfo in this SDK version.
    The difference between the two lets us infer the machine's timezone,
    rounding to the nearest hour; this corrects, for example, vpsfc01 in
    UTC+02 and hosts in UTC-03.
    """
    if started_at.tzinfo is not None:
        return started_at.astimezone(timezone.utc), "explicit"
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

    progress("reading credentials from .env")
    cfg = dotenv_values(env_path)
    required = ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN")
    missing = [key for key in required if not cfg.get(key)]
    if missing:
        raise RuntimeError(f"Missing variables in .env: {', '.join(missing)}")

    dbx = dropbox.Dropbox(
        oauth2_refresh_token=cfg["DROPBOX_REFRESH_TOKEN"],
        app_key=cfg["DROPBOX_APP_KEY"],
        app_secret=cfg["DROPBOX_APP_SECRET"],
    )
    progress("connecting to Dropbox")
    now = datetime.now().astimezone()
    now_utc = now.astimezone(timezone.utc)
    progress("listing files in the folder")
    entries = remote_entries(dbx, root)

    files = {entry.path_display: entry for entry in entries}
    audio_paths = sorted(
        path for path, entry in files.items() if PurePosixPath(entry.name).suffix.lower() in AUDIO_EXTENSIONS
    )
    transcript_paths = sorted(path for path in files if path.endswith(TRANSCRIPT_SUFFIX))
    lock_paths = sorted(path for path in files if path.endswith(LOCK_SUFFIX))
    progress(
        f"Dropbox listed: {len(audio_paths)} audio files, {len(transcript_paths)} transcripts, and {len(lock_paths)} locks"
    )

    transcripts = []
    for index, path in enumerate(transcript_paths, start=1):
        progress(f"reading transcript {index}/{len(transcript_paths)}")
        text = read_remote_text(dbx, path)
        has_front_matter, fields = parse_front_matter(text)
        stem = path[: -len(TRANSCRIPT_SUFFIX)]
        audio_path = next((f"{stem}{ext}" for ext in AUDIO_EXTENSIONS if f"{stem}{ext}" in files), None)
        # NOTE: "audio_duration"/"conversion_time" match the front-matter field
        # names in use when this tool was updated. If the pipeline's
        # front-matter field names change, these lookups must be updated to
        # match, or metrics below will silently come out empty.
        audio_duration = parse_duration(fields.get("audio_duration"))
        conversion_seconds = parse_duration(fields.get("conversion_time"))
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
        progress(f"analyzing lock {index}/{len(lock_paths)}")
        text = read_remote_text(dbx, path)
        fields = {}
        for line in text.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip()] = value.strip()
        started_at = None
        # NOTE: "Started at"/"Processing on" match the lock content field
        # labels in use when this tool was updated. If the pipeline's lock
        # format changes, these lookups must be updated to match.
        started_raw = fields.get("Started at")
        if started_raw:
            try:
                started_at = datetime.fromisoformat(started_raw)
            except ValueError:
                pass
        server_modified = files[path].server_modified
        started_utc = None
        start_timezone = "n/a"
        if started_at:
            started_utc, start_timezone = normalize_lock_start(started_at, server_modified)
        age = age_seconds(started_utc, now_utc) if started_utc else None
        transcript = transcript_by_stem.get(path[: -len(LOCK_SUFFIX)])
        audio_duration = transcript["audio_duration_seconds"] if transcript else None
        if audio_duration is None:
            for extension in AUDIO_EXTENSIONS:
                audio_path = path[: -len(LOCK_SUFFIX)] + extension
                if audio_path in files:
                    progress(f"measuring audio for lock {index}/{len(lock_paths)}")
                    audio_duration = probe_remote_audio_duration(dbx, audio_path)
                    break
        locks.append(
            {
                "path": path,
                "name": relative_name(path, root),
                "machine": fields.get("Processing on", "unknown"),
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

    progress("query complete", done=True)
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
        recent_by_machine.setdefault(item["fields"].get("running_on", "n/a"), []).append(item)

    report_tz = datetime.fromisoformat(data["generated_at"]).tzinfo or timezone.utc

    def lock_started_display(item: dict) -> str:
        if not item.get("started_at_utc"):
            return "n/a"
        started = datetime.fromisoformat(item["started_at_utc"])
        return started.astimezone(report_tz).strftime("%Y-%m-%d %H:%M:%S")

    def metric_text(item: dict) -> tuple[str, str, str]:
        duration = item["audio_duration_seconds"]
        if duration is None:
            return "n/a (no front matter)", "n/a (no front matter)", "n/a (no front matter)"
        if duration < MIN_AUDIO_FOR_METRICS_SECONDS:
            return "not calculated (<1 min)", "not calculated (<1 min)", "not calculated (<1 min)"
        conversion = item["conversion_seconds"]
        rtf = item["conversion_rtf"]
        if conversion is None or rtf is None:
            return "n/a", "n/a", "n/a"
        rtf_text = f"{rtf:.3f}x"
        inverse = f"{1 / rtf:.2f} min/min" if rtf > 0 else "n/a (conversion rounded to 0s)"
        return format_seconds(conversion), rtf_text, inverse

    lines = [
        "# VOXEL FC Audit — MamyCalls",
        "",
        f"- **Dropbox folder:** `{data['root']}`",
        f"- **Query performed at:** `{data['generated_at']}`",
        f"- **Audio files found:** {data['audio_count']}",
        f"- **`.transcriptFC.txt` transcripts:** {data['transcript_count']}",
        f"- **Locks found:** {data['lock_count']}",
        "",
        "## Locks and current runs",
        "",
    ]
    if active_locks:
        lines.append("| Machine | File | Since | Audio duration | Elapsed time |")
        lines.append("|---|---|---:|---:|---:|")
        for item in active_locks:
            lines.append(
                f"| {md_cell(item['machine'])} | {md_cell(item['name'])} | "
                f"{lock_started_display(item)} | {format_seconds(item['audio_duration_seconds'])} | "
                f"{format_elapsed_humanized(item['age_seconds'])} |"
            )
        lines.append("")
        lines.append("Distribution by machine: " + ", ".join(f"`{machine}` ({count})" for machine, count in sorted(machines.items())) + ".")
    else:
        lines.append("No lock within the 36h window was found.")

    lines += [
        "",
        "## Average metrics by machine — last 12 hours",
        "",
        f"Considers transcripts with front matter modified on Dropbox from `{(recent_cutoff_utc.astimezone(report_tz)).strftime('%Y-%m-%d %H:%M:%S')}` up to the query, with at least 1 minute of audio. The transcript's modification time is used as an approximation of completion.",
        "",
    ]
    if recent_by_machine:
        lines.append("| Machine | Files | Average audio | Average conversion | Average RTF | Weighted audio-min/conversion-min |")
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
                f"{f'{avg_rtf:.3f}x' if avg_rtf is not None else 'n/a'} | "
                f"{f'{throughput:.2f} min/min' if throughput is not None else 'n/a (conversion rounded to 0s)'} |"
            )
    else:
        lines.append("No transcript with front matter and at least 1 minute of audio was completed in the last 12 hours.")

    lines += [
        "",
        "## Summary",
        "",
        f"- With front matter: **{len(with_front)}**",
        f"- Without front matter: **{len(without_front)}**",
        f"- Locks considered active by the 36h rule: **{len(active_locks)}**",
        f"- Stale locks or locks without a parseable date: **{len(stale_or_unparsed)}**",
        "",
        "## Conversion metric",
        "",
        "Only files with **1 minute or more of audio** were considered for the calculations. Smaller files remain listed, but appear as `not calculated (<1 min)`. ",
        "",
        "The **RTF (real-time factor)** is `conversion time ÷ audio duration`. Lower is better: `0.10x` means converting 1 hour of audio took 6 minutes.",
        "",
        "**Audio-min/conversion-min** is the inverse, `audio duration ÷ conversion time`. It answers how many minutes of audio the machine processed for each minute spent on conversion. For example: `30 min/min` means 30 minutes of audio were converted in 1 minute. Higher is better.",
        "",
        "",
        f"- Records with valid duration and conversion time: **{len(valid_metrics)}**",
        f"- Records under 1 minute, excluded from the metrics: **{len(below_threshold)}**",
        f"- Total audio considered: **{format_seconds(total_audio)}**",
        f"- Total conversion considered: **{format_seconds(total_conversion)}**",
        f"- RTF weighted by total audio: **{weighted_rtf:.3f}x**" if weighted_rtf is not None else "- Weighted RTF: **n/a**",
        f"- Weighted audio-min/conversion-min: **{1 / weighted_rtf:.2f} min/min**" if weighted_rtf else "- Weighted audio-min/conversion-min: **n/a**",
        f"- Simple average RTF per file: **{simple_mean_rtf:.3f}x**" if simple_mean_rtf is not None else "- Simple average RTF: **n/a**",
        "",
        "## All transcripts",
        "",
        "The `Audio-min/conversion-min` column uses the unit **minutes of audio per minute of conversion**. `not calculated (<1 min)` is intentional and follows the requested cutoff.",
        "",
        "| Transcript | Front matter | Recorded machine | Audio | Conversion | RTF | Audio-min/conversion-min |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for item in transcripts:
        conversion_text, rtf_text, inverse = metric_text(item)
        lines.append(
            f"| {md_cell(item['name'])} | {'yes' if item['has_front_matter'] else 'no'} | "
            f"{md_cell(item['fields'].get('running_on', 'n/a'))} | {format_seconds(item['audio_duration_seconds'])} | "
            f"{conversion_text} | {rtf_text} | {inverse} |"
        )
    lines += [
        "",
        "## Transcripts without front matter — full list",
        "",
    ]
    if without_front:
        lines.extend(f"- `{md_cell(item['name'])}`" for item in without_front)
    else:
        lines.append("None.")

    lines += ["", "## Transcripts with front matter — full list", ""]
    if with_front:
        lines.extend(f"- `{md_cell(item['name'])}`" for item in with_front)
    else:
        lines.append("None.")

    lines += ["", "## Stale locks or locks without a parseable date", ""]
    if stale_or_unparsed:
        lines.append("| File | Machine | Started | Age | Content |")
        lines.append("|---|---|---:|---:|---|")
        for item in stale_or_unparsed:
            lines.append(
                f"| {md_cell(item['name'])} | {md_cell(item['machine'])} | "
                f"{md_cell(item['started_at'] or 'n/a')} | {format_seconds(item['age_seconds'])} | "
                f"{md_cell(item['content'])} |"
            )
    else:
        lines.append("None.")
    lines += [
        "",
        "## Criteria",
        "",
        "- Front matter was considered present when the file starts with a block delimited by `---` and `---`.",
        "- A lock was considered a current run when it contains a parseable `Started at:` and is at most 36 hours old, the same rule documented in the project's pipeline.",
        "- Since the pipeline records the start time without an offset, the report infers the timezone by comparing `Started at` with Dropbox's `server_modified`; the elapsed time is computed in UTC.",
        "- Individual and aggregate metrics exclude files with less than 1 minute of duration; these files remain visible in the full table.",
        "- The query was read-only; no remote file was created, updated, or removed.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="Absolute path of the Dropbox folder")
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
    print(f"\nReport saved to: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
