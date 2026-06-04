from __future__ import annotations

from fastapi import FastAPI

from src.api.routes.health import router as health_router
from src.api.routes.splice import router as splice_router


app = FastAPI(
    title="3d-splicer API",
    version="0.1",
)

app.include_router(health_router)
app.include_router(splice_router)

