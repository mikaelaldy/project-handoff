"""Pure helper functions used by the MCP server and CLI.

Kept free of MCP SDK imports so the CLI works without the optional
dependency and the logic can be tested directly.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .embeddings import embedding_provider_from_env
from .envelope import Handoff, new_handoff, redact
from .storage import HandoffStore, ResumeQuery, store_from_env


def do_checkpoint(args: Dict[str, Any], store: Optional[HandoffStore] = None) -> Dict[str, Any]:
    """Create and persist a checkpoint from an agent-provided payload."""
    store = store or store_from_env()
    embedder = embedding_provider_from_env()
    sections = {k: redact(str(v)) for k, v in (args.get("sections") or {}).items()}
    rec = new_handoff(
        project_id=args["project_id"],
        repository=args["repository"],
        source_agent=args["source_agent"],
        goal=redact(str(args.get("goal", ""))),
        branch=args.get("branch", ""),
        commit=args.get("commit", ""),
        sections=sections,
        files=[redact(f) for f in (args.get("files") or [])],
        workstream_id=args.get("workstream_id"),
        status=args.get("status", "active"),
    )
    text_for_embedding = "\n".join([rec.goal, *[str(v) for v in sections.values()], *rec.files])
    rec.embedding = embedder.embed(text_for_embedding)
    store.insert(rec)
    return {
        "ok": True,
        "handoff_id": rec.id,
        "workstream_id": rec.workstream_id,
        "embedding_provider": embedder.name,
    }


def do_resume(args: Dict[str, Any], store: Optional[HandoffStore] = None) -> list[Handoff]:
    store = store or store_from_env()
    embedding = None
    query_text = args.get("query_text", "")
    if query_text:
        embedding = embedding_provider_from_env().embed(query_text)
    query = ResumeQuery(
        project_id=args["project_id"],
        repository=args.get("repository", ""),
        branch=args.get("branch", ""),
        limit=int(args.get("limit", 1)),
        embedding=embedding,
    )
    return store.resume(query)


def do_get(handoff_id: str, store: Optional[HandoffStore] = None) -> Optional[Handoff]:
    store = store or store_from_env()
    return store.get(handoff_id)


def do_list(project_id: str, statuses=None, limit: int = 20, store: Optional[HandoffStore] = None) -> list[Handoff]:
    store = store or store_from_env()
    return store.list(project_id, statuses=statuses, limit=limit)


def do_complete(workstream_id: str, store: Optional[HandoffStore] = None) -> Optional[Handoff]:
    store = store or store_from_env()
    return store.complete(workstream_id)


def handoff_to_dict(rec: Handoff) -> Dict[str, Any]:
    return {
        "id": rec.id,
        "workstream_id": rec.workstream_id,
        "project_id": rec.project_id,
        "repository": rec.repository,
        "branch": rec.branch,
        "commit": rec.commit,
        "source_agent": rec.source_agent,
        "status": rec.status,
        "goal": rec.goal,
        "sections": {k: str(v) for k, v in rec.sections.items()},
        "files": list(rec.files),
        "created_ms": rec.created_ms,
        "updated_ms": rec.updated_ms,
        "continues_from": rec.continues_from,
    }