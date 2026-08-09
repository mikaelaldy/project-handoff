"""Vercel serverless function: live vector search backed by CockroachDB + Bedrock."""

import json
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from handoff.aws.worker import process_checkpoint_event  # noqa: E402
from handoff.embeddings import embedding_provider_from_env  # noqa: E402
from handoff.storage import CockroachHandoffStore, ResumeQuery  # noqa: E402

PROJECT_ID = "mikaelaldy/project-handoff"
REPOSITORY = "mikaelaldy/project-handoff"
BRANCH = "main"
DEFAULT_QUERY = "How to query vector memory from CockroachDB"


def _cors(headers=None):
    h = {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
    if headers:
        h.update(headers)
    return h


def _json(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": _cors(), "body": json.dumps(body)}


def _example_response(reason: str) -> dict:
    return _json(200, {"mode": "example", "reason": reason})


def handler(event, context=None) -> dict:
    params = event.get("queryStringParameters") or {}
    q = (params.get("q") or "").strip()[:256] or DEFAULT_QUERY
    agent = (params.get("agent") or "").strip().lower()[:32]

    db_url = os.environ.get("HANDOFF_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        return _example_response("HANDOFF_DATABASE_URL not set")

    try:
        store = CockroachHandoffStore(database_url=db_url)
        store.open()
        try:
            embedder = embedding_provider_from_env()
            rows = store.resume(
                ResumeQuery(
                    project_id=PROJECT_ID,
                    repository=REPOSITORY,
                    branch=BRANCH,
                    query_text=q,
                    embedding=embedder.embed(q),
                    limit=10,
                )
            )
            top = next((r for r in rows if not agent or r.source_agent == agent), None)
            if top is None:
                return _example_response(
                    f"no active {agent or 'project'} handoff found"
                )
            packet = top.resume_payload(token_budget=1400)
            return _json(
                200,
                {
                    "mode": "live",
                    "embedding_provider": embedder.name,
                    "query": q,
                    "agent": top.source_agent,
                    "handoff_id": top.id,
                    "status": top.status,
                    "goal": top.goal,
                    "packet": packet,
                    "packet_tokens": max(1, len(packet) // 4),
                    "budget": 1400,
                    "cosine": round(top.cosine, 3) if top.cosine is not None else None,
                },
            )
        finally:
            store.close()
    except Exception as exc:  # pragma: no cover - boundary keeps page alive
        return _json(
            200,
            {"mode": "example", "reason": f"{type(exc).__name__}: {exc}"},
        )
