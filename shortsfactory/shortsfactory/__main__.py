from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .config import Settings
from .footage import PexelsFootage, PixabayFootage, PlaceholderFootage
from .pipeline import make_short
from .script import ClaudeScriptWriter, FileScriptWriter, GeminiScriptWriter
from .tts import EdgeTTS


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(asctime)s %(name)s %(message)s")
    # httpx logs full request URLs, and Pixabay takes its API key as a URL parameter. Never let that reach a log.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="shortsfactory", description="Make one vertical Short from a topic.")
    p.add_argument("--topic", default="", help="what the Short is about (needs ANTHROPIC_API_KEY)")
    p.add_argument("--script-file", type=Path, help="use this script.json instead of calling Claude")
    p.add_argument("--placeholder-footage", action="store_true", help="DRY RUN: solid colours instead of Pexels")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    configure_logging(args.verbose)
    cfg = Settings.from_env()

    if args.script_file:
        writer = FileScriptWriter(args.script_file)
    elif args.topic and cfg.gemini_api_key:  # free tier first; Anthropic if you have API credit
        writer = GeminiScriptWriter(cfg.gemini_api_key, cfg.gemini_model)
    elif args.topic and cfg.anthropic_api_key:
        writer = ClaudeScriptWriter(cfg.anthropic_api_key, cfg.script_model)
    else:
        print("error: give --script-file, or --topic with GEMINI_API_KEY or ANTHROPIC_API_KEY set", file=sys.stderr)
        return 2

    if args.placeholder_footage:
        footage = PlaceholderFootage()
    elif cfg.pexels_api_key:  # portrait-native, so looks best when available
        footage = PexelsFootage(cfg.pexels_api_key)
    elif cfg.pixabay_api_key:
        footage = PixabayFootage(cfg.pixabay_api_key)
    else:
        print("error: set PEXELS_API_KEY or PIXABAY_API_KEY, or pass --placeholder-footage for a dry run", file=sys.stderr)
        return 2

    try:
        res = asyncio.run(make_short(args.topic, writer, EdgeTTS(cfg.voice, cfg.voice_rate), footage, cfg))
    except Exception as exc:  # surfaced, never swallowed: print and exit non-zero
        logging.getLogger("sf").error("failed: %s", exc)
        return 1
    print(f"OK {res.video} ({res.duration:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
