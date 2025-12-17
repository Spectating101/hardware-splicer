#!/usr/bin/env python3
"""
Design Assistant: prompts the LLM for a block diagram/BOM/topology sketch from a use case.
Requires LLM access (CEREBRAS_API_KEY) or runs stubbed if LLM is disabled.
"""
import asyncio
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from circuit_agent import CircuitAgent, LLM_ENABLED


async def run_design_assistant():
    use_case = input("Describe your desired tool/circuit (e.g., 'USB-C PD trigger for 12V out'): ").strip()
    constraints = input("Constraints (voltage/current/size/cost/safety), or leave blank: ").strip()

    prompt = f"""
You are a hardware design assistant. Propose a circuit architecture for the following use case:

Use case: {use_case}
Constraints: {constraints or "None specified"}

Output:
1) Block diagram in text (major blocks and signal/power flow).
2) BOM (major parts with rough specs).
3) Topology sketch: describe how blocks connect (nets) and any critical components (e.g., protection, regulation).
4) Safety/EMC considerations and test plan.
Keep it concise and actionable for an engineer to implement in KiCad/Altium.
"""

    agent = CircuitAgent(knowledge_path="knowledge_base")
    await agent.initialize()
    resp = await agent.process_request(prompt, image_b64=None, mode="standard")
    print("\n=== DESIGN PROPOSAL ===\n")
    print(resp.get("llm_response", "No response (LLM disabled)."))
    print("\n=== NOTES ===")
    print("LLM_ENABLED:", LLM_ENABLED)


if __name__ == "__main__":
    asyncio.run(run_design_assistant())
