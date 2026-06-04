#!/usr/bin/env python3
"""
CI Smoke Test for v0.1 Functional Planning System.
"""

import json
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.schemas.functional import FunctionalSpec
from services.deterministic_engine import DeterministicEngine
from services.heuristic_planner import HeuristicPlanner
from services.evaluator.master import MasterEvaluator

def test_health_endpoints():
    """Test health endpoints"""
    print("🔍 Testing health endpoints...")
    
    try:
        import requests
        import subprocess
        import time
        
        # Start server in background
        print("Starting server...")
        proc = subprocess.Popen([
            sys.executable, "-m", "uvicorn", 
            "src.api.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for server to start
        time.sleep(5)
        
        # Test health endpoints
        base_url = "http://localhost:8000"
        
        # Test basic health
        response = requests.get(f"{base_url}/health", timeout=10)
        assert response.status_code == 200
        health_data = response.json()
        assert health_data.get("ok") == True
        print("✅ Basic health check passed")
        
        # Test geometry health
        response = requests.get(f"{base_url}/health/geom", timeout=10)
        assert response.status_code == 200
        geom_data = response.json()
        assert geom_data.get("ok") == True
        assert geom_data.get("bytes", 0) > 0
        print("✅ Geometry health check passed")
        
        # Stop server
        proc.terminate()
        proc.wait()
        
        return True
        
    except Exception as e:
        print(f"❌ Health endpoint test failed: {e}")
        if 'proc' in locals():
            proc.terminate()
        return False

def test_functional_planning():
    """Test functional planning with example spec"""
    print("\n🧪 Testing functional planning...")
    
    try:
        # Load example specification
        spec_path = Path("examples/functional_example.json")
        if not spec_path.exists():
            print(f"❌ Example spec not found: {spec_path}")
            return False
        
        with open(spec_path, 'r') as f:
            spec_data = json.load(f)
        
        spec = FunctionalSpec(**spec_data)
        print(f"✅ Loaded spec: {spec.id}")
        
        # Initialize services
        planner = HeuristicPlanner(seed=42)
        evaluator = MasterEvaluator()
        engine = DeterministicEngine(planner, evaluator)
        
        # Limit iterations for CI
        spec.iteration_budget.max_iters = 3
        spec.iteration_budget.max_seconds = 60
        
        print("✅ Initialized services")
        
        # Run optimization
        print("⚙️ Running optimization...")
        start_time = time.time()
        result = engine.optimize(spec, output_dir="ci_test_output")
        elapsed = time.time() - start_time
        
        print(f"✅ Optimization complete in {elapsed:.1f}s")
        
        # Validate results
        assert result.job_id is not None
        assert len(result.iterations) > 0
        assert result.total_time_s > 0
        
        print(f"   Job ID: {result.job_id}")
        print(f"   Iterations: {len(result.iterations)}")
        print(f"   Success: {result.success}")
        print(f"   Final satisfaction: {result.iterations[-1].overall_score:.3f}")
        
        # Check if we have a reasonable result (PASS or ≥80% satisfaction)
        final_score = result.iterations[-1].overall_score
        if result.success or final_score >= 0.8:
            print("✅ Result meets success criteria")
        else:
            print(f"⚠️ Result below 80% satisfaction: {final_score:.3f}")
        
        # Check artifacts
        if result.artifacts:
            print("✅ Artifacts generated:")
            for artifact_type, path in result.artifacts.items():
                print(f"   {artifact_type}: {path}")
        
        # Test idempotency
        print("🔄 Testing idempotency...")
        result2 = engine.optimize(spec, output_dir="ci_test_output")
        
        # Should get same result
        assert result.job_id == result2.job_id
        assert len(result.iterations) == len(result2.iterations)
        
        # Compare final scores (should be identical)
        score1 = result.iterations[-1].overall_score
        score2 = result2.iterations[-1].overall_score
        assert abs(score1 - score2) < 0.001, f"Score mismatch: {score1} vs {score2}"
        
        print("✅ Idempotency test passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Functional planning test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_golden_specs():
    """Test with golden specifications"""
    print("\n🏆 Testing golden specifications...")
    
    # Create test specs
    golden_specs = [
        {
            "id": "tight_fit_test",
            "context": {
                "board_bbox_mm": {"x": 40.0, "y": 25.0, "z": 1.6},
                "mounts": [{"type": "standoff", "pos": [5, 5], "dia": 2.5, "height": 3}],
                "io": [{"type": "usb", "edge": "south", "offset_mm": 20.0, "slot": [12, 5]}]
            },
            "functional_requirements": [
                {"id": "F1", "goal": "drop_protection", "absorb_energy_J": 1.5}
            ],
            "constraints": [
                {"id": "C1", "rule": "overall_envelope_mm", "value": "[50, 35, 12]"}
            ]
        },
        {
            "id": "vented_test", 
            "context": {
                "board_bbox_mm": {"x": 60.0, "y": 40.0, "z": 2.0},
                "mounts": [
                    {"type": "standoff", "pos": [10, 10], "dia": 3.0, "height": 4},
                    {"type": "standoff", "pos": [50, 30], "dia": 3.0, "height": 4}
                ],
                "io": [{"type": "usb", "edge": "south", "offset_mm": 30.0, "slot": [12, 5]}]
            },
            "functional_requirements": [
                {"id": "F1", "goal": "thermal_clearance", "min_air_gap_mm": 2.0}
            ],
            "constraints": [
                {"id": "C1", "rule": "overall_envelope_mm", "value": "[70, 50, 15]"}
            ]
        }
    ]
    
    success_count = 0
    
    for spec_data in golden_specs:
        try:
            print(f"\nTesting spec: {spec_data['id']}")
            
            spec = FunctionalSpec(**spec_data)
            
            # Initialize services
            planner = HeuristicPlanner(seed=42)
            evaluator = MasterEvaluator()
            engine = DeterministicEngine(planner, evaluator)
            
            # Quick test (2 iterations max)
            spec.iteration_budget.max_iters = 2
            spec.iteration_budget.max_seconds = 30
            
            result = engine.optimize(spec, output_dir="ci_test_output")
            
            # Check basic success
            if result.iterations and result.iterations[-1].overall_score > 0.5:
                print(f"✅ {spec_data['id']}: Score {result.iterations[-1].overall_score:.3f}")
                success_count += 1
            else:
                print(f"⚠️ {spec_data['id']}: Low score")
                
        except Exception as e:
            print(f"❌ {spec_data['id']}: Failed - {e}")
    
    print(f"\nGolden specs: {success_count}/{len(golden_specs)} passed")
    return success_count >= len(golden_specs) // 2  # At least half should pass

def main():
    """Run all CI smoke tests"""
    print("🚀 Starting CI Smoke Tests for v0.1 Functional Planning")
    print("=" * 60)
    
    success = True
    
    # Test 1: Health endpoints
    success &= test_health_endpoints()
    
    # Test 2: Functional planning
    success &= test_functional_planning()
    
    # Test 3: Golden specifications
    success &= test_golden_specs()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 All CI smoke tests PASSED!")
        print("✅ v0.1 system is ready for production")
        sys.exit(0)
    else:
        print("❌ Some CI smoke tests FAILED")
        print("⚠️ System needs fixes before production deployment")
        sys.exit(1)

if __name__ == "__main__":
    main()
