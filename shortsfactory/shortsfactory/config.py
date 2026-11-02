"""All settings live here and come from environment variables. No keys in code."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    pexels_api_key: str | None
    gemini_api_key: str | None = None
    script_model: str = "claude-haiku-5-5"
    gemini_model: str = "gemini-2.5-flash"  # model names change; override with SF_GEMINI_MODEL
    voice: str = "en-US-AriaNeural"
    voice_rate: str = "+8%"  # edge-tts rate; Shorts reward brisk delivery
    width: int = 1080
    height: int = 1920
    fps: int = 30
    scene_tail_pad: float = 0.15  # seconds of breathing room after each scene
    font: str = "DejaVu Sans"
    work_dir: Path = Path("work")
    out_dir: Path = Path("out")

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ.get
        return cls(
            anthropic_api_key=e("ANTHROPIC_API_KEY"),
            pexels_api_key=e("PEXELS_API_KEY"),
            gemini_api_key=e("GEMINI_API_KEY"),
            script_model=e("SF_SCRIPT_MODEL", cls.script_model),
            gemini_model=e("SF_GEMINI_MODEL", cls.gemini_model),
            voice=e("SF_VOICE", cls.voice),
            voice_rate=e("SF_VOICE_RATE", cls.voice_rate),
            font=e("SF_FONT", cls.font),
            work_dir=Path(e("SF_WORK_DIR", "work")),
            out_dir=Path(e("SF_OUT_DIR", "out")),
        )
