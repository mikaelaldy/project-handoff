"""Vercel serverless function: live vector search backed by CockroachDB + Bedrock.

GET /api/playground?q=<query text>&agent=<source agent>

- Embeds the query (Bedrock when AWS creds are present; lexical fallback otherwise).
- Runs the vector-ranked resume query against the CockroachDB cluster.
- Returns the top handoff + its resume packet + real cosine distance.
- On any failure (no creds, DB down, missing rows) returns {"mode": "example"}
  so the frontend can render its static example with an honest label.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

PROJECT_ID = "mikaelaldy/project-handoff"
REPOSITORY = "mikaelaldy/project-handoff"
BRANCH = "main"
DEFAULT_QUERY = "How to query vector memory from CockroachDB"


def _example(reason: str) -> dict:
    return {"mode": "example", "reason": reason}


def run_playground(q: str, agent: str) -> dict:
    """Core logic, kept separate so it is testable outside the HTTP layer."""
    try:
        from handoff.embeddings import embedding_provider_from_env
        from handoff.storage import CockroachHandoffStore, ResumeQuery
    except Exception as exc:  # import-time guard (missing deps on cold start)
        return _example(f"import error: {type(exc).__name__}: {exc}")

    db_url = os.environ.get("HANDOFF_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        return _example("HANDOFF_DATABASE_URL not set")

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
                return _example(f"no active {agent or 'project'} handoff found")
            packet = top.resume_payload(token_budget=1400)
            return {
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
            }
        finally:
            store.close()
    except Exception as exc:  # boundary keeps the page alive for judges
        return _example(f"{type(exc).__name__}: {exc}")


class handler(BaseHTTPRequestHandler):
    """Vercel Python runtime entry point (BaseHTTPRequestHandler contract)."""

    def _send_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        q = (params.get("q", [""])[0] or "").strip()[:256] or DEFAULT_QUERY
        agent = (params.get("agent", [""])[0] or "").strip().lower()[:32]

        try:
            result = run_playground(q, agent)
            self._send_json(200, result)
        except Exception as exc:  # absolute last resort
            self._send_json(200, _example(f"{type(exc).__name__}: {exc}"))

    def do_OPTIONS(self):  # noqa: N802 - CORS preflight
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A002 - silence stderr logging
        pass
