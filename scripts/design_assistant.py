#!/usr/bin/env python3
"""
Design Assistant: prompts the LLM for a block diagram/BOM/topology sketch from a use case,
and tries to extract machine-readable artifacts (netlist JSON + NGSpice stub).
Requires LLM access (CEREBRAS_API_KEY) or runs stubbed if LLM is disabled.
"""
import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in [ROOT, os.path.join(ROOT, "src")]:
    if path not in sys.path:
        sys.path.insert(0, path)

from circuit_agent import CircuitAgent, LLM_ENABLED


def extract_code_block(text: str, lang: str) -> str | None:
    """Grab the first fenced code block of the requested language."""
    pattern = rf"```{lang}\s*(.*?)```"
    m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


async def run_design_assistant():
    ap = argparse.ArgumentParser(description="LLM-powered hardware design assistant")
    ap.add_argument("--use-case", help="Describe the desired tool/circuit")
    ap.add_argument("--constraints", help="Voltage/current/size/cost/safety, etc.")
    ap.add_argument("--out-prefix", default="design_output", help="Prefix for saved artifacts")
    args = ap.parse_args()

    use_case = args.use_case or input("Describe your desired tool/circuit (e.g., 'USB-C PD trigger for 12V out'): ").strip()
    constraints = args.constraints or input("Constraints (voltage/current/size/cost/safety), or leave blank: ").strip()

    prompt = f"""
You are a hardware design assistant. Propose a circuit architecture for the following use case:

Use case: {use_case}
Constraints: {constraints or "None specified"}

Outputs:
1) Block diagram in text (major blocks and signal/power flow).
2) BOM (major parts with rough specs).
3) Topology sketch: describe how blocks connect (nets) and critical components (protection/regulation).
4) Safety/EMC considerations and test plan.
5) Emit a machine-readable netlist as JSON in a ```json``` block with fields: components:[{{ref,type,value,notes}}], nets:[{{name,nodes}}].
6) Emit a minimal NGSpice-compatible stub in a ```spice``` block (include V1 source and element lines) suitable for quick hand-editing.
Keep it concise and actionable for an engineer to implement in KiCad/Altium.
"""

    agent = CircuitAgent(knowledge_path="knowledge_base")
    await agent.initialize()
    resp = await agent.process_request(prompt, image_b64=None, mode="standard")
    llm_text = resp.get("llm_response", "No response (LLM disabled).")

    print("\n=== DESIGN PROPOSAL ===\n")
    print(llm_text)

    # Try to extract artifacts
    out_prefix = Path(args.out_prefix)
    json_block = extract_code_block(llm_text, "json")
    spice_block = extract_code_block(llm_text, "spice") or extract_code_block(llm_text, "cir")

    if json_block:
        json_path = out_prefix.with_suffix(".netlist.json")
        try:
            # Validate JSON before writing prettified
            parsed = json.loads(json_block)
            json_path.write_text(json.dumps(parsed, indent=2))
        except Exception:
            # Write raw if parsing fails
            json_path.write_text(json_block)
        print(f"\n📄 Saved netlist JSON -> {json_path}")

    if spice_block:
        spice_path = out_prefix.with_suffix(".spice.cir")
        spice_path.write_text(spice_block)
        print(f"📄 Saved NGSpice stub -> {spice_path}")

    txt_path = out_prefix.with_suffix(".txt")
    txt_path.write_text(llm_text)
    print(f"📄 Saved full response -> {txt_path}")

    print("\n=== NOTES ===")
    print("LLM_ENABLED:", LLM_ENABLED)


if __name__ == "__main__":
    asyncio.run(run_design_assistant())
