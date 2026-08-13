"""Fresh unseen cleanroom case: 1.8 V SPI flash programming/validation adapter.

This corpus is deliberately outside the rover/robot golden family. It carries product-visible
manufacturer evidence for a Winbond W25Q128JW target and voltage-translation candidates,
then applies evidence-preserving label/order perturbations plus non-equivalent identity,
missing-evidence, tool-failure, lower-authority analogy, and stale-revision challenges.

No case encodes a golden schematic, translator choice, pin mapping, or authorization result.
The durable requirements are evidence identity, unresolved-state preservation, provenance,
revision reasoning, and zero physical authority from the embedded operator.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, Mapping

from .cleanroom_perturbations import (
    build_lower_authority_analogy_case,
    build_parser_failure_case,
    build_partial_evidence_case,
    build_standard_equivalence_suite,
)
from .cleanroom_replay import ReplayCase, run_cleanroom_replay
from .cleanroom_retrospective import build_cleanroom_retrospective
from .cleanroom_revision_challenges import build_stale_revision_case
from .cleanroom_truth_audit import audit_cleanroom_replay_truth
from .integrations.llm_text_client import llm_configured


SCHEMA_VERSION = "hardware_splicer.cleanroom_unseen_spi_flash_experiment.v1"
CAPTURE_DATE = "2026-08-13"

WINBOND_W25Q128JW_URL = (
    "https://www.winbond.com.tw/hq/product/code-storage-flash-memory/serial-nor-flash/"
    "?__locale=en&partNo=W25Q128JW"
)
WINBOND_W25Q_JV_URL = (
    "https://www.winbond.com.tw/hq/product/code-storage-flash/qspi-nor/w25q-jv/?__locale=en"
)
TI_TXU0304_URL = "https://www.ti.com/product/TXU0304"
TI_SN74AXC4T245_URL = "https://www.ti.com/product/SN74AXC4T245"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _record_hash(*, source_locator: str, facts: Mapping[str, Any]) -> str:
    """Hash the experiment's captured fact record, not the mutable remote webpage bytes."""

    body = {
        "captured_on": CAPTURE_DATE,
        "source_locator": source_locator,
        "facts": dict(facts),
    }
    return "sha256:" + hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()


def _source(
    source_id: str,
    *,
    source_type: str,
    revision: str,
    authority_ceiling: str,
    label: str,
    facts: Mapping[str, Any],
    source_locator: str = "",
    limitations: list[str] | None = None,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "label": label,
        "facts": dict(facts),
        "captured_on": CAPTURE_DATE,
    }
    if source_locator:
        metadata["source_locator"] = source_locator
    if limitations:
        metadata["limitations"] = list(limitations)
    return {
        "source_id": source_id,
        "source_type": source_type,
        "content_hash": _record_hash(source_locator=source_locator or source_id, facts=facts),
        "revision": revision,
        "authority_ceiling": authority_ceiling,
        "metadata": metadata,
    }


