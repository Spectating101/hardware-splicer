"""Evidence-specific technical procurement packets, not product purchase orders.

The packets are source-attributed pre-purchase test plans. An assertion that
the seller's device "works" is not a passed physical acceptance test.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "hardware_splicer.commercial_validation_packet.v1"

# These are pre-registered checks, not actual measurements or negotiations.
PROTOCOLS: dict[str, dict[str, Any]] = {
    "tsc-ttp244plus-budget-fault": {
        "target_mode": "repair_or_refurbish",
        "no_go": ["Printhead visibly damaged or fails sample output",
                  "Replacement quote makes the expected net below target",
                  "Exact TTP-244 Plus variant or seller condition unresolved"],
        "identity": ["Model and model suffix on unit", "Printhead connector and revision",
                     "Power supply rating and original cables"],
        "physical": ["Non-invasive visual check with power disconnected",
                     "Power-on only with correct approved PSU",
                     "Self-test label and printhead-quality sample",
                     "Check drive, ribbon feed, platen, sensors and interface"],
        "quotes": ["Repair head exact revision and genuine/compatible status",
                   "Replacement platen/motor if fault indicated",
                   "Consumables, shipment, packaging and returns"],
        "commercial": ["Same-variant completed resale transaction",
                       "Conditional failure recovery and labor",
                       "Price/payments/warranty policy for actual buyer"],
    },
    "proofpod-v0": {
        "target_mode": "build_and_replicate",
        "no_go": ["Reference schematic and electrical test not accepted",
                  "Supplier BOM, firmware licensing or rights missing",
                  "Customer need or internal productive output unknown"],
        "identity": ["Exact MCU/bridge/protection parts against CAD",
                     "Target-voltage and connector compatibility"],
        "physical": ["Bench checks of bounded target voltage/current",
                     "Protocol interaction reproducibility",
                     "Firmware trace/error handling and safe disconnect"],
        "quotes": ["Line-item electronics BOM in native currency",
                   "PCB/assembly, enclosure, calibration, test fixture and packaging",
                   "MOQ1 and MOQ10 lead time, failed unit rework"],
        "commercial": ["A qualified user workflow and acceptable installed price",
                       "Warranty/regulatory obligations and usable test records"],
    },
    "ls2208": {
        "target_mode": "recover_repair_or_use",
        "no_go": ["Scanner optics or decoder unverified",
                  "Unknown cut cable pinout or unapproved power",
                  "Recovered use cannot offset acquisition and test costs"],
        "identity": ["Serial/model plate and board revision", "Connector and cut-wire mapping"],
        "physical": ["Unpowered cable continuity check",
                     "Approved 5 V interface proof before powered test",
                     "Recognize reference barcodes and repeat scan"],
        "quotes": ["Correct replacement cable/connector",
                   "Testing labor and resale/repair material allowances"],
        "commercial": ["Matched scanner engine resale, or internal barcode task throughput"],
    },
    "qnap-ts219pii": {
        "target_mode": "reuse_components_or_operate",
        "no_go": ["Exact board revision unconfirmed",
                  "Missing PSU or unsafe substitute",
                  "Obsolete software exposed to untrusted networks"],
        "identity": ["Board model/revision and physical connectors", "Power input specification"],
        "physical": ["Unpowered corrosion/damage check",
                     "Boot with approved supply in isolated environment",
                     "Storage/network port functional checks with no user data"],
        "quotes": ["Approved supply or test bench adapter",
                   "Replacement connectors and storage if required"],
        "commercial": ["Usable compute/storage throughput and idle-power measurement",
                       "Alternative intact used NAS/computing hardware price"],
    },
    "TW-PF-EDGE-001": {
        "target_mode": "remanufacture_own_or_sell",
        "no_go": ["Supplier exact model/CPU/revision mismatches official evidence",
                  "Quantity and tested yield unverified",
                  "No output advantage versus new commodity edge device"],
        "identity": ["Original brand/model serial identification",
                     "CPU and board marking versus OEM specifications",
                     "BIOS identifier, RAM/storage/power configuration"],
        "physical": ["POST, diagnostic and I/O tests on approved PSU",
                     "Storage health and secure wipe",
                     "Stable load/temperature/power measurement"],
        "quotes": ["Validated thin-client donor lot at MOQ1 and MOQ10",
                   "I/O sidecar and isolation BOM, enclosure and test labor",
                   "Shipping, returns and tax"],
        "commercial": ["Specific gateway/workshop task and measured utility",
                       "Native TWD delivered competitor price and support"],
    },
    "TW-PF-ARK-001": {
        "target_mode": "refurbish_or_operate",
        "no_go": ["Revisions/interfaces mismatch proposed application",
                  "Industrial PSU not rated/approved",
                  "Unsupported OS or missing secure replacement software"],
        "identity": ["ARK-1122/1123/2120L exact variant and accessories",
                     "DC input spec and available serial/network ports"],
        "physical": ["Approved PSU boot and isolation conditions",
                     "Serial/network/storage tests", "Long-run reliability and power logging"],
        "quotes": ["Exact-unit acquisition, storage/PSU/rework and freight",
                   "Replacement module, QA and warranty labor"],
        "commercial": ["Internal supervisory workload or qualified industrial buyer",
                       "Comparable supported used/new controllers"],
    },
    "CN-PF-HMI-001": {
        "target_mode": "remanufacture_in_china",
        "no_go": ["Lot not demonstrably NEC J1900 touch POS",
                  "Touch/display/mechanics yield unknown",
                  "Commodity touch panels cheaper at equivalent delivered function"],
        "identity": ["NEC N8910 exact touchscreen/CPU/display interface",
                     "Mainboard, external PSU and touch driver"],
        "physical": ["Panel dead-pixel/touch-accuracy sample tests",
                     "Power and thermal stability", "Actual port compatibility"],
        "quotes": ["MOQ1/MOQ10 unit condition in CNY, source and lead time",
                   "Sidecar, freight within China and rework yield"],
        "commercial": ["Real Chinese user/retailer willingness to pay",
                       "Compare local replacement panel, industrial HMI alternatives"],
    },
    "CN-PF-EDGE-001": {
        "target_mode": "productive_compute_in_china",
        "no_go": ["Actual HP T620/Dell N03D identity not verified",
                  "Integrated workflow cannot compete with ¥-priced commodity module",
                  "Buyer needs legal/IP or unimplemented functions"],
        "identity": ["Exact approved AMD thin-client or Dell model and hardware configuration",
                     "Do not accept HP T620 J1900 without independent identification"],
        "physical": ["POST, approved power and measured steady load",
                     "UART/RS485/CAN sidecar compatibility if proposed"],
        "quotes": ["CNY matched-market donor quotation for 1 and 10 units",
                   "New commodity gateway benchmark, internal shipping and test"],
        "commercial": ["Chinese buyer outcome or own productive use",
                       "Replacement part availability and long-term support"],
    },
}


def build_validation_packets(dossier: Mapping[str, Any]) -> dict[str, Any]:
    backlog = dossier.get("validation_backlog")
    if not isinstance(backlog, Mapping) or backlog.get("schema_version") != "hardware_splicer.commercial_validation_backlog.v1":
        raise ValueError("validation backlog required")
    entries = {e["concept_id"]: e for e in backlog.get("entries") or []}
    packets: list[dict[str, Any]] = []
    for cid in backlog.get("first_evidence_wave") or []:
        if cid not in PROTOCOLS or cid not in entries:
            raise ValueError(f"missing pre-registered case protocol: {cid}")
        data, e = PROTOCOLS[cid], entries[cid]
        packets.append({
            "packet_schema": SCHEMA,
            "candidate_id": cid,
            "source_refs": e["source_refs"],
            "currency": e["native_currencies"],
            "mode": data["target_mode"],
            "physical_identity_checks": data["identity"],
            "physical_acceptance_plan": data["physical"],
            "materials_and_supplier_quotes": data["quotes"],
            "commercial_evidence": data["commercial"],
            "hard_stop_conditions": data["no_go"],
            "known_sold_comparable_status": e["market_sold_evidence_status"],
            "factual_quote_inputs_received": 0,
            "physical_acceptance_recorded": False,
            "verified_ownership_rights": False,
            "buyer_or_output_verified": False,
            "status": "PACKET_FOR_EVIDENCE_COLLECTION_ONLY",
            "purchase_authorized": False,
            "production_authorized": False,
        })
    return {
        "schema_version": "hardware_splicer.commercial_validation_packets.v1",
        "count": len(packets),
        "packets": packets,
        "notes": [
            "Specific parts, ratings and variants must be verified against device OEM data",
            "No packet authenticates seller claims, sale price, physical QA or regulatory clearance",
            "No market listing means a procurement or sale has occurred",
        ],
        "purchase_authorized": False,
    }
