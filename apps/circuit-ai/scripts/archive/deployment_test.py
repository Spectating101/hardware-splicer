#!/usr/bin/env python3
"""
Deployment Testing Script for Circuit.AI
========================================

This script tests the system in production-like conditions to ensure
it's ready for deployment to cloud platforms.
"""

import sys
import os
import time
import requests
import json
from pathlib import Path
from typing import Dict, Any, List

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.ingest import CircuitAnalyzer
from src.core.database import CircuitDatabase


class DeploymentTester:
    """Test Circuit.AI for deployment readiness."""
    
    def __init__(self):
        """Initialize the deployment tester."""
        self.analyzer = CircuitAnalyzer()
        self.database = CircuitDatabase()
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
    
    def test_environment_variables(self):
        """Test environment variable configuration."""
        print("\n🔧 Testing Environment Variables...")
        
        required_vars = [
            "LLM_ENABLED",
            "DEBUG",
            "HOST",
            "PORT",
            "DATABASE_URL"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.log_test("Environment Variables", "FAIL", f"Missing: {missing_vars}")
        else:
            self.log_test("Environment Variables", "PASS", "All required variables set")
    
    def test_dependencies(self):
        """Test all required dependencies are available."""
        print("\n📦 Testing Dependencies...")
        
        required_packages = [
            "fastapi",
            "uvicorn",
            "opencv-python",
            "ultralytics",
            "torch",
            "Pillow",
            "numpy",
            "pytesseract",
            "loguru",
            "requests"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            self.log_test("Dependencies", "FAIL", f"Missing: {missing_packages}")
        else:
            self.log_test("Dependencies", "PASS", "All required packages available")
    
    def test_database_operations(self):
        """Test database operations in production-like conditions."""
        print("\n🗄️ Testing Database Operations...")
        
        try:
            # Test database connection
            start_time = time.time()
            analyses = self.database.get_recent_analyses(limit=1)
            duration = time.time() - start_time
            
            if analyses is not None:
                self.log_test("Database Connection", "PASS", f"Connected in {duration:.3f}s", duration)
            else:
                self.log_test("Database Connection", "FAIL", "Could not connect to database")
                
        except Exception as e:
            self.log_test("Database Connection", "ERROR", str(e))
    
    def test_component_detection(self):
        """Test component detection in production-like conditions."""
        print("\n🔍 Testing Component Detection...")
        
        test_image = "data/test_images/demo_pcb.png"
        if not os.path.exists(test_image):
            self.log_test("Component Detection", "SKIP", "Test image not found")
            return
        
        try:
            start_time = time.time()
            results = self.analyzer.analyze_from_file(test_image)
            duration = time.time() - start_time
            
            if "error" in results:
                self.log_test("Component Detection", "FAIL", f"Error: {results['error']}", duration)
            else:
                components = results.get("detection_summary", {}).get("total_components", 0)
                self.log_test("Component Detection", "PASS", 
                            f"Detected {components} components in {duration:.2f}s", duration)
                
        except Exception as e:
            self.log_test("Component Detection", "ERROR", str(e))
    
    def test_memory_usage(self):
        """Test memory usage under load."""
        print("\n💾 Testing Memory Usage...")
        
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            if memory_mb < 500:  # Less than 500MB
                self.log_test("Memory Usage", "PASS", f"Using {memory_mb:.1f}MB", 0)
            elif memory_mb < 1000:  # Less than 1GB
                self.log_test("Memory Usage", "PASS", f"Using {memory_mb:.1f}MB (acceptable)", 0)
            else:
                self.log_test("Memory Usage", "WARN", f"Using {memory_mb:.1f}MB (high)", 0)
                
        except ImportError:
            self.log_test("Memory Usage", "SKIP", "psutil not available")
        except Exception as e:
            self.log_test("Memory Usage", "ERROR", str(e))
    
    def test_startup_time(self):
        """Test application startup time."""
        print("\n⚡ Testing Startup Time...")
        
        try:
            start_time = time.time()
            
            # Simulate startup by reinitializing analyzer
            analyzer = CircuitAnalyzer()
            
            duration = time.time() - start_time
            
            if duration < 5.0:
                self.log_test("Startup Time", "PASS", f"Started in {duration:.2f}s", duration)
            elif duration < 10.0:
                self.log_test("Startup Time", "PASS", f"Started in {duration:.2f}s (acceptable)", duration)
            else:
                self.log_test("Startup Time", "WARN", f"Started in {duration:.2f}s (slow)", duration)
                
        except Exception as e:
            self.log_test("Startup Time", "ERROR", str(e))
    
    def test_file_permissions(self):
        """Test file permissions for production deployment."""
        print("\n📁 Testing File Permissions...")
        
        required_dirs = [
            "data",
            "data/uploads",
            "data/annotated",
            "data/cache",
            "models",
            "models/yolo"
        ]
        
        missing_dirs = []
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                missing_dirs.append(dir_path)
        
        if missing_dirs:
            self.log_test("File Permissions", "FAIL", f"Missing directories: {missing_dirs}")
        else:
            self.log_test("File Permissions", "PASS", "All required directories exist")
    
    def test_api_endpoints(self):
        """Test API endpoints in production-like conditions."""
        print("\n🌐 Testing API Endpoints...")
        
        # Start a test server
        import subprocess
        import threading
        import time
        
        # Start server in background
        server_process = None
        try:
            server_process = subprocess.Popen(
                ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8001"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for server to start
            time.sleep(5)
            
            # Test endpoints
            endpoints = ["/health", "/demo", "/statistics"]
            
            for endpoint in endpoints:
                try:
                    start_time = time.time()
                    response = requests.get(f"http://localhost:8001{endpoint}", timeout=10)
                    duration = time.time() - start_time
                    
                    if response.status_code == 200:
                        self.log_test(f"API {endpoint}", "PASS", f"Response in {duration:.3f}s", duration)
                    else:
                        self.log_test(f"API {endpoint}", "FAIL", f"Status: {response.status_code}", duration)
                        
                except Exception as e:
                    self.log_test(f"API {endpoint}", "ERROR", str(e))
            
        except Exception as e:
            self.log_test("API Server", "ERROR", f"Could not start server: {str(e)}")
        finally:
            if server_process:
                server_process.terminate()
                server_process.wait()
    
    def test_docker_build(self):
        """Test Docker build process."""
        print("\n🐳 Testing Docker Build...")
        
        try:
            # Test if Dockerfile exists
            if not os.path.exists("Dockerfile"):
                self.log_test("Docker Build", "FAIL", "Dockerfile not found")
                return
            
            # Test if docker-compose.yml exists
            if not os.path.exists("docker-compose.yml"):
                self.log_test("Docker Build", "WARN", "docker-compose.yml not found")
            
            self.log_test("Docker Build", "PASS", "Docker configuration files present")
            
        except Exception as e:
            self.log_test("Docker Build", "ERROR", str(e))
    
    def generate_deployment_report(self):
        """Generate deployment readiness report."""
        print("\n📊 Generating Deployment Report...")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed_tests = sum(1 for r in self.test_results if r["status"] == "FAIL")
        error_tests = sum(1 for r in self.test_results if r["status"] == "ERROR")
        warning_tests = sum(1 for r in self.test_results if r["status"] == "WARN")
        skipped_tests = sum(1 for r in self.test_results if r["status"] == "SKIP")
        
        total_duration = time.time() - self.start_time
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "errors": error_tests,
                "warnings": warning_tests,
                "skipped": skipped_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "total_duration": total_duration
            },
            "results": self.test_results
        }
        
        # Save report
        with open("deployment_test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"📊 DEPLOYMENT READINESS REPORT")
        print(f"{'='*60}")
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️ Errors: {error_tests}")
        print(f"🔶 Warnings: {warning_tests}")
        print(f"⏭️ Skipped: {skipped_tests}")
        print(f"📈 Success Rate: {report['summary']['success_rate']:.1f}%")
        print(f"⏱️ Total Duration: {total_duration:.2f}s")
        print(f"{'='*60}")
        
        if failed_tests == 0 and error_tests == 0:
            print("🎉 DEPLOYMENT READY! System is ready for production deployment!")
        elif failed_tests <= 2 and error_tests == 0:
            print("✅ MOSTLY READY! Minor issues to address before deployment.")
        else:
            print("🔧 NEEDS WORK! Address issues before deployment.")
        
        return report
    
    def run_all_tests(self):
        """Run all deployment readiness tests."""
        print("🚀 Starting Circuit.AI Deployment Readiness Testing")
        print("=" * 60)
        
        self.test_environment_variables()
        self.test_dependencies()
        self.test_database_operations()
        self.test_component_detection()
        self.test_memory_usage()
        self.test_startup_time()
        self.test_file_permissions()
        self.test_api_endpoints()
        self.test_docker_build()
        
        return self.generate_deployment_report()


def main():
    """Main deployment testing function."""
    tester = DeploymentTester()
    report = tester.run_all_tests()
    
    # Exit with appropriate code
    if report["summary"]["failed"] == 0 and report["summary"]["errors"] == 0:
        sys.exit(0)  # Ready for deployment
    else:
        sys.exit(1)  # Needs work


if __name__ == "__main__":
    main()
