"""AWS Lambda worker for async checkpoint processing.

Receives a checkpoint or github event, produces an embedding, and persists a
handoff to the configured storage backend (CockroachDB primary, SQLite
fallback). The handler is intentionally thin; all logic lives in
process_checkpoint_event so it can be exercised without AWS.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from ..envelope import new_handoff, now_ms, redact
from ..embeddings import EmbeddingProvider, embedding_provider_from_env
from ..storage import store_from_env


def process_checkpoint_event(
    event: Dict[str, Any],
    store=None,
    embedder: Optional[EmbeddingProvider] = None,
) -> Dict[str, Any]:
    """Persist one checkpoint event. Returns a summary dict.

    event shape:
    {
      "type": "checkpoint" | "github_push",
      "project_id": "...",
      "repository": "...",
      "branch": "...",
      "commit": "...",
      "source_agent": "codex|antigravity|opencode|lovable|manual",
      "status": "active|paused|blocked",
      "goal": "...",
      "sections": {...},
      "files": [...],
      "workstream_id": "... (optional)",
      "event_id": "... (optional, for idempotency)"
    }
    """
    if store is None:
        store = store_from_env()
    if embedder is None:
        embedder = embedding_provider_from_env()

    event_type = event.get("type", "checkpoint")
    project_id = event.get("project_id")
    repository = event.get("repository") or "unknown"
    branch = event.get("branch") or ""
    commit = event.get("commit") or ""
    source_agent = event.get("source_agent") or "unknown"
    status = event.get("status") or "active"
    goal = event.get("goal") or ""
    sections = event.get("sections") or {}
    files = event.get("files") or []
    workstream_id = event.get("workstream_id")

    if not project_id:
        raise ValueError("project_id is required in checkpoint event")

    text_for_embedding = "\n".join(
        [goal, *[str(v) for v in sections.values()], *files]
    )
    embedding = embedder.embed(text_for_embedding)

    handoff = new_handoff(
        project_id=project_id,
        repository=repository,
        source_agent=source_agent,
        goal=redact(goal),
        branch=branch,
        commit=commit,
        sections={k: redact(str(v)) for k, v in sections.items()},
        files=[redact(f) for f in files],
        workstream_id=workstream_id,
        status=status,
    )
    handoff.embedding = embedding
    store.insert(handoff)

    return {
        "ok": True,
        "handoff_id": handoff.id,
        "workstream_id": handoff.workstream_id,
        "event_type": event_type,
        "embedding_provider": embedder.name,
        "embedding_dim": len(embedding),
        "created_ms": handoff.created_ms,
    }


def lambda_handler(event: Dict[str, Any], context=None) -> Dict[str, Any]:
    """AWS Lambda entry point. Environment:
    HANDOFF_DATABASE_URL / DATABASE_URL, HANDOFF_EMBEDDING_PROVIDER,
    HANDOFF_BEDROCK_EMBED_MODEL, AWS_REGION.
    """
    # Decode both direct calls and SNS/SQS envelopes so the same function
    # works behind EventBridge, SNS, or a direct invoke.
    if "Records" in event and isinstance(event["Records"], list):
        record = event["Records"][0]
        body = record.get("body") or record.get("Sns", {}).get("Message") or "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}
    else:
        payload = event
    try:
        result = process_checkpoint_event(payload)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as exc:  # pragma: no cover - defensive Lambda boundary
        return {"statusCode": 500, "body": json.dumps({"error": str(exc)})}