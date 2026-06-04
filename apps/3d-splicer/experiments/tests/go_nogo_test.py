#!/usr/bin/env python3
"""
Go/No-Go test for v0.1 production readiness.
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd: str, description: str) -> bool:
    """Run a command and return success status"""
    print(f"🔍 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print(f"✅ {description}: SUCCESS")
            return True
        else:
            print(f"❌ {description}: FAILED")
            print(f"   Error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏰ {description}: TIMEOUT")
        return False
    except Exception as e:
        print(f"❌ {description}: ERROR - {e}")
        return False

def main():
    """Run go/no-go test suite"""
    print("🚀 v0.1 Go/No-Go Test Suite")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Health endpoints
    total_tests += 1
    if run_command(
        "curl -s http://localhost:8000/health | grep -q '\"ok\":true'",
        "Basic health endpoint"
    ):
        tests_passed += 1
    
    # Test 2: Geometry health
    total_tests += 1
    if run_command(
        "curl -s http://localhost:8000/health/geom | grep -q '\"ok\":true'",
        "Geometry health endpoint"
    ):
        tests_passed += 1
    
    # Test 3: Golden specs determinism
    total_tests += 1
    if run_command(
        "python test_golden_specs.py",
        "Golden specs test (determinism + pass rate)"
    ):
        tests_passed += 1
    
    # Test 4: API functional planning
    total_tests += 1
    if run_command(
        "curl -s -X POST http://localhost:8000/v1/plan -H 'Content-Type: application/json' --data @examples/golden_shock.json | grep -q 'job_id'",
        "API functional planning endpoint"
    ):
        tests_passed += 1
    
    # Test 5: Preview endpoint
    total_tests += 1
    if run_command(
        "curl -s -X POST http://localhost:8000/v1/splice/preview -H 'Content-Type: application/json' --data @examples/golden_io.json | grep -q 'overall_score'",
        "Preview endpoint"
    ):
        tests_passed += 1
    
    # Results
    print("\n" + "=" * 50)
    print(f"📊 Go/No-Go Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 GO FOR PRODUCTION!")
        print("✅ All tests passed - v0.1 is ready for deployment")
        sys.exit(0)
    else:
        print("⚠️ NO-GO - NEEDS FIXES")
        print("❌ Some tests failed - fix issues before production")
        sys.exit(1)

if __name__ == "__main__":
    main()
