#!/usr/bin/env python3
"""Fail-closed, TEST_FIXTURE-only two-path measurement discrimination.

This is a separate experimental screen, not the frozen Policy Lab receiver.
It cannot establish physical calibration, independence, safety or fabrication.
The primary samples must match their INA228 acquisition receipt and raw
register stream. Reference CSV bytes are hashed but NOT physically authenticated.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path


class ScreeningError(ValueError):
    """Invalid evidence or a failed strict timebase/data-quality precondition."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _time(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ScreeningError("Timestamp must be explicitly UTC (Z)")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ScreeningError("Malformed UTC timestamp: " + repr(value)) from exc
    return result.astimezone(timezone.utc)


def _read(path: Path, names: tuple[str, ...], max_gap_s: float) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ScreeningError("Absent or duplicate CSV headers: " + str(path))
        if not set(names).issubset(reader.fieldnames):
            raise ScreeningError("Required columns missing: " + str(path))
        rows = []
        for index, raw in enumerate(reader, start=2):
            if None in raw:
                raise ScreeningError(f"Surplus CSV columns at line {index}")
            ts = _time(raw["timestamp_utc"])
            numbers = {}
            for key in names:
                if key == "timestamp_utc":
                    continue
                try:
                    number = float(raw[key])
                except (ValueError, TypeError) as exc:
                    raise ScreeningError(f"Bad {key} at line {index}") from exc
                if not math.isfinite(number) or number < 0:
                    raise ScreeningError(f"Nonfinite or negative {key} at line {index}")
                numbers[key] = number
            if rows:
                delta = (ts - rows[-1]["timestamp"]).total_seconds()
                if delta <= 0:
                    raise ScreeningError("Non-monotonic or duplicate timestamps")
                if delta > max_gap_s:
                    raise ScreeningError("Sampling gap exceeds configured maximum")
            rows.append({"timestamp": ts, **numbers})
    if len(rows) < 3:
        raise ScreeningError("At least three samples required")
    return rows


def _verify_primary(session: Path, primary: Path, registers: Path) -> dict:
    try:
        receipt = json.loads(session.read_text(encoding="utf-8"))
        files = receipt["files"]
    except (KeyError, ValueError, OSError) as exc:
        raise ScreeningError("Unreadable primary INA228 receipt") from exc
    if receipt.get("capture_kind") != "TEST_FIXTURE" or receipt.get("source_kind") != "register_fixture":
        raise ScreeningError("This screen only accepts original TEST_FIXTURE INA228 receipts")
    for name, file in (("samples.csv", primary), ("registers.jsonl", registers)):
        if not file.is_file() or files.get(name, {}).get("sha256") != sha256(file):
            raise ScreeningError("Primary raw capture/receipt SHA mismatch: " + name)
        if files[name].get("bytes") != file.stat().st_size:
            raise ScreeningError("Primary raw capture/receipt size mismatch: " + name)
    if receipt.get("status") != "COMPLETE" or receipt.get("completed_samples", 0) < 3:
        raise ScreeningError("Incomplete INA228 receipt")
    return receipt


def conservative_load_power_bound(max_bus_v: float, nominal_load_ohms: float,
                                  tolerance_pct: float, ceiling_w: float) -> dict:
    """Fault-free J2 load bound: P <= V_J2_max^2/Rmin.

    Requires a verified J2 voltage ceiling; software sampling alone cannot
    enforce that ceiling or capture transients. Does not bound faults,
    source energy, thermal conditions or fuse clearing.
    """
    for value in (max_bus_v, nominal_load_ohms, ceiling_w):
        if not math.isfinite(value) or value <= 0:
            raise ScreeningError("Positive finite bus, load and power required")
    if not math.isfinite(tolerance_pct) or not (0 <= tolerance_pct < 100):
        raise ScreeningError("Tolerance must be finite and in [0, 100)")
    min_load = nominal_load_ohms * (1 - tolerance_pct / 100)
    power_w = max_bus_v ** 2 / min_load
    return {
        "voltage_ceiling_v": max_bus_v,
        "nominal_load_ohms": nominal_load_ohms,
        "assumed_tolerance_pct": tolerance_pct,
        "minimum_load_ohms": min_load,
        "max_load_power_w_conservative": power_w,
        "maximum_load_current_a_conservative": max_bus_v / min_load,
        "claimed_power_ceiling_w": ceiling_w,
        "within_ceiling": power_w <= ceiling_w,
        "physical_part_selected": False,
        "physical_fault_protection_proven": False,
    }


