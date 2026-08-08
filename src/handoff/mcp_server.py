"""MCP server exposing Handoff tools to MCP-compatible AI clients.

Tool surface (small by design):
- handoff_checkpoint
- handoff_resume
- handoff_get
- handoff_list
- handoff_complete
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Optional

from .actions import do_checkpoint, do_complete, do_get, do_list, do_resume, handoff_to_dict
from .storage import HandoffStore, store_from_env

try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import CallToolResult, TextContent, Tool

    _HAS_MCP = True
except Exception:  # pragma: no cover - guard for optional dependency
    Server = None
    InitializationOptions = None
    stdio_server = None
    CallToolResult = None
    TextContent = None
    Tool = None
    _HAS_MCP = False


def _text(content: str) -> Any:
    return TextContent(type="text", text=content)


def build_mcp_server(store: Optional[HandoffStore] = None):
    if not _HAS_MCP:
        raise RuntimeError("MCP SDK is not installed (pip install 'handoff[mcp]')")
    store = store or store_from_env()
    server = Server("handoff")

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="handoff_checkpoint",
                description=(
                    "Persist a checkpoint of the current work so another AI coding "
                    "agent can continue it. Provide project_id, repository, "
                    "source_agent, goal, optional sections (current_state, "
                    "next_action, decisions, blockers, validation), and files."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "repository": {"type": "string"},
                        "branch": {"type": "string"},
                        "commit": {"type": "string"},
                        "source_agent": {"type": "string"},
                        "goal": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["active", "paused", "blocked"],
                            "default": "active",
                        },
                        "sections": {"type": "object"},
                        "files": {"type": "array", "items": {"type": "string"}},
                        "workstream_id": {"type": "string"},
                    },
                    "required": ["project_id", "repository", "source_agent", "goal"],
                },
            ),
            Tool(
                name="handoff_resume",
                description=(
                    "Return the best unfinished handoff for a project so this agent "
                    "can continue work another agent started. Filters by repository "
                    "and branch; query_text enables semantic ranking."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "repository": {"type": "string"},
                        "branch": {"type": "string"},
                        "query_text": {"type": "string"},
                        "limit": {"type": "integer", "default": 1},
                    },
                    "required": ["project_id"],
                },
            ),
            Tool(
                name="handoff_get",
                description="Fetch the full handoff record by id.",
                inputSchema={
                    "type": "object",
                    "properties": {"handoff_id": {"type": "string"}},
                    "required": ["handoff_id"],
                },
            ),
            Tool(
                name="handoff_list",
                description="List recent handoffs for a project.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["project_id"],
                },
            ),
            Tool(
                name="handoff_complete",
                description="Mark the latest handoff of a workstream completed.",
                inputSchema={
                    "type": "object",
                    "properties": {"workstream_id": {"type": "string"}},
                    "required": ["workstream_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]):
        if name == "handoff_checkpoint":
            return _text(json.dumps(do_checkpoint(arguments, store=store), indent=2))
        if name == "handoff_resume":
            results = do_resume(arguments, store=store)
            if not results:
                return _text(json.dumps({"ok": True, "results": []}, indent=2))
            return _text("\n\n---\n\n".join(r.resume_payload() for r in results))
        if name == "handoff_get":
            rec = do_get(arguments["handoff_id"], store=store)
            return _text(json.dumps(handoff_to_dict(rec) if rec else {"error": "not found"}, indent=2))
        if name == "handoff_list":
            results = do_list(arguments["project_id"], limit=int(arguments.get("limit", 20)), store=store)
            return _text(
                json.dumps(
                    [
                        {"id": r.id, "workstream_id": r.workstream_id, "status": r.status,
                         "goal": r.goal, "updated_ms": r.updated_ms}
                        for r in results
                    ],
                    indent=2,
                )
            )
        if name == "handoff_complete":
            rec = do_complete(arguments["workstream_id"], store=store)
            return _text(json.dumps({"ok": rec is not None, "handoff_id": rec.id if rec else None}, indent=2))
        raise ValueError(f"unknown tool: {name}")

    return server


async def serve_stdio() -> None:
    server = build_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="handoff",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities=None,
                ),
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Handoff MCP server")
    parser.add_argument("--check", action="store_true", help="verify the environment and exit")
    args = parser.parse_args()
    if args.check:
        try:
            store = store_from_env()
            store.open()
            store.close()
            print("handoff mcp: ok")
            return
        except Exception as exc:
            print(f"handoff mcp: error: {exc}")
            raise SystemExit(1)
    if not _HAS_MCP:
        raise SystemExit("MCP SDK is not installed; run: pip install 'handoff[mcp]'")
    import asyncio

    asyncio.run(serve_stdio())


if __name__ == "__main__":
    main()