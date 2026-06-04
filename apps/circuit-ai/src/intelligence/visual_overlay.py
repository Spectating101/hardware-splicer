"""
Visual Overlay System

Draws visual guidance on PCB images:
- "Cut trace here ✂️"
- "Desolder this component"
- "Measure voltage here 🔍"
- "Solder bridge here"
- Highlight traces
- Show probe points

This makes repair instructions visual and easy to follow.
"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from intelligence.pin_detector import ICDetectionResult, DetectedPin
from intelligence.connection_mapper import CircuitSchematic, PinConnection


class OverlayType(Enum):
    """Types of visual overlays."""
    CUT_TRACE = "cut_trace"
    DESOLDER_PIN = "desolder_pin"
    MEASURE_POINT = "measure_point"
    SOLDER_BRIDGE = "solder_bridge"
    HIGHLIGHT_COMPONENT = "highlight_component"
    HIGHLIGHT_TRACE = "highlight_trace"
    WARNING = "warning"
    INFO = "info"


@dataclass
class VisualOverlay:
    """A single visual overlay element."""
    overlay_type: OverlayType
    position: Tuple[int, int]  # (x, y) center
    label: str
    color: Tuple[int, int, int]  # BGR
    secondary_position: Optional[Tuple[int, int]] = None  # For lines, bridges
    bbox: Optional[Tuple[int, int, int, int]] = None  # For component highlights


class VisualOverlayRenderer:
    """Renders visual overlays on PCB images."""

    def __init__(self):
        # Color scheme (BGR format for OpenCV)
        self.colors = {
            'cut': (0, 0, 255),  # Red
            'desolder': (0, 140, 255),  # Orange
            'measure': (255, 255, 0),  # Cyan
            'bridge': (0, 255, 0),  # Green
            'highlight': (255, 0, 255),  # Magenta
            'warning': (0, 0, 255),  # Red
            'info': (255, 255, 255)  # White
        }

        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale = 0.5
        self.font_thickness = 2
        self.line_thickness = 3
        self.marker_size = 15

    def render_all_overlays(self, image: np.ndarray, overlays: List[VisualOverlay]) -> np.ndarray:
        """
        Render all overlays on image.

        Args:
            image: PCB image (will be copied, not modified)
            overlays: List of overlays to render

        Returns:
            Image with overlays drawn
        """
        result = image.copy()

        # Sort overlays: highlights first, then markers, then labels
        sorted_overlays = sorted(overlays, key=lambda o: (
            0 if o.overlay_type == OverlayType.HIGHLIGHT_TRACE else
            1 if o.overlay_type == OverlayType.HIGHLIGHT_COMPONENT else
            2
        ))

        for overlay in sorted_overlays:
            result = self._render_single_overlay(result, overlay)

        return result

    def _render_single_overlay(self, image: np.ndarray, overlay: VisualOverlay) -> np.ndarray:
        """Render a single overlay."""
        if overlay.overlay_type == OverlayType.CUT_TRACE:
            return self._render_cut_marker(image, overlay)
        elif overlay.overlay_type == OverlayType.DESOLDER_PIN:
            return self._render_desolder_marker(image, overlay)
        elif overlay.overlay_type == OverlayType.MEASURE_POINT:
            return self._render_measure_marker(image, overlay)
        elif overlay.overlay_type == OverlayType.SOLDER_BRIDGE:
            return self._render_bridge_marker(image, overlay)
        elif overlay.overlay_type == OverlayType.HIGHLIGHT_COMPONENT:
            return self._render_component_highlight(image, overlay)
        elif overlay.overlay_type == OverlayType.HIGHLIGHT_TRACE:
            return self._render_trace_highlight(image, overlay)
        elif overlay.overlay_type in [OverlayType.WARNING, OverlayType.INFO]:
            return self._render_text_label(image, overlay)
        else:
            return image

    def _render_cut_marker(self, image: np.ndarray, overlay: VisualOverlay) -> np.ndarray:
        """Draw scissors icon and "CUT HERE" label."""
        x, y = overlay.position
        color = overlay.color

        # Draw X marker
        size = self.marker_size
        cv2.line(image, (x - size, y - size), (x + size, y + size), color, self.line_thickness)
        cv2.line(image, (x - size, y + size), (x + size, y - size), color, self.line_thickness)

        # Draw circle around it
        cv2.circle(image, (x, y), size + 5, color, 2)

        # Add label
        label = f"CUT: {overlay.label}"
        self._add_label(image, (x, y - 30), label, color)

        # If there's a line to cut along, draw it
        if overlay.secondary_position:
            x2, y2 = overlay.secondary_position
            # Draw dashed line showing cut path
            self._draw_dashed_line(image, (x, y), (x2, y2), color, 2)

        return image

    def _render_desolder_marker(self, image: np.ndarray, overlay: VisualOverlay) -> np.ndarray:
        """Draw desolder marker (circle with target)."""
        x, y = overlay.position
        color = overlay.color

        # Draw target circles
        cv2.circle(image, (x, y), 10, color, 2)
        cv2.circle(image, (x, y), 15, color, 2)

        # Draw crosshair
        cv2.line(image, (x - 20, y), (x + 20, y), color, 1)
        cv2.line(image, (x, y - 20), (x, y + 20), color, 1)

        # Add label
        label = f"DESOLDER: {overlay.label}"
        self._add_label(image, (x, y - 30), label, color)

        return image

    def _render_measure_marker(self, image: np.ndarray, overlay: VisualOverlay) -> np.ndarray:
        """Draw measurement point marker (probe tip icon)."""
        x, y = overlay.position
        color = overlay.color

        # Draw probe tip (triangle pointing down to measurement point)
        pts = np.array([
            [x, y],  # Point
            [x - 10, y - 20],  # Left
            [x + 10, y - 20]  # Right
        ], np.int32)
        cv2.polylines(image, [pts], True, color, 2)

        # Draw circle at tip
        cv2.circle(image, (x, y), 5, color, -1)

        # Add label
        label = f"MEASURE: {overlay.label}"
        self._add_label(image, (x, y - 40), label, color)

        return image

    def _render_bridge_marker(self, image: np.ndarray, overlay: VisualOverlay) -> np.ndarray:
        """Draw solder bridge instruction (line between two points)."""
        if not overlay.secondary_position:
            return image

        x1, y1 = overlay.position
        x2, y2 = overlay.secondary_position
        color = overlay.color

        # Draw thick line showing bridge path
        cv2.line(image, (x1, y1), (x2, y2), color, self.line_thickness)

        # Draw circles at endpoints
        cv2.circle(image, (x1, y1), 8, color, -1)
        cv2.circle(image, (x2, y2), 8, color, -1)

        # Add label at midpoint
        mid_x = (x1 + x2) // 2
        mid_y = (y1 + y2) // 2
        label = f"BRIDGE: {overlay.label}"
        self._add_label(image, (mid_x, mid_y - 20), label, color)

        return image

    def _render_component_highlight(self, image: np.ndarray, overlay: VisualOverlay) -> np.ndarray:
        """Highlight a component with bounding box."""
        if not overlay.bbox:
            return image

        x1, y1, x2, y2 = overlay.bbox
        color = overlay.color

        # Draw thick rectangle
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)

        # Add semi-transparent overlay
        overlay_img = image.copy()
        cv2.rectangle(overlay_img, (x1, y1), (x2, y2), color, -1)
        cv2.addWeighted(overlay_img, 0.2, image, 0.8, 0, image)

        # Add label
        self._add_label(image, (x1, y1 - 10), overlay.label, color)

        return image

    def _render_trace_highlight(self, image: np.ndarray, overlay: VisualOverlay) -> np.ndarray:
        """Highlight a trace."""
        if not overlay.secondary_position:
            return image

        x1, y1 = overlay.position
        x2, y2 = overlay.secondary_position
        color = overlay.color

        # Draw thick highlighted line
        cv2.line(image, (x1, y1), (x2, y2), color, self.line_thickness + 2)

        return image

    def _render_text_label(self, image: np.ndarray, overlay: VisualOverlay) -> np.ndarray:
        """Render text label (warning or info)."""
        self._add_label(image, overlay.position, overlay.label, overlay.color)
        return image

    def _add_label(self, image: np.ndarray, position: Tuple[int, int],
                  text: str, color: Tuple[int, int, int]):
        """Add text label with background."""
        x, y = position

        # Get text size
        (text_width, text_height), baseline = cv2.getTextSize(
            text, self.font, self.font_scale, self.font_thickness
        )

        # Draw background rectangle
        padding = 5
        cv2.rectangle(
            image,
            (x - padding, y - text_height - padding),
            (x + text_width + padding, y + baseline + padding),
            (0, 0, 0),  # Black background
            -1
        )

        # Draw text
        cv2.putText(
            image, text, (x, y),
            self.font, self.font_scale, color,
            self.font_thickness, cv2.LINE_AA
        )

    def _draw_dashed_line(self, image: np.ndarray, pt1: Tuple[int, int],
                         pt2: Tuple[int, int], color: Tuple[int, int, int],
                         thickness: int = 2, dash_length: int = 10):
        """Draw a dashed line."""
        x1, y1 = pt1
        x2, y2 = pt2

        # Calculate line length and angle
        dist = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        dashes = int(dist / dash_length)

        for i in range(dashes):
            if i % 2 == 0:  # Draw every other segment
                start_x = int(x1 + (x2 - x1) * i / dashes)
                start_y = int(y1 + (y2 - y1) * i / dashes)
                end_x = int(x1 + (x2 - x1) * (i + 1) / dashes)
                end_y = int(y1 + (y2 - y1) * (i + 1) / dashes)
                cv2.line(image, (start_x, start_y), (end_x, end_y), color, thickness)

    def create_cut_trace_overlay(self, connection: PinConnection, label: Optional[str] = None) -> VisualOverlay:
        """Create overlay for cutting a trace."""
        # Midpoint of trace
        mid_x = (connection.ic1_position[0] + connection.ic2_position[0]) // 2
        mid_y = (connection.ic1_position[1] + connection.ic2_position[1]) // 2

        if label is None:
            label = f"{connection.ic1_part} pin{connection.ic1_pin_number} to {connection.ic2_part} pin{connection.ic2_pin_number}"

        return VisualOverlay(
            overlay_type=OverlayType.CUT_TRACE,
            position=(mid_x, mid_y),
            secondary_position=None,  # Could add cut line direction
            label=label,
            color=self.colors['cut']
        )

    def create_desolder_pin_overlay(self, ic: ICDetectionResult, pin_number: int,
                                    label: Optional[str] = None) -> Optional[VisualOverlay]:
        """Create overlay for desoldering a pin."""
        # Find pin position
        pin = None
        for p in ic.pins:
            if p.pin_number == pin_number:
                pin = p
                break

        if not pin:
            return None

        if label is None:
            label = f"pin {pin_number} of {ic.part_number}"

        return VisualOverlay(
            overlay_type=OverlayType.DESOLDER_PIN,
            position=pin.position,
            label=label,
            color=self.colors['desolder']
        )

    def create_measure_point_overlay(self, ic: ICDetectionResult, pin_number: int,
                                     expected_voltage: Optional[float] = None) -> Optional[VisualOverlay]:
        """Create overlay for measuring voltage at a pin."""
        # Find pin position
        pin = None
        for p in ic.pins:
            if p.pin_number == pin_number:
                pin = p
                break

        if not pin:
            return None

        label = f"pin {pin_number} of {ic.part_number}"
        if expected_voltage is not None:
            label += f" (expect {expected_voltage}V)"

        return VisualOverlay(
            overlay_type=OverlayType.MEASURE_POINT,
            position=pin.position,
            label=label,
            color=self.colors['measure']
        )

    def create_solder_bridge_overlay(self, ic: ICDetectionResult, pin1_number: int,
                                     pin2_number: int, label: Optional[str] = None) -> Optional[VisualOverlay]:
        """Create overlay for bridging two pins."""
        # Find pin positions
        pin1 = None
        pin2 = None
        for p in ic.pins:
            if p.pin_number == pin1_number:
                pin1 = p
            if p.pin_number == pin2_number:
                pin2 = p

        if not pin1 or not pin2:
            return None

        if label is None:
            label = f"pin {pin1_number} to pin {pin2_number}"

        return VisualOverlay(
            overlay_type=OverlayType.SOLDER_BRIDGE,
            position=pin1.position,
            secondary_position=pin2.position,
            label=label,
            color=self.colors['bridge']
        )

    def create_component_highlight_overlay(self, ic: ICDetectionResult,
                                          label: Optional[str] = None) -> VisualOverlay:
        """Create overlay for highlighting a component."""
        if label is None:
            label = ic.part_number

        return VisualOverlay(
            overlay_type=OverlayType.HIGHLIGHT_COMPONENT,
            position=(ic.bbox[0], ic.bbox[1]),
            bbox=ic.bbox,
            label=label,
            color=self.colors['highlight']
        )

    def create_trace_highlight_overlay(self, connection: PinConnection,
                                       label: Optional[str] = None) -> VisualOverlay:
        """Create overlay for highlighting a trace."""
        if label is None:
            label = f"{connection.ic1_pin_name} → {connection.ic2_pin_name}"

        return VisualOverlay(
            overlay_type=OverlayType.HIGHLIGHT_TRACE,
            position=connection.ic1_position,
            secondary_position=connection.ic2_position,
            label=label,
            color=self.colors['highlight']
        )

    def create_repair_sequence_overlays(self, image: np.ndarray, schematic: CircuitSchematic,
                                        repair_steps: List[Dict[str, Any]]) -> List[np.ndarray]:
        """
        Create a sequence of images, one for each repair step.

        Args:
            image: Base PCB image
            schematic: Circuit schematic
            repair_steps: List of repair step dicts with:
                {
                    'type': 'cut_trace' | 'desolder' | 'measure' | 'bridge',
                    'ic_name': str,
                    'pin1': int,
                    'pin2': Optional[int],
                    'label': str
                }

        Returns:
            List of images, one per step with cumulative overlays
        """
        sequence = []
        overlays = []

        for i, step in enumerate(repair_steps):
            step_type = step.get('type')
            ic_name = step.get('ic_name')
            pin1 = step.get('pin1')
            pin2 = step.get('pin2')
            label = step.get('label', f"Step {i+1}")

            # Find IC
            ic = None
            for ic_det in schematic.ics:
                if ic_det.part_number == ic_name:
                    ic = ic_det
                    break

            if not ic:
                continue

            # Create overlay for this step
            if step_type == 'desolder' and pin1:
                overlay = self.create_desolder_pin_overlay(ic, pin1, label)
            elif step_type == 'measure' and pin1:
                expected_v = step.get('expected_voltage')
                overlay = self.create_measure_point_overlay(ic, pin1, expected_v)
            elif step_type == 'bridge' and pin1 and pin2:
                overlay = self.create_solder_bridge_overlay(ic, pin1, pin2, label)
            elif step_type == 'cut_trace':
                # Find connection
                conn = None
                for c in schematic.connections:
                    if ((c.ic1_part == ic_name and c.ic1_pin_number == pin1 and
                         c.ic2_pin_number == pin2) or
                        (c.ic2_part == ic_name and c.ic2_pin_number == pin1 and
                         c.ic1_pin_number == pin2)):
                        conn = c
                        break
                if conn:
                    overlay = self.create_cut_trace_overlay(conn, label)
                else:
                    overlay = None
            else:
                overlay = None

            if overlay:
                overlays.append(overlay)

            # Render image with all overlays up to this point
            step_image = self.render_all_overlays(image, overlays)

            # Add step counter
            self._add_label(step_image, (20, 30), f"Step {i+1}/{len(repair_steps)}: {label}",
                          self.colors['info'])

            sequence.append(step_image)

        return sequence


# Global singleton
visual_overlay_renderer = VisualOverlayRenderer()
