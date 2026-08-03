"""Canonical product API composition.

The core engine factory remains in :mod:`hardware_splicer.api`; this module mounts
product-level routers that own durable workspace state, canonical machine and
electrical models, external interchange, runtime capability truth, source-agnostic
engineering planning, and engineering-review evidence. Keeping composition here gives
every UI and CLI entry point one durable cross-discipline product boundary without
coupling the engine endpoint module to product storage or ontology details.
"""

from __future__ import annotations

from fastapi import FastAPI

from .api import create_app as create_engine_app
from .capability_api import create_capability_router
from .circuit_json_api import create_circuit_json_router
from .electrical_design_api import create_electrical_design_router
from .electrical_interchange_api import create_electrical_interchange_router
from .engineering_api import create_engineering_router
from .engineering_review_api import create_engineering_review_router
from .engineering_review_identity_api import create_engineering_review_identity_router
from .machine_project_api import create_machine_project_router
from .project_api import create_project_router
from .project_compatibility import CompatibleProjectStore
from .project_store import ProjectStore


def create_product_app(project_store: ProjectStore | None = None) -> FastAPI:
    """Build the canonical user-facing API with all product route families."""

    resolved_store = project_store or CompatibleProjectStore()
    app = create_engine_app()
    app.state.project_store = resolved_store
    app.include_router(create_project_router(resolved_store))
    app.include_router(create_machine_project_router())
    app.include_router(create_electrical_design_router())
    app.include_router(create_circuit_json_router())
    app.include_router(create_electrical_interchange_router())
    app.include_router(create_capability_router())
    app.include_router(create_engineering_router(resolved_store))
    app.include_router(create_engineering_review_router())
    app.include_router(create_engineering_review_identity_router())
    return app


app = create_product_app()
