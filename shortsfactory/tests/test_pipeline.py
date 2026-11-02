"""End to end with REAL ffmpeg. Only the network parts (Claude, edge-tts, Pexels) are faked."""
import asyncio
import json

from shortsfactory.config import Settings
from shortsfactory.footage import PlaceholderFootage
from shortsfactory.media import probe_duration, run_ffmpeg
from shortsfactory.models import Scene, Script
from shortsfactory.pipeline import make_short
from shortsfactory.tts import SceneAudio, WordTiming


class FakeWriter:
    def write(self, topic):
        return Script("Honey Never Spoils", [Scene(f"Scene {i} has five words total.", "honey", f"claim {i}") for i in range(4)], ["facts"])


class FakeTTS:
    """Real 1.5s audio file via ffmpeg sine; synthetic word timings."""

    async def synth(self, text, out_path):
        run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=440:duration=1.5", str(out_path)])
        words = text.split()
        step = 1.5 / len(words)
        return SceneAudio(out_path, probe_duration(out_path), [WordTiming(w, i * step, (i + 1) * step) for i, w in enumerate(words)])


def test_end_to_end_produces_vertical_mp4(tmp_path):
    cfg = Settings(None, None, work_dir=tmp_path / "work", out_dir=tmp_path / "out")
    res = asyncio.run(make_short("honey", FakeWriter(), FakeTTS(), PlaceholderFootage(), cfg))

    assert res.video.exists() and res.video.suffix == ".mp4"
    # 4 scenes * (1.5s audio + 0.15 pad) = 6.6s, allow encoder rounding
    assert abs(probe_duration(res.video) - 6.6) < 0.4

    import subprocess

    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(res.video)],
        capture_output=True, text=True,
    ).stdout.strip()
    assert out == "1080,1920"
    audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(res.video)], capture_output=True, text=True).stdout.strip()
    assert audio == "aac"

    meta = json.loads(res.metadata.read_text())
    assert meta["title"] == "Honey Never Spoils" and meta["scenes"][0]["claim"] == "claim 0"
