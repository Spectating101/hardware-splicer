"""
Circuit-AI Splicer Engine (Microservice Client)
===============================================
Talks to the 3d-splicer Microservice via HTTP.
Decouples the heavy CAD dependencies from the Main API.
"""

import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any

class SplicerEngine:
    def __init__(self):
        # Read env at runtime so callers can dynamically point to ephemeral/local splicer instances.
        self.api_url = (os.getenv("SPLICER_API_URL", "http://localhost:8000") or "http://localhost:8000").rstrip("/")
        self.endpoint = (os.getenv("SPLICER_ENDPOINT", "/v1/splice") or "/v1/splice").strip() or "/v1/splice"

    def generate_enclosure(self, vision_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Input: Vision Data (PCB Dimensions)
        Output: URL to download STL
        """
        # 1) Sanitize Data (use the robust BridgeAdapter if present)
        spec = self._bridge_adapter(vision_data)
        
        # 2) Call Microservice
        try:
            req = urllib.request.Request(
                f"{self.api_url}{self.endpoint}",
                data=json.dumps(spec).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result
                
        except Exception as e:
            # Try script-only mode for environments without CadQuery / offline STL generation.
            try:
                req2 = urllib.request.Request(
                    f"{self.api_url}/v1/splice/script",
                    data=json.dumps(spec).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req2) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    result["mode"] = "script"
                    return result
            except Exception as e2:
                return {
                    "status": "error",
                    "error": str(e),
                    "fallback_error": str(e2),
                    "note": "3d-splicer not reachable or cannot generate. Start 3d-splicer (Docker recommended) and set SPLICER_API_URL.",
                }

    def _bridge_adapter(self, vision_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from src.utils.bridge_adapter import BridgeAdapter  # type: ignore

            return BridgeAdapter.sanitize_vision_data(vision_data)
        except Exception:
            # Minimal fallback (kept for backward compatibility)
            return {
                "version": "v1",
                "device": vision_data.get("device_name", "unknown_device"),
                "pcb": {
                    "width_mm": vision_data.get("width", 100),
                    "height_mm": vision_data.get("height", 100),
                    "thickness_mm": vision_data.get("thickness", 1.6),
                    "corner_radius_mm": 2.0,
                },
                "enclosure": {"wall_mm": 2.0, "clearance_mm": 0.5, "lip_mm": 1.0, "fillet_mm": 1.0},
                "ports": vision_data.get("ports", []),
                "mounts": vision_data.get("mounts", []),
            }

if __name__ == "__main__":
    engine = SplicerEngine()
    print(engine.generate_enclosure({"width": 50, "height": 50}))
