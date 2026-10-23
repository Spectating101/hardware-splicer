"""DC winding terminals are not logic/chassis ground.

A generic motor catalog's legacy GND label represents one winding lead:
an H-bridge can switch this node to either rail. The electrical review must
recognize that without ignoring true logic GND-to-GPIO shorts.
"""
from hardware_splicer.pcb.safety_rules import analyze_build


def _wires(*pairs):
    return [
        {"id": f"w{i}", "from": {"nodeId": a, "pinId": pa},
         "to": {"nodeId": b, "pinId": pb}}
        for i, ((a, pa), (b, pb)) in enumerate(pairs, 1)
    ]


def test_h_bridge_winding_leads_do_not_create_fake_ground_short():
    graph = {
        "nodes": [
            {"id": "d", "moduleId": "l298n"},
            {"id": "left", "moduleId": "dc_motor_3v_6v"},
            {"id": "right", "moduleId": "dc_motor_3v_6v"},
        ],
        "wires": _wires(
            (("d", "OUT1"), ("left", "VCC")),
            (("d", "OUT2"), ("left", "GND")),
            (("d", "OUT3"), ("right", "VCC")),
            (("d", "OUT4"), ("right", "GND")),
        ),
    }
    issues = analyze_build(graph)
    assert not [issue for issue in issues if issue["level"] == "error" and "Wire connects GND" in issue["message"]]
    # Driver remains unpowered; passing this invariant is not fabrication safety.
    assert any("no power connection" in issue["message"] for issue in issues)


def test_true_logic_gnd_connected_to_signal_stays_a_hard_error():
    graph = {
        "nodes": [
            {"id": "mcu", "moduleId": "esp32-devkit"},
            {"id": "drv", "moduleId": "l298n"},
        ],
        "wires": _wires((("mcu", "GND"), ("drv", "IN1"))),
    }
    issues = analyze_build(graph)
    assert any(issue["level"] == "error" and "Wire connects GND" in issue["message"]
               for issue in issues)


def test_winding_ground_label_not_a_ground_requirement():
    graph = {
        "nodes": [{"id": "motor", "moduleId": "dc_motor_3v_6v"}],
        "wires": [],
    }
    issues = analyze_build(graph)
    assert not any("no GND connection" in item["message"] for item in issues)


def test_direct_gpio_to_motor_winding_is_rejected():
    graph = {
        "nodes": [
            {"id": "mcu", "moduleId": "esp32-devkit"},
            {"id": "motor", "moduleId": "dc_motor_3v_6v"},
        ],
        "wires": _wires((("mcu", "GPIO16"), ("motor", "VCC"))),
    }
    issues = analyze_build(graph)
    assert any(
        i["level"] == "error" and "directly to an MCU output" in i["message"]
        for i in issues
    )


def test_motor_return_through_mcu_ground_is_not_silently_recommended():
    graph = {
        "nodes": [
            {"id": "mcu", "moduleId": "esp32-devkit"},
            {"id": "motor", "moduleId": "dc_motor_3v_6v"},
        ],
        "wires": _wires((("mcu", "GND"), ("motor", "GND"))),
    }
    issues = analyze_build(graph)
    assert any("high-current ground path" in i["message"] for i in issues)
