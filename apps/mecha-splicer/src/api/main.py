from __future__ import annotations

import os

from fastapi import FastAPI

from .routes.bundle import router as bundle_router
from .routes.mint import router as mint_router
from .routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Mecha-Splicer",
        version=os.getenv("MECHA_SPLICER_VERSION", "0.1.0"),
        description="Mechanical splicing API: bundle generation and mint pipeline.",
    )
    app.include_router(health_router, prefix="/v1")
    app.include_router(bundle_router, prefix="/v1")
    app.include_router(mint_router, prefix="/v1")
    return app


app = create_app()

