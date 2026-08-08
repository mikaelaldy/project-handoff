# Memory and handoff model

## Two layers

Handoff separates short-lived workstream state from durable project memory.

### Workstream state

Answers: “What was happening in the unfinished task?”

A workstream is an evolving chain of handoffs for one project task. It contains:

- Workstream ID
- Project ID
- Repository identity
- Branch and commit
- Source and receiving agents
- Status: active, paused, blocked, completed, abandoned
- Latest handoff ID
- Freshness and capture source
- Created and updated timestamps

### Project memory

Answers: “What should future work on this project always know?”

Project memory is out of the MVP’s automatic scope but the model leaves room for:

- Confirmed decisions
- Project conventions
- Reusable lessons
- Known gotchas
- Architecture constraints

Do not mix durable project memory with every session observation. Handoff is primarily about unfinished work.

## Handoff sections

The compact handoff projection uses these sections, based on recurring patterns in open-source handoff projects and Hermes-style compression:

1. **Goal** — what the user asked for
2. **Current state** — what is true now
3. **Completed** — work already finished
4. **Decisions** — choices and reasons
5. **Blockers** — what prevents completion
6. **Files and artifacts** — repository-relative pointers only
7. **Validation** — tests and commands already run
8. **Next action** — the smallest useful next step
9. **Risks and cautions** — what the next agent must verify
10. **Provenance** — source agent, event boundary, commit, timestamp, and confidence

The receiving agent gets a token-bounded projection. A human can inspect the full version in the dashboard or CLI.

## Versioning

Every compression creates a new handoff version instead of mutating history. Versions link with `continues_from` and `supersedes` relationships.

This supports:

- Resuming a chain
- Seeing what changed between handoffs
- Correcting a bad summary
- Auditing which agent produced a claim
- Recovering from a failed compression

## Retrieval

Retrieval is hybrid:

- Exact project and repository filter
- Branch filter when available
- Status filter for unfinished work
- Keyword and file-path matches
- Vector similarity over handoff sections
- Recency and freshness score
- Explicit user-selected handoff ID wins over automatic ranking

Handoffs should normally be pinned or protected from generic memory decay until their workstream is completed. Completed work can remain searchable as history but should not automatically dominate active-task retrieval.

## Token budget

The resume packet has a hard budget. It should include the current state and next action first, then decisions, blockers, files, and validation. Full transcripts and large diffs are references, not injected context.

If the packet is too large:

1. Keep goal, current state, blockers, and next action.
2. Keep only relevant file paths.
3. Replace long validation logs with results and links.
4. Add a source reference for deeper inspection.

## Confidence and freshness

Each extracted section carries:

- Confidence: confirmed, inferred, or unknown
- Source: explicit agent statement, tool evidence, Git evidence, or model inference
- Captured at
- Last verified commit

The receiving agent should be told when the handoff is stale or was created from partial evidence.

## Automatic capture policy

Capture checkpoints at:

- Pre-compaction or context-pressure boundary
- Session end or stop boundary
- Idle boundary when the adapter exposes one
- GitHub push for Lovable projects
- Explicit user request
- Significant milestone, subject to a debounce and daily cap

Do not capture every tool result as a permanent handoff. Raw observations may be retained temporarily for compression, but only a projection becomes the resumable handoff.

## Failure behavior

If Bedrock is unavailable:

- Preserve the raw event and Git metadata.
- Create a deterministic partial handoff.
- Mark extraction as partial.
- Let the next agent inspect the source files.

If CockroachDB is unavailable:

- Queue or write locally when configured.
- Never block the coding agent by default.
- Report that the handoff is pending synchronization.
