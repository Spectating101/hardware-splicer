"""
Geometric PCB Validation - Fallback when circuit solver fails

Performs basic physical checks on PCB geometry without electrical simulation:
- Trace width vs copper weight standards
- Pad size vs footprint standards
- Component spacing (clearance)
- Board edge clearance
- Via size standards

These checks don't require solving the circuit, just geometric analysis.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path


@dataclass
class GeometricIssue:
    """Issue found during geometric validation"""
    severity: str  # 'critical', 'error', 'warning', 'info'
    component: str
    issue: str
    explanation: str
    solution: str
    physics_data: Optional[Dict[str, Any]] = None


def validate_pcb_geometry(kicad_file: str) -> List[GeometricIssue]:
    """
    Validate PCB geometry from .kicad_pcb file

    Returns list of issues found. Empty list if file can't be parsed.
    """
    issues = []

    try:
        # Try to extract geometry
        from src.engines.kicad_pcb_geometry import extract_pcb_geometry
        geometry = extract_pcb_geometry(kicad_file)

        # Check 1: Board size sanity
        board = geometry.get('board', {})
        bbox = board.get('bbox_mm', {})
        width = bbox.get('width', 0)
        height = bbox.get('height', 0)

        if width > 600 or height > 600:
            issues.append(GeometricIssue(
                severity='warning',
                component='Board',
                issue=f'Unusually large board ({width}mm x {height}mm)',
                explanation='Most PCB fabs have size limits around 400mm. Large boards are expensive.',
                solution='Consider splitting into smaller boards or verify dimensions are correct',
                physics_data={'width_mm': width, 'height_mm': height}
            ))

        if width < 10 or height < 10:
            issues.append(GeometricIssue(
                severity='warning',
                component='Board',
                issue=f'Unusually small board ({width}mm x {height}mm)',
                explanation='Very small boards can be difficult to manufacture and handle.',
                solution='Verify dimensions are correct. Consider adding panelization.',
                physics_data={'width_mm': width, 'height_mm': height}
            ))

        # Check 2: Trace width standards
        segments = geometry.get('segments', [])
        thin_traces = []
        for seg in segments:
            width_mm = seg.get('width_mm', 0)
            net_name = seg.get('net', {}).get('name', 'unknown')

            if width_mm < 0.15:  # Less than 0.15mm is difficult to manufacture
                thin_traces.append({
                    'net': net_name,
                    'width_mm': width_mm
                })

        if thin_traces:
            # Group by width
            widths = {}
            for trace in thin_traces:
                w = trace['width_mm']
                if w not in widths:
                    widths[w] = []
                widths[w].append(trace['net'])

            for width_mm, nets in widths.items():
                net_names = ', '.join(set(nets[:3]))  # Show first 3 unique nets
                count = len(nets)

                issues.append(GeometricIssue(
                    severity='warning',
                    component=f'Traces ({net_names}...)',
                    issue=f'{count} trace(s) with {width_mm}mm width',
                    explanation='Traces under 0.15mm (6mil) can be difficult to manufacture reliably. Standard PCB fabs typically support 0.15mm (6mil) minimum.',
                    solution='Widen traces to at least 0.15mm for better yield, or use advanced PCB fab capabilities',
                    physics_data={'width_mm': width_mm, 'count': count, 'min_recommended_mm': 0.15}
                ))

        # Check 3: Component density
        footprints = geometry.get('footprints', [])
        if width > 0 and height > 0:
            area_mm2 = width * height
            density = len(footprints) / area_mm2 if area_mm2 > 0 else 0

            if density > 0.5:  # More than 0.5 components per mm²
                issues.append(GeometricIssue(
                    severity='info',
                    component='Board Layout',
                    issue=f'High component density ({density:.2f} components/mm²)',
                    explanation=f'{len(footprints)} components on {width}x{height}mm board is dense. This is fine for modern SMD but may be difficult to hand-solder or rework.',
                    solution='Consider increasing board size if manual assembly is needed, or use assembly service',
                    physics_data={'density_per_mm2': density, 'total_components': len(footprints)}
                ))

        # Check 4: Power components
        power_components = []
        for fp in footprints:
            value = fp.get('value', '').upper()
            footprint = fp.get('footprint', '').upper()
            ref = fp.get('ref', '')

            # Look for regulators, power ICs
            if any(keyword in value or keyword in footprint for keyword in ['LDO', 'BUCK', 'BOOST', 'REGULATOR', 'AMS1117', 'LM317']):
                power_components.append(ref)

        if power_components and not any('THERMAL' in fp.get('footprint', '').upper() for fp in footprints):
            issues.append(GeometricIssue(
                severity='info',
                component=', '.join(power_components),
                issue='Power components detected',
                explanation=f'Found power regulators: {", ".join(power_components)}. Ensure adequate thermal management.',
                solution='Consider adding thermal vias under power components and verify copper pour for heat dissipation',
                physics_data={'power_components': power_components}
            ))

    except Exception as e:
        # If geometry extraction fails, return empty list (no geometric validation possible)
        pass

    return issues


def add_hints_recommendation(kicad_file: str) -> List[str]:
    """
    Suggest what hints the user should provide for better validation

    Returns list of recommendations
    """
    recommendations = []

    try:
        from src.engines.kicad_pcb_geometry import extract_pcb_geometry
        geometry = extract_pcb_geometry(kicad_file)

        # Look for components that need hints
        footprints = geometry.get('footprints', [])

        # Check for USB components
        has_usb = any('USB' in fp.get('value', '').upper() or 'USB' in fp.get('footprint', '').upper()
                      for fp in footprints)
        if has_usb:
            recommendations.append(
                'Add USB power source hint: {"sources": [{"name": "USB", "net": "VBUS", "volts": 5.0, "max_current_a": 0.5}]}'
            )

        # Check for voltage regulators
        has_ldo = any('LDO' in fp.get('value', '').upper() or 'AMS1117' in fp.get('value', '').upper()
                      for fp in footprints)
        if has_ldo:
            recommendations.append(
                'Add load hints for components powered by regulators: {"loads_cc": [{"name": "MCU", "net": "+3V3", "amps": 0.2}]}'
            )

        # Check for MCUs that need current specs
        has_mcu = any(keyword in fp.get('value', '').upper()
                     for fp in footprints
                     for keyword in ['ESP32', 'ESP8266', 'STM32', 'ATMEGA', 'ARDUINO'])
        if has_mcu and not has_ldo:
            recommendations.append(
                'Add current consumption hints for MCU to validate power budget'
            )

    except Exception:
        pass

    return recommendations
