"""Background music. Tracks come from a folder YOU fill with music you are licensed to use.

We deliberately do not download music from the internet: copyright claims on Shorts are real, and no
free service offers a music API we can rely on. Good sources: YouTube Audio Library (YouTube Studio),
and Pixabay Music (check each track's licence). Put 5-10 mp3 files in the folder and one is picked per video.
"""
from __future__ import annotations

import logging
import random
from pathlib import Path

log = logging.getLogger("sf.music")

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}


def pick_track(music_dir: Path, rng: random.Random | None = None) -> Path | None:
    rng = rng or random.Random()
    if not music_dir.is_dir():
        log.warning("no music folder at %s: this video will have NO background music", music_dir.resolve())
        return None
    tracks = sorted(p for p in music_dir.iterdir() if p.suffix.lower() in AUDIO_EXT)
    if not tracks:
        log.warning("music folder %s has no audio files: this video will have NO background music", music_dir.resolve())
        return None
    choice = rng.choice(tracks)
    log.info("music: %s", choice.name)
    return choice
