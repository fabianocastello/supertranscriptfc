from __future__ import annotations

import sys
import time


def format_duration(seconds: float) -> str:
    """Formats seconds as '2h58m32s', '55m10s', or '32s'."""
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


class ProgressPrinter:
    """Prints a progress line (% + ETA) that updates in place, based on how
    much of the audio (in seconds) has been processed so far. Only writes to
    the terminal (stderr); never goes into the log file."""

    def __init__(self, label: str, total_seconds: float, min_interval: float = 0.5):
        self.label = label
        self.total_seconds = total_seconds
        self.min_interval = min_interval
        self.start_time = time.monotonic()
        self._last_print = 0.0
        self._printed = False
        self._last_line_len = 0

    def update(self, processed_seconds: float) -> None:
        now = time.monotonic()
        if now - self._last_print < self.min_interval:
            return
        self._last_print = now
        self._render(processed_seconds, now)

    def _render(self, processed_seconds: float, now: float) -> None:
        if self.total_seconds <= 0:
            return
        elapsed = now - self.start_time
        pct = min(99.9, processed_seconds / self.total_seconds * 100)
        rate = processed_seconds / elapsed if elapsed > 0 else 0
        remaining_audio = max(0.0, self.total_seconds - processed_seconds)
        eta = remaining_audio / rate if rate > 0 else None
        eta_str = format_duration(eta) if eta is not None else "?"
        text = f"{self.label}: {pct:5.1f}% (ETA {eta_str})"
        padding = max(0, self._last_line_len - len(text))
        sys.stderr.write(f"\r{text}{' ' * padding}")
        sys.stderr.flush()
        self._last_line_len = len(text)
        self._printed = True

    def finish(self) -> None:
        if not self._printed:
            return
        sys.stderr.write(f"\r{self.label}: 100.0%" + " " * 20 + "\n")
        sys.stderr.flush()
