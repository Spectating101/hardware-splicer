from __future__ import annotations

import json
import io
import os
import tempfile
import inspect
from typing import Any, Dict, Optional

import numpy as np
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from loguru import logger
from PIL import Image
from starlette.datastructures import UploadFile as StarletteUploadFile

from src.api.v1.auth import get_current_user
from src.api.v1.billing import router as billing_router
from src.api.v1.physics import router as physics_router
from src.core.ingest import CircuitAnalyzer
from src.engines.kicad_parser import KiCadParser


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
    reference_counts: Optional[str] = Form(None),
    reference_file: Optional[UploadFile] = File(None),
    reference_topology: Optional[str] = Form(None),
    reference_topology_file: Optional[UploadFile] = File(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    analyzer: CircuitAnalyzer = Depends(get_analyzer),
) -> Dict[str, Any]:
    try:
        image_bytes = file.file.read()
        image = Image.open(io.BytesIO(image_bytes))
        image_np = np.array(image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    reference_payload: Dict[str, int] = {}
    reference_topology_payload: Dict[str, Any] | None = None
    reference_source = "none"

    reference_counts_text = reference_counts if isinstance(reference_counts, str) else None
    if isinstance(reference_counts_text, str):
        reference_counts_text = reference_counts_text.strip()
        if reference_counts_text == "":
            reference_counts_text = None

    reference_topology_text = reference_topology if isinstance(reference_topology, str) else None
    if isinstance(reference_topology_text, str):
        reference_topology_text = reference_topology_text.strip()
        if reference_topology_text == "":
            reference_topology_text = None

    def _has_upload(file_item: Any) -> bool:
        return isinstance(file_item, StarletteUploadFile) and bool((file_item.filename or "").strip())

    ref_inputs = [
        ("reference_counts", reference_counts_text is not None),
        ("reference_file", _has_upload(reference_file)),
        ("reference_topology", reference_topology_text is not None),
        ("reference_topology_file", _has_upload(reference_topology_file)),
    ]
    provided_ref_inputs = [name for name, value in ref_inputs if value]
    if len(provided_ref_inputs) > 1:
        raise HTTPException(
            status_code=400,
            detail="Use only one of reference_counts, reference_file, reference_topology, reference_topology_file",
        )

    def _parse_counts_payload(raw_counts: Any) -> Dict[str, int]:
        if not isinstance(raw_counts, dict):
            raise HTTPException(
                status_code=400,
                detail="reference payload must be a JSON object mapping component names to counts",
            )
        parsed: Dict[str, int] = {}
        for name, raw_count in raw_counts.items():
            try:
                count = int(raw_count)
            except (TypeError, ValueError):
                continue
            if count > 0:
                parsed[str(name)] = count
        return parsed

    def _parse_reference_file(file_item: UploadFile) -> tuple[Dict[str, int], Dict[str, Any] | None]:
        reference_bytes = file_item.file.read()
        if not reference_bytes:
            raise HTTPException(status_code=400, detail="Reference file is empty")

        content_type = (file_item.content_type or "").lower()
        filename = (file_item.filename or "").lower()
        is_json = (
            filename.endswith(".json")
            or "application/json" in content_type
            or content_type.startswith("text/")
        )

        if is_json:
            try:
                raw_reference = json.loads(reference_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid reference JSON file: {e}")
            if isinstance(raw_reference, dict) and {"nets", "components"}.issubset(set(raw_reference.keys())):
                return {}, raw_reference
            return _parse_counts_payload(raw_reference), None

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".net") as tmp:
                tmp.write(reference_bytes)
                tmp_path = tmp.name
            parsed = KiCadParser(tmp_path).parse()
            if not isinstance(parsed, dict) or not parsed.get("nets"):
                raise ValueError("Not a KiCad netlist")
            return {}, parsed
        except HTTPException:
            raise
        except Exception:
            # Legacy behavior fallback: treat as image and run component count AOI.
            try:
                reference_image = Image.open(io.BytesIO(reference_bytes))
                reference_np = np.array(reference_image)
                reference_detections = analyzer.detector.detect_components(
                    reference_np,
                    backend=backend,
                    enable_ocr=enable_ocr,
                )
                parsed_counts: Dict[str, int] = {}
                for det in reference_detections:
                    name = str(det.get("class_name", "unknown"))
                    parsed_counts[name] = parsed_counts.get(name, 0) + 1
                return parsed_counts, None
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Could not parse reference file: {e}")
        finally:
            if tmp_path is not None:
                os.remove(tmp_path)

    if reference_counts_text is not None:
        try:
            reference_payload = _parse_counts_payload(json.loads(reference_counts_text))
            reference_source = "json"
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid reference_counts JSON: {e}")

    elif reference_topology_text is not None:
        try:
            raw_reference_topology = json.loads(reference_topology_text)
            if (
                isinstance(raw_reference_topology, dict)
                and {"nets", "components"}.issubset(set(raw_reference_topology.keys()))
            ):
                reference_topology_payload = raw_reference_topology
                reference_source = "topology_json"
            else:
                reference_payload = _parse_counts_payload(raw_reference_topology)
                reference_source = "topology_json"
        except json.JSONDecodeError:
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".net") as tmp:
                    tmp.write(reference_topology_text.encode("utf-8"))
                    tmp_path = tmp.name
                parsed = KiCadParser(tmp_path).parse()
                if not isinstance(parsed, dict) or not parsed.get("nets"):
                    raise ValueError("Not a KiCad netlist")
                reference_topology_payload = parsed
                reference_source = "topology_text"
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid reference_topology text: {e}")
            finally:
                if tmp_path is not None:
                    os.remove(tmp_path)

    elif _has_upload(reference_topology_file):
        reference_payload, reference_topology_payload = _parse_reference_file(reference_topology_file)
        reference_source = "topology_file"

    elif _has_upload(reference_file):
        reference_payload, reference_topology_payload = _parse_reference_file(reference_file)
        reference_source = "topology_file" if reference_topology_payload is not None else "image"

    analyzer_signature = inspect.signature(analyzer.analyze_pcb)
    analyze_kwargs: Dict[str, Any] = {
        "backend": backend,
        "enable_ocr": enable_ocr,
    }
    if "reference_counts" in analyzer_signature.parameters:
        analyze_kwargs["reference_counts"] = reference_payload
    if "reference_topology" in analyzer_signature.parameters:
        analyze_kwargs["reference_topology"] = reference_topology_payload

    try:
        results = analyzer.analyze_pcb(image_np, **analyze_kwargs)
    except TypeError as e:
        # Backward-compatible fallback for older/an alternative analyzer mocks.
        if "reference_counts" in str(e) or "reference_topology" in str(e):
            results = analyzer.analyze_pcb(image_np, backend=backend, enable_ocr=enable_ocr)
        else:
            raise
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
            "reference": {
                "status": analysis_meta.get("reference_aoi_status"),
                "component_delta": analysis_meta.get("reference_component_delta", 0),
                "topology_status": analysis_meta.get("topology_aoi_status"),
                "topology_delta": analysis_meta.get("topology_aoi_delta", 0),
                "input": {
                    "counts": reference_payload,
                    "reference_source": reference_source,
                    "topology": bool(reference_topology_payload),
                },
            },
        },
    }
