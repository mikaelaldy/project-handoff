"""Seed the CockroachDB cluster with realistic demo handoffs for the landing
page playground. Uses the same worker path as production (process_checkpoint_event
-> Bedrock embedding -> CockroachDB insert), so the live playground queries
records that are indistinguishable from real ones.

Run:  HANDOFF_DATABASE_URL=... HANDOFF_EMBEDDING_PROVIDER=bedrock python -m scripts.seed_demo
Idempotent only per workstream: it creates NEW handoffs each run.
"""

import os
import sys

from handoff.aws.worker import process_checkpoint_event
from handoff.storage import CockroachHandoffStore

PROJECT_ID = "mikaelaldy/project-handoff"
REPOSITORY = "mikaelaldy/project-handoff"
BRANCH = "main"

EVENTS = [
    {
        "workstream_id": "ws-vector-memory",
        "source_agent": "antigravity",
        "goal": "Implement CockroachDB vector memory and Bedrock Titan V2 integration",
        "sections": {
            "current_state": "Verified live vector query execution against the CockroachDB cluster.",
            "next_action": "Execute Codex agent resume query and finalize submission evidence.",
            "decisions": "Use CockroachDB VECTOR(512) index with project_id prefix.",
        },
        "files": ["src/handoff/storage/cockroach.py", "src/handoff/embeddings.py"],
    },
    {
        "workstream_id": "ws-mcp-server",
        "source_agent": "opencode",
        "goal": "Build the MCP server exposing checkpoint and resume tools",
        "sections": {
            "current_state": "MCP server exposes checkpoint, resume, get, list, complete via stdio JSON-RPC.",
            "next_action": "Add session.idle plugin hook to OpenCode config.",
            "decisions": "Stdio transport only; no network listener for local-first security.",
        },
        "files": ["src/handoff/mcp_server.py"],
    },
    {
        "workstream_id": "ws-landing",
        "source_agent": "lovable",
        "goal": "Design the handoff landing page with live playground",
        "sections": {
            "current_state": "Light theme landing page deployed to Vercel with brand logos.",
            "next_action": "Seat real rows in CockroachDB so the live playground returns a real handoff.",
            "decisions": "Static site + one serverless function; no frontend framework.",
        },
        "files": ["web/index.html", "api/playground.py"],
    },
]


def main() -> None:
    db_url = os.environ.get("HANDOFF_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("set HANDOFF_DATABASE_URL")
    store = CockroachHandoffStore(database_url=db_url)
    store.open()
    try:
        for i, ev in enumerate(EVENTS):
            ev = {**ev, "type": "checkpoint", "project_id": REPOSITORY.replace("demo-", ""), "repository": REPOSITORY, "branch": BRANCH, "commit": f"seed{i+1}"}
            res = process_checkpoint_event(ev, store=store)
            print(f"seeded {ev['source_agent']:>10}  {res['handoff_id']}  dim={res['embedding_dim']}")
    finally:
        store.close()


if __name__ == "__main__":
    main()