"""Source quality and build-authority gates for replaceable compute carriers.

Only evidence-backed interface contracts may advance toward ECAD. Radxa's
current agent-facing hardware-db contains cloned placeholder pinout and power
files for distinct CM4/CM5 modules; shared pinout data is NOT compatibility.
Manufacturer PDFs/pinouts and reuse of vendor carrier CAD still require
independent pin, voltage, layout, and thermal verification by HS.

This tool does not create a routed board or imply an operational prototype.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping


SCHEMA = "hs.compute_carrier_evidence.v1"
OUTPUT_SCHEMA = "hs.compute_carrier_reference_gate.v1"
EXPECTED_MODULES = {"radxa_cm4_rk3576", "radxa_cm5_rk3588s2", "samsung_s21_donor"}
EXPECTED_SOC = {"radxa_cm4_rk3576": "RK3576(J)", "radxa_cm5_rk3588s2": "RK3588S2"}
DANGEROUS_PIN_IDS = {94, 96, 98}
ESSENTIAL_DEVICE_FUNCTIONS = {"system_power", "touch_and_keyboard", "video", "recovery", "comms", "thermal"}


class CarrierGateError(ValueError):
    """Invalid contract or unsupported board compatibility claim."""


def assess(source: bytes) -> dict[str, Any]:
    try:
        obj = json.loads(source)
    except (ValueError, UnicodeDecodeError) as exc:
        raise CarrierGateError("invalid reference source JSON") from exc
    if not isinstance(obj, dict) or obj.get("schema") != SCHEMA:
        raise CarrierGateError("unknown compute-carrier source schema")
    if obj.get("reference_repo") != "radxa/radxa-som-projects" or not obj.get("reference_commit"):
        raise CarrierGateError("missing pinned source-of-truth revision")
    modules = obj.get("modules")
    if not isinstance(modules, list) or len(modules) != 3:
        raise CarrierGateError("missing candidate modules")
    by_id = {x.get("id"): x for x in modules if isinstance(x, dict)}
    if set(by_id) != EXPECTED_MODULES:
        raise CarrierGateError("candidate identities missing or duplicated")
    issues: list[dict[str, str]] = []
    def block(code: str, scope: str, detail: str) -> None:
        issues.append({"code": code, "scope": scope, "detail": detail})
    vendor = [by_id[k] for k in ("radxa_cm4_rk3576", "radxa_cm5_rk3588s2")]
    for m in vendor:
        mid = m["id"]
        if m.get("soc") != EXPECTED_SOC[mid] or m.get("vendor_connector_count") != 3 or m.get("vendor_pins_per_connector") != 100:
            raise CarrierGateError(f"{mid}: wrong module silicon or vendor connector family")
        if m.get("vendor_pitch_mm") != .4 or m.get("physical_nominal_mm") != [55, 40]:
            raise CarrierGateError(f"{mid}: nominal module/connector geometry mismatch")
        if mid == "radxa_cm5_rk3588s2":
            references = m.get("mechanical_conflicting_vendor_references", [])
            unique = {tuple(x.get("dimensions_mm", [])) for x in references if isinstance(x, dict)}
            if len(unique) < 2 or (55,40) not in unique or (56,41) not in unique:
                raise CarrierGateError("known CM5 55x40 vs 56x41 vendor drawing conflict omitted")
            block("vendor_dimension_reference_conflict", mid,
                  "CM5 product page says 56x41mm; docs say 55x40mm; actual vendor DXF+STEP must govern fitting")
        if not m.get("official_carrier_design") or not m.get("kicad_community"):
            block("missing_reference_cad", mid, "vendor carrier and open KiCad library must be traced")
        db = m.get("agent_hardware_db")
        if not isinstance(db, dict) or not db.get("pinout_blob_sha") or not db.get("power_blob_sha"):
            raise CarrierGateError(f"{mid}: missing source database provenance")
        if db.get("board_soc") != EXPECTED_SOC[mid]:
            block("upstream_soc_metadata_conflict", mid,
                  f"agent-db soc={db.get('board_soc')} differs from official {EXPECTED_SOC[mid]}")
        if db.get("placeholder_pin_names_present"):
            block("upstream_placeholder_pin_map", mid, "agent-db PIN_N is not a verified signal mapping")
        if db.get("power_fields_unknown"):
            block("upstream_missing_voltage_limits", mid, "no verified module input or rail limits")
        if not m.get("pinout_verified_against_vendor_schematic"):
            block("pinout_not_approved", mid, "vendor XLSX+schematic contact-by-contact comparison required")
        if not m.get("board_power_characterized"):
            block("power_not_characterized", mid, "voltage, current, startup and power sequencing unverified")
        if not m.get("revision_and_mechanical_fit_validated_by_hs"):
            block("mechanical_not_verified", mid, "connector heights, keep-outs, footprint revision unverified")
        if not m.get("source_reuse_cleared"):
            block("reference_license_unresolved", mid, "verify vendor CAD reuse rights and preserve MIT notices")
    da, db = [m["agent_hardware_db"] for m in vendor]
    if da["pinout_blob_sha"] == db["pinout_blob_sha"]:
        block("identical_upstream_pinout_blobs", "cm4_cm5",
              "distinct SoCs share the exact upstream placeholder pinout blob; NOT evidence of electrical equivalence")
    if da["power_blob_sha"] == db["power_blob_sha"]:
        block("identical_upstream_power_blobs", "cm4_cm5",
              "identical unknown power blob is NOT shared rail compatibility")
    standards = {x.get("id"): x for x in obj.get("alternative_standards", [])}
    if set(standards) != {"sget_smarc_sdt01", "sget_osm_sdt05"}:
        raise CarrierGateError("missing actual industry-standard alternatives")
    if standards["sget_osm_sdt05"].get("interchange") != "SOLDERED_NOT_FIELD_SWAPPABLE":
        raise CarrierGateError("OSM is soldered; cannot claim field replaceability")
    if standards["sget_smarc_sdt01"].get("edge_contact_count") != 314:
        raise CarrierGateError("SMARC connector contract invalid")
    market = {x.get("id"): x for x in obj.get("current_taiwan_market_reference", [])}
    cm4_price = market.get("radxa_cm4_4gb_32gb_icshop", {})
    donor = market.get("used_s21_prior_research", {})
    if (cm4_price.get("listed_twd") != 4200 or cm4_price.get("availability") != "SOLD_OUT"
            or donor.get("listed_twd") != 1600 or donor.get("availability") != "UNVERIFIED_USED_LISTING"):
        raise CarrierGateError("cost comparison sources altered or incorrectly classified")
    block("no_reproducible_supply_quote", "commercial",
          "local 4GB CM4 offer sold out; used donor ask not a stable supplier quotation")
    known = obj.get("source_known_hazards")
    if not isinstance(known, list) or {x.get("id") for x in known} != {
        "radxa_cm3_to_cm5_5v_gpio", "radxa_cm3j_to_cm5_not_dropin", "radxa_cm4_to_cm5_pinout_unverified"
    }:
        raise CarrierGateError("vendor safety exceptions missing")
    danger = next(x for x in known if x["id"] == "radxa_cm3_to_cm5_5v_gpio")
    if set(danger.get("pins", [])) != DANGEROUS_PIN_IDS or danger.get("severity") != "DO_NOT_POWER_ON":
        raise CarrierGateError("critical 5V-to-GPIO vendor warning modified")
    block("direct_socket_swap_not_proven", "cm4_cm5",
          "CM4 vs CM5 contact-level signals, voltage domains and support circuits not independently verified")
    phone = by_id["samsung_s21_donor"]
    for field in ("connector_pinout_verified", "boot_without_oem_screen_battery_verified",
                  "usb_display_output_on_sample_verified", "board_power_characterized",
                  "revision_and_mechanical_fit_validated_by_hs"):
        if not phone.get(field):
            block("donor_dependency_unverified", "s21_donor", field)
    if phone.get("official_carrier_design"):
        raise CarrierGateError("proprietary phone motherboard cannot claim public vendor carrier CAD")
    device = obj.get("device_contract")
    if not isinstance(device, dict) or device.get("independent_module_adapters_required") is not True:
        raise CarrierGateError("must require distinct validated compute adapters")
    if device.get("interface_scope") != "LOGICAL_SUBSYSTEM_CONTRACT_ONLY_NO_PHYSICAL_PIN_ALLOCATION":
        raise CarrierGateError("logical services cannot be promoted to a physical pinout")
    funcs = device.get("functions")
    if not isinstance(funcs, list) or {x.get("name") for x in funcs} != ESSENTIAL_DEVICE_FUNCTIONS:
        raise CarrierGateError("incomplete common motherboard subsystem contract")
    for item in funcs:
        if item.get("state") != "MAPPED_AND_ELECTRICALLY_VERIFIED":
            block("device_function_not_mapped", item["name"], "adapter-specific electrical contact/voltage map missing")
    if obj.get("active_cad_outputs", 0) == 0:
        block("no_design_artifacts", "hs_carrier", "no HS-generated schematic, board, ERC/DRC or fab package")
    for key in ("independent_erc_pass", "independent_drc_pass", "high_speed_signal_integrity_pass"):
        if obj.get(key) is not True:
            block(key + "_missing", "hs_carrier", "independent electrical/layout validation required")
    if not obj.get("physical_test_pass"):
        block("physical_test_missing", "hs_carrier", "assembled board and real boot/load/thermal tests not recorded")
    # Do not conflate a logical interface contract with a safe PCB layout or
    # actual module substitution; the vendor safety advisory remains open.
    return {
        "schema": OUTPUT_SCHEMA, "source_sha256": sha256(source).hexdigest(),
        "target": obj["target"], "reference_repo_commit": obj["reference_commit"],
        "compatible_compute_socket_claim": False,
        "architecture_candidate": "COMMON_LOGICAL_DEVICE_IO_WITH_DIFFERENT_PHYSICAL_COMPUTE_ADAPTERS",
        "source_designs_available": all(m.get("official_carrier_design") and m.get("kicad_community") for m in vendor),
        "upstream_db_trusted_for_pinout": False,
        "source_conflicts": [i for i in issues if i["code"].startswith(("upstream_", "identical_"))],
        "blockers": issues, "blocker_count": len(issues),
        "design_authorization": "RESEARCH_ONLY", "safe_to_fabricate": False,
        "safe_to_power_any_cross_module_swap": False,
        "operationally_verified": False,
        "next_gate": "Import a verified individual module pinout and vendor reference PCB, then derive separately routed adapters and run KiCad ERC/DRC and manual SI/power review."
    }
