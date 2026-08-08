"""Hook adapter installers for AI coding agents.

Each adapter writes the platform hook configuration that invokes the
handoff CLI at lifecycle boundaries:
- Codex: `~/.codex/hooks.json` (PreCompact, SessionEnd) + MCP config
- Antigravity: `.agents/hooks.json` (Stop, PostInvocation) + MCP config
- OpenCode: `.opencode/plugin.ts` (session.idle / session.compacted)

Everything is fail-safe by design: hook commands exit 0 even when the
checkpoint pipeline fails, so a Handoff failure never blocks the agent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

HOOK_SCRIPT = """#!/usr/bin/env python3
# Handoff auto-capture adapter. Fail-safe: never blocks the agent.
import json, os, subprocess, sys, tempfile

def main():
    try:
        payload = json.load(sys.stdin or sys.stdin.buffer)
    except Exception:
        payload = {}
    cwd = os.getcwd()
    branch = "unknown"
    commit = ""
    try:
        branch = subprocess.run(["git","branch","--show-current"],capture_output=True,text=True,timeout=3).stdout.strip() or "unknown"
        commit = subprocess.run(["git","rev-parse","--short","HEAD"],capture_output=True,text=True,timeout=3).stdout.strip()
    except Exception:
        pass
    event = {
        "type": "checkpoint",
        "project_id": payload.get("project_id") or os.path.basename(cwd),
        "repository": payload.get("repository") or os.path.basename(cwd),
        "branch": payload.get("branch") or branch,
        "commit": payload.get("commit") or commit,
        "source_agent": payload.get("source_agent") or os.environ.get("HANDOFF_SOURCE_AGENT","agent"),
        "status": "active",
        "goal": payload.get("goal",""),
        "sections": payload.get("sections") or {},
        "files": payload.get("files") or [],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(event, fh)
        path = fh.name
    try:
        subprocess.run(["handoff","checkpoint","--event",path], capture_output=True, timeout=10)
    finally:
        try: os.unlink(path)
        except OSError: pass

if __name__ == "__main__":
    main()
"""


def write_script(root: Path) -> Path:
    script = root / "handoff-adapter.py"
    script.write_text(HOOK_SCRIPT, encoding="utf-8")
    script.chmod(0o755)
    return script


def codex_hooks_json(script: Path) -> Dict[str, Any]:
    return {
        "hooks": {
            "PreCompact": [
                {
                    "matcher": "manual|auto",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"python3 {script}",
                            "statusMessage": "Capturing Handoff checkpoint",
                        }
                    ],
                }
            ],
            "SessionEnd": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"python3 {script}",
                            "statusMessage": "Saving Handoff session end",
                        }
                    ]
                }
            ],
        }
    }


def antigravity_hooks_json(script: Path) -> Dict[str, Any]:
    return {
        "hooks": {
            "PostInvocation": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"python3 {script}",
                            "timeout": 120,
                        }
                    ]
                }
            ],
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"python3 {script}",
                            "timeout": 120,
                        }
                    ]
                }
            ],
        }
    }


def opencode_plugin_js(script: Path) -> str:
    return f"""// Handoff OpenCode plugin: captures session boundaries to the CLI.
// Fail-safe by design: errors are logged, never thrown.
import {{ promises }} from "node:fs";

export const HandoffPlugin = async (ctx) => {{
  const capture = async () => {{
    try {{
      const session = ctx.getSession?.() ?? null;
      const payload = JSON.stringify({{
        project_id: ctx.project?.path ? ctx.project.path.split("/").pop() : "unknown",
        repository: ctx.project?.path ? ctx.project.path.split("/").pop() : "unknown",
        branch: "",
        commit: "",
        source_agent: "opencode",
        goal: session?.title || "opencode session",
        sections: {{ current_state: JSON.stringify(session?.summary ?? "Unknown state") }},
        files: session?.directory || [],
      }});
      await ctx.exec?.("python3", ["{script}", "--stdin-json"], {{ env: {{ HANDOFF_PAYLOAD: payload }} }});
    }} catch {{ /* advisory */ }}
  }};
  return {{
    "session.idle": capture,
    "session.compacted": capture,
    "session.error": capture,
    "session.end": capture,
  }};
}};
"""


def write_codex_config(hooks_path: Path, script: Path) -> Dict[str, Any]:
    os.makedirs(hooks_path.parent, exist_ok=True)
    script = write_script(hooks_path.parent / "handoff-adapter.py")
    config = codex_hooks_json(script)
    hooks_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config


def write_antigravity_config(hooks_path: Path, script_path: Path) -> Dict[str, Any]:
    script = write_script(script_path)
    config = antigravity_hooks_json(script)
    hooks_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config


def write_script(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HOOK_SCRIPT, encoding="utf-8")
    path.chmod(0o755)
    return path


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Install Handoff agent hooks")
    parser.add_argument("agent", choices=["codex", "antigravity", "opencode", "all"])
    parser.add_argument("--home", default=str(Path.home()), help="home directory")
    args = parser.parse_args(argv)

    home = Path(args.home)
    script_root = home / ".handoff"
    script = write_script(script_root / "adapter.py")

    if args.agent in ("codex", "all"):
        write_codex_config(home / ".codex" / "hooks.json", script)
        print("codex: wrote ~/.codex/hooks.json")
    if args.agent in ("antigravity", "all"):
        write_antigravity_config(home / ".gemini" / "config" / "hooks.json", script)
        print("antigravity: wrote ~/.gemini/config/hooks.json")
    if args.agent in ("opencode", "all"):
        plugin_dir = home / ".config" / "opencode"
        os.makedirs(plugin_dir, exist_ok=True)
        plugin = plugin_dir / "plugins" / "handoff.ts"
        os.makedirs(plugin.parent, exist_ok=True)
        plugin.write_text(opencode_plugin_js(script), encoding="utf-8")
        print("opencode: wrote ~/.config/opencode/plugins/handoff.ts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())