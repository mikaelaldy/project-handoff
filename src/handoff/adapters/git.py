"""Git based capture adapters (Lovable/GitHub path).

Lovable syncs code to a GitHub repository. The Git path is the reliable
automatic trigger; explicit reasoning checkpoints come via the MCP server
with an agent-note payload. This module turns Git and webhook evidence into
Handoff events and labels them as partial context when no agent notes are
present.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..aws.worker import process_checkpoint_event
from ..storage import HandoffStore, store_from_env


def local_tracking_info(cwd: str) -> tuple:
    branch = ""
    commit = ""
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


def github_push_to_events(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert a GitHub push webhook payload into Handoff checkpoint events."""
    repo = payload.get("repository") or {}
    full_name = repo.get("full_name") or "unknown"
    ref = payload.get("ref", "")
    branch = ref.rsplit("/", 1)[-1] if ref else ""
    events: List[Dict[str, Any]] = []
    for commit in payload.get("commits") or []:
        files = list(commit.get("modified") or []) + list(commit.get("added") or [])
        events.append(
            {
                "type": "github_push",
                "project_id": full_name,
                "repository": full_name,
                "branch": branch,
                "commit": commit.get("id", ""),
                "source_agent": "lovable",
                "status": "active",
                "goal": commit.get("message", "GitHub push from Lovable"),
                "sections": {
                    "current_state": "Code pushed to repository; agent notes not captured.",
                    "validation": "Push event only (Git evidence).",
                },
                "files": files,
            }
        )
    return events


def git_checkpoint(cwd: str) -> Dict[str, Any]:
    """Build a single checkpoint event from a local git checkout."""
    branch, commit = local_tracking_info(cwd)
    return {
        "type": "git_checkpoint",
        "project_id": Path(cwd).name,
        "repository": Path(cwd).name,
        "branch": branch,
        "commit": commit,
        "source_agent": "git",
        "status": "active",
        "goal": "Repository state captured via git",
        "sections": {"current_state": "No explicit agent notes available."},
        "files": [],
    }


def ingest_push(payload: Dict[str, Any], store=None) -> int:
    """Persist all commits in a push payload. Returns number stored."""
    if store is None:
        store = store_from_env()
    count = 0
    for event in github_push_to_events(payload):
        process_checkpoint_event(event, store=store)
        count += 1
    return count