from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

from dotenv import dotenv_values

AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma", ".mp4", ".mov")
TRANSCRIPT_SUFFIX = ".voxel.txt"
LOCK_SUFFIX = ".voxel.lock"
# Older runs wrote the transcript/lock under these names; recognized here
# too so files already produced under them are still found by these
# read-only tools.
LEGACY_TRANSCRIPT_SUFFIX = ".transcriptFC.txt"
LEGACY_LOCK_SUFFIX = ".transcriptFC.lock"
STALE_AFTER = timedelta(hours=36)
VALID_AGE_RE = re.compile(r"^(?P<amount>[1-9]\d*)(?P<unit>[hms])$")
DURATION_RE = re.compile(r"^(?:(?P<h>\d+)h)?(?:(?P<m>\d+)m)?(?:(?P<s>\d+)s)?$")
FRONT_MATTER_RE = re.compile(r"^---\s*\n(?P<body>.*?)\n---(?:\s*\n|$)", re.DOTALL)


def transcript_suffix_for(path: str) -> str | None:
    """Returns whichever transcript suffix (current or legacy) `path` ends
    with, or None if it doesn't end with either."""
    if path.endswith(TRANSCRIPT_SUFFIX):
        return TRANSCRIPT_SUFFIX
    if path.endswith(LEGACY_TRANSCRIPT_SUFFIX):
        return LEGACY_TRANSCRIPT_SUFFIX
    return None


def strip_transcript_suffix(path: str) -> str:
    """Removes whichever transcript suffix `path` ends with (current or
    legacy). Returns `path` unchanged if it ends with neither."""
    suffix = transcript_suffix_for(path)
    return path[: -len(suffix)] if suffix else path


def lock_suffix_for(path: str) -> str | None:
    """Returns whichever lock suffix (current or legacy) `path` ends with,
    or None if it doesn't end with either."""
    if path.endswith(LOCK_SUFFIX):
        return LOCK_SUFFIX
    if path.endswith(LEGACY_LOCK_SUFFIX):
        return LEGACY_LOCK_SUFFIX
    return None


def strip_lock_suffix(path: str) -> str:
    """Removes whichever lock suffix `path` ends with (current or legacy).
    Returns `path` unchanged if it ends with neither."""
    suffix = lock_suffix_for(path)
    return path[: -len(suffix)] if suffix else path


@dataclass(frozen=True)
class LockRecord:
    path: str
    name: str
    machine: str
    started_raw: str | None
    started_utc: datetime | None
    age_seconds: float | None
    audio_duration_seconds: float | None
    content: str
    server_modified: datetime

    @property
    def has_valid_start(self) -> bool:
        return self.started_utc is not None

    @property
    def is_active(self) -> bool:
        return self.age_seconds is not None and self.age_seconds <= STALE_AFTER.total_seconds()



def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def connect_from_env(env_path: Path | None = None):
    import dropbox

    env_path = env_path or project_root() / ".env"
    values = dotenv_values(env_path)
    required = ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise RuntimeError(f"Missing variables in {env_path}: {', '.join(missing)}")
    return dropbox.Dropbox(
        oauth2_refresh_token=values["DROPBOX_REFRESH_TOKEN"],
        app_key=values["DROPBOX_APP_KEY"],
        app_secret=values["DROPBOX_APP_SECRET"],
    )


def list_files(dbx, root: str):
    from dropbox.files import FileMetadata

    if not root.startswith("/"):
        raise ValueError("The Dropbox path must start with '/'.")
    result = dbx.files_list_folder(root.rstrip("/") or "/", recursive=True)
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


def parse_lock(content: str) -> tuple[str, str | None]:
    # NOTE: these field labels ("Processing on" / "Started at") match the
    # lock file content format written by the pipeline at the time this tool
    # was updated. If the pipeline's lock format changes, this parser must
    # be updated to match, or it will silently stop finding these fields.
    machine = "unknown"
    started = None
    for line in content.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() == "Processing on":
            machine = value.strip() or machine
        elif key.strip() == "Started at":
            started = value.strip() or None
    return machine, started


def parse_duration(value: str | None) -> float | None:
    if not value:
        return None
    match = DURATION_RE.fullmatch(value.strip())
    if not match:
        return None
    return (
        int(match.group("h") or 0) * 3600
        + int(match.group("m") or 0) * 60
        + int(match.group("s") or 0)
    )


