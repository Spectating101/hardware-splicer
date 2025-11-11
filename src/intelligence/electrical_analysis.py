"""
Electrical Analysis - Circuit Calculations & Behavior Prediction

Pure electrical engineering calculations based on component detection:
- Voltage/current/power calculations
- Thermal analysis
- Signal analysis
- Power budget estimation
- Circuit behavior prediction
"""

import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PowerBudget:
    """Power budget analysis for a circuit."""
    total_power_w: float
    components: Dict[str, float]  # component -> power consumption
    voltage_rails: Dict[str, float]  # rail voltage -> current draw
    thermal_estimate_c: float
    power_source_adequate: bool
    recommendations: List[str]


@dataclass
class VoltageRail:
    """Voltage rail in the circuit."""
    voltage: float
    current_capacity_a: float
    current_draw_a: float
    margin_percent: float
    components_powered: List[str]
    safe_to_tap: bool


@dataclass
class SignalPath:
    """Signal path analysis."""
    source: str
    destination: str
    signal_type: str  # digital, analog, power, rf
    frequency_estimate_hz: Optional[float]
    voltage_levels: List[float]
    impedance_estimate_ohm: Optional[float]


class ElectricalAnalyzer:
    """Analyzes electrical characteristics of circuits."""

    def __init__(self):
        # Standard voltage rails
        self.common_rails = {
            5.0: "USB/Arduino",
            3.3: "ESP/Modern Logic",
            12.0: "Traditional Power",
            24.0: "Industrial",
            48.0: "PoE"
        }

    def analyze_power_budget(self, components: List[str]) -> PowerBudget:
        """
        Calculate power budget for detected components.

        This is pure electrical calculation - no ML needed.
        """
        from src.intelligence.component_knowledge import estimate_power_consumption

        total_power = 0.0
        component_power = {}
        voltage_rails = {}

        for comp in components:
            power_info = estimate_power_consumption(comp)
            power_w = power_info["power_w"]

            total_power += power_w
            component_power[comp] = power_w

            # Track by voltage rail
            voltage = power_info["voltage_v"]
            if voltage > 0:
                if voltage not in voltage_rails:
                    voltage_rails[voltage] = 0
                voltage_rails[voltage] += power_info["current_a"]

        # Thermal estimate (rough)
        thermal_estimate = 25 + (total_power * 10)  # 10°C per watt rule of thumb

        # Check if power source is adequate
        power_adequate = total_power < 10.0  # Most PCBs < 10W

        # Recommendations
        recommendations = []
        if total_power > 5.0:
            recommendations.append("Consider active cooling for power components")
        if thermal_estimate > 50:
            recommendations.append(f"High thermal estimate ({thermal_estimate:.1f}°C) - check component ratings")
        if not power_adequate:
            recommendations.append("Power consumption high - verify power supply capacity")

        for voltage, current in voltage_rails.items():
            if current > 1.0:
                recommendations.append(f"{voltage}V rail draws {current:.2f}A - ensure adequate supply")

        return PowerBudget(
            total_power_w=total_power,
            components=component_power,
            voltage_rails=voltage_rails,
            thermal_estimate_c=thermal_estimate,
            power_source_adequate=power_adequate,
            recommendations=recommendations
        )

    def analyze_voltage_rails(self, components: List[str], regulator_info: Dict) -> List[VoltageRail]:
        """
        Analyze voltage rails in the circuit.

        Determines what voltages are present and safe to tap.
        """
        from src.intelligence.component_knowledge import estimate_power_consumption

        rails = []

        # Common rails to check for
        rail_voltages = [5.0, 3.3, 12.0]

        for voltage in rail_voltages:
            current_draw = 0.0
            powered_components = []

            # Find components on this rail
            for comp in components:
                power_info = estimate_power_consumption(comp)
                if abs(power_info["voltage_v"] - voltage) < 0.5:  # Tolerance
                    current_draw += power_info["current_a"]
                    powered_components.append(comp)

            if powered_components:
                # Estimate regulator capacity (typical values)
                capacity_map = {5.0: 1.5, 3.3: 1.0, 12.0: 1.0}
                capacity = capacity_map.get(voltage, 1.0)

                margin = ((capacity - current_draw) / capacity) * 100 if capacity > 0 else 0

                # Safe to tap if margin > 30%
                safe_to_tap = margin > 30 and current_draw < capacity * 0.7

                rails.append(VoltageRail(
                    voltage=voltage,
                    current_capacity_a=capacity,
                    current_draw_a=current_draw,
                    margin_percent=margin,
                    components_powered=powered_components,
                    safe_to_tap=safe_to_tap
                ))

        return rails

    def calculate_led_current_limiting_resistor(self, supply_v: float, led_vf: float = 2.0,
                                                 led_current_a: float = 0.020) -> Dict[str, Any]:
        """
        Calculate LED current limiting resistor.

        Classic electronics calculation: R = (Vs - Vf) / I
        """
        if supply_v <= led_vf:
            return {
                "error": "Supply voltage too low for LED",
                "resistor_ohm": None,
                "power_w": None
            }

        resistor_ohm = (supply_v - led_vf) / led_current_a
        power_w = (supply_v - led_vf) * led_current_a

        # Standard resistor values (E12 series)
        standard_values = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82, 100, 120, 150,
                          180, 220, 270, 330, 390, 470, 560, 680, 820, 1000]

        # Find nearest standard value
        nearest = min(standard_values, key=lambda x: abs(x - resistor_ohm))

        return {
            "calculated_resistor_ohm": resistor_ohm,
            "standard_resistor_ohm": nearest,
            "power_dissipation_w": power_w,
            "recommended_rating_w": 0.25 if power_w < 0.125 else 0.5,
            "actual_current_a": (supply_v - led_vf) / nearest
        }

    def calculate_voltage_divider(self, vin: float, r1: float, r2: float) -> Dict[str, Any]:
        """
        Calculate voltage divider output.

        Vout = Vin * (R2 / (R1 + R2))
        """
        if r1 <= 0 or r2 <= 0:
            return {"error": "Invalid resistor values", "vout": None}

        vout = vin * (r2 / (r1 + r2))
        current = vin / (r1 + r2)
        power_r1 = current * current * r1
        power_r2 = current * current * r2

        return {
            "vout": vout,
            "current_a": current,
            "power_r1_w": power_r1,
            "power_r2_w": power_r2,
            "total_power_w": power_r1 + power_r2
        }

    def estimate_regulator_efficiency(self, vin: float, vout: float, iout: float,
                                       regulator_type: str = "linear") -> Dict[str, Any]:
        """
        Estimate regulator efficiency and thermal dissipation.
        """
        if regulator_type == "linear":
            # Linear regulator: efficiency = Vout / Vin
            efficiency = vout / vin if vin > 0 else 0
            power_out = vout * iout
            power_in = vin * iout
            power_dissipated = power_in - power_out

            # Thermal calculation (simplified)
            # Assume thermal resistance of 50°C/W for TO-220 without heatsink
            thermal_resistance = 50.0
            temp_rise = power_dissipated * thermal_resistance

        else:  # switching
            # Switching regulator: typically 85-95% efficient
            efficiency = 0.90
            power_out = vout * iout
            power_in = power_out / efficiency
            power_dissipated = power_in - power_out
            thermal_resistance = 20.0  # Better thermal performance
            temp_rise = power_dissipated * thermal_resistance

        return {
            "efficiency_percent": efficiency * 100,
            "power_in_w": power_in,
            "power_out_w": power_out,
            "power_dissipated_w": power_dissipated,
            "temperature_rise_c": temp_rise,
            "ambient_25c_final_temp_c": 25 + temp_rise,
            "heatsink_recommended": power_dissipated > 1.0
        }

    def estimate_trace_current_capacity(self, width_mm: float, thickness_oz: float = 1.0,
                                         temp_rise_c: float = 10.0) -> Dict[str, Any]:
        """
        Estimate PCB trace current capacity.

        Uses IPC-2221 formula: I = k * dT^0.44 * A^0.725
        where k = 0.048 for external layers, 0.024 for internal
        """
        # Convert to mils and square mils
        width_mils = width_mm * 39.37
        thickness_mils = thickness_oz * 1.35  # 1 oz = 1.35 mils
        area_sq_mils = width_mils * thickness_mils

        # External layer assumption
        k = 0.048
        current_a = k * (temp_rise_c ** 0.44) * (area_sq_mils ** 0.725)

        return {
            "current_capacity_a": current_a,
            "width_mm": width_mm,
            "width_mils": width_mils,
            "temp_rise_c": temp_rise_c,
            "recommendation": f"Safe for up to {current_a:.2f}A with {temp_rise_c}°C rise"
        }

    def calculate_capacitor_decoupling(self, ic_current_a: float, voltage_v: float,
                                        switching_freq_hz: float = 1e6) -> Dict[str, Any]:
        """
        Calculate decoupling capacitor requirements for ICs.

        Rule of thumb: C = I * dt / dV
        """
        # Assume we want to limit voltage droop to 5% during switching
        dv = voltage_v * 0.05
        dt = 1.0 / switching_freq_hz  # One period

        capacitance_f = (ic_current_a * dt) / dv

        # Convert to more readable units
        if capacitance_f < 1e-9:
            cap_value = capacitance_f * 1e12
            unit = "pF"
        elif capacitance_f < 1e-6:
            cap_value = capacitance_f * 1e9
            unit = "nF"
        else:
            cap_value = capacitance_f * 1e6
            unit = "µF"

        # Standard capacitor values
        standard_caps = [0.1, 0.22, 0.47, 1.0, 2.2, 4.7, 10, 22, 47, 100]
        nearest_standard = min(standard_caps, key=lambda x: abs(x - cap_value))

        return {
            "calculated_capacitance_f": capacitance_f,
            "capacitance_value": cap_value,
            "unit": unit,
            "standard_value": nearest_standard,
            "recommendation": f"Use {nearest_standard}{unit} ceramic capacitor, X7R or X5R type",
            "voltage_rating": voltage_v * 2  # 2x derating
        }

    def estimate_crystal_load_capacitance(self, crystal_freq_hz: float) -> Dict[str, Any]:
        """
        Estimate crystal load capacitance requirements.

        Typical load caps: 18-22pF for most crystals
        """
        # Most crystals specify load capacitance
        # Common values: 12pF, 18pF, 20pF, 22pF

        typical_load_pf = 20.0  # Default

        # For each load cap: CL = (C1 * C2) / (C1 + C2) + Cstray
        # If C1 = C2, then CL = C1/2 + Cstray
        # Cstray ≈ 2-5pF, assume 3pF

        cstray_pf = 3.0
        load_cap_pf = (typical_load_pf - cstray_pf) * 2

        return {
            "crystal_freq_hz": crystal_freq_hz,
            "typical_load_capacitance_pf": typical_load_pf,
            "recommended_load_caps_pf": load_cap_pf,
            "standard_value": 22,  # 22pF is most common
            "recommendation": f"Use two 22pF ceramic capacitors for {crystal_freq_hz/1e6:.1f}MHz crystal"
        }

    def predict_circuit_behavior(self, circuit_type: str, components: List[str]) -> Dict[str, Any]:
        """
        Predict circuit behavior based on topology.

        This uses electrical engineering domain knowledge.
        """
        behaviors = {
            "power_supply": {
                "function": "Converts and regulates voltage",
                "expected_waveform": "DC with some ripple",
                "failure_symptoms": ["No output voltage", "Excessive ripple", "Overheating"],
                "test_procedure": [
                    "Measure input voltage",
                    "Measure output voltage (should be regulated)",
                    "Check ripple with oscilloscope",
                    "Verify current capacity"
                ]
            },
            "microcontroller": {
                "function": "Programmable logic and I/O control",
                "expected_waveform": "Digital pulses on I/O pins",
                "failure_symptoms": ["No clock signal", "Not responding to programming", "Erratic behavior"],
                "test_procedure": [
                    "Check power supply voltage",
                    "Verify clock signal on crystal pins",
                    "Check RESET pin status",
                    "Attempt programming via bootloader"
                ]
            },
            "wireless": {
                "function": "RF transmission/reception",
                "expected_waveform": "RF signal at specified frequency",
                "failure_symptoms": ["No WiFi connection", "Weak signal", "Cannot program"],
                "test_procedure": [
                    "Check 3.3V power supply (critical for ESP)",
                    "Verify sufficient current capacity (250mA+)",
                    "Check EN/RESET pins",
                    "Verify antenna connection"
                ]
            },
            "usb_interface": {
                "function": "USB data communication and power",
                "expected_waveform": "Differential USB data signals",
                "failure_symptoms": ["Not detected by computer", "Intermittent connection"],
                "test_procedure": [
                    "Check VBUS (5V)",
                    "Verify D+ and D- connections",
                    "Check for proper termination resistors",
                    "Test with different USB cable"
                ]
            }
        }

        return behaviors.get(circuit_type, {
            "function": "Unknown circuit type",
            "expected_waveform": "Unknown",
            "failure_symptoms": [],
            "test_procedure": []
        })


# Instantiate global analyzer
electrical_analyzer = ElectricalAnalyzer()
