"""Manufacturer Radxa CM5 IO v2200 routed-pad extraction and revision gate.

This is NOT a full PCB netlist or schematic: PADS ASCII *ROUTE* entries show
only routed endpoint pairs. Other net assignments may be unrouted or single-
terminal. We use this to audit the corrected CM5 V2.21 contact-name library,
not to authorize board assembly or backfeed any module rail.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Mapping

SCHEMA = "hs.cm5_reference_board_routed_nets.v1"
BOARD_SHA256 = "b229b4c5960aad6376e60258b5a5cd62ea7c8e3f31fde94066ef850fb0e3eeed"
BOARD_SOURCE_URL = (
    "https://raw.githubusercontent.com/radxa/radxa-som-projects/"
    "cf5a4b1984fb4321233d2439320bcaea05af4817/"
    "cm5/radxa-cm5-io-board/radxa_cm5_io_board_v2200.asc"
)
EXPECTED_PADS_ROUTED = 241
EXPECTED_NETS_ROUTED = 159
EXPECTED_NAME_MISMATCHES = {106, 145, 147, 153, 290, 292}
PAIR = re.compile(r"\s*([A-Z0-9_-]+\.\d+)\s+([A-Z0-9_-]+\.\d+)\s*")


class ReferenceBoardAuditError(ValueError):
    """Source or board contacts do not support safe pin mapping."""


def vendor_names(manifest: Mapping) -> dict[int,str]:
    if manifest.get("schema") != "hs.cm5_pinout_v2210.v1" or manifest.get("manufacturer_revision") != "V2.21":
        raise ReferenceBoardAuditError("unexpected manufacturer pinout revision")
    names = {int(k):v for k,v in manifest.get("pin_names",{}).items()}
    if set(names) != set(range(1,301)) or not all(isinstance(s,str) and s for s in names.values()):
        raise ReferenceBoardAuditError("official contact manifest not exactly 300 names")
    return names


def parse_board_routed_pins(raw: bytes, *, verify_hash: bool = True) -> dict[int,set[str]]:
    if verify_hash and sha256(raw).hexdigest()!=BOARD_SHA256:
        raise ReferenceBoardAuditError("reference PADS board revision SHA256 mismatch")
    text = raw.decode("latin-1")
    if "*ROUTE*" not in text or "*POUR*" not in text:
        raise ReferenceBoardAuditError("PADS route/pour sections missing")
    if "U33             DF40C-200DS-D4-OK" not in text:
        raise ReferenceBoardAuditError("missing validated U33 200-contact connector ID")
    if "J24             DF40C_100DS" not in text:
        raise ReferenceBoardAuditError("missing validated J24 100-contact connector ID")
    route=text[text.index("*ROUTE*"):text.index("*POUR*")]
    mapped: dict[int,set[str]] = defaultdict(set)
    signal=None
    seen=0
    for line in route.splitlines():
        if line.startswith("*SIGNAL* "):
            signal=line.split()[1]
            continue
        if not signal:
            continue
        match=PAIR.fullmatch(line)
        if not match:
            continue
        for token in match.groups():
            ref,number=token.rsplit(".",1)
            if ref not in ("U33","J24"):
                continue
            pad=int(number)
            # U33 footprint has extra non-signal mechanical ground tabs
            # numbered >200. They are not the 3rd connector's 201-300 pins.
            if ref=="U33" and pad>200:
                continue
            if ref=="U33" and not 1<=pad<=200:
                raise ReferenceBoardAuditError(f"U33 signal contact outside 1-200: {pad}")
            if ref=="J24" and not 1<=pad<=100:
                raise ReferenceBoardAuditError(f"J24 contact outside 1-100: {pad}")
            global_number=pad+(200 if ref=="J24" else 0)
            mapped[global_number].add(signal)
            seen+=1
    if not mapped or not seen:
        raise ReferenceBoardAuditError("no physical contact routing identified")
    if any(len(nets)>1 for nets in mapped.values()):
        raise ReferenceBoardAuditError("same physical contact connected to multiple differently named nets")
    return mapped


def audit(raw: bytes, manifest: Mapping) -> dict:
    official=vendor_names(manifest)
    routes=parse_board_routed_pins(raw)
    different=[
        {"pin":n,"manufacturer_label":official[n],"reference_board_nets":sorted(nets),
         "is_manufacturer_nc":official[n]=="NC"}
        for n,nets in sorted(routes.items()) if official[n] not in nets
    ]
    critical=[x for x in different if x["is_manufacturer_nc"]]
    if not critical:
        raise ReferenceBoardAuditError("known revision-dependent NC contact conflict unexpectedly missing")
    if (len(routes)!=EXPECTED_PADS_ROUTED
        or len({net for nets in routes.values() for net in nets})!=EXPECTED_NETS_ROUTED
        or {x["pin"] for x in different} != EXPECTED_NAME_MISMATCHES
        or {x["pin"] for x in critical}!={290}):
        raise ReferenceBoardAuditError("reference routing has changed from observed audited evidence")
    matches=len(routes)-len(different)
    return {
        "schema":SCHEMA,
        "source_board":"Radxa CM5 IO v2200 PADS ASCII",
        "source_url":BOARD_SOURCE_URL,
        "source_sha256":BOARD_SHA256,
        "manufacturer_pinout_revision":"V2.21",
        "manufacturer_pinout_sha256":manifest["source_sha256"],
        "source_evidence":"routed_endpoint_pairs_only_not_complete_component_netlist",
        "physical_contact_count":300,
        "reference_contacts_with_routes":len(routes),
        "reference_unique_routed_net_names":len({net for nets in routes.values() for net in nets}),
        "reference_contact_net_conflicts":0,
        "exact_matches_to_manufacturer_names":matches,
        "reference_net_name_differences":different,
        "manufacturer_nc_with_reference_route":critical,
        "manufacturer_nc_count":sum(s=="NC" for s in official.values()),
        "unrepresented_unrouted_or_single_terminal_contacts":sorted(set(official)-set(routes)),
        "reference_contact_routed_net_map":{str(k):sorted(v) for k,v in sorted(routes.items())},
        "reused_reference_board_revision_may_not_match_module_pinout_revision":True,
        "power_input_mapping_review_required":True,
        "usb_signal_integration_tested":False,
        "module_revision_compatibility_verified":False,
        "complete_schematic_erc_pass":False,
        "complete_pcb_drc_pass":False,
        "physical_prototype_validated":False,
        "safe_to_fabricate":False,
        "next_design_gate":"Resolve CM5 J1 contact 90: reference routed RTC_32K_SOC vs module V2.21 NC; obtain matching module/carrier revisions and inspect manufacturer power and USB reference schematics.",
    }


def main() -> int:
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--board-asc",required=True,type=Path)
    p.add_argument("--vendor-pin-manifest",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    manifest=json.loads(args.vendor_pin_manifest.read_text(encoding="utf-8"))
    result=audit(args.board_asc.read_bytes(),manifest)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("Module routed contacts:",result["reference_contacts_with_routes"])
    print("Exact manufacturer label/routed net matches:",result["exact_matches_to_manufacturer_names"])
    print("Revision-related no-connect conflicts:",result["manufacturer_nc_with_reference_route"])
    print("Safe to fabricate:",result["safe_to_fabricate"])
    return 0


if __name__=="__main__":
    raise SystemExit(main())
