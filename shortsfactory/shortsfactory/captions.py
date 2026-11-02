"""Word-by-word style captions as an ASS subtitle file (burned in by ffmpeg/libass)."""
from __future__ import annotations

from .tts import WordTiming

MAX_WORDS_PER_CHUNK = 3
_ENDERS = (".", "!", "?", ",", ";", ":")


def chunk_words(words: list[WordTiming]) -> list[list[WordTiming]]:
    chunks: list[list[WordTiming]] = []
    cur: list[WordTiming] = []
    for w in words:
        cur.append(w)
        if len(cur) >= MAX_WORDS_PER_CHUNK or w.text.endswith(_ENDERS):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def _ts(sec: float) -> str:
    cs = int(round(sec * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _clean(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\\", "").upper()


def build_ass(words: list[WordTiming], width: int, height: int, font: str) -> str:
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\nWrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Default,{font},96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
        "-1,0,0,0,100,100,0,0,1,7,2,2,60,60,520,1\n\n"
        "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )
    chunks = chunk_words(words)
    lines = []
    for i, chunk in enumerate(chunks):
        start, end = chunk[0].start, chunk[-1].end
        if i + 1 < len(chunks):
            nxt = chunks[i + 1][0].start
            if 0 <= nxt - end < 0.25:  # close the gap so captions don't flicker
                end = nxt
        text = " ".join(_clean(w.text) for w in chunk)
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{text}")
    return header + "\n".join(lines) + "\n"
