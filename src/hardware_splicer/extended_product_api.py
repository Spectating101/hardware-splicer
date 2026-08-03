"""Extended product composition including strict physical-evidence release gates.

The canonical product app is reused unchanged, then the physical-evidence routers are
mounted. This gives deployments an immediately runnable integration target while the
main launcher remains draft/validation-gated.
"""

from __future__ import annotations

from fastapi import FastAPI

from .physical_evidence_api import create_physical_evidence_router
from .physical_evidence_persistence_api import create_physical_evidence_persistence_router
from .product_api import create_product_app as create_base_product_app
from .project_store import ProjectStore


def create_extended_product_app(project_store: ProjectStore | None = None) -> FastAPI:
    app = create_base_product_app(project_store)
    resolved_store = app.state.project_store
    app.include_router(create_physical_evidence_router())
    app.include_router(create_physical_evidence_persistence_router(resolved_store))
    return app


app = create_extended_product_app()
