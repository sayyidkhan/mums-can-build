from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(StrEnum):
    SESSION_STARTED = "session.started"
    USER_TRANSCRIPT = "user.transcript"
    PM_THINKING = "pm.thinking"
    PM_QUESTION = "pm.question"
    PM_TASK_READY = "pm.task_ready"
    CODEX_STARTED = "codex.started"
    CODEX_LOG = "codex.log"
    CODEX_DONE = "codex.done"
    SESSION_ERROR = "session.error"


class CodexTask(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    user_goal: str = Field(min_length=3)
    requirements: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class SessionEvent(BaseModel):
    type: EventType
    session_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    spoken: str | None = None
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserTranscriptMessage(BaseModel):
    type: EventType = EventType.USER_TRANSCRIPT
    text: str = Field(min_length=1)
    worker: str = Field(default="mock", pattern="^(mock|real)$")
    workspace: str | None = None
    auto_start: bool = True
