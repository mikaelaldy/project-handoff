# Project Handoff

> Continue unfinished work with a different AI coding agent — powered by CockroachDB Cloud & AWS.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CockroachDB](https://img.shields.io/badge/Database-CockroachDB_Cloud-blue.svg)](https://www.cockroachlabs.com/cloud/)
[![AWS Bedrock](https://img.shields.io/badge/AI-Amazon_Bedrock-orange.svg)](https://aws.amazon.com/bedrock/)

**Project Handoff** is a vendor-neutral, open-source continuity layer for AI-assisted development. It captures the progress, decisions, blockers, and next actions of an unfinished coding task, embeds and indexes them in **CockroachDB Cloud** via **Amazon Bedrock**, and makes that context available to another AI agent through **MCP (Model Context Protocol)**.

Primary workflow demo:
> **Antigravity** (or Claude Code) stops → Handoff captures state & embeds via Bedrock → Saved in CockroachDB Vector Memory → **Codex** (or OpenCode) resumes seamlessly.

---

## 🏗 Architecture & Hackathon Integration

```
                                 +---------------------------------------+
                                 |          AI Coding Clients            |
                                 |  (Codex, Antigravity, OpenCode, etc.) |
                                 +-------------------+-------------------+
                                                     |
                                                     | MCP / CLI Hooks
                                                     v
                                 +---------------------------------------+
                                 |             Handoff Core              |
                                 |    (Envelope, Redaction, Budgeting)   |
                                 +---------+-------------------+---------+
                                           |                   |
                                           v                   v
+----------------------------------------------+   +----------------------------------------------+
|            CockroachDB Cloud Memory          |   |                 AWS Services                 |
|  - Managed MCP Server (Audit & Query)       |   |  - Amazon Bedrock (Titan Text Embeddings V2) |
|  - Distributed Vector Indexing (VECTOR 512)  |   |  - AWS Lambda (Async Checkpoint Processor)   |
+----------------------------------------------+   +----------------------------------------------+
                                           |
                                           +---> Local Fallback (SQLite + Lexical Embeddings)
```

### 🪳 CockroachDB Tools Used

| Tool | How it is used in Handoff |
| --- | --- |
| **Distributed Vector Indexing** | Stores `VECTOR(512)` embeddings generated for each task section. Uses `CREATE VECTOR INDEX` to perform fast approximate nearest-neighbor (ANN) similarity search across handoffs scoped by project and branch. |
| **Managed MCP Server** | Connects to `https://cockroachlabs.cloud/mcp` allowing AI agents to directly inspect live database schema and task state with full auditability. |

### ☁️ AWS Services Used

| Service | How it is used in Handoff |
| --- | --- |
| **Amazon Bedrock** | Invokes `amazon.titan-embed-text-v2:0` to convert task goals, status updates, decisions, and file paths into 512-dimensional normalized vector embeddings. |
| **AWS Lambda** | Runs asynchronous background worker (`src/handoff/aws/worker.py`) that processes lifecycle events and writes complete handoffs to CockroachDB. |

---

## ⚡ Quickstart

### 1. Prerequisites

- Python 3.11+
- CockroachDB Cloud database URL (`postgresql://...`)
- AWS CLI configured with active Bedrock permissions

### 2. Installation

```bash
git clone https://github.com/mikaelaldy/project-handoff.git
cd project-handoff
pip install -e '.[cockroach,aws,mcp,cli,test]'
```

### 3. Environment Setup

```bash
# Download CockroachDB CA Certificate
curl --create-dirs -o $HOME/.postgresql/root.crt 'https://cockroachlabs.cloud/clusters/<your-cluster-id>/cert'

# Export environment variables
export HANDOFF_DATABASE_URL="postgresql://<user>:<password>@<host>:26257/defaultdb?sslmode=verify-full"
export HANDOFF_EMBEDDING_PROVIDER="bedrock"
export AWS_REGION="us-east-1"
```

### 4. Running the Local Test Suite

Verify both local fallback and live cloud integrations:

```bash
pytest tests/ -v
```

---

## 🛠 Usage & Tool Surface

### Using via MCP Server

Add to your MCP-compatible client config (e.g. Codex or Claude Code):

```json
{
  "mcpServers": {
    "handoff": {
      "command": "handoff",
      "args": ["mcp-serve"]
    }
  }
}
```

#### Exposed MCP Tools:

1. **`handoff_checkpoint`**: Saves an active handoff (goal, state, decisions, blockers, files).
2. **`handoff_resume`**: Retrieves token-budgeted, vector-ranked handoffs for a project/branch.
3. **`handoff_get`**: Fetches full handoff by ID.
4. **`handoff_list`**: Lists workstreams by status.
5. **`handoff_complete`**: Marks a workstream finished so it drops out of the active resume list.

### Using via CLI

```bash
# Initialize schema
handoff init

# Save checkpoint from JSON payload
cat event.json | handoff checkpoint --event -

# Resume unfinished workstream
handoff resume --project "my-app" --repo "mikaelaldy/my-app" --branch "main"

# Complete workstream
handoff complete --workstream "<workstream-id>"
```

### Installing Agent Hooks

Auto-capture hooks for AI coding assistants:

```bash
handoff-hooks all
```
This generates:
- Codex hooks in `~/.codex/hooks.json` (`PreCompact`, `SessionEnd`)
- Antigravity hooks in `~/.gemini/config/hooks.json` (`Stop`, `PostInvocation`)
- OpenCode plugin in `~/.config/opencode/plugins/handoff.ts`

---

## 🔒 Security & Privacy

- Secret redaction runs automatically before persisting any handoff (API keys, tokens, SSH keys, passwords).
- Token-bounded resume payloads prevent prompt-injection bloat and context explosion.

---

## 📜 License

MIT License. See [LICENSE](LICENSE).
