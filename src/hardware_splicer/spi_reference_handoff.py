"""Independent reference-design handoff audit: actual board, BOM and frozen receipt.

Does not re-run KiCad, authenticate external PDFs, or approve physical fabrication.
The reference's native KiCad 9 package builder remains the canonical Gerber
and remote-FCT generator; this file audits inputs before that handoff.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Mapping
from pathlib import Path

from .reference_device_dossier import build_reference_device_dossier

SCHEMA = "hardware_splicer.spi_reference_handoff_audit.v1"
# This mapping mirrors the frozen revision's RECEIPT_INPUTS. The receipt must
# bind *every* listed input; no partial/historic hash success is accepted.
RECEIPT_FILES = {
    "schematic": "spi_flash_adapter_v1.kicad_sch",
    "pcb": "spi_flash_adapter_v1.kicad_pcb",
    "project_rules": "spi_flash_adapter_v1.kicad_pro",
    "symbol_library": "HardwareSplicer.kicad_sym",
    "symbol_library_table": "sym-lib-table",
    "bom": "BOM.csv",
    "design_manifest": "design_manifest.json",
    "verifier": "verify_design.py",
    "electrical_contract": "design_checks.py",
}
CANONICAL_DNP = {"R1", "R4"}
J1_PIN_NETS = {
    "1": "HOST_3V3", "2": "GND", "3": "HOST_SCLK",
    "4": "HOST_MOSI", "5": "HOST_CS_N", "6": "HOST_MISO",
}


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return data


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_bom(path: Path) -> tuple[list[dict], list[str]]:
    reader = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")))
    required = {
        "References", "Quantity", "Value", "Manufacturer",
        "Manufacturer Part Number", "Footprint", "Initial Assembly",
    }
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError("BOM is missing required columns")
    flattened: list[dict] = []
    issues: list[str] = []
    seen = set()
    for line_no, row in enumerate(reader, start=2):
        refs = str(row["References"] or "").split()
        try:
            quantity = int(row["Quantity"])
        except (TypeError, ValueError):
            issues.append(f"BOM line {line_no}: quantity not integral")
            continue
        if not refs or quantity != len(refs):
            issues.append(f"BOM line {line_no}: reference count disagrees with quantity")
        if any(not row.get(field) for field in (
            "Manufacturer", "Manufacturer Part Number", "Footprint", "Value"
        )):
            issues.append(f"BOM line {line_no}: supplier/identity/footprint field missing")
        assembly = row.get("Initial Assembly")
        if assembly not in ("FIT", "DNP"):
            issues.append(f"BOM line {line_no}: unsupported assembly variant {assembly!r}")
        for ref in refs:
            if ref in seen:
                issues.append(f"BOM duplicate reference: {ref}")
            seen.add(ref)
            flattened.append({
                "ref": ref, "assembly": assembly,
                "manufacturer": row.get("Manufacturer"),
                "mpn": row.get("Manufacturer Part Number"),
                "value": row.get("Value"),
                "footprint": row.get("Footprint"),
                "purpose": row.get("Purpose") or "",
                "procurement_identity_documented": bool(row.get("Manufacturer Part Number")),
                "physical_part_inspected": False,
                "stock_and_price_verified": False,
            })
    return flattened, issues


def _reference_pinout_issues(assembly_plan: Mapping) -> list[str]:
    j1 = next((row for row in assembly_plan["connections"] if row["ref"] == "J1"), None)
    if j1 is None:
        return ["J1 missing from source KiCad connector topology"]
    actual = {str(row["pin"]): row["net"] for row in j1["pins"]}
    return [f"J1 pin {pin}: source net {actual.get(pin)!r}, expected {net!r}"
            for pin, net in J1_PIN_NETS.items() if actual.get(pin) != net]


def build_spi_reference_handoff(
    reference_dir: str | Path, *, output_dir: str | Path,
    enclosure_inner_mm: dict[str, float] | None = None,
) -> dict:
    reference = Path(reference_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    receipt = _read_json(reference / "verification.json")
    manifest = _read_json(reference / "design_manifest.json")

    # Reuse the source-file parser to tie the assembly plan to the exact PCB.
    dossier = build_reference_device_dossier(
        reference / "spi_flash_adapter_v1.kicad_pcb",
        output_dir=output,
        declared_internal_enclosure_mm=enclosure_inner_mm,
    )
    plan = _read_json(output / "REFERENCE_ASSEMBLY_PLAN.json")
    bom, issues = _read_bom(reference / "BOM.csv")

    receipt_hashes = receipt.get("artifact_sha256") or {}
    receipt_bindings = {}
    for role, filename in RECEIPT_FILES.items():
        path = reference / filename
        expected = receipt_hashes.get(role)
        actual = _file_hash(path) if path.is_file() else None
        matches = isinstance(expected, str) and len(expected) == 64 and expected == actual
        receipt_bindings[role] = {
            "file": filename, "receipt_sha256": expected, "actual_sha256": actual,
            "hash_matches_frozen_receipt": matches,
        }
        if not matches:
            issues.append(f"frozen verification receipt does not match current {role}")

    if receipt.get("result") != "pass":
        issues.append("historical native verifier receipt is not a pass")
    if not isinstance(receipt.get("checks"), dict):
        issues.append("native verification receipt lacks checks")
    else:
        for category, count in receipt["checks"].items():
            if isinstance(count, bool) or not isinstance(count, int) or count != 0:
                issues.append(f"historical native check is nonzero/invalid: {category}")
    if manifest.get("design_id") != receipt.get("design_id"):
        issues.append("manifest and verification receipt identify different designs")
    if receipt.get("authority", {}).get("physical_authority_granted") is not False:
        issues.append("historical receipt has unexpected physical authority")
    if receipt.get("authority", {}).get("fabrication_ready") is not False:
        issues.append("historical receipt does not retain fabrication block")

    actual_parts = {
        part["ref"]: part for part in plan["parts"]
        if part["kind"] not in ("testpoint", "mounting_hole")
    }
    bom_refs = {row["ref"] for row in bom}
    for ref in sorted(set(actual_parts) - bom_refs):
        issues.append(f"source PCB component not listed in BOM: {ref}")
    for ref in sorted(bom_refs - set(actual_parts)):
        issues.append(f"BOM part missing from PCB: {ref}")
    for row in bom:
        p = actual_parts.get(row["ref"])
        if p is None:
            continue
        if p["footprint"] != row["footprint"]:
            issues.append(f"{row['ref']} footprint mismatch: PCB {p['footprint']}, BOM {row['footprint']}")
        if bool(p["do_not_populate"]) != (row["assembly"] == "DNP"):
            issues.append(f"{row['ref']} source PCB vs BOM DNP contradiction")
        pcb_mpn = (p.get("identity") or {}).get("mpn")
        if pcb_mpn and pcb_mpn != row["mpn"]:
            issues.append(f"{row['ref']} manufacturer part number differs between PCB and BOM")
    configured_dnp = set(manifest.get("bringup_controls", {}).get("initial_dnp_references") or [])
    bom_dnp = {row["ref"] for row in bom if row["assembly"] == "DNP"}
    if configured_dnp != bom_dnp or configured_dnp != CANONICAL_DNP:
        issues.append("initial supply-isolation DNP controls disagree with BOM/manifest")
    if manifest.get("bringup_controls", {}).get("enable_shunt_initially_fitted") is not False:
        issues.append("JP1 enable shunt must be declared absent at first assembly")
    supplied_mpn = {row["mpn"] for row in bom}
    missing_key_parts = set(manifest.get("selected_components", {}).values()) - supplied_mpn
    if missing_key_parts:
        issues.append("selected design IC identities missing from BOM: " + ", ".join(sorted(missing_key_parts)))
    issues.extend(_reference_pinout_issues(plan))
    if len(bom) != 18:
        issues.append(f"unexpected number of purchasable component positions: {len(bom)}")
    if sum(row["assembly"] == "FIT" for row in bom) != 16:
        issues.append("initial assembly must have sixteen populated BOM positions")
    if sum(p["kind"] == "testpoint" for p in plan["parts"]) != 18:
        issues.append("test-pad geometry count differs from frozen contract")
    if sum(p["kind"] == "mounting_hole" for p in plan["parts"]) != 4:
        issues.append("mounting-hole geometry count differs from frozen contract")

    issues = sorted(set(issues))
    populated = [row for row in bom if row["assembly"] == "FIT"]
    not_fitted = [row for row in bom if row["assembly"] == "DNP"]
    # The assembly_plan's 'fitted' count includes test pads and hole footprints.
    # It MUST NOT be presented as a physical component procurement count.
    summary = {
        "schema": SCHEMA,
        "design_id": manifest.get("design_id"),
        "revision": manifest.get("revision"),
        "audit_status": "source_consistent_historical_receipt_only" if not issues else "blocked_source_inconsistency",
        "issues": issues,
        "source_receipt_bindings": receipt_bindings,
        "native_kicad_erc_drc_reexecuted": False,
        "historical_native_receipt_hash_bound": not any(not row["hash_matches_frozen_receipt"] for row in receipt_bindings.values()),
        "source_pcb_sha256": dossier["source"]["sha256"],
        "bom_total_positions": len(bom),
        "bom_to_fit": len(populated),
        "bom_dnp": len(not_fitted),
        "test_pad_footprints_not_purchase_parts": sum(p["kind"] == "testpoint" for p in plan["parts"]),
        "mounting_hole_footprints_not_purchase_parts": sum(p["kind"] == "mounting_hole" for p in plan["parts"]),
        "assembly_plan_fitted_footprints_including_board_features": dossier["fitted"],
        "bom_line_items": bom,
        "external_manufacturer_pdfs_refetched_or_authenticated": False,
        "vendor_stock_or_price_verified": False,
        "fabrication_files_generated_in_this_audit": False,
        "canonical_fabrication_path": "build_package.py (requires native KiCad 9 and an independently re-run verification)",
        "canonical_remote_test_path": "build_remote_fct_campaign.py (requires reviewed physical test provider)",
        "unpowered_validation_observed": False,
        "powered_validation_observed": False,
        "physical_authority_granted": False,
        "fabrication_authorized": False,
        "release_authorized": False,
        "unresolved_acceptance_gates": [
            "Independent EE sign-off of schematic, routed PCB, selected components and manufacturer datasheets",
            "KiCad 9 native ERC/DRC re-execution and revision-bound Gerber/NC drill/placement exports",
            "Fabrication stackup and package selection; actual vendor approval and availability",
            "Continuity, shorts, rail and timing measurement evidence after separately authorized assembly",
            "Read-only 0x9F response and waveform evidence from an independently reviewed powered bench procedure",
        ],
    }
    (output / "REFERENCE_HANDOFF_AUDIT.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output / "REFERENCE_ASSEMBLY_PICKLIST.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "ref", "assembly", "manufacturer", "mpn", "value", "footprint", "purpose",
        ])
        writer.writeheader()
        for part in bom:
            writer.writerow({key: part[key] for key in writer.fieldnames})
    review = [
        "# SPI flash adapter — evidence-bound pre-build handoff",
        "",
        f"Design: {summary['design_id']} / {summary['revision']}",
        f"Source consistency: {summary['audit_status']}",
        "This is a paper review aid, NOT an approved build, procurement or power-on instruction.",
        "",
        "## What to physically install",
        f"{len(populated)} BOM component positions initially FIT. Through-hole J1 and JP1 are included in those positions.",
        "Initial DNP: R1 and R4; JP1 header exists but **NO enable shunt** is fitted.",
        f"Do not order/solder {summary['test_pad_footprints_not_purchase_parts']} bare PCB test pads as separate parts.",
        f"The {summary['mounting_hole_footprints_not_purchase_parts']} mounting holes are board geometry; fastening hardware is not part of this electrical BOM.",
        "",
        "## Source-only steps (unpowered review)",
        "1. Compare exact manufacturer suffix/package and pins against frozen source documents.",
        "2. Review BOM-to-footprint parity, with R1/R4 left unpopulated.",
        "3. Inspect printed pin-1/orientation markings; verify J1 pin-to-net assignment.",
        "4. Verify 2D/3D component envelopes, through-hole accessibility and enclosure cutouts.",
        "5. Have an independent engineer review the existing controlled bring-up sequence before physical execution.",
        "",
        "## Open release gates",
        *[f"- {gate}" for gate in summary["unresolved_acceptance_gates"]],
    ]
    if issues:
        review.extend(["", "## Detected source inconsistencies", *[f"- {i}" for i in issues]])
    (output / "REFERENCE_PREBUILD_REVIEW.md").write_text("\n".join(review) + "\n", encoding="utf-8")
    return summary
