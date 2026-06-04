#!/usr/bin/env python3
"""
Golden specs test - validates determinism and pass rates for v0.1 go/no-go.
"""

import json
import sys
import hashlib
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.schemas.functional import FunctionalSpec
from services.deterministic_engine import DeterministicEngine
from services.heuristic_planner import HeuristicPlanner
from services.evaluator.master import MasterEvaluator

def test_golden_spec(spec_path: Path, max_iterations: int = 5) -> dict:
    """Test a single golden specification"""
    print(f"\n🧪 Testing: {spec_path.name}")
    
    # Load specification
    with open(spec_path, 'r') as f:
        spec_data = json.load(f)
    
    spec = FunctionalSpec(**spec_data)
    print(f"   Spec ID: {spec.id}")
    
    # Initialize services
    planner = HeuristicPlanner(seed=42)
    evaluator = MasterEvaluator()
    engine = DeterministicEngine(planner, evaluator)
    
    # Set iteration budget
    spec.iteration_budget.max_iters = max_iterations
    spec.iteration_budget.max_seconds = 120
    
    results = []
    
    # Run twice for determinism check
    for run in [1, 2]:
        print(f"   Run {run}: ", end="", flush=True)
        
        try:
            start_time = time.time()
            result = engine.optimize(spec, output_dir="golden_test_output")
            elapsed = time.time() - start_time
            
            # Extract key metrics
            final_score = result.iterations[-1].overall_score if result.iterations else 0.0
            all_passed = result.iterations[-1].all_passed if result.iterations else False
            iterations = len(result.iterations)
            
            # Calculate artifact hash for determinism
            artifact_hash = None
            if result.artifacts and "stl" in result.artifacts:
                stl_path = Path(result.artifacts["stl"])
                if stl_path.exists():
                    with open(stl_path, 'rb') as f:
                        artifact_hash = hashlib.sha256(f.read()).hexdigest()[:16]
            
            run_result = {
                "run": run,
                "success": result.success,
                "final_score": final_score,
                "all_passed": all_passed,
                "iterations": iterations,
                "elapsed_s": elapsed,
                "artifact_hash": artifact_hash,
                "job_id": result.job_id
            }
            
            results.append(run_result)
            
            status = "✅ PASS" if (all_passed or final_score >= 0.8) else "⚠️ PARTIAL"
            print(f"{status} (score: {final_score:.2f}, {iterations} iters, {elapsed:.1f}s)")
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            results.append({
                "run": run,
                "success": False,
                "error": str(e),
                "final_score": 0.0,
                "all_passed": False,
                "iterations": 0,
                "elapsed_s": 0.0,
                "artifact_hash": None
            })
    
    # Check determinism
    deterministic = False
    if len(results) == 2:
        hash1 = results[0].get("artifact_hash")
        hash2 = results[1].get("artifact_hash")
        if hash1 and hash2 and hash1 == hash2:
            deterministic = True
            print(f"   Determinism: ✅ MATCH (hash: {hash1})")
        else:
            print(f"   Determinism: ❌ MISMATCH ({hash1} vs {hash2})")
    
    # Calculate pass rate
    pass_count = sum(1 for r in results if r.get("final_score", 0) >= 0.8)
    pass_rate = pass_count / len(results) if results else 0.0
    
    return {
        "spec_id": spec.id,
        "spec_path": str(spec_path),
        "results": results,
        "deterministic": deterministic,
        "pass_rate": pass_rate,
        "avg_score": sum(r.get("final_score", 0) for r in results) / len(results) if results else 0.0,
        "avg_iterations": sum(r.get("iterations", 0) for r in results) / len(results) if results else 0.0,
        "avg_elapsed": sum(r.get("elapsed_s", 0) for r in results) / len(results) if results else 0.0
    }

def main():
    """Run golden specs test suite"""
    print("🏆 Golden Specs Test Suite - v0.1 Go/No-Go Validation")
    print("=" * 60)
    
    # Find golden spec files
    examples_dir = Path("examples")
    golden_specs = [
        "golden_shock.json",
        "golden_vented.json", 
        "golden_io.json"
    ]
    
    test_results = []
    
    for spec_name in golden_specs:
        spec_path = examples_dir / spec_name
        if not spec_path.exists():
            print(f"❌ Golden spec not found: {spec_path}")
            continue
        
        result = test_golden_spec(spec_path)
        test_results.append(result)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 GOLDEN SPECS SUMMARY")
    print("=" * 60)
    
    all_deterministic = True
    all_pass_rate_good = True
    total_tests = 0
    total_passed = 0
    
    for result in test_results:
        print(f"\n{result['spec_id']}:")
        print(f"   Pass Rate: {result['pass_rate']:.1%}")
        print(f"   Avg Score: {result['avg_score']:.2f}")
        print(f"   Avg Iterations: {result['avg_iterations']:.1f}")
        print(f"   Deterministic: {'✅' if result['deterministic'] else '❌'}")
        
        if not result['deterministic']:
            all_deterministic = False
        
        if result['pass_rate'] < 1.0:
            all_pass_rate_good = False
        
        total_tests += len(result['results'])
        total_passed += sum(1 for r in result['results'] if r.get('final_score', 0) >= 0.8)
    
    overall_pass_rate = total_passed / total_tests if total_tests > 0 else 0.0
    
    print(f"\n🎯 OVERALL RESULTS:")
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {total_passed}")
    print(f"   Overall Pass Rate: {overall_pass_rate:.1%}")
    print(f"   All Deterministic: {'✅' if all_deterministic else '❌'}")
    
    # Go/No-Go Decision
    print(f"\n🚀 GO/NO-GO DECISION:")
    
    go_criteria = [
        ("Pass Rate ≥ 80%", overall_pass_rate >= 0.8),
        ("All Specs Deterministic", all_deterministic),
        ("At Least 2/3 Specs Pass", len([r for r in test_results if r['pass_rate'] >= 1.0]) >= 2)
    ]
    
    for criterion, passed in go_criteria:
        status = "✅" if passed else "❌"
        print(f"   {status} {criterion}")
    
    all_criteria_met = all(passed for _, passed in go_criteria)
    
    if all_criteria_met:
        print(f"\n🎉 GO FOR PRODUCTION!")
        print(f"   ✅ v0.1 system meets all go/no-go criteria")
        print(f"   ✅ Ready for internal deployment and Circuit.AI integration")
        sys.exit(0)
    else:
        print(f"\n⚠️ NO-GO - NEEDS IMPROVEMENT")
        print(f"   ❌ v0.1 system does not meet go/no-go criteria")
        print(f"   🔧 Fix issues before production deployment")
        sys.exit(1)

if __name__ == "__main__":
    main()
