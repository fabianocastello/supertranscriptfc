#!/usr/bin/env python3
"""VoxelFC Doctor: diagnoses whether this machine's VoxelFC installation is
set up correctly.

Checks Python version, the virtual environment (including the "moved
after creation" launcher-path bug that has bitten Windows/renamed
folders before), FFmpeg, required dependencies (including mlx-whisper on
Apple Silicon), GPU/acceleration availability, .env credentials, live
Dropbox connectivity, and the VOXELFC_HOME directory.

Usage:
    source .venv/bin/activate
    python utils/voxel_doctor.py
"""
from __future__ import annotations

import importlib
import platform
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402

# Load explicitly from the repo's own .env, regardless of the caller's cwd -
# voxelfc.config's own load_dotenv() call depends on cwd and could silently
# miss it if the doctor is run from elsewhere.
load_dotenv(REPO_ROOT / ".env")

OK, WARN, FAIL = "OK", "WARN", "FAIL"
results: list[tuple[str, str, str]] = []  # (check name, status, message)


def check(name: str, status: str, message: str) -> None:
    results.append((name, status, message))


def check_python_version() -> None:
    version = platform.python_version()
    if sys.version_info >= (3, 10):
        check("Python version", OK, f"{version} (>= 3.10 required)")
    else:
        check("Python version", FAIL, f"{version} - VoxelFC requires >= 3.10")


def check_venv() -> None:
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    if not venv_python.exists():
        check("Virtual environment", FAIL, f"{venv_python} not found - run ./scripts/install.sh")
        return
    if sys.prefix == sys.base_prefix:
        check(
            "Virtual environment",
            WARN,
            "Not running inside a venv - activate it first: source .venv/bin/activate",
        )
        return
    current = Path(sys.executable).resolve()
    expected = venv_python.resolve()
    if current != expected:
        check(
            "Virtual environment",
            WARN,
            f"Running interpreter ({current}) isn't this project's .venv ({expected}) - "
            "you may have another venv or conda environment active.",
        )
    else:
        check("Virtual environment", OK, str(venv_python))


_POLYGLOT_EXEC_RE = re.compile(r"""^'''exec' "(?P<path>.+?)" "\$0" "\$@"$""")


def _launcher_target_path(launcher_path: Path) -> str | None:
    """Extracts the interpreter path a generated console-script launcher
    points to, handling both forms setuptools/pip use: a plain shebang
    (#!/path/to/python), and the "polyglot" form (#!/bin/sh + an embedded
    'exec' line) used instead whenever the interpreter's own path contains
    a space, since a plain shebang can't reliably quote that."""
    try:
        lines = launcher_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if not lines or not lines[0].startswith("#!"):
        return None
    if lines[0].strip() != "#!/bin/sh":
        return lines[0][2:].strip()
    for line in lines[1:4]:
        match = _POLYGLOT_EXEC_RE.match(line)
        if match:
            return match.group("path")
    return None


def check_venv_launcher_paths() -> None:
    """Catches the "venv moved/renamed after creation" bug: on both Linux
    and macOS, .venv/bin/pip's launcher bakes in the absolute path to
    .venv/bin/python at creation time. If the project folder is later
    moved or renamed, that path goes stale and pip/voxelfc fail with
    errors like "bad interpreter" or "Fatal error in launcher" (the exact
    failure hit on ps20 after C:\\supertranscriptfc was renamed to
    C:\\voxelfc)."""
    pip_path = REPO_ROOT / ".venv" / "bin" / "pip"
    if not pip_path.exists():
        return  # already reported as missing by check_venv
    target = _launcher_target_path(pip_path)
    if target is None:
        return  # not a text launcher on this platform, nothing to check
    if not target.startswith(str(REPO_ROOT)):
        check(
            "venv launcher paths",
            FAIL,
            f".venv/bin/pip points to '{target}', which isn't inside this folder "
            f"({REPO_ROOT}) - the project was likely moved/renamed after the venv was "
            "created. Fix: rm -rf .venv && ./scripts/install.sh",
        )
    else:
        check("venv launcher paths", OK, "launcher paths match this folder's current location")


def check_ffmpeg() -> None:
    for binary in ("ffmpeg", "ffprobe"):
        path = shutil.which(binary)
        if path is None:
            check(binary, FAIL, "not found in PATH - install FFmpeg")
        else:
            check(binary, OK, path)


def check_dependency(module_name: str, extra_name: str) -> None:
    try:
        importlib.import_module(module_name)
        check(module_name, OK, "installed")
    except ImportError as exc:
        check(module_name, FAIL, f"not installed (pip install -e '.[{extra_name}]') - {exc}")


