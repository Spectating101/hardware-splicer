from typing import Dict, List, Any
import logging

logger = logging.getLogger("circuit_splicer_bridge")

class BridgeAdapter:
    """
    Sanitizes Circuit-AI Vision data for 3d-splicer.
    Enforces physical constraints and prevents geometry errors.
    """
    
    @staticmethod
    def sanitize_vision_data(vision_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Input: Raw Circuit-AI detection (bbox in mm or px)
        Output: Clean 3d-splicer Description JSON
        """
        
        pcb_width = vision_data.get("width", 100.0)
        pcb_height = vision_data.get("height", 100.0)
        pcb_thick = vision_data.get("thickness", 1.6)
        
        splicer_req = {
            "version": "v1",
            "device": vision_data.get("device_name", "unknown_device"),
            "pcb": {
                "width_mm": pcb_width,
                "height_mm": pcb_height,
                "thickness_mm": pcb_thick,
                "corner_radius_mm": 2.0
            },
            "enclosure": {"wall_mm": 2.0, "clearance_mm": 0.5, "lip_mm": 1.0, "fillet_mm": 1.0},
            "ports": [],
            "mounts": []
        }
        
        for p in vision_data.get("ports", []):
            label = p.get("label", "port")
            box = p.get("box") # [x1, y1, x2, y2]
            
            if not box or len(box) != 4:
                logger.warning(f"Skipping malformed port {label}: {box}")
                continue
                
            x1, y1, x2, y2 = box
            w = abs(x2 - x1)
            h = abs(y2 - y1)
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            
            # --- ROBUSTNESS LOGIC ---
            
            # 1. Clamp to bounds (prevent floating ports)
            cx = max(0, min(cx, pcb_width))
            cy = max(0, min(cy, pcb_height))
            
            # 2. Snap to nearest edge (Ports must exit the case)
            dist_left = cx
            dist_right = pcb_width - cx
            dist_bottom = cy # Assuming 0 is bottom
            dist_top = pcb_height - cy
            
            min_dist = min(dist_left, dist_right, dist_bottom, dist_top)
            
            side = "bottom"
            if min_dist == dist_bottom:
                side = "bottom"
                cy = 0 # Snap flush
            elif min_dist == dist_top:
                side = "top"
                cy = pcb_height
            elif min_dist == dist_left:
                side = "left"
                cx = 0
            elif min_dist == dist_right:
                side = "right"
                cx = pcb_width
                
            # 3. Collision Detection (Simple)
            # Check if this overlaps significantly with existing ports
            is_duplicate = False
            for existing in splicer_req["ports"]:
                ex, ey = existing["x_mm"], existing["y_mm"]
                if abs(ex - cx) < 2.0 and abs(ey - cy) < 2.0:
                    logger.info(f"Merging duplicate port {label} at {cx},{cy}")
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                splicer_req["ports"].append({
                    "name": label,
                    "type": "rect",
                    "x_mm": cx,
                    "y_mm": cy,
                    "w_mm": w,
                    "h_mm": h,
                    "side": side
                })
                
        return splicer_req
