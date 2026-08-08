# Architectural Specification

## Overview

Project Handoff is an agentic memory continuity layer. It ensures AI coding agents (Codex, Antigravity, OpenCode, Claude Code) can pass unfinished task state to one another with zero context loss and zero manual recap.

```text
+-----------------------------------------------------------------------------------+
|                                  AI CLIENT LAYER                                  |
|   Codex Hooks       Antigravity Hooks       OpenCode Plugin       Lovable Push   |
+------------------------------------------+----------------------------------------+
                                           |
                                           | MCP / Stdio / REST
                                           v
+-----------------------------------------------------------------------------------+
|                                   HANDOFF CORE                                    |
|   - Envelope Validation                                                           |
|   - Automatic Secret Redaction                                                    |
|   - Token Budgeting & Markdown Formatting                                         |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                                PERSISTENCE LAYER                                  |
|                                                                                   |
|  [PRIMARY CLOUD PATH]                                                             |
|  - CockroachDB Cloud: Distributed VECTOR(512) index with project scoping          |
|  - CockroachDB Managed MCP Server: Schema inspection & audited operations         |
|  - Amazon Bedrock: Titan Text Embeddings V2                                       |
|  - AWS Lambda: Asynchronous checkpoint worker                                     |
|                                                                                   |
|  [PORTABILITY / FALLBACK PATH]                                                    |
|  - SQLite + Lexical Hashing Embeddings                                            |
+-----------------------------------------------------------------------------------+
```

## Data Schema & Vector Memory

Handoff records use a PostgreSQL/CockroachDB schema:

```sql
CREATE TABLE IF NOT EXISTS handoffs (
    id            TEXT PRIMARY KEY,
    workstream_id TEXT NOT NULL,
    project_id    TEXT NOT NULL,
    repository    TEXT NOT NULL DEFAULT '',
    branch        TEXT NOT NULL DEFAULT '',
    commit        TEXT NOT NULL DEFAULT '',
    source_agent  TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'active',
    goal          TEXT NOT NULL DEFAULT '',
    sections      JSONB NOT NULL DEFAULT '{}'::JSONB,
    files         JSONB NOT NULL DEFAULT '[]'::JSONB,
    embedding     VECTOR(512),
    created_ms    BIGINT NOT NULL,
    updated_ms    BIGINT NOT NULL,
    continues_from TEXT
);

-- Compound index for scoped lookups
CREATE INDEX IF NOT EXISTS idx_handoffs_ws ON handoffs (workstream_id, updated_ms DESC);
CREATE INDEX IF NOT EXISTS idx_handoffs_proj ON handoffs (project_id, status, updated_ms DESC);

-- CockroachDB Distributed Vector Indexing
CREATE VECTOR INDEX IF NOT EXISTS idx_handoffs_vec ON handoffs (project_id, embedding);
```

## Key Invariants

1. **Immutability**: Each checkpoint creates a new handoff version linked via `continues_from`.
2. **Scoping**: Searches are strictly isolated by `project_id`, `repository`, and `branch`.
3. **Resilience**: If Amazon Bedrock or CockroachDB is unreachable, the system falls back gracefully to SQLite and deterministic hashing without crashing the host agent.
