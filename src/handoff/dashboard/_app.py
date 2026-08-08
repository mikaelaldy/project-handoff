"""Minimal dashboard for inspecting handoff state.

The primary surfaces are the MCP server and CLI; this tiny read-only JSON
view exists so the demo has a human-visible surface. Flask is optional.
"""

from __future__ import annotations

import os

try:
    from flask import Flask, Response, request

    _HAS_FLASK = True
except Exception:  # pragma: no cover
    Flask = None
    Response = None
    request = None
    _HAS_FLASK = False


def create_app():
    if not _HAS_FLASK:
        raise RuntimeError("dashboard requires flask (pip install flask)")
    from .actions import do_list

    app = Flask("handoff")

    @app.get("/")
    def index():
        project_id = request.args.get("project_id", "")
        rows = []
        if project_id:
            rows = do_list(project_id, limit=50)
        payload = {
            "service": "handoff",
            "project_id": project_id or None,
            "handoffs": [
                {
                    "id": r.id,
                    "workstream_id": r.workstream_id,
                    "status": r.status,
                    "goal": r.goal,
                    "updated_ms": r.updated_ms,
                }
                for r in rows
            ],
        }
        return Response(
            __import__("json").dumps(payload, indent=2),
            mimetype="application/json",
        )

    return app


def main() -> None:
    port = int(os.getenv("HANDOFF_DASHBOARD_PORT", "8080"))
    create_app().run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()