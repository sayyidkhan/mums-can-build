# Plan

## Product Loop

The app should feel like this:

```text
user speaks
→ voice PM understands and clarifies
→ voice PM prepares resources
→ voice PM delegates to Codex
→ Codex builds
→ voice PM gives short spoken updates
→ user gives feedback
```

The voice PM should not narrate implementation details. The user is listening, not reading.

Good spoken updates:
- "I am checking what you need."
- "I need one detail before I build."
- "I have enough. I am preparing the build task."
- "I am starting the builder now."
- "The builder is editing files."
- "The first version is ready."

Avoid spoken updates like:
- file-by-file explanations
- stack traces
- long logs
- implementation reasoning
- full diffs

Detailed progress should still be captured as text events for debugging.

---

## Definition Of Done

The POC is done when the user can code hands-free through the voice harness.

That means:
- the user can speak an app or code change request
- the voice PM can clarify only what is necessary
- the voice PM can create a structured Codex task
- the harness can delegate that task to real Codex
- Codex can edit code in a workspace
- progress is streamed back in real time
- the voice PM gives short spoken milestone updates
- the user can give follow-up instructions by voice
- the loop works without the user touching the machine during the coding flow

The project is not done just because:
- transcript input works
- mock Codex works
- task JSON is generated
- logs stream correctly
- a UI exists

Those are intermediate milestones. The real finish line is:

```text
talk → Codex builds → voice feedback → Codex iterates
```

---

## Phase 0: Build Resources First

Before building the app, create the resources the harness needs to behave consistently.

Resources to define:
- session event schema
- voice PM prompt
- spoken update policy
- structured Codex task schema
- Codex prompt template
- mock Codex event script
- real Codex CLI command contract
- minimal state shape
- Redis usage rules, if needed

Target outcome:
- the harness has clear contracts before any app code exists
- the voice PM knows when to clarify, when to delegate, and what to say aloud
- Codex receives scoped tasks instead of raw user speech

---

## Phase 1: Realtime Voice Harness Skeleton

Build the smallest FastAPI harness.

Core pieces:
- WebSocket endpoint for session events
- in-memory session state
- optional local Redis adapter only if in-memory state becomes painful
- event broadcaster for realtime updates
- transcript input support before full audio support

Initial event types:

```text
session.started
user.transcript
pm.thinking
pm.question
pm.task_ready
codex.started
codex.log
codex.done
session.error
```

Spoken events should be short and high level.

Text/debug events can contain more detail.

---

## Phase 2: Voice PM

The voice PM acts like a project manager.

Responsibilities:
- listen to the user
- detect missing requirements
- ask only necessary clarifying questions
- convert intent into structured task JSON
- decide when to delegate to Codex
- provide short spoken updates

The voice PM must not pass raw speech directly to Codex.

Required task format:

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

---

## Phase 3: Mock Codex Worker

Build the mock worker before real Codex integration.

Purpose:
- prove delegation flow
- prove realtime updates
- prove session state
- prove spoken status behavior
- avoid waiting on real Codex during harness testing

Mock worker emits:

```text
codex.started
codex.log
codex.done
```

The voice PM speaks only summarized milestones.

Example:

```text
"The builder is editing files."
"The first version is ready."
```

---

## Phase 4: Real Codex Worker

Connect the harness to Codex CLI through a subprocess.

Flow:

```text
structured task JSON
→ Codex prompt template
→ codex exec
→ stdout/stderr stream
→ codex.log events
→ completion status
→ git diff summary
```

Rules:
- run Codex in a controlled workspace
- stream raw logs as text/debug events
- do not speak raw logs
- summarize progress aloud only at milestone changes
- capture changed files or git diff after completion

Workspace order:
- start with one local test repo
- move to git worktree per session when needed

---

## Phase 5: Realtime Audio

After transcript mode works, connect audio.

Use `gpt-realtime-2` for the voice PM.

Connection choice:
- WebSocket for the first backend-driven POC
- WebRTC later for browser/mobile direct audio

Realtime responsibilities:
- receive user speech
- produce short spoken responses
- emit text events for detailed progress
- allow interruption
- keep the user informed without over-explaining

---

## Phase 6: Preview And Feedback Loop

After Codex can build, add the preview loop.

Core pieces:
- run the generated app locally
- return preview URL or local status
- summarize what changed
- ask for feedback by voice
- create follow-up task from feedback

The voice PM should say:

```text
"The first version is ready. You can try it now."
```

It should not read the diff aloud.

---

## Phase 7: Demo Flow

Target demo:

```text
user describes an app idea
→ voice PM asks one or two clarifying questions
→ resources/task are prepared
→ Codex starts
→ voice PM gives short milestone updates
→ app preview is ready
→ user gives voice feedback
→ Codex iterates
```

Success criteria:
- the user can complete the coding loop hands-free
- the app feels voice-first
- the user never has to read logs
- the harness still captures enough detail for debugging
- Codex receives scoped tasks, not vague conversation
- the architecture stays lean
