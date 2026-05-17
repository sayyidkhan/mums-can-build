# AGENTS.md

## Project: Mums Can Build

Mums Can Build is a voice-first backend harness that turns natural spoken ideas into structured software tasks, then coordinates Codex to build, test, and iterate on the codebase.

The product metaphor is simple: a non-technical user speaks naturally, like a mum talking to her son. The harness acts like the son: it listens, clarifies, translates the idea into requirements, and delegates implementation to Codex.

## Core Principle

Do not treat user speech as direct coding instructions.

Always convert:

Voice input → clarified intent → structured requirements → scoped Codex task → code change → validation → user feedback.

## System Roles

### 1. User

The user may be non-technical. They may describe problems vaguely, emotionally, or incompletely.

Example:

> I want people to book cake orders from me.

Do not expect technical language.

### 2. Voice Harness

The harness is responsible for:
- understanding the user’s goal
- asking clarifying questions
- extracting requirements
- creating structured tasks
- deciding when Codex should run
- summarizing Codex progress back to the user

### 3. Codex Worker

Codex is the developer.

Codex should:
- inspect the existing repo before editing
- make the smallest useful change
- avoid unrelated refactors
- run validation commands
- report changed files
- explain what was built in plain English

## Build Task Format

Every Codex task should be created in this structure:

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