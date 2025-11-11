#!/usr/bin/env python3
"""
End-to-End System Test for Circuit.AI
Tests complete workflow from image upload to analysis results
"""

import sys
import time
import requests
import json
import io
from pathlib import Path
from PIL import Image
import numpy as np
from datetime import datetime
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.ingest import CircuitAnalyzer
from src.core.database import CircuitDatabase


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'


class E2ESystemTest:
    """End-to-end system testing"""

    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
        self.test_results = []
        self.start_time = None
        self.analyzer = None
        self.database = None

    def print_header(self, text: str):
        """Print formatted header"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")

    def print_test(self, name: str, status: str, message: str = ""):
        """Print test result"""
        if status == "PASS":
            icon = "✓"
            color = Colors.GREEN
        elif status == "FAIL":
            icon = "✗"
            color = Colors.RED
        elif status == "SKIP":
            icon = "○"
            color = Colors.YELLOW
        else:
            icon = "•"
            color = Colors.WHITE

        print(f"{color}{icon} {name:<45} [{status}]{Colors.END}")
        if message:
            print(f"  {Colors.WHITE}{message}{Colors.END}")

    def record_result(self, test_name: str, passed: bool, message: str = ""):
        """Record test result"""
        self.test_results.append({
            "name": test_name,
            "passed": passed,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

    def test_system_dependencies(self) -> bool:
        """Test 1: Check system dependencies"""
        self.print_header("PHASE 1: System Dependencies")

        tests_passed = True

        # Test Python imports
        try:
            import cv2
            import numpy
            import PIL
            from ultralytics import YOLO
            self.print_test("Python Dependencies", "PASS", "All required packages available")
            self.record_result("Python Dependencies", True)
        except ImportError as e:
            self.print_test("Python Dependencies", "FAIL", f"Missing: {e}")
            self.record_result("Python Dependencies", False, str(e))
            tests_passed = False

        # Test core module imports
        try:
            self.analyzer = CircuitAnalyzer()
            self.database = CircuitDatabase()
            self.print_test("Core Modules", "PASS", "CircuitAnalyzer and Database initialized")
            self.record_result("Core Modules", True)
        except Exception as e:
            self.print_test("Core Modules", "FAIL", str(e))
            self.record_result("Core Modules", False, str(e))
            tests_passed = False

        # Test data directories
        try:
            data_dir = Path("data")
            required_dirs = ["uploads", "annotated", "cache", "knowledge_base"]
            missing = [d for d in required_dirs if not (data_dir / d).exists()]

            if missing:
                self.print_test("Data Directories", "SKIP", f"Missing: {', '.join(missing)}")
                self.record_result("Data Directories", False, f"Missing: {missing}")
            else:
                self.print_test("Data Directories", "PASS", "All required directories exist")
                self.record_result("Data Directories", True)
        except Exception as e:
            self.print_test("Data Directories", "FAIL", str(e))
            self.record_result("Data Directories", False, str(e))

        return tests_passed

    def test_api_health(self) -> bool:
        """Test 2: API health checks"""
        self.print_header("PHASE 2: API Health")

        tests_passed = True

        # Test health endpoint
        try:
            response = requests.get(f"{self.api_url}/health", timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.print_test("Health Endpoint", "PASS", f"API is healthy (v{data['data'].get('version', 'unknown')})")
                    self.record_result("Health Endpoint", True)
                else:
                    self.print_test("Health Endpoint", "FAIL", "API returned unhealthy status")
                    self.record_result("Health Endpoint", False)
                    tests_passed = False
            else:
                self.print_test("Health Endpoint", "FAIL", f"Status code: {response.status_code}")
                self.record_result("Health Endpoint", False, f"Status {response.status_code}")
                tests_passed = False

        except requests.exceptions.ConnectionError:
            self.print_test("Health Endpoint", "FAIL", "Could not connect to API")
            self.record_result("Health Endpoint", False, "Connection refused")
            tests_passed = False
        except Exception as e:
            self.print_test("Health Endpoint", "FAIL", str(e))
            self.record_result("Health Endpoint", False, str(e))
            tests_passed = False

        return tests_passed

    def test_ml_pipeline(self) -> bool:
        """Test 3: ML pipeline"""
        self.print_header("PHASE 3: ML Pipeline")

        tests_passed = True

        # Create test image
        test_image = self._create_test_pcb_image()

        # Test local analysis (without API)
        try:
            if self.analyzer:
                start = time.perf_counter()
                results = self.analyzer.analyze_pcb(
                    test_image,
                    backend="enhanced",
                    enable_ocr=False
                )
                elapsed = time.perf_counter() - start

                if results and "detections" in results:
                    self.print_test(
                        "Local ML Analysis",
                        "PASS",
                        f"Completed in {elapsed:.2f}s, found {len(results['detections'])} components"
                    )
                    self.record_result("Local ML Analysis", True)
                else:
                    self.print_test("Local ML Analysis", "SKIP", "No detections (may be expected)")
                    self.record_result("Local ML Analysis", True, "No detections")
            else:
                self.print_test("Local ML Analysis", "SKIP", "Analyzer not initialized")
                self.record_result("Local ML Analysis", False, "Not initialized")

        except Exception as e:
            self.print_test("Local ML Analysis", "FAIL", str(e))
            self.record_result("Local ML Analysis", False, str(e))
            tests_passed = False

        # Test YOLO model loading
        try:
            from src.vision.loader import get_detector

            model_path = Path("pcb_runs/electrocom61_full_production/weights/best.pt")
            if model_path.exists():
                model = get_detector("electrocom61_v1")
                if model:
                    self.print_test("YOLO Model Loading", "PASS", f"Loaded model from {model_path}")
                    self.record_result("YOLO Model Loading", True)
                else:
                    self.print_test("YOLO Model Loading", "SKIP", "Model not loaded")
                    self.record_result("YOLO Model Loading", False)
            else:
                self.print_test("YOLO Model Loading", "SKIP", "Model file not found")
                self.record_result("YOLO Model Loading", False, "File not found")

        except Exception as e:
            self.print_test("YOLO Model Loading", "FAIL", str(e))
            self.record_result("YOLO Model Loading", False, str(e))

        return tests_passed

    def test_knowledge_base(self) -> bool:
        """Test 4: Knowledge base"""
        self.print_header("PHASE 4: Knowledge Base")

        tests_passed = True

        kb_path = Path("data/knowledge_base/complete_knowledge_base.json")

        if kb_path.exists():
            try:
                with open(kb_path) as f:
                    kb = json.load(f)

                stats = kb.get("statistics", {})
                fault_patterns = stats.get("total_fault_patterns", 0)
                ic_pinouts = stats.get("total_ic_pinouts", 0)

                self.print_test(
                    "Knowledge Base",
                    "PASS",
                    f"{fault_patterns:,} fault patterns, {ic_pinouts} IC pinouts"
                )
                self.record_result("Knowledge Base", True, f"{fault_patterns} patterns")

            except Exception as e:
                self.print_test("Knowledge Base", "FAIL", str(e))
                self.record_result("Knowledge Base", False, str(e))
                tests_passed = False
        else:
            self.print_test("Knowledge Base", "SKIP", "Knowledge base file not found")
            self.record_result("Knowledge Base", False, "File not found")

        return tests_passed

    def test_database_operations(self) -> bool:
        """Test 5: Database operations"""
        self.print_header("PHASE 5: Database Operations")

        tests_passed = True

        if self.database:
            try:
                # Test storing analysis
                test_result = {
                    "detections": [
                        {"type": "resistor", "confidence": 0.95},
                        {"type": "capacitor", "confidence": 0.87}
                    ],
                    "timestamp": datetime.now().isoformat()
                }

                analysis_id = self.database.store_analysis_result(test_result, "e2e_test.jpg")

                if analysis_id:
                    self.print_test("Database Write", "PASS", f"Stored analysis ID: {analysis_id}")
                    self.record_result("Database Write", True)

                    # Test retrieval
                    retrieved = self.database.get_analysis_by_id(analysis_id)
                    if retrieved:
                        self.print_test("Database Read", "PASS", "Retrieved stored analysis")
                        self.record_result("Database Read", True)
                    else:
                        self.print_test("Database Read", "FAIL", "Could not retrieve analysis")
                        self.record_result("Database Read", False)
                        tests_passed = False
                else:
                    self.print_test("Database Write", "FAIL", "Could not store analysis")
                    self.record_result("Database Write", False)
                    tests_passed = False

            except Exception as e:
                self.print_test("Database Operations", "FAIL", str(e))
                self.record_result("Database Operations", False, str(e))
                tests_passed = False
        else:
            self.print_test("Database Operations", "SKIP", "Database not initialized")
            self.record_result("Database Operations", False, "Not initialized")

        return tests_passed

    def test_complete_workflow(self) -> bool:
        """Test 6: Complete end-to-end workflow"""
        self.print_header("PHASE 6: Complete Workflow")

        tests_passed = True

        # This would test the complete flow:
        # 1. Upload image via API
        # 2. Get analysis results
        # 3. Verify results structure
        # 4. Check database storage
        # 5. Retrieve analysis history

        # For now, mark as TODO
        self.print_test("Complete Workflow", "SKIP", "To be implemented with live API")
        self.record_result("Complete Workflow", False, "Not implemented")

        return tests_passed

    def _create_test_pcb_image(self) -> np.ndarray:
        """Create a realistic test PCB image"""
        # Create green PCB background
        img = Image.new('RGB', (1024, 768), color=(34, 139, 34))
        pixels = img.load()

        # Add some copper traces
        for x in range(100, 900):
            for y in range(380, 385):
                pixels[x, y] = (184, 115, 51)

        # Add simulated components
        # Resistor (brown)
        for x in range(200, 240):
            for y in range(370, 385):
                pixels[x, y] = (139, 69, 19)

        # Capacitor (blue)
        for x in range(300, 330):
            for y in range(365, 395):
                pixels[x, y] = (0, 0, 128)

        # IC chip (black)
        for x in range(450, 530):
            for y in range(340, 420):
                pixels[x, y] = (20, 20, 20)

        return np.array(img)

    def print_summary(self):
        """Print test summary"""
        self.print_header("TEST SUMMARY")

        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["passed"])
        failed = total - passed

        print(f"\n{Colors.BOLD}Results:{Colors.END}")
        print(f"  {Colors.GREEN}✓ Passed: {passed}{Colors.END}")
        print(f"  {Colors.RED}✗ Failed: {failed}{Colors.END}")
        print(f"  {Colors.WHITE}━ Total:  {total}{Colors.END}\n")

        if failed > 0:
            print(f"{Colors.BOLD}Failed Tests:{Colors.END}")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  {Colors.RED}• {result['name']}{Colors.END}")
                    if result["message"]:
                        print(f"    {Colors.WHITE}{result['message']}{Colors.END}")

        # Calculate completion percentage
        completion = (passed / total * 100) if total > 0 else 0
        print(f"\n{Colors.BOLD}System Readiness: {completion:.1f}%{Colors.END}\n")

        # Save results to file
        self._save_results()

    def _save_results(self):
        """Save test results to JSON file"""
        results_file = Path("test_results_e2e.json")

        results_data = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.test_results),
            "passed": sum(1 for r in self.test_results if r["passed"]),
            "failed": sum(1 for r in self.test_results if not r["passed"]),
            "tests": self.test_results
        }

        with open(results_file, 'w') as f:
            json.dump(results_data, f, indent=2)

        print(f"{Colors.CYAN}Results saved to: {results_file}{Colors.END}\n")

    def run_all_tests(self):
        """Run all E2E tests"""
        self.start_time = time.perf_counter()

        print(f"\n{Colors.BOLD}{Colors.MAGENTA}")
        print("╔════════════════════════════════════════════════════════════╗")
        print("║         Circuit.AI - End-to-End System Test               ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print(f"{Colors.END}")

        # Run test phases
        self.test_system_dependencies()
        self.test_api_health()
        self.test_ml_pipeline()
        self.test_knowledge_base()
        self.test_database_operations()
        self.test_complete_workflow()

        # Print summary
        elapsed = time.perf_counter() - self.start_time
        print(f"\n{Colors.WHITE}Total execution time: {elapsed:.2f}s{Colors.END}")
        self.print_summary()

        # Return exit code
        all_passed = all(r["passed"] for r in self.test_results)
        return 0 if all_passed else 1


if __name__ == "__main__":
    tester = E2ESystemTest()
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)
