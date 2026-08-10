from __future__ import annotations

from hardware_splicer.netlist.erc import run_erc
from hardware_splicer.netlist.ir import CircuitNetlist, ComponentInstance, Net, PinRef


def _component(ref: str, module_id: str) -> ComponentInstance:
    return ComponentInstance(ref=ref, module_id=module_id)


def test_l298_structured_ttl_contract_accepts_esp32_3v3_drive() -> None:
    netlist = CircuitNetlist(
        source="contract_test",
        components=[
            _component("U1", "esp32-devkit"),
            _component("U2", "l298n"),
        ],
        nets=[
            Net(
                name="MOTOR_IN1",
                pins=[PinRef("U1", "GPIO4"), PinRef("U2", "IN1")],
            )
        ],
    )

    result = run_erc(netlist)

    assert result["errors"] == 0
    assert result["pass"] is True
    assert not [row for row in result["violations"] if row["severity"] == "error"]


def test_uncontracted_3v3_5v_logic_pair_remains_blocked() -> None:
    netlist = CircuitNetlist(
        source="contract_test",
        components=[
            _component("U1", "esp32-devkit"),
            _component("U2", "arduino-nano"),
        ],
        nets=[
            Net(
                name="UNPROVEN_LOGIC_BRIDGE",
                pins=[PinRef("U1", "GPIO4"), PinRef("U2", "D2")],
            )
        ],
    )

    result = run_erc(netlist)

    assert result["pass"] is False
    assert result["errors"] == 1
    assert result["violations"][0]["rule"] == "erc-voltage-mismatch"