def spi_flash_adapter_snapshot(*, name: str = "SPI Flash Programming Adapter") -> Dict[str, Any]:
    """Return the product-visible baseline for the fresh unseen case.

    Manufacturer-page facts are intentionally narrow. For example, the Winbond product page
    establishes the W25Q128JW VCC range and package options, but this snapshot does not infer
    absolute-max I/O tolerance or an exact orderable package suffix from those facts.
    """

    host_facts = {
        "host_logic_voltage_v": 3.3,
        "transport": "SPI",
        "host_output_signals": ["SCLK", "CS#", "MOSI_IO0"],
        "host_input_signals": ["MISO_IO1"],
        "target_dut_family_declared": "W25Q128JW",
    }
    dut_facts = {
        "vendor": "Winbond",
        "part_family": "W25Q128JW",
        "density_mbit": 128,
        "vcc_min_v": 1.7,
        "vcc_max_v": 1.95,
        "frequency_mhz": 133,
        "interface": "Dual/Quad SPI",
        "package_options": ["SOP8 208mil", "SOP16 300mil", "WSON8 6x5mm"],
        "exact_orderable_suffix_resolved": False,
        "io_absolute_max_verified": False,
    }
    txu_facts = {
        "vendor": "Texas Instruments",
        "part_family": "TXU0304",
        "channels": 4,
        "translation": "dual-supply noninverting fixed direction",
        "port_operating_range_v": [1.1, 5.5],
        "oe_low_outputs": "high_impedance",
        "application_examples_include": "SPI",
    }
    axc_facts = {
        "vendor": "Texas Instruments",
        "part_family": "SN74AXC4T245",
        "channels": 4,
        "translation": "dual-supply direction-controlled bus transceiver",
        "input_range_v": [0.65, 3.6],
        "output_range_v": [0.65, 3.6],
        "application_examples_include": "SPI",
    }
    fixture_facts = {
        "default_power_state": "off",
        "dut_supply_target_v": 1.8,
        "dut_supply_implementation_verified": False,
        "exact_dut_package_verified": False,
        "dut_pinout_verified": False,
        "translator_channel_direction_mapping_verified": False,
        "physical_bench_evidence_present": False,
    }

    return {
        "name": name,
        "mission": (
            "Prepare the next defensible pre-fabrication engineering actions for an SPI "
            "programming/validation adapter between the declared 3.3 V host and the candidate "
            "flash DUT. Preserve unresolved identity/electrical evidence and do not claim "
            "fabrication or power-on readiness."
        ),
        "constraints": {
            "host_logic_voltage_v": 3.3,
            "declared_dut_supply_target_v": 1.8,
            "default_power_state": "off",
            "authority_effect": "none",
        },
        "engineeringSources": [
            _source(
                "src-controller",
                source_type="fixture_interface_declaration",
                revision="1",
                authority_ceiling="declared",
                label="3.3 V SPI programmer interface",
                facts=host_facts,
            ),
            _source(
                "src-dut",
                source_type="manufacturer_product_page_fact_snapshot",
                revision="current-2026-08-13",
                authority_ceiling="declared",
                label="Winbond W25Q128JW product record",
                facts=dut_facts,
                source_locator=WINBOND_W25Q128JW_URL,
                limitations=[
                    "Product page does not resolve the exact orderable package suffix for the physical DUT.",
                    "Do not infer absolute-maximum I/O tolerance from VCC range alone.",
                ],
            ),
            _source(
                "src-translator-fixed",
                source_type="manufacturer_product_page_fact_snapshot",
                revision="current-2026-08-13",
                authority_ceiling="declared",
                label="TI TXU0304 translator record",
                facts=txu_facts,
                source_locator=TI_TXU0304_URL,
                limitations=["Fixed channel directions still require an explicit signal-direction mapping."],
            ),
            _source(
                "src-translator-dir",
                source_type="manufacturer_product_page_fact_snapshot",
                revision="current-2026-08-13",
                authority_ceiling="declared",
                label="TI SN74AXC4T245 translator record",
                facts=axc_facts,
                source_locator=TI_SN74AXC4T245_URL,
                limitations=["Direction-control behavior must be explicitly designed; product presence is not a wiring decision."],
            ),
            _source(
                "src-fixture",
                source_type="fixture_readiness_declaration",
                revision="1",
                authority_ceiling="declared",
                label="Adapter bring-up constraints",
                facts=fixture_facts,
            ),
        ],
        "engineeringBlockers": [
            "The physical DUT's exact orderable package suffix and package-specific pinout are not verified.",
            "The W25Q128JW product-page VCC range does not by itself establish absolute-maximum I/O tolerance.",
            "The level-translator channel direction/control mapping has not been verified for the chosen implementation.",
            "The local 1.8 V DUT supply implementation has not been selected and verified.",
            "No physical power-on or programming evidence exists for this adapter revision.",
        ],
        "engineeringAdvisories": [
            "Treat manufacturer product-page facts as design evidence with the stated limitations, not bench confirmation.",
            "A similar W25Q family name is not sufficient evidence of identical voltage/package requirements.",
        ],
        "engineering_status": "pre_fabrication_review",
        "engineering_readiness": {
            "fabrication_ready": False,
            "power_on_ready": False,
            "evidence_complete": False,
        },
    }


