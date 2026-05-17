from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas import CodexTask


DEFAULT_CONSTRAINTS = [
    "Inspect the existing repo before editing.",
    "Make the smallest useful change for a demo.",
    "Do not change unrelated files.",
    "Run relevant validation commands and report the result.",
]


@dataclass(frozen=True)
class PMDecision:
    kind: str
    question: str | None = None
    task: CodexTask | None = None


def decide_next_step(transcript: str) -> PMDecision:
    cleaned = _normalize(transcript)
    words = cleaned.split()

    if len(words) < 8:
        return PMDecision(
            kind="question",
            question="What do you want the first version to do?",
        )

    if not _has_build_intent(cleaned):
        return PMDecision(
            kind="question",
            question="Should I build a new app, change an existing app, or investigate the repo?",
        )

    task = CodexTask(
        title=_make_title(cleaned),
        user_goal=cleaned,
        requirements=_extract_requirements(cleaned),
        acceptance_criteria=[
            "The requested workflow can be exercised locally.",
            "The implementation is small enough to inspect during the POC.",
            "Progress and completion are reported back through session events.",
        ],
        constraints=DEFAULT_CONSTRAINTS,
    )
    return PMDecision(kind="task_ready", task=task)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _has_build_intent(text: str) -> bool:
    intent_words = {
        "build",
        "create",
        "make",
        "add",
        "implement",
        "change",
        "fix",
        "update",
        "generate",
        "scaffold",
        "prototype",
    }
    return any(word in text.lower().split() for word in intent_words)


def _make_title(text: str) -> str:
    title = re.sub(r"^(please|can you|could you|help me to|help me)\s+", "", text, flags=re.I)
    title = title[:80].strip(" .,")
    if not title:
        return "Build requested software change"
    return title[0].upper() + title[1:]


def _extract_requirements(text: str) -> list[str]:
    clauses = re.split(r"\s+(?:and|then|also|with)\s+", text)
    requirements = []
    for clause in clauses:
        clause = clause.strip(" .,")
        if len(clause.split()) >= 3:
            requirements.append(clause[0].upper() + clause[1:])
    return requirements[:6] or [text]
