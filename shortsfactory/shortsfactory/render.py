"""ffmpeg assembly: per-scene segment (clip + voice), concat, then burn captions."""
from __future__ import annotations

from pathlib import Path

from .media import run_ffmpeg


def render_segment(clip: Path, audio: Path, duration: float, out: Path, w: int, h: int, fps: int) -> None:
    """Clip is looped if too short, cropped to w x h, cut to `duration`; audio is padded with silence."""
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},setsar=1"
    run_ffmpeg(
        [
            "-stream_loop", "-1", "-i", str(clip),
            "-i", str(audio),
            "-t", f"{duration:.3f}",
            "-vf", vf,
            "-af", "apad",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            str(out),
        ]
    )


def concat_segments(segments: list[Path], out: Path) -> None:
    """Segments share identical encode params, so stream-copy concat is safe. Paths are in `out`'s folder."""
    listing = out.parent / "segments.txt"
    listing.write_text("".join(f"file '{s.name}'\n" for s in segments), encoding="utf-8")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", listing.name, "-c", "copy", out.name], cwd=out.parent)


def burn_captions(video: Path, ass_name: str, out: Path) -> None:
    """`ass_name` must sit next to `video`; running with that cwd avoids filter-path escaping."""
    run_ffmpeg(
        [
            "-i", video.name,
            "-vf", f"ass={ass_name}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart",
            str(out.resolve()),
        ],
        cwd=video.parent,
    )
