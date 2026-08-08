# Handoff roadmap

This is a planning roadmap, not an implementation status report.

## Phase 0 — plan review

- Review concept, architecture, memory model, and integrations.
- Confirm the first demo pair: Antigravity → Codex.
- Confirm the secondary pair: Lovable → OpenCode.
- Confirm local fallback and vendor-neutral boundary.
- Freeze the MVP scope.

Exit condition: written approval to implement.

## Phase 1 — portable local core

- Define the handoff envelope.
- Define project, repository, branch, and workstream identity.
- Implement event idempotency rules.
- Implement bounded resume packet rules.
- Implement SQLite persistence.
- Implement deterministic partial handoff fallback.

Exit condition: seeded local data can be saved and resumed without a model or cloud account.

## Phase 2 — MCP and automatic lifecycle capture

- Define the minimal MCP tool surface.
- Add Codex MCP configuration and hook adapter.
- Add Antigravity MCP configuration and hook adapter.
- Add OpenCode MCP configuration and optional plugin adapter.
- Add session-start resume injection where the client supports it.
- Add failure-safe hook wrappers.

Exit condition: two local agents can create and resume a handoff using the same project and branch.

## Phase 3 — cloud memory and AWS path

- Add CockroachDB storage adapter.
- Create SQL tables for workstreams, events, handoffs, and embeddings.
- Create the Distributed Vector Indexing path.
- Configure Managed MCP Server for read-only database inspection.
- Add Bedrock structured extraction.
- Add Bedrock embedding generation.
- Add Lambda checkpoint processor.

Exit condition: a handoff is processed by Lambda, stored in CockroachDB, retrieved by vector similarity, and returned through MCP.

## Phase 4 — Lovable and GitHub path

- Receive GitHub push events.
- Link commits to a project and workstream.
- Summarize changed files.
- Provide an explicit Lovable MCP checkpoint path.
- Show partial-context labeling when only Git evidence is available.

Exit condition: Lovable-generated code can be pulled into OpenCode and resumed with Handoff context.

## Phase 5 — demo surface and evidence

- Build a small dashboard for workstreams and handoff versions.
- Add seed scenarios for quota stop, context pressure, and crash/partial capture.
- Add a CockroachDB inspection view or scripted query evidence.
- Add Lambda and Bedrock processing logs.
- Add a local-mode fallback demo.
- Test the full acceptance criteria.

Exit condition: the complete workflow is repeatable without relying on a live provider quota.

## Phase 6 — submission packaging

- Public MIT repository.
- Setup instructions.
- Architecture diagram.
- CockroachDB integration explanation.
- AWS integration explanation.
- Security and privacy notes.
- Demo app URL.
- Public video.
- Honest limitations and prior-art disclosure.

## Explicitly deferred

- Team accounts
- Billing
- Agent orchestration and spawning
- A2A protocol
- Full transcript cloud archive
- S3 and EventBridge requirements
- ccloud CLI
- Agent Skills Repo
- Broad project-memory features
- Automatic code changes by Handoff
