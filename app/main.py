from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
import re
import subprocess

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app.codex_worker import check_codex_harness, run_mock_codex, run_real_codex
from app.events import event
from app.realtime import RealtimeCallRequest, check_openai_connection, create_realtime_call
from app.schemas import EventType, SessionEvent, UserTranscriptMessage
from app.sessions import SessionState, store
from app.voice_pm import decide_next_step

load_dotenv()

app = FastAPI(title="Mums Can Build", version="0.1.0")
app.mount("/static", StaticFiles(directory="web"), name="static")
DEFAULT_WORKSPACE_ROOT = Path("workspace")
RUNTIME_PID_FILE = Path("/tmp/mcb-runtime-9000.pid")


def _start_workspace_app(workspace: Path, port: int = 9000) -> dict[str, object]:
    _stop_port_process(port)
    process = subprocess.Popen(
        ["npm", "start"],
        cwd=workspace,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**dict(**__import__("os").environ), "PORT": str(port)},
        start_new_session=True,
    )
    RUNTIME_PID_FILE.write_text(str(process.pid), encoding="utf-8")
    return {"started": True, "pid": process.pid, "url": f"http://127.0.0.1:{port}"}


def _stop_port_process(port: int = 9000) -> None:
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return
    pids = [item.strip() for item in result.stdout.splitlines() if item.strip()]
    for pid in pids:
        subprocess.run(["kill", "-9", pid], check=False)


