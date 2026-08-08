"""Database-agnostic storage interface for handoff records."""

from __future__ import annotations

import abc
import dataclasses
import json
import re
from typing import List, Optional, Sequence

from .envelope import Handoff, VALID_STATUSES, new_handoff


@dataclasses.dataclass
class ResumeQuery:
    project_id: str
    repository: str = ""
    branch: str = ""
    statuses: Sequence[str] = ("active", "paused", "blocked")
    limit: int = 1
    query_text: str = ""
    embedding: Optional[Sequence[float]] = None

    def filters(self) -> str:
        parts = [f"project_id = {self.project_id!r}"]
        if self.repository:
            parts.append(f"repository = {self.repository!r}")
        if self.branch:
            parts.append(f"branch = {self.branch!r}")
        parts.append(f"status IN ({','.join('(? )' for _ in self.statuses)})")
        return " AND ".join(parts)


class HandoffStore:
    """Interface shared by CockroachDB and SQLite adapters.

    Each row maps to a immutable Handoff record. ``save`` replaces the row for
    the same record id, so corrections create a new row with a new id and
    link back via ``continues_from``.
    """

    name = "base"

    # -- lifecycle --------------------------------------------------------
    def save(self, record: Handoff) -> Handoff:
        """Insert a handoff with a deterministic UI assertion on idempotency."""
        raise NotImplementedError

    def update_progress(
        self,
        workstream_id: str,
        status: str,
        next_action: str,
        commit: str = "",
    ) -> Optional[Handoff]:
        """Create a new version of the workstream's latest handoff."""
        raise NotImplementedError

    def complete(self, workstream_id: str, commit: str = "") -> Optional[Handoff]:
        """Mark the latest workstream handoff as completed."""
        raise NotImplementedError

    # -- retrieval --------------------------------------------------------
    def resume(self, query: ResumeQuery) -> List[Handoff]:
        """Return unfinished handoffs for a project, ordered newest first."""
        raise NotImplementedError

    def get(self, handoff_id: str) -> Optional[Handoff]:
        raise NotImplementedError

    def list(
        self,
        project_id: str,
        statuses: Optional[Sequence[str]] = None,
        limit: int = 20,
    ) -> List[Handoff]:
        raise NotImplementedError

    # -- schema ------------------------------------------------------------
    def create_schema(self) -> None:
        """Create tables/indexes if absent. Idempotent."""
        raise NotImplementedError

    def close(self) -> None:
        pass


