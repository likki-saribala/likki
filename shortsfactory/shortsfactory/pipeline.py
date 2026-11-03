"""Phase 1 pipeline: topic -> script -> ONE continuous voice track -> footage -> captions -> MP4 (+ metadata sidecar)."""
from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .align import scene_durations
from .captions import build_ass
from .config import Settings
from .footage import Footage
from .music import pick_track
from .render import concat_segments, finalize, render_segment
from .script import ScriptWriter
from .tts import TTS

log = logging.getLogger("sf.pipeline")


@dataclass
class Result:
    video: Path
    metadata: Path
    duration: float


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50] or "short"


async def make_short(topic: str, writer: ScriptWriter, tts: TTS, footage: Footage, cfg: Settings) -> Result:
    script = writer.write(topic)
    script.validate()
    log.info("script: %r, %d scenes, %d words", script.title, len(script.scenes), script.word_count())

    slug = slugify(script.title)
    work = (cfg.work_dir / slug).resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    # One TTS call for the whole script: a single continuous read has natural flow across sentences,
    # unlike one clip per scene, which restarts the voice (and its intonation) at every cut.
    texts = [s.text for s in script.scenes]
    voice = await tts.synth(" ".join(texts), work / "voice.mp3")
    durations = scene_durations(texts, voice.words, voice.duration, cfg.end_pad)
    total = sum(durations)

    segments: list[Path] = []
    for i, (scene, dur) in enumerate(zip(script.scenes, durations)):
        clip = footage.fetch(scene.query, work / f"clip_{i}.mp4")
        seg = work / f"seg_{i}.mp4"
        render_segment(clip, dur, seg, cfg.width, cfg.height, cfg.fps)
        segments.append(seg)
        log.info("scene %d/%d done (%.1fs)", i + 1, len(script.scenes), dur)

    (work / "captions.ass").write_text(build_ass(voice.words, cfg.width, cfg.height, cfg.font), encoding="utf-8")
    concat_segments(segments, work / "joined.mp4")
    track = pick_track(cfg.music_dir)
    final = cfg.out_dir / f"{slug}.mp4"
    finalize(work / "joined.mp4", voice.path, "captions.ass", final, total, track, cfg.music_volume)

    meta = cfg.out_dir / f"{slug}.json"
    meta.write_text(
        json.dumps(
            {
                "topic": topic,
                "created": datetime.now(timezone.utc).isoformat(),
                "duration": round(total, 2),
                "music": track.name if track else None,
                **script.to_dict(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info("wrote %s (%.1fs)", final, total)
    return Result(final, meta, total)