def transcript_audio_duration(dbx, transcript_path: str) -> float | None:
    try:
        text = read_remote_text(dbx, transcript_path)
    except Exception:
        return None
    match = FRONT_MATTER_RE.match(text.lstrip("\ufeff \t\r\n"))
    if not match:
        return None
    for line in match.group("body").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        # NOTE: "audio_duration" matches the front-matter field name in use
        # when this tool was updated; if the pipeline's front-matter field
        # names change, this lookup must be updated to match.
        if key.strip() == "audio_duration":
            return parse_duration(value.strip().strip('"'))
    return None


def probe_remote_audio_duration(dbx, audio_path: str) -> float | None:
    """Temporarily downloads an audio file and gets its duration with ffprobe."""
    try:
        _metadata, response = dbx.files_download(audio_path)
        suffix = PurePosixPath(audio_path).suffix or ".audio"
        with tempfile.NamedTemporaryFile(suffix=suffix) as temporary:
            temporary.write(response.content)
            temporary.flush()
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", temporary.name,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        if result.returncode != 0:
            return None
        return float(result.stdout.strip())
    except Exception:
        return None


def normalize_lock_start(started_at: datetime, server_modified: datetime) -> datetime:
    """Normalizes the start time to UTC.

    The original pipeline records datetime.now().isoformat() without an
    offset. The Dropbox SDK exposes server_modified as UTC without tzinfo;
    we use that difference to infer the machine's offset, same as in the
    main report.
    """
    if started_at.tzinfo is not None:
        return started_at.astimezone(timezone.utc)
    server_utc = server_modified.replace(tzinfo=timezone.utc)
    delta_hours = (server_utc.replace(tzinfo=None) - started_at).total_seconds() / 3600
    offset_hours = round(-delta_hours)
    offset = timezone(timedelta(hours=offset_hours))
    return started_at.replace(tzinfo=offset).astimezone(timezone.utc)


def collect_locks(
    dbx,
    root: str,
    entries,
    now: datetime | None = None,
    include_audio_duration: bool = False,
) -> list[LockRecord]:
    now_utc = (now or datetime.now().astimezone()).astimezone(timezone.utc)
    files_by_path = {entry.path_display: entry for entry in entries}
    locks: list[LockRecord] = []
    for entry in entries:
        if lock_suffix_for(entry.name) is None:
            continue
        content = read_remote_text(dbx, entry.path_display)
        machine, started_raw = parse_lock(content)
        started_utc = None
        if started_raw:
            try:
                started_utc = normalize_lock_start(
                    datetime.fromisoformat(started_raw), entry.server_modified
                )
            except ValueError:
                started_utc = None
        age = max(0.0, (now_utc - started_utc).total_seconds()) if started_utc else None
        stem = strip_lock_suffix(entry.path_display)
        transcript_path = stem + TRANSCRIPT_SUFFIX
        if transcript_path not in files_by_path:
            legacy_path = stem + LEGACY_TRANSCRIPT_SUFFIX
            if legacy_path in files_by_path:
                transcript_path = legacy_path
        audio_duration = None
        if include_audio_duration:
            audio_duration = (
                transcript_audio_duration(dbx, transcript_path)
                if transcript_path in files_by_path
                else None
            )
            if audio_duration is None:
                for extension in AUDIO_EXTENSIONS:
                    audio_path = stem + extension
                    if audio_path in files_by_path:
                        audio_duration = probe_remote_audio_duration(dbx, audio_path)
                        break
        locks.append(
            LockRecord(
                path=entry.path_display,
                name=relative_name(entry.path_display, root),
                machine=machine,
                started_raw=started_raw,
                started_utc=started_utc,
                age_seconds=age,
                audio_duration_seconds=audio_duration,
                content=content.strip(),
                server_modified=entry.server_modified,
            )
        )
    return sorted(locks, key=lambda item: item.path)


def parse_age(value: str) -> int:
    match = VALID_AGE_RE.fullmatch(value)
    if not match:
        raise ValueError(
            f"Invalid duration: {value!r}. Use exactly formats like 1h, 10m, or 30s, with no spaces."
        )
    amount = int(match.group("amount"))
    unit = match.group("unit")
    multiplier = {"h": 3600, "m": 60, "s": 1}[unit]
    return amount * multiplier


def format_elapsed(seconds: float | None) -> str:
    if seconds is None:
        return "unknown time"
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


def format_age_limit(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def display_start(lock: LockRecord, report_tz: timezone) -> str:
    if lock.started_utc is None:
        return "n/a"
    return lock.started_utc.astimezone(report_tz).strftime("%Y-%m-%d %H:%M:%S")


def md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def summarize_entries(entries) -> tuple[int, int]:
    audio_count = sum(PurePosixPath(entry.name).suffix.lower() in AUDIO_EXTENSIONS for entry in entries)
    transcript_count = sum(transcript_suffix_for(entry.name) is not None for entry in entries)
    return audio_count, transcript_count
