from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Callable

from app.events import event
from app.schemas import CodexTask, EventType, SessionEvent


async def check_codex_harness() -> dict[str, str]:
    codex_path = shutil.which("codex")
    if not codex_path:
        return {"status": "down", "reason": "Codex CLI was not found on PATH."}

    try:
        process = await asyncio.create_subprocess_exec(
            codex_path,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
    except TimeoutError:
        return {"status": "degraded", "reason": "Codex CLI version check timed out."}
    except OSError as exc:
        return {"status": "down", "reason": f"Codex CLI failed to start: {exc.__class__.__name__}."}

    output = (stdout or stderr).decode(errors="replace").strip()
    if process.returncode == 0:
        return {"status": "ok", "reason": output or "Codex CLI reachable."}
    return {"status": "down", "reason": output or f"Codex CLI exited with {process.returncode}."}


async def run_mock_codex(session_id: str, task: CodexTask) -> AsyncIterator[SessionEvent]:
    yield event(
        EventType.CODEX_STARTED,
        session_id,
        {"worker": "mock", "task": task.model_dump()},
        spoken="The builder is editing files.",
    )

    for message in [
        "Reading the scoped task.",
        "Inspecting the workspace.",
        "Applying the smallest useful change.",
        "Running validation checks.",
    ]:
        await asyncio.sleep(0.25)
        yield event(EventType.CODEX_LOG, session_id, {"stream": "mock", "message": message})

    yield event(
        EventType.CODEX_DONE,
        session_id,
        {
            "worker": "mock",
            "status": "completed",
            "changed_files": [],
            "summary": "Mock run completed. No files were changed.",
        },
        spoken="The first version is ready.",
    )


async def run_real_codex(
    session_id: str,
    task: CodexTask,
    workspace: str | None = None,
    on_raw_log: Callable[[str, str], None] | None = None,
) -> AsyncIterator[SessionEvent]:
    workspace_path = Path(workspace or os.getcwd()).expanduser().resolve()
    prompt = render_codex_prompt(task)
    command = [
        "codex",
        "exec",
        "--json",
        "--sandbox",
        "workspace-write",
        "--cd",
        str(workspace_path),
        "-",
    ]

    if os.getenv("CODEX_BYPASS_APPROVALS") == "1":
        command.insert(2, "--dangerously-bypass-approvals-and-sandbox")

    yield event(
        EventType.CODEX_STARTED,
        session_id,
        {"worker": "real", "workspace": str(workspace_path), "task": task.model_dump()},
        spoken="I am starting the builder now.",
    )

    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert process.stdin is not None
    process.stdin.write(prompt.encode())
    await process.stdin.drain()
    process.stdin.close()

    async for stream, line in _stream_process(process):
        if on_raw_log:
            on_raw_log(stream, line)
        clean_log = normalize_codex_log(stream, line)
        if clean_log:
            yield event(EventType.CODEX_LOG, session_id, clean_log)

    return_code = await process.wait()
    diff_summary = await _git_changed_files(workspace_path)
    status = "completed" if return_code == 0 else "failed"
    spoken = "The first version is ready." if return_code == 0 else "The builder hit an error."
    yield event(
        EventType.CODEX_DONE,
        session_id,
        {
            "worker": "real",
            "status": status,
            "return_code": return_code,
            "changed_files": diff_summary,
        },
        spoken=spoken,
    )


def render_codex_prompt(task: CodexTask) -> str:
    return f"""You are Codex working inside the selected repository.

Build task:
{task.model_dump_json(indent=2)}

Execution rules:
- Inspect the repo before editing.
- Make the smallest useful change that satisfies the task.
- Avoid unrelated refactors.
- Run relevant validation commands.
- Finish with a concise summary of changed files and validation results.
"""


def normalize_codex_log(stream: str, line: str) -> dict[str, object] | None:
    if not line.strip():
        return None

    if stream == "stderr" and _is_noisy_codex_warning(line):
        return None

    if stream != "stdout":
        return {"stream": stream, "message": line, "level": "error"}

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return {"stream": stream, "message": line, "level": "info"}

    message = _summarize_codex_json_event(data)
    if message is None:
        return None
    return {"stream": "codex", "message": message, "level": "info", "source_type": data.get("type")}


def _is_noisy_codex_warning(line: str) -> bool:
    noisy_fragments = [
        "WARN codex_core_plugins::manifest",
        "WARN codex_core_skills::loader",
        "ignoring interface.defaultPrompt",
        "icon path must not contain '..'",
    ]
    return any(fragment in line for fragment in noisy_fragments)


def _summarize_codex_json_event(data: dict[str, object]) -> str | None:
    event_type = data.get("type")

    if event_type == "thread.started":
        return "Codex session started."
    if event_type == "turn.started":
        return "Codex is inspecting the task."
    if event_type == "turn.completed":
        usage = data.get("usage")
        if isinstance(usage, dict) and usage.get("output_tokens"):
            return f"Codex run completed with {usage.get('output_tokens')} output tokens."
        return "Codex run completed."

    item = data.get("item")
    if not isinstance(item, dict):
        return None

    status = item.get("status")
    item_type = item.get("type")

    if item_type == "agent_message":
        text = str(item.get("text", "")).strip()
        return _compact_text(text) if text else None

    if item_type == "command_execution":
        command = str(item.get("command", "")).strip()
        if status == "in_progress":
            return f"Running validation command: {_compact_command(command)}"
        exit_code = item.get("exit_code")
        return f"Command finished with exit code {exit_code}: {_compact_command(command)}"

    if item_type == "file_change":
        changes = item.get("changes")
        if not isinstance(changes, list):
            return None
        paths = []
        for change in changes[:3]:
            if isinstance(change, dict) and change.get("path"):
                paths.append(Path(str(change["path"])).name)
        suffix = ", ".join(paths) if paths else "files"
        if len(changes) > 3:
            suffix += f", and {len(changes) - 3} more"
        verb = "Editing" if status == "in_progress" else "Edited"
        return f"{verb} {suffix}."

    return None


def _compact_text(text: str, limit: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def _compact_command(command: str, limit: int = 120) -> str:
    compact = " ".join(command.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


async def _stream_process(process: asyncio.subprocess.Process) -> AsyncIterator[tuple[str, str]]:
    queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()

    async def read_stream(name: str, reader: asyncio.StreamReader | None) -> None:
        if reader is None:
            await queue.put((name, None))
            return
        while line := await reader.readline():
            await queue.put((name, line.decode(errors="replace").rstrip()))
        await queue.put((name, None))

    tasks = [
        asyncio.create_task(read_stream("stdout", process.stdout)),
        asyncio.create_task(read_stream("stderr", process.stderr)),
    ]
    finished = 0
    while finished < len(tasks):
        stream, line = await queue.get()
        if line is None:
            finished += 1
            continue
        yield stream, line

    await asyncio.gather(*tasks)


async def _git_changed_files(workspace: Path) -> list[str]:
    process = await asyncio.create_subprocess_exec(
        "git",
        "status",
        "--short",
        cwd=workspace,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await process.communicate()
    if process.returncode != 0:
        return []
    return [line.strip() for line in stdout.decode().splitlines() if line.strip()]
