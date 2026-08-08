# Hackathon requirements

## Competition

CockroachDB × AWS Hackathon — Build with Agentic Memory.

Official page: https://cockroachdb-ai.devpost.com/

## Required project shape

Handoff must be an agentic application that uses CockroachDB as its persistent memory layer and is deployed on AWS.

## CockroachDB tools selected

### Managed MCP Server

Use the CockroachDB Cloud Managed MCP Server to inspect the live Handoff schema, indexes, and query plans from an MCP-compatible coding agent. Scope the connection to the Handoff cluster and keep access read-only unless a clearly demonstrated operation requires a write.

Official docs: https://www.cockroachlabs.com/docs/cockroachcloud/connect-to-the-cockroachdb-cloud-mcp-server

### Distributed Vector Indexing

Use CockroachDB VECTOR columns and vector indexes for semantic retrieval of handoff sections. Filter by project and branch before ranking similar work. The vector index must be part of the real resume path, not a dormant example table.

Official docs: https://www.cockroachlabs.com/docs/stable/vector-indexes

## AWS services selected

### Amazon Bedrock

Use Bedrock through the Converse API for structured extraction of handoff state and embedding generation. The provider is isolated behind a model adapter so local mode can use another provider.

Official docs: https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html

### AWS Lambda

Use Lambda for asynchronous checkpoint processing: receive an event, load bounded observations, call Bedrock, validate the result, and write the handoff projection and vector to CockroachDB.

Official docs: https://docs.aws.amazon.com/lambda/latest/dg/welcome.html

## Evidence the submission must show

- Public repository with MIT license.
- Functional demo app or accessible workflow.
- Public video under three minutes.
- Which CockroachDB tools were used and what the agent did with them.
- Which AWS services were used and what they did.
- Handoff memory being written, retrieved, and used to continue work.
- A visible distinction between current repository state and compressed handoff context.

## Demo acceptance criteria

The demo is successful when:

1. Agent A starts a task in a sample repository.
2. Agent A creates meaningful progress and then stops before completion.
3. Handoff automatically creates a partial or complete checkpoint.
4. Agent B opens the same repository or branch.
5. Agent B retrieves the latest unfinished workstream through Handoff.
6. The resume packet contains bounded, actionable context.
7. Agent B continues and validates the next step.
8. The UI or MCP response shows the CockroachDB-backed memory record.
9. The AWS processing path is visible in logs or an architecture view.

## Out of scope for the first submission

- ccloud CLI integration
- CockroachDB Agent Skills Repo integration
- Amazon S3 as a required path
- Amazon EventBridge
- ECS/EKS
- Bedrock Agents
- Automatic execution of generated code changes
- Billing or teams
- Broad support for every agent

## New-work rule

The final project code must be created during the hackathon submission period. Research, planning, and generic reusable tools may inform the project, but any pre-existing code incorporated into the submission must be disclosed as required by the rules.

## Sources

- Hackathon: https://cockroachdb-ai.devpost.com/
- Rules: https://cockroachdb-ai.devpost.com/rules
- CockroachDB AI: https://www.cockroachlabs.com/docs/stable/cockroachdb-and-ai
- CockroachDB vector indexes: https://www.cockroachlabs.com/docs/stable/vector-indexes
- CockroachDB Cloud MCP: https://www.cockroachlabs.com/docs/cockroachcloud/connect-to-the-cockroachdb-cloud-mcp-server
- Bedrock Converse: https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html
- Lambda: https://docs.aws.amazon.com/lambda/latest/dg/welcome.html
- MCP server concepts: https://modelcontextprotocol.io/docs/learn/server-concepts
- Codex MCP: https://developers.openai.com/codex/mcp
- Codex hooks: https://developers.openai.com/codex/hooks
- Antigravity MCP: https://antigravity.google/docs/mcp
- Antigravity hooks: https://antigravity.google/docs/hooks
- OpenCode MCP: https://opencode.ai/docs/mcp-servers/
- OpenCode plugins: https://opencode.ai/docs/plugins/
- Lovable GitHub sync: https://docs.lovable.dev/integrations/github
- Lovable custom MCP: https://docs.lovable.dev/integrations/custom-mcp
- Lovable agent integrations: https://docs.lovable.dev/features/agent-integrations
- Lovable MCP server: https://docs.lovable.dev/integrations/lovable-mcp-server.md
- Hermes compression: https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching
- Hermes memory provider lifecycle: https://hermes-agent.nousresearch.com/docs/developer-guide/memory-provider-plugin
- Hermes hooks: https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks

