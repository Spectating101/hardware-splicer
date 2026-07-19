#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.integration_stack import IntegrationStack


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/tmp/hardware_splicer_integration_stack")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stack = IntegrationStack(graph_id="verify-integration-stack")
    contracts = stack.ingest_functional_salvage(
        [
            {
                "board_id": "enabot-mainboard",
                "block_id": "dual-hbridge-01",
                "name": "Dual H-bridge motor driver",
                "function_type": "actuator_driver",
                "capabilities": ["dual motor driver", "h-bridge"],
                "connector_refs": ["J_MOTOR_L", "J_MOTOR_R", "J_LOGIC"],
            }
        ]
    )
    contract = contracts[0]
    package = stack.write_package(contract.interface_id, out)

    assert contract.virtual_module_id == "donor:enabot-mainboard:dual-hbridge-01"
    assert contract.reference_equivalents[0]["module_id"] == "l298n"
    assert contract.reference_equivalents[0]["electrical_contract_inherited"] is False
    assert package["compile_status"] == "blocked"
    assert package["resolved_module"]["firmware_authorized"] is False

    blocked_fw = stack.generate_platformio(
        manifest={
            "target": {"platform": "espressif32", "board": "esp32dev"},
            "interfaces": {},
            "firmware_authorized": False,
        },
        out_dir=out / "firmware-blocked",
    )
    assert blocked_fw.status.value == "blocked"

    projection = stack.project_tscircuit(
        modules=[package["resolved_module"]],
        wires=[],
        project_name="integration-stack-verification",
        out_path=out / "circuit.json",
    )
    assert projection.ok

    report = {
        "ok": True,
        "contract": contract.to_dict(),
        "package": package,
        "blocked_firmware": blocked_fw.to_dict(),
        "tscircuit_projection": projection.to_dict(),
    }
    (out / "VERIFY_INTEGRATION_STACK.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
