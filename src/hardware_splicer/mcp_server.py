"""MCP server — expose Hardware-Splicer compile engine to any MCP client.

Run:
  PYTHONPATH=src python -m hardware_splicer.mcp_server

Requires: pip install mcp  (see requirements-mcp.txt)
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Sequence

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError as exc:  # pragma: no cover - optional dependency
    print(
        "Hardware-Splicer MCP requires the 'mcp' package.\n"
        "  pip install -r requirements-mcp.txt\n",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

from . import sdk

app = Server("hardware-splicer")


def _tool_result(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=sdk.dump_json(payload))]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="hs_sdk_info",
            description=(
                "Capability card: what Hardware-Splicer engine does vs Flux, default env, "
                "honest limits (cosmetic copper, KiCad truth)."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="hs_engine_doctor",
            description="Check local runtime: Python deps, KiCad/node, app roots.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="hs_list_catalog_builds",
            description="List canned catalog build IDs compileable by the engine.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="hs_resolve_parts",
            description=(
                "Map inventory part rows (name, type, optional module_id, voltage_v) "
                "to module-library IDs and power topology."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "parts": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "e.g. [{\"name\": \"ESP32 devkit\", \"type\": \"microcontroller\"}]",
                    }
                },
                "required": ["parts"],
            },
        ),
        Tool(
            name="hs_suggest_modules",
            description="NL goal → open-catalog module suggestions (scratch mode starter set).",
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "e.g. wifi temperature logger"}
                },
                "required": ["goal"],
            },
        ),
        Tool(
            name="hs_plan_salvage",
            description=(
                "Plan salvage splice from goal + inventory without KiCad compile (~fast). "
                "Use before hs_salvage_bringup when exploring feasibility."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "parts": {"type": "array", "items": {"type": "object"}},
                    "constraints": {"type": "object"},
                    "project_name": {"type": "string"},
                },
                "required": ["goal", "parts"],
            },
        ),
        Tool(
            name="hs_compose",
            description=(
                "Compose and compile: NL phrase, module_ids, or canvas nodes → "
                "wired graph, netlist, KiCad PCB, BOM, firmware scaffold. "
                "KiCad DRC errors=0 is the pass bar; copper is cosmetic preview by default."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "phrase": {"type": "string"},
                    "module_ids": {"type": "array", "items": {"type": "string"}},
                    "canvas_nodes": {"type": "array", "items": {"type": "object"}},
                    "canvas_wires": {"type": "array", "items": {"type": "object"}},
                    "constraints": {"type": "object"},
                    "material_mode": {"type": "string", "enum": ["scratch", "salvage"]},
                    "salvage_mode": {"type": "boolean"},
                    "out_dir": {"type": "string"},
                    "export_gerber": {"type": "boolean", "default": False},
                    "fab_profile": {"type": "boolean", "default": False},
                    "arbitrary": {"type": "boolean", "default": False},
                },
            },
        ),
        Tool(
            name="hs_salvage_bringup",
            description=(
                "Full salvage bring-up from PROJECT_INTAKE-shaped JSON: "
                "splice + compile + SALVAGE_BRINGUP_REPORT.json."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "intake": {"type": "object"},
                    "out_dir": {"type": "string"},
                    "export_gerber": {"type": "boolean", "default": False},
                },
                "required": ["intake"],
            },
        ),
        Tool(
            name="hs_compose_arbitrary",
            description=(
                "NL goal → Qwen text netlist IR (when DASHSCOPE_API_KEY set) → KiCad compile. "
                "Use arbitrary=true for Qwen text netlist path. fab_profile exports gerbers headlessly (no FreeRouting)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "constraints": {"type": "object"},
                    "fab_profile": {"type": "boolean", "default": False},
                    "export_gerber": {"type": "boolean"},
                    "out_dir": {"type": "string"},
                    "allow_qwen": {"type": "boolean", "default": True},
                },
                "required": ["goal"],
            },
        ),
        Tool(
            name="hs_jarvis_build",
            description=(
                "Primary electrical JARVIS path: NL goal (+ optional salvage parts) → "
                "Qwen netlist when keyed → KiCad compile → simulation → TRUST_REPORT + JARVIS narrative."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "parts": {"type": "array", "items": {"type": "object"}},
                    "constraints": {"type": "object"},
                    "project_name": {"type": "string"},
                    "out_dir": {"type": "string"},
                    "export_gerber": {"type": "boolean", "default": False},
                    "allow_qwen": {"type": "boolean", "default": True},
                },
                "required": ["goal"],
            },
        ),
        Tool(
            name="hs_inspect_fab",
            description=(
                "Inspect fabrication package on disk (PCB, BOM, Gerbers) without recompiling. "
                "Pass a catalog build dir or splice output dir."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "build_dir": {"type": "string", "description": "Compile or splice output directory"},
                },
                "required": ["build_dir"],
            },
        ),
        Tool(
            name="hs_verify_engine",
            description=(
                "Compile catalog builds headlessly and check KiCad DRC errors=0. "
                "Slow (~20s full set). No FreeRouting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "build_ids": {"type": "array", "items": {"type": "string"}},
                    "max_warnings": {"type": "integer", "default": 500},
                    "out_dir": {"type": "string"},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> Sequence[TextContent]:
    args = arguments or {}

    if name == "hs_sdk_info":
        return _tool_result(sdk.sdk_info())
    if name == "hs_engine_doctor":
        return _tool_result(sdk.engine_doctor())
    if name == "hs_list_catalog_builds":
        return _tool_result(sdk.list_catalog_builds())
    if name == "hs_resolve_parts":
        return _tool_result(sdk.resolve_inventory_parts(args.get("parts") or []))
    if name == "hs_suggest_modules":
        return _tool_result(sdk.suggest_modules(str(args.get("goal") or "")))
    if name == "hs_plan_salvage":
        return _tool_result(
            sdk.plan_salvage(
                goal=str(args.get("goal") or ""),
                parts=args.get("parts") or [],
                constraints=args.get("constraints"),
                project_name=args.get("project_name"),
            )
        )
    if name == "hs_compose":
        return _tool_result(
            sdk.compose_design(
                phrase=args.get("phrase"),
                module_ids=args.get("module_ids"),
                canvas_nodes=args.get("canvas_nodes"),
                canvas_wires=args.get("canvas_wires"),
                constraints=args.get("constraints"),
                material_mode=args.get("material_mode"),
                salvage_mode=bool(args.get("salvage_mode")),
                out_dir=args.get("out_dir"),
                export_gerber=bool(args.get("export_gerber")),
                fab_profile=bool(args.get("fab_profile")),
                arbitrary=bool(args.get("arbitrary")),
            )
        )
    if name == "hs_compose_arbitrary":
        return _tool_result(
            sdk.compose_arbitrary(
                str(args.get("goal") or ""),
                constraints=args.get("constraints"),
                out_dir=args.get("out_dir"),
                fab_profile=bool(args.get("fab_profile")),
                export_gerber=args.get("export_gerber"),
                allow_qwen=bool(args.get("allow_qwen", True)),
            )
        )
    if name == "hs_salvage_bringup":
        return _tool_result(
            sdk.salvage_bringup(
                args.get("intake") or {},
                out_dir=args.get("out_dir"),
                export_gerber=bool(args.get("export_gerber")),
            )
        )
    if name == "hs_jarvis_build":
        return _tool_result(
            sdk.jarvis_build(
                str(args.get("goal") or ""),
                parts=args.get("parts"),
                constraints=args.get("constraints"),
                project_name=args.get("project_name"),
                out_dir=args.get("out_dir"),
                export_gerber=bool(args.get("export_gerber")),
                allow_qwen=bool(args.get("allow_qwen", True)),
            )
        )
    if name == "hs_inspect_fab":
        return _tool_result(sdk.inspect_fab_build_dir(str(args.get("build_dir") or "")))
    if name == "hs_verify_engine":
        return _tool_result(
            sdk.verify_engine(
                build_ids=args.get("build_ids"),
                max_warnings=int(args.get("max_warnings") or 500),
                out_dir=args.get("out_dir"),
            )
        )

    raise ValueError(f"Unknown tool: {name}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
