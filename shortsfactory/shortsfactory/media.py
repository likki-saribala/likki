"""Thin, loud wrappers around ffmpeg/ffprobe. Failures raise with ffmpeg's own error text."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger("sf.media")


class MediaError(RuntimeError):
    pass


def run_ffmpeg(args: list[str], cwd: Path | None = None) -> None:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    log.debug("ffmpeg %s", " ".join(args))
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise MediaError(f"ffmpeg failed ({proc.returncode}): {proc.stderr.strip()[-800:]}")


def probe_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise MediaError(f"ffprobe failed for {path}: {proc.stderr.strip()[-400:]}")
    return float(proc.stdout.strip())
