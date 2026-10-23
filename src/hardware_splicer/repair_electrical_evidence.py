"""KiCad source-netlist and operator-claimed measurement reconciliation.

Accepts a KiCad CLI *netlist export*, not raw .kicad_sch, and a bounded CSV.
Pin membership can be source-matched; physical readings/causality cannot be
independently verified through a self-reported CSV.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from .netlist.import_kicad import parse_kicad_netlist

SCHEMA = "hardware_splicer.repair_electrical_evidence.v1"
FIELDS = ("observation_id", "observed_at", "component_ref", "pin",
          "measurement_kind", "value", "unit", "instrument_id",
          "operator_id", "condition")
KINDS = {"dc_voltage": "V", "resistance": "ohm", "continuity": "boolean"}


def _read(path: str | Path, max_size: int) -> bytes:
    raw = Path(path).read_bytes()
    if len(raw) > max_size:
        raise ValueError("evidence input exceeds maximum supported size")
    return raw


def _timestamp(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValueError("observed_at must be a timezone-aware ISO-8601 timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("observed_at requires an explicit timezone")
    return dt.isoformat()


def capture_repair_evidence(netlist_file: str | Path, csv_file: str | Path) -> dict[str, Any]:
    net_bytes = _read(netlist_file, 2_000_000)
    csv_bytes = _read(csv_file, 500_000)
    netlist = parse_kicad_netlist(net_bytes.decode("utf-8"))
    if not netlist.components or not netlist.nets:
        raise ValueError("source netlist lacks components or nets")
    refs = [c.ref for c in netlist.components]
    if len(refs) != len(set(refs)):
        raise ValueError("duplicate component references in source netlist")
    pin_map: dict[tuple[str, str], set[str]] = {}
    for net in netlist.nets:
        for pin in net.pins:
            if pin.component_ref not in refs:
                raise ValueError("net references unknown component")
            pin_map.setdefault((pin.component_ref, pin.pin), set()).add(net.name)
    if not pin_map or any(len(nets) != 1 for nets in pin_map.values()):
        raise ValueError("netlist has absent or multiply-assigned pin connectivity")
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
    if not reader.fieldnames or len(reader.fieldnames) != len(FIELDS) or set(reader.fieldnames) != set(FIELDS):
        raise ValueError("CSV requires exactly: " + ", ".join(FIELDS))
    observed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row_number, item in enumerate(reader, 1):
        if row_number > 2000:
            raise ValueError("too many observations")
        if None in item or any(v is None for v in item.values()):
            raise ValueError("CSV row is malformed")
        values = {name: str(item[name]).strip() for name in FIELDS}
        identifier = values["observation_id"]
        if not identifier or identifier in seen:
            raise ValueError("missing/duplicate observation ID")
        seen.add(identifier)
        endpoint = (values["component_ref"], values["pin"])
        if endpoint not in pin_map:
            raise ValueError(f"unmapped source pin {endpoint[0]}.{endpoint[1]}")
        kind = values["measurement_kind"]
        if kind not in KINDS or values["unit"] != KINDS[kind]:
            raise ValueError("invalid measurement kind/unit pair")
        if not values["instrument_id"] or not values["operator_id"] or not values["condition"]:
            raise ValueError("measurements require instrument/operator/condition identity")
        try:
            reading = float(values["value"])
        except ValueError as exc:
            raise ValueError("reading must be numeric") from exc
        if not math.isfinite(reading) or kind == "resistance" and reading < 0 or kind == "continuity" and reading not in (0, 1):
            raise ValueError("invalid measurement value")
        observed.append({
            "observation_id": identifier,
            "observed_at": _timestamp(values["observed_at"]),
            "component_ref": endpoint[0], "pin": endpoint[1],
            "net": next(iter(pin_map[endpoint])),
            "kind": kind, "value": reading, "unit": KINDS[kind],
            "instrument_id": values["instrument_id"],
            "operator_id": values["operator_id"],
            "condition": values["condition"],
            "evidence_status": "operator_claim_not_instrument_authenticated",
        })
    if not observed:
        raise ValueError("no operator observations supplied")
    groups: dict[tuple[str,str,str,str],list[dict[str,Any]]] = {}
    for row in observed:
        key=(row["component_ref"],row["pin"],row["kind"],row["instrument_id"])
        groups.setdefault(key,[]).append(row)
    changes=[]
    for key, rows in sorted(groups.items()):
        rows=sorted(rows,key=lambda r:(r["observed_at"],r["observation_id"]))
        for earlier,later in zip(rows,rows[1:]):
            if earlier["condition"] == later["condition"]:
                continue
            changes.append({
                "component_pin": f"{key[0]}.{key[1]}",
                "source_net": earlier["net"],
                "from_observation": earlier["observation_id"],
                "to_observation": later["observation_id"],
                "delta": round(later["value"]-earlier["value"],12),
                "unit": earlier["unit"],
                "meaning": "operator_reported_condition_delta_not_component_causation",
            })
    return {
        "schema_version": SCHEMA,
        "status": "pin_mapping_checked_operator_readings_unverified",
        "netlist": {
            "sha256": hashlib.sha256(net_bytes).hexdigest(),
            "components": len(netlist.components), "nets": len(netlist.nets),
            "pins_mapped": len(pin_map),
            "source": "kicad_sexpr_netlist_export",
            "independent_erc_verified": False,
        },
        "measurements": {
            "sha256": hashlib.sha256(csv_bytes).hexdigest(),
            "count": len(observed), "instrument_authenticated": False,
        },
        "observations": observed,
        "condition_changes": changes,
        "repair_path_authority": "none",
        "failed_component_identified": False,
        "physical_repair_verified": False,
        "power_on_authorized": False,
        "next_action": "Verify source revision, instrument calibration and probe reference before deriving any engineering conclusion. A shared net is not a functional fault path.",
    }


def write_repair_evidence(netlist_file: str | Path, csv_file: str | Path, output: str | Path) -> dict[str,Any]:
    report=capture_repair_evidence(netlist_file,csv_file)
    out=Path(output)
    out.mkdir(parents=True, exist_ok=True)
    (out/"REPAIR_ELECTRICAL_EVIDENCE.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    md=[
        "# Hardware Splicer — repair electrical evidence", "",
        "**Source pin references matched; readings NOT instrument-authenticated.**", "",
        f"- Netlist components: {report['netlist']['components']}",
        f"- Netlist nets: {report['netlist']['nets']}",
        f"- Matched measurement observations: {report['measurements']['count']}",
        f"- Condition-only differences: {len(report['condition_changes'])}", "",
        "**No diagnosis, physical repair or authorization to power equipment was established.**", "",
        report["next_action"], "",
    ]
    (out/"REPAIR_ELECTRICAL_EVIDENCE.md").write_text("\n".join(md),encoding="utf-8")
    return report


def main() -> None:
    parser=argparse.ArgumentParser(description="Reconcile claimed measurements with KiCad netlist pin membership")
    parser.add_argument("--netlist",required=True,type=Path)
    parser.add_argument("--csv",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    result=write_repair_evidence(args.netlist,args.csv,args.out)
    print(json.dumps({"netlist":result["netlist"],"measurements":result["measurements"],
        "condition_changes":len(result["condition_changes"]),"physical_repair_verified":False}))


if __name__=="__main__":
    main()