def check_mlx() -> None:
    is_apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"
    if not is_apple_silicon:
        check("mlx-whisper", OK, "not applicable (not Apple Silicon)")
        return
    try:
        importlib.import_module("mlx_whisper")
        check("mlx-whisper", OK, "installed (GPU/Neural Engine transcription enabled)")
    except ImportError:
        check(
            "mlx-whisper",
            WARN,
            "not installed on Apple Silicon - transcription will fall back to CPU. "
            "Install with: pip install -e '.[mlx]'",
        )


def check_gpu_acceleration() -> None:
    try:
        import torch
    except ImportError:
        check("GPU acceleration", WARN, "torch not installed, can't detect")
        return
    if torch.cuda.is_available():
        check("GPU acceleration", OK, f"CUDA available ({torch.cuda.get_device_name(0)})")
    elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        check("GPU acceleration", OK, "MPS available (Apple Silicon, used for diarization)")
    else:
        check("GPU acceleration", WARN, "No GPU acceleration detected - will run on CPU (slower)")


def check_cli_entrypoint() -> None:
    path = shutil.which("voxelfc")
    if path is None:
        check("voxelfc CLI", WARN, "not found in PATH - activate the venv: source .venv/bin/activate")
    else:
        check("voxelfc CLI", OK, path)


def check_env_file() -> None:
    from dotenv import dotenv_values

    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        check(".env file", FAIL, f"{env_path} not found - copy from .env.example")
        return
    values = dotenv_values(env_path)
    required = ["DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN", "HF_TOKEN"]
    missing = [key for key in required if not values.get(key)]
    if missing:
        check(".env file", WARN, f"missing/empty: {', '.join(missing)}")
    else:
        check(".env file", OK, f"all required variables set ({len(required)}/{len(required)})")


def check_hf_token_format() -> None:
    from voxelfc.config import Config

    hf_token = Config().hf_token
    if not hf_token:
        check("HF_TOKEN", WARN, "not configured - diarization will fail")
    elif hf_token.startswith("hf_"):
        check("HF_TOKEN", OK, "configured (format looks valid)")
    else:
        check("HF_TOKEN", WARN, "configured but doesn't start with 'hf_' - double-check the token")


def check_dropbox_connectivity() -> None:
    from voxelfc.config import Config

    config = Config()
    if not config.has_dropbox_credentials:
        check("Dropbox connectivity", WARN, "credentials not configured in .env, skipping")
        return
    try:
        from voxelfc.dropbox_client import DropboxClient

        client = DropboxClient(
            config.dropbox_app_key, config.dropbox_app_secret, config.dropbox_refresh_token
        )
        client.dbx.users_get_current_account()
        check("Dropbox connectivity", OK, "authenticated successfully")
    except Exception as exc:
        check("Dropbox connectivity", FAIL, f"authentication failed: {exc}")


def check_voxelfc_home() -> None:
    from voxelfc.config import Config

    config = Config()
    try:
        config.ensure_dirs()
        check("VOXELFC_HOME", OK, f"{config.home_dir} (writable)")
    except OSError as exc:
        check("VOXELFC_HOME", FAIL, f"{config.home_dir} not writable: {exc}")


def print_report() -> int:
    print("=== VoxelFC Doctor ===\n")
    width = max(len(name) for name, _, _ in results)
    symbols = {OK: "[OK]  ", WARN: "[WARN]", FAIL: "[FAIL]"}
    exit_code = 0
    for name, status, message in results:
        print(f"{symbols[status]} {name.ljust(width)}  {message}")
        if status == FAIL:
            exit_code = 1

    n_ok = sum(1 for _, s, _ in results if s == OK)
    n_warn = sum(1 for _, s, _ in results if s == WARN)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    print(f"\n{n_ok} OK, {n_warn} warning(s), {n_fail} failure(s).")
    if n_fail:
        print("Some checks failed - fix the [FAIL] items above before relying on this installation.")
    elif n_warn:
        print("No failures, but the [WARN] items above are worth checking.")
    else:
        print("Everything looks good!")
    return exit_code


def main() -> int:
    check_python_version()
    check_venv()
    check_venv_launcher_paths()
    check_ffmpeg()
    check_dependency("dropbox", "dropbox")
    check_dependency("faster_whisper", "transcribe")
    check_dependency("pyannote.audio", "diarize")
    check_dependency("torch", "diarize")
    check_mlx()
    check_gpu_acceleration()
    check_cli_entrypoint()
    check_env_file()
    check_hf_token_format()
    check_dropbox_connectivity()
    check_voxelfc_home()
    return print_report()


if __name__ == "__main__":
    raise SystemExit(main())