Current hackathon submissions were not used as examples.

## Financial and operational caution

AWS and CockroachDB limits, model availability, and pricing can change. The implementation must include a local mode and deterministic fallback so the demo does not fail solely because a provider quota or account permission is unavailable.

The official hackathon rules are the source of truth for eligibility and submission compliance.

## Ponytail simplification

The first submission uses two CockroachDB tools and two AWS services. Add more only when a judging requirement or a visible demo gap demands it.

Skipped: S3, EventBridge, ccloud CLI, Agent Skills. Add when raw artifact storage, scheduled maintenance, infrastructure operations, or database-specific expert workflows are proven useful.

## File-by-file execution plan

Implementation starts only after this planning repository is reviewed. The future implementation plan should create tasks in this order:

1. Project identity and portable handoff schema.
2. CockroachDB event and handoff store.
3. CockroachDB Distributed Vector Indexing and filtered resume query.
4. CockroachDB Cloud Managed MCP Server inspection path.
5. MCP tools for start, checkpoint, resume, update, and complete.
6. Amazon Bedrock extraction and embeddings adapter.
7. AWS Lambda asynchronous checkpoint processing.
8. Deterministic partial-handoff fallback.
9. Codex adapter and hooks.
10. Antigravity adapter and hooks.
11. OpenCode adapter and plugin.
12. Lovable GitHub event ingestion and explicit checkpoint path.
13. SQLite storage and local-model fallback.
14. Dashboard and CLI inspection surfaces.
15. Demo fixtures and failure-mode verification.
16. Deployment, README, architecture evidence, and submission packaging.

Each future code task must leave one runnable verification behind. No implementation belongs in this planning repository yet.

## Quality gates

- Handoff capture failure never blocks the source agent.
- Secret redaction tests pass.
- Repeated hook events are idempotent.
- Resume payload respects a token budget.
- Project and branch scoping prevents cross-project leakage.
- Stale and partial checkpoints are visibly labeled.
- Bedrock failures produce a deterministic partial handoff.
- CockroachDB outages queue or fall back locally.
- Vector retrieval is exercised by an end-to-end test.
- The demo can run with seeded data when external provider quotas are unavailable.

## Risks

| Risk | Mitigation |
|---|---|
| Agent hook payloads differ or change | Thin adapters, fixture payloads, explicit version metadata |
| Lovable does not expose full session history | Use GitHub diffs plus explicit MCP checkpoint; label partial context |
| Bedrock quota or model access fails | Deterministic fallback and local provider mode |
| Vector index setup is unavailable on a small cluster | Keep lexical retrieval fallback and surface index health |
| Resume context is wrong | Show provenance, confidence, freshness, and require repository verification |
| Automatic capture is noisy | Debounce, event caps, and projection-only persistence |
| Tool schema bloats agent context | Keep MCP surface small and return bounded packets |
| Cloud deployment distracts from the core | Local-first first, AWS adapter second |

## Judge-facing proof

The demo must prove that the memory layer changes the agent outcome:

- Without Handoff, the second agent starts cold.
- With Handoff, it receives a compact continuation packet.
- CockroachDB stores the task state and embedding used by retrieval.
- Bedrock produces the structured projection.
- Lambda runs the processing path.
- The second agent validates the packet against the code and continues.

A screenshot of a connected database is not enough. The integration seam must be visible in the workflow.

## Licensing

Use MIT for the Handoff repository unless a dependency imposes a compatible alternative. Track third-party licenses in the final implementation repository.

## Current decision log

- Product name: Handoff
- Primary user: developers switching between AI coding agents
- Core job: save unfinished work so another agent can continue
- Primary automatic demo: Antigravity → Codex
- Secondary example: Lovable → OpenCode
- Core architecture: vendor-neutral adapters over a portable handoff store
- Hackathon CockroachDB tools: Managed MCP Server + Distributed Vector Indexing
- Hackathon AWS services: Bedrock + Lambda
- No code in the planning phase
- No current hackathon submissions used as prior art

## Review gate before implementation

The owner should review and approve:

- Product scope
- Adapter order
- Handoff sections
- Local/cloud boundary
- Selected CockroachDB and AWS services
- Failure behavior
- Demo acceptance criteria

Only after approval should the implementation repository be created or code be added.
