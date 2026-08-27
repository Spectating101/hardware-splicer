"""Compatibility alias for the canonical product API.

Strict physical-evidence and scoped-release routes are now mounted directly by
:mod:`hardware_splicer.product_api`. This module remains for deployments that already
reference ``hardware_splicer.extended_product_api`` without registering duplicate
routes.
"""

from __future__ import annotations

from fastapi import FastAPI

from .product_api import create_product_app
from .project_store import ProjectStore


def create_extended_product_app(project_store: ProjectStore | None = None) -> FastAPI:
    return create_product_app(project_store)


app = create_extended_product_app()
