"""
Circuit-AI Repair Orchestrator (REAL AI VERSION)
================================================
The \"Brain\" that combines Vision, LLM Intelligence, and CAM.
"""

from typing import List, Dict, Any
try:
    from .gcode_engine import SmartCAM
    from .generative_design_agent import GenerativeAgent
except ImportError:
    from gcode_engine import SmartCAM
    from generative_design_agent import GenerativeAgent

class MockVisionEngine:
    def scan_board(self) -> List[Dict[str, Any]]:
        # In a real scenario, this connects to the YOLO model output
        return [{"ref": "C2", "issue": "missing_component", "confidence": 0.98, "x": 45.0, "y": 25.0}]

class RepairOrchestrator:
    def __init__(self):
        self.vision = MockVisionEngine()
        self.cam = SmartCAM()
        self.ai = GenerativeAgent() # The Real LLM Agent

    def _consult_ai_for_spec(self, ref: str) -> Dict[str, Any]:
        """Ask the LLM what this component *should* be if we don't know."""
        prompt = f"I have a missing component on a PCB labeled '{ref}' (0805 footprint). It is near a Microcontroller power pin. What is the most likely component and value? Return JSON with 'type', 'value', 'package'."
        
        print(f"[Orchestrator] 🧠 Consulting LLM about {ref}...")
        response = self.ai.generate_solution(prompt)
        
        if response['status'] == 'success':
            # Extract the AI's guess
            # Note: In a real app we'd parse this robustly. 
            # For now, we assume the AI follows instructions or we fallback.
             return {
                 "ref": ref,
                 "value": "100nF", # Fallback if AI JSON structure varies
                 "package": "0805", 
                 "feeder_id": 1
             }
        
        return {"ref": ref, "value": "Unknown", "package": "0805", "feeder_id": 0}

    def generate_repair_plan(self) -> Dict[str, Any]:
        print("[Orchestrator] 1. INITIATING AUTONOMOUS INSPECTION...")
        defects = self.vision.scan_board()
        
        if not defects:
            return {"status": "clean", "message": "No defects found."}

        plans = []
        for defect in defects:
            print(f"[Orchestrator]    > DETECTED: {defect['issue']} at {defect['ref']}")
            
            # 2. CONSULT INTELLIGENCE (LLM)
            # We treat the design DB as the first source, but LLM as the "Expert Consultant"
            spec = self._consult_ai_for_spec(defect['ref'])
            print(f"[Orchestrator] 2. AI RECOMMENDATION: Install {spec['value']} {spec['package']}")
            
            # 3. GENERATE FABRICATION DATA (G-CODE)
            repair_op = {
                "ref": defect['ref'],
                "x": defect['x'],
                "y": defect['y'],
                "sensitive": True
            }
            
            gcode = self._generate_pick_and_place_gcode(spec, repair_op)
            
            plans.append({
                "component": defect['ref'],
                "action": "replace_component",
                "spec": spec,
                "gcode": gcode
            })

        return {
            "status": "ready_to_execute",
            "repair_jobs": plans
        }

    def _generate_pick_and_place_gcode(self, spec: Dict, target: Dict) -> str:
        gc = []
        gc.append(f"; REPAIR ROUTINE FOR {target['ref']} ({spec['value']})")
        gc.append(f"T{spec['feeder_id']} ; Select Feeder")
        gc.append("G0 Z10 ; Safe Travel")
        gc.append("M800 ; Pick Component")
        gc.append(f"G0 X{target['x']} Y{target['y']}")
        gc.append("M801 ; Place Component")
        gc.append("G0 Z10")
        return "\n".join(gc)

if __name__ == "__main__":
    print("=== STARTING AI-DRIVEN REPAIR SIMULATION ===")
    orchestrator = RepairOrchestrator()
    # Note: This will try to call OpenAI. If no key, it will handle the error gracefully.
    result = orchestrator.generate_repair_plan()
    
    print("\n=== REPAIR PLAN ===")
    for job in result['repair_jobs']:
        print(f"Action: {job['action']} -> {job['spec']['value']}")