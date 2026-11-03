import httpx
import pytest

from shortsfactory.footage import FootageNotFound, PixabayFootage, pick_pixabay_rendition


def _hit(i, **sizes):
    return {"id": i, "videos": {k: {"url": f"https://cdn/{i}-{k}.mp4", "width": h * 16 // 9, "height": h} for k, h in sizes.items()}}


def test_rendition_prefers_smallest_that_is_1080_tall_and_skips_empty_urls():
    hit = _hit(1, tiny=360, medium=1080, large=2160)
    assert pick_pixabay_rendition(hit)["height"] == 1080
    assert pick_pixabay_rendition(_hit(2, tiny=360, small=720))["height"] == 720  # best available
    hit = _hit(3, large=2160)
    hit["videos"]["large"]["url"] = ""
    assert pick_pixabay_rendition(hit) is None


def test_fetch_dedupes_falls_back_and_fails_loudly(tmp_path):
    data = {"sea waves": [_hit(1, medium=1080), _hit(2, medium=1080)], "waves": [_hit(3, medium=1080)]}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "pixabay.com":
            assert req.url.params["key"] == "k"
            return httpx.Response(200, json={"hits": data.get(req.url.params["q"], [])})
        return httpx.Response(200, content=b"VIDEO")

    f = PixabayFootage("k", httpx.Client(transport=httpx.MockTransport(handler)))
    assert f.fetch("sea waves", tmp_path / "a.mp4").read_bytes() == b"VIDEO"
    f.fetch("sea waves", tmp_path / "b.mp4")
    f.fetch("sea waves", tmp_path / "c.mp4")  # exhausted -> last word
    assert f._used == {1, 2, 3}
    with pytest.raises(FootageNotFound):
        f.fetch("zzz qqq", tmp_path / "d.mp4")
