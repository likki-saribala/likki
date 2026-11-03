import httpx
import pytest

from shortsfactory.captions import build_ass, chunk_words
from shortsfactory.footage import FootageNotFound, PexelsFootage, pick_file
from shortsfactory.models import Script
from shortsfactory.tts import WordTiming


def scene(text="One fact here.", query="ocean", claim="c"):
    return {"text": text, "query": query, "claim": claim}


def test_script_roundtrip_and_validation():
    d = {"title": "T", "scenes": [scene() for _ in range(4)], "hashtags": ["a"]}
    assert Script.from_dict(d).to_dict()["title"] == "T"
    with pytest.raises(ValueError):
        Script.from_dict({"title": "T", "scenes": [scene()] * 2})  # too few
    with pytest.raises(ValueError):
        Script.from_dict({"title": "T", "scenes": [scene("word " * 60)] * 4})  # too long
    with pytest.raises(ValueError):
        Script.from_dict({"scenes": []})  # malformed


def test_caption_chunks_and_ass():
    from shortsfactory.captions import MAX_CHARS_PER_CHUNK

    ws = [WordTiming(t, i * 0.3, i * 0.3 + 0.25) for i, t in enumerate("Honey never spoils, ever. Really {x}".split())]
    chunks = chunk_words(ws)
    assert all(len(c) <= 3 for c in chunks)
    for c in chunks:  # width budget: never over the char limit unless it is one long word
        assert len(c) == 1 or len(" ".join(w.text for w in c)) <= MAX_CHARS_PER_CHUNK
    assert chunks[-2][-1].text == "ever."  # sentence end closes a chunk
    ass = build_ass(ws, 1080, 1920, "DejaVu Sans")
    assert "PlayResY: 1920" in ass and "HONEY NEVER" in ass
    assert "{x}" not in ass  # override braces neutralised


def test_long_words_get_their_own_chunk_instead_of_overflowing():
    ws = [WordTiming(t, i, i + 0.5) for i, t in enumerate("International infrastructure consequences".split())]
    assert [len(c) for c in chunk_words(ws)] == [1, 1, 1]


def test_pick_file_prefers_portrait_near_1080():
    video = {
        "video_files": [
            {"file_type": "video/mp4", "width": 1920, "height": 1080, "link": "land"},
            {"file_type": "video/mp4", "width": 540, "height": 960, "link": "small"},
            {"file_type": "video/mp4", "width": 1080, "height": 1920, "link": "good"},
            {"file_type": "video/webm", "width": 1080, "height": 1920, "link": "webm"},
        ]
    }
    assert pick_file(video)["link"] == "good"
    assert pick_file({"video_files": []}) is None


def _pexels(videos_by_query):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "api.pexels.com":
            assert req.headers["Authorization"] == "k"
            return httpx.Response(200, json={"videos": videos_by_query.get(req.url.params["query"], [])})
        return httpx.Response(200, content=b"VIDEO")

    return PexelsFootage("k", httpx.Client(transport=httpx.MockTransport(handler)))


def _vid(i):
    return {"id": i, "video_files": [{"file_type": "video/mp4", "width": 1080, "height": 1920, "link": f"https://cdn/{i}.mp4"}]}


def test_pexels_dedupes_falls_back_and_fails_loudly(tmp_path):
    f = _pexels({"ocean waves": [_vid(1), _vid(2)], "waves": [_vid(3)]})
    assert f.fetch("ocean waves", tmp_path / "a.mp4").read_bytes() == b"VIDEO"
    f.fetch("ocean waves", tmp_path / "b.mp4")  # takes vid 2, not 1 again
    assert f._used == {1, 2}
    f.fetch("ocean waves", tmp_path / "c.mp4")  # exhausted -> falls back to last word
    assert f._used == {1, 2, 3}
    with pytest.raises(FootageNotFound):
        f.fetch("nothing here", tmp_path / "d.mp4")
