"""
IPC-2152 Standard Trace Width Calculator

Implements the IPC-2152 standard for PCB trace current capacity calculations.
This replaces the legacy IPC-2221 standard which used 50+ year old data.

IPC-2152 accounts for:
- Temperature rise vs current
- Internal vs external layers
- PCB thickness
- Copper thickness (oz)
- Ambient temperature

References:
- IPC-2152: "Standard for Determining Current Carrying Capacity in Printed Board Design"
- https://www.smps.us/pcb-calculator.html
- https://www.nextpcb.com/blog/pcb-trace-width-calculation-high-current-design-and-thermal-analysis
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
import math


@dataclass(frozen=True)
class IPC2152Result:
    """Result from IPC-2152 trace width calculation"""
    required_width_mm: float
    current_a: float
    temp_rise_c: float
    copper_oz: float
    layer_type: str
    cross_sectional_area_mm2: float
    current_density_a_per_mm2: float
    method: str  # "IPC-2152" or "simple_ohms_law"

    def __str__(self):
        return (
            f"IPC-2152 Calculation ({self.method}):\n"
            f"  Required Width: {self.required_width_mm:.3f}mm\n"
            f"  Current: {self.current_a:.3f}A\n"
            f"  Temp Rise: {self.temp_rise_c:.1f}°C\n"
            f"  Copper: {self.copper_oz}oz\n"
            f"  Layer: {self.layer_type}\n"
            f"  Current Density: {self.current_density_a_per_mm2:.2f}A/mm²"
        )


def calculate_trace_width_ipc2152(
    current_a: float,
    temp_rise_c: float = 10.0,
    copper_oz: float = 1.0,
    layer_type: Literal["external", "internal"] = "external",
    ambient_temp_c: float = 25.0,
) -> IPC2152Result:
    """
    Calculate required trace width using IPC-2152 standard.

    Args:
        current_a: Current in amperes
        temp_rise_c: Allowable temperature rise above ambient (default: 10°C)
        copper_oz: Copper weight in ounces (default: 1oz = 35µm)
        layer_type: "external" (outer layers) or "internal" (inner layers)
        ambient_temp_c: Ambient temperature (default: 25°C)

    Returns:
        IPC2152Result with required width and details

    Notes:
        - External layers have better thermal dissipation (exposed to air)
        - Internal layers trap heat (worse thermal performance)
        - Standard temp rise: 10°C (conservative), 20°C (moderate), 30°C (aggressive)
    """

    if current_a <= 0:
        raise ValueError("Current must be positive")
    if temp_rise_c <= 0:
        raise ValueError("Temperature rise must be positive")
    if copper_oz <= 0:
        raise ValueError("Copper weight must be positive")

    # IPC-2152 formula (from SMPS.US calculator - empirically fit to IPC-2152 charts)
    # This is a curve-fitted approximation of Figure 5-2 in IPC-2152
    # Source: http://www.smps.us/pcb-calculator.html (Jack Olson, Caterpillar)
    #
    # Formula: Ac (sq.mil) = (117.555 × ΔT^(-0.913) + 1.15) × i^(0.84×ΔT^(-0.108) + 1.159)
    # Where:
    #   Ac = cross-sectional area in square mils
    #   i = RMS current in amperes
    #   ΔT = temperature rise in °C

    # Calculate the exponent term first
    exponent = 0.84 * (temp_rise_c ** -0.108) + 1.159

    # Calculate the multiplier term
    multiplier = 117.555 * (temp_rise_c ** -0.913) + 1.15

    # Calculate cross-sectional area in square mils
    area_mil2 = multiplier * (current_a ** exponent)

    # Internal layers have worse thermal dissipation
    # IPC-2152 charts show internal layers need ~2x the area
    if layer_type == "internal":
        area_mil2 *= 2.0

    # Convert mil² to mm²
    # 1 mil = 0.0254 mm, so 1 mil² = 0.00064516 mm²
    area_mm2 = area_mil2 * 0.00064516

    # Convert copper oz to thickness in mm
    # 1 oz = 35µm = 0.035mm (approximately)
    thickness_mm = 0.035 * copper_oz

    # Width = Area / Thickness
    width_mm = area_mm2 / thickness_mm

    # Current density (useful for validation)
    current_density = current_a / area_mm2

    return IPC2152Result(
        required_width_mm=width_mm,
        current_a=current_a,
        temp_rise_c=temp_rise_c,
        copper_oz=copper_oz,
        layer_type=layer_type,
        cross_sectional_area_mm2=area_mm2,
        current_density_a_per_mm2=current_density,
        method="IPC-2152"
    )


def calculate_trace_width_simple(
    current_a: float,
    max_voltage_drop_v: float,
    trace_length_m: float,
    copper_oz: float = 1.0,
) -> IPC2152Result:
    """
    Simple trace width calculation using Ohm's law (legacy method).

    This is the method currently used in power_tree_validator.py.
    Kept for backwards compatibility and simple voltage drop calculations.

    Args:
        current_a: Current in amperes
        max_voltage_drop_v: Maximum allowable voltage drop
        trace_length_m: Trace length in meters
        copper_oz: Copper weight in ounces

    Returns:
        IPC2152Result (marked as "simple_ohms_law" method)
    """

    if current_a <= 0 or max_voltage_drop_v <= 0 or trace_length_m <= 0:
        raise ValueError("All parameters must be positive")

    # Copper resistivity at 20°C (ohm·m)
    rho = 1.724e-8

    # Thickness in meters
    thickness_m = 35e-6 * copper_oz

    # R_target = V_drop / I
    # R = ρL/(wt) → w = ρL/(R*t)
    r_target = max_voltage_drop_v / current_a
    width_m = (rho * trace_length_m) / (r_target * thickness_m)
    width_mm = width_m * 1000

    # Approximate temp rise (not accurate without IPC-2152)
    area_mm2 = width_mm * (thickness_m * 1000)
    current_density = current_a / max(area_mm2, 0.001)

    return IPC2152Result(
        required_width_mm=width_mm,
        current_a=current_a,
        temp_rise_c=0.0,  # Unknown without thermal model
        copper_oz=copper_oz,
        layer_type="unknown",
        cross_sectional_area_mm2=area_mm2,
        current_density_a_per_mm2=current_density,
        method="simple_ohms_law"
    )


def calculate_max_current_for_width(
    width_mm: float,
    temp_rise_c: float = 10.0,
    copper_oz: float = 1.0,
    layer_type: Literal["external", "internal"] = "external",
) -> float:
    """
    Calculate maximum current for a given trace width (inverse calculation).

    Uses IPC-2152 formula solved for current.

    Args:
        width_mm: Trace width in millimeters
        temp_rise_c: Allowable temperature rise
        copper_oz: Copper weight in ounces
        layer_type: "external" or "internal"

    Returns:
        Maximum current in amperes
    """

    # Thickness
    thickness_mm = 0.035 * copper_oz

    # Cross-sectional area in mm²
    area_mm2 = width_mm * thickness_mm

    # Convert to mil²
    area_mil2 = area_mm2 / 0.00064516

    # Adjust for internal layers
    if layer_type == "internal":
        area_mil2 /= 2.0

    # IPC-2152 formula:
    # Ac = (117.555 × ΔT^(-0.913) + 1.15) × i^(0.84×ΔT^(-0.108) + 1.159)
    # Solve for i:
    # i = (Ac / (117.555 × ΔT^(-0.913) + 1.15))^(1 / (0.84×ΔT^(-0.108) + 1.159))

    exponent = 0.84 * (temp_rise_c ** -0.108) + 1.159
    multiplier = 117.555 * (temp_rise_c ** -0.913) + 1.15

    max_current = (area_mil2 / multiplier) ** (1.0 / exponent)

    return max_current


# Validation functions

def validate_trace_design(
    current_a: float,
    width_mm: float,
    copper_oz: float = 1.0,
    layer_type: Literal["external", "internal"] = "external",
    max_temp_rise_c: float = 20.0,
) -> tuple[bool, str]:
    """
    Validate if a trace design is adequate for the given current.

    Returns:
        (is_valid, message)
    """

    max_current = calculate_max_current_for_width(
        width_mm, max_temp_rise_c, copper_oz, layer_type
    )

    if current_a <= max_current:
        margin = ((max_current - current_a) / current_a) * 100
        return True, f"✓ Trace OK: {current_a:.2f}A < {max_current:.2f}A max ({margin:.1f}% margin)"
    else:
        required = calculate_trace_width_ipc2152(
            current_a, max_temp_rise_c, copper_oz, layer_type
        )
        return False, f"✗ Trace too thin: {current_a:.2f}A > {max_current:.2f}A max. Need {required.required_width_mm:.2f}mm (current: {width_mm:.2f}mm)"


# Comparison function

def compare_ipc2152_vs_simple(
    current_a: float,
    voltage_drop_v: float = 0.25,
    trace_length_m: float = 0.05,
    temp_rise_c: float = 10.0,
    copper_oz: float = 1.0,
    layer_type: Literal["external", "internal"] = "external",
) -> dict:
    """
    Compare IPC-2152 vs simple Ohm's law calculation.

    Useful for understanding the difference between methods.
    """

    ipc_result = calculate_trace_width_ipc2152(
        current_a, temp_rise_c, copper_oz, layer_type
    )

    simple_result = calculate_trace_width_simple(
        current_a, voltage_drop_v, trace_length_m, copper_oz
    )

    diff_pct = ((ipc_result.required_width_mm - simple_result.required_width_mm)
                / simple_result.required_width_mm * 100)

    return {
        "ipc2152": ipc_result,
        "simple": simple_result,
        "difference_mm": ipc_result.required_width_mm - simple_result.required_width_mm,
        "difference_pct": diff_pct,
        "recommendation": (
            "Use IPC-2152 for thermal-critical designs. "
            f"IPC-2152 is {abs(diff_pct):.1f}% {'more conservative' if diff_pct > 0 else 'less conservative'} than simple calculation."
        )
    }


if __name__ == "__main__":
    # Demo: Calculate required width for 2A at 10°C rise
    print("=== IPC-2152 Trace Width Calculator Demo ===\n")

    # Example 1: External layer, 2A, 10°C rise
    result = calculate_trace_width_ipc2152(
        current_a=2.0,
        temp_rise_c=10.0,
        copper_oz=1.0,
        layer_type="external"
    )
    print("Example 1: External layer, 2A, 10°C rise")
    print(result)
    print()

    # Example 2: Internal layer (needs wider trace!)
    result_internal = calculate_trace_width_ipc2152(
        current_a=2.0,
        temp_rise_c=10.0,
        copper_oz=1.0,
        layer_type="internal"
    )
    print("Example 2: Internal layer, 2A, 10°C rise")
    print(result_internal)
    print(f"Internal layer needs {result_internal.required_width_mm / result.required_width_mm:.1f}x wider trace!")
    print()

    # Example 3: Compare methods
    print("Example 3: IPC-2152 vs Simple Ohm's Law")
    comparison = compare_ipc2152_vs_simple(
        current_a=1.5,
        voltage_drop_v=0.25,
        trace_length_m=0.05,  # 50mm trace
        temp_rise_c=10.0,
        copper_oz=1.0,
        layer_type="external"
    )
    print(f"IPC-2152:  {comparison['ipc2152'].required_width_mm:.3f}mm")
    print(f"Simple:    {comparison['simple'].required_width_mm:.3f}mm")
    print(f"Difference: {comparison['difference_pct']:.1f}%")
    print(comparison['recommendation'])
    print()

    # Example 4: Validation
    print("Example 4: Validate existing trace design")
    is_valid, msg = validate_trace_design(
        current_a=1.5,
        width_mm=1.0,
        copper_oz=1.0,
        layer_type="external",
        max_temp_rise_c=20.0
    )
    print(msg)
