#!/usr/bin/env python3
"""Enabot-class endgame bar across flagship money paths (offline)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_LLM", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_VISION", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
os.environ.setdefault("QWEN_DISABLED", "1")
os.environ.setdefault("HARDWARE_SPLICER_SKIP_VISION_LIVE", "1")
os.environ.setdefault("HARDWARE_SPLICER_AUTOROUTE", "0")
os.environ.setdefault("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")

from hardware_splicer.project_intake import load_project_intake, splice_and_build_from_intake


def _eval_path(spec: Mapping[str, Any], out_root: Path) -> Dict[str, Any]:
    failures: List[str] = []
    path_id = str(spec["path_id"])
    intake_path = ROOT / spec["intake"]
    out_dir = out_root / path_id
    out_dir.mkdir(parents=True, exist_ok=True)

    intake = load_project_intake(intake_path)
    result = splice_and_build_from_intake(
        intake,
        out_dir=out_dir,
        export_gerber=False,
        request_id=f"money_{path_id}",
    )
    package = dict(result.get("salvage_package") or {})
    resolved = list(package.get("resolved_modules") or [])
    bringup = dict(package.get("bringup_card") or {})
    bringup_md = str(bringup.get("markdown") or "")
    gap = dict(package.get("gap_analysis") or {})
    shopping = {str(r.get("module_id") or "") for r in (gap.get("shopping_list") or [])}
    overrides = dict(package.get("module_overrides") or {})
    roles = {str(r.get("role") or "") for r in resolved if r.get("role")}
    module_ids = {str(r.get("module_id") or "") for r in resolved if r.get("module_id")}
    build_id = (
        result.get("build_id")
        or (result.get("project") or {}).get("build_id")
        or package.get("recommended_build_id")
    )

    if spec.get("require_compile", True) and result.get("ok") is not True:
        failures.append(
            f"compile ok!=True (build_ready={ (result.get('design_quality_gate') or {}).get('build_ready') })"
        )

    expected = list(spec.get("expected_build_ids") or [])
    if expected and build_id not in expected:
        failures.append(f"build_id {build_id!r} not in {expected}")

    for role in spec.get("require_roles") or []:
        if role not in roles:
            # role may be filled via category
            if role == "mcu" and any(
                m in module_ids for m in ("esp32-devkit", "esp32-cam-module", "arduino-nano", "rpi-pico")
            ):
                continue
            failures.append(f"missing role {role}")

    any_mods = list(spec.get("require_module_ids_any") or [])
    if any_mods and not (module_ids & set(any_mods)):
        failures.append(f"missing any of modules {any_mods} (have {sorted(module_ids)})")

    for mid in spec.get("require_mcu_ids") or []:
        if mid not in module_ids and overrides.get("mcu") != mid:
            failures.append(f"MCU {mid} not selected")

    if spec.get("require_donor_drv"):
        if not any(
            r.get("source") == "donor_functional_salvage" and r.get("role") == "drv" for r in resolved
        ):
            failures.append("donor drv not bound")

    for mid in spec.get("forbid_gap_fill_drivers") or []:
        if any(r.get("source") == "gap_fill" and r.get("module_id") == mid for r in resolved):
            failures.append(f"gap_fill driver {mid}")

    refs_blob = " ".join(
        [bringup_md]
        + [str(c) for r in resolved for c in (r.get("connector_refs") or [])]
    )
    for label in spec.get("require_harness_labels") or []:
        if label not in refs_blob:
            failures.append(f"bringup/harness missing {label}")

    motors = [r for r in resolved if "motor" in str(r.get("module_id") or "").lower() or r.get("role") == "mot"]
    if spec.get("min_motors") and len(motors) < int(spec["min_motors"]):
        failures.append(f"motors {len(motors)} < {spec['min_motors']}")

    servos = [r for r in resolved if r.get("module_id") == "sg90"]
    if spec.get("min_servos") and len(servos) < int(spec["min_servos"]):
        failures.append(f"servos {len(servos)} < {spec['min_servos']}")

    for mid in spec.get("forbid_shopping") or []:
        if mid in shopping:
            failures.append(f"shopping asks for inventory part {mid}")

    fw_meta = out_dir / "firmware" / "FIRMWARE_SCAFFOLD.json"
    fw: Dict[str, Any] = {}
    if fw_meta.is_file():
        fw = json.loads(fw_meta.read_text(encoding="utf-8"))
    elif spec.get("require_dual_hbridge_firmware") or spec.get("require_firmware_pins_any"):
        failures.append("firmware scaffold missing")

    if spec.get("require_dual_hbridge_firmware"):
        src = str(fw.get("source") or "")
        pins = dict(fw.get("pins") or {})
        if "const int IN3" not in src or pins.get("in3") is None:
            failures.append("firmware not dual-channel")

    pin_any = list(spec.get("require_firmware_pins_any") or [])
    if pin_any and fw:
        pins = dict(fw.get("pins") or {})
        if not any(pins.get(k) is not None for k in pin_any):
            failures.append(f"firmware pins missing any of {pin_any}")

    if not (out_dir / "PROJECT_PACKAGE.json").is_file():
        failures.append("PROJECT_PACKAGE.json missing")

    bringup_json_path = out_dir / "BRINGUP_CARD.json"
    if result.get("ok") and bringup_json_path.is_file():
        bringup_body = json.loads(bringup_json_path.read_text(encoding="utf-8"))
        if not bringup_body.get("sourced_from_graph"):
            failures.append("bringup not regenerated from compiled build_graph")
    elif result.get("ok"):
        failures.append("BRINGUP_CARD.json missing after compile")

    if (result.get("project") or result.get("project_package") or {}).get("power_on_authorized") is True:
        failures.append("power_on_authorized without bench evidence")

    return {
        "path_id": path_id,
        "title": spec.get("title"),
        "passed": not failures,
        "build_id": build_id,
        "compile_ok": bool(result.get("ok")),
        "roles": sorted(roles),
        "module_ids": sorted(module_ids),
        "shopping": sorted(shopping),
        "failures": failures,
        "out_dir": str(out_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "examples" / "money_paths" / "manifest.json",
    )
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_money_paths"))
    parser.add_argument("--path", action="append", default=[], help="Run only these path_id values")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    paths = list(manifest.get("paths") or [])
    if args.path:
        want = set(args.path)
        paths = [p for p in paths if p.get("path_id") in want]

    out_root = args.out.resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    rows = []
    for spec in paths:
        print(f"→ {spec['path_id']} …", flush=True)
        rows.append(_eval_path(spec, out_root))

    passed = sum(1 for r in rows if r["passed"])
    report = {
        "schema_version": "hardware_splicer.money_paths_verify.v1",
        "passed_count": passed,
        "path_count": len(rows),
        "all_passed": passed == len(rows) and len(rows) > 0,
        "paths": rows,
    }
    report_path = out_root / "MONEY_PATHS_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = [
        f"# Money paths: {passed}/{len(rows)} passed",
        "",
    ]
    for r in rows:
        status = "PASS" if r["passed"] else "FAIL"
        md.append(f"- **{status}** `{r['path_id']}` → `{r.get('build_id')}`")
        for f in r.get("failures") or []:
            md.append(f"  - {f}")
    (out_root / "MONEY_PATHS_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Money paths: {passed}/{len(rows)} passed")
        print(f"report: {report_path}")
        for r in rows:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  [{status}] {r['path_id']} build={r.get('build_id')}")
            for f in r.get("failures") or []:
                print(f"         - {f}")

    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
