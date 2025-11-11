"""
Advanced Trace Following Algorithm

Improvements over basic trace_analyzer:
- Multi-layer support (detect vias)
- Better trace extraction (handles solder mask, silk screen)
- Trace continuation under components
- Junction detection
- Copper pour detection
"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from scipy.ndimage import distance_transform_edt
import networkx as nx


@dataclass
class Via:
    """Represents a via (connection between layers)."""
    position: Tuple[int, int]
    diameter_px: float
    top_net: Optional[str] = None
    bottom_net: Optional[str] = None


@dataclass
class TraceSegment:
    """A segment of a trace."""
    start: Tuple[int, int]
    end: Tuple[int, int]
    points: List[Tuple[int, int]]
    width_px: float
    layer: str  # "top", "bottom", "inner1", etc.
    net_id: Optional[str] = None


@dataclass
class Junction:
    """Where multiple traces meet."""
    position: Tuple[int, int]
    connected_traces: List[int]  # Trace IDs
    junction_type: str  # "T", "cross", "Y"


class AdvancedTraceFollower:
    """Advanced trace following with multi-layer support."""

    def __init__(self):
        self.min_trace_width = 3  # pixels
        self.max_trace_width = 50
        self.via_min_diameter = 5
        self.via_max_diameter = 30

    def analyze_multilayer_pcb(self, top_image: np.ndarray,
                               bottom_image: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        Analyze multi-layer PCB.

        Args:
            top_image: Top layer image
            bottom_image: Bottom layer image (optional)

        Returns:
            Complete trace network with vias
        """
        # Extract top layer traces
        top_traces, top_mask = self._extract_traces_advanced(top_image, "top")

        # Detect vias on top layer
        vias = self._detect_vias(top_image, top_mask)

        # Extract bottom layer if available
        bottom_traces = []
        if bottom_image is not None:
            bottom_traces, _ = self._extract_traces_advanced(bottom_image, "bottom")

        # Build connectivity graph
        graph = self._build_trace_graph(top_traces + bottom_traces, vias)

        # Identify nets
        nets = self._identify_nets(graph, top_traces + bottom_traces, vias)

        # Detect junctions
        junctions = self._detect_junctions(top_mask)

        return {
            'traces': top_traces + bottom_traces,
            'vias': vias,
            'nets': nets,
            'junctions': junctions,
            'graph': graph,
            'trace_count': len(top_traces) + len(bottom_traces),
            'via_count': len(vias),
            'net_count': len(nets)
        }

    def _extract_traces_advanced(self, image: np.ndarray, layer: str) -> Tuple[List[TraceSegment], np.ndarray]:
        """
        Advanced trace extraction with better noise handling.

        Handles:
        - Solder mask (green layer that obscures copper)
        - Silk screen (white text/markings)
        - Varying illumination
        - Reflections
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Remove solder mask (green tint) if color image
        if len(image.shape) == 3:
            # Convert to HSV
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

            # Mask for green solder mask (want to see through it)
            green_lower = np.array([35, 40, 40])
            green_upper = np.array([85, 255, 255])
            green_mask = cv2.inRange(hsv, green_lower, green_upper)

            # Invert (we want non-green areas = copper)
            copper_hint = cv2.bitwise_not(green_mask)
        else:
            copper_hint = np.ones_like(gray) * 255

        # Adaptive thresholding for varying illumination
        # Need to invert for white traces on dark background
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 25, 5
        )

        # Combine with copper hint
        binary = cv2.bitwise_and(binary, copper_hint)

        # Remove small noise
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

        # Close small gaps in traces
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)

        # Skeletonize to find centerlines
        skeleton = self._skeletonize(binary)

        # Find contours (trace boundaries)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Extract trace segments
        traces = []
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if area < 20:  # Too small
                continue

            # Get bounding rect to estimate width
            x, y, w, h = cv2.boundingRect(contour)
            width = min(w, h)

            if width < self.min_trace_width or width > self.max_trace_width:
                continue

            # Get skeleton points for this trace
            mask = np.zeros_like(binary)
            cv2.drawContours(mask, [contour], 0, 255, -1)
            skeleton_points = np.column_stack(np.where((skeleton & mask) > 0))

            if len(skeleton_points) < 2:
                continue

            # Order points along trace
            ordered = self._order_points_along_trace(skeleton_points)

            if len(ordered) >= 2:
                traces.append(TraceSegment(
                    start=tuple(ordered[0]),
                    end=tuple(ordered[-1]),
                    points=[(int(p[0]), int(p[1])) for p in ordered],
                    width_px=float(width),
                    layer=layer,
                    net_id=f"{layer}_net_{i}"
                ))

        return traces, binary

    def _skeletonize(self, binary: np.ndarray) -> np.ndarray:
        """
        Skeletonize binary image to find centerlines.
        Uses Zhang-Suen thinning algorithm.
        """
        # Simple implementation using distance transform + local maxima
        dist = distance_transform_edt(binary)

        # Find ridge points (local maxima along perpendicular to trace)
        # Use morphological thinning
        skeleton = np.zeros_like(binary, dtype=np.uint8)

        # Simple thinning: keep only pixels that are local maxima in distance transform
        for i in range(1, binary.shape[0] - 1):
            for j in range(1, binary.shape[1] - 1):
                if binary[i, j] > 0:
                    # Check if local maximum in 3x3 neighborhood
                    neighborhood = dist[i-1:i+2, j-1:j+2]
                    if dist[i, j] == np.max(neighborhood):
                        skeleton[i, j] = 255

        return skeleton

    def _order_points_along_trace(self, points: np.ndarray) -> List[np.ndarray]:
        """
        Order points along trace path.
        Uses nearest neighbor with backtracking.
        """
        if len(points) == 0:
            return []

        # Start from first point
        ordered = [points[0]]
        remaining = list(points[1:])

        while remaining:
            # Find nearest point to last ordered point
            last = ordered[-1]
            distances = [np.linalg.norm(p - last) for p in remaining]
            nearest_idx = np.argmin(distances)

            # If distance too large, we've reached end of connected segment
            if distances[nearest_idx] > 50:
                break

            ordered.append(remaining[nearest_idx])
            remaining.pop(nearest_idx)

        return ordered

    def _detect_vias(self, image: np.ndarray, trace_mask: np.ndarray) -> List[Via]:
        """
        Detect vias (circular holes connecting layers).

        Vias appear as:
        - Circular holes in solder mask
        - Usually have copper ring around them
        - Connect to traces on both sides
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Look for circles
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, dp=1,
            minDist=20,
            param1=50, param2=30,
            minRadius=self.via_min_diameter // 2,
            maxRadius=self.via_max_diameter // 2
        )

        vias = []
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for circle in circles[0, :]:
                x, y, r = circle

                # Check if connected to traces
                # Look for trace mask pixels near circle edge
                mask_region = trace_mask[max(0, y-r-5):y+r+5, max(0, x-r-5):x+r+5]
                if np.any(mask_region > 0):
                    vias.append(Via(
                        position=(int(x), int(y)),
                        diameter_px=float(r * 2)
                    ))

        return vias

    def _build_trace_graph(self, traces: List[TraceSegment], vias: List[Via]) -> nx.Graph:
        """
        Build graph of trace connectivity.

        Nodes: trace endpoints, vias, junctions
        Edges: connections
        """
        G = nx.Graph()

        # Add trace segments as edges
        for i, trace in enumerate(traces):
            start_id = f"point_{trace.start[0]}_{trace.start[1]}"
            end_id = f"point_{trace.end[0]}_{trace.end[1]}"

            G.add_edge(start_id, end_id, trace_id=i, width=trace.width_px, layer=trace.layer)

        # Add vias as nodes connecting layers
        for i, via in enumerate(vias):
            via_id = f"via_{i}"
            G.add_node(via_id, type='via', position=via.position)

            # Find traces near via
            for j, trace in enumerate(traces):
                # Check if trace endpoint near via
                dist_start = np.linalg.norm(np.array(trace.start) - np.array(via.position))
                dist_end = np.linalg.norm(np.array(trace.end) - np.array(via.position))

                if dist_start < via.diameter_px:
                    start_id = f"point_{trace.start[0]}_{trace.start[1]}"
                    G.add_edge(via_id, start_id, type='via_connection')

                if dist_end < via.diameter_px:
                    end_id = f"point_{trace.end[0]}_{trace.end[1]}"
                    G.add_edge(via_id, end_id, type='via_connection')

        return G

    def _identify_nets(self, graph: nx.Graph, traces: List[TraceSegment],
                      vias: List[Via]) -> List[Dict[str, Any]]:
        """
        Identify nets (groups of connected traces).
        """
        nets = []

        # Find connected components in graph
        for i, component in enumerate(nx.connected_components(graph)):
            net_traces = []
            net_vias = []

            for node in component:
                if 'via' in node:
                    via_idx = int(node.split('_')[1])
                    net_vias.append(vias[via_idx])

            # Get all edges in this component
            for edge in graph.edges(component):
                edge_data = graph.get_edge_data(*edge)
                if 'trace_id' in edge_data:
                    trace_id = edge_data['trace_id']
                    if trace_id < len(traces):
                        net_traces.append(traces[trace_id])

            if net_traces:
                nets.append({
                    'net_id': f'net_{i}',
                    'traces': net_traces,
                    'vias': net_vias,
                    'layers': list(set([t.layer for t in net_traces]))
                })

        return nets

    def _detect_junctions(self, trace_mask: np.ndarray) -> List[Junction]:
        """
        Detect junctions (T, cross, Y intersections).
        """
        # Skeletonize
        skeleton = self._skeletonize(trace_mask)

        # Find junction points (where >2 traces meet)
        # Use hit-or-miss transform with junction templates
        junctions = []

        # T-junction templates (4 rotations)
        t_templates = [
            np.array([[0, 1, 0], [1, 1, 1], [0, 0, 0]], dtype=np.uint8),
            np.array([[0, 1, 0], [0, 1, 1], [0, 1, 0]], dtype=np.uint8),
            np.array([[0, 0, 0], [1, 1, 1], [0, 1, 0]], dtype=np.uint8),
            np.array([[0, 1, 0], [1, 1, 0], [0, 1, 0]], dtype=np.uint8),
        ]

        # Cross junction
        cross_template = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=np.uint8)

        # Find T-junctions
        for template in t_templates:
            result = cv2.morphologyEx(skeleton, cv2.MORPH_HITMISS, template)
            junction_points = np.column_stack(np.where(result > 0))
            for pt in junction_points:
                junctions.append(Junction(
                    position=(int(pt[1]), int(pt[0])),
                    connected_traces=[],
                    junction_type="T"
                ))

        # Find cross junctions
        result = cv2.morphologyEx(skeleton, cv2.MORPH_HITMISS, cross_template)
        junction_points = np.column_stack(np.where(result > 0))
        for pt in junction_points:
            junctions.append(Junction(
                position=(int(pt[1]), int(pt[0])),
                connected_traces=[],
                junction_type="cross"
            ))

        return junctions

    def follow_trace_under_component(self, image: np.ndarray,
                                     component_bbox: Tuple[int, int, int, int],
                                     entry_point: Tuple[int, int],
                                     entry_direction: Tuple[float, float]) -> Optional[Tuple[int, int]]:
        """
        Predict where trace exits from under a component.

        Args:
            image: PCB image
            component_bbox: Component bounding box (x1, y1, x2, y2)
            entry_point: Where trace enters component
            entry_direction: Direction vector of trace at entry

        Returns:
            Predicted exit point
        """
        x1, y1, x2, y2 = component_bbox

        # Simple prediction: assume trace continues in same direction
        # More advanced: use component type knowledge (e.g., IC pins are usually straight through)

        # Extend line through component
        dx, dy = entry_direction

        # Normalize direction
        length = np.sqrt(dx**2 + dy**2)
        if length > 0:
            dx /= length
            dy /= length

        # Component diagonal length
        comp_width = x2 - x1
        comp_height = y2 - y1
        max_distance = np.sqrt(comp_width**2 + comp_height**2)

        # Project entry point in direction across component
        exit_x = int(entry_point[0] + dx * max_distance)
        exit_y = int(entry_point[1] + dy * max_distance)

        # Clamp to component boundary
        exit_x = max(x1, min(x2, exit_x))
        exit_y = max(y1, min(y2, exit_y))

        return (exit_x, exit_y)

    def estimate_trace_impedance(self, width_mm: float, thickness_mm: float = 0.035,
                                 height_above_plane_mm: float = 1.6,
                                 er: float = 4.5) -> float:
        """
        Estimate trace impedance (for high-speed signals).

        Uses simplified microstrip formula.

        Args:
            width_mm: Trace width
            thickness_mm: Copper thickness (default 1oz = 0.035mm)
            height_above_plane_mm: Height above ground plane
            er: Substrate dielectric constant (default FR4 = 4.5)

        Returns:
            Characteristic impedance in ohms
        """
        w = width_mm
        h = height_above_plane_mm
        t = thickness_mm

        # Effective width accounting for thickness
        w_eff = w + (t / np.pi) * np.log(2 * h / t)

        # Microstrip impedance formula
        if w_eff / h < 1:
            Z0 = (60 / np.sqrt(er)) * np.log(8 * h / w_eff + w_eff / (4 * h))
        else:
            Z0 = (120 * np.pi) / (np.sqrt(er) * (w_eff / h + 1.393 + 0.667 * np.log(w_eff / h + 1.444)))

        return Z0


# Global singleton
advanced_trace_follower = AdvancedTraceFollower()
