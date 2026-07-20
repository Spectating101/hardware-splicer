"""Canonical product API composition.

The core engine factory remains in :mod:`hardware_splicer.api`; this module mounts
product-level routers that own durable workspace state. Keeping composition here
avoids coupling the large engine endpoint module to storage implementation details.
"""

from __future__ import annotations

from fastapi import FastAPI

from .api import create_app as create_engine_app
from .project_api import create_project_router
from .project_store import ProjectStore


def create_product_app(*, project_store: ProjectStore | None = None) -> FastAPI:
    """Build the canonical user-facing API with persistent project routes."""

    resolved_store = project_store or ProjectStore()
    app = create_engine_app()
    app.include_router(create_project_router(resolved_store))
    app.state.project_store = resolved_store
    return app


app = create_product_app()
