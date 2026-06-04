#!/usr/bin/env python3
"""Demo script for 3D Splicer MVP"""

import requests
import json
from pathlib import Path

def demo_api():
    """Demonstrate the API functionality."""
    print("🚀 3D Splicer MVP Demo")
    print("=" * 50)
    
    # Check if API is running
    try:
        response = requests.get("http://127.0.0.1:8000/health")
        if response.status_code == 200:
            print("✅ API is running and healthy")
        else:
            print("❌ API is not responding properly")
            return
    except requests.exceptions.ConnectionError:
        print("❌ API is not running. Start it with: uvicorn src.api.main:app --reload")
        return
    
    # Load example description
    desc_path = Path(__file__).parent / "examples" / "iphone7_desc.json"
    with open(desc_path) as f:
        desc = json.load(f)
    
    print(f"\n📱 Generating case for: {desc['device']}")
    print(f"   PCB: {desc['pcb']['width_mm']}x{desc['pcb']['height_mm']}mm")
    print(f"   Ports: {len(desc['ports'])}")
    print(f"   Mount points: {len(desc['mounts'])}")
    
    # Send request to API
    try:
        response = requests.post(
            "http://127.0.0.1:8000/v1/splice",
            json=desc,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ STL generation successful!")
            print(f"   Output: {result['stl_path']}")
            print(f"   Faces: {result['validation']['faces']}")
            print(f"   Watertight: {result['validation']['watertight']}")
        else:
            print(f"❌ Generation failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    demo_api()
