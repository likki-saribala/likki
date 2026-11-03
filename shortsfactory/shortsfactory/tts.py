"""Text-to-speech with word timings. edge-tts is unofficial: it can break without notice."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .media import probe_duration

log = logging.getLogger("sf.tts")


@dataclass
class WordTiming:
    text: str
    start: float  # seconds from the start of this scene's audio
    end: float


@dataclass
class SceneAudio:
    path: Path
    duration: float
    words: list[WordTiming]


class TTS(Protocol):
    async def synth(self, text: str, out_path: Path) -> SceneAudio: ...


class EdgeTTS:
    def __init__(self, voice: str, rate: str) -> None:
        self._voice = voice
        self._rate = rate

    async def synth(self, text: str, out_path: Path) -> SceneAudio:
        import edge_tts

        comm = edge_tts.Communicate(text, self._voice, rate=self._rate, boundary="WordBoundary")
        words: list[WordTiming] = []
        with out_path.open("wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start = chunk["offset"] / 1e7  # service reports 100-ns ticks
                    words.append(WordTiming(chunk["text"], start, start + chunk["duration"] / 1e7))
        if not words:
            raise RuntimeError("TTS returned audio but no word timings; captions would be wrong")
        return SceneAudio(out_path, probe_duration(out_path), words)
