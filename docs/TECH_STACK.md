# Mums Can Build — Tech Stack

## Core Vision

A lean voice-first backend harness that:
- listens to users in real time
- converts conversations into structured software tasks
- coordinates Codex to build software
- streams progress back to the user

The POC should prove one loop:

```text
user talks
→ voice PM clarifies intent
→ structured task JSON
→ Codex builds
→ progress streams back
→ user gives feedback
```

## POC Scope

Keep the first version deliberately small.

In scope:
- voice/session WebSocket
- transcript and session state
- voice PM task shaping
- mock Codex worker for harness testing
- real Codex CLI worker via subprocess
- progress streaming

Out of scope:
- database
- auth
- multi-tenancy
- dashboard
- hosted queues
- agent frameworks
- production deployment complexity

Redis is allowed only if in-memory state becomes painful or you need simple local pub/sub between processes.

---

# Final POC Stack

```text
Voice:
- OpenAI Realtime API

Backend Harness:
- FastAPI

Runtime:
- Python asyncio

Realtime:
- WebSockets

State:
- in-memory first
- optional local Redis if needed

Codex Bridge:
- mock Codex worker first
- real Codex CLI subprocess second

Workspace:
- local repo for earliest testing
- git worktree per session when isolation is needed

Database:
- none

Frontend:
- none for first POC
- optional minimal UI later
```

---

# 1. Voice Layer

## Recommended

- OpenAI Realtime API
- WebSocket connection
- low-latency speech-to-speech interaction

Why:
- realtime conversations
- interruption handling
- streaming responses
- natural voice-first experience

---

# 2. Backend Harness

## Recommended

- FastAPI

Use FastAPI as a thin transport and orchestration layer.

It should handle:
- WebSocket connections
- receiving audio, transcript, and session events
- keeping session state
- calling the voice PM logic
- starting Codex workers
- streaming logs and task status back to the user

It should not become a large backend platform.

Avoid for POC:
- ORM
- database models
- complex routers
- dependency injection layers
- background job framework
- separate services

Minimal structure:

```text
app/
  main.py
  sessions.py
  voice_pm.py
  codex_worker.py
```

---

# 3. State

## Default

- in-memory Python objects

Use this first for:
- active sessions
- transcript buffer
- current requirements
- current task state
- current Codex run status

## Optional

- local Redis

Use Redis only if you need:
- state shared across multiple backend processes
- simple pub/sub for streaming events
- resumable-ish session state during local development
- a small queue for Codex jobs

Do not use Redis as a reason to add BullMQ, Celery, or a larger worker system in the POC.

---

# 4. Voice PM Layer

The voice PM is not an extra framework at first.

It is plain application logic that:
- reads transcript/session context
- asks clarifying questions
- extracts requirements
- creates a structured Codex task
- decides when the task is ready to run

Every Codex task should use this shape:

```json
{
  "title": "Short task title",
  "user_goal": "What the user wants in plain English",
  "requirements": [
    "Requirement 1",
    "Requirement 2"
  ],
  "acceptance_criteria": [
    "Criteria 1",
    "Criteria 2"
  ],
  "constraints": [
    "Do not change unrelated files",
    "Keep implementation simple for demo"
  ]
}
```

Do not add Mastra or LangGraph until plain code becomes the bottleneck.

---

# 5. Codex Execution Layer

## Recommended Development Order

### 1. Mock Codex Worker

Use this first to test the harness loop without invoking real Codex.

It should emit fake progress events:

```text
codex_started
codex_log
codex_done
```

This validates:
- WebSocket event flow
- session state
- task creation
- progress streaming
- user feedback loop

### 2. Real Codex CLI Worker

Once the harness works, run Codex through a subprocess:

```text
FastAPI
→ asyncio subprocess
→ codex exec
→ streamed stdout/stderr
→ git diff/result summary
```

Responsibilities:
- receive structured task JSON
- generate a Codex prompt
- run Codex in the selected workspace
- stream logs back to the user
- capture completion status
- capture changed files or git diff

---

# 6. Workspace

## Earliest POC

Run Codex in one local test repo.

This is fastest for proving the loop.

## Better POC

Use one git worktree per session:

```bash
git worktree add /tmp/mcb-session-001 main
```

Why:
- isolates Codex runs
- makes diffs easier to inspect
- allows cleanup after each session
- reduces accidental damage to the main repo

---

# 7. Real-Time Event Streaming

Use WebSockets for all live events:
- transcript updates
- voice PM status
- clarifying questions
- task JSON preview
- Codex logs
- completion status
- preview URL later

Keep event payloads simple JSON.

---

# 8. Frontend

No frontend is required for the first POC.

Start with:
- WebSocket client script
- terminal logs
- voice/transcript test input

Add a minimal UI later only if needed for demo clarity.

---

# 9. Deployment

Do not optimize deployment yet.

For the first version:
- run locally
- use local environment variables
- use local Redis only if needed
- run Codex on the same machine

Deployment comes after the local voice-to-Codex loop works.

---

# Most Important Design Principle

Keep the architecture:

```text
simple
observable
streaming-first
demo-first
```

The magic is:

```text
user talks → PM scopes → Codex builds live
```
