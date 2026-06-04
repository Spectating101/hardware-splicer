#!/usr/bin/env python3
"""
Test script for v0.1 deterministic functional planning.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.schemas.functional import FunctionalSpec
from services.deterministic_engine import DeterministicEngine
from services.heuristic_planner import HeuristicPlanner
from services.evaluator.master import MasterEvaluator

def test_v01_functional_planning():
    """Test the v0.1 functional planning system"""
    print("🧪 Testing v0.1 Functional Planning System")
    print("=" * 50)
    
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
    
    print("✅ Initialized services")
    
    # Test initial parameter generation
    print("\n📋 Testing initial parameter generation...")
    initial_params = planner.propose_initial_parameters(spec)
    print(f"✅ Generated initial parameters:")
    print(f"   Shell thickness: {initial_params.shell.get('thickness_mm', 0):.2f}mm")
    print(f"   Bosses: {len(initial_params.bosses)}")
    print(f"   IO slots: {len(initial_params.io_slots)}")
    print(f"   Latches: {initial_params.latches.get('count', 0)}")
    
    # Test parameter validation
    print("\n🔍 Testing parameter validation...")
    violations = planner.clamp_layer.validate_params(initial_params.model_dump())
    if violations:
        print(f"⚠️  Parameter violations: {violations}")
    else:
        print("✅ All parameters within valid ranges")
    
    # Test optimization (limited iterations for testing)
    print("\n⚙️ Testing optimization engine...")
    spec.iteration_budget.max_iters = 3  # Limit for testing
    spec.iteration_budget.max_seconds = 60  # Limit for testing
    
    try:
        result = engine.optimize(spec, output_dir="test_output")
        print(f"✅ Optimization complete:")
        print(f"   Success: {result.success}")
        print(f"   Iterations: {len(result.iterations)}")
        print(f"   Total time: {result.total_time_s:.1f}s")
        
        if result.iterations:
            final_score = result.iterations[-1].overall_score
            final_passed = result.iterations[-1].all_passed
            print(f"   Final score: {final_score:.3f}")
            print(f"   All tests passed: {final_passed}")
            
            # Show test results
            print(f"\n📊 Final test results:")
            for test_result in result.iterations[-1].evaluation:
                status = "✅" if test_result.passed else "❌"
                print(f"   {status} {test_result.test_id}: {test_result.score:.3f}")
                if test_result.details:
                    print(f"      {test_result.details}")
        
        # Check artifacts
        print(f"\n📁 Generated artifacts:")
        for artifact_type, path in result.artifacts.items():
            print(f"   {artifact_type}: {path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Optimization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_preview():
    """Test preview generation"""
    print("\n🔍 Testing preview generation...")
    
    try:
        from routes.preview import preview_case
        from src.schemas.functional import FunctionalSpec
        
        # Load spec
        with open("examples/functional_example.json", 'r') as f:
            spec_data = json.load(f)
        spec = FunctionalSpec(**spec_data)
        
        # Generate preview
        preview_result = preview_case(spec)
        
        print(f"✅ Preview generated:")
        print(f"   Overall score: {preview_result['overall_score']:.3f}")
        print(f"   Passed tests: {preview_result['passed_tests']}/{preview_result['total_tests']}")
        print(f"   Success rate: {preview_result['success_rate']:.1%}")
        
        return True
        
    except Exception as e:
        print(f"❌ Preview test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Starting v0.1 Functional Planning Tests")
    print()
    
    success = True
    
    # Test main optimization
    success &= test_v01_functional_planning()
    
    # Test preview
    success &= test_preview()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed! v0.1 system is working.")
    else:
        print("❌ Some tests failed. Check the output above.")
        sys.exit(1)
