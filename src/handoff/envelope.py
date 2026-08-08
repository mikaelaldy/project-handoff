"""Handoff envelope model shared by the MCP server, CLI, and adapters."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import uuid
from typing import Any, Dict, List, Optional, Sequence

_HANDOFF_SECTIONS = (
    "goal",
    "current_state",
    "completed",
    "decisions",
    "blockers",
    "files_and_artifacts",
    "validation",
    "next_action",
    "risks_and_cautions",
    "provenance",
)

_SECTION_ORDER = (
    "current_state",
    "completed",
    "decisions",
    "blockers",
    "validation",
    "next_action",
    "risks_and_cautions",
)

VALID_STATUSES = ("active", "paused", "blocked", "completed", "abandoned")

_SECRET_RE = re.compile(
    r"(?i)"
    r"(?:"
    r"(?:sk|pk|ghp|gho|ghs|AKIA|xox[baprs])[A-Za-z0-9_-]{6,}"
    r"|aws_[a-z]+_[A-Za-z0-9]{16,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|password[=:]\s*\S+"
    r"|token[=:]\s*\S+"
    r")"
)


def redact(text: str) -> str:
    if not text:
        return text
    return _SECRET_RE.sub("[REDACTED]", text)


def now_ms() -> int:
    import time

    return int(time.time() * 1000)


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ("" if value is None else str(value))


@dataclasses.dataclass
class Handoff:
    """Projection of unfinished work. Immutable after persistence."""

    id: str
    workstream_id: str
    project_id: str
    repository: str
    branch: str
    commit: str
    source_agent: str
    status: str
    goal: str
    sections: Dict[str, Any]
    files: List[str]
    created_ms: int
    updated_ms: int
    continues_from: Optional[str] = None
    embedding: Optional[Sequence[float]] = None

    @property
    def summary_text(self) -> str:
        parts = [self.goal or ""]
        for key in _HANDOFF_SECTIONS:
            value = _text(self.sections.get(key)).strip()
            if value:
                parts.append(value)
        return "\n".join(parts)

    def resume_payload(self, token_budget: int = 1400) -> str:
        """Bounded Markdown resume packet (1 token ~ 4 chars heuristic)."""
        blocks: List[tuple] = []

        def add(title: str, body: Any) -> None:
            body = _text(body).strip()
            if body:
                blocks.append((title, body))

        add("Goal", self.goal)
        for name in _SECTION_ORDER:
            add(name.replace("_", " ").title(), self.section(name))
        if self.files:
            add("Files and Artifacts", "\n".join(f"- {f}" for f in self.files))
        provenance = (
            f"- source agent: {self.source_agent}\n"
            f"- status: {self.status}\n"
            f"- repository: {self.repository} @ {self.commit}\n"
            f"- handoff id: {self.id}\n"
            f"- workstream: {self.workstream_id}\n"
            f"- created at: {self.created_ms}\n"
        )
        if self.continues_from:
            provenance += f"- continues: {self.continues_from}\n"
        add("Provenance", provenance)

        output: List[str] = []
        remaining = max(0, token_budget)
        for title, body in blocks:
            size = max(24, len(body) // 4)
            if title in ("Goal", "Provenance"):
                output.append(f"## {title}\n{body}")
                continue
            if size > remaining:
                output.append("... further context available on request")
                break
            remaining -= size
            output.append(f"## {title}\n{body}")
        return "\n\n".join(output)

    def section(self, name: str) -> str:
        return _text(self.sections.get(name))

    def as_dict(self) -> dict:
        return dict(
            id=self.id,
            workstream_id=self.workstream_id,
            project_id=self.project_id,
            repository=self.repository,
            branch=self.branch,
            commit=self.commit,
            source_agent=self.source_agent,
            status=self.status,
            goal=self.goal,
            sections={k: _text(v) for k, v in self.sections.items()},
            files=list(self.files),
            created_ms=self.created_ms,
            updated_ms=self.updated_ms,
            continues_from=self.continues_from,
        )


def new_handoff(
    project_id: str,
    repository: str,
    source_agent: str,
    goal: str,
    branch: str = "",
    commit: str = "",
    sections: Optional[Dict[str, Any]] = None,
    files: Optional[Sequence[str]] = None,
    workstream_id: Optional[str] = None,
    status: str = "active",
    continues_from: Optional[str] = None,
) -> Handoff:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status!r}")
    if not project_id or not repository or not source_agent:
        raise ValueError("project_id, repository and source_agent are required")
    hid = uuid.uuid4().hex[:16]
    ws = workstream_id or uuid.uuid4().hex[:16]
    now = now_ms()
    data: Dict[str, Any] = {"goal": _text(goal)}
    if sections:
        data.update({str(k): _text(v) for k, v in sections.items()})
    return Handoff(
        id=hid,
        workstream_id=ws,
        project_id=project_id,
        repository=repository,
        branch=redact(branch),
        commit=redact(commit),
        source_agent=source_agent,
        status=status,
        goal=_text(goal),
        sections=data,
        files=[redact(str(f)) for f in (files or [])],
        created_ms=now,
        updated_ms=now,
        continues_from=continues_from,
    )


def digest_record(record: Handoff) -> str:
    """Stable digest over canonical content, ignoring volatile ids and clocks."""
    data = {
        "project_id": record.project_id,
        "repository": record.repository,
        "branch": record.branch,
        "commit": record.commit,
        "source_agent": record.source_agent,
        "status": record.status,
        "goal": record.goal,
        "sections": {k: str(v) for k, v in sorted(record.sections.items())},
        "files": sorted(record.files),
    }
    return hashlib.sha256(
        json.dumps(data, sort_keys=True).encode()
    ).hexdigest()[:16]