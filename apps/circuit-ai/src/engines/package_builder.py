#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timezone


@dataclass(frozen=True)
class PackageResult:
    zip_path: Path
    manifest: Dict[str, Any]


def build_package_zip(
    *,
    out_path: Path,
    report_md: str,
    bom_csv: Optional[str] = None,
    pnp_csv: Optional[str] = None,
    gerbers_zip_path: Optional[Path] = None,
    extra_files: Optional[Dict[str, bytes]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> PackageResult:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Any] = {
        "files": [],
    }
    if metadata:
        manifest["metadata"] = metadata
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("DFM_REPORT.md", report_md)
        manifest["files"].append({"path": "DFM_REPORT.md", "kind": "report"})

        if bom_csv is not None:
            zf.writestr("BOM.csv", bom_csv)
            manifest["files"].append({"path": "BOM.csv", "kind": "bom"})

        if pnp_csv is not None:
            zf.writestr("PnP.csv", pnp_csv)
            manifest["files"].append({"path": "PnP.csv", "kind": "pnp"})

        if gerbers_zip_path is not None and gerbers_zip_path.exists():
            zf.write(str(gerbers_zip_path), arcname="Gerbers.zip")
            manifest["files"].append({"path": "Gerbers.zip", "kind": "gerbers"})

        if extra_files:
            for name, blob in extra_files.items():
                safe = name.strip().lstrip("/").replace("..", "_")
                if not safe:
                    continue
                zf.writestr(safe, blob)
                manifest["files"].append({"path": safe, "kind": "extra"})

        manifest["files"].append({"path": "MANIFEST.json", "kind": "manifest"})
        zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))

    return PackageResult(zip_path=out_path, manifest=manifest)
