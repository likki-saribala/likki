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
    """Real audio via ffmpeg sine (0.3s per word); synthetic word timings. Called once per video."""

    SEC_PER_WORD = 0.3

    async def synth(self, text, out_path):
        words = text.split()
        run_ffmpeg(["-f", "lavfi", "-i", f"sine=frequency=440:duration={len(words) * self.SEC_PER_WORD}", str(out_path)])
        step = self.SEC_PER_WORD
        return SceneAudio(out_path, probe_duration(out_path), [WordTiming(w, i * step, (i + 1) * step) for i, w in enumerate(words)])


def test_end_to_end_produces_vertical_mp4(tmp_path):
    cfg = Settings(None, None, work_dir=tmp_path / "work", out_dir=tmp_path / "out")
    res = asyncio.run(make_short("honey", FakeWriter(), FakeTTS(), PlaceholderFootage(), cfg))

    assert res.video.exists() and res.video.suffix == ".mp4"
    # 4 scenes * 6 words * 0.3s = 7.2s of voice, plus the 0.5s end pad
    assert abs(probe_duration(res.video) - 7.7) < 0.4

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


def _mean_volume(path):
    import re
    import subprocess

    out = subprocess.run(["ffmpeg", "-i", str(path), "-af", "volumedetect", "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.search(r"mean_volume: (-?[\d.]+) dB", out).group(1))


class SilentTTS(FakeTTS):
    """Digital silence for the voice track, so any sound in the final video must come from the music."""

    async def synth(self, text, out_path):
        words = text.split()
        run_ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(len(words) * self.SEC_PER_WORD), str(out_path)])
        step = self.SEC_PER_WORD
        return SceneAudio(out_path, probe_duration(out_path), [WordTiming(w, i * step, (i + 1) * step) for i, w in enumerate(words)])


def test_music_is_mixed_in_loops_and_video_length_unchanged(tmp_path):
    music = tmp_path / "music"
    music.mkdir()
    run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=220:duration=3", str(music / "bed.mp3")])  # shorter than video: must loop

    no_music = Settings(None, None, work_dir=tmp_path / "w1", out_dir=tmp_path / "o1", music_dir=tmp_path / "nonexistent")
    with_music = Settings(None, None, work_dir=tmp_path / "w2", out_dir=tmp_path / "o2", music_dir=music)
    a = asyncio.run(make_short("t", FakeWriter(), SilentTTS(), PlaceholderFootage(), no_music))
    b = asyncio.run(make_short("t", FakeWriter(), SilentTTS(), PlaceholderFootage(), with_music))

    assert json.loads(a.metadata.read_text())["music"] is None
    assert json.loads(b.metadata.read_text())["music"] == "bed.mp3"
    assert abs(probe_duration(b.video) - probe_duration(a.video)) < 0.4  # looped to full length, not truncated
    assert _mean_volume(a.video) < -80  # no music, silent voice: silence
    assert _mean_volume(b.video) > -50  # the bed is audibly present, even past its own 3s length
