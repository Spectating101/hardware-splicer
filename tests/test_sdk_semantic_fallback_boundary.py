from __future__ import annotations

import json
from pathlib import Path

import pytest

import hardware_splicer.integrations.qwen_netlist_compose as compose_module
import hardware_splicer.sdk as sdk


class _FailedCompile:
    ok = False
    build_id = "model-design"
    design_quality = {
        "build_ready": False,
        "build_graph_compiled": True,
        "electrical_safety_pass": False,
        "kicad_drc_pass": False,
        "kicad_drc_errors": 2,
        "erc_pass": True,
    }

    def to_dict(self) -> dict:
        return {
            "ok": False,
            "build_id": self.build_id,
            "design_quality": dict(self.design_quality),
        }


def test_compose_arbitrary_failed_model_compile_cannot_retry_through_legacy_picker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).resolve().parents[1]
    netlist = json.loads(
        (root / "examples/netlist_fixtures/json/usb_esp_dht22.json").read_text(encoding="utf-8")
    )

    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    monkeypatch.setattr(
        compose_module,
        "call_qwen_netlist_compose",
        lambda goal, constraints=None: {
            "ok": True,
            "provider": "cleanroom-test",
            "model": "deterministic-fixture",
            "netlist": netlist,
            "erc": {"pass": True, "errors": [], "warnings": []},
            "module_ids": ["usb-power-5v", "esp32-devkit", "dht22"],
        },
    )
    monkeypatch.setattr(sdk, "compile_from_netlist", lambda *args, **kwargs: _FailedCompile())

    import hardware_splicer.module_picker as legacy_picker

    monkeypatch.setattr(
        legacy_picker,
        "pick_modules_for_goal",
        lambda goal: (_ for _ in ()).throw(
            AssertionError("SDK failed-model retry executed legacy semantic picker")
        ),
    )

    result = sdk.compose_arbitrary(
        "model-generated design that deterministically fails compile",
        out_dir=tmp_path,
        allow_qwen=True,
    )

    assert result["ok"] is False
    assert result["compose_mode"] == "legacy_offline_blocked"
    assert result["design_quality"]["kicad_drc_errors"] == 2
    assert result["design_quality_gate"]["build_ready"] is False
