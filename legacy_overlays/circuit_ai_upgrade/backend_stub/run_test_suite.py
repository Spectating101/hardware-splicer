
import sys
import os

# Fix path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from repair_orchestrator import RepairOrchestrator

if __name__ == "__main__":
    print("==============================================")
    print("   CIRCUIT-AI: AUTONOMOUS REPAIR STRESS TEST  ")
    print("==============================================")
    
    # 1. Initialize
    orchestrator = RepairOrchestrator()
    
    # 2. Run the Loop
    print("\n[TEST] Triggering autonomous repair loop...")
    result = orchestrator.generate_repair_plan()
    
    # 3. Validation
    print("\n[TEST] Validating G-Code Output...")
    for job in result['repair_jobs']:
        gcode = job['gcode']
        print(f"--- G-Code for {job['component']} ---")
        print(gcode[:300] + "...") # Print first 300 chars
        
        # Check for Safety Logic
        if "T1" in gcode:
            print("✅ Feeder Selected")
        else:
            print("❌ Feeder Selection Missing")
            
        if "M800" in gcode:
            print("✅ Vacuum Pick-Up Active")
        else:
            print("❌ Vacuum Missing")
            
        # Check if the AI correctly identified the part
        spec = job['spec']
        print(f"\n[TEST] AI Identification Verification:")
        print(f"   > Ref: {spec['ref']}")
        print(f"   > Value: {spec['value']}")
        print(f"   > Package: {spec['package']}")
        
        if spec['value'] != "Unknown":
            print("✅ AI successfully identified component spec.")
        else:
            print("❌ AI failed identification.")

    print("\n==============================================")
    print("             TEST COMPLETE                    ")
    print("==============================================")
