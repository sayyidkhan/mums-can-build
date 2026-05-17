import pytest

from app.realtime import RealtimeCallRequest, check_openai_connection, realtime_session_update


def test_realtime_call_request_allows_server_defaults() -> None:
    request = RealtimeCallRequest(sdp="fake offer sdp long enough")

    assert request.model is None
    assert request.voice is None


def test_realtime_session_update_contains_transcription_and_audio() -> None:
    update = realtime_session_update("marin")

    assert update["type"] == "session.update"
    session = update["session"]
    assert session["output_modalities"] == ["audio"]
    assert session["audio"]["input"]["transcription"]["model"] == "gpt-4o-mini-transcribe"
    assert session["audio"]["output"]["voice"] == "marin"


@pytest.mark.anyio
async def test_check_openai_connection_reports_missing_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    health = await check_openai_connection()

    assert health["status"] == "down"
    assert "OPENAI_API_KEY" in health["reason"]
