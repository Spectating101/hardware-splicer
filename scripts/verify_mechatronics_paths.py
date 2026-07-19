#!/usr/bin/env python3
"""Money-path electrical bar + firmware + mechanism pack (offline mechatronics)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_LLM", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_VISION", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
os.environ.setdefault("QWEN_DISABLED", "1")
os.environ.setdefault("HARDWARE_SPLICER_SKIP_VISION_LIVE", "1")
os.environ.setdefault("HARDWARE_SPLICER_AUTOROUTE", "0")
os.environ.setdefault("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")

# Reuse electrical checks from money-path verifier
sys.path.insert(0, str(ROOT / "scripts"))
from verify_money_paths import _eval_path  # noqa: E402

from hardware_splicer.mechanism_bridge import mechanism_kinds_present  # noqa: E402


def _eval_mechatronics(spec: Mapping[str, Any], out_root: Path) -> Dict[str, Any]:
    row = _eval_path(spec, out_root)
    failures: List[str] = list(row.get("failures") or [])
    out_dir = Path(str(row["out_dir"]))

    # Firmware bar
    require_fw = spec.get("require_firmware", True)
    fw_meta = out_dir / "firmware" / "FIRMWARE_SCAFFOLD.json"
    fw: Dict[str, Any] = {}
    if fw_meta.is_file():
        fw = json.loads(fw_meta.read_text(encoding="utf-8"))
    elif require_fw:
        failures.append("firmware scaffold missing")

    if require_fw and fw:
        src = str(fw.get("source") or "")
        if len(src.strip()) < 40:
            failures.append("firmware source too thin")
        min_pins = int(spec.get("min_firmware_pins") or 0)
        pins = {k: v for k, v in dict(fw.get("pins") or {}).items() if k not in {"sourced_from_graph", "sourced_from_bringup"}}
        if min_pins and len(pins) < min_pins:
            # Allow sketches that embed defaults (relay/fan/servo) when bring-up sparse
            if not any(tok in src for tok in ("RELAY_PIN", "FAN_PIN", "PAN_PIN", "PUMP_PIN", "IN1", "SOIL_PIN", "DHT")):
                failures.append(f"firmware pins {len(pins)} < {min_pins}")
        for token in spec.get("require_firmware_tokens") or []:
            if token not in src:
                failures.append(f"firmware missing token {token}")

    # Mechanism bar
    require_mech = spec.get("require_mechanism", True)
    mech_path = out_dir / "MECHANISM_PACK.json"
    pack_path = out_dir / "MECHATRONICS_PACK.json"
    mech: Dict[str, Any] = {}
    if mech_path.is_file():
        mech = json.loads(mech_path.read_text(encoding="utf-8"))
    elif require_mech:
        failures.append("MECHANISM_PACK.json missing")

    if require_mech and mech:
        status = str(mech.get("status") or "")
        if status not in {"ok", "planned"}:
            if status == "degraded" and not spec.get("allow_mechanism_degraded"):
                failures.append(f"mechanism degraded: {mech.get('degraded_reason')}")
        if status == "planned":
            failures.append("mechanism still planned (not materialized)")
        kinds = set(mechanism_kinds_present(mech))
        want = set(spec.get("mechanism_kinds_any") or [])
        if want and not (kinds & want):
            failures.append(f"mechanism kinds {sorted(kinds)} miss any of {sorted(want)}")
        outputs = list(mech.get("outputs") or [])
        if status == "ok" and not outputs and not (out_dir / "mecha_bundle").is_dir():
            failures.append("mechanism ok but no outputs/bundle")

    if require_mech and not pack_path.is_file():
        failures.append("MECHATRONICS_PACK.json missing")

    auth_path = out_dir / "MECHATRONICS_AUTHORITY.json"
    if spec.get("require_authority", True):
        if not auth_path.is_file():
            failures.append("MECHATRONICS_AUTHORITY.json missing")
        else:
            auth = json.loads(auth_path.read_text(encoding="utf-8"))
            offline = dict(auth.get("offline_pack") or {})
            level = str(auth.get("current_authority_level") or "")
            # Prefer honest offline_pack.ready over faking production ladder stages
            if offline.get("ready") is True:
                if auth.get("production_authorized") is True:
                    failures.append("production_authorized without closed production stage")
            elif level in {"", "no_mechatronics_authority"} and not spec.get("allow_no_authority"):
                failures.append(
                    f"authority not ready (level={level!r}, offline_pack.ready={offline.get('ready')})"
                )

    row["failures"] = failures
    row["passed"] = not failures
    row["mechanism_kind"] = mech.get("kind")
    row["mechanism_status"] = mech.get("status")
    row["firmware_file"] = fw.get("filename")
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "examples" / "money_paths" / "manifest.json",
    )
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_mechatronics_paths"))
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    paths = list(manifest.get("paths") or [])
    if args.path:
        want = set(args.path)
        paths = [p for p in paths if p.get("path_id") in want]

    # Default mechatronics requirements when not specified
    defaults = {
        "require_firmware": True,
        "require_mechanism": True,
        "require_authority": True,
        "min_firmware_pins": 0,
    }

    out_root = args.out.resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    rows = []
    for spec in paths:
        merged = {**defaults, **spec}
        print(f"→ {merged['path_id']} …", flush=True)
        rows.append(_eval_mechatronics(merged, out_root))

    passed = sum(1 for r in rows if r["passed"])
    report = {
        "schema_version": "hardware_splicer.mechatronics_paths_verify.v1",
        "passed_count": passed,
        "path_count": len(rows),
        "all_passed": passed == len(rows) and len(rows) > 0,
        "paths": rows,
    }
    report_path = out_root / "MECHATRONICS_PATHS_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = [f"# Mechatronics paths: {passed}/{len(rows)} passed", ""]
    for r in rows:
        status = "PASS" if r["passed"] else "FAIL"
        md.append(
            f"- **{status}** `{r['path_id']}` mech={r.get('mechanism_kind')}/{r.get('mechanism_status')} fw={r.get('firmware_file')}"
        )
        for f in r.get("failures") or []:
            md.append(f"  - {f}")
    (out_root / "MECHATRONICS_PATHS_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Mechatronics paths: {passed}/{len(rows)} passed")
        print(f"report: {report_path}")
        for r in rows:
            status = "PASS" if r["passed"] else "FAIL"
            print(
                f"  [{status}] {r['path_id']} build={r.get('build_id')} "
                f"mech={r.get('mechanism_kind')}/{r.get('mechanism_status')}"
            )
            for f in r.get("failures") or []:
                print(f"         - {f}")

    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
