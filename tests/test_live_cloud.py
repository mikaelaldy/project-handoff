import os
import pytest
from handoff.storage import CockroachHandoffStore, ResumeQuery
from handoff.embeddings import BedrockEmbeddingProvider
from handoff.aws.worker import process_checkpoint_event

DB_URL = os.environ.get("HANDOFF_DB_URL")

pytestmark = pytest.mark.skipif(
    not DB_URL,
    reason="set HANDOFF_DB_URL to run the live CockroachDB + Bedrock integration test",
)

def test_live_cockroach_and_bedrock_vector_search():
    # 1. Initialize CockroachDB primary storage (creates table + vector index)
    store = CockroachHandoffStore(database_url=DB_URL)
    store.open()

    # 2. Bedrock Titan text embeddings v2
    embedder = BedrockEmbeddingProvider(region="us-east-1")

    # 3. Create a checkpoint event
    event = {
        "type": "checkpoint",
        "project_id": "live-hackathon-demo",
        "repository": "mikaelaldy/project-handoff",
        "branch": "main",
        "commit": "live123",
        "source_agent": "antigravity",
        "goal": "Implement CockroachDB vector memory and Bedrock integration",
        "sections": {
            "current_state": "CockroachDB connection and Bedrock Titan v2 verified live.",
            "next_action": "Execute vector similarity query from Codex agent.",
            "decisions": "Use CockroachDB VECTOR(512) and Titan v2 512 dimensions.",
        },
        "files": ["src/handoff/storage/cockroach.py", "src/handoff/embeddings.py"],
    }

    # 4. Process event via AWS Lambda worker logic
    res = process_checkpoint_event(event, store=store, embedder=embedder)
    assert res["ok"] is True
    assert res["embedding_provider"] == "bedrock"
    assert res["embedding_dim"] == 512

    # 5. Query vector search from CockroachDB
    query_vector = embedder.embed("How to query vector memory from CockroachDB")
    query = ResumeQuery(
        project_id="live-hackathon-demo",
        repository="mikaelaldy/project-handoff",
        embedding=query_vector,
        limit=1,
    )

    resumed_handoffs = store.resume(query)
    assert len(resumed_handoffs) > 0
    top = resumed_handoffs[0]
    assert top.project_id == "live-hackathon-demo"
    assert top.source_agent == "antigravity"
    assert "CockroachDB" in top.goal or "CockroachDB" in top.summary_text

    print("\n[LIVE CLOUD TEST SUCCESSFUL]")
    print("Handoff ID:", top.id)
    print("Resume payload:\n", top.resume_payload())

    store.close()
