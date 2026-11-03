"""Word-by-word style captions as an ASS subtitle file (burned in by ffmpeg/libass)."""
from __future__ import annotations

from .tts import WordTiming

MAX_WORDS_PER_CHUNK = 3
# Width budget: 1080px - 2*70px margins = 940px. Bold caps at 76px are ~0.75em wide (~57px),
# so 16 characters is ~910px. Longer chunks ran off the screen edge.
MAX_CHARS_PER_CHUNK = 16
_ENDERS = (".", "!", "?", ",", ";", ":")


def chunk_words(words: list[WordTiming]) -> list[list[WordTiming]]:
    chunks: list[list[WordTiming]] = []
    cur: list[WordTiming] = []
    for w in words:
        if cur and (
            len(cur) >= MAX_WORDS_PER_CHUNK or len(" ".join(x.text for x in cur)) + 1 + len(w.text) > MAX_CHARS_PER_CHUNK
        ):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if w.text.endswith(_ENDERS):
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
        f"PlayResX: {width}\nPlayResY: {height}\nWrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Default,{font},76,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
        "-1,0,0,0,100,100,0,0,1,7,2,2,70,70,520,1\n\n"
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
