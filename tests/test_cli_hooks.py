import json
import os
import subprocess
import sys
from pathlib import Path

from handoff.adapters.hooks import antigravity_hooks_json, codex_hooks_json, opencode_plugin_js

REPO_ROOT = Path(__file__).parent.parent


def _run_cli(args, env, stdin=None):
    return subprocess.run(
        [sys.executable, "-m", "handoff.cli", *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )


def test_cli_checkpoint_and_resume(tmp_path):
    db = tmp_path / "h.db"
    env = dict(os.environ)
    env["HANDOFF_SQLITE_PATH"] = str(db)

    init = _run_cli(["init"], env)
    assert init.returncode == 0, init.stderr

    event = json.dumps(
        {
            "type": "checkpoint",
            "project_id": "demo",
            "repository": "acme/web",
            "branch": "main",
            "commit": "abc",
            "source_agent": "codex",
            "goal": "Fix login rate limiting",
            "sections": {"next_action": "Add user limiter"},
            "files": ["src/auth/login.ts"],
        }
    )
    cp = _run_cli(["checkpoint", "--event", "-"], env, stdin=event)
    assert cp.returncode == 0, cp.stderr
    assert "handoff_id" in cp.stdout

    resume = _run_cli(["resume", "--project", "demo", "--repo", "acme/web"], env)
    assert resume.returncode == 0, resume.stderr
    assert "Fix login rate limiting" in resume.stdout
    assert "next action" in resume.stdout.lower()


def test_hook_configs_are_valid_json():
    script = Path("~/.handoff/adapter.py").expanduser()
    codex = codex_hooks_json(script)
    assert "PreCompact" in codex["hooks"]
    assert "SessionEnd" in codex["hooks"]
    anti = antigravity_hooks_json(script)
    assert "Stop" in anti["hooks"]
    plugin = opencode_plugin_js(script)
    assert "session.idle" in plugin


def test_git_push_conversion():
    from handoff.adapters.git import github_push_to_events

    payload = {
        "ref": "refs/heads/main",
        "repository": {"full_name": "acme/web", "name": "web"},
        "commits": [
            {
                "id": "c1",
                "message": "Add search page",
                "added": ["src/search.tsx"],
                "modified": ["src/app.tsx"],
                "removed": [],
            }
        ],
    }
    events = github_push_to_events(payload)
    assert len(events) == 1
    assert events[0]["source_agent"] == "lovable"
    assert events[0]["branch"] == "main"
    assert "src/search.tsx" in events[0]["files"]