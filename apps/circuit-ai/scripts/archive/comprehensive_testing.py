#!/usr/bin/env python3
"""
Comprehensive Testing Suite for Circuit.AI
==========================================

This script performs thorough testing of all system components:
- Component detection with various images
- API endpoints functionality
- Web interface integration
- Database operations
- Error handling and edge cases
- Performance metrics
- User experience validation
"""

import sys
import os
import time
import requests
import json
from pathlib import Path
from typing import Dict, Any, List
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.ingest import CircuitAnalyzer
from src.core.database import CircuitDatabase
from src.config import settings


class ComprehensiveTester:
    """Comprehensive testing suite for Circuit.AI."""
    
    def __init__(self):
        """Initialize the tester."""
        self.analyzer = CircuitAnalyzer()
        self.database = CircuitDatabase()
        self.api_base_url = "http://localhost:8000"
        self.test_results = []
        self.start_time = time.time()
        
    def log_test(self, test_name: str, status: str, details: str = "", duration: float = 0):
        """Log test results."""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "duration": duration,
            "timestamp": time.time()
        }
        self.test_results.append(result)
        print(f"[{status.upper()}] {test_name}: {details}")
        
    def test_component_detection(self):
        """Test component detection with various images."""
        print("\n🔍 Testing Component Detection...")
        
        test_images = [
            "data/test_images/demo_pcb.png",
            "data/test_images/test_pcb.png",
            "data/test_images/raspberry_pi.jpg"
        ]
        
        for image_path in test_images:
            if not os.path.exists(image_path):
                self.log_test(f"Detection {image_path}", "SKIP", "Image not found")
                continue
                
            try:
                start_time = time.time()
                results = self.analyzer.analyze_from_file(image_path)
                duration = time.time() - start_time
                
                if "error" in results:
                    self.log_test(f"Detection {image_path}", "FAIL", f"Error: {results['error']}", duration)
                else:
                    components = results.get("detection_summary", {}).get("total_components", 0)
                    confidence = results.get("detection_summary", {}).get("average_confidence", 0)
                    self.log_test(f"Detection {image_path}", "PASS", 
                                f"Detected {components} components, {confidence:.2f} confidence", duration)
                    
            except Exception as e:
                self.log_test(f"Detection {image_path}", "ERROR", str(e))
    
    def test_api_endpoints(self):
        """Test all API endpoints."""
        print("\n🌐 Testing API Endpoints...")
        
        endpoints = [
            ("/", "Root endpoint"),
            ("/health", "Health check"),
            ("/demo", "Demo data"),
            ("/analyses", "Analysis history"),
            ("/statistics", "Statistics"),
            ("/components", "Component database"),
            ("/projects", "Project templates")
        ]
        
        for endpoint, description in endpoints:
            try:
                start_time = time.time()
                response = requests.get(f"{self.api_base_url}{endpoint}", timeout=10)
                duration = time.time() - start_time
                
                if response.status_code == 200:
                    self.log_test(f"API {endpoint}", "PASS", f"{description} - {response.status_code}", duration)
                else:
                    self.log_test(f"API {endpoint}", "FAIL", f"{description} - {response.status_code}", duration)
                    
            except Exception as e:
                self.log_test(f"API {endpoint}", "ERROR", f"{description} - {str(e)}")
    
    def test_image_upload_api(self):
        """Test image upload via API."""
        print("\n📤 Testing Image Upload API...")
        
        test_image = "data/test_images/demo_pcb.png"
        if not os.path.exists(test_image):
            self.log_test("Image Upload API", "SKIP", "Test image not found")
            return
            
        try:
            start_time = time.time()
            with open(test_image, 'rb') as f:
                files = {'file': ('demo_pcb.png', f, 'image/png')}
                response = requests.post(f"{self.api_base_url}/analyze", files=files, timeout=30)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                components = data.get("detection_summary", {}).get("total_components", 0)
                self.log_test("Image Upload API", "PASS", f"Uploaded and analyzed - {components} components", duration)
            else:
                self.log_test("Image Upload API", "FAIL", f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_test("Image Upload API", "ERROR", str(e))
    
    def test_database_operations(self):
        """Test database operations."""
        print("\n🗄️ Testing Database Operations...")
        
        try:
            # Test getting analyses
            start_time = time.time()
            analyses = self.database.get_recent_analyses(limit=5)
            duration = time.time() - start_time
            
            if analyses is not None:
                self.log_test("Database Get Analyses", "PASS", f"Retrieved {len(analyses)} analyses", duration)
            else:
                self.log_test("Database Get Analyses", "FAIL", "Failed to retrieve analyses")
                
        except Exception as e:
            self.log_test("Database Get Analyses", "ERROR", str(e))
    
    def test_performance_metrics(self):
        """Test performance under load."""
        print("\n⚡ Testing Performance...")
        
        def analyze_image(image_path):
            try:
                start_time = time.time()
                results = self.analyzer.analyze_from_file(image_path)
                duration = time.time() - start_time
                return duration, "success" if "error" not in results else "error"
            except Exception as e:
                return 0, str(e)
        
        # Test concurrent processing
        test_images = ["data/test_images/demo_pcb.png"] * 3
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(analyze_image, test_images))
        total_duration = time.time() - start_time
        
        success_count = sum(1 for _, status in results if status == "success")
        avg_duration = sum(duration for duration, _ in results) / len(results) if results else 0
        
        self.log_test("Concurrent Processing", "PASS" if success_count == len(results) else "FAIL",
                     f"{success_count}/{len(results)} successful, avg {avg_duration:.2f}s, total {total_duration:.2f}s")
    
    def test_error_handling(self):
        """Test error handling and edge cases."""
        print("\n🛡️ Testing Error Handling...")
        
        # Test with non-existent file
        try:
            results = self.analyzer.analyze_from_file("non_existent_file.jpg")
            if "error" in results:
                self.log_test("Non-existent File", "PASS", "Properly handled missing file")
            else:
                self.log_test("Non-existent File", "FAIL", "Should have returned error")
        except Exception as e:
            self.log_test("Non-existent File", "ERROR", str(e))
        
        # Test with invalid image
        try:
            # Create a text file with .jpg extension
            with open("data/test_images/invalid.jpg", "w") as f:
                f.write("This is not an image")
            
            results = self.analyzer.analyze_from_file("data/test_images/invalid.jpg")
            if "error" in results:
                self.log_test("Invalid Image", "PASS", "Properly handled invalid image")
            else:
                self.log_test("Invalid Image", "FAIL", "Should have returned error")
                
            os.remove("data/test_images/invalid.jpg")
        except Exception as e:
            self.log_test("Invalid Image", "ERROR", str(e))
    
    def test_web_interface_availability(self):
        """Test web interface availability."""
        print("\n🌍 Testing Web Interface...")
        
        try:
            start_time = time.time()
            response = requests.get("http://localhost:7860", timeout=10)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                self.log_test("Web Interface", "PASS", "Gradio interface accessible", duration)
            else:
                self.log_test("Web Interface", "FAIL", f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_test("Web Interface", "ERROR", f"Interface not accessible: {str(e)}")
    
    def test_system_health(self):
        """Test overall system health."""
        print("\n🏥 Testing System Health...")
        
        # Check if servers are running
        try:
            api_response = requests.get(f"{self.api_base_url}/health", timeout=5)
            if api_response.status_code == 200:
                health_data = api_response.json()
                status = health_data.get("status", "unknown")
                self.log_test("API Health", "PASS", f"Status: {status}")
            else:
                self.log_test("API Health", "FAIL", f"Status: {api_response.status_code}")
        except Exception as e:
            self.log_test("API Health", "ERROR", str(e))
        
        # Check database health
        try:
            analyses = self.database.get_recent_analyses(limit=1)
            if analyses is not None:
                self.log_test("Database Health", "PASS", "Database accessible")
            else:
                self.log_test("Database Health", "FAIL", "Database not accessible")
        except Exception as e:
            self.log_test("Database Health", "ERROR", str(e))
    
    def generate_report(self):
        """Generate comprehensive test report."""
        print("\n📊 Generating Test Report...")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed_tests = sum(1 for r in self.test_results if r["status"] == "FAIL")
        error_tests = sum(1 for r in self.test_results if r["status"] == "ERROR")
        skipped_tests = sum(1 for r in self.test_results if r["status"] == "SKIP")
        
        total_duration = time.time() - self.start_time
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "errors": error_tests,
                "skipped": skipped_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "total_duration": total_duration
            },
            "results": self.test_results
        }
        
        # Save report
        with open("test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"📊 COMPREHENSIVE TEST REPORT")
        print(f"{'='*60}")
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️ Errors: {error_tests}")
        print(f"⏭️ Skipped: {skipped_tests}")
        print(f"📈 Success Rate: {report['summary']['success_rate']:.1f}%")
        print(f"⏱️ Total Duration: {total_duration:.2f}s")
        print(f"{'='*60}")
        
        if failed_tests == 0 and error_tests == 0:
            print("🎉 ALL TESTS PASSED! System is fully functional!")
        else:
            print("🔧 Some tests failed. Check individual results above.")
        
        return report
    
    def run_all_tests(self):
        """Run all comprehensive tests."""
        print("🚀 Starting Comprehensive Circuit.AI Testing Suite")
        print("=" * 60)
        
        self.test_system_health()
        self.test_component_detection()
        self.test_api_endpoints()
        self.test_image_upload_api()
        self.test_database_operations()
        self.test_performance_metrics()
        self.test_error_handling()
        self.test_web_interface_availability()
        
        return self.generate_report()


def main():
    """Main testing function."""
    tester = ComprehensiveTester()
    report = tester.run_all_tests()
    
    # Exit with appropriate code
    if report["summary"]["failed"] == 0 and report["summary"]["errors"] == 0:
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Some tests failed


if __name__ == "__main__":
    main()
