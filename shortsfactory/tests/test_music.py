import random

from shortsfactory.music import pick_track


def test_pick_track_handles_missing_empty_and_filled(tmp_path):
    assert pick_track(tmp_path / "nope") is None
    assert pick_track(tmp_path) is None  # exists but empty
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "b.WAV").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("ignore me")
    picked = {pick_track(tmp_path, random.Random(i)).name for i in range(30)}
    assert picked == {"a.mp3", "b.WAV"}
