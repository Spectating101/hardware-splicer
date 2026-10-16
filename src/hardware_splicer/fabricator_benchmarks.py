"""Progressive end-to-end benchmarks for Hardware Splicer as a fabricator.

The benchmark harness scores retained receipts and truth-boundary behavior.  It
does not simulate missing evidence and it never treats connector count as proof
of fabrication capability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .fabrication_operator import FabricationValidationError


@dataclass(frozen=True)
class FabricatorBenchmark:
    benchmark_id: str
    title: str
    goal: str
    required_record_schemas: tuple[str, ...]
    required_evidence_kinds: tuple[str, ...]
    requires_failed_evidence_revision_cycle: bool
    donor_required: bool
    multi_machine_required: bool
    acceptance_notes: tuple[str, ...]

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


_BENCHMARKS = {
    "B1_CLOSED_LOOP_LOGGER": FabricatorBenchmark(
        benchmark_id="B1_CLOSED_LOOP_LOGGER",
        title="Clean-sheet environmental logger closed loop",
        goal=(
            "Create a small logger from known parts, verify EDA/model artifacts, fabricate an enclosure, "
            "flash firmware, capture serial output and electrical/fit evidence, then revise after one injected failure."
        ),
        required_record_schemas=(
            "hardware_splicer.kicad_verification.v1",
            "hardware_splicer.ngspice_receipt.v1",
            "hardware_splicer.physical_dispatch_receipt.v1",
            "hardware_splicer.serial_observation.v1",
            "hardware_splicer.physical_evidence.v1",
            "hardware_splicer.physical_revision_proposal.v1",
        ),
        required_evidence_kinds=("electrical_measurement", "dimensional_measurement"),
        requires_failed_evidence_revision_cycle=True,
        donor_required=False,
        multi_machine_required=False,
        acceptance_notes=(
            "At least one real physical failure is retained and causes a reviewable revision proposal.",
            "Final success requires new physical evidence after the revision; a software-only rerun is insufficient.",
        ),
    ),
    "B2_DONOR_RECLAIM_BUILD": FabricatorBenchmark(
        benchmark_id="B2_DONOR_RECLAIM_BUILD",
        title="Donor-heavy salvage build",
        goal=(
            "Build a useful device that reuses at least two capabilities from an unknown or retired donor and "
            "fabricates only the missing electronics/mechanics."
        ),
        required_record_schemas=(
            "hardware_splicer.physical_evidence.v1",
            "hardware_splicer.physical_dispatch_receipt.v1",
            "hardware_splicer.physical_revision_proposal.v1",
        ),
        required_evidence_kinds=("inspection", "electrical_measurement", "dimensional_measurement"),
        requires_failed_evidence_revision_cycle=False,
        donor_required=True,
        multi_machine_required=False,
        acceptance_notes=(
            "Donor capabilities must be supported by P4/P5 evidence rather than agent assertion.",
            "Clean-sheet, reclaim-heavy and hybrid options must remain distinguishable in the decision record.",
        ),
    ),
    "B3_MULTI_MACHINE_FABRICATION": FabricatorBenchmark(
        benchmark_id="B3_MULTI_MACHINE_FABRICATION",
        title="Multi-machine electronics fabrication cell",
        goal=(
            "Take a requirement through EDA, assembly package, additive/subtractive fabrication, programming, "
            "instrumented validation and at least one cross-machine recovery path."
        ),
        required_record_schemas=(
            "hardware_splicer.kicad_verification.v1",
            "hardware_splicer.openpnp_simulation_package.v1",
            "hardware_splicer.gcode_dry_run.v1",
            "hardware_splicer.mtconnect_observation.v1",
            "hardware_splicer.physical_dispatch_receipt.v1",
            "hardware_splicer.physical_evidence.v1",
        ),
        required_evidence_kinds=("electrical_measurement", "inspection"),
        requires_failed_evidence_revision_cycle=False,
        donor_required=False,
        multi_machine_required=True,
        acceptance_notes=(
            "Simulation-only CNC/laser/OpenPnP results do not satisfy real fabrication acceptance by themselves.",
            "Each live physical actuation must retain its own plan-bound human authority provenance.",
        ),
    ),
}


def list_benchmarks() -> list[dict[str, Any]]:
    return [_BENCHMARKS[key].public_dict() for key in sorted(_BENCHMARKS)]


def benchmark(benchmark_id: str) -> dict[str, Any]:
    try:
        return _BENCHMARKS[benchmark_id].public_dict()
    except KeyError as exc:
        raise FabricationValidationError("unknown fabricator benchmark") from exc


def assess_trace(benchmark_id: str, records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    try:
        definition = _BENCHMARKS[benchmark_id]
    except KeyError as exc:
        raise FabricationValidationError("unknown fabricator benchmark") from exc
    rows = [dict(row) for row in records if isinstance(row, Mapping)]
    schemas = {_schema(row) for row in rows if _schema(row)}
    evidence_kinds = {
        str(row.get("kind"))
        for row in rows
        if _schema(row) == "hardware_splicer.physical_evidence.v1" and row.get("kind")
    }
    missing_schemas = [schema for schema in definition.required_record_schemas if schema not in schemas]
    missing_evidence = [kind for kind in definition.required_evidence_kinds if kind not in evidence_kinds]

    false_truth = []
    for index, row in enumerate(rows):
        schema = _schema(row)
        if schema in {
            "hardware_splicer.physical_dispatch_receipt.v1",
            "hardware_splicer.serial_observation.v1",
            "hardware_splicer.camera_observation.v1",
            "hardware_splicer.mtconnect_observation.v1",
            "hardware_splicer.gcode_dry_run.v1",
            "hardware_splicer.openpnp_simulation_package.v1",
        } and row.get("physical_correctness") not in {None, "UNPROVEN"}:
            false_truth.append({"index": index, "schema": schema, "claim": row.get("physical_correctness")})

    failed_evidence = [
        row for row in rows
        if _schema(row) == "hardware_splicer.physical_evidence.v1" and row.get("passed") is False
    ]
    revision_proposals = [
        row for row in rows
        if _schema(row) == "hardware_splicer.physical_revision_proposal.v1" and row.get("needs_revision") is True
    ]
    revision_cycle_missing = (
        definition.requires_failed_evidence_revision_cycle
        and (not failed_evidence or not revision_proposals)
    )

    passed = not missing_schemas and not missing_evidence and not false_truth and not revision_cycle_missing
    return {
        "schema": "hardware_splicer.fabricator_benchmark_assessment.v1",
        "benchmark_id": benchmark_id,
        "passed": passed,
        "missing_record_schemas": missing_schemas,
        "missing_evidence_kinds": missing_evidence,
        "false_persisted_truth": false_truth,
        "failed_evidence_count": len(failed_evidence),
        "grounded_revision_proposal_count": len(revision_proposals),
        "required_revision_cycle_missing": revision_cycle_missing,
        "note": "This trace assessment does not replace real hardware acceptance criteria.",
    }


def _schema(row: Mapping[str, Any]) -> str | None:
    value = row.get("schema") or row.get("schema_version")
    return str(value) if isinstance(value, str) else None
