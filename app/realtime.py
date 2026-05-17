from __future__ import annotations

import os

import httpx
from pydantic import BaseModel, Field


REALTIME_INSTRUCTIONS = """You are the voice interface for Mums Can Build.
Keep speech very short and conversational.
Do not explain implementation details, logs, stack traces, or diffs.
When the user gives a software request, acknowledge briefly and wait while the backend harness scopes and builds it.
When the app sends you a message beginning with "SAY:", say exactly the text after "SAY:" and nothing else.
"""


class RealtimeCallRequest(BaseModel):
    sdp: str = Field(min_length=10)
    model: str | None = None
    voice: str | None = None


async def check_openai_connection() -> dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"status": "down", "reason": "OPENAI_API_KEY is not set."}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        except httpx.HTTPError as exc:
            return {"status": "down", "reason": f"OpenAI request failed: {exc.__class__.__name__}"}

    if response.status_code == 200:
        return {"status": "ok", "reason": "OpenAI API reachable."}
    if response.status_code in {401, 403}:
        return {"status": "down", "reason": "OpenAI API key was rejected."}
    return {"status": "degraded", "reason": f"OpenAI returned HTTP {response.status_code}."}


async def create_realtime_call(request: RealtimeCallRequest) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    model = request.model or os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/realtime/calls",
            params={"model": model},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/sdp",
                "Accept": "application/sdp",
            },
            content=request.sdp,
        )

    if response.status_code >= 400:
        raise RuntimeError(f"OpenAI Realtime call failed: {response.status_code} {response.text}")
    return response.text


def realtime_session_update(voice: str | None = None) -> dict[str, object]:
    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "instructions": REALTIME_INSTRUCTIONS,
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "transcription": {
                        "model": "gpt-4o-mini-transcribe",
                        "language": "en",
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "silence_duration_ms": 320,
                    },
                },
                "output": {
                    "voice": voice or os.getenv("OPENAI_REALTIME_VOICE", "marin"),
                },
            },
        },
    }
