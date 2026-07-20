from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional


SCHEMA_VERSION = "hardware_splicer.bench_recipe.v1"


class Outcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    REPEAT = "repeat"
    NEEDS_HUMAN = "needs_human"
    ERROR = "error"


@dataclass(frozen=True)
class MeasurementSpec:
    measurement_id: str
    description: str
    unit: Optional[str] = None
    lower: Optional[float] = None
    upper: Optional[float] = None
    required: bool = True

    def validate(self, value: Any) -> tuple[Outcome, str]:
        if value is None:
            return (
                (Outcome.BLOCKED, "required measurement missing")
                if self.required
                else (Outcome.SKIPPED, "optional measurement missing")
            )
        if self.lower is None and self.upper is None:
            return Outcome.PASS, "recorded"
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return Outcome.FAIL, "measurement is not numeric"
        if self.lower is not None and numeric < self.lower:
            return Outcome.FAIL, f"{numeric} < lower bound {self.lower}"
        if self.upper is not None and numeric > self.upper:
            return Outcome.FAIL, f"{numeric} > upper bound {self.upper}"
        return Outcome.PASS, "within bounds"


@dataclass
class Phase:
    phase_id: str
    title: str
    instructions: List[str]
    measurements: List[MeasurementSpec] = field(default_factory=list)
    requires_human: bool = True
    stop_on_fail: bool = True
    evidence_kind: str = "bench_measurement"

    def evaluate(self, values: Mapping[str, Any]) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        outcome = Outcome.PASS
        for spec in self.measurements:
            status, reason = spec.validate(values.get(spec.measurement_id))
            results.append(
                {
                    "measurement_id": spec.measurement_id,
                    "value": values.get(spec.measurement_id),
                    "unit": spec.unit,
                    "outcome": status.value,
                    "reason": reason,
                }
            )
            if status in {Outcome.FAIL, Outcome.BLOCKED, Outcome.ERROR}:
                outcome = status
                if self.stop_on_fail:
                    break
        if not self.measurements and self.requires_human:
            outcome = Outcome.NEEDS_HUMAN
        return {
            "phase_id": self.phase_id,
            "title": self.title,
            "outcome": outcome.value,
            "measurements": results,
        }


@dataclass
class BenchRecipe:
    recipe_id: str
    target_id: str
    phases: List[Phase]
    claim_boundary: str = "No power or function claim is authorized until all required phases pass."
    schema_version: str = SCHEMA_VERSION

    def run_manual(self, observations: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
        phase_results: List[Dict[str, Any]] = []
        overall = Outcome.PASS
        for phase in self.phases:
            values = observations.get(phase.phase_id) or {}
            result = phase.evaluate(values)
            phase_results.append(result)
            status = Outcome(result["outcome"])
            if status != Outcome.PASS:
                overall = status
                if phase.stop_on_fail:
                    break
        return {
            "schema_version": self.schema_version,
            "recipe_id": self.recipe_id,
            "target_id": self.target_id,
            "outcome": overall.value,
            "power_authorized": overall == Outcome.PASS,
            "claim_boundary": self.claim_boundary,
            "phases": phase_results,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "recipe_id": self.recipe_id,
            "target_id": self.target_id,
            "claim_boundary": self.claim_boundary,
            "phases": [asdict(p) for p in self.phases],
        }


def donor_interface_discovery_recipe(interface_id: str) -> BenchRecipe:
    phases = [
        Phase(
            phase_id="identify_ground",
            title="Identify ground contacts",
            instructions=[
                "Keep the donor unpowered.",
                "Measure continuity between candidate ground contacts and known ground planes.",
                "Record resistance and the exact probe points.",
            ],
            measurements=[
                MeasurementSpec("ground_resistance_ohm", "Resistance to known ground", "ohm", 0.0, 2.0)
            ],
        ),
        Phase(
            phase_id="idle_voltage",
            title="Measure idle logic voltage",
            instructions=[
                "Use a current-limited supply at the donor's verified input voltage.",
                "Do not attach a microcontroller yet.",
                "Measure the candidate control contact relative to verified ground.",
            ],
            measurements=[
                MeasurementSpec("idle_voltage_v", "Idle contact voltage", "V", 0.0, 5.5)
            ],
        ),
        Phase(
            phase_id="controlled_stimulus",
            title="Verify control polarity and response",
            instructions=[
                "Apply a protected logic stimulus through a series resistor.",
                "Observe the corresponding motor output with no mechanical load.",
                "Record the stimulus level, output response and current draw.",
            ],
            measurements=[
                MeasurementSpec("stimulus_voltage_v", "Applied stimulus", "V", 0.0, 5.5),
                MeasurementSpec("supply_current_a", "Supply current", "A", 0.0, 2.0),
                MeasurementSpec("response_observed", "Expected output response observed"),
            ],
        ),
    ]
    return BenchRecipe(
        recipe_id=f"bench:{interface_id}",
        target_id=interface_id,
        phases=phases,
    )
