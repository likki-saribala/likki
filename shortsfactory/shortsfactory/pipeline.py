"""Phase 1 pipeline: topic -> script -> voice -> footage -> captions -> MP4 (+ metadata sidecar)."""
from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .captions import build_ass
from .config import Settings
from .footage import Footage
from .music import pick_track
from .render import burn_captions, concat_segments, render_segment
from .script import ScriptWriter
from .tts import TTS, WordTiming

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

    segments: list[Path] = []
    all_words: list[WordTiming] = []
    offset = 0.0
    for i, scene in enumerate(script.scenes):
        audio = await tts.synth(scene.text, work / f"audio_{i}.mp3")
        clip = footage.fetch(scene.query, work / f"clip_{i}.mp4")
        seg_len = audio.duration + cfg.scene_tail_pad
        seg = work / f"seg_{i}.mp4"
        render_segment(clip, audio.path, seg_len, seg, cfg.width, cfg.height, cfg.fps)
        segments.append(seg)
        all_words += [WordTiming(w.text, w.start + offset, w.end + offset) for w in audio.words]
        offset += seg_len
        log.info("scene %d/%d done (%.1fs)", i + 1, len(script.scenes), seg_len)

    (work / "captions.ass").write_text(build_ass(all_words, cfg.width, cfg.height, cfg.font), encoding="utf-8")
    concat_segments(segments, work / "joined.mp4")
    final = cfg.out_dir / f"{slug}.mp4"
    track = pick_track(cfg.music_dir)
    burn_captions(work / "joined.mp4", "captions.ass", final, track, offset, cfg.music_volume)

    meta = cfg.out_dir / f"{slug}.json"
    meta.write_text(
        json.dumps(
            {
                "topic": topic,
                "created": datetime.now(timezone.utc).isoformat(),
                "duration": round(offset, 2),
                "music": track.name if track else None,
                **script.to_dict(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info("wrote %s (%.1fs)", final, offset)
    return Result(final, meta, offset)
