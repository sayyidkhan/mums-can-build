from __future__ import annotations

from typing import Any

from app.schemas import EventType, SessionEvent


def event(
    event_type: EventType,
    session_id: str,
    payload: dict[str, Any] | None = None,
    spoken: str | None = None,
) -> SessionEvent:
    return SessionEvent(
        type=event_type,
        session_id=session_id,
        payload=payload or {},
        spoken=spoken,
    )
