"""Script writing. ScriptWriter is the injection seam; ClaudeScriptWriter is the real one."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol

import httpx

from .models import MAX_SCENES, MAX_WORDS, MIN_SCENES, Script

log = logging.getLogger("sf.script")


class ScriptWriter(Protocol):
    def write(self, topic: str) -> Script: ...


SYSTEM = f"""You write scripts for faceless YouTube Shorts. Each Short is a serious, informational explainer that
teaches ONE useful idea in under a minute: how something actually works, why something happens, or what most
people get wrong about it. Subject areas: science, technology, engineering, history, economics and money, health,
space, psychology, geography.

Tone: calm, confident and concrete, like a good documentary narrator. NOT cute, NOT quirky trivia, NOT hype.
Avoid animals, food and "fun fact" fluff unless the requested topic is itself about that.

Rules:
- {MIN_SCENES}-{MAX_SCENES} scenes (aim for 6-8), 90-125 words of narration in total, never more than {MAX_WORDS}.
- Structure: hook -> the surprising or important claim -> the mechanism (WHY or HOW it works) -> one concrete
  example or consequence -> a closing takeaway that changes how the viewer sees it.
- Scene 1 is the hook: a specific, concrete line with real stakes that makes a stranger stop scrolling.
  No "Did you know", no "Here's a fun fact".
- Every scene is short, plain spoken English with one idea. No emojis, no hashtags, no on-screen-text cues.
- Write for the EAR, not the page: it will be read aloud by a text-to-speech voice, in one continuous take.
  Use contractions ("it's", "doesn't"), talk to the viewer as "you", and vary sentence length: mix short punchy
  sentences with longer ones. Add an occasional rhetorical question. Use commas and dashes where a speaker would
  pause or shift tone, and a question mark where the voice should lift. At most one exclamation mark in the whole
  script. Scenes must flow into each other as one story, not read as separate captions.
- Only well-established facts you are highly confident are correct. If unsure of a number, leave the number out.
  Never invent statistics, quotes, dates, studies or names. Accuracy matters more than shock value.
- For each scene give `claim`: the single checkable factual claim it makes, stated plainly.
- For each scene give `query`: 2-3 words describing what a camera could literally film that fits the narration
  (e.g. "server room", "stock exchange floor", "satellite orbit", "brain scan", "oil refinery"). Never a single
  abstract word like "economy" or "progress".
- The last scene ends on a line that loops back to the hook or sets up a rewatch. No "like and subscribe".
- title: under 60 characters, clear and honest, no clickbait lies. hashtags: 3-5, lowercase, no '#' symbol."""

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
        self._client = client or httpx.Client(timeout=httpx.Timeout(240, connect=20))  # thinking models can be slow
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
        if resp.status_code >= 400:  # show Google's own explanation instead of a bare status code
            raise RuntimeError(f"Gemini API error {resp.status_code} for model {self._model!r}: {resp.text[:500]}")
        try:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Gemini returned no script text: {resp.text[:300]}") from exc

    def write(self, topic: str) -> Script:
        log.info("writing script for topic %r with %s", topic, self._model)
        prompt = f"Topic: {topic}"
        for attempt in (1, 2):
            try:
                raw = self._ask(prompt)
            except httpx.TimeoutException as exc:
                if attempt == 2:
                    raise RuntimeError(f"Gemini timed out twice on model {self._model!r}; try SF_GEMINI_MODEL=<a -lite model>") from exc
                log.warning("Gemini timed out; retrying once")
                continue
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
