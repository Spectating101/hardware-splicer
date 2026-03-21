from __future__ import annotations

import io
from typing import Any, Dict, Optional

import numpy as np
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from loguru import logger
from PIL import Image

from src.api.v1.auth import get_current_user
from src.api.v1.billing import router as billing_router
from src.api.v1.physics import router as physics_router
from src.core.ingest import CircuitAnalyzer


app = FastAPI(title="Circuit.AI API v1", version="1.0.0")
app.include_router(physics_router)
app.include_router(billing_router)
_analyzer: CircuitAnalyzer | None = None


def get_analyzer() -> CircuitAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = CircuitAnalyzer()
    return _analyzer


@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {"ok": True}


@app.get("/readyz")
def readyz(analyzer: CircuitAnalyzer = Depends(get_analyzer)) -> Dict[str, Any]:
    # "Ready" means the app can import and create its analyzer; the heavy
    # YOLO weights are lazily loaded per request.
    return {"ready": True, "backend_default": getattr(analyzer.detector, "default_backend", "unknown")}


@app.post("/analyze")
def analyze(
    file: UploadFile = File(...),
    backend: Optional[str] = Form(None),
    enable_ocr: bool = Form(True),
    current_user: Dict[str, Any] = Depends(get_current_user),
    analyzer: CircuitAnalyzer = Depends(get_analyzer),
) -> Dict[str, Any]:
    try:
        image_bytes = file.file.read()
        image = Image.open(io.BytesIO(image_bytes))
        image_np = np.array(image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    results = analyzer.analyze_pcb(image_np, backend=backend, enable_ocr=enable_ocr)
    summary = analyzer.get_analysis_summary(results)

    analysis_meta = results.get("analysis_metadata", {}) if isinstance(results, dict) else {}
    detection_summary = results.get("detection_summary", {}) if isinstance(results, dict) else {}
    detection_quality = (
        analysis_meta.get("detection_quality")
        or detection_summary.get("detection_quality")
        or "unknown"
    )

    logger.info(
        f"/analyze user={current_user.get('user_id')} backend={backend or analysis_meta.get('backend')} ocr={enable_ocr}"
    )
    return {
        "results": results,
        "summary": summary,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "detection_quality": detection_quality,
            "detection_summary": detection_summary,
            "backend": analysis_meta.get("backend") or backend,
            "ocr": analysis_meta.get("ocr") if "ocr" in analysis_meta else enable_ocr,
        },
    }