def _identity_conflict_case(base: ReplayCase) -> ReplayCase:
    """Add an unresolved lower-authority JV-vs-JW procurement identity conflict."""

    snapshot = deepcopy(dict(base.snapshot))
    procurement_facts = {
        "transcribed_target_marking": "W25Q128JV",
        "transcription_status": "unverified_procurement_note",
        "note": "The procurement note conflicts with the current W25Q128JW project declaration.",
    }
    sources = list(snapshot.get("engineeringSources") or [])
    sources.append(
        _source(
            "src-procurement-note",
            source_type="procurement_note",
            revision="note-1",
            authority_ceiling="advisory",
            label="Unverified procurement transcription",
            facts=procurement_facts,
        )
    )
    snapshot["engineeringSources"] = sources
    conflicts = list(snapshot.get("engineeringSourceConflicts") or [])
    conflicts.append(
        {
            "conflict_id": "candidate-part-identity:jv-vs-jw",
            "source_ids": ["src-dut", "src-procurement-note"],
            "field": "candidate_part_identity",
            "status": "unresolved",
            "authority_note": "An advisory transcription cannot silently replace the current declared DUT identity.",
        }
    )
    snapshot["engineeringSourceConflicts"] = conflicts
    blockers = list(snapshot.get("engineeringBlockers") or [])
    blockers.append("The physical DUT identity is disputed between current project evidence and an unverified procurement note.")
    snapshot["engineeringBlockers"] = blockers
    return ReplayCase(
        case_id=f"{base.case_id}:identity-conflict",
        project_id=base.project_id,
        project_revision=base.project_revision + 20,
        snapshot=snapshot,
        equivalence_group=None,
        perturbation_kind="conflicting_component_identity",
        metadata={
            **dict(base.metadata or {}),
            "baseline_case_id": base.case_id,
            "expected_equivalent": False,
        },
    )


def build_unseen_spi_flash_cases() -> list[ReplayCase]:
    """Build the fresh case plus controlled equivalent and non-equivalent perturbations."""

    base = ReplayCase(
        case_id="spi-flash-adapter-baseline",
        project_id="cleanroom-unseen-spi-flash-adapter",
        project_revision=1,
        snapshot=spi_flash_adapter_snapshot(),
        equivalence_group="spi-flash-evidence-equivalent",
        perturbation_kind="baseline",
        metadata={
            "scenario_family": "spi_flash_programming_adapter",
            "fresh_unseen_case": True,
            "golden_architecture_encoded": False,
        },
    )
    equivalent = build_standard_equivalence_suite(
        base,
        mission_paraphrase_text=(
            "Using only the persisted adapter evidence, identify the next defensible engineering "
            "work before fabrication or power-on and keep unresolved identity/electrical facts explicit."
        ),
    )
    partial = build_partial_evidence_case(base, remove_source_ids=["src-dut"])
    identity_conflict = _identity_conflict_case(base)
    parser_failure = build_parser_failure_case(
        base,
        source_id="src-dut",
        parser_route="manufacturer_flash_limits_parser",
    )
    analogy = build_lower_authority_analogy_case(
        base,
        analogy_source_id="src-legacy-jv-3v-adapter",
        metadata={
            "label": "Historical W25Q-JV 3 V adapter analogy",
            "source_locator": WINBOND_W25Q_JV_URL,
            "facts": {
                "historical_product_series": "W25Q-JV",
                "historical_voltage_class": "3V",
                "claimed_direct_3v3_fixture_reuse_ok": True,
            },
            "warning": "Different voltage-family evidence; advisory historical analogy only.",
        },
    )
    stale = build_stale_revision_case(
        base,
        current_source_id="src-dut",
        stale_source_id="src-dut-rev-jv",
        stale_revision="historical-jv",
        stale_metadata={
            "label": "Superseded W25Q128JV-era target record",
            "source_locator": WINBOND_W25Q_JV_URL,
            "facts": {
                "historical_part_family": "W25Q128JV",
                "historical_supply_class": "2.7V_to_3.6V_family",
                "target_for_current_adapter": False,
            },
            "warning": "Historical target retained for traceability only; not current DUT evidence.",
        },
    )
    return [*equivalent, partial, identity_conflict, parser_failure, analogy, stale]


