"""Script writing. ScriptWriter is the injection seam; ClaudeScriptWriter is the real one."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol

from .models import MAX_SCENES, MAX_WORDS, MIN_SCENES, Script

log = logging.getLogger("sf.script")


class ScriptWriter(Protocol):
    def write(self, topic: str) -> Script: ...


SYSTEM = f"""You write scripts for faceless YouTube Shorts that deliver quick, surprising, TRUE facts.

Rules:
- {MIN_SCENES}-{MAX_SCENES} scenes, at most {MAX_WORDS} words of narration in total.
- Scene 1 is the hook: a concrete, specific line that makes a stranger stop scrolling. No "Did you know".
- Every scene's narration is short, spoken English with one idea. No emojis, no hashtags in narration.
- Only well-established facts you are highly confident are correct. If unsure of a number, leave the number out.
  Never invent statistics, quotes, dates or names. Accuracy matters more than shock value.
- For each scene give `claim`: the single checkable factual claim it makes, stated plainly.
- For each scene give `query`: a concrete 1-3 word stock-footage search (something filmable, e.g. "ocean waves"),
  not an abstract concept.
- The last scene ends on a line that loops back to the hook or sets up a rewatch. No "like and subscribe".
- title: under 60 characters, no clickbait lies. hashtags: 3-5, lowercase, no '#' symbol."""

TOOL = {
    "name": "submit_script",
    "description": "Submit the finished Short script.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "query": {"type": "string"},
                        "claim": {"type": "string"},
                    },
                    "required": ["text", "query", "claim"],
                },
            },
            "hashtags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "scenes", "hashtags"],
    },
}


class ClaudeScriptWriter:
    def __init__(self, api_key: str, model: str) -> None:
        import anthropic  # imported lazily so tests/offline runs don't need a key

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def write(self, topic: str) -> Script:
        log.info("writing script for topic %r with %s", topic, self._model)
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=1500,
            system=SYSTEM,
            tools=[TOOL],
            tool_choice={"type": "tool", "name": "submit_script"},
            messages=[{"role": "user", "content": f"Topic: {topic}"}],
        )
        for block in resp.content:
            if block.type == "tool_use" and block.name == "submit_script":
                return Script.from_dict(block.input)  # validates; raises on a bad script
        raise RuntimeError("model did not return a script (no submit_script tool call)")


def _gemini_schema(node):
    """Gemini wants OpenAPI-style upper-case type names."""
    if isinstance(node, dict):
        return {k: (v.upper() if k == "type" and isinstance(v, str) else _gemini_schema(v)) for k, v in node.items()}
    if isinstance(node, list):
        return [_gemini_schema(x) for x in node]
    return node


class GeminiScriptWriter:
    """Free-tier-friendly alternative to Claude. Retries once, feeding the validation error back."""

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, model: str, client=None) -> None:
        import httpx

        self._client = client or httpx.Client(timeout=90)
        self._key = api_key
        self._model = model

    def _ask(self, prompt: str) -> str:
        resp = self._client.post(
            self.URL.format(model=self._model),
            headers={"x-goog-api-key": self._key},
            json={
                "systemInstruction": {"parts": [{"text": SYSTEM}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": _gemini_schema(TOOL["input_schema"]),
                    "temperature": 0.8,
                },
            },
        )
        resp.raise_for_status()
        try:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Gemini returned no script text: {resp.text[:300]}") from exc

    def write(self, topic: str) -> Script:
        log.info("writing script for topic %r with %s", topic, self._model)
        prompt = f"Topic: {topic}"
        for attempt in (1, 2):
            raw = self._ask(prompt)
            try:
                return Script.from_dict(json.loads(raw))
            except (ValueError, json.JSONDecodeError) as exc:
                if attempt == 2:
                    raise RuntimeError(f"Gemini script invalid twice: {exc}") from exc
                log.warning("script rejected (%s); retrying once", exc)
                prompt = f"Topic: {topic}\n\nYour previous attempt was rejected: {exc}. Fix that and try again."
        raise AssertionError("unreachable")


class FileScriptWriter:
    """Loads a hand-written or previously generated script.json. Useful for re-renders."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, topic: str) -> Script:
        return Script.from_dict(json.loads(self._path.read_text(encoding="utf-8")))
