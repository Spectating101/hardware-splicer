from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.electrical_design import (
    ElectricalComponent,
    ElectricalDesign,
    ElectricalNet,
    ElectricalPin,
    NetKind,
)
from hardware_splicer.engineering_review_identity import resolve_engineering_review
from hardware_splicer.machine_project import (
    Component,
    Domain,
    MachineProject,
    Subsystem,
)

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


def _electrical_design() -> ElectricalDesign:
    return ElectricalDesign(
        design_id="design-1",
        project_id="project-1",
        components=[
            ElectricalComponent(
                component_id="electrical:source-component:source_component_r12",
                reference="R12",
                name="1k resistor",
                pin_ids=["electrical:source-port:r12_1", "electrical:source-port:r12_2"],
                metadata={
                    "identity": {
                        "source_component_id": "source_component_r12",
                        "kicad_reference": "R12",
                    }
                },
            )
        ],
        pins=[
            ElectricalPin(
                pin_id="electrical:source-port:r12_1",
                component_id="electrical:source-component:source_component_r12",
                number="1",
                name="1",
                net_id="electrical:source-net:vbus",
            ),
            ElectricalPin(
                pin_id="electrical:source-port:r12_2",
                component_id="electrical:source-component:source_component_r12",
                number="2",
                name="2",
                net_id=None,
            ),
        ],
        nets=[
            ElectricalNet(
                net_id="electrical:source-net:vbus",
                name="VBUS",
                kind=NetKind.POWER,
                pin_ids=["electrical:source-port:r12_1"],
                metadata={
                    "identity": {
                        "source_net_ids": ["source_net_vbus"],
                        "kicad_net_name": "VBUS",
                    }
                },
            )
        ],
    )


def _machine_project() -> MachineProject:
    return MachineProject(
        project_id="project-1",
        name="Identity fixture",
        purpose="Resolve external findings without display-name guessing.",
        subsystems=[
            Subsystem(
                subsystem_id="subsystem-electrical",
                name="Electrical",
                domain=Domain.ELECTRICAL,
                component_ids=["machine:r12"],
            )
        ],
        components=[
            Component(
                component_id="machine:r12",
                name="Resistor in the power path",
                domain=Domain.ELECTRICAL,
                subsystem_id="subsystem-electrical",
                metadata={
                    "identity": {
                        "electrical_component_id": (
                            "electrical:source-component:source_component_r12"
                        ),
                        "kicad_reference": "R12",
                    }
                },
            )
        ],
        interfaces=[],
    )


def _review() -> dict:
    return {
        "ok": True,
        "schema_version": "hardware_splicer.engineering_review.v1",
        "run_id": "review-1",
        "cache_key": "cache-1",
        "authority": {
            "maximum": "observed",
            "may_authorize_release": False,
        },
        "findings": [
            {
                "finding_id": "schematic:power:1",
                "rule_id": "power_path",
                "severity": "warning",
                "components": ["R12", "UNKNOWN_COMPONENT"],
                "nets": ["VBUS", "UNKNOWN_NET"],
                "authority": "observed",
            }
        ],
    }


def test_resolves_exact_electrical_and_machine_aliases_without_authority_upgrade() -> None:
    resolved = resolve_engineering_review(
        _review(),
        _electrical_design(),
        _machine_project(),
    )

    finding = resolved["findings"][0]
    identity = finding["identity_resolution"]
    assert finding["authority"] == "observed"
    assert resolved["authority"]["maximum"] == "observed"
    assert resolved["authority"]["may_authorize_release"] is False
    assert identity["canonical"] == {
        "electrical_component_ids": [
            "electrical:source-component:source_component_r12"
        ],
        "electrical_net_ids": ["electrical:source-net:vbus"],
        "machine_component_ids": ["machine:r12"],
        "machine_interface_ids": [],
    }
    assert identity["electrical_components"][0] == {
        "input": "R12",
        "status": "resolved",
        "canonical_id": "electrical:source-component:source_component_r12",
    }
    assert identity["electrical_components"][1] == {
        "input": "UNKNOWN_COMPONENT",
        "status": "unresolved",
    }
    assert identity["electrical_nets"][1] == {
        "input": "UNKNOWN_NET",
        "status": "unresolved",
    }
    assert identity["fully_resolved"] is False
    assert resolved["identity_resolution"]["unresolved_reference_count"] == 2


def test_ambiguous_alias_remains_explicit() -> None:
    design = ElectricalDesign(
        design_id="ambiguous",
        project_id="project-1",
        components=[
            ElectricalComponent(
                component_id="electrical:u1",
                reference="U1",
                name="First",
                metadata={"identity": {"source_component_id": "shared_source"}},
            ),
            ElectricalComponent(
                component_id="electrical:u2",
                reference="U2",
                name="Second",
                metadata={"identity": {"source_component_id": "shared_source"}},
            ),
        ],
    )
    review = {
        "schema_version": "hardware_splicer.engineering_review.v1",
        "findings": [
            {
                "finding_id": "ambiguous",
                "components": ["shared_source"],
                "nets": [],
                "authority": "observed",
            }
        ],
    }

    resolved = resolve_engineering_review(review, design)
    row = resolved["findings"][0]["identity_resolution"]["electrical_components"][0]

    assert row == {
        "input": "shared_source",
        "status": "ambiguous",
        "candidate_ids": ["electrical:u1", "electrical:u2"],
    }
    assert resolved["identity_resolution"]["unresolved_reference_count"] == 1


def test_machine_display_name_alone_does_not_resolve() -> None:
    project = MachineProject(
        project_id="project-1",
        name="No display guessing",
        purpose="Test identity boundary.",
        subsystems=[
            Subsystem(
                subsystem_id="subsystem-electrical",
                name="Electrical",
                domain=Domain.ELECTRICAL,
                component_ids=["machine:unrelated"],
            )
        ],
        components=[
            Component(
                component_id="machine:unrelated",
                name="R12",
                domain=Domain.ELECTRICAL,
                subsystem_id="subsystem-electrical",
            )
        ],
    )

    resolved = resolve_engineering_review(_review(), _electrical_design(), project)
    machine_rows = resolved["findings"][0]["identity_resolution"]["machine_components"]

    assert all(row.get("canonical_id") != "machine:unrelated" for row in machine_rows)


def test_product_api_persists_hash_pinned_resolved_derivative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", "1")
    compilation = tmp_path / "build_compilation"
    compilation.mkdir()
    source_path = compilation / "ENGINEERING_REVIEW.json"
    source_path.write_text(json.dumps(_review()), encoding="utf-8")

    client = TestClient(create_product_app())
    response = client.post(
        "/v1/build-files/engineering-review/resolve-identities",
        json={
            "build_dir": str(tmp_path),
            "electrical_design": _electrical_design().model_dump(mode="json"),
            "machine_project": _machine_project().model_dump(mode="json"),
        },
    )

    assert response.status_code == 200
    body = response.json()
    artifact = Path(body["artifact"])
    assert artifact == compilation / "ENGINEERING_REVIEW_RESOLVED.json"
    assert artifact.is_file()
    persisted = json.loads(artifact.read_text(encoding="utf-8"))
    assert len(persisted["source_review"]["sha256"]) == 64
    assert persisted["findings"][0]["identity_resolution"]["canonical"][
        "electrical_component_ids"
    ] == ["electrical:source-component:source_component_r12"]
    assert persisted["authority"]["maximum"] == "observed"

    paths = set(client.get("/openapi.json").json()["paths"])
    assert "/v1/build-files/engineering-review/resolve-identities" in paths
