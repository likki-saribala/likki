"""Stock footage. Pexels is the real source; PlaceholderFootage exists only for offline dry runs."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

import httpx

from .media import run_ffmpeg

log = logging.getLogger("sf.footage")

PEXELS_URL = "https://api.pexels.com/videos/search"


class FootageNotFound(RuntimeError):
    pass


class Footage(Protocol):
    def fetch(self, query: str, dest: Path) -> Path: ...


def pick_file(video: dict, target_width: int = 1080) -> dict | None:
    """Best portrait mp4 rendition: closest to target width, never upscaling by much."""
    files = [
        f
        for f in video.get("video_files", [])
        if f.get("file_type") == "video/mp4" and f.get("height", 0) > f.get("width", 0) and f.get("link")
    ]
    if not files:
        return None
    return min(files, key=lambda f: (f["width"] < 720, abs(f["width"] - target_width)))


class PexelsFootage:
    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=60, follow_redirects=True)
        self._headers = {"Authorization": api_key}
        self._used: set[int] = set()  # no repeated clip within one Short

    def _search(self, query: str) -> dict | None:
        resp = self._client.get(
            PEXELS_URL,
            headers=self._headers,
            params={"query": query, "orientation": "portrait", "per_page": 15, "size": "medium"},
        )
        resp.raise_for_status()
        for video in resp.json().get("videos", []):
            if video["id"] in self._used:
                continue
            f = pick_file(video)
            if f:
                self._used.add(video["id"])
                return f
        return None

    def fetch(self, query: str, dest: Path) -> Path:
        # Try the full phrase, then just its last word, before giving up loudly.
        candidates = [query] + ([query.split()[-1]] if len(query.split()) > 1 else [])
        for q in candidates:
            f = self._search(q)
            if f:
                log.info("footage %r -> %dx%d", q, f["width"], f["height"])
                with self._client.stream("GET", f["link"]) as r:
                    r.raise_for_status()
                    with dest.open("wb") as out:
                        for part in r.iter_bytes():
                            out.write(part)
                return dest
        raise FootageNotFound(f"no usable portrait footage on Pexels for {query!r}")


PIXABAY_URL = "https://pixabay.com/api/videos/"


def pick_pixabay_rendition(hit: dict) -> dict | None:
    """Smallest rendition that is at least 1080 tall (we crop to 9:16, so height is what matters);
    otherwise the biggest one available."""
    rends = [r for r in hit.get("videos", {}).values() if r.get("url") and r.get("height")]
    if not rends:
        return None
    big = [r for r in rends if r["height"] >= 1080]
    return min(big, key=lambda r: r["height"]) if big else max(rends, key=lambda r: r["height"])


class PixabayFootage:
    """Pixabay videos are mostly LANDSCAPE (no portrait filter exists), so they get centre-cropped to 9:16."""

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=60, follow_redirects=True)
        self._key = api_key
        self._used: set[int] = set()

    def _search(self, query: str) -> dict | None:
        resp = self._client.get(PIXABAY_URL, params={"key": self._key, "q": query[:100], "per_page": 20, "safesearch": "true"})
        resp.raise_for_status()
        for hit in resp.json().get("hits", []):
            if hit["id"] in self._used:
                continue
            r = pick_pixabay_rendition(hit)
            if r:
                self._used.add(hit["id"])
                return r
        return None

    def fetch(self, query: str, dest: Path) -> Path:
        candidates = [query] + ([query.split()[-1]] if len(query.split()) > 1 else [])
        for q in candidates:
            r = self._search(q)
            if r:
                log.info("pixabay %r -> %dx%d", q, r["width"], r["height"])
                with self._client.stream("GET", r["url"]) as resp:
                    resp.raise_for_status()
                    with dest.open("wb") as out:
                        for part in resp.iter_bytes():
                            out.write(part)
                return dest
        raise FootageNotFound(f"no usable footage on Pixabay for {query!r}")


class PlaceholderFootage:
    """Solid-colour clips. Dry-run/testing only; never used unless explicitly requested."""

    _colors = ["0x1b2a49", "0x3d1e4f", "0x14463f", "0x4a2a1a"]

    def __init__(self) -> None:
        self._n = 0

    def fetch(self, query: str, dest: Path) -> Path:
        color = self._colors[self._n % len(self._colors)]
        self._n += 1
        log.warning("PLACEHOLDER footage for %r (not real stock video)", query)
        run_ffmpeg(["-f", "lavfi", "-i", f"color=c={color}:s=1080x1920:r=30:d=12", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dest)])
        return dest
