# Handoff architecture

## Architectural shape

Handoff uses a thin adapter layer around a provider-neutral core.

```text
AI client adapters
  Codex hooks + MCP
  Antigravity hooks + MCP
  OpenCode plugin + MCP
  Lovable GitHub events + MCP checkpoint
          |
          v
Handoff core
  project identity
  workstream state
  event ledger
  compression pipeline
  resume packet
  retrieval and freshness rules
          |
          +--> local backend: SQLite + local files + local model
          |
          +--> hackathon backend: API + Lambda + Bedrock + CockroachDB
```

Handoff does not run an agent loop. The connected agent continues to own model calls, file operations, shell commands, permissions, and code changes.

## Runtime boundaries

### Agent clients

Agents provide lifecycle events, MCP calls, filesystem context, and Git context. Each adapter normalizes its event format into Handoff events.

### Handoff MCP server

The MCP server is the agent-facing interface. The initial tool surface should stay small:

- Start or identify a workstream
- Record an observation or checkpoint
- Resume the best unfinished workstream
- Get a specific handoff
- Update progress
- Complete or abandon a workstream

The server returns structured results and a compact Markdown resume packet.

### Handoff API

The API is the application boundary for local HTTP mode and the cloud deployment. It owns authentication, project scoping, idempotency, event ingestion, compression jobs, and storage access.

### Compression worker

The worker converts raw observations and Git metadata into a handoff projection. It may use a model, but the core must retain a deterministic fallback that can produce a basic summary from Git state and captured events.

### Dashboard and CLI

These are inspection surfaces, not the primary agent interface. They show workstreams, freshness, changed files, blockers, decisions, and the latest next action. They allow a developer to correct or archive an incorrect handoff.

## Hackathon deployment

```text
Agent client
    |
    | MCP
    v
Handoff MCP/API on AWS
    |
    +--> AWS Lambda: checkpoint and GitHub event processing
    |
    +--> Amazon Bedrock: structured extraction and embeddings
    |
    +--> CockroachDB Cloud: SQL state + vector memory
    |       |
    |       +--> Managed MCP Server: audited database inspection
    |       +--> Distributed Vector Indexing: similar-work retrieval
    |
    +--> optional S3 later: raw transcripts and large artifacts
```

The MVP should use Bedrock and Lambda. S3 and EventBridge remain optional until the core handoff path works.

## Local deployment

```text
Agent client
    |
    | stdio MCP
    v
Local Handoff process
    |
    +--> SQLite: workstreams, events, handoffs
    +--> local files: optional source artifacts
    +--> Ollama or deterministic extractor: optional compression
```

The local backend is a portability and failure fallback. The hackathon cloud backend is the primary implementation path and must be exercised end to end before the local fallback is considered complete.

## Data flow

### Capture

1. An adapter receives a lifecycle event or GitHub event.
2. It validates the project identity and event envelope.
3. It redacts obvious secrets and records only allowed fields.
4. It writes an idempotent event.
5. A compression job is queued when the event is a checkpoint, compaction boundary, idle boundary, or session end.

### Compression

1. Load the latest workstream state and bounded recent observations.
2. Load Git branch, commit, dirty files, and changed-file metadata when available.
3. Ask Bedrock for structured extraction in hackathon mode.
4. Validate the response against the handoff schema.
5. Fall back to deterministic Git/event summarization if the model fails.
6. Write a new immutable handoff projection and update the workstream pointer.
7. Generate an embedding for retrieval.

### Resume

1. The receiving adapter identifies the project and current branch.
2. Handoff selects unfinished workstreams, preferring exact project and branch matches.
3. It combines status, freshness, recency, lexical matches, and vector similarity.
4. It returns a token-bounded resume packet.
5. The receiving agent inspects the listed files and validates the packet against the repository.

## Important invariants

- Event ingestion is idempotent using adapter event ID plus source identity.
- A handoff is immutable; corrections create a new version linked to the previous one.
- The latest pointer can move backward only through an explicit user action.
- Branch and repository scope are mandatory for automatic retrieval.
- Secrets, tokens, and full environment dumps are excluded by default.
- Handoff hooks are best effort and always exit successfully unless a user explicitly requests a blocking policy.
- Raw transcripts are never included in the default resume payload.
