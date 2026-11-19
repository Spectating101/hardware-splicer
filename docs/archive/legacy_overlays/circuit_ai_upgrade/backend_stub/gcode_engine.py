"""
Circuit-AI G-Code Engine
========================
Generates CNC/Robot toolpaths from PCB geometry.
Compatible with Marlin 2.0 (Dum-E) and GRBL (CNC Mills).
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import math

@dataclass
class Point:
    x: float
    y: float
    z: float = 0.0

@dataclass
class ToolpathConfig:
    travel_z: float = 5.0      # Safe height (mm)
    work_z: float = -0.1       # Engraving/Probing depth (mm)
    feed_rate_xy: int = 1500   # Travel speed (mm/min)
    feed_rate_z: int = 200     # Plunge speed (mm/min)
    spindle_speed: int = 10000 # RPM (for milling)
    robot_mode: bool = True    # True = Dum-E (Arm), False = CNC Mill

class GCodeGenerator:
    def __init__(self, config: ToolpathConfig = ToolpathConfig()):
        self.config = config
        self.buffer: List[str] = []
        self.current_pos = Point(0, 0, 0)
        self.header()

    def header(self):
        """Standard G-Code Header"""
        self.buffer.append("; Circuit-AI Toolpath Generation")
        self.buffer.append(f"; Mode: {'ROBOT (Dum-E)' if self.config.robot_mode else 'CNC MILL'}")
        self.buffer.append("G21 ; Units: mm")
        self.buffer.append("G90 ; Absolute positioning")
        if not self.config.robot_mode:
            self.buffer.append(f"M3 S{self.config.spindle_speed} ; Spindle ON")
        self.buffer.append(f"G0 Z{self.config.travel_z} F{self.config.feed_rate_z} ; Safe Height")

    def move_to(self, x: float, y: float):
        """Rapid move to XY at Safe Z"""
        self.buffer.append(f"G0 X{x:.3f} Y{y:.3f} F{self.config.feed_rate_xy}")
        self.current_pos.x = x
        self.current_pos.y = y

    def plunge(self):
        """Move down to Work Z (With Safety Clamp)"""
        safe_limit = -2.0
        target_z = self.config.work_z
        
        if target_z < safe_limit:
            self.buffer.append(f"; SAFETY: Clamped Z from {target_z} to {safe_limit}")
            target_z = safe_limit
            
        self.buffer.append(f"G1 Z{target_z} F{self.config.feed_rate_z}")
        self.current_pos.z = target_z

    def retract(self):
        """Move up to Safe Z"""
        self.buffer.append(f"G0 Z{self.config.travel_z} F{self.config.feed_rate_z}")
        self.current_pos.z = self.config.travel_z

    def probe_point(self, x: float, y: float) -> List[str]:
        """Generate a probing sequence for a specific component pin"""
        # 1. Move to location
        self.move_to(x, y)
        # 2. Pause for vision alignment (Robot only)
        if self.config.robot_mode:
             self.buffer.append("M0 ; Pause for Alignment Check")
        # 3. Probe down
        self.plunge()
        # 4. Wait for electrical reading
        self.buffer.append("G4 P500 ; Dwell 500ms for stable reading")
        # 5. Retract
        self.retract()
        return self.buffer

    def mill_trace(self, start: Point, end: Point):
        """Generate milling path for a PCB trace"""
        self.move_to(start.x, start.y)
        self.plunge()
        self.buffer.append(f"G1 X{end.x:.3f} Y{end.y:.3f} F{self.config.feed_rate_xy}")
        self.retract()

    def export(self) -> str:
        """Finalize and return G-Code string"""
        self.buffer.append("M5 ; Spindle OFF")
        self.buffer.append("G0 X0 Y0 ; Return Home")
        self.buffer.append("M2 ; End Program")
        return "\n".join(self.buffer)

# --- AI Integration Layer ---
class SmartCAM:
    """
    Optimizes G-Code based on AI insights (Thermal, Component Sensitivity).
    """
    def generate_optimized_probe_sequence(self, components: List[dict]) -> str:
        """
        Input: List of components with 'sensitivity' metadata.
        Output: G-Code optimized for safety.
        """
        # Slow down for sensitive components
        safe_config = ToolpathConfig(feed_rate_z=50) 
        fast_config = ToolpathConfig(feed_rate_z=200)
        
        gc = GCodeGenerator(fast_config)
        
        for comp in components:
            is_sensitive = comp.get("sensitive", False)
            if is_sensitive:
                gc.buffer.append(f"; WARNING: Probing Sensitive Component {comp['ref']}")
                gc.config = safe_config # Slow down
            else:
                gc.config = fast_config
            
            gc.probe_point(comp['x'], comp['y'])
            
        return gc.export()

if __name__ == "__main__":
    # Test Run
    test_comps = [
        {"ref": "U1", "x": 40.0, "y": 30.0, "sensitive": True},
        {"ref": "C1", "x": 10.0, "y": 10.0, "sensitive": False}
    ]
    ai_cam = SmartCAM()
    print(ai_cam.generate_optimized_probe_sequence(test_comps))
