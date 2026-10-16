from __future__ import annotations

import httpx
import pytest

from hardware_splicer.fabrication_capability_registry import (
    FabricationCapabilityDescriptor,
    FabricationCapabilityRegistry,
)
from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.kicad_cli_operator import KicadCliOperator, KicadProjectRegistry
from hardware_splicer.mtconnect_observer import MtconnectExecutionError, MtconnectObserver
from hardware_splicer.ngspice_operator import NgspiceCircuitRegistry, NgspiceOperator
from hardware_splicer.openpnp_simulation import OpenPnpJobRegistry, OpenPnpSimulationInspector
from hardware_splicer.physical_observation_store import PhysicalObservationStore


def test_capability_match_rejects_string_instead_of_collection():
    registry = FabricationCapabilityRegistry()
    registry.register(FabricationCapabilityDescriptor(
        operator_id="printer-a",
        kind="printer",
        display_name="Printer",
        capabilities=("additive_fabrication",),
        limits={},
    ))
    with pytest.raises(FabricationValidationError, match="collection"):
        registry.match(required_capabilities="additive_fabrication")


def test_kicad_refuses_symlink_output_root(tmp_path):
    (tmp_path / "board.kicad_sch").write_text("(kicad_sch)\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".hs-kicad").symlink_to(outside, target_is_directory=True)
    projects = KicadProjectRegistry()
    projects.register(project_id="board", root=tmp_path, schematic="board.kicad_sch")
    operator = KicadCliOperator(projects=projects)
    with pytest.raises(FabricationValidationError, match="output root"):
        operator.verify("board")


def test_ngspice_refuses_symlink_output_root(tmp_path):
    (tmp_path / "board.cir").write_text("V1 out 0 3.3\n.op\n.end\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".hs-ngspice").symlink_to(outside, target_is_directory=True)
    circuits = NgspiceCircuitRegistry(tmp_path)
    circuits.register(circuit_id="board", path="board.cir")
    operator = NgspiceOperator(circuits=circuits)
    with pytest.raises(FabricationValidationError, match="output root"):
        operator.run("board")


def test_mtconnect_rejects_dtd_entity_xml(tmp_path):
    xml = b'''<?xml version="1.0"?><!DOCTYPE x [<!ENTITY ext "unsafe">]><MTConnectStreams><Header instanceId="1"/></MTConnectStreams>'''

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/xml"}, content=xml)

    observations = PhysicalObservationStore(tmp_path / "observations")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    observer = MtconnectObserver(
        source_id="mill",
        base_url="http://mtconnect.test",
        observations=observations,
        client=client,
    )
    with pytest.raises(MtconnectExecutionError, match="DTD/entity"):
        observer.current()
    assert observations.list_public() == []
    client.close()


def test_openpnp_refuses_symlink_job_and_dtd_package(tmp_path):
    real_job = tmp_path / "real.job.xml"
    real_job.write_text("<openpnp-job/>", encoding="utf-8")
    alias = tmp_path / "alias.job.xml"
    alias.symlink_to(real_job)
    registry = OpenPnpJobRegistry()
    with pytest.raises(FabricationValidationError, match="symlink"):
        registry.register(job_id="alias", root=tmp_path, job_file="alias.job.xml")

    bad_job = tmp_path / "bad.job.xml"
    bad_job.write_text(
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY ext "unsafe">]><openpnp-job/>',
        encoding="utf-8",
    )
    registry.register(job_id="bad", root=tmp_path, job_file="bad.job.xml")
    with pytest.raises(FabricationValidationError, match="DTD/entity"):
        OpenPnpSimulationInspector(jobs=registry).inspect("bad")
