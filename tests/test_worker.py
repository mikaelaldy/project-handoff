import json

from handoff.aws.worker import process_checkpoint_event
from handoff.storage import SqliteHandoffStore


def test_checkpoint_event_persists_handoff(tmp_path):
    db = tmp_path / "handoffs.db"
    store = SqliteHandoffStore(str(db))
    store.open()

    event = {
        "type": "checkpoint",
        "project_id": "demo",
        "repository": "acme/web",
        "branch": "feat/auth",
        "commit": "abc123",
        "source_agent": "codex",
        "goal": "Add login rate limiting",
        "sections": {
            "current_state": "Login uses global limiter",
            "next_action": "Add user-scoped limiter",
            "decisions": "Keep global limiter for password reset",
        },
        "files": ["src/auth/login.ts", "tests/auth/login.test.ts"],
    }

    # Loopback embedder: deterministic hash vectors so the test never needs a
    # network call or AWS credentials.
    from handoff.embeddings import LexicalEmbeddingProvider

    result = process_checkpoint_event(event, store=store, embedder=LexicalEmbeddingProvider())

    assert result["ok"] is True
    assert result["embedding_provider"] == "lexical"
    assert result["embedding_dim"] > 0

    stored = store.get(result["handoff_id"])
    assert stored is not None
    assert stored.goal == "Add login rate limiting"
    assert stored.sections["next_action"] == "Add user-scoped limiter"
    assert stored.embedding is not None

    # A handoff must be resumable through the normal query path.
    from handoff.storage import ResumeQuery

    resumed = store.resume(ResumeQuery(project_id="demo", repository="acme/web"))
    assert any(r.id == stored.id for r in resumed)


def test_checkpoint_event_requires_project():
    store = SqliteHandoffStore(":memory:")
    store.open()
    import pytest

    from handoff.aws.worker import process_checkpoint_event

    with pytest.raises(ValueError):
        process_checkpoint_event({"goal": "x"}, store=store)