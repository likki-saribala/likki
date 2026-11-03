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
export PIXABAY_API_KEY=...          # free at pixabay.com/api/docs (Pexels also works, but it paused new keys)
python -m shortsfactory --topic "how GPS actually knows where you are"
```

Hand-written script instead of Claude: `--script-file examples/gps.json`.
Dry run with no Pexels key: add `--placeholder-footage` (solid colours, clearly logged, never automatic).

Settings are environment variables only (see `shortsfactory/config.py`): `SF_VOICE`, `SF_VOICE_RATE`, `SF_SCRIPT_MODEL`,
`SF_GEMINI_MODEL`, `SF_FONT`, `SF_MUSIC_DIR`, `SF_MUSIC_VOLUME`.

## Background music

Put 5-10 mp3 files in `shortsfactory/music/` (the folder is git-ignored). One is picked at random per video, looped to
fit, faded in and out, and ducked under the voice. Use only music you are licensed to use: the YouTube Audio Library
(YouTube Studio, Audio Library) is the safest source for a YouTube channel. We never download music automatically,
because copyright claims on Shorts are real. With no files in the folder, the video is made without music and the log says so.

## Voice

The whole script is voiced in ONE continuous take, so intonation flows across sentences; scene cuts are placed on the
words afterwards. Pick a voice with `SF_VOICE` and audition candidates without running the pipeline:

```bash
python -m edge_tts --list-voices                      # all voices; names like en-US-AvaMultilingualNeural
python -m edge_tts --voice en-US-AvaMultilingualNeural --text "Your phone finds you, without ever sending a signal." --write-media test.mp3
```

`edge-tts` is limited: no emotion or style controls, only `SF_VOICE_RATE`. Some voices may not report word timings
(captions need them); the run then fails with a clear message and you pick another voice.

## Style

Scripts are serious, informational explainers (science, technology, history, economics, health, space, psychology),
not cute trivia. The prompt lives in `shortsfactory/script.py` (`SYSTEM`).

## Tests

```bash
python -m pytest -q
```

Real ffmpeg, fake network. Not covered by automated tests: live Claude, Pexels and edge-tts calls.

## Known limits

- `edge-tts` is an unofficial Microsoft endpoint and can break without notice. TTS sits behind an interface for swapping.
- Facts come from the model. The per-scene `claim` field is saved so Phase 2 can check them; until then, read the JSON before posting.
