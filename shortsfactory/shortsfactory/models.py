from __future__ import annotations

from dataclasses import asdict, dataclass, field

MIN_SCENES = 4
MAX_SCENES = 10
MAX_WORDS = 140  # ~50s at a brisk pace; Shorts must stay well under 3 min


@dataclass
class Scene:
    text: str  # narration, spoken aloud and captioned
    query: str  # stock-footage search phrase (concrete, visual, 1-3 words)
    claim: str  # the single checkable factual claim in this scene (for QA in Phase 2)


@dataclass
class Script:
    title: str
    scenes: list[Scene]
    hashtags: list[str] = field(default_factory=list)

    def word_count(self) -> int:
        return sum(len(s.text.split()) for s in self.scenes)

    def validate(self) -> None:
        if not self.title.strip():
            raise ValueError("script has no title")
        if not MIN_SCENES <= len(self.scenes) <= MAX_SCENES:
            raise ValueError(f"script needs {MIN_SCENES}-{MAX_SCENES} scenes, got {len(self.scenes)}")
        for i, s in enumerate(self.scenes):
            if not s.text.strip() or not s.query.strip():
                raise ValueError(f"scene {i} has empty text or query")
        if self.word_count() > MAX_WORDS:
            raise ValueError(f"script is {self.word_count()} words, max {MAX_WORDS}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Script":
        try:
            script = cls(
                title=str(d["title"]),
                scenes=[Scene(str(s["text"]), str(s["query"]), str(s.get("claim", ""))) for s in d["scenes"]],
                hashtags=[str(h) for h in d.get("hashtags", [])],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"malformed script: {exc!r}") from exc
        script.validate()
        return script
