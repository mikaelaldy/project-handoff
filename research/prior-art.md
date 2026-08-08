# Prior art and architecture research

Research date: 2026-08-08.

Current CockroachDB hackathon submissions were excluded.

## Main patterns found

### 1. Thin adapters over a shared core

Agent Recall and ai-memory support several clients with platform-specific hooks or plugins over a shared worker/API and storage layer. The key lesson is that most logic should be platform-agnostic; each new client should only translate lifecycle events and context injection.

- Agent Recall: https://github.com/d-wwei/agent-recall
- ai-memory: https://github.com/akitaonrails/ai-memory

### 2. Compact handoff instead of raw transcript injection

A2CR’s WorkBaton, Engram’s seven handoff sections, Mimir’s compact session summary, and AI Switch’s resume prompt all make the same tradeoff: the next agent needs goal, current state, decisions, blockers, validation, and next action, not every previous message.

- A2CR: https://github.com/a2cr/a2cr
- Engram: https://github.com/edg-l/engram-mcp
- Mimir: https://github.com/iamngoni/mimir
- AI Switch: https://github.com/Alex-Shirazi1/AISwitchMCPServer

### 3. Automatic capture must use lifecycle hooks

MCP alone is request/response. It cannot reliably push a memory into a client without the agent calling a tool. Automatic behavior therefore uses client hooks or plugins:

- Codex: `PreCompact`, `PostCompact`, `SessionStart`, `SessionEnd`, `PostToolUse`
- Antigravity: `PostInvocation`, `PostToolUse`, `Stop`
- OpenCode: session events and compaction plugin hook
- Lovable: GitHub push events and explicit MCP checkpoint, because full conversation lifecycle access is not documented

This is consistent with:

- Hermes memory providers and `on_pre_compress` / `on_session_end`
- Codex hooks: https://developers.openai.com/codex/hooks
- Antigravity hooks: https://antigravity.google/docs/hooks
- OpenCode plugins: https://opencode.ai/docs/plugins/
- Lovable GitHub sync: https://docs.lovable.dev/integrations/github

### 4. Separate current work from durable memory

Open-source systems distinguish a current task/session handoff from long-lived project facts. Handoff should begin with the former. Generic project memory, graph links, decay, and global preferences should not make the MVP noisy.

- Engram: structured handoffs plus separate typed memories
- A2CR: WorkBaton for resume state, WorkStash for supporting notes
- Mimir: session summaries plus a writable project notes store
- Hermes: persistent memory and separate context compression

### 5. Branch and project scope prevent context leakage

Engram chains handoffs by Git branch. Kairo records repository intelligence and branch/session state. This is important because a handoff from `feat/auth` should not automatically appear while working on an unrelated `fix/billing` branch.

- Engram: https://github.com/edg-l/engram-mcp
- Kairo: https://github.com/sandeepbollavaram/Kairo
- Context Fabric: https://github.com/vikas9793/context-fabric

### 6. Hybrid retrieval beats a single giant vector store

Prior projects combine project/branch filters, keyword/file matches, recency, and semantic similarity. Pure vector search can return a semantically related but wrong project or branch. Handoff should filter first and use vectors as one ranking signal.

- Engram: hybrid cosine + recency + importance
- Synapto: vector + full-text + structural signals
- Context Fabric: FTS5 plus path-aware relevance and token budgeting

- Synapto: https://github.com/ramonlimaramos/synapto
- Context Fabric: https://github.com/vikas9793/context-fabric

### 7. Fail-safe capture and deterministic fallback matter

Memory systems run beside coding agents, so a memory failure must not break the coding session. ai-memory and the memory-agent project use safe fallbacks; several systems support local SQLite and rule-based summaries. Handoff should persist a partial Git/event checkpoint even when the model or cloud backend fails.

- ai-memory: https://github.com/akitaonrails/ai-memory
- memory-agent: https://github.com/nathanmauro/memory-agent
- Engram: https://github.com/edg-l/engram-mcp

### 8. Local-first is a strong open-source boundary

Mimir, Engram, A2CR, and Kairo keep local storage as the primary distribution model. Cloud sync creates operational and privacy complexity. Handoff should keep SQLite/local files as a complete mode and add CockroachDB as the hackathon cloud adapter.

- Mimir: SQLite handoff notes
- Engram: SQLite + local ONNX embeddings
- A2CR: local SQLite and no hosted relay
- Kairo: `.kairo/` append-only local state

### 9. Do not overbuild an orchestrator

`agent-handoff` is a different category: it spawns agents, queues jobs, and passes context payloads between workers. That is useful, but it expands the project into orchestration, process management, heartbeats, retries, and A2A. Handoff should first remember and resume work; it should not run agents.

- agent-handoff: https://github.com/daax-dev/agent-handoff

### 10. Existing naming collision

There are already projects called `handoff`, `handoff-mcp`, and `agent-handoff`. The public repository can remain `handoff` if available, but the package name, CLI binary, and MCP server name will need a distinct namespace before implementation. Candidate names should be checked before publishing a package.

- https://github.com/trevhud/handoff
- https://github.com/alphaelements/handoff-mcp
- https://github.com/Alex-Shirazi1/AISwitchMCPServer

## Architecture decisions derived from the research

1. Use a compact, versioned handoff packet.
2. Store handoff sections separately enough to retrieve only what fits the token budget.
3. Scope by project, repository, and branch before semantic ranking.
4. Use immutable handoff versions with `continues_from` and `supersedes` links.
5. Use hooks for automatic capture and MCP for explicit operations.
6. Keep all hooks failure-safe and idempotent.
7. Make local SQLite a complete fallback, not a demo stub.
8. Keep cloud-specific behavior behind storage/model/queue adapters.
9. Use Bedrock only for extraction and embeddings during the hackathon; do not make it the agent runtime.
10. Prove the vector search changes resume behavior in the demo.

## Official references

- MCP server concepts: https://modelcontextprotocol.io/docs/learn/server-concepts
- Codex MCP: https://developers.openai.com/codex/mcp
- Codex hooks: https://developers.openai.com/codex/hooks
- Antigravity MCP: https://antigravity.google/docs/mcp
- Antigravity hooks: https://antigravity.google/docs/hooks
- OpenCode MCP: https://opencode.ai/docs/mcp-servers/
- OpenCode plugins: https://opencode.ai/docs/plugins/
- Lovable GitHub sync: https://docs.lovable.dev/integrations/github
- Lovable custom MCP: https://docs.lovable.dev/integrations/custom-mcp
- CockroachDB AI: https://www.cockroachlabs.com/docs/stable/cockroachdb-and-ai
- CockroachDB vector indexes: https://www.cockroachlabs.com/docs/stable/vector-indexes
- CockroachDB Cloud MCP: https://www.cockroachlabs.com/docs/cockroachcloud/connect-to-the-cockroachdb-cloud-mcp-server
- Bedrock Converse: https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html
- Hermes compression: https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching
- Hermes memory provider: https://hermes-agent.nousresearch.com/docs/developer-guide/memory-provider-plugin
- Hermes hooks: https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks

## Research caveats

GitHub star counts and project capabilities change. Search results were used for discovery, and the linked repositories are the source of truth for their current implementation. No claims here imply that a project is production-ready merely because it exposes a feature in its README.
