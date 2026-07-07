"""KiBot-style fab artifact reference — compare build_compilation/ outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ..build_files import resolve_build_dir

# KiBot emits many of these in CI; we surface what the compile spine already produces.
KIBOT_REFERENCE_ROWS = [
    {
        "id": "gerbers",
        "kibot_output": "Gerber + drill files",
        "ours_glob": "gerber/**",
        "ours_file": None,
        "label": "Gerber package",
        "optional": True,
        "optional_note": "Present when compile used export_gerber",
    },
    {
        "id": "bom_csv",
        "kibot_output": "bom.csv",
        "ours_glob": None,
        "ours_file": "BOM.csv",
        "label": "BOM (CSV)",
    },
    {
        "id": "bom_json",
        "kibot_output": "bom.json",
        "ours_glob": None,
        "ours_file": "BOM.json",
        "label": "BOM (JSON)",
    },
    {
        "id": "positions",
        "kibot_output": "positions.csv / CPL",
        "ours_glob": None,
        "ours_file": "positions.csv",
        "label": "Pick-and-place (CPL)",
    },
    {
        "id": "fab_zip",
        "kibot_output": "Compressed fab upload",
        "ours_glob": None,
        "ours_file": "fab_package.zip",
        "label": "Fab package zip",
    },
    {
        "id": "drc_report",
        "kibot_output": "DRC report",
        "ours_glob": None,
        "ours_file": "KICAD_DRC.json",
        "label": "KiCad DRC report",
    },
    {
        "id": "schematic_pdf",
        "kibot_output": "PDF schematic",
        "ours_glob": None,
        "ours_file": None,
        "label": "Schematic PDF",
        "planned": True,
    },
]


def fab_output_manifest(build_dir: str | Path) -> Dict[str, Any]:
    root = resolve_build_dir(build_dir)
    comp = root / "build_compilation"
    rows: List[Dict[str, Any]] = []
    present_count = 0
    for spec in KIBOT_REFERENCE_ROWS:
        paths: List[Path] = []
        if spec.get("ours_file"):
            candidate = comp / str(spec["ours_file"])
            if candidate.is_file():
                paths.append(candidate)
        if spec.get("ours_glob") and comp.is_dir():
            paths.extend(sorted(p for p in comp.glob(str(spec["ours_glob"])) if p.is_file()))
        present = len(paths) > 0
        if present:
            present_count += 1
        status = "present"
        if spec.get("planned"):
            status = "planned"
        elif present:
            status = "present"
        elif spec.get("optional"):
            status = "optional"
        else:
            status = "missing"
        rows.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "kibot_output": spec["kibot_output"],
                "present": present,
                "status": status,
                "planned": bool(spec.get("planned")),
                "optional": bool(spec.get("optional")),
                "optional_note": spec.get("optional_note"),
                "paths": [str(p.relative_to(root)) for p in paths[:8]],
                "file_count": len(paths),
            }
        )
    total = len([r for r in rows if not r.get("planned") and not r.get("optional")])
    optional_present = len([r for r in rows if r.get("optional") and r.get("present")])
    return {
        "ok": True,
        "build_dir": str(root),
        "reference": "KiBot",
        "reference_url": "https://github.com/INTI-CMNB/KiBot",
        "note": "Reference comparison only — KiBot is not vendored. Use our artifacts or run KiBot externally.",
        "artifacts": rows,
        "present_count": present_count,
        "trackable_count": total,
        "optional_present_count": optional_present,
        "coverage_ratio": round(present_count / total, 3) if total else 0.0,
    }
