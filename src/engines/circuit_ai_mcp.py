"""
Circuit-AI MCP Server (Integrated)
==================================
Leverages the official 'mcp' SDK pattern found in 'jobs_mcp.py'.
Exposes the new engines as standard MCP Tools.
"""

from typing import Any, Sequence
import asyncio
import sys
import os

# Fix path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent, EmbeddedResource, ImageContent
except ImportError:
    # Fallback for dev environment if SDK is missing
    # In production, this file requires 'mcp' pip package
    print("Warning: 'mcp' SDK not found. Install it to run this server.")
    sys.exit(1)

from generative.generative_design_agent import GenerativeAgent
from cam.repair_orchestrator import RepairOrchestrator
from cam.gcode_engine import SmartCAM

# Initialize Server
app = Server("circuit-ai-hardware")

# Initialize Engines
gen_agent = GenerativeAgent()
orchestrator = RepairOrchestrator()
cam = SmartCAM()

@app.list_tools()
def list_tools() -> list[Tool]:
    return [
        Tool(
            name="generate_circuit_design",
            description="Generates a structured circuit design plan from a natural language prompt.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The design request (e.g. 'Add a blinking LED')"}
                },
                "required": ["prompt"]
            }
        ),
        Tool(
            name="diagnose_and_repair",
            description="Runs the autonomous repair loop on a board. Detects defects and generates G-Code.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="optimize_gcode",
            description="Generates safety-optimized G-Code for a list of components.",
            inputSchema={
                "type": "object",
                "properties": {
                    "components": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of component dicts with 'ref', 'x', 'y', 'sensitive'"
                    }
                },
                "required": ["components"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    if name == "generate_circuit_design":
        prompt = arguments.get("prompt")
        result = gen_agent.generate_solution(prompt)
        return [TextContent(type="text", text=str(result))]

    elif name == "diagnose_and_repair":
        result = orchestrator.generate_repair_plan()
        return [TextContent(type="text", text=str(result))]

    elif name == "optimize_gcode":
        components = arguments.get("components")
        result = cam.generate_optimized_probe_sequence(components)
        return [TextContent(type="text", text=result)]

    raise ValueError(f"Unknown tool: {name}")

async def main():
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())