"""
Text-to-KiCad Generator
=======================
Asks the LLM to write a Python script that generates a .kicad_pcb file.
This bridges the gap between "Idea" and "Manufacturable File".
"""

import sys
import os
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from generative_design_agent import GenerativeAgent

def generate_kicad_code():
    print(">>> GENERATING KICAD PYTHON SCRIPT <<<")
    agent = GenerativeAgent()
    
    prompt = """
    Write a complete, executable Python script using the 'pcbnew' library (KiCad Python API).
    
    The script must:
    1. Create a new BOARD.
    2. Add an ATTiny85 footprint ('Package_DIP:DIP-8_W7.62mm').
    3. Add a LED footprint ('LED_THT:LED_D5.0mm').
    4. Place them on the board at (100, 100) and (110, 100).
    5. Create a net connecting ATTiny Pin 5 to LED Anode.
    6. Save the file to 'soul_core.kicad_pcb'.
    
    RETURN ONLY THE RAW PYTHON CODE. NO MARKDOWN. NO COMMENTS.
    """
    
    # We cheat the 'json mode' here by asking for text in the narrative/plan for this specific test
    # In production, we'd have a separate 'code_generation' mode
    
    # HACK: Using the 'modification' schema but asking for code in narrative to bypass JSON constraint
    # Actually, let's just make a raw call if possible, or parse the JSON 'narrative' field as code.
    
    res = agent._call_llm(prompt) # Raw call to bypass JSON enforcement if possible
    
    # Check if we got JSON back (since agent enforces it). 
    # If the Agent enforces JSON, we need to ask it to put the code inside a JSON field.
    
    code_prompt = """
    Generate a JSON object where the key 'code' contains a Python script using 'pcbnew' to generate a KiCad board with an ATTiny85 and an LED.
    The script should save to 'output.kicad_pcb'.
    """
    
    res = agent.generate_solution(code_prompt)
    code = res.get('plan', {}).get('code', '# No code generated')
    
    if not code or code == "# No code generated":
        # Fallback: Try to extract from narrative or custom field
        code = res.get('plan', {}).get('narrative', '')

    print("-" * 40)
    print(code)
    print("-" * 40)
    
    # Save the generated script
    with open("generated_kicad_script.py", "w") as f:
        f.write(code)
        
    print("✅ Saved to generated_kicad_script.py")

if __name__ == "__main__":
    generate_kicad_code()
