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
    if not isinstance(value, str) or not value.endswith("Z"):
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
        receipt = _strict_json_document(session.read_text(encoding="utf-8"), "primary session")
        files = receipt["files"]
    except ScreeningError:
        raise
    except (KeyError, ValueError, OSError, TypeError) as exc:
        raise ScreeningError("Unreadable primary INA228 receipt") from exc
    if receipt.get("capture_kind") != "TEST_FIXTURE" or receipt.get("source_kind") != "register_fixture":
        raise ScreeningError("This screen only accepts original TEST_FIXTURE INA228 receipts")
    if not isinstance(files, dict):
        raise ScreeningError("INA228 receipt files must be an object")
    for name, file in (("samples.csv", primary), ("registers.jsonl", registers)):
        item = files.get(name)
        if not isinstance(item, dict) or not file.is_file() or item.get("sha256") != sha256(file):
            raise ScreeningError("Primary raw capture/receipt SHA mismatch: " + name)
        if type(item.get("bytes")) is not int or item["bytes"] != file.stat().st_size:
            raise ScreeningError("Primary raw capture/receipt size mismatch: " + name)
    count = receipt.get("completed_samples")
    if receipt.get("status") != "COMPLETE" or type(count) is not int or count < 3:
        raise ScreeningError("Incomplete INA228 receipt")
    return receipt


