from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from hardware_splicer.backends import (
    BackendResult,
    write_platformio_project,
    write_tscircuit_projection,
)
from hardware_splicer.bench import donor_interface_discovery_recipe
from hardware_splicer.donor import InterfaceContract, interface_from_functional_salvage
from hardware_splicer.evidence import EvidenceGraph


SCHEMA_VERSION = "hardware_splicer.integration_stack.v1"


class IntegrationStack:
    """Evidence-first orchestration around optional specialist backends.

    The stack never upgrades a functional analogy into an electrical contract.
    Unknown donor interfaces produce a bench recipe and block firmware generation.
    """

    def __init__(self, *, graph_id: str) -> None:
        self.evidence_graph = EvidenceGraph(graph_id=graph_id)
        self.interfaces: Dict[str, InterfaceContract] = {}

    def ingest_functional_salvage(self, blocks: Iterable[Mapping[str, Any]]) -> List[InterfaceContract]:
        created: List[InterfaceContract] = []
        for block in blocks:
            contract = interface_from_functional_salvage(block)
            self.interfaces[contract.interface_id] = contract
            self.evidence_graph.upsert_entity(
                contract.virtual_module_id,
                entity_type="donor_functional_block",
                board_id=contract.board_id,
                block_id=contract.block_id,
                functional_role=contract.functional_role,
                interface_status=contract.status.value,
            )
            created.append(contract)
        return created

    def build_interface_package(self, interface_id: str) -> Dict[str, Any]:
        contract = self.interfaces[interface_id]
        recipe = donor_interface_discovery_recipe(interface_id)
        return {
            "schema_version": SCHEMA_VERSION,
            "interface_contract": contract.to_dict(),
            "resolved_module": contract.to_resolved_module(),
            "bench_recipe": recipe.to_dict(),
            "compile_status": "ready" if contract.can_generate_firmware() else "blocked",
            "blockers": contract.unresolved_fields(),
        }

    def write_package(self, interface_id: str, out_dir: str | Path) -> Dict[str, Any]:
        root = Path(out_dir)
        root.mkdir(parents=True, exist_ok=True)
        package = self.build_interface_package(interface_id)
        contract_path = root / "INTERFACE_CONTRACT.json"
        recipe_path = root / "BENCH_RECIPE.json"
        graph_path = root / "EVIDENCE_GRAPH.json"
        contract_path.write_text(
            json.dumps(package["interface_contract"], indent=2), encoding="utf-8"
        )
        recipe_path.write_text(json.dumps(package["bench_recipe"], indent=2), encoding="utf-8")
        graph_path.write_text(
            json.dumps(self.evidence_graph.to_dict(), indent=2), encoding="utf-8"
        )
        package["artifacts"] = [str(contract_path), str(recipe_path), str(graph_path)]
        return package

    def project_tscircuit(
        self,
        *,
        modules: Iterable[Mapping[str, Any]],
        wires: Iterable[Mapping[str, Any]],
        project_name: str,
        out_path: str | Path,
    ) -> BackendResult:
        return write_tscircuit_projection(
            modules=modules,
            wires=wires,
            project_name=project_name,
            out_path=out_path,
        )

    def generate_platformio(
        self,
        *,
        manifest: Mapping[str, Any],
        out_dir: str | Path,
    ) -> BackendResult:
        return write_platformio_project(manifest, out_dir)
