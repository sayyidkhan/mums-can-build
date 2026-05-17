from app.realtime import RealtimeCallRequest, realtime_session_update


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
