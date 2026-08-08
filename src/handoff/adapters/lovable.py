"""Lovable/GitHub ingestion: convert a GitHub push payload into a
project/repository checkpoint event.

Lovable continuously syncs to GitHub; the push event is the reliable
lifecycle boundary. Reasoning notes (decisions, why) are captured when the
Lovable agent writes an explicit Handoff MCP checkpoint; this module only
covers the Git evidence path, labelled as partial context.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .envelope import redact
from .storage import HandoffStore, store_from_env


def git_tracking_info(cwd: str) -> tuple[str, str]:
    """Best-effort branch + commit for a local checkout."""
    branch, commit = "", ""
    try:
        branch = subprocess.run(
            ["git", "-C", cwd, "branch", "--show-current"],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
    except Exception:
        pass
    try:
        commit = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
    except Exception:
        pass
    return branch, commit


def github_push_to_events(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Convert a GitHub push webhook payload into Handoff checkpoint events."""
    repo_full = (payload.get("repository") or {}).get("full_name") or "unknown"
    ref = payload.get("ref", "")
    branch = ref.split("/")[-1] if ref else ""
    events = []
    for commit in payload.get("commits") or []:
        events.append(
            {
                "type": "github_push",
                "project_id": payload.get("repository", {}).get("name") or repo_full,
                "repository": repo_full,
                "branch": branch,
                "commit": commit.get("id", ""),
                "source_agent": "lovable",
                "status": "active",
                "goal": commit.get("message", "GitHub push from Lovable"),
                "sections": {"current_state": "Code synchronized by Lovable to repository."},
                "files": commit.get("modified", [])
                + commit.get("added", [])
                + commit.get("removed", []),
            }
        )
    return events


def ingest_lovable_push(
    payload: Dict[str, Any],
    store: Optional[HandoffStore] = None,
) -> int:
    """Persist all commits in a push; returns count stored."""
    if store is None:
        store = store_from_env()
    events = github_push_to_events(payload)
    for event in events:
        from .worker import process_checkpoint_event  # avoid import cycle

        process_checkpoint_event(event, store=store)
    return len(events)


def github_to_checkpoint(cwd: str) -> Dict[str, Any]:
    """Build a single checkpoint event from a local git checkout."""
    branch, commit = gitlab_tracking_info(cwd)
    return {
        "type": "git_checkpoint",
        "project_id": Path(cwd).name,
        "repository": Path(cwd).name,
        "branch": branch,
        "commit": commit,
        "source_agent": os.getenv("HANDOFF_SOURCE_AGENT", "git"),
        "status": "active",
        "goal": "Working tree snapshot (no explicit agent notes)",
        "sections": {"current_state": "Local repository state captured via git."},
        "files": changed := [],
    }