def screen(primary: Path, reference: Path, receipt: Path, registers: Path,
           *, shunt_ohms: float = 0.01, max_gap_s: float = 1.5,
           max_pair_offset_ms: float = 200.0,
           diagnostic_threshold_pct: float = 0.75) -> dict:
    """Strict single-sample synchronous fixture screen; not metrological acceptance."""
    if not (math.isfinite(shunt_ohms) and shunt_ohms > 0):
        raise ScreeningError("Reference shunt resistance must be positive")
    if not (math.isfinite(max_gap_s) and max_gap_s > 0 and
            math.isfinite(max_pair_offset_ms) and max_pair_offset_ms > 0 and
            math.isfinite(diagnostic_threshold_pct) and diagnostic_threshold_pct > 0):
        raise ScreeningError("Screen thresholds must be positive and finite")
    _verify_primary(receipt, primary, registers)
    p = _read(primary, ("timestamp_utc", "voltage_v", "current_a"), max_gap_s)
    r = _read(reference, ("timestamp_utc", "voltage_v", "shunt_voltage_v"), max_gap_s)
    if len(p) != len(r):
        raise ScreeningError("Unpaired sample count: require strict one-to-one captures")
    powers_p, powers_r, offsets_ms, outliers = [], [], [], []
    for i, (a, b) in enumerate(zip(p, r)):
        lag = abs((a["timestamp"] - b["timestamp"]).total_seconds()) * 1000
        offsets_ms.append(lag)
        if lag > max_pair_offset_ms:
            raise ScreeningError(f"Unverified or excessive clock offset at sample {i}: {lag:.1f} ms")
        pa = a["voltage_v"] * a["current_a"]
        pb = b["voltage_v"] * b["shunt_voltage_v"] / shunt_ohms
        pct = 100 * abs(pb - pa) / max(abs(pa), 1e-12)
        powers_p.append(pa)
        powers_r.append(pb)
        if pct >= diagnostic_threshold_pct:
            outliers.append({"index": i, "disagreement_pct": pct})
    energy_p = 0.0
    energy_r = 0.0
    for i in range(1, len(p)):
        dt_hours = (p[i]["timestamp"] - p[i-1]["timestamp"]).total_seconds() / 3600
        energy_p += (powers_p[i] + powers_p[i-1]) * dt_hours / 2
        energy_r += (powers_r[i] + powers_r[i-1]) * dt_hours / 2
    total_diff = 100 * abs(energy_r - energy_p) / max(abs(energy_p), 1e-12)
    fails = bool(outliers) or total_diff >= diagnostic_threshold_pct
    return {
        "schema": "hardware_splicer.witness_fixture_discrimination.v1",
        "decision": "FAIL_FIXTURE_DISAGREEMENT" if fails else "PASS_FIXTURE_DISCRIMINATION_ONLY",
        "diagnostic_only": True,
        "fixture_only": True,
        "physical_ready": False,
        "metrological_agreement_proven": False,
        "fabrication_allowed": False,
        "reference_independence_verified": False,
        "reference_calibration_verified": False,
        "external_timebase_verified": False,
        "primary_receipt_verified": True,
        "reference_bytes_sha256": sha256(reference),
        "primary_bytes_sha256": sha256(primary),
        "samples_paired": len(p),
        "max_observed_sample_offset_ms": max(offsets_ms),
        "max_allowed_pair_offset_ms": max_pair_offset_ms,
        "diagnostic_threshold_pct": diagnostic_threshold_pct,
        "primary_energy_wh": energy_p,
        "reference_energy_wh": energy_r,
        "energy_disagreement_primary_denominator_pct": total_diff,
        "outlier_count": len(outliers),
        "outliers_first_10": outliers[:10],
        "note": "Relative difference uses primary denominator, not larger reading. Threshold is a synthetic sensitivity control, NOT an uncertainty-backed physical tolerance.",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--primary", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--primary-session", type=Path, required=True)
    p.add_argument("--primary-registers", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True, help="New JSON report (must not exist)")
    p.add_argument("--shunt-ohms", type=float, default=0.01)
    p.add_argument("--max-gap-s", type=float, default=1.5)
    p.add_argument("--max-pair-offset-ms", type=float, default=200)
    p.add_argument("--diagnostic-threshold-pct", type=float, default=0.75)
    args = p.parse_args(argv)
    if args.out.exists():
        p.error("Output report already exists; no overwriting evidence")
    try:
        result = screen(args.primary, args.reference, args.primary_session,
                        args.primary_registers, shunt_ohms=args.shunt_ohms,
                        max_gap_s=args.max_gap_s,
                        max_pair_offset_ms=args.max_pair_offset_ms,
                        diagnostic_threshold_pct=args.diagnostic_threshold_pct)
    except (ScreeningError, OSError) as exc:
        result = {"schema": "hardware_splicer.witness_fixture_discrimination.v1",
                  "decision": "INVALID_INPUT_HOLD", "reason": str(exc),
                  "physical_ready": False, "fabrication_allowed": False}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"decision": result["decision"], "out": str(args.out)}))
    return 0 if result["decision"] == "PASS_FIXTURE_DISCRIMINATION_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
