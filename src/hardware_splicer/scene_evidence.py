"""Evidence records a scene manifest lists, read into one shape the device workspace can show.

A scene manifest may carry ``"evidence": [{"kind": ..., "path": ..., "label": ...}]`` with
repo-relative JSON or CSV paths under ``ALLOWED_ROOTS``. Each kind has a reader that keeps the
record's own words and numbers, adds nothing, and returns the source path and its SHA-256.

Kinds:
  strategy        an engineering decision: options with known costs, gaps and risks, and the choice
  simulation      a digital study's verification: scenarios, acceptance, scope limits
  design_receipt  a reference-design verification receipt: checks, authority, non-claims
  tool_run        a GitHub-signal capability verdict and the tool's findings
  bom_csv         a bill of materials with prices and their basis

``kicad_checks`` runs KiCad's own DRC and ERC on a revision's board files and names the parts each
violation involves, so a violation can be shown on the model.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path

ALLOWED_ROOTS = ("projects", "examples", "evidence", "hardware", "docs/status")
_REF = re.compile(r"\b([A-Z]{1,3}\d{1,3})\b")


class EvidenceError(ValueError):
    """A listed record is missing, outside the allowed roots, or not in the expected shape."""


def resolve(root: Path, relative: str) -> Path:
    path = Path(relative or "")
    if not relative or path.is_absolute() or ".." in path.parts or not any(
            path.as_posix().startswith(prefix + "/") for prefix in ALLOWED_ROOTS):
        raise EvidenceError("Evidence path is not an allowed repository path")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise EvidenceError("Evidence record not found")
    return resolved


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EvidenceError("Evidence record is not valid JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceError("Evidence record is not a JSON object")
    return value


def read_strategy(path: Path) -> dict:
    record = _json(path)
    decision = record.get("decision") or {}
    return {
        "objective": record.get("objective"),
        "constraints": record.get("constraints") or {},
        "options": [{
            "id": row.get("id"), "label": row.get("label"), "known_usd": row.get("known_usd"),
            "cost_basis": row.get("cost_basis"), "cost_complete": bool(row.get("cost_complete")),
            "included": row.get("included") or [], "missing": row.get("missing") or [],
            "engineering_status": row.get("engineering_status"), "procurement_status": row.get("procurement_status"),
            "risk": row.get("risk"), "source": row.get("source"),
        } for row in record.get("strategies") or []],
        "decision": {key: decision.get(key) for key in decision},
    }


_SIM_METRICS = ("seconds", "hover_error_m", "gust_recovery_error_m", "landing_speed_m_s", "max_tracking_tilt_deg",
                "tracking_rms_m", "peak_current_a_est", "consumed_mah_est", "fault_detected", "landed_contact")


def read_simulation(path: Path) -> dict:
    record = _json(path)
    scenarios = []
    for row in record.get("scenarios") or []:
        scenario = row.get("scenario") or {}
        metrics = row.get("metrics") or {}
        scenarios.append({
            "id": scenario.get("id"), "expected": scenario.get("expected"), "accepted": bool(row.get("accepted")),
            "extra_mass_g": scenario.get("extra_mass_g"), "motor_failure": scenario.get("motor_failure"),
            "metrics": {key: metrics.get(key) for key in _SIM_METRICS if key in metrics},
            "checks_failed": sorted(key for key, ok in (row.get("checks") or {}).items() if ok is False),
        })
    return {
        "requirements_met": record.get("requirements_met"), "scenarios": scenarios,
        "failed_checks": record.get("failed_checks") or [], "scope_limits": record.get("scope_limits") or [],
        "authorization": {key: record.get(key) for key in ("flight_authorized", "power_on_authorized",
                                                            "fabrication_authorized") if key in record},
    }


def read_design_receipt(path: Path) -> dict:
    record = _json(path)
    return {
        "design_id": record.get("design_id"), "result": record.get("result"),
        "checks": record.get("checks") or {}, "authority": record.get("authority") or {},
        "nonclaims": record.get("nonclaims") or [], "toolchain": record.get("toolchain") or {},
    }


def read_tool_run(path: Path) -> dict:
    verdict = _json(path)
    executed = [row for row in verdict.get("candidates") or [] if row.get("executed")]
    capability = verdict.get("capability") or {}
    findings = []
    findings_name = capability.get("diagnostics_file")
    if findings_name and (path.parent / findings_name).is_file():
        for row in _json(path.parent / findings_name).get("findings") or []:
            message = str(row.get("message") or "")
            findings.append({"code": row.get("code"), "severity": row.get("severity"), "message": message,
                             "parts": sorted(set(_REF.findall(message)) - {"GND"})})
    return {
        "tools": [{"repository": row.get("repository"), "commit_sha": row.get("commit_sha"),
                   "license": row.get("license_claim"), "state": row.get("state"), "url": row.get("url")}
                  for row in executed],
        "not_run": [{"repository": row.get("repository"), "reason": row.get("reason")}
                    for row in verdict.get("candidates") or [] if not row.get("executed")],
        "capability": {key: capability.get(key) for key in ("adapter", "compatible_input", "network", "sandbox")
                       if key in capability},
        "findings": findings,
    }


def read_bom_csv(path: Path) -> dict:
    try:
        rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))
    except (OSError, csv.Error) as exc:
        raise EvidenceError("BOM is not readable CSV") from exc
    lines, total, unpriced, bases = [], 0.0, [], {}
    for row in rows:
        quantity = _number(row.get("quantity") or row.get("qty") or "1") or 1.0
        price = _number(row.get("price_usd") or row.get("unit_price_usd") or "")
        basis = (row.get("price_basis") or "").strip() or ("unpriced" if price is None else "not stated")
        name = row.get("description") or row.get("name") or row.get("id") or row.get("reference") or ""
        line_total = None if price is None else round(price * quantity, 2)
        if line_total is None:
            unpriced.append(name)
        else:
            total += line_total
            bases[basis] = round(bases.get(basis, 0.0) + line_total, 2)
        lines.append({"id": row.get("id") or row.get("reference"), "name": name, "quantity": quantity,
                      "unit_usd": price, "line_usd": line_total, "basis": basis,
                      "open_issue": (row.get("open_issue") or "").strip() or None})
    return {"lines": lines, "known_total_usd": round(total, 2), "unpriced": unpriced, "by_basis": bases}


def _number(text: str) -> float | None:
    try:
        return float(str(text).strip().replace("$", "").replace(",", ""))
    except ValueError:
        return None


READERS = {"strategy": read_strategy, "simulation": read_simulation, "design_receipt": read_design_receipt,
           "tool_run": read_tool_run, "bom_csv": read_bom_csv}


def scene_evidence(root: Path, manifest: dict) -> list[dict]:
    out = []
    for entry in manifest.get("evidence") or []:
        if not isinstance(entry, dict) or entry.get("kind") not in READERS:
            continue
        base = {"kind": entry["kind"], "label": entry.get("label") or entry["kind"], "source": entry.get("path")}
        try:
            path = resolve(root, entry.get("path"))
            out.append({**base, "sha256": _sha(path), **READERS[entry["kind"]](path)})
        except EvidenceError as exc:
            out.append({**base, "error": str(exc)})
    return out


# ---- Live KiCad checks ------------------------------------------------------------------------

_OF_REF = re.compile(r"\bof ([A-Z]{1,3}\d{1,3})\b")


def _at(footprints: list[dict], pos: dict | None, margin: float = 1.0) -> str | None:
    """The footprint whose box (grown by margin) contains a KiCad position, else the nearest centre
    within 5 mm; None when nothing is that close."""
    if not pos or not footprints:
        return None
    x, y = pos.get("x"), pos.get("y")
    if x is None or y is None:
        return None
    inside = [fp for fp in footprints if fp["bbox"][0] - margin <= x <= fp["bbox"][2] + margin
              and fp["bbox"][1] - margin <= y <= fp["bbox"][3] + margin]
    if inside:
        return min(inside, key=lambda fp: (fp["bbox"][2] - fp["bbox"][0]) * (fp["bbox"][3] - fp["bbox"][1]))["ref"]
    def distance(fp):
        cx, cy = (fp["bbox"][0] + fp["bbox"][2]) / 2, (fp["bbox"][1] + fp["bbox"][3]) / 2
        return ((cx - x) ** 2 + (cy - y) ** 2) ** 0.5
    best = min(footprints, key=distance)
    return best["ref"] if distance(best) <= 5.0 else None


def _violations(report: dict, key: str, footprints: list[dict]) -> list[dict]:
    rows = []
    groups = report.get(key) or []
    if key == "sheets":  # ERC: violations live under each sheet
        groups = [violation for sheet in groups for violation in sheet.get("violations") or []]
    for violation in groups:
        items = violation.get("items") or []
        text = " ".join(str(item.get("description") or "") for item in items)
        named = set(_OF_REF.findall(text))
        located = {ref for item in items if (ref := _at(footprints, item.get("pos")))}
        # Nets the violation involves: "(nets GND and VBUS)" and each item's "[NET]".
        nets = set(re.findall(r"\[([^\]]+)\]", text))
        pair = re.search(r"nets? (\S+) and (\S+?)\)", str(violation.get("description") or ""))
        if pair:
            nets |= {pair.group(1), pair.group(2)}
        rows.append({
            "type": violation.get("type"), "severity": violation.get("severity"),
            "description": violation.get("description"),
            "items": [str(item.get("description") or "") for item in items][:4],
            "positions_mm": [item.get("pos") for item in items if item.get("pos")][:4],
            # Parts the violation names, then parts whose footprint its items sit in or next to.
            "parts": sorted(named | located),
            "parts_named": sorted(named),
            "nets": sorted(nets),
        })
    return rows


def summarise_kicad(drc: dict | None, erc: dict | None, footprints: list[dict] | None = None) -> dict:
    result = {"drc": None, "erc": None}
    for name, report, keys in (("drc", drc, ("violations", "unconnected_items", "schematic_parity")),
                               ("erc", erc, ("sheets",))):
        if report is None:
            continue
        rows = [dict(row, group=key) for key in keys for row in _violations(report, key, footprints or [])]
        counts = {}
        for row in rows:
            counts[row["severity"] or "unknown"] = counts.get(row["severity"] or "unknown", 0) + 1
        result[name] = {"kicad_version": report.get("kicad_version"), "counts": counts, "total": len(rows),
                        "violations": rows[:80]}
    return result