def _strict_json_document(text: str, label: str) -> dict:
    """Reject duplicate JSON keys and nonfinite pseudo-JSON before trusting a receipt."""
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ScreeningError(f"Duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ScreeningError(f"Nonfinite JSON constant in {label}: {value}")

    try:
        obj = json.loads(text, object_pairs_hook=unique_pairs, parse_constant=invalid_constant)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ScreeningError(f"Malformed JSON in {label}") from exc
    if not isinstance(obj, dict):
        raise ScreeningError(f"Expected JSON object in {label}")
    return obj


def _positive_setting(obj: dict, name: str) -> float:
    value = obj.get(name)
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ScreeningError(f"Invalid receipt configuration: {name}")
    return float(value)


def _signed_20bit_register(encoded: str, name: str) -> int:
    """Independent INA228 decode, mirroring producer's 3-byte signed-20 format."""
    if not isinstance(encoded, str) or len(encoded) != 6:
        raise ScreeningError(f"Malformed INA228 {name} register")
    try:
        raw = bytes.fromhex(encoded)
    except ValueError as exc:
        raise ScreeningError(f"Malformed INA228 {name} register") from exc
    if len(raw) != 3 or (raw[-1] & 0x0F):
        raise ScreeningError(f"INA228 {name} register has invalid reserved bits")
    value = int.from_bytes(raw, "big") >> 4
    value = value - (1 << 20) if (value & (1 << 19)) else value
    if value in (-(1 << 19), (1 << 19) - 1):
        raise ScreeningError(f"INA228 {name} register is saturated")
    return value


def _verify_register_trace(primary_rows: list[dict], session: dict, registers: Path) -> None:
    """Bind displayed CSV readings to raw registers, not merely to mutable file hashes.

    This tests internal source coherence, NOT the authenticity of hardware or
    receipt signing. An attacker who replaces raw registers and every pin still
    cannot be detected without external custody/attestation.
    """
    if type(session.get("completed_samples")) is not int or session["completed_samples"] != len(primary_rows):
        raise ScreeningError("INA228 session sample count disagrees with CSV")
    config, spec = session.get("configuration"), session.get("station_spec")
    if not isinstance(config, dict) or not isinstance(spec, dict):
        raise ScreeningError("INA228 receipt lacks configuration/station specification")
    bus_lsb = _positive_setting(config, "bus_lsb_v")
    shunt_lsb = _positive_setting(config, "shunt_lsb_v")
    current_lsb = _positive_setting(config, "current_lsb_a")
    shunt_cal = _positive_setting(config, "shunt_cal")
    shunt_ohms = _positive_setting(spec, "shunt_ohm")
    calibration_full_scale = _positive_setting(spec, "calibration_full_scale_a")
    max_v = _positive_setting(spec, "maximum_bus_voltage_v")
    max_i = _positive_setting(spec, "monitor_headroom_a")
    max_power = _positive_setting(spec, "maximum_power_w")
    cal_factor = 13107.2e6  # INA228 ADC range 0; matches HS dc_measurement_station.py
    expected_cal = round(cal_factor * (calibration_full_scale / (2 ** 19)) * shunt_ohms)
    if (not math.isclose(bus_lsb, 195.3125e-6, rel_tol=1e-12)
            or not math.isclose(shunt_lsb, 312.5e-9, rel_tol=1e-12)
            or shunt_cal != expected_cal
            or not math.isclose(current_lsb, expected_cal / (cal_factor * shunt_ohms), rel_tol=1e-12)):
        raise ScreeningError("INA228 receipt calibration does not agree with declared station")
    if (session.get("first_sample_utc") != primary_rows[0]["timestamp"].isoformat(timespec="microseconds").replace("+00:00", "Z")
            or session.get("last_sample_utc") != primary_rows[-1]["timestamp"].isoformat(timespec="microseconds").replace("+00:00", "Z")):
        raise ScreeningError("INA228 receipt first/last UTC disagrees with CSV")

    count = 0
    try:
        with registers.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle):
                if number >= len(primary_rows):
                    raise ScreeningError("INA228 raw register stream has excess samples")
                entry = _strict_json_document(line, f"INA228 register line {number + 1}")
                sample = primary_rows[number]
                if type(entry.get("index")) is not int or entry["index"] != number:
                    raise ScreeningError(f"INA228 raw index mismatch at {number}")
                if _time(entry.get("timestamp_utc", "")) != sample["timestamp"]:
                    raise ScreeningError(f"INA228 raw timestamp disagrees with CSV at {number}")
                raw = entry.get("registers_hex")
                if not isinstance(raw, dict) or set(raw) != {"vbus", "vshunt", "current"}:
                    raise ScreeningError(f"Missing INA228 raw register trio at {number}")
                decoded_v = _signed_20bit_register(raw["vbus"], "vbus") * bus_lsb
                decoded_i = _signed_20bit_register(raw["current"], "current") * current_lsb
                decoded_shunt = _signed_20bit_register(raw["vshunt"], "vshunt") * shunt_lsb
                if not (0 <= decoded_v <= max_v and 0 <= decoded_i <= max_i
                        and decoded_v * decoded_i <= max_power):
                    raise ScreeningError(f"Decoded INA228 source violates station envelope at {number}")
                quantization = 2 * shunt_lsb / shunt_ohms + 2 * current_lsb
                if abs(decoded_i - decoded_shunt / shunt_ohms) > quantization:
                    raise ScreeningError(f"INA228 source current/shunt inconsistency at {number}")
                expected = {"voltage_v": decoded_v, "current_a": decoded_i,
                            "shunt_voltage_v": decoded_shunt, "power_w": decoded_v * decoded_i}
                for field, derived in expected.items():
                    reported = entry.get(field)
                    if (type(reported) not in (int, float) or not math.isfinite(reported)
                            or not math.isclose(reported, derived, rel_tol=5e-11, abs_tol=5e-10)):
                        raise ScreeningError(f"INA228 raw register decode mismatch: {field} at {number}")
                for field in ("voltage_v", "current_a"):
                    if not math.isclose(sample[field], expected[field], rel_tol=5e-11, abs_tol=5e-10):
                        raise ScreeningError(f"Primary CSV does not match INA228 raw register: {field} at {number}")
                count += 1
    except OSError as exc:
        raise ScreeningError("INA228 raw register file unreadable") from exc
    if count != len(primary_rows):
        raise ScreeningError("INA228 raw register stream has missing samples")


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
    primary_session = _verify_primary(receipt, primary, registers)
    p = _read(primary, ("timestamp_utc", "voltage_v", "current_a"), max_gap_s)
    _verify_register_trace(p, primary_session, registers)
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
