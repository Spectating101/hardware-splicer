"""Golden intake compile manifest for engine CI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .runtime import ROOT

MANIFEST_PATH = ROOT / "examples" / "intakes" / "golden_compile_manifest.json"
INTAKES_DIR = ROOT / "examples" / "intakes"


def load_golden_compile_manifest() -> Dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"golden manifest missing: {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def golden_compile_cases() -> List[Dict[str, Any]]:
    manifest = load_golden_compile_manifest()
    cases: List[Dict[str, Any]] = []
    for row in manifest.get("cases") or []:
        case = dict(row)
        intake_name = str(row.get("intake") or "")
        if intake_name:
            case["intake_path"] = INTAKES_DIR / intake_name
        cases.append(case)
    return cases


def golden_catalog_direct_cases() -> List[Dict[str, Any]]:
    manifest = load_golden_compile_manifest()
    return [dict(row) for row in manifest.get("catalog_direct") or []]
