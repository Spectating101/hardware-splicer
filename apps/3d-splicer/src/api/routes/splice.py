from __future__ import annotations

import json
import os
import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from src.api.schemas import Description, SpliceResponse
from src.core.template_loader import render_template


router = APIRouter()


def _artifact_dir() -> Path:
    d = os.environ.get("ARTIFACT_DIR", "").strip() or str(Path(__file__).resolve().parents[3] / "stl")
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _render_phone_case_script(desc: Description) -> str:
    # `phone_case.cq.j2` expects top-level vars pcb/enclosure/ports/mounts, which Description provides.
    context: Dict[str, Any] = json.loads(desc.model_dump_json())
    return render_template("phone_case.cq.j2", context)


@router.post("/v1/splice/script")
def splice_script(desc: Description) -> Dict[str, Any]:
    """
    CadQuery-free endpoint: returns the generated CadQuery script (as text).
    This is the best connectivity test when CadQuery isn't installed on the host.
    """
    script = _render_phone_case_script(desc)
    return {"ok": True, "device": desc.device, "script": script}


@router.post("/v1/splice", response_model=SpliceResponse)
def splice(desc: Description) -> SpliceResponse:
    """
    Generate an enclosure STL from a v1 Description payload.

    Requires CadQuery to be installed. If missing, returns `success=false` and includes
    the generated script inside `validation.script` so upstream callers can still proceed
    (e.g. run inside the Docker image).
    """
    script = _render_phone_case_script(desc)

    if importlib.util.find_spec("cadquery") is None:
        return SpliceResponse(
            stl_path="",
            validation={"ok": False, "reason": "cadquery_unavailable", "script": script},
            success=False,
            ok=False,
            mode="script_fallback",
            script=script,
            error="CadQuery is not available in this environment.",
            message="CadQuery is not available in this environment. Use /v1/splice/script or run 3d-splicer via Docker.",
        )

    try:
        # Lazy import so the module can load in "no cadquery" environments.
        from src.core.cadquery_generator import script_to_stl
    except Exception as e:
        return SpliceResponse(
            stl_path="",
            validation={"ok": False, "reason": "cadquery_unavailable", "error": str(e), "script": script},
            success=False,
            ok=False,
            mode="script_fallback",
            script=script,
            error=str(e),
            message="CadQuery is not available in this environment. Use /v1/splice/script or run 3d-splicer via Docker.",
        )

    out_dir = _artifact_dir()
    out_path = out_dir / f"{desc.device}.stl"

    try:
        script_to_stl(script, out_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"STL generation failed: {e}")

    return SpliceResponse(
        stl_path=str(out_path),
        validation={"ok": True},
        success=True,
        ok=True,
        mode="stl",
        script=script,
        message="STL generated",
    )


# Back-compat aliases for older Circuit-AI clients.
@router.post("/generate", response_model=SpliceResponse)
def generate_alias(desc: Description) -> SpliceResponse:
    return splice(desc)


@router.post("/generate/script")
def generate_script_alias(desc: Description) -> Dict[str, Any]:
    return splice_script(desc)
