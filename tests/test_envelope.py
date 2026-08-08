import json
from pathlib import Path

from handoff.envelope import Handoff, new_handoff, redact, digest_record


def test_resume_payload_budget():
    rec = new_handoff(
        project_id="proj",
        repository="demo",
        source_agent="antigravity",
        goal="Fix login rate limiting",
        sections={
            "current_state": "Global limiter used on login; should be user-scoped.",
            "next_action": "Add user limiter to src/auth/login.ts",
            "decisions": "Keep global limiter; it protects password reset.",
        },
        files=["src/auth/login.ts", "tests/auth/login.test.ts"],
    )
    payload = rec.resume_payload(token_budget=240)
    assert "Fix login rate limiting" in payload
    # budget must truncate optional sections
    assert "further context available on request" in payload or len(payload) < 240 * 4


def test_resume_payload_always_has_provenance():
    rec = new_handoff("p", "r", "codex", "goal x")
    payload = rec.resume_payload(token_budget=50)
    assert "handoff id:" in payload
    assert "source agent: codex" in payload


def test_redact_secrets():
    text = "use token=sk-abcdef123456 and AKIA1234567890ABCDEF ok"
    out = redact(text)
    assert "sk-abcdef123456" not in out
    assert "AKIA1234567890ABCDEF" not in out
    assert "ok" in out


def test_digest_stable():
    a = new_handoff("p", "r", "a", "g")
    b = new_handoff("p", "r", "a", "g")
    assert digest_record(a) == digest_record(b)