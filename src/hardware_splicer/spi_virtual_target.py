"""Exact, source-bound virtual target for the SPI flash adapter campaign.

The target is deliberately a *virtual* implementation.  It selects exact orderable parts
for software analysis without claiming that any selected part is the user's physical DUT.
Manufacturer web pages establish catalog/product facts; simulator model bytes must be
captured and hashed separately before they can receive model-backed verification credit.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .spi_virtual_verification import EXPECTED_SPI_DIRECTIONS

TARGET_SCHEMA_VERSION = "hardware_splicer.spi_virtual_target.v1"
MODEL_REGISTRY_SCHEMA_VERSION = "hardware_splicer.vendor_model_registry.v1"


def build_vendor_model_registry() -> dict[str, Any]:
    """Return the frozen model-acquisition registry for the grounded virtual target.

    ``remote_available_not_captured`` means an official manufacturer page advertises the
    model, but HS does not yet possess immutable model bytes and therefore cannot claim a
    model-backed pass.
    """

    return {
        "schema_version": MODEL_REGISTRY_SCHEMA_VERSION,
        "authority_effect": "none",
        "modeled_evidence_only": True,
        "models": [
            {
                "model_id": "txu0304-ibis-scem787",
                "component": "TXU0304PWR",
                "model_kind": "IBIS",
                "publisher": "Texas Instruments",
                "landing_url": "https://www.ti.com/product/TXU0304",
                "download_url": "https://www.ti.com/lit/zip/SCEM787",
                "expected_hosts": ["www.ti.com"],
                "advertised_artifact": "SCEM787.ZIP",
                "advertised_size_bytes": 56 * 1024,
                "capture_status": "remote_available_not_captured",
                "sha256": None,
                "required_for": ["translator_signal_integrity"],
            },
            {
                "model_id": "w25q128jwsiq-ibis-da03-aag072",
                "component": "W25Q128JWSIQ",
                "model_kind": "IBIS",
                "publisher": "Winbond Electronics",
                "landing_url": (
                    "https://www.winbond.com/hq/support/documentation/downloadV2022.jsp?"
                    "__locale=en&xmlPath=/support/resources/.content/item/DA03-AAG072.html&level=3"
                ),
                "download_url": None,
                "expected_hosts": ["www.winbond.com"],
                "advertised_artifact": "W25Q128JWSIQ IBIS Model",
                "capture_status": "remote_available_not_captured",
                "sha256": None,
                "required_for": ["dut_signal_integrity"],
            },
            {
                "model_id": "w25q128jw-q-verilog-da02-aag072",
                "component": "W25Q128JWSIQ",
                "model_kind": "Verilog",
                "publisher": "Winbond Electronics",
                "landing_url": (
                    "https://www.winbond.com/hq/support/documentation/downloadV2022.jsp?"
                    "__locale=en&xmlPath=/support/resources/.content/item/DA02-AAG072.html&level=2"
                ),
                "download_url": None,
                "expected_hosts": ["www.winbond.com"],
                "advertised_artifact": "W25Q128JW-Q Verilog Model",
                "capture_status": "remote_available_not_captured",
                "sha256": None,
                "required_for": ["spi_protocol_behavior"],
            },
        ],
        "nonclaims": [
            "A vendor landing page is not a captured simulator model.",
            "A model-file hash proves captured-byte identity, not model correctness.",
            "Simulator agreement is not measured physical evidence.",
        ],
    }


def build_grounded_virtual_spi_target() -> dict[str, Any]:
    """Build the exact virtual implementation selected for the next HS campaign."""

    return {
        "schema_version": TARGET_SCHEMA_VERSION,
        "candidate_id": "hs-spi-grounded-virtual-target-v1",
        "candidate_origin": "manufacturer_catalog_grounded_virtual_selection",
        "virtual_target_only": True,
        "physical_identity_asserted": False,
        "host_logic_high_v": 3.3,
        "dut_supply_target_v": 1.8,
        "dut_vcc_min_v": 1.7,
        "dut_vcc_max_v": 1.95,
        "dut_pin_abs_max_rule": {"kind": "vcc_plus_offset", "offset_v": 0.4},
        "signals": dict(EXPECTED_SPI_DIRECTIONS),
        "direct_connection": False,
        "dut": {
            "family": "W25Q128JW",
            "exact_orderable_mpn": "W25Q128JWSIQ",
            "package": "SOP-8 208 mil",
            "density_mbit": 128,
            "interface": "SPI/Dual/Quad",
            "catalog_str_max_hz": 133_000_000,
            "operating_range_v": [1.7, 1.95],
            "physical_part_match": "UNRESOLVED",
        },
        "translator": {
            "family": "TXU0304",
            "topology": "fixed_direction",
            "forward_channels": 3,
            "reverse_channels": 1,
            "exact_orderable_mpn": "TXU0304PWR",
            "package": "TSSOP (PW), 14 pin",
            "rail_a_v": 3.3,
            "rail_b_v": 1.8,
            "signal_assignment": {
                "A1_to_B1Y": "SCLK",
                "A2_to_B2Y": "MOSI",
                "A3_to_B3Y": "CS#",
                "B4_to_A4Y": "MISO",
            },
            "oe_strategy": "OE tied to VCCB (1.8-V virtual DUT rail)",
            "partial_power_behavior_verified": True,
            # Dynamic overshoot and exact loaded output envelope remain model work.
            "dut_side_output_max_v": None,
        },
        "supply": {
            "part": "TLV75518PDBVR",
            "package": "SOT-23 (DBV), 5 pin",
            "input_nominal_v": 3.3,
            "output_nominal_v": 1.8,
            # Conservative +/-1.5% catalog accuracy envelope; still within 1.7-1.95 V.
            "output_min_v": 1.773,
            "output_max_v": 1.827,
            "rated_output_current_a": 0.5,
            "minimum_output_capacitance_uf": 1.0,
            "soft_start_present": True,
            "current_budget_verified": False,
            "sequencing_verified": False,
        },
        "timing": {
            "spi_clock_hz": 5_000_000,
            # Do not turn catalog headline rates into an adapter timing proof.
            "max_supported_spi_clock_hz": None,
            "selected_load_verified": False,
        },
        "simulation": None,
        "vendor_model_registry": build_vendor_model_registry(),
        "source_claim_ids": {
            "host_logic_high_v": ["src-controller"],
            "dut_vcc_range": ["dut-operating-supply", "winbond-w25q-jw-2025-selection-guide"],
            "dut_pin_abs_max_rule": ["dut-pin-absolute-maximum"],
            "spi_directions": ["dut-standard-spi-directions"],
            "translator_topology": ["txu-fixed-direction-map", "ti-txu0304-pin-table"],
            "exact_virtual_dut": ["winbond-w25q-jw-2025-selection-guide"],
            "exact_virtual_translator": ["ti-txu0304pwr-part-page"],
            "exact_virtual_supply": ["ti-tlv75518pdbvr-part-page"],
        },
        "source_registry": {
            "winbond-w25q-jw-2025-selection-guide": {
                "publisher": "Winbond Electronics",
                "url": (
                    "https://www.winbond.com/export/sites/winbond/product-selection-guide/file/"
                    "2025-Product-Selection-Guide-Winbond-Code-Storage-Flash-Memory.pdf"
                ),
                "supports": [
                    "W25Q128JWSIQ",
                    "SOP-8 208 mil",
                    "1.7-1.95 V",
                    "133 MHz STR catalog maximum",
                ],
            },
            "ti-txu0304pwr-part-page": {
                "publisher": "Texas Instruments",
                "url": "https://www.ti.com/product/TXU0304/part-details/TXU0304PWR",
                "supports": ["TXU0304PWR", "TSSOP PW 14-pin", "active catalog part"],
            },
            "ti-txu0304-pin-table": {
                "publisher": "Texas Instruments",
                "url": "https://www.ti.com/document-viewer/TXU0304/datasheet",
                "supports": [
                    "A1/A2/A3 are A-side inputs",
                    "B1Y/B2Y/B3Y are B-side outputs",
                    "B4 is B-side input",
                    "A4Y is A-side output",
                    "OE may reference either rail",
                    "partial-power/isolation features",
                ],
            },
            "ti-tlv75518pdbvr-part-page": {
                "publisher": "Texas Instruments",
                "url": "https://www.ti.com/product/TLV755P/part-details/TLV75518PDBVR",
                "supports": [
                    "TLV75518PDBVR",
                    "fixed 1.8-V variant",
                    "500-mA class",
                    "SOT-23 DBV 5-pin",
                    "1-uF minimum ceramic output capacitor",
                    "soft start",
                ],
            },
        },
        "known_unresolved": [
            "Exact physical DUT marking, package, orderable suffix, and package-specific pinout.",
            "Exact programmer identity, voltage levels under load, supported clock rate, and timing behavior.",
            "Captured and hashed TXU0304 IBIS model bytes.",
            "Captured and hashed W25Q128JWSIQ IBIS model bytes.",
            "Captured and hashed W25Q128JW-Q Verilog model bytes.",
            "Loaded TXU0304 output/overshoot envelope at the selected rails and interconnect.",
            "Complete SPI propagation-delay, setup/hold, and selected-load timing budget.",
            "W25Q128JW worst-case current demand and complete 1.8-V rail current budget.",
            "System-level rail sequencing, decoupling, protection, and OE behavior.",
            "Schematic/ERC/PCB/DRC results and all physical measurements.",
            "Independent review of all model-proposed document claims.",
        ],
    }


def clone_grounded_virtual_spi_target() -> dict[str, Any]:
    """Return a deep copy for mutation by fault/campaign tooling."""

    return deepcopy(build_grounded_virtual_spi_target())
