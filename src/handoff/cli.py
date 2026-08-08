"""Handoff CLI: the human-facing surface for local mode and debugging.

Subcommands mirror the MCP tools so the same checks run in a terminal:
    handoff init
    handoff checkpoint --event <json-file-or-stdin>
    handoff resume --project <id> [--repo R] [--branch B] [--query "..."]
    handoff get <handoff-id>
    handoff list --project <id>
    handoff complete --workstream <id>
    handoff mcp-serve
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

from .actions import do_checkpoint, do_complete, do_get, do_list, do_resume, handoff_to_dict
from .storage import store_from_env


def _load_event(raw: str) -> Dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("event must be a JSON object")
    return data


def run(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="handoff", description="Vendor-neutral handoff layer for AI coding agents")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create local storage and schema")

    p = sub.add_parser("checkpoint", help="persist a checkpoint event (JSON file or stdin)")
    p.add_argument("--event", help="path to a JSON event file (default: stdin)")
    p.add_argument("--project", dest="project_id", help="project id (override)")
    p.add_argument("--repo", dest="repository", help="repository (override)")
    p.add_argument("--agent", dest="source_agent", help="source agent (override)")

    p = sub.add_parser("resume", help="return best unfinished handoff")
    p.add_argument("--project", dest="project_id", required=True)
    p.add_argument("--repo", dest="repository", default="")
    p.add_argument("--branch", default="")
    p.add_argument("--query", dest="query_text", default="")
    p.add_argument("--limit", type=int, default=1)

    p = sub.add_parser("get", help="fetch a handoff by id")
    p.add_argument("handoff_id")

    p = sub.add_parser("list", help="list handoffs for a project")
    p.add_argument("--project", dest="project_id", required=True)
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("complete", help="complete a workstream")
    p.add_argument("--workstream", dest="workstream_id", required=True)

    sub.add_parser("mcp-serve", help="run the MCP server over stdio")

    args = parser.parse_args(argv)

    if args.command == "init":
        store = store_from_env()
        store.open()
        store.close()
        print("handoff: initialized")
        return 0

    if args.command == "checkpoint":
        raw = ""
        if args.event and args.event != "-":
            with open(args.event, "r", encoding="utf-8") as fh:
                raw = fh.read()
        else:
            raw = sys.stdin.read()
        event = _load_event(raw)
        if args.project_id:
            event["project_id"] = args.project_id
        if args.repository:
            event["repository"] = args.repository
        if args.source_agent:
            event["source_agent"] = args.source_agent
        result = do_checkpoint(event)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "resume":
        results = do_resume(
            {
                "project_id": args.project_id,
                "repository": args.repository,
                "branch": args.branch,
                "query_text": args.query_text,
                "limit": args.limit,
            }
        )
        if not results:
            print(json.dumps({"ok": True, "results": []}, indent=2))
            return 0
        for r in results:
            print(r.resume_payload())
            print("\n---\n")
        return 0

    if args.command == "get":
        rec = do_get(args.handoff_id)
        print(json.dumps(handoff_to_dict(rec) if rec else {"error": "not found"}, indent=2))
        return 0

    if args.command == "list":
        recs = do_list(args.project_id, limit=args.limit)
        print(
            json.dumps(
                [
                    {"id": r.id, "workstream_id": r.workstream_id, "status": r.status,
                     "goal": r.goal, "updated_ms": r.updated_ms}
                    for r in recs
                ],
                indent=2,
            )
        )
        return 0

    if args.command == "complete":
        rec = do_complete(args.workstream_id)
        print(json.dumps({"ok": rec is not None, "handoff_id": rec.id if rec else None}, indent=2))
        return 0

    if args.command == "mcp-serve":
        from .mcp_server import main as mcp_main

        mcp_main()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(run())