from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import websockets


REPO_ROOT = Path(__file__).resolve().parent.parent
START_SCRIPT = REPO_ROOT / "scripts" / "start-on-9000.sh"
PROMPT = (
    "Build a simple todo list web app for a mum as the primary user. "
    "Include create, update, and delete todo features. "
    "Success means she can use it locally today from a browser on localhost:9000. "
    "Use plain Node.js with package.json and a start script so `npm start` runs it on port 9000. "
    "Keep it MVP and start the build now."
)


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)


async def _run_harness_flow(session_id: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    events: list[dict[str, object]] = []
    async with websockets.connect(f"ws://127.0.0.1:8000/ws/{session_id}") as websocket:
        started = json.loads(await websocket.recv())
        events.append(started)

        await websocket.send(
            json.dumps(
                {
                    "type": "user.transcript",
                    "text": PROMPT,
                    "worker": "real",
                    "workspace": None,
                    "auto_start": True,
                }
            )
        )

        while True:
            message = json.loads(await websocket.recv())
            events.append(message)
            if message["type"] in {"codex.done", "pm.question", "session.error"}:
                return message, events


def _start_backend() -> subprocess.Popen[str]:
    log_path = Path("/tmp/mcb-e2e-backend.log")
    log_file = log_path.open("w", encoding="utf-8")
    return subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=REPO_ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> int:
    print("Starting backend...")
    backend = _start_backend()
    time.sleep(2)

    session_id = f"e2e-{uuid4().hex[:8]}"
    print(f"Running real-worker flow for session: {session_id}")

    try:
        final_event, events = asyncio.run(_run_harness_flow(session_id))
    finally:
        _stop_process(backend)

    if final_event["type"] != "codex.done":
        print(f"FAIL: flow ended with {final_event['type']}")
        return 1

    payload = final_event.get("payload", {})
    if payload.get("status") != "completed":
        print(f"FAIL: codex status={payload.get('status')}")
        return 1

    started = next((e for e in events if e.get("type") == "codex.started"), None)
    if not started:
        print("FAIL: missing codex.started event")
        return 1
    workspace = started.get("payload", {}).get("workspace")
    if not workspace:
        print("FAIL: missing workspace path in codex.started")
        return 1

    workspace_path = Path(str(workspace))
    if not workspace_path.exists():
        print(f"FAIL: workspace path does not exist: {workspace_path}")
        return 1
    if session_id not in str(workspace_path):
        print(f"FAIL: workspace is not scoped to session id: {workspace_path}")
        return 1

    package_json = workspace_path / "package.json"
    server_js = workspace_path / "server.js"
    if not package_json.exists() or not server_js.exists():
        print(f"FAIL: expected app files missing in {workspace_path}")
        return 1

    print(f"Workspace created: {workspace_path}")
    print("Starting app on port 9000 (with auto pre-kill)...")
    app_dir = workspace_path
    # Restart with app-specific env so it starts the generated app.
    env = os.environ.copy()
    env["APP_DIR"] = str(app_dir)
    env["START_CMD"] = "npm start"
    restart = subprocess.run(
        ["bash", str(START_SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if restart.returncode != 0:
        print("FAIL: failed to start generated app on 9000")
        print(restart.stdout)
        print(restart.stderr)
        return 1

    time.sleep(2)
    curl = _run(["curl", "-sS", "http://127.0.0.1:9000"], cwd=REPO_ROOT, timeout=10)
    page = curl.stdout
    looks_like_todo = (
        "todo" in page.lower()
        or "add" in page.lower()
        or "delete" in page.lower()
        or "save" in page.lower()
    )
    if curl.returncode != 0 or not looks_like_todo:
        print("FAIL: localhost:9000 check failed")
        print(curl.stdout)
        print(curl.stderr)
        return 1

    print("PASS")
    print(f"- session: {session_id}")
    print(f"- workspace: {workspace_path}")
    print(f"- response: {curl.stdout.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
