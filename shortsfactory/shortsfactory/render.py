"""ffmpeg assembly: silent video segment per scene, concat, then voice + captions + music in one final pass."""
from __future__ import annotations

from pathlib import Path

from .media import run_ffmpeg


def render_segment(clip: Path, duration: float, out: Path, w: int, h: int, fps: int) -> None:
    """Video only. Clip is looped if too short, cropped to w x h and cut to `duration`."""
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},setsar=1"
    run_ffmpeg(
        [
            "-stream_loop", "-1", "-i", str(clip),
            "-t", f"{duration:.3f}",
            "-vf", vf,
            "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            str(out),
        ]
    )


def concat_segments(segments: list[Path], out: Path) -> None:
    """Segments share identical encode params, so stream-copy concat is safe. Paths are in `out`'s folder."""
    listing = out.parent / "segments.txt"
    listing.write_text("".join(f"file '{s.name}'\n" for s in segments), encoding="utf-8")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", listing.name, "-c", "copy", out.name], cwd=out.parent)


def finalize(
    video: Path, voice: Path, ass_name: str, out: Path, duration: float, music: Path | None = None, music_volume: float = 0.22
) -> None:
    """Burn captions, lay the continuous voice over the video and (optionally) mix looping music under it.

    `ass_name` must sit next to `video`; running with that cwd avoids filter-path escaping.
    """
    common = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    audio_enc = ["-c:a", "aac", "-ar", "44100", "-ac", "2"]
    voice_in = f"[1:a]apad=whole_dur={duration:.3f}"  # voice runs to the very end of the video
    if music is None:
        run_ffmpeg(
            ["-i", video.name, "-i", str(voice.resolve()),
             "-filter_complex", f"[0:v]ass={ass_name}[v];{voice_in}[a]",
             "-map", "[v]", "-map", "[a]", "-t", f"{duration:.3f}", *common, *audio_enc, str(out.resolve())],
            cwd=video.parent,
        )
        return
    fade_out_at = max(duration - 1.5, 0.0)
    graph = (
        f"[0:v]ass={ass_name}[v];"
        f"{voice_in},asplit=2[voice1][voice2];"
        f"[2:a]volume={music_volume},afade=t=in:d=1.0,afade=t=out:st={fade_out_at:.2f}:d=1.5[bed];"
        # the voice drives a compressor on the music, so the bed dips whenever someone is speaking
        "[bed][voice1]sidechaincompress=threshold=0.03:ratio=10:attack=15:release=400[ducked];"
        "[voice2][ducked]amix=inputs=2:duration=first:dropout_transition=0,volume=2[a]"
    )
    run_ffmpeg(
        ["-i", video.name, "-i", str(voice.resolve()), "-stream_loop", "-1", "-i", str(music.resolve()),
         "-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-t", f"{duration:.3f}", *common, *audio_enc, str(out.resolve())],
        cwd=video.parent,
    )
