from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.schemas import CodexTask, SessionEvent


@dataclass
class SessionState:
    session_id: str
    transcripts: list[str] = field(default_factory=list)
    events: list[SessionEvent] = field(default_factory=list)
    current_task: CodexTask | None = None
    codex_running: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_event(self, event: SessionEvent) -> None:
        self.events.append(event)

    def add_transcript(self, text: str) -> None:
        self.transcripts.append(text.strip())

    def add_raw_codex_log(self, stream: str, line: str) -> None:
        logs = self.metadata.setdefault("raw_codex_logs", [])
        logs.append(
            {
                "stream": stream,
                "line": line,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

    @property
    def transcript_text(self) -> str:
        return "\n".join(item for item in self.transcripts if item)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._runtime_memory: dict[str, Any] = {}

    def get(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def snapshot(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        return {
            "session_id": session.session_id,
            "transcripts": session.transcripts,
            "current_task": session.current_task.model_dump() if session.current_task else None,
            "codex_running": session.codex_running,
            "event_count": len(session.events),
            "raw_codex_log_count": len(session.metadata.get("raw_codex_logs", [])),
            "active_workspace": session.metadata.get("active_workspace"),
            "codex_session_id": session.metadata.get("codex_session_id"),
            "runtime_memory": self._runtime_memory,
            "created_at": session.created_at.isoformat(),
        }

    def set_runtime_memory(self, key: str, value: Any) -> None:
        self._runtime_memory[key] = value

    def get_runtime_memory(self, key: str) -> Any:
        return self._runtime_memory.get(key)


store = SessionStore()
