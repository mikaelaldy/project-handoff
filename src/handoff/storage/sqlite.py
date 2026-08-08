"""SQLite adapter: the vendor-neutral fallback mode.

Implements the identical interface as the CockroachDB adapter so the MCP
server, CLI, and AWS worker share one code path. Embeddings are stored as
JSON text and ranked by cosine at read time (small local corpus).

Selecting the backend:

    HANDOFF_DATABASE_URL=<cockroachdb url>  -> CockroachDB (primary)
    otherwise                                -> SQLite (fallback / dev)
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from typing import Any, Dict, List, Optional, Sequence

from ..envelope import VALID_STATUSES, Handoff, new_handoff, redact
from .cockroach import CockroachHandoffStore

__all__ = ["HandoffStore", "ResumeQuery", "SqliteHandoffStore", "CockroachHandoffStore", "store_from_env"]


class HandoffStore:
    """Interface shared by the CockroachDB and SQLite adapters.

    Records are immutable; progress writes a new version chained via
    ``continues_from``.
    """

    name = "base"

    def open(self) -> None: ...
    def insert(self, record: Handoff) -> None: ...
    def update_progress(self, workstream_id: str, status: str, sections: Optional[Dict[str, Any]] = None, commit: str = "", branch: str = "") -> Optional[Handoff]: ...
    def complete(self, workstream_id: str, commit: str = "") -> Optional[Handoff]: ...
    def resume(self, query: "ResumeQuery") -> list[Handoff]: ...
    def get(self, handoff_id: str) -> Optional[Handoff]: ...
    def list(self, project_id: str, statuses: Optional[Sequence[str]] = None, limit: int = 20) -> list[Handoff]: ...
    def close(self) -> None: ...


class ResumeQuery:
    def __init__(
        self,
        project_id: str,
        repository: str = "",
        branch: str = "",
        statuses: Sequence[str] = ("active", "paused", "blocked"),
        limit: int = 1,
        query_text: str = "",
        embedding: Optional[Sequence[float]] = None,
    ):
        self.project_id = project_id
        self.repository = repository
        self.branch = branch
        self.statuses = list(statuses or VALID_STATUSES[:3])
        self.limit = limit
        self.query_text = query_text
        self.embedding = embedding


def _std_vector(v: Sequence[float]) -> list[float]:
    return [float(x) for x in v]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return -1.0
    return dot / (na * nb)


class SqliteHandoffStore(HandoffStore):
    name = "sqlite"

    def __init__(self, path: str = ":memory:"):
        self.path = path
        self._conn: Optional[sqlite3.Connection] = None

    def open(self) -> None:
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS handoffs (
                id             TEXT PRIMARY KEY,
                workstream_id  TEXT NOT NULL,
                project_id     TEXT NOT NULL,
                repository     TEXT NOT NULL DEFAULT '',
                branch         TEXT NOT NULL DEFAULT '',
                "commit"         TEXT NOT NULL DEFAULT '',
                source_agent   TEXT NOT NULL DEFAULT '',
                status         TEXT NOT NULL DEFAULT 'active',
                goal           TEXT NOT NULL DEFAULT '',
                sections       TEXT NOT NULL DEFAULT '{}',
                files          TEXT NOT NULL DEFAULT '[]',
                embedding      TEXT,
                created_ms     INTEGER NOT NULL,
                updated_ms     INTEGER NOT NULL,
                continues_from TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_ws ON handoffs (workstream_id, updated_ms DESC);
            CREATE INDEX IF NOT EXISTS idx_proj ON handoffs (project_id, status, updated_ms DESC);
            """
        )
        self._conn.commit()

    def _require(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("store not open")
        return self._conn

    def insert(self, record: Handoff) -> None:
        conn = self._require()
        conn.execute(
            "INSERT OR REPLACE INTO handoffs "
            "(id, workstream_id, project_id, repository, branch, \"commit\", source_agent, "
            " status, goal, sections, files, embedding, created_ms, updated_ms, continues_from) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                record.id,
                record.workstream_id,
                record.project_id,
                record.repository,
                redact(record.branch),
                redact(record.commit),
                record.source_agent,
                record.status,
                record.goal,
                json.dumps(record.sections, sort_keys=True),
                json.dumps(record.files),
                json.dumps(list(record.embedding)) if record.embedding else None,
                record.created_ms,
                record.updated_ms,
                record.continues_from,
            ),
        )
        conn.commit()

    def _row(self, row: Optional[sqlite3.Row]) -> Optional[Handoff]:
        if row is None:
            return None
        emb = None
        if row["embedding"]:
            try:
                emb = json.loads(row["embedding"])
            except Exception:
                emb = None
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
            embedding=emb,
        )

    def _base_where(self, query: ResumeQuery) -> tuple[str, list[Any]]:
        clauses = ["project_id = ?"]
        params: list[Any] = [query.project_id]
        if query.repository:
            clauses.append("repository = ?")
            params.append(query.repository)
        if query.branch:
            clauses.append("branch = ?")
            params.append(query.branch)
        statuses = list(query.statuses or VALID_STATUSES[:3])
        clauses.append(f"status IN ({','.join('?' * len(statuses))})")
        params.extend(statuses)
        return " AND ".join(clauses), params

    def resume(self, query: ResumeQuery) -> list[Handoff]:
        conn = self._require()
        where, params = self._base_where(query)
        params.append(query.limit)
        # Only the newest handoff of each workstream is resumable, and only
        # when that newest version is itself unfinished. Older active records
        # are history, not live work.
        rows = conn.execute(
            f"""
            SELECT h.* FROM handoffs h
            JOIN (
                SELECT workstream_id, MAX(updated_ms) AS m FROM handoffs
                WHERE {where}
                GROUP BY workstream_id
            ) latest ON latest.workstream_id = h.workstream_id
                AND h.updated_ms = latest.m
            WHERE h.status IN ('active','paused','blocked')
              AND NOT EXISTS (
                SELECT 1 FROM handoffs done
                WHERE done.workstream_id = h.workstream_id
                  AND done.status = 'completed'
              )
            ORDER BY h.updated_ms DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        out: List[Handoff] = []
        for r in rows:
            rec = self._row(r)
            if rec is not None:
                out.append(rec)
        if query.embedding:
            qv = _std_vector(query.embedding)
            scored = []
            for h in out:
                if h.embedding:
                    scored.append((_cos(qv, _std_vector(h.embedding)), h))
                else:
                    scored.append((-2.0, h))
            scored.sort(key=lambda x: x[0], reverse=True)
            out = [h for _, h in scored]
        return out

    def update_progress(
        self,
        workstream_id: str,
        status: str,
        sections: Optional[Dict[str, Any]] = None,
        commit: str = "",
        branch: str = "",
    ) -> Optional[Handoff]:
        conn = self._require()
        row = conn.execute(
            "SELECT * FROM handoffs WHERE workstream_id = ? ORDER BY updated_ms DESC LIMIT 1",
            (workstream_id,),
        ).fetchone()
        latest = self._row(row)
        if latest is None:
            return None
        merged = dict(latest.sections)
        if sections:
            merged.update({str(k): str(v) for k, v in sections.items()})
        rec = new_handoff(
            project_id=latest.project_id,
            repository=latest.repository,
            source_agent=latest.source_agent,
            goal=latest.goal,
            branch=branch or latest.branch,
            commit=commit or latest.commit,
            sections=merged,
            files=latest.files,
            workstream_id=latest.workstream_id,
            status=status,
            continues_from=latest.id,
        )
        rec.created_ms = latest.created_ms
        rec.embedding = latest.embedding
        self.insert(rec)
        return rec

    def complete(self, workstream_id: str, commit: str = "") -> Optional[Handoff]:
        return self.update_progress(workstream_id, "completed", commit=commit)

    def get(self, handoff_id: str) -> Optional[Handoff]:
        conn = self._require()
        row = conn.execute("SELECT * FROM handoffs WHERE id = ?", (handoff_id,)).fetchone()
        return self._row(row)

    def list(self, project_id: str, statuses: Optional[Sequence[str]] = None, limit: int = 20) -> list[Handoff]:
        conn = self._require()
        statuses = list(statuses or VALID_STATUSES)
        placeholders = ",".join("?" * len(statuses))
        rows = conn.execute(
            f"SELECT * FROM handoffs WHERE project_id = ? AND status IN ({placeholders}) "
            "ORDER BY updated_ms DESC LIMIT ?",
            [project_id, *statuses, limit],
        ).fetchall()
        out: List[Handoff] = []
        for r in rows:
            rec = self._row(r)
            if rec is not None:
                out.append(rec)
        return out

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()


def store_from_env(database_url: Optional[str] = None) -> HandoffStore:
    """Select the primary backend from the environment.

    CockroachDB wins when a database URL is provided or set; otherwise the
    SQLite fallback is used (documented portability/failure mode).
    """
    url = database_url or os.getenv("HANDOFF_DATABASE_URL") or os.getenv("DATABASE_URL")
    if url:
        store = CockroachHandoffStore(url)
    else:
        store = SqliteHandoffStore(os.getenv("HANDOFF_SQLITE_PATH", ":memory:"))
    store.open()
    return store


def _cos(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        return -2.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-12
    nb = math.sqrt(sum(y * y for y in b)) or 1e-12
    return dot / (na * nb)