def _fmt(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(f"{v!r}" for v in value) + "]"
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def _parse_sections(raw) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _parse_files(raw) -> list:
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
            return value if isinstance(value, list) else []
        except Exception:
            return []
    return list(raw or [])


def record_from_row(row, section_key) -> Handoff:
    """Row is a dict with keys: id, workstream_id, project_id, repository,
    branch, commit, source_agent, status, goal, sections, files,
    created_ms, updated_ms, continues_from."""
    return Handoff(
        id=row["id"],
        workstream_id=row["workstream_id"],
        project_id=row["project_id"],
        repository=row["repository"],
        branch=row["branch"],
        commit=row["commit"],
        source_agent=row["source_agent"],
        status=row["status"],
        goal=_fmt(row["goal"]),
        sections=_parse_sections(row.get(section_names) or row.get("sections")),
        files=_parse_files(row.get("files")),
        created_ms=row["created_ms"],
        updated_ms=row["updated_ms"],
        continues_from=row.get("continues_from"),
    )


class _MemoryOPTIONSRecordStore(HandoffStore):
    """Pure-Python SQLite-backed store for tests and local fallback.

    This is not a gimmick: it is the vendor-neutral fallback mode documented
    in the architecture guide. The CockroachDB adapter shares this same
    interface, so any fallback path exercises the identical lifecycle logic.
    """

    name = "sqlite"

    def __init__(self, path: str = ":memory:"):
        import sqlite3

        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")

    @staticmethod
    def _select() -> str:
        return (
            "SELECT id, workstream_id, project_id, repository, branch, commit, "
            "source_agent, status, goal, sections, files, created_ms, updated_ms, "
            "continues_from FROM handoffs"
        )

    def create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS handoffs (
                id TEXT PRIMARY KEY,
                workstream_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                repository TEXT NOT NULL,
                branch TEXT NOT NULL DEFAULT '',
                commit TEXT NOT NULL DEFAULT '',
                source_agent TEXT NOT NULL,
                status TEXT NOT NULL,
                goal TEXT NOT NULL,
                sections TEXT NOT NULL DEFAULT '{}',
                files TEXT NOT NULL DEFAULT '[]',
                created_ms INTEGER NOT NULL,
                updated_ms INTEGER NOT NULL,
                continues_from TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_handoffs_project_status
                ON handoffs (project_id, status, updated_ms DESC);
            """
        )
        self._conn.commit()

    def open(self) -> None:
        self.create_schema()

    def insert(self, record: Handoff) -> Handoff:
        self._conn.execute(
            "INSERT INTO handoffs "
            "(id, workstream_id, project_id, repository, branch, commit, "
            " source_agent, status, goal, sections, files, created_ms, updated_ms, continues_from) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                record.id,
                record.workstream_id,
                record.project_id,
                record.repository,
                record.branch,
                record.commit,
                record.source_agent,
                record.status,
                record.goal,
                json.dumps(record.sections, sort_keys=True),
                json.dumps(record.files),
                record.created_ms,
                record.updated_ms,
                record.continues_from,
            ),
        )
        self._conn.commit()
        return record

    def update_progress(
        self,
        workstream_id: str,
        status: str,
        sections: Optional[dict] = None,
        commit: str = "",
    ) -> Optional[Handoff]:
        latest = self._latest(workstream_id)
        if latest is None:
            return None
        merged = dict(latest.sections)
        if sections:
            merged.update({k: _fmt(v) for k, v in sections.items()})
        now = _ms()
        rec = new_handoff(
            project_id=latest.project_id,
            repository=latest.repository,
            branch=latest.branch,
            commit=commit or latest.commit,
            source_agent=latest.source_agent,
            goal=latest.goal,
            sections=merged,
            files=latest.files,
            workstream_id=latest.workstream_id,
            status=status if status in VALID_STATUSES else latest.status,
            continues_from=latest.id,
        )
        rec.created_ms = latest.created_ms
        rec.updated_ms = now
        return self.insert(rec)

    def complete(self, workstream_id: str, commit: str = "") -> Optional[Handoff]:
        return self.update_progress(workstream_id, "completed", commit=commit)

    def resume(self, query: ResumeQuery) -> List[Handoff]:
        statuses = tuple(query.statuses or VALID_STATUSES)
        sql = (
            "SELECT * FROM handoffs WHERE project_id = ?"
            + (" AND repository = ?" if query.repository else "")
            + (" AND branch = ?" if query.branch else "")
            + f" AND status IN ({','.join('?' * len(statuses))})"
            + " ORDER BY updated_ms DESC LIMIT ?"
        )
        params = [query.project_id]
        if query.repository:
            params.append(query.repository)
        if query.branch:
            params.append(query.branch)
        params += list(statuses) + [query.limit]
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get(self, handoff_id: str) -> Optional[Handoff]:
        row = self._conn.execute(
            "SELECT * FROM handoffs WHERE id = ?", (handoff_id,)
        ).fetchone()
        return self._row_to_record(row) if row else None

    def list(self, project_id: str, statuses=None, limit=20) -> List[Handoff]:
        if statuses is None:
            statuses = VALID_STATUSES
        qs = ",".join("?" * len(statuses))
        rows = self._conn.execute(
            f"SELECT * FROM handoffs WHERE project_id = ? AND status IN ({qs}) "
            "ORDER BY updated_ms DESC LIMIT ?",
            [project_id, *statuses, limit],
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def _latest(self, workstream_id: str) -> Optional[Handoff]:
        row = self._conn.execute(
            "SELECT * FROM handoffs WHERE workstream_id = ? "
            "ORDER BY updated_ms DESC LIMIT 1",
            (workstream_id,),
        ).fetchone()
        return self._row_to_record(row) if row else None

    @staticmethod
    def _row_to_record(row) -> Handoff:
        return Handoff(
            id=row["id"],
            workstream_id=row["workstream_id"],
            project_id=row["project_id"],
            repository=row["repository"],
            branch=row["branch"],
            commit=row["commit"],
            source_agent=row["source_agent"],
            status=row["status"],
            goal=row["goal"],
            sections=json.loads(row["sections"] or "{}"),
            files=json.loads(row["files"] or "[]"),
            created_ms=row["created_ms"],
            updated_ms=row["updated_ms"],
            continues_from=row["continues_from"],
        )

    def close(self) -> None:
        self._conn.close()