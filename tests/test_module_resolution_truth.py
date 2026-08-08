from __future__ import annotations

import json

import hardware_splicer.integrations.llm_policy as llm_policy
import hardware_splicer.module_resolution_truth as truth_module
from hardware_splicer.module_resolution_truth import (
    fill_capability_gaps,
    functional_salvage_identity_rows,
    infer_power_topology_truth,
    module_overrides_truth,
    resolve_inventory_identity,
)


def _llm(bindings):
    def fake_llm(prompt: str, **kwargs: object) -> dict:
        return {
            "ok": True,
            "provider": "identity-test",
            "model": "deterministic",
            "content": json.dumps({"bindings": bindings, "unresolved_questions": []}),
            "usage": {},
        }
    return fake_llm


def test_explicit_valid_module_id_is_declared_identity_without_model(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)

    def fail_model(*args, **kwargs):
        raise AssertionError("explicit physical identity unnecessarily called model")

    rows, meta = resolve_inventory_identity(
        [{"component_id": "mcu-1", "name": "controller", "module_id": "esp32-devkit"}],
        llm_callable=fail_model,
    )

    assert rows[0]["module_id"] == "esp32-devkit"
    assert rows[0]["identity_status"] == "declared"
    assert rows[0]["source"] == "declared_catalog_identity"
    assert meta["explicit_binding_count"] == 1
    assert meta["legacy_heuristic_used"] is False


def test_exact_distinctive_identity_can_bind_model_proposal(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    rows, _ = resolve_inventory_identity(
        [{"component_id": "fet-1", "name": "IRLZ44N MOSFET", "type": "mosfet"}],
        llm_callable=_llm([
            {"part_index": 0, "match_kind": "exact_identity", "module_id": "mosfet-irlz44n", "reasoning": "MPN token matches."}
        ]),
    )
    assert rows[0]["module_id"] == "mosfet-irlz44n"
    assert rows[0]["identity_status"] == "model_proposed"
    assert "irlz44n" in rows[0]["identity_basis"].lower()


def test_ao3400_cannot_be_substituted_to_irlz44n(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    rows, meta = resolve_inventory_identity(
        [{"component_id": "fet-1", "name": "AO3400 MOSFET", "type": "mosfet"}],
        llm_callable=_llm([
            {"part_index": 0, "match_kind": "exact_identity", "module_id": "mosfet-irlz44n", "reasoning": "Functionally similar MOSFET."}
        ]),
    )
    assert rows[0]["module_id"] is None
    assert rows[0]["identity_status"] == "unresolved"
    assert rows[0]["rejected_module_id"] == "mosfet-irlz44n"
    assert meta["unresolved_count"] == 1


def test_generic_dc_motor_cannot_become_catalog_representative(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    rows, _ = resolve_inventory_identity(
        [{"component_id": "motor-1", "name": "generic DC gear motor", "type": "dc_motor"}],
        llm_callable=_llm([
            {"part_index": 0, "match_kind": "exact_identity", "module_id": "dc_motor_3v_6v", "reasoning": "Same category."}
        ]),
    )
    assert rows[0]["module_id"] is None
    assert rows[0]["role"] == "act"
    assert rows[0]["source"] == "unresolved_identity"


def test_declared_equivalent_requires_persisted_equivalent_id(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    rows, _ = resolve_inventory_identity(
        [{
            "component_id": "sensor-1",
            "name": "external sensor assembly",
            "catalog_equivalent_id": "bme280",
            "type": "sensor",
        }],
        llm_callable=_llm([
            {"part_index": 0, "match_kind": "declared_equivalent", "module_id": "bme280", "reasoning": "Persisted equivalent."}
        ]),
    )
    assert rows[0]["module_id"] == "bme280"
    assert rows[0]["identity_match_kind"] == "declared_equivalent"


def test_provider_unavailable_keeps_part_unresolved_without_regex_fallback(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    monkeypatch.setattr(truth_module, "_identity_model_enabled", lambda: True)

    def failed_llm(*args, **kwargs):
        return {"ok": False, "error": "provider_failed"}

    rows, meta = resolve_inventory_identity(
        [{"name": "ESP32 devkit-looking board", "type": "controller"}],
        llm_callable=failed_llm,
    )
    assert rows[0]["module_id"] is None
    assert rows[0]["reason"] == "identity model/provider unavailable"
    assert meta["legacy_heuristic_used"] is False


def test_unknown_donor_hbridge_preserves_capability_without_l298n(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    rows = functional_salvage_identity_rows({
        "reusable_blocks": [
            {
                "block_id": "donor-hbridge-1",
                "name": "unknown donor H-bridge",
                "function_type": "actuator_driver",
                "capabilities": ["bidirectional_dc_motor_drive"],
                "status": "reusable",
            }
        ]
    })
    assert len(rows) == 1
    assert rows[0]["module_id"] is None
    assert rows[0]["role"] == "drv"
    assert rows[0]["external_capability_only"] is True
    assert rows[0]["donor_block_id"] == "donor-hbridge-1"
    assert "l298n" not in repr(rows).lower()


def test_missing_driver_is_capability_gap_not_magic_component(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    rows = fill_capability_gaps(
        [{"instance_id": "motor-1", "module_id": None, "role": "act", "source": "unresolved_identity"}],
        parts=[{"component_id": "motor-1", "name": "motor", "type": "dc_motor"}],
    )
    gap = next(row for row in rows if row.get("source") == "unresolved_capability_gap")
    assert gap["module_id"] is None
    assert gap["role"] == "drv"
    assert gap["required_capability"] == "actuator_driver_or_switch"
    assert "l298n" not in repr(gap).lower()
    assert "a4988" not in repr(gap).lower()


def test_power_topology_requires_explicit_contract_or_exact_bound_source(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    assert infer_power_topology_truth(
        [{"name": "12V wall adapter", "type": "power_source", "voltage_v": 12.0}],
        [],
        constraints={},
    ) == "unresolved"
    assert infer_power_topology_truth([], [], constraints={"power_topology": "usb_5v"}) == "usb_5v"
    assert infer_power_topology_truth([], [{"module_id": "dc-barrel-12v"}], constraints={}) == "barrel_12v"


def test_overrides_are_direct_bindings_without_substitution(monkeypatch) -> None:
    monkeypatch.setattr(llm_policy, "offline_salvage_enabled", lambda: False)
    overrides = module_overrides_truth([
        {"module_id": "mosfet-irf520", "role": "drv", "source": "declared_catalog_identity"},
    ])
    assert overrides == {"drv": "mosfet-irf520"}
    assert "mosfet-irlz44n" not in overrides.values()
