"""Map scene boundaries onto a single continuous narration, using the TTS word timings."""
from __future__ import annotations

from .tts import WordTiming


class AlignmentError(RuntimeError):
    pass


def _alnum(text: str) -> int:
    return sum(ch.isalnum() for ch in text)


def scene_durations(scene_texts: list[str], words: list[WordTiming], audio_duration: float, end_pad: float) -> list[float]:
    """Length of each scene's visuals so each cut lands exactly where its first word is spoken.

    Scenes are matched to words by counting letters and digits, which is immune to how the TTS tokenises
    punctuation. If the counts do not line up we fail loudly: wrong cuts would silently mis-sync everything.
    """
    ends: list[int] = []
    running = 0
    for t in scene_texts:
        running += _alnum(t)
        ends.append(running)
    spoken = sum(_alnum(w.text) for w in words)
    if spoken != running:
        raise AlignmentError(f"TTS words cover {spoken} letters/digits but the script has {running}; cannot place scene cuts")

    starts = [0.0]  # the first scene always opens the video
    seen = 0
    next_boundary = 0
    for w in words:
        if next_boundary < len(ends) - 1 and seen == ends[next_boundary]:
            starts.append(w.start)
            next_boundary += 1
        seen += _alnum(w.text)
    if len(starts) != len(scene_texts):
        raise AlignmentError(f"found {len(starts)} scene starts for {len(scene_texts)} scenes; a cut fell inside a spoken word")

    durs = [starts[i + 1] - starts[i] for i in range(len(starts) - 1)]
    durs.append(audio_duration + end_pad - starts[-1])
    if any(d <= 0 for d in durs):
        raise AlignmentError(f"non-positive scene duration: {durs}")
    return durs
