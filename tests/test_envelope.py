import json
from pathlib import Path

import pytest

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


SECRETS = [
    "sk-proj-abc123def456ghi789jkl012",
    "ghp_16C7e42F292c6912E7710c838347Ae178B4a",
    "AKIAIOSFODNN7EXAMPLE",
    "xoxb-1234567890-abcdefghijkl",
    "-----BEGIN RSA PRIVATE KEY-----",
    "password=hunter2correcthorse",
    "token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
]


@pytest.mark.parametrize("secret", SECRETS)
def test_redact_removes_real_secret(secret):
    """Each secret shape the regex claims to cover must actually be stripped."""
    out = redact(f"prefix {secret} suffix")
    assert secret not in out, f"leaked: {secret}"
    assert "[REDACTED]" in out
    # surrounding non-secret text must survive
    assert out.startswith("prefix ")
    assert out.endswith(" suffix")


def test_redact_preserves_innocent_text():
    text = "deploy the login service to us-east-1 and run the tests"
    assert redact(text) == text


def test_redact_handles_multiple_secrets_in_one_string():
    out = redact("a sk-proj-abc123def456ghi789 b AKIAIOSFODNN7EXAMPLE c")
    assert "sk-proj" not in out
    assert "AKIA" not in out
    assert out.count("[REDACTED]") == 2


def test_new_handoff_redacts_secrets_in_files_and_commit():
    """Redaction must apply at the envelope boundary, not just as a helper."""
    rec = new_handoff(
        "p", "r", "codex", "goal",
        commit="AKIAIOSFODNN7EXAMPLE",
        files=["src/app.py", "creds/sk-proj-abc123def456ghi789"],
    )
    assert "AKIA" not in rec.commit
    assert not any("sk-proj" in f for f in rec.files)


def test_digest_stable():
    a = new_handoff("p", "r", "a", "g")
    b = new_handoff("p", "r", "a", "g")
    assert digest_record(a) == digest_record(b)