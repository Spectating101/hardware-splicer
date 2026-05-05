"""
PCB Trace Analysis - Visual Geometric Analysis

Analyzes PCB traces without requiring ML training:
- Trace detection using image processing
- Connection inference from geometry
- Trace width estimation
- Current capacity calculation
- Short circuit detection
- Signal path reconstruction
"""

import numpy as np
import cv2
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Trace:
    """Represents a PCB trace."""
    trace_id: str
    start_point: Tuple[int, int]
    end_point: Tuple[int, int]
    path_points: List[Tuple[int, int]]
    width_px: float
    width_mm: Optional[float] = None
    length_px: float = 0
    length_mm: Optional[float] = None
    current_capacity_a: Optional[float] = None
    connected_components: List[str] = field(default_factory=list)
    layer: str = "top"  # top, bottom, inner
    trace_type: str = "signal"  # signal, power, ground


@dataclass
class Connection:
    """Represents electrical connection between components."""
    component1: str
    component2: str
    trace_id: str
    connection_type: str  # direct, via, multi_hop
    resistance_estimate_ohm: Optional[float] = None
    verified: bool = False


class TraceAnalyzer:
    """Analyzes PCB traces using computer vision."""

    def __init__(self):
        self.pixel_to_mm_ratio: Optional[float] = None
        self.copper_thickness_oz = 1.0  # Standard 1oz copper
        self.max_trace_candidates = 250
        self.max_short_check_traces = 120

    def analyze_traces(self, image: np.ndarray,
                       component_detections: List[Any],
                       calibration_mm: Optional[float] = None) -> Dict[str, Any]:
        """
        Analyze PCB traces from image using computer vision.

        No ML needed - pure image processing!
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Estimate pixel to mm ratio from component sizes if not provided
        if calibration_mm:
            self.pixel_to_mm_ratio = self._estimate_scale(component_detections, gray)

        # Extract copper traces
        traces = self._extract_traces(gray)

        # Identify connections between components
        connections = self._identify_connections(traces, component_detections)

        # Analyze trace widths and current capacity
        for trace in traces:
            if self.pixel_to_mm_ratio:
                trace.width_mm = trace.width_px * self.pixel_to_mm_ratio
                trace.length_mm = trace.length_px * self.pixel_to_mm_ratio
                trace.current_capacity_a = self._calculate_current_capacity(trace.width_mm)

        # Detect potential issues
        issues = self._detect_trace_issues(traces, connections)

        return {
            "traces": traces,
            "connections": connections,
            "trace_count": len(traces),
            "connection_count": len(connections),
            "issues": issues,
            "scale_mm_per_px": self.pixel_to_mm_ratio
        }

    def _extract_traces(self, gray_image: np.ndarray) -> List[Trace]:
        """
        Extract traces using edge detection and morphological operations.

        Classical computer vision - no ML!
        """
        traces = []

        # Adaptive thresholding to handle varying illumination
        binary = cv2.adaptiveThreshold(
            gray_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )

        # Morphological operations to clean up
        kernel = np.ones((3, 3), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        # Find contours (traces)
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = [
            (cv2.contourArea(contour), contour)
            for contour in contours
        ]
        candidates = [
            (area, contour)
            for area, contour in candidates
            if area >= 50
        ]
        candidates.sort(key=lambda item: item[0], reverse=True)

        for idx, (area, contour) in enumerate(candidates[: self.max_trace_candidates]):

            # Get bounding rect
            x, y, w, h = cv2.boundingRect(contour)

            # Estimate trace width (minimum of width/height for thin traces)
            width_px = min(w, h)

            # Get skeleton for path
            path_points = self._skeletonize_trace(contour)

            if len(path_points) < 2:
                continue

            # Calculate length
            length_px = self._calculate_path_length(path_points)

            trace = Trace(
                trace_id=f"trace_{idx}",
                start_point=tuple(path_points[0]),
                end_point=tuple(path_points[-1]),
                path_points=path_points,
                width_px=width_px,
                length_px=length_px
            )

            traces.append(trace)

        return traces

    def _skeletonize_trace(self, contour: np.ndarray) -> List[Tuple[int, int]]:
        """Extract centerline of trace."""
        # Fit line through contour points
        if len(contour) < 2:
            return []

        # Reshape contour
        points = contour.reshape(-1, 2)

        # Sort by x coordinate to get path order
        sorted_points = points[np.argsort(points[:, 0])]

        # Sample points along trace
        step = max(1, len(sorted_points) // 20)  # Sample ~20 points
        sampled = sorted_points[::step]

        return [tuple(p) for p in sampled]

    def _calculate_path_length(self, points: List[Tuple[int, int]]) -> float:
        """Calculate total length of path."""
        if len(points) < 2:
            return 0

        total_length = 0
        for i in range(len(points) - 1):
            p1 = np.array(points[i])
            p2 = np.array(points[i + 1])
            total_length += np.linalg.norm(p2 - p1)

        return total_length

    def _identify_connections(self, traces: List[Trace],
                             component_detections: List[Any]) -> List[Connection]:
        """Identify which components are connected by traces."""
        connections = []

        for trace in traces:
            # Find components near trace endpoints
            start_components = self._find_nearby_components(
                trace.start_point, component_detections, radius=50
            )
            end_components = self._find_nearby_components(
                trace.end_point, component_detections, radius=50
            )

            # Create connections
            seen_pairs: set[tuple[str, str]] = set()
            for comp1 in start_components:
                for comp2 in end_components:
                    if comp1 != comp2:
                        edge_key = tuple(sorted([comp1, comp2]))
                        if edge_key in seen_pairs:
                            continue
                        seen_pairs.add(edge_key)
                        connection = Connection(
                            component1=comp1,
                            component2=comp2,
                            trace_id=trace.trace_id,
                            connection_type="direct"
                        )

                        # Estimate resistance based on trace geometry
                        if trace.width_mm and trace.length_mm:
                            connection.resistance_estimate_ohm = self._calculate_trace_resistance(
                                trace.length_mm, trace.width_mm
                            )

                        connections.append(connection)
                        trace.connected_components.extend([comp1, comp2])

        return connections

    def _find_nearby_components(self, point: Tuple[int, int],
                                components: List[Any],
                                radius: int = 50) -> List[str]:
        """Find components within radius of point."""
        nearby = []
        px, py = point

        for comp in components:
            center = None
            class_name = None
            bbox = None
            if isinstance(comp, dict):
                center = comp.get("center")
                class_name = comp.get("class_name")
                bbox = comp.get("bbox")
            elif hasattr(comp, 'center') and comp.center:
                center = comp.center
                class_name = getattr(comp, "class_name", None)
                bbox = getattr(comp, "bbox", None)

            if center:
                cx, cy = center
                distance = np.sqrt((px - cx)**2 + (py - cy)**2)
                if distance <= radius:
                    instance_id = getattr(comp, "component_id", None)
                    if instance_id is not None:
                        nearby.append(str(instance_id))
                        continue
                    if isinstance(comp, dict):
                        explicit_id = comp.get("topology_id") or comp.get("_instance_id") or comp.get("id")
                        if explicit_id:
                            nearby.append(str(explicit_id))
                            continue
                    nearby.append(f"{str(class_name or 'unknown')}")
            elif bbox is not None:
                # Use bbox center
                x1, y1, x2, y2 = bbox
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                distance = np.sqrt((px - cx)**2 + (py - cy)**2)
                if distance <= radius:
                    instance_id = getattr(comp, "component_id", None)
                    if instance_id is not None:
                        nearby.append(str(instance_id))
                        continue
                    if isinstance(comp, dict):
                        explicit_id = comp.get("topology_id") or comp.get("_instance_id") or comp.get("id")
                        if explicit_id:
                            nearby.append(str(explicit_id))
                            continue
                    nearby.append(f"{str(class_name or 'unknown')}")

        return nearby

    def _calculate_current_capacity(self, width_mm: float,
                                   temp_rise_c: float = 10) -> float:
        """
        Calculate trace current capacity using IPC-2221 formula.

        Pure electrical engineering calculation!
        """
        # Convert to mils
        width_mils = width_mm * 39.37

        # Copper thickness in mils (1oz = 1.35 mils)
        thickness_mils = self.copper_thickness_oz * 1.35

        # Cross-sectional area
        area_sq_mils = width_mils * thickness_mils

        # IPC-2221 formula for external layers
        # I = k * dT^0.44 * A^0.725
        k = 0.048  # External layer constant
        current_a = k * (temp_rise_c ** 0.44) * (area_sq_mils ** 0.725)

        return current_a

    def _calculate_trace_resistance(self, length_mm: float, width_mm: float) -> float:
        """
        Calculate trace DC resistance.

        R = ρ * L / A
        where ρ = resistivity of copper = 1.68e-8 Ω·m
        """
        # Copper resistivity
        rho_copper = 1.68e-8  # Ω·m

        # Convert to meters
        length_m = length_mm / 1000
        width_m = width_mm / 1000
        thickness_m = (self.copper_thickness_oz * 0.035) / 1000  # 1oz = 35µm

        # Cross-sectional area
        area_m2 = width_m * thickness_m

        # Resistance
        if area_m2 > 0:
            resistance_ohm = rho_copper * length_m / area_m2
        else:
            resistance_ohm = float('inf')

        return resistance_ohm

    def _detect_trace_issues(self, traces: List[Trace],
                            connections: List[Connection]) -> List[Dict[str, Any]]:
        """Detect potential trace issues."""
        issues = []
        issue_traces = traces
        if len(traces) > self.max_short_check_traces:
            issue_traces = sorted(traces, key=lambda trace: trace.length_px, reverse=True)[: self.max_short_check_traces]
            issues.append({
                "severity": "info",
                "trace_id": "trace_density_limit",
                "issue": "Dense trace map truncated",
                "details": (
                    f"Short-circuit proximity checks were limited to the {self.max_short_check_traces} "
                    f"longest trace regions out of {len(traces)} extracted regions"
                ),
                "recommendation": "Use Gerber/KiCad input for exhaustive production net comparison"
            })

        # Check for very thin traces (potential current issues)
        for trace in issue_traces:
            if trace.width_mm and trace.width_mm < 0.15:  # < 0.15mm is very thin
                issues.append({
                    "severity": "warning",
                    "trace_id": trace.trace_id,
                    "issue": "Very thin trace",
                    "details": f"Width {trace.width_mm:.3f}mm may be insufficient for high current",
                    "recommendation": "Verify current requirements are low"
                })

            # Check for very long thin traces (high resistance)
            if trace.width_mm and trace.length_mm:
                if trace.width_mm < 0.3 and trace.length_mm > 50:
                    resistance = self._calculate_trace_resistance(trace.length_mm, trace.width_mm)
                    issues.append({
                        "severity": "warning",
                        "trace_id": trace.trace_id,
                        "issue": "High resistance trace",
                        "details": f"Long ({trace.length_mm:.1f}mm) thin ({trace.width_mm:.2f}mm) trace, R≈{resistance*1000:.1f}mΩ",
                        "recommendation": "May cause voltage drop under load"
                    })

        # Check for potential short circuits (traces very close together)
        for i, trace1 in enumerate(issue_traces):
            for trace2 in issue_traces[i+1:]:
                min_distance = self._minimum_trace_distance(trace1, trace2)
                if min_distance < 5:  # < 5 pixels very close
                    issues.append({
                        "severity": "critical",
                        "trace_id": f"{trace1.trace_id}_{trace2.trace_id}",
                        "issue": "Potential short circuit",
                        "details": f"Traces extremely close ({min_distance:.1f}px)",
                        "recommendation": "Inspect visually for shorts"
                    })

        return issues

    def _minimum_trace_distance(self, trace1: Trace, trace2: Trace) -> float:
        """Calculate minimum distance between two traces."""
        min_dist = float('inf')

        for p1 in trace1.path_points:
            for p2 in trace2.path_points:
                dist = np.linalg.norm(np.array(p1) - np.array(p2))
                min_dist = min(min_dist, dist)

        return min_dist

    def _estimate_scale(self, component_detections: List[Any],
                       image: np.ndarray) -> Optional[float]:
        """
        Estimate pixel-to-mm scale from known component sizes.

        Uses component database to get real-world sizes.
        """
        # Look for components with known sizes
        known_sizes = {
            "USB-Connector": 12.0,  # USB-A ~12mm width
            "Ethernet-Connector": 16.0,  # RJ45 ~16mm width
            "Arduino-Uno": 53.3,  # Arduino Uno width in mm
        }

        for comp in component_detections:
            if isinstance(comp, dict):
                comp_name = str(comp.get("class_name") or "")
                bbox = comp.get("bbox")
            else:
                comp_name = comp.class_name if hasattr(comp, 'class_name') else str(comp)
                bbox = getattr(comp, "bbox", None)

            for known_comp, real_size_mm in known_sizes.items():
                if known_comp in comp_name:
                    # Get component width in pixels
                    if bbox is not None:
                        x1, y1, x2, y2 = bbox
                        width_px = x2 - x1
                        # Calculate scale
                        scale = real_size_mm / width_px
                        return scale

        # Default estimate if no known components found
        # Assume typical PCB image is ~100mm wide
        return 100.0 / image.shape[1]

    def generate_trace_map(self, traces: List[Trace],
                          connections: List[Connection]) -> Dict[str, Any]:
        """Generate connectivity map showing which components are connected."""
        connectivity_graph = defaultdict(set)

        for conn in connections:
            connectivity_graph[conn.component1].add(conn.component2)
            connectivity_graph[conn.component2].add(conn.component1)

        # Find isolated components (no connections)
        all_components = set()
        for conn in connections:
            all_components.add(conn.component1)
            all_components.add(conn.component2)

        isolated = []
        for comp in all_components:
            if len(connectivity_graph[comp]) == 0:
                isolated.append(comp)

        # Find power/ground nets (highly connected nodes)
        power_ground_candidates = []
        for comp, connections_set in connectivity_graph.items():
            if len(connections_set) > 5:  # Connected to many components
                power_ground_candidates.append({
                    "component": comp,
                    "connections": len(connections_set),
                    "likely_type": "power_or_ground"
                })

        return {
            "connectivity_graph": {k: list(v) for k, v in connectivity_graph.items()},
            "isolated_components": isolated,
            "power_ground_candidates": power_ground_candidates,
            "total_nodes": len(all_components),
            "total_edges": len(connections)
        }


# Global instance
trace_analyzer = TraceAnalyzer()
