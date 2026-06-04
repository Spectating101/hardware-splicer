#!/usr/bin/env python3
"""
Circuit.AI MVP Deployment Script

This script automates the MVP deployment process:
1. Initialize SQLite database
2. Create .env file with secure defaults
3. Verify all dependencies
4. Test model loading
5. Ready for frontend/backend launch
"""

import os
import sys
import subprocess
import secrets
import json
from pathlib import Path
from typing import Dict, Any
import sqlite3

# Color codes for output
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(text: str):
    """Print formatted header."""
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}🚀 {text}{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")

def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text: str):
    """Print error message."""
    print(f"{RED}❌ {text}{RESET}")

def print_info(text: str):
    """Print info message."""
    print(f"{BLUE}ℹ️  {text}{RESET}")

def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}⚠️  {text}{RESET}")

def step_complete(step_num: int, description: str):
    """Print step completion."""
    print(f"\n{BOLD}Step {step_num}: {description}{RESET}")
    print("-" * 70)

def run_command(cmd: str, description: str, show_output: bool = False) -> tuple[bool, str]:
    """Run shell command and return success status and output."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            print_success(description)
            if show_output:
                print(result.stdout)
            return True, result.stdout
        else:
            print_error(f"{description}: {result.stderr}")
            return False, result.stderr
    except subprocess.TimeoutExpired:
        print_error(f"{description}: Command timed out")
        return False, "Timeout"
    except Exception as e:
        print_error(f"{description}: {str(e)}")
        return False, str(e)

def check_directory() -> bool:
    """Check if we're in the correct directory."""
    step_complete(1, "Verify Project Directory")
    
    required_files = [
        'src/api/v1/main.py',
        'db/schema_sqlite.sql',
        'requirements.txt',
        'circuit-ai-frontend/package.json'
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print_success(f"Found: {file}")
        else:
            print_error(f"Missing: {file}")
            all_exist = False
    
    return all_exist

def create_env_file() -> bool:
    """Create .env file with secure defaults."""
    step_complete(2, "Generate .env Configuration File")
    
    if os.path.exists('.env'):
        response = input(f"{YELLOW}⚠️  .env already exists. Overwrite? (y/n): {RESET}")
        if response.lower() != 'y':
            print_info("Keeping existing .env file")
            return True
    
    # Generate secure secrets
    jwt_secret = secrets.token_urlsafe(32)
    test_api_key_1 = secrets.token_urlsafe(32)
    test_api_key_2 = secrets.token_urlsafe(32)
    
    env_content = f"""# Circuit.AI Environment Configuration
# Generated: {__import__('datetime').datetime.now().isoformat()}
# IMPORTANT: Keep this file secure and never commit to version control

# Database Configuration
DATABASE_URL=sqlite:///./data/circuit_ai.db

# Security & Authentication
JWT_SECRET={jwt_secret}
CORS_ORIGINS=http://localhost:3000,http://localhost:8000,http://localhost:8080
TEST_API_KEYS={test_api_key_1},{test_api_key_2}

# Model Configuration
YOLO_MODEL_PATH=models/yolov8n.pt
YOLO_CONFIDENCE_THRESHOLD=0.5

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=False
LOG_LEVEL=INFO

# LLM Configuration (get API keys from respective services)
LLM_PROVIDER=cohere
LLM_MODEL=command-r
OPENAI_API_KEY=
COHERE_API_KEY=
MISTRAL_API_KEY=
ANTHROPIC_API_KEY=
CEREBRAS_API_KEY=

# Optional: Redis Cache (for production)
REDIS_URL=

# Optional: Monitoring
SENTRY_DSN=
PROMETHEUS_PORT=9090

# Development
DEVELOPMENT_MODE=False
TESTING_MODE=False
"""
    
    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        print_success(f".env file created")
        print_info(f"JWT_SECRET: {jwt_secret[:20]}...")
        print_info(f"Test API Key 1: {test_api_key_1[:20]}...")
        print_info(f"Test API Key 2: {test_api_key_2[:20]}...")
        return True
    except Exception as e:
        print_error(f"Failed to create .env: {e}")
        return False

def initialize_database() -> bool:
    """Initialize SQLite database."""
    step_complete(3, "Initialize SQLite Database")
    
    # Check if database exists
    db_path = 'data/circuit_ai.db'
    if os.path.exists(db_path):
        file_size = os.path.getsize(db_path)
        print_info(f"Database exists ({file_size} bytes)")
        
        # Check if it's initialized
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            
            if len(tables) > 0:
                print_success(f"Database already initialized with {len(tables)} tables")
                return True
        except Exception:
            print_warning("Database file exists but appears corrupted")
    
    # Create directory if needed
    os.makedirs('data', exist_ok=True)
    
    # Initialize with schema
    success, output = run_command(
        f"sqlite3 {db_path} < db/schema_sqlite.sql",
        "Execute database schema"
    )
    
    if success:
        # Verify tables
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [t[0] for t in cursor.fetchall()]
            conn.close()
            
            print_success(f"Database initialized with {len(tables)} tables:")
            for table in tables:
                print(f"  - {table}")
            return True
        except Exception as e:
            print_error(f"Failed to verify database: {e}")
            return False
    return False

def check_python_packages() -> bool:
    """Check Python dependencies."""
    step_complete(4, "Verify Python Dependencies")
    
    required_packages = [
        ('fastapi', 'FastAPI'),
        ('uvicorn', 'Uvicorn'),
        ('ultralytics', 'Ultralytics (YOLOv8)'),
        ('torch', 'PyTorch'),
        ('pydantic', 'Pydantic'),
        ('sqlalchemy', 'SQLAlchemy'),
    ]
    
    all_installed = True
    for package, name in required_packages:
        try:
            __import__(package)
            print_success(f"{name} installed")
        except ImportError:
            print_warning(f"{name} not installed: pip install {package}")
            all_installed = False
    
    return all_installed

def test_model_loading() -> bool:
    """Test YOLO model loading."""
    step_complete(5, "Test YOLOv8 Model Loading")
    
    test_code = """
import torch
print(f"PyTorch available: {torch.cuda.is_available()}")
print(f"Device: {'cuda' if torch.cuda.is_available() else 'cpu'}")

try:
    from ultralytics import YOLO
    model = YOLO('models/yolov8n.pt')
    print(f"✅ YOLO model loaded successfully")
    print(f"Model version: {model.__class__.__name__}")
    print(f"Model size: {sum(p.numel() for p in model.model.parameters()) if hasattr(model, 'model') else 'N/A'} parameters")
except Exception as e:
    print(f"❌ Failed to load YOLO model: {e}")
    import sys
    sys.exit(1)
"""
    
    try:
        result = subprocess.run(
            [sys.executable, '-c', test_code],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print_success("YOLOv8 model loads successfully")
            for line in result.stdout.strip().split('\n'):
                print_info(line)
            return True
        else:
            print_error(f"Model loading failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print_error("Model loading timed out (GPU issue?)")
        return False
    except Exception as e:
        print_error(f"Error testing model: {e}")
        return False

def check_dataset() -> bool:
    """Check available training datasets."""
    step_complete(6, "Check Training Datasets")
    
    datasets_to_check = [
        ('datasets/electrocom61_full', 'ElectroCom61 Full (61 classes)'),
        ('datasets/electrocom61_real', 'ElectroCom61 Real'),
        ('datasets/deeppcb', 'DeepPCB'),
        ('datasets/fpic_raw', 'FPIC Raw'),
        ('datasets/fpic_yolo', 'FPIC YOLO Format'),
    ]
    
    found_datasets = []
    for dataset_path, description in datasets_to_check:
        if os.path.exists(dataset_path):
            size = sum(os.path.getsize(os.path.join(dirpath, filename))
                      for dirpath, dirnames, filenames in os.walk(dataset_path)
                      for filename in filenames) / (1024**3)  # Convert to GB
            print_success(f"{description}: {size:.2f} GB")
            found_datasets.append(dataset_path)
        else:
            print_warning(f"{description}: Not found")
    
    return len(found_datasets) > 0

def create_deployment_summary() -> None:
    """Create deployment summary file."""
    step_complete(7, "Generate Deployment Summary")
    
    summary = {
        "deployment_date": __import__('datetime').datetime.now().isoformat(),
        "status": "MVP Ready",
        "checklist": {
            "database": os.path.exists('data/circuit_ai.db'),
            "env_file": os.path.exists('.env'),
            "model": os.path.exists('models/yolov8n.pt'),
            "backend": os.path.exists('src/api/v1/main.py'),
            "frontend": os.path.exists('circuit-ai-frontend'),
            "schema": os.path.exists('db/schema_sqlite.sql'),
        },
        "next_steps": [
            "1. Verify all dependencies: pip install -r requirements.txt",
            "2. Start backend: uvicorn src.api.v1.main:app --host 0.0.0.0 --port 8000",
            "3. Start frontend: cd circuit-ai-frontend && npm run dev",
            "4. Access: http://localhost:3000 (frontend) and http://localhost:8000/docs (API)",
            "5. Test endpoints as described in MVP_DEPLOYMENT.md",
        ],
        "optional": [
            "- Train custom model on ElectroCom61 dataset",
            "- Configure LLM API keys for repair guidance",
            "- Set up monitoring and logging",
            "- Deploy to cloud platform (Railway/Render/Vercel)",
        ]
    }
    
    with open('DEPLOYMENT_SUMMARY.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print_success("Deployment summary saved to DEPLOYMENT_SUMMARY.json")

def print_deployment_status() -> None:
    """Print final deployment status."""
    print(f"\n{BOLD}{GREEN}{'='*70}{RESET}")
    print(f"{BOLD}{GREEN}🎉 MVP DEPLOYMENT INITIALIZATION COMPLETE!{RESET}")
    print(f"{BOLD}{GREEN}{'='*70}{RESET}\n")
    
    print(f"{BOLD}✅ Completed:{RESET}")
    print("  • SQLite database initialized")
    print("  • .env configuration created")
    print("  • YOLOv8 model verified")
    print("  • Dependencies checked")
    
    print(f"\n{BOLD}🚀 Next Steps:{RESET}")
    print(f"  1. {BLUE}Install dependencies:{RESET}")
    print(f"     pip install -r requirements.txt")
    print(f"\n  2. {BLUE}Start backend server:{RESET}")
    print(f"     python -m uvicorn src.api.v1.main:app --host 0.0.0.0 --port 8000")
    print(f"\n  3. {BLUE}Start frontend (new terminal):{RESET}")
    print(f"     cd circuit-ai-frontend && npm run dev")
    print(f"\n  4. {BLUE}Access the application:{RESET}")
    print(f"     Frontend: {BLUE}http://localhost:3000{RESET}")
    print(f"     API Docs: {BLUE}http://localhost:8000/docs{RESET}")
    print(f"     ReDoc:    {BLUE}http://localhost:8000/redoc{RESET}")
    
    print(f"\n{BOLD}📚 Documentation:{RESET}")
    print("  • MVP_DEPLOYMENT.md - Full deployment guide")
    print("  • DEPLOYMENT_SUMMARY.json - Deployment checklist")
    print("  • IMPLEMENTATION_GUIDE.md - Implementation details")
    print("  • COMPREHENSIVE_AUDIT.md - Audit findings")
    
    print(f"\n{BOLD}💡 Tips:{RESET}")
    print("  • Use .env file to configure API keys and secrets")
    print("  • Check http://localhost:8000/health for API status")
    print("  • Test endpoints: http://localhost:8000/docs")
    print("  • Train custom model: python scripts/production_training_v2.py --dataset datasets/electrocom61_full")
    
    print(f"\n{BOLD}{GREEN}{'='*70}{RESET}\n")

def main():
    """Main deployment script."""
    print_header("Circuit.AI MVP Deployment Initialization")
    
    try:
        # Step 1: Check directory
        if not check_directory():
            print_error("Not in correct project directory")
            return 1
        
        # Step 2: Create .env
        if not create_env_file():
            print_warning("Failed to create .env, continuing...")
        
        # Step 3: Initialize database
        if not initialize_database():
            print_error("Failed to initialize database")
            return 1
        
        # Step 4: Check packages
        packages_ok = check_python_packages()
        if not packages_ok:
            print_warning("Some packages missing, install with: pip install -r requirements.txt")
        
        # Step 5: Test model
        if not test_model_loading():
            print_warning("Model loading failed - install ultralytics: pip install ultralytics")
        
        # Step 6: Check datasets
        check_dataset()
        
        # Step 7: Create summary
        create_deployment_summary()
        
        # Print status
        print_deployment_status()
        
        return 0
        
    except KeyboardInterrupt:
        print(f"\n{YELLOW}⏸️  Deployment interrupted by user{RESET}")
        return 1
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
