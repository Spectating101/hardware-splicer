"""Model-written netlists must be opt-in on every entry point, matching REST."""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any

import pytest

from hardware_splicer import jarvis_build as jarvis_module
from hardware_splicer import sdk


@pytest.fixture
def mcp_server() -> Any:
    # The default dev install does not include the legacy MCP SDK. Keep the
    # SDK/REST defaults covered there, and exercise MCP only with its extra.
    pytest.importorskip("mcp.server", reason="requires the optional legacy MCP SDK")
    pytest.importorskip("mcp.types", reason="requires the optional legacy MCP SDK")
    from hardware_splicer import mcp_server as server

    return server


@pytest.mark.parametrize(
    "func",
    [
        sdk.compose_design,
        sdk.compose_design_agent_loop,
        sdk.compose_agent_bench_loop,
        sdk.jarvis_build,
        jarvis_module.jarvis_build,
    ],
)
def test_allow_llm_first_defaults_to_false(func: Any) -> None:
    param = inspect.signature(func).parameters["allow_llm_first"]
    assert param.default is False


def test_rest_default_is_still_false() -> None:
    from hardware_splicer.api import ComposeRequest

    assert ComposeRequest(phrase="x").allow_llm_first is False


def test_mcp_tool_schemas_default_allow_llm_first_false(mcp_server: Any) -> None:
    tools = asyncio.run(mcp_server.list_tools())
    seen = {}
    for tool in tools:
        prop = (tool.inputSchema.get("properties") or {}).get("allow_llm_first")
        if prop is not None:
            seen[tool.name] = prop.get("default")
    assert {"hs_compose", "hs_compose_drc_agent", "hs_compose_bench_loop", "hs_jarvis_build"} <= set(seen)
    assert all(value is False for value in seen.values()), seen


@pytest.mark.parametrize(
    ("tool", "sdk_name", "args"),
    [
        ("hs_compose", "compose_design", {"phrase": "x"}),
        ("hs_compose_drc_agent", "compose_design_agent_loop", {"phrase": "x"}),
        ("hs_compose_bench_loop", "compose_agent_bench_loop", {"phrase": "x"}),
        ("hs_jarvis_build", "jarvis_build", {"goal": "x"}),
    ],
)
def test_mcp_handlers_do_not_enable_llm_first_when_omitted(
    monkeypatch: pytest.MonkeyPatch, mcp_server: Any,
    tool: str, sdk_name: str, args: dict[str, Any]
) -> None:
    calls: list[dict[str, Any]] = []

    def fake(*a: Any, **kw: Any) -> dict[str, Any]:
        calls.append(kw)
        return {"ok": True}

    monkeypatch.setattr(sdk, sdk_name, fake)
    asyncio.run(mcp_server.call_tool(tool, args))
    assert calls and calls[0]["allow_llm_first"] is False
    asyncio.run(mcp_server.call_tool(tool, {**args, "allow_llm_first": True}))
    assert calls[1]["allow_llm_first"] is True


def test_jarvis_build_skips_model_compose_unless_opted_in(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setattr(jarvis_module, "llm_first_enabled", lambda: True)
    taken: list[str] = []

    def fake_llm_first(*a: Any, **kw: Any) -> dict[str, Any]:
        taken.append("llm_first")
        return {"ok": False, "compose_mode": "x", "compile_result": None}

    def fake_scratch(*a: Any, **kw: Any) -> dict[str, Any]:
        taken.append("scratch_only")
        return {"ok": False, "compose_mode": "scratch_pipeline", "compile_result": None}

    monkeypatch.setattr(jarvis_module, "_open_compose_llm_first", fake_llm_first)
    monkeypatch.setattr(jarvis_module, "_open_compose_scratch_only", fake_scratch)
    jarvis_module.jarvis_build("some goal", out_dir=tmp_path / "a")
    assert taken == ["scratch_only"]
    jarvis_module.jarvis_build("some goal", out_dir=tmp_path / "b", allow_llm_first=True)
    assert taken == ["scratch_only", "llm_first"]
