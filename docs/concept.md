# Handoff concept

## One-sentence product

Handoff lets a different AI coding agent continue unfinished work without making the developer explain the project again.

## User

Developers who use multiple AI coding agents and switch between them because of:

- Rate limits or quotas
- Context limits
- Crashes or disconnects
- Different strengths between tools
- A preference for a different interface
- The need to move from a web builder to a local coding agent

## Core moment

A developer is halfway through a task. The current agent stops. The developer opens another agent, which normally starts cold. Handoff automatically preserves a compact, useful continuation brief and makes it available to the next agent.

## Example

1. Antigravity investigates a rate-limiting bug.
2. It changes several files and discovers the likely cause.
3. Antigravity reaches a quota limit before writing the final fix.
4. Handoff has already captured the project, branch, changed files, decisions, blockers, and next action.
5. The developer opens Codex in the same repository.
6. Codex receives the relevant handoff and continues from the next action.
7. Codex updates the same workstream with the fix and test result.

## Product promise

Handoff should make the following sentence true:

> I can switch agents without losing the work already done.

## Why it is different from a transcript archive

A transcript archive answers: “What did the previous agent say?”

Handoff answers: “What should the next agent do now?”

The system keeps source evidence available, but the default resume payload is compact and actionable. It should contain enough context to continue while avoiding a full conversation dump.

## Design principles

1. **The codebase remains the source of truth.** Handoff never replaces Git, tests, or file inspection.
2. **The handoff is a projection, not an authority.** The receiving agent must verify important claims.
3. **Automatic capture must fail safe.** A Handoff failure must never break the coding agent.
4. **Freshness is visible.** Every handoff shows when and how it was captured.
5. **No invented recovery.** If an adapter did not receive the last conversation, Handoff reports the checkpoint boundary honestly.
6. **Local-first after the hackathon.** Cloud vendor integrations are adapters, not the product boundary.
7. **Small tool surface.** The receiving agent should have a few clear tools rather than dozens of generic memory operations.

## Non-goals for MVP

- Running or orchestrating agents as child processes
- Automatic code edits by Handoff
- Full transcript replay in the default resume flow
- Team collaboration and multi-user billing
- A general knowledge graph
- A hosted SaaS requirement
- Supporting every AI coding client at launch
- Replacing GitHub or Git

## Success criteria

A new user should be able to understand the product in one sentence, install it without an account in local mode, connect an agent, see an automatic checkpoint, and resume the task from another agent with a bounded context payload.
