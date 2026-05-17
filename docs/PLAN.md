Phase 1: Backend skeleton
- FastAPI or Node.js backend
- WebSocket endpoint for voice/session events
- In-memory session state for transcript, requirements, task state (POC: no DB; optional local Redis only if you add a queue)

Phase 2: Voice harness (project manager agent)
- Accept audio stream or transcript input
- Maintain conversation state in memory
- Extract intent into structured build tasks
- Ask clarifying questions before handing off to Codex

Phase 3: Codex worker
- Create isolated repo workspace
- Generate Codex prompt from task JSON
- Run Codex CLI
- Stream logs back to harness
- Capture git diff

Phase 4: Preview loop
- Run app locally or generate preview URL
- Return logs, diff, preview URL
- User gives voice feedback
- Harness creates follow-up task

Phase 5: Demo flow
- User says an idea
- Harness clarifies
- Codex builds
- Harness reports progress
- User refines by voice