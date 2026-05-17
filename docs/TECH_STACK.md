# Mums Can Build — Tech Stack

## Core Vision

A voice-first backend harness that:
- listens to users in real time
- converts conversations into structured software tasks
- coordinates Codex to build software
- streams progress back to the user

## POC scope (keep this minimal)

For the first POC, treat the **voice agent as the project manager**: it clarifies intent, scopes work, and hands **structured tasks** to **Codex**—nothing else is in scope until that loop feels solid.

- **Codex**: required integration (CLI or equivalent bridge from the harness).
- **Database**: skip for POC (no SQLite/Postgres). Hold session/transcript/task state **in memory** in the backend process.
- **Redis**: only add if you truly need a queue/pub-sub beyond an in-process queue; run **Redis locally** (Docker/`redis-server`), not a hosted DB.

---

# Recommended Hackathon Stack

## 1. Voice Layer

### Realtime Voice
- OpenAI Realtime API
- WebSocket connection
- Low-latency speech-to-speech interaction

### Why
This gives:
- realtime conversations
- interruption handling
- streaming responses
- natural “ChatGPT Voice”-like experience

---

# 2. Backend Harness

## Framework

### Option A (Recommended)
- FastAPI

Why:
- fast WebSocket support
- async friendly
- easy orchestration
- great for AI backends

### Option B
- NestJS

Use if:
- you prefer TypeScript everywhere

---

# 3. Agent Harness Layer

POC framing: one primary agent—the **voice PM**—owns clarification and task shaping before Codex runs.

## Recommended

### Option A
- Mastra

Why:
- lightweight
- agent orchestration
- workflow abstraction
- hackathon friendly

### Option B
- LangGraph

Why:
- more advanced workflows
- stateful agent graphs

For hackathon:
> Mastra is probably faster.

---

# 4. Codex Execution Layer

## Core
- OpenAI Codex CLI

Responsibilities:
- inspect repo
- edit files
- run commands
- generate code
- validate builds

---

# 5. Sandbox / Workspace

## Recommended
- git worktree
- temporary isolated folders

Example:

```bash
/workspaces/session-001
/workspaces/session-002
```

Why:
- isolated builds
- safe iteration
- easier cleanup

---

# 6. Real-Time Event Streaming

## Recommended
- WebSockets

Used for:
- live logs
- transcript streaming
- Codex progress
- task updates

---

# 7. Database

POC default: **none**. Persist nothing beyond what git already captures once Codex edits the repo.

When you outgrow POC:

## Simple Option
- SQLite

## Scalable Option
- PostgreSQL

Store (later): sessions, transcripts, tasks, diffs, previews.

---

# 8. Queue System

POC default: **in-memory async queue** inside the backend (good enough for one Codex job at a time).

If you need durability or worker separation:

### Optional (local only)
- Redis (local)
- BullMQ (if you adopt Redis)

Used for:
- Codex jobs
- background execution
- retries

---

# 9. Frontend (Optional for POC)

## Recommended
- Next.js

Only needed for:
- transcript UI
- preview iframe
- logs panel

But honestly:
> backend-only POC is enough initially.

---

# 10. Deployment

## Fastest
- Railway
- Render

## Frontend
- Vercel

---

# Final Recommended Stack

```text
Voice:
- OpenAI Realtime API

Backend Harness:
- FastAPI

Agent Orchestration:
- Mastra

Voice agent role (POC):
- Project manager → structured tasks → Codex

Execution:
- Codex CLI

Realtime:
- WebSockets

Queue (POC):
- in-process (optional: local Redis + BullMQ)

Database (POC):
- none

Frontend:
- Next.js (optional)

Deployment:
- Railway + Vercel
```

---

# Most Important Design Principle

Keep the architecture:

```text
simple
observable
streaming-first
demo-first
```

Do NOT overbuild:
- auth
- multi-tenancy
- Kubernetes
- scalable infra
- production security

The magic is:

> user talks → PM agent scopes → Codex builds live.