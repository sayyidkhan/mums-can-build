import re
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.main import app


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_connection_health_reports_core_services(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.get("/health/connections")

    assert response.status_code == 200
    payload = response.json()
    assert payload["frontend"]["status"] == "ok"
    assert payload["backend"]["status"] == "ok"
    assert payload["openai"]["status"] == "down"
    assert "codex" in payload


def test_index_serves_voice_ui() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Mums Can Build" in response.text
    assert "Start call" in response.text


def test_realtime_call_requires_api_key(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.post("/realtime/call", json={"sdp": "not a real offer but long enough"})

    assert response.status_code == 400
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_websocket_mock_flow() -> None:
    client = TestClient(app)

    with client.websocket_connect("/ws/test-session") as websocket:
        started = websocket.receive_json()
        assert started["type"] == "session.started"

        websocket.send_json(
            {
                "type": "user.transcript",
                "text": "Build a simple booking app with a form and confirmation page",
                "worker": "mock",
            }
        )

        seen = []
        while True:
            event = websocket.receive_json()
            seen.append(event["type"])
            if event["type"] == "codex.done":
                assert event["payload"]["status"] == "completed"
                break

        assert "pm.task_ready" in seen
        assert "codex.started" in seen


def test_session_snapshot_includes_raw_log_count() -> None:
    client = TestClient(app)

    response = client.get("/sessions/test-session")

    assert response.status_code == 200
    assert "raw_codex_log_count" in response.json()


def test_resolve_run_workspace_creates_timestamped_project_folder(tmp_path) -> None:
    workspace = main._resolve_run_workspace("Build todo app for me", str(tmp_path))

    assert workspace.exists()
    assert workspace.is_dir()
    assert workspace.parent == tmp_path
    assert re.fullmatch(r"build-todo-app-for-me-\d{8}-\d{6}", workspace.name)


def test_resolve_run_workspace_uses_default_workspace_root(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main, "DEFAULT_WORKSPACE_ROOT", Path(tmp_path / "workspace-root"))

    workspace = main._resolve_run_workspace("Prototype v1", None)

    assert workspace.exists()
    assert workspace.parent == tmp_path / "workspace-root"
    assert workspace.name.startswith("prototype-v1-")
