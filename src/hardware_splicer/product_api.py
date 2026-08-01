"""Canonical product API composition.

The core engine factory remains in :mod:`hardware_splicer.api`; this module mounts
product-level routers that own durable workspace state and the cross-discipline
machine model. Keeping composition here avoids coupling the large engine endpoint
module to product storage and ontology implementation details.
"""

from __future__ import annotations

from fastapi import FastAPI

from .api import create_app as create_engine_app
from .circuit_json_api import create_circuit_json_router
from .engineering_review_api import create_engineering_review_router
from .machine_project_api import create_machine_project_router
from .project_api import create_project_router
from .project_store import ProjectStore


def create_product_app(*, project_store: ProjectStore | None = None) -> FastAPI:
    """Build the canonical user-facing API with project and machine routes."""

    resolved_store = project_store or ProjectStore()
    app = create_engine_app()
    app.include_router(create_project_router(resolved_store))
    app.include_router(create_machine_project_router())
    app.include_router(create_circuit_json_router())
    app.include_router(create_engineering_review_router())
    app.state.project_store = resolved_store
    return app


app = create_product_app()
