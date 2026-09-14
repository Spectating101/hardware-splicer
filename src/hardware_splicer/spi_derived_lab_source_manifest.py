"""Source manifest for the Derived Virtual Lab v1 experiment.

The manifest binds the lower-fidelity surrogate experiment to the canonical virtual target,
spec-level timing inputs, and power inputs from PR #93.  It does not increase authority; it
exists so a benchmark artifact can prove which source-bound inputs it inherited.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .spi_power_budget import build_grounded_spi_power_inputs
from .spi_timing_budget import build_grounded_spi_timing_inputs
from .spi_virtual_target import build_grounded_virtual_spi_target

SCHEMA_VERSION = "hardware_splicer.spi_derived_lab_source_manifest.v1"


def _hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_derived_lab_source_manifest() -> dict[str, Any]:
    target = build_grounded_virtual_spi_target()
    timing = build_grounded_spi_timing_inputs()
    power = build_grounded_spi_power_inputs()

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": "hs-spi-derived-virtual-lab-v1",
        "canonical_inputs": {
            "virtual_target_sha256": _hash(target),
            "timing_inputs_sha256": _hash(timing),
            "power_inputs_sha256": _hash(power),
        },
        "selected_inherited_terms": {
            "candidate_id": target["candidate_id"],
            "host_logic_high_v": target["host_logic_high_v"],
            "dut_vcc_range_v": [target["dut_vcc_min_v"], target["dut_vcc_max_v"]],
            "dut_pin_abs_max_rule": target["dut_pin_abs_max_rule"],
            "txu_a_to_b_tpd_max_ns": timing["txu0304"]["a_to_b_tpd_max_ns"],
            "txu_b_to_a_tpd_max_ns": timing["txu0304"]["b_to_a_tpd_max_ns"],
            "dut_clock_low_to_output_valid_max_ns": timing["w25q128jw"]["clock_low_to_output_valid_max_ns"],
            "regulator_part": power["regulator"]["part"],
            "regulator_capacity_ma": power["regulator"]["rated_output_current_ma"],
            "regulator_output_range_v": [
                power["regulator"]["output_min_v"],
                power["regulator"]["output_max_v"],
            ],
        },
        "source_records": {
            "txu_timing": timing["txu0304"]["source"],
            "dut_timing": timing["w25q128jw"]["source"],
            "regulator": power["regulator"]["source"],
            "translator_power": power["translator"]["source"],
        },
        "evidence_class": "derived_surrogate_only",
        "vendor_model_campaign_credit_eligible": False,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
    manifest["manifest_sha256"] = _hash(manifest)
    return manifest
