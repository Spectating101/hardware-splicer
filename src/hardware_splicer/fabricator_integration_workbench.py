"""Agent-facing facade over bounded fabricator integrations.

All private configuration is injected by the server.  The workbench only accepts
stable ids and bounded parameters; it is not an arbitrary process, filesystem or
network proxy.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .fabrication_capability_registry import FabricationCapabilityRegistry
from .fabrication_operator import FabricationValidationError
from .fabricator_benchmarks import assess_trace, list_benchmarks
from .gcode_dry_run import GcodeDryRunAnalyzer
from .kicad_cli_operator import KicadCliOperator
from .mtconnect_observer import MtconnectObserver
from .ngspice_operator import NgspiceOperator
from .openpnp_simulation import OpenPnpSimulationInspector
from .physical_revision_proposal import PhysicalRevisionProposalBuilder


class FabricatorIntegrationWorkbench:
    def __init__(
        self,
        *,
        capabilities: FabricationCapabilityRegistry | None = None,
        kicad: KicadCliOperator | None = None,
        ngspice: NgspiceOperator | None = None,
        mtconnect_sources: Mapping[str, MtconnectObserver] | None = None,
        machine_job_analyzers: Mapping[str, GcodeDryRunAnalyzer] | None = None,
        openpnp: OpenPnpSimulationInspector | None = None,
        revisions: PhysicalRevisionProposalBuilder | None = None,
    ):
        self.capabilities = capabilities or FabricationCapabilityRegistry()
        self.kicad = kicad
        self.ngspice = ngspice
        self.mtconnect_sources = dict(mtconnect_sources or {})
        self.machine_job_analyzers = dict(machine_job_analyzers or {})
        self.openpnp = openpnp
        self.revisions = revisions

    def list_capabilities(self, *, kind: str | None = None) -> list[dict[str, Any]]:
        return self.capabilities.list_public(kind=kind)

    def match_capabilities(
        self,
        *,
        required_capabilities: Iterable[str],
        kind: str | None = None,
        numeric_minimums: Mapping[str, float | int] | None = None,
        allow_simulated: bool = True,
    ) -> list[dict[str, Any]]:
        return self.capabilities.match(
            required_capabilities=required_capabilities,
            kind=kind,
            numeric_minimums=numeric_minimums,
            allow_simulated=allow_simulated,
        )

    def kicad_verify(self, project_id: str) -> dict[str, Any]:
        if self.kicad is None:
            raise FabricationValidationError("KiCad integration is not configured")
        return self.kicad.verify(project_id)

    def kicad_manufacturing(self, project_id: str) -> dict[str, Any]:
        if self.kicad is None:
            raise FabricationValidationError("KiCad integration is not configured")
        return self.kicad.export_manufacturing(project_id)

    def simulate_circuit(self, circuit_id: str, *, mode: str = "report") -> dict[str, Any]:
        if self.ngspice is None:
            raise FabricationValidationError("ngspice integration is not configured")
        return self.ngspice.run(circuit_id, mode=mode)

    def mtconnect(self, source_id: str, *, operation: str, from_sequence: int | None = None, count: int = 1000) -> dict[str, Any]:
        try:
            source = self.mtconnect_sources[source_id]
        except KeyError as exc:
            raise FabricationValidationError("unknown MTConnect source id") from exc
        if operation == "probe":
            return source.probe()
        if operation == "current":
            return source.current()
        if operation == "sample":
            if from_sequence is None:
                raise FabricationValidationError("MTConnect sample requires from_sequence")
            return source.sample(from_sequence=from_sequence, count=count)
        raise FabricationValidationError("MTConnect operation must be probe, current or sample")

    def dry_run_machine_job(self, analyzer_id: str, *, artifact_id: str) -> dict[str, Any]:
        try:
            analyzer = self.machine_job_analyzers[analyzer_id]
        except KeyError as exc:
            raise FabricationValidationError("unknown machine-job analyzer id") from exc
        return analyzer.analyze(artifact_id)

    def openpnp_simulation_package(self, job_id: str) -> dict[str, Any]:
        if self.openpnp is None:
            raise FabricationValidationError("OpenPnP integration is not configured")
        return self.openpnp.inspect(job_id)

    @staticmethod
    def benchmarks() -> list[dict[str, Any]]:
        return list_benchmarks()

    @staticmethod
    def assess_benchmark(benchmark_id: str, records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        return assess_trace(benchmark_id, records)

    def revision_proposal(self, project_id: str, mission_id: str, *, candidate_id: str | None = None) -> dict[str, Any]:
        if self.revisions is None:
            raise FabricationValidationError("physical revision proposal integration is not configured")
        return self.revisions.build(project_id, mission_id, candidate_id=candidate_id)
