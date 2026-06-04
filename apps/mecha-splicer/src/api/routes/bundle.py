from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from src.mecha_splicer.runner import run

router = APIRouter()


@router.post("/bundle")
def bundle(
    payload: Dict[str, Any],
    out_dir: Optional[str] = Query(default=None, description="Optional output directory to write bundle files"),
    use_3d_splicer: bool = Query(default=False),
    render_stl: bool = Query(default=False),
):
    return run(payload, out_dir=Path(out_dir) if out_dir else None, use_3d_splicer=use_3d_splicer, render_stl=render_stl)

