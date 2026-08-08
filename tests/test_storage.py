"""Storage tests. The SQLite adapter is the vendor-neutral fallback used in
tests; it must behave identically to the CockroachDB adapter, which runs in
integration tests when a live DATABASE_URL is present."""

import os

import pytest

from handoff.envelope import new_handoff
from handoff.storage import HandoffStore, ResumeQuery, SqliteHandoffStore

CRDB_URL = os.getenv("HANDOFF_DATABASE_URL") or os.getenv("DATABASE_URL")


@pytest.fixture()
def store():
    s = SqliteHandoffStore(":memory:")
    s.open()
    yield s
    s.close()


def test_lifecycle_create_resume_complete(store):
    rec = new_handoff(
        project_id="proj",
        repository="demo",
        source_agent="antigravity",
        goal="Fix login rate limiting",
        sections={"next_action": "Add user limiter"},
        files=["src/auth/login.ts"],
    )
    store.insert(rec)

    rows = store.resume(ResumeQuery(project_id="proj", repository="demo"))
    assert len(rows) == 1
    assert rows[0].id == rec.id
    assert rows[0].status == "active"
    assert rows[0].summary_text

    updated = store.update_progress(
        rec.workstream_id, "completed", {"next_action": "Done"}, commit="abc"
    )
    assert updated is not None
    assert updated.continues_from == rec.id
    assert updated.status == "completed"

    # The original record remains immutable history; resume only surfaces
    # unfinished workstreams, so a completed chain is not resumable.
    assert store.resume(ResumeQuery(project_id="proj", repository="demo")) == []
    assert store.get(rec.id) is not None
    assert store.get(updated.id) is not None


def test_scope_by_repository_and_branch(store):
    a = new_handoff("proj", "repo-a", "codex", "task a", branch="main")
    b = new_handoff("proj", "repo-b", "codex", "task b", branch="main")
    store.insert(a)
    store.insert(b)

    rows = store.resume(ResumeQuery(project_id="proj", repository="repo-a"))
    assert [r.id for r in rows] == [a.id]


def test_list_filters_status(store):
    a = new_handoff("proj", "repo", "opencode", "a")
    store.insert(a)
    done = store.complete(a.workstream_id)
    assert done is not None
    assert store.list("proj", statuses=["completed"])[0].id == done.id


def test_get_unknown(store):
    assert store.get("nope") is None