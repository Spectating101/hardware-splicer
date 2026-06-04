#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class CaseResult:
    name: str
    pcb_path: str
    sch_path: Optional[str]
    ok: bool
    pnp_ok: bool
    pnp_export_method: Optional[str]
    dfm_ok: bool
    package_ok: bool
    gerbers_export_method: Optional[str]
    netlist_export_method: Optional[str]
    errors: List[str]
    seconds: float


def _guess_schematic_for_pcb(pcb_path: Path) -> Optional[Path]:
    # Common patterns: same directory, same stem, schematic lives near PCB.
    cand = pcb_path.with_suffix(".kicad_sch")
    if cand.exists():
        return cand
    # Try sibling with .kicad_sch anywhere in same directory.
    for sch in pcb_path.parent.glob("*.kicad_sch"):
        if sch.stem == pcb_path.stem:
            return sch
    return None


def _list_demo_pcbs(demos_root: Path) -> List[Path]:
    if not demos_root.exists():
        return []
    return sorted(p for p in demos_root.rglob("*.kicad_pcb") if p.is_file())


def _api_call(client, url: str, *, pcb: Path, sch: Optional[Path] = None) -> Tuple[bool, Dict]:
    headers = {"X-API-Key": "testkey"}
    data = {
        "pcb_file": (io.BytesIO(pcb.read_bytes()), pcb.name),
    }
    if sch is not None:
        data["sch_file"] = (io.BytesIO(sch.read_bytes()), sch.name)
    resp = client.post(url, data=data, headers=headers, content_type="multipart/form-data")
    try:
        payload = resp.get_json() or {}
    except Exception:
        payload = {"_raw": resp.data.decode("utf-8", errors="replace")}
    return (resp.status_code == 200 and payload.get("status") == "success", payload)


def main() -> int:
    ap = argparse.ArgumentParser(description="Regression run for Circuit-AI KiCad deliverables endpoints using KiCad demos.")
    ap.add_argument("--demos-root", default="/usr/share/kicad/demos", help="Root directory to search for *.kicad_pcb files")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of PCBs (0 = no limit)")
    ap.add_argument("--out", default="", help="Write JSON results to this path")
    args = ap.parse_args()

    os.environ.setdefault("CIRCUIT_AI_API_KEYS", "testkey")
    os.environ.setdefault("CIRCUIT_AI_REQUIRE_API_KEY", "1")

    # Ensure repo root on sys.path when executed as `python scripts/...`.
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

    # Import after env vars set.
    from api_server import app  # type: ignore

    pcbs = _list_demo_pcbs(Path(args.demos_root))
    if args.limit and args.limit > 0:
        pcbs = pcbs[: args.limit]

    if not pcbs:
        print(f"No KiCad PCB demos found under: {args.demos_root}", file=sys.stderr)
        return 2

    results: List[CaseResult] = []
    t0 = time.time()
    with app.test_client() as client:
        for pcb in pcbs:
            start = time.time()
            errors: List[str] = []
            sch = _guess_schematic_for_pcb(pcb)

            ok_pnp, pnp_payload = _api_call(client, "/api/v2/manufacture/pnp", pcb=pcb)
            if not ok_pnp:
                errors.append(f"pnp_failed: {pnp_payload.get('error') or pnp_payload}")

            ok_dfm, dfm_payload = _api_call(client, "/api/v2/report/dfm", pcb=pcb)
            if not ok_dfm:
                errors.append(f"dfm_failed: {dfm_payload.get('error') or dfm_payload}")

            ok_pkg, pkg_payload = _api_call(client, "/api/v2/manufacture/package", pcb=pcb, sch=sch)
            if not ok_pkg:
                errors.append(f"package_failed: {pkg_payload.get('error') or pkg_payload}")

            # If package built, ensure download is a valid ZIP and contains expected filenames.
            if ok_pkg and isinstance(pkg_payload.get("download_url"), str):
                dl = pkg_payload["download_url"]
                headers = {"X-API-Key": "testkey"}
                dl_resp = client.get(dl, headers=headers)
                if dl_resp.status_code != 200:
                    ok_pkg = False
                    errors.append(f"package_download_failed: http_{dl_resp.status_code}")
                else:
                    try:
                        z = zipfile.ZipFile(io.BytesIO(dl_resp.data))
                        names = set(z.namelist())
                        for required in ("DFM_REPORT.md", "PnP.csv", "Gerbers.zip", "MANIFEST.json"):
                            if required not in names:
                                ok_pkg = False
                                errors.append(f"package_missing:{required}")
                        z.close()
                    except Exception as e:
                        ok_pkg = False
                        errors.append(f"package_zip_invalid:{e}")

            seconds = time.time() - start
            results.append(
                CaseResult(
                    name=pcb.stem,
                    pcb_path=str(pcb),
                    sch_path=str(sch) if sch else None,
                    ok=(not errors),
                    pnp_ok=ok_pnp,
                    pnp_export_method=pnp_payload.get("export_method"),
                    dfm_ok=ok_dfm,
                    package_ok=ok_pkg,
                    gerbers_export_method=pkg_payload.get("export_method") if ok_pkg else None,
                    netlist_export_method=pkg_payload.get("netlist_export_method") if ok_pkg else None,
                    errors=errors,
                    seconds=seconds,
                )
            )

    passed = sum(1 for r in results if r.ok)
    failed = len(results) - passed
    elapsed = time.time() - t0

    summary = {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "seconds": elapsed,
        "results": [asdict(r) for r in results],
    }

    if args.out:
        Path(args.out).write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Total: {len(results)}  Passed: {passed}  Failed: {failed}  Seconds: {elapsed:.1f}")
    if failed:
        for r in results:
            if not r.ok:
                print(f"- FAIL {r.name}: {r.errors}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
