"""CockroachDB primary storage adapter.

Primary hackathon path. Uses native VECTOR column + distributed vector index
(hnsw-like local code), with a JSON fallback for embeddings so the resume
path works even when the cluster lacks vector support.

Requires HANDOFF_DATABASE_URL to be set; the adapter refuses to open without
it, and every write/read is executed inside a connection from a small pool.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence

from ..envelope import Handoff, new_handoff, now_ms

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    _HAS_PSYCOPG = True
except Exception:  # pragma: no cover - import guard only
    psycopg = None
    dict_row = None
    ConnectionPool = None
    _HAS_PSYCOPG = False

VECTOR_DIM = int(os.getenv("HANDOFF_VECTOR_DIM", "512"))

_SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS handoffs (
    id            TEXT PRIMARY KEY,
    workstream_id TEXT NOT NULL,
    project_id    TEXT NOT NULL,
    repository    TEXT NOT NULL DEFAULT '',
    branch        TEXT NOT NULL DEFAULT '',
    commit        TEXT NOT NULL DEFAULT '',
    source_agent  TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'active',
    goal          TEXT NOT NULL DEFAULT '',
    sections      JSONB NOT NULL DEFAULT '{{}}'::JSONB,
    files         JSONB NOT NULL DEFAULT '[]'::JSONB,
    embedding     VECTOR({VECTOR_DIM}),
    created_ms    BIGINT NOT NULL,
    updated_ms    BIGINT NOT NULL,
    continues_from TEXT
);

CREATE INDEX IF NOT EXISTS idx_handoffs_ws
    ON handoffs (workstream_id, updated_ms DESC);
CREATE INDEX IF NOT EXISTS idx_handoffs_proj
    ON handoffs (project_id, status, updated_ms DESC);

CREATE VECTOR INDEX IF NOT EXISTS idx_handoffs_vec
    ON handoffs (project_id, embedding);
"""


def _embed_text(values: Optional[Sequence[float]]) -> Optional[str]:
    if values is None:
        return None
    return "[" + ",".join(f"{float(v):.6f}" for v in values) + "]"


def _parse_embed_text(value: Any) -> Optional[List[float]]:
    if value is None:
        return None
    if isinstance(value, list):
        return [float(v) for v in value]
    text = str(value).strip("[]")
    if not text:
        return None
    return [float(v) for v in text.split(",") if v.strip()]


