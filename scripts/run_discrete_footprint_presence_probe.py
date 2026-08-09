#!/usr/bin/env python3
"""Verify manufacturer-backed footprint candidates exist and parse in installed KiCad."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict


def _load(path: str | Path) -> Dict[str, Any]:
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise ValueError("evidence must be one JSON object")
    return body


def _footprint_location(root: Path, library_id: str) -> tuple[Path, Path, str]:
    lib, name = library_id.split(":", 1)
    library_dir = root / f"{lib}.pretty"
    return library_dir, library_dir / f"{name}.kicad_mod", name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="experiments/electronics/discrete_uart_3v3_1v8_evidence.json")
    parser.add_argument("--out-dir", default="artifacts/discrete-footprint-presence")
    parser.add_argument("--kicad-footprint-root", default=os.environ.get("KICAD_FOOTPRINT_ROOT", "/usr/share/kicad/footprints"))
    args = parser.parse_args()

    evidence = _load(args.evidence)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(args.kicad_footprint_root)
    kicad_cli = shutil.which("kicad-cli")

    selected_evidence_ids = {"part-tlv75533pdbvr", "part-sn74axc2t245rsw"}
    rows = []
    for part in evidence.get("parts") or []:
        if not isinstance(part, dict) or part.get("evidence_id") not in selected_evidence_ids:
            continue
        candidate = str(part.get("verified_kicad_footprint_candidate") or "")
        library_dir, path, footprint_name = _footprint_location(root, candidate) if candidate else (Path(), Path(), "")
        exists = bool(candidate) and path.is_file()
        export_ok = False
        returncode = None
        stdout = ""
        stderr = ""
        if exists and kicad_cli:
            export_dir = out / str(part["evidence_id"])
            export_dir.mkdir(parents=True, exist_ok=True)
            proc = subprocess.run(
                [
                    kicad_cli,
                    "fp",
                    "export",
                    "svg",
                    "--output",
                    str(export_dir),
                    "--footprint",
                    footprint_name,
                    str(library_dir),
                ],
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
            )
            returncode = proc.returncode
            stdout = proc.stdout[-4000:]
            stderr = proc.stderr[-4000:]
            export_ok = proc.returncode == 0 and any(export_dir.glob("*.svg"))
        rows.append(
            {
                "evidence_id": part.get("evidence_id"),
                "mpn": part.get("mpn"),
                "package_code": part.get("package_code"),
                "package_mechanical_code": part.get("package_mechanical_code"),
                "candidate": candidate,
                "library_dir": str(library_dir),
                "footprint_name": footprint_name,
                "path": str(path),
                "file_exists": exists,
                "kicad_parse_export_ok": export_ok,
                "kicad_returncode": returncode,
                "stdout_tail": stdout,
                "stderr_tail": stderr,
            }
        )

    checks = {
        "kicad_cli_available": bool(kicad_cli),
        "footprint_root_exists": root.is_dir(),
        "both_selected_ic_candidates_checked": len(rows) == 2,
        "all_candidate_files_exist": len(rows) == 2 and all(row["file_exists"] for row in rows),
        "all_candidate_files_parse_in_kicad": len(rows) == 2 and all(row["kicad_parse_export_ok"] for row in rows),
        "authority_stays_closed": True,
    }
    diagnostic_pass = all(checks.values())
    report = {
        "schema_version": "hardware_splicer.discrete_footprint_presence_probe.v1",
        "benchmark": "manufacturer_package_to_installed_kicad_footprint",
        "diagnostic_pass": diagnostic_pass,
        "kicad_cli": kicad_cli,
        "kicad_footprint_root": str(root),
        "checks": checks,
        "parts": rows,
        "promotion_policy": {
            "eligible_for_canonical_footprint_promotion": diagnostic_pass,
            "meaning": "Only exact candidates grounded by manufacturer/package evidence and independently present/parseable in the installed KiCad library may be promoted to kicad_footprint.",
            "fabrication_authorized": False,
            "authority_effect": "none"
        },
        "fabrication_authorized": False,
        "power_on_authorized": False
    }
    (out / "DISCRETE_FOOTPRINT_PRESENCE.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "benchmark=manufacturer_package_to_installed_kicad_footprint",
        f"diagnostic_pass={diagnostic_pass}",
    ]
    for row in rows:
        lines.append(f"{row['evidence_id']}.candidate={row['candidate']}")
        lines.append(f"{row['evidence_id']}.exists={row['file_exists']}")
        lines.append(f"{row['evidence_id']}.parse_export_ok={row['kicad_parse_export_ok']}")
    lines.extend(f"check.{key}={bool(value)}" for key, value in checks.items())
    (out / "DISCRETE_FOOTPRINT_PRESENCE_SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print((out / "DISCRETE_FOOTPRINT_PRESENCE_SUMMARY.txt").read_text(encoding="utf-8"), end="")
    return 0 if diagnostic_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
