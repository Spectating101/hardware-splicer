#!/usr/bin/env python3
"""Extend the outsider mock with project discovery for the canonical Studio E2E."""

from __future__ import annotations

from typing import Any

from mock_outsider_jarvis_backend import PROJECT_ID, app, snapshot, state


@app.get("/v1/projects")
def list_projects() -> dict[str, Any]:
    current = snapshot()
    return {
        "ok": True,
        "projects": [
            {
                "project_id": PROJECT_ID,
                "name": current.get("name"),
                "project_name": current.get("name"),
                "revision": state["revision"],
                "archived": False,
                "saved_at": "2026-08-05T09:00:00+00:00",
            }
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8090)
