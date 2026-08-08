# Handoff

> Continue unfinished work with a different AI coding agent.

Handoff is a vendor-neutral, open-source continuity layer for AI-assisted development. It captures the useful state of an unfinished coding task, compresses it into a bounded handoff, and makes that context available to another agent.

The primary workflow is:

> Antigravity stops → Handoff saves the work → Codex continues.

The same core is intended to support OpenCode and Lovable through adapters.

## What Handoff is

Handoff is:

- An MCP server that exposes save, resume, and search tools
- A project- and Git-aware task ledger
- An automatic session summarizer inspired by Hermes-style context compression
- A portable handoff format that works across agents
- A local-first product with optional cloud deployment

Handoff is not:

- A replacement for OpenCode, Codex, Antigravity, or Lovable
- A new coding agent
- A general-purpose chatbot memory database
- A system that promises to recover context it never received

## MVP

The MVP solves one problem:

> When an AI coding agent stops before finishing, another agent can continue without starting over.

First-class adapter targets:

- Codex
- Antigravity
- OpenCode
- Lovable through GitHub sync and explicit MCP checkpoints

The first judging path is Antigravity → Codex. Lovable → OpenCode is a secondary product example.

## Hackathon mode

During the CockroachDB × AWS hackathon:

- CockroachDB Cloud is the durable memory backend.
- CockroachDB Distributed Vector Indexing powers similar-task retrieval.
- The CockroachDB Cloud Managed MCP Server provides an audited database access surface.
- Amazon Bedrock extracts compact handoff state and creates embeddings.
- AWS Lambda runs background processing after checkpoints and GitHub events.

After the hackathon, the core remains usable with SQLite, local files, Ollama, and other OpenAI-compatible providers.

## Project status

Planning only. This repository intentionally contains specifications and research first. Implementation starts only after the plan is reviewed.

## Planned docs

- [Concept](docs/concept.md)
- [Architecture](docs/architecture.md)
- [Memory and handoff model](docs/memory-model.md)
- [Integration strategy](docs/integrations.md)
- [Hackathon requirements](docs/hackathon-requirements.md)
- [Roadmap](docs/roadmap.md)
- [Research and prior art](research/prior-art.md)

## License

MIT. See [LICENSE](LICENSE).

## Research note

The architecture was informed by official Codex, Antigravity, OpenCode, Lovable, MCP, CockroachDB, AWS, and Hermes documentation, plus unrelated open-source projects listed in [research/prior-art.md](research/prior-art.md).

Current hackathon submissions were intentionally excluded from the prior-art research.