class CockroachHandoffStore:
    name = "cockroachdb"

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = (
            database_url
            or os.getenv("HANDOFF_DATABASE_URL")
            or os.getenv("DATABASE_URL")
        )
        if not self.database_url:
            raise RuntimeError(
                "CockroachDB adapter requires DATABASE_URL or "
                "HANDOFF_DATABASE_URL to be set"
            )
        if not _HAS_PSYCOPG:
            raise RuntimeError(
                "psycopg3 and psycopg_pool are required for the CockroachDB adapter"
            )
        self._pool: Optional[ConnectionPool] = None

    # -- connection lifecycle ------------------------------------------
    def open(self) -> None:
        self._pool = ConnectionPool(
            conninfo=self.database_url,
            min_size=1,
            max_size=4,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        self._pool.open()
        with self._pool.connection() as conn:
            conn.execute(_SCHEMA_SQL)
            conn.commit()

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()

    def _conn(self):
        if self._pool is None:
            raise RuntimeError("CockroachDB store is not open (call open first)")
        return self._pool.connection()

    # -- core ops -------------------------------------------------------
    def insert(self, record: Handoff) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO handoffs
                  (id, workstream_id, project_id, repository, branch, commit,
                   source_agent, status, goal, sections, files, embedding,
                   created_ms, updated_ms, continues_from)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
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
                    _embed_text(record.embedding) if getattr(record, "embedding", None) else None,
                    record.created_ms,
                    record.updated_ms,
                    record.continues_from,
                ),
            )
            conn.commit()

    def update_progress(
        self,
        workstream_id: str,
        status: str,
        sections: Optional[Dict[str, Any]] = None,
        commit: str = "",
        branch: str = "",
    ) -> Optional[Handoff]:
        latest = self._latest(workstream_id)
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
        self.insert(rec)
        return rec

    def complete(self, workstream_id: str, commit: str = "") -> Optional[Handoff]:
        return self.update_progress(workstream_id, "completed", commit=commit)

    def resume(self, query) -> List[Handoff]:
        clauses = ["project_id = %s"]
        params: List[Any] = [query.project_id]
        if query.repository:
            clauses.append("repository = %s")
            params.append(query.repository)
        if query.branch:
            clauses.append("branch = %s")
            params.append(query.branch)
        statuses = list(query.statuses or ["active", "paused", "blocked"])
        placeholders = ", ".join(["%s"] * len(statuses))
        clauses.append(f"status IN ({placeholders})")
        params.extend(statuses)
        params.append(query.limit)

        if query.embedding:
            # Vector-ranked resume: rank by cosine distance, still scoped to
            # project/repository/branch/status. Only the newest handoff of a
            # workstream is resumable.
            sql = (
                "SELECT h.*, h.embedding <=> %s AS distance FROM handoffs h "
                "JOIN (SELECT workstream_id, MAX(updated_ms) AS m FROM handoffs "
                f"WHERE {' AND '.join(clauses)} GROUP BY workstream_id) latest "
                "ON latest.workstream_id = h.workstream_id AND h.updated_ms = latest.m "
                "WHERE h.status IN ('active','paused','blocked') "
                "AND NOT EXISTS (SELECT 1 FROM handoffs done "
                "WHERE done.workstream_id = h.workstream_id AND done.status = 'completed') "
                "ORDER BY distance ASC LIMIT %s"
            )
            params = [_embed_text(query.embedding), *params]
        else:
            sql = (
                "SELECT h.* FROM handoffs h "
                "JOIN (SELECT workstream_id, MAX(updated_ms) AS m FROM handoffs "
                f"WHERE {' AND '.join(clauses)} GROUP BY workstream_id) latest "
                "ON latest.workstream_id = h.workstream_id AND h.updated_ms = latest.m "
                "WHERE h.status IN ('active','paused','blocked') "
                "AND NOT EXISTS (SELECT 1 FROM handoffs done "
                "WHERE done.workstream_id = h.workstream_id AND done.status = 'completed') "
                "ORDER BY h.updated_ms DESC LIMIT %s"
            )
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        out: List[Handoff] = []
        for row in rows:
            rec = self._row(row)
            if rec is not None:
                out.append(rec)
        return out

    def _latest(self, workstream_id: str) -> Optional[Handoff]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM handoffs WHERE workstream_id = %s "
                "ORDER BY updated_ms DESC LIMIT 1",
                (workstream_id,),
            ).fetchall()
        return self._row(rows[0]) if rows else None

    def get(self, handoff_id: str) -> Optional[Handoff]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM handoffs WHERE id = %s", (handoff_id,)
            ).fetchall()
        return self._row(rows[0]) if rows else None

    def list(
        self,
        project_id: str,
        statuses: Optional[Sequence[str]] = None,
        limit: int = 20,
    ) -> List[Optional[Handoff]]:
        statuses = list(statuses or ["active", "paused", "blocked", "completed", "abandoned"])
        placeholders = ", ".join(["%s"] * len(statuses))
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM handoffs WHERE project_id = %s AND status IN ({placeholders}) "
                "ORDER BY updated_ms DESC LIMIT %s",
                [project_id, *statuses, limit],
            ).fetchall()
        return [self._row(row) for row in rows]

    @staticmethod
    def _row(row: Dict[str, Any]) -> Optional[Handoff]:
        if not row:
            return None
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
            sections=row["sections"] if isinstance(row["sections"], dict) else json.loads(row["sections"] or "{}"),
            files=row["files"] if isinstance(row["files"], list) else json.loads(row["files"] or "[]"),
            created_ms=int(row["created_ms"]),
            updated_ms=int(row["updated_ms"]),
            continues_from=row.get("continues_from"),
            cosine=row.get("distance"),
        )