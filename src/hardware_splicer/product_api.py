"""Canonical product API composition.

The engine router remains the product's existing capability surface.  Persistent
project and complete-machine routers are mounted beside it so all UI and CLI entry
points share one durable, cross-discipline product boundary.
"""

from __future__ import annotations

from fastapi import FastAPI

from .api import create_app as create_engine_app
from .electrical_design_api import create_electrical_design_router
from .machine_project_api import create_machine_project_router
from .project_api import create_project_router
from .project_store import ProjectStore


def create_product_app(project_store: ProjectStore | None = None) -> FastAPI:
    store = project_store or ProjectStore()
    app = create_engine_app()
    app.state.project_store = store
    app.include_router(create_project_router(store))
    app.include_router(create_machine_project_router())
    app.include_router(create_electrical_design_router())
    return app


app = create_product_app()
