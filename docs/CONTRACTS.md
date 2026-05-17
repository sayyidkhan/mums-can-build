# Contracts

This document captures the current POC contracts implemented by the FastAPI harness.

## WebSocket

Endpoint:

```text
ws://127.0.0.1:8000/ws/{session_id}
```

## Browser Voice Call

Endpoint:

```text
GET /
```

The browser page starts a WebRTC call with OpenAI Realtime and opens a harness WebSocket for builder events.

SDP proxy endpoint:

```text
POST /realtime/call
```

Request:

```json
{
  "sdp": "browser-generated SDP offer",
  "model": "gpt-realtime-2",
  "voice": "marin"
}
```

`model` and `voice` are optional. Defaults come from `OPENAI_REALTIME_MODEL` and `OPENAI_REALTIME_VOICE`, falling back to `gpt-realtime-2` and `marin`.

The server sends the browser SDP offer to OpenAI as `application/sdp`. Detailed session configuration, including transcription and voice, is applied from the browser over the Realtime data channel with `session.update` after the channel opens.

## Client Message

```json
{
  "type": "user.transcript",
  "text": "Build a cake order app with a menu and checkout request form",
  "worker": "mock",
  "workspace": "/optional/path/for/real/codex",
  "auto_start": true
}
```

Fields:

- `type`: currently only `user.transcript`
- `text`: transcript text from the user
- `worker`: `mock` or `real`
- `workspace`: optional path used by the real Codex worker
- `auto_start`: when `false`, the PM creates the task but does not start a worker

## Server Event

```json
{
  "type": "pm.task_ready",
  "session_id": "local-demo",
  "payload": {},
  "spoken": "I have enough. I am preparing the build task.",
  "event_id": "abc123",
  "created_at": "2026-05-17T05:05:17Z"
}
```

Fields:

- `type`: event name
- `session_id`: active session id
- `payload`: event-specific structured data
- `spoken`: short voice-safe text, or `null`
- `event_id`: unique event id
- `created_at`: UTC timestamp

## Event Types

- `session.started`
- `user.transcript`
- `pm.thinking`
- `pm.question`
- `pm.task_ready`
- `codex.started`
- `codex.log`
- `codex.done`
- `session.error`

## Codex Task

```json
{
  "title": "Short task title",
  "user_goal": "What the user wants in plain English",
  "requirements": ["Requirement 1"],
  "acceptance_criteria": ["Criteria 1"],
  "constraints": [
    "Inspect the existing repo before editing.",
    "Make the smallest useful change for a demo.",
    "Do not change unrelated files.",
    "Run relevant validation commands and report the result."
  ]
}
```

## Spoken Update Policy

Allowed spoken updates are short milestones:

- "I am ready."
- "I am checking what you need."
- "I have enough. I am preparing the build task."
- "I am starting the builder now."
- "The builder is editing files."
- "The first version is ready."
- "The builder hit an error."

Raw logs, stack traces, diffs, and file-by-file implementation details should stay in text events.

## Real Codex Log Handling

The real Codex subprocess emits verbose JSONL and stderr warnings. The harness keeps raw subprocess lines in session metadata and sends clients cleaned `codex.log` events.

Current client-facing behavior:

- known plugin and skill-loader warnings are suppressed
- Codex JSONL events are summarized into short progress messages
- file changes are reported by filename
- command executions are reported by command and exit code
- long agent messages are compacted

Session snapshots expose `raw_codex_log_count` for debugging without returning the raw log body.
