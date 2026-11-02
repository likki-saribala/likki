# shortsfactory

Topic in, vertical YouTube Short (1080x1920 MP4) out. Faceless: AI voice, stock footage, burned-in word captions.
Lives in its own folder; the rest of this repo (the website) is untouched.

**Status: Phase 1 of 4.** Renders a Short locally. It does NOT upload yet (Phase 0 gate / Phase 3), has no QA gate (Phase 2)
and no scheduler.

## Pipeline

```
topic -> Claude script (JSON: scenes, footage query, checkable claim)
      -> edge-tts voice per scene (+ word timings)
      -> Pexels portrait clip per scene
      -> ffmpeg: segment per scene -> concat -> burn ASS captions
      -> out/<slug>.mp4 + out/<slug>.json (title, hashtags, claims for Phase 2 QA)
```

## Setup

```bash
cd shortsfactory
pip install -r requirements.txt     # needs ffmpeg with libass on PATH
export GEMINI_API_KEY=...           # script writing, free key: aistudio.google.com/apikey
# or: export ANTHROPIC_API_KEY=...  # needs paid API credit; a Claude Pro chat plan does not include it
# Gemini wins if both are set. Override the model with SF_GEMINI_MODEL if the default is retired.
export PEXELS_API_KEY=...           # free at pexels.com/api
python -m shortsfactory --topic "why honey never spoils"
```

Hand-written script instead of Claude: `--script-file examples/honey.json`.
Dry run with no Pexels key: add `--placeholder-footage` (solid colours, clearly logged, never automatic).

Settings are environment variables only (see `shortsfactory/config.py`): `SF_VOICE`, `SF_VOICE_RATE`, `SF_SCRIPT_MODEL`, `SF_FONT`.

## Tests

```bash
python -m pytest -q
```

Real ffmpeg, fake network. Not covered by automated tests: live Claude, Pexels and edge-tts calls.

## Known limits

- `edge-tts` is an unofficial Microsoft endpoint and can break without notice. TTS sits behind an interface for swapping.
- Facts come from the model. The per-scene `claim` field is saved so Phase 2 can check them; until then, read the JSON before posting.
