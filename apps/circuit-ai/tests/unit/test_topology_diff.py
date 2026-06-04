from src.intelligence.topology_diff import TopologyDiff


def _reference_model():
    return {
        "components": {
            "R1": {"value": "10k", "footprint": "R_0805"},
            "R2": {"value": "1k", "footprint": "R_0805"},
            "U1": {"value": "STM32", "footprint": "QFN32"},
            "R3": {"value": "100", "footprint": "R_0805"},
        },
        "nets": {
            "NET_1": {
                "nodes": [
                    {"ref": "R1", "pin": "1"},
                    {"ref": "R2", "pin": "2"},
                ]
            },
            "NET_2": {
                "nodes": [
                    {"ref": "U1", "pin": "3"},
                    {"ref": "R3", "pin": "1"},
                ]
            },
        },
    }


def _visual_topology_passthrough():
    return {
        "component_instances": [
            {"instance_id": "R1", "class_name": "resistor"},
            {"instance_id": "R2", "class_name": "resistor"},
            {"instance_id": "U1", "class_name": "ic"},
            {"instance_id": "R3", "class_name": "resistor"},
        ],
        "connections": [
            {"component1": "R1", "component2": "R2"},
            {"component1": "U1:pin1", "component2": "R3"},
        ],
    }


def test_topology_diff_passes_when_signatures_match():
    diff = TopologyDiff()
    result = diff.compare(_reference_model(), _visual_topology_passthrough())

    assert result["status"] == "PASS"
    assert result["topology_delta"] == 0
    assert result["matched_clusters"] == 2
    assert not result["missing"]
    assert not result["extra"]


def test_topology_diff_reports_missing_and_extra_signatures():
    visual = _visual_topology_passthrough()
    # Break the visual netlist by replacing IC-resistor connectivity with resistor-resistor.
    visual["connections"] = [
        {"component1": "R1", "component2": "R2"},
        {"component1": "R1", "component2": "R3"},
    ]

    diff = TopologyDiff()
    result = diff.compare(_reference_model(), visual)

    assert result["status"] == "FAIL"
    assert result["topology_delta"] > 0
    assert result["missing"]
    assert result["extra"]
    assert any(item["signature"].startswith("ic:1|resistor:1") for item in result["missing"])


def test_topology_diff_is_empty_safe_on_bad_inputs():
    diff = TopologyDiff()
    result = diff.compare({"components": {}, "nets": {}}, {"component_instances": [], "connections": []})

    assert result["status"] == "PASS"
    assert result["topology_delta"] == 0
    assert result["reference_signature_count"] == 0
    assert result["observed_signature_count"] == 0
