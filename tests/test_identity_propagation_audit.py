from __future__ import annotations

from hardware_splicer.identity_propagation_audit import audit_identity_propagation


def _base_package():
    return {
        "resolved_modules": [
            {
                "instance_id": "sensor-1",
                "module_id": "bme280",
                "role": "sns",
                "source": "declared_catalog_identity",
                "identity_status": "declared",
            },
            {
                "instance_id": "driver-gap",
                "module_id": None,
                "role": "drv",
                "source": "unresolved_capability_gap",
                "identity_status": "unresolved",
            },
        ]
    }


def test_trusted_bound_module_can_flow_into_graph_and_firmware() -> None:
    package = _base_package()
    package.update(
        {
            "graph_input": {"nodes": [{"module_id": "bme280"}]},
            "firmware_scaffold": {"sensor_module_id": "bme280"},
            "bringup_card": {"module_ids": ["bme280"]},
        }
    )

    report = audit_identity_propagation(package)

    assert report["status"] == "pass"
    assert report["finding_count"] == 0
    assert report["trusted_module_ids"] == ["bme280"]
    assert report["checks"]["graph_identity_closed"] is True
    assert report["checks"]["firmware_identity_closed"] is True


def test_unknown_driver_cannot_reappear_as_l298n_in_firmware_or_graph() -> None:
    package = _base_package()
    package.update(
        {
            "graph_input": {
                "nodes": [
                    {"module_id": "bme280"},
                    {"module_id": "l298n"},
                ]
            },
            "firmware_scaffold": {
                "driver_module_id": "l298n",
            },
        }
    )

    report = audit_identity_propagation(package)

    assert report["status"] == "blocked"
    assert report["blocking_finding_count"] == 2
    assert {row["surface"] for row in report["findings"]} == {
        "graph_input",
        "firmware_scaffold",
    }
    assert all(row["module_id"] == "l298n" for row in report["findings"])


def test_bom_can_propose_future_component_but_it_is_not_inventory_truth() -> None:
    package = _base_package()
    package["bom_estimate"] = {
        "items": [
            {
                "module_id": "mosfet-irlz44n",
                "reason": "Candidate future purchase",
            }
        ]
    }

    report = audit_identity_propagation(package)

    assert report["status"] == "review"
    assert report["blocking_finding_count"] == 0
    assert report["review_finding_count"] == 1
    finding = report["findings"][0]
    assert finding["surface"] == "bom_estimate"
    assert finding["module_id"] == "mosfet-irlz44n"
    assert finding["severity"] == "review"


def test_mechanical_projection_of_unbound_catalog_part_is_review_not_physical_truth() -> None:
    package = _base_package()
    package["mechanism_pack"] = {
        "project_spec": {
            "mounts": [
                {"module_id": "sg90"},
            ]
        }
    }

    report = audit_identity_propagation(package)

    assert report["status"] == "review"
    assert report["review_finding_count"] == 1
    assert report["findings"][0]["surface"] == "mechanism_pack"
    assert report["findings"][0]["module_id"] == "sg90"


def test_workshop_design_proposal_is_trusted_as_proposal_not_existing_inventory() -> None:
    package = _base_package()
    package["resolved_modules"].append(
        {
            "instance_id": "design-driver-1",
            "module_id": "mosfet-irlz44n",
            "role": "drv",
            "source": "workshop_design_proposal",
            "identity_status": "proposed_design_component",
            "physical_inventory_identity": False,
        }
    )
    package["graph_input"] = {
        "nodes": [
            {"module_id": "mosfet-irlz44n"},
        ]
    }

    report = audit_identity_propagation(package)

    assert report["status"] == "pass"
    assert "mosfet-irlz44n" in report["trusted_module_ids"]
