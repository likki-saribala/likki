import pytest

from shortsfactory.align import AlignmentError, scene_durations
from shortsfactory.tts import WordTiming


def words(text, step=0.4, start=0.0):
    return [WordTiming(w, start + i * step, start + (i + 1) * step) for i, w in enumerate(text.split())]


def test_cuts_land_on_the_first_word_of_each_scene():
    texts = ["Hello there, friend.", "This is scene two.", "Last one."]
    ws = words(" ".join(texts))  # 3 + 4 + 2 words at 0.4s each
    d = scene_durations(texts, ws, audio_duration=9 * 0.4, end_pad=0.5)
    assert d == pytest.approx([1.2, 1.6, 0.8 + 0.5])
    assert sum(d) == pytest.approx(9 * 0.4 + 0.5)  # video ends end_pad after the last word


def test_punctuation_and_hyphenation_do_not_confuse_matching():
    texts = ["It's twenty-thousand km up.", "Really?"]
    # a TTS may split "twenty-thousand" in two; letter counts still line up
    ws = [WordTiming(t, i * 0.5, i * 0.5 + 0.4) for i, t in enumerate(["It's", "twenty-", "thousand", "km", "up.", "Really?"])]
    assert scene_durations(texts, ws, 3.0, 0.5)[0] == pytest.approx(2.5)


def test_mismatch_fails_loudly_instead_of_misplacing_cuts():
    with pytest.raises(AlignmentError):
        scene_durations(["One two three."], words("One two"), 1.0, 0.5)