@app.post("/runtime/start-latest")
async def runtime_start_latest() -> dict[str, object]:
    candidates = sorted(DEFAULT_WORKSPACE_ROOT.glob("e2e-*/*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise HTTPException(status_code=404, detail="No generated workspace found.")
    latest = candidates[0]
    if not (latest / "package.json").exists():
        raise HTTPException(status_code=400, detail="Latest workspace does not contain package.json.")
    return {"workspace": str(latest), **_start_workspace_app(latest, 9000)}


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    with open("web/index.html", encoding="utf-8") as file:
        return file.read()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/connections")
async def connection_health() -> dict[str, object]:
    openai = await check_openai_connection()
    codex = await check_codex_harness()
    return {
        "frontend": {"status": "ok", "reason": "Page assets loaded."},
        "backend": {"status": "ok", "reason": "FastAPI is reachable."},
        "openai": openai,
        "codex": codex,
    }


@app.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, object]:
    return store.snapshot(session_id)


@app.post("/realtime/call", response_class=PlainTextResponse)
async def realtime_call(request: RealtimeCallRequest) -> str:
    try:
        return await create_realtime_call(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.websocket("/ws/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    session = store.get(session_id)
    await _send(
        websocket,
        session,
        event(
            EventType.SESSION_STARTED,
            session_id,
            {"message": "Session started."},
            spoken="I am ready.",
        ),
    )

    try:
        while True:
            data = await websocket.receive_json()
            try:
                message = UserTranscriptMessage.model_validate(data)
            except ValidationError as exc:
                await _send(
                    websocket,
                    session,
                    event(
                        EventType.SESSION_ERROR,
                        session_id,
                        {"error": "Invalid message.", "details": exc.errors()},
                    ),
                )
                continue

            await _handle_transcript(websocket, session, message)
    except WebSocketDisconnect:
        return


async def _handle_transcript(
    websocket: WebSocket,
    session: SessionState,
    message: UserTranscriptMessage,
) -> None:
    session.add_transcript(message.text)
    await _send(
        websocket,
        session,
        event(EventType.USER_TRANSCRIPT, session.session_id, {"text": message.text}),
    )
    await _send(
        websocket,
        session,
        event(
            EventType.PM_THINKING,
            session.session_id,
            {"message": "Voice PM is checking the request."},
        ),
    )

    # Gate delegation behind explicit user confirmation so voice turns can
    # first refine requirements before Codex starts running.
    if message.auto_start and session.current_task and _is_confirmation_turn(message.text):
        if session.codex_running:
            await _send(
                websocket,
                session,
                event(
                    EventType.SESSION_ERROR,
                    session.session_id,
                    {"error": "Codex is already running for this session."},
                ),
            )
            return

        await _send(
            websocket,
            session,
            event(
                EventType.PM_TASK_READY,
                session.session_id,
                {"task": session.current_task.model_dump()},
                spoken="Confirmed. I am starting the build now.",
            ),
        )
        await _run_worker(websocket, session, message, session.current_task)
        return

    decision = decide_next_step(session.transcript_text)
    if decision.kind == "question":
        await _send(
            websocket,
            session,
            event(
                EventType.PM_QUESTION,
                session.session_id,
                {"question": decision.question},
                spoken=decision.question,
            ),
        )
        return

    if decision.task is None:
        await _send(
            websocket,
            session,
            event(EventType.SESSION_ERROR, session.session_id, {"error": "No task was created."}),
        )
        return

    session.current_task = decision.task
    await _send(
        websocket,
        session,
        event(
            EventType.PM_TASK_READY,
            session.session_id,
            {"task": decision.task.model_dump()},
            spoken="I have enough. I am preparing the build task.",
        ),
    )

    if not message.auto_start:
        return
    await _run_worker(websocket, session, message, decision.task)


async def _run_worker(
    websocket: WebSocket,
    session: SessionState,
    message: UserTranscriptMessage,
    task,
) -> None:
    if session.codex_running:
        await _send(
            websocket,
            session,
            event(
                EventType.SESSION_ERROR,
                session.session_id,
                {"error": "Codex is already running for this session."},
            ),
        )
        return

    session.codex_running = True
    try:
        worker = _select_worker(
            message.worker,
            session.session_id,
            task,
            message.workspace,
            session,
        )
        async for worker_event in worker:
            await _send(websocket, session, worker_event)
    finally:
        session.codex_running = False


def _is_confirmation_turn(text: str) -> bool:
    normalized = text.lower().strip()
    if not normalized:
        return False
    confirmations = ("confirm", "go ahead", "proceed", "start build", "ship it", "do it now", "delegate now")
    return any(phrase in normalized for phrase in confirmations)


def _select_worker(
    worker: str,
    session_id: str,
    task,
    workspace: str | None,
    session: SessionState,
) -> AsyncIterator[SessionEvent]:
    if worker == "real":
        run_workspace = _resolve_run_workspace(task.title, session_id, workspace)
        return run_real_codex(
            session_id,
            task,
            str(run_workspace),
            on_raw_log=lambda stream, line: session.add_raw_codex_log(stream, line),
        )
    return run_mock_codex(session_id, task)


def _resolve_run_workspace(task_title: str, session_id: str, requested_workspace: str | None) -> Path:
    base = Path(requested_workspace).expanduser() if requested_workspace else DEFAULT_WORKSPACE_ROOT
    base.mkdir(parents=True, exist_ok=True)

    session_slug = _slugify(session_id) or "session"
    session_root = base / session_slug
    session_root.mkdir(parents=True, exist_ok=True)

    task_slug = _slugify(task_title) or "project"
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    run_dir = session_root / f"{task_slug}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:48]


async def _send(websocket: WebSocket, session: SessionState, session_event: SessionEvent) -> None:
    if session_event.type == EventType.CODEX_LOG and not session_event.spoken:
        session_event.spoken = _spoken_update_for_codex_log(session_event.payload)
    if session_event.type == EventType.SESSION_ERROR and not session_event.spoken:
        error_text = str(session_event.payload.get("error", "")).strip()
        if error_text:
            session_event.spoken = f"I hit an issue: {error_text}"

    session.add_event(session_event)
    await websocket.send_json(session_event.model_dump(mode="json"))


def _spoken_update_for_codex_log(payload: dict[str, object]) -> str | None:
    message = str(payload.get("message", "")).strip()
    if not message:
        return None

    lowered = message.lower()
    if "running validation command:" in lowered:
        return "Running checks now."
    if "command finished with exit code 0" in lowered:
        return "Checks passed."
    if "command finished with exit code" in lowered and "exit code 0" not in lowered:
        return "A check failed. I will report details."
    if lowered.startswith("edited ") or lowered.startswith("editing "):
        return message
    if "codex is inspecting the task" in lowered:
        return "I am reviewing the codebase now."
    return None