def _source_inventory(snapshot: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for row in list(snapshot.get("engineeringSources") or []):
        if not isinstance(row, Mapping):
            continue
        rows.append(
            (
                str(row.get("source_id") or ""),
                str(row.get("content_hash") or ""),
                str(row.get("revision") or ""),
            )
        )
    return sorted(rows)


def validate_unseen_spi_flash_corpus() -> Dict[str, Any]:
    """Check corpus construction without asserting a golden engineering solution."""

    cases = build_unseen_spi_flash_cases()
    baseline = next(case for case in cases if case.perturbation_kind == "baseline")
    baseline_inventory = _source_inventory(baseline.snapshot)
    equivalent = [case for case in cases if case.equivalence_group == baseline.equivalence_group]
    challenge_kinds = {
        case.perturbation_kind for case in cases if case.equivalence_group is None
    }
    dut = next(
        row
        for row in list(baseline.snapshot.get("engineeringSources") or [])
        if isinstance(row, Mapping) and row.get("source_id") == "src-dut"
    )
    dut_facts = dict((dut.get("metadata") or {}).get("facts") or {})
    identity_case = next(case for case in cases if case.perturbation_kind == "conflicting_component_identity")
    identity_conflicts = list(identity_case.snapshot.get("engineeringSourceConflicts") or [])
    stale_case = next(case for case in cases if case.perturbation_kind == "stale_revision_evidence")
    stale_sources = [
        row
        for row in list(stale_case.snapshot.get("engineeringSources") or [])
        if isinstance(row, Mapping) and row.get("source_id") == "src-dut-rev-jv"
    ]

    required_challenges = {
        "partial_evidence",
        "conflicting_component_identity",
        "deterministic_tool_failure",
        "plausible_wrong_analogy",
        "stale_revision_evidence",
    }
    checks = {
        "fresh_family_declared": bool(baseline.metadata and baseline.metadata.get("fresh_unseen_case")),
        "no_golden_architecture_declared": bool(
            baseline.metadata and baseline.metadata.get("golden_architecture_encoded") is False
        ),
        "current_dut_is_w25q128jw": dut_facts.get("part_family") == "W25Q128JW",
        "current_dut_vcc_record_is_1v7_to_1v95": (
            dut_facts.get("vcc_min_v") == 1.7 and dut_facts.get("vcc_max_v") == 1.95
        ),
        "io_abs_max_remains_unverified": dut_facts.get("io_absolute_max_verified") is False,
        "physical_authority_closed": (
            baseline.snapshot.get("engineering_readiness", {}).get("fabrication_ready") is False
            and baseline.snapshot.get("engineering_readiness", {}).get("power_on_ready") is False
        ),
        "equivalent_variants_preserve_source_identity": all(
            _source_inventory(case.snapshot) == baseline_inventory for case in equivalent
        ),
        "required_non_equivalent_challenges_present": required_challenges.issubset(challenge_kinds),
        "identity_conflict_is_explicitly_unresolved": any(
            isinstance(row, Mapping)
            and row.get("field") == "candidate_part_identity"
            and row.get("status") == "unresolved"
            for row in identity_conflicts
        ),
        "stale_jv_source_is_explicitly_superseded": bool(
            stale_sources
            and isinstance(stale_sources[0].get("metadata"), Mapping)
            and stale_sources[0]["metadata"].get("lifecycle_status") == "superseded"
            and stale_sources[0]["metadata"].get("superseded_by_source_id") == "src-dut"
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "unseen_spi_flash_corpus_validation",
        "case_count": len(cases),
        "equivalent_case_count": len(equivalent),
        "challenge_kinds": sorted(challenge_kinds),
        "checks": checks,
        "pass": all(checks.values()),
    }


def run_unseen_spi_flash_live_experiment(*, model: str | None = None) -> Dict[str, Any]:
    """Run the configured source-blind operator against the fresh unseen corpus."""

    cases = build_unseen_spi_flash_cases()
    corpus_validation = validate_unseen_spi_flash_corpus()
    configured = llm_configured()
    replay = run_cleanroom_replay(cases, model=model)
    retrospective = build_cleanroom_retrospective(replay, cases=cases)
    truth_audit = audit_cleanroom_replay_truth(replay)
    hard_contract_failures = [
        row
        for row in list(replay.get("results") or [])
        if isinstance(row, Mapping)
        and row.get("failure_class") in {"cleanroom_contract", "authority_contract"}
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "live_unseen_spi_flash_provider",
        "provider_configured": configured,
        "model_requested": model,
        "corpus_validation": corpus_validation,
        "contract_pass": bool(
            corpus_validation.get("pass")
            and not hard_contract_failures
            and truth_audit.get("status") == "pass"
        ),
        "hard_contract_failures": hard_contract_failures,
        "case_count": len(cases),
        "challenge_kinds": sorted(
            {case.perturbation_kind for case in cases if case.equivalence_group is None}
        ),
        "replay": replay,
        "retrospective": retrospective,
        "truth_audit": truth_audit,
    }
