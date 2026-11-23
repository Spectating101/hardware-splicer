"""
Circuit-AI Splicer Engine (Microservice Client)
===============================================
Talks to the 3d-splicer Microservice via HTTP.
Decouples the heavy CAD dependencies from the Main API.
"""

import os
import json
import urllib.request
from typing import Dict, Any

SPLICER_API_URL = os.getenv("SPLICER_API_URL", "http://localhost:8001")

class SplicerEngine:
    def __init__(self):
        self.api_url = SPLICER_API_URL

    def generate_enclosure(self, vision_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Input: Vision Data (PCB Dimensions)
        Output: URL to download STL
        """
        # 1. Sanitize Data
        spec = self._bridge_adapter(vision_data)
        
        # 2. Call Microservice
        try:
            req = urllib.request.Request(
                f"{self.api_url}/generate",
                data=json.dumps(spec).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result
                
        except Exception as e:
            # Fallback for Demo/Dev when service is offline
            print(f"[Splicer] Service unavailable ({e}). Returning Mock Data.")
            return {
                "status": "mock_success",
                "stl_url": "/api/mock/enclosure.stl",
                "note": "Real Splicer Service not running. Start 3d-splicer container."
            }

    def _bridge_adapter(self, vision_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "version": "v1",
            "pcb": {
                "width_mm": vision_data.get("width", 100),
                "height_mm": vision_data.get("height", 100),
                "thickness_mm": 1.6
            },
            "ports": vision_data.get("ports", [])
        }

if __name__ == "__main__":
    engine = SplicerEngine()
    print(engine.generate_enclosure({"width": 50, "height": 50}))