from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "apps" / "circuit-ai" / "circuit-ai-frontend"


def _read(relative: str) -> str:
    return (FRONTEND / relative).read_text(encoding="utf-8")


def test_execution_capability_proxy_targets_hardware_splicer_backend() -> None:
    source = _read("app/api/proxy/engineering/execution/capabilities/route.ts")

    assert "getHardwareSplicerApiUrl" in source
    assert "/v1/engineering/execution/capabilities" in source
    assert 'method: "GET"' in source
    assert 'cache: "no-store"' in source
    assert "proxyUiFailureResponse" in source


def test_engineering_layout_mounts_runtime_capability_truth() -> None:
    source = _read("app/engineering/layout.tsx")

    assert "EngineeringExecutionCapabilityPanel" in source
    assert "Execution host truth" in source
    assert "fixed bottom-4 right-4" in source
    assert "group-open:hidden" in source


def test_capability_panel_discloses_adapter_tool_policy_and_isolation_truth() -> None:
    source = _read("components/engineering-execution-capability-panel.tsx")

    assert "/api/proxy/engineering/execution/capabilities" in source
    assert "adapter only; tool unavailable" in source
    assert "installed; host execution disabled" in source
    assert "installed and permitted" in source
    assert "OS-level network isolation is not claimed" in source
    assert "Device access, flashing, power control, motion, and field release remain prohibited" in source


def test_engineering_action_panel_never_calls_execution_run() -> None:
    source = _read("components/engineering-action-panel.tsx")

    assert "/api/proxy/engineering/actions/prepare" in source
    assert "/api/proxy/engineering/execution/run" not in source
    assert "Preparation only • no automatic physical execution" in source
