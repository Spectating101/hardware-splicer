"""
Safety Validation System - Modification Safety Checks

Validates modifications for electrical and physical safety:
- Voltage/current compatibility
- Thermal limits
- Component ratings
- Short circuit risks
- ESD protection
- High voltage warnings
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(Enum):
    SAFE = "safe"
    CAUTION = "caution"
    WARNING = "warning"
    DANGER = "danger"
    CRITICAL = "critical"


@dataclass
class SafetyCheck:
    """Single safety validation check."""
    check_name: str
    risk_level: RiskLevel
    passed: bool
    message: str
    recommendation: str
    blocking: bool = False  # If True, must fix before proceeding


@dataclass
class SafetyValidation:
    """Complete safety validation result."""
    overall_safe: bool
    risk_level: RiskLevel
    checks: List[SafetyCheck]
    critical_issues: List[str]
    warnings: List[str]
    recommendations: List[str]
    proceed_allowed: bool


class SafetyValidator:
    """Validates modification and repair safety."""

    def __init__(self):
        self.voltage_limits = self._load_voltage_limits()
        self.current_limits = self._load_current_limits()
        self.thermal_limits = self._load_thermal_limits()

    def validate_modification(self, modification_plan: Any,
                             circuit_topology: Any,
                             components: List[str]) -> SafetyValidation:
        """
        Validate if a modification is safe to perform.

        Checks electrical, thermal, and mechanical safety.
        """

        checks = []

        # Voltage compatibility
        voltage_check = self._check_voltage_compatibility(modification_plan, components)
        checks.append(voltage_check)

        # Current capacity
        current_check = self._check_current_capacity(modification_plan, circuit_topology)
        checks.append(current_check)

        # Thermal safety
        thermal_check = self._check_thermal_safety(modification_plan, circuit_topology)
        checks.append(thermal_check)

        # Short circuit risk
        short_check = self._check_short_circuit_risk(modification_plan)
        checks.append(short_check)

        # Component ratings
        rating_check = self._check_component_ratings(modification_plan)
        checks.append(rating_check)

        # High voltage present
        hv_check = self._check_high_voltage(components)
        checks.append(hv_check)

        # ESD sensitivity
        esd_check = self._check_esd_sensitivity(components)
        checks.append(esd_check)

        # Reversibility
        reversibility_check = self._check_reversibility(modification_plan)
        checks.append(reversibility_check)

        # Determine overall safety
        critical_issues = [c.message for c in checks if c.risk_level == RiskLevel.CRITICAL]
        warnings = [c.message for c in checks if c.risk_level in [RiskLevel.WARNING, RiskLevel.DANGER]]
        recommendations = [c.recommendation for c in checks if not c.passed]

        blocking_issues = [c for c in checks if c.blocking and not c.passed]

        overall_safe = len(critical_issues) == 0 and len(blocking_issues) == 0
        proceed_allowed = len(blocking_issues) == 0

        # Determine overall risk level
        if any(c.risk_level == RiskLevel.CRITICAL for c in checks):
            overall_risk = RiskLevel.CRITICAL
        elif any(c.risk_level == RiskLevel.DANGER for c in checks):
            overall_risk = RiskLevel.DANGER
        elif any(c.risk_level == RiskLevel.WARNING for c in checks):
            overall_risk = RiskLevel.WARNING
        elif any(c.risk_level == RiskLevel.CAUTION for c in checks):
            overall_risk = RiskLevel.CAUTION
        else:
            overall_risk = RiskLevel.SAFE

        return SafetyValidation(
            overall_safe=overall_safe,
            risk_level=overall_risk,
            checks=checks,
            critical_issues=critical_issues,
            warnings=warnings,
            recommendations=recommendations,
            proceed_allowed=proceed_allowed
        )

    def _check_voltage_compatibility(self, modification_plan: Any,
                                    components: List[str]) -> SafetyCheck:
        """Check if voltages are compatible."""

        # Critical: ESP8266/ESP32 with 5V
        esp_components = [c for c in components if 'ESP' in c]
        if esp_components:
            # Check if plan mentions 5V or Arduino (5V logic)
            plan_text = str(modification_plan)
            if '5V' in plan_text or 'Arduino' in plan_text:
                return SafetyCheck(
                    check_name="Voltage Compatibility",
                    risk_level=RiskLevel.CRITICAL,
                    passed=False,
                    message="CRITICAL: ESP modules require 3.3V! 5V will permanently damage chip!",
                    recommendation="Use level shifters for data lines, separate 3.3V regulator for power",
                    blocking=True
                )

        # Check for voltage regulator stress
        if hasattr(modification_plan, 'parts_needed'):
            parts = str(modification_plan.parts_needed)
            if 'regulator' in parts.lower():
                return SafetyCheck(
                    check_name="Voltage Compatibility",
                    risk_level=RiskLevel.CAUTION,
                    passed=True,
                    message="Voltage regulator modification detected",
                    recommendation="Verify input/output voltage specs before powering on"
                )

        return SafetyCheck(
            check_name="Voltage Compatibility",
            risk_level=RiskLevel.SAFE,
            passed=True,
            message="No voltage compatibility issues detected",
            recommendation="Always verify voltage levels before connecting power"
        )

    def _check_current_capacity(self, modification_plan: Any,
                               circuit_topology: Any) -> SafetyCheck:
        """Check if current capacity is adequate."""

        # Check power budget if available
        if hasattr(circuit_topology, 'power_budget') and circuit_topology.power_budget:
            total_power = circuit_topology.power_budget.get('total_power_w', 0)

            if total_power > 10:
                return SafetyCheck(
                    check_name="Current Capacity",
                    risk_level=RiskLevel.WARNING,
                    passed=False,
                    message=f"High power consumption: {total_power:.1f}W",
                    recommendation="Ensure power supply can handle this load + margin (1.5x recommended)"
                )

        # Check for WiFi modules (high peak current)
        plan_text = str(modification_plan)
        if 'ESP8266' in plan_text or 'WiFi' in plan_text:
            return SafetyCheck(
                check_name="Current Capacity",
                risk_level=RiskLevel.WARNING,
                passed=False,
                message="WiFi modules have high peak current draw (300mA+)",
                recommendation="Use dedicated regulator with >500mA capacity, add bulk capacitor (100-470µF)"
            )

        return SafetyCheck(
            check_name="Current Capacity",
            risk_level=RiskLevel.SAFE,
            passed=True,
            message="Current capacity appears adequate",
            recommendation="Monitor for brownouts or unexpected resets"
        )

    def _check_thermal_safety(self, modification_plan: Any,
                             circuit_topology: Any) -> SafetyCheck:
        """Check thermal safety."""

        # Check if regulator thermal dissipation is high
        if hasattr(circuit_topology, 'electrical_calculations'):
            calcs = circuit_topology.electrical_calculations
            if 'regulator_efficiency' in calcs:
                reg_calc = calcs['regulator_efficiency']
                temp = reg_calc.get('ambient_25c_final_temp_c', 0)

                if temp > 85:
                    return SafetyCheck(
                        check_name="Thermal Safety",
                        risk_level=RiskLevel.DANGER,
                        passed=False,
                        message=f"Voltage regulator will reach {temp:.0f}°C - exceeds safe limits!",
                        recommendation="Add heatsink, or use switching regulator instead of linear",
                        blocking=True
                    )
                elif temp > 60:
                    return SafetyCheck(
                        check_name="Thermal Safety",
                        risk_level=RiskLevel.WARNING,
                        passed=False,
                        message=f"Voltage regulator will reach {temp:.0f}°C",
                        recommendation="Consider adding heatsink for better reliability"
                    )

        return SafetyCheck(
            check_name="Thermal Safety",
            risk_level=RiskLevel.SAFE,
            passed=True,
            message="No thermal issues detected",
            recommendation="Monitor component temperatures during initial testing"
        )

    def _check_short_circuit_risk(self, modification_plan: Any) -> SafetyCheck:
        """Check for short circuit risks."""

        # Check if plan involves soldering or wiring
        plan_text = str(modification_plan).lower()

        if 'solder' in plan_text or 'wire' in plan_text:
            return SafetyCheck(
                check_name="Short Circuit Risk",
                risk_level=RiskLevel.CAUTION,
                passed=True,
                message="Modification involves soldering/wiring",
                recommendation="Inspect for solder bridges, verify no shorts with multimeter before powering"
            )

        return SafetyCheck(
            check_name="Short Circuit Risk",
            risk_level=RiskLevel.SAFE,
            passed=True,
            message="Low short circuit risk",
            recommendation="Always verify connections before applying power"
        )

    def _check_component_ratings(self, modification_plan: Any) -> SafetyCheck:
        """Check if components are within ratings."""

        # Check for capacitor voltage ratings
        plan_text = str(modification_plan).lower()

        if 'capacitor' in plan_text:
            return SafetyCheck(
                check_name="Component Ratings",
                risk_level=RiskLevel.CAUTION,
                passed=True,
                message="Modification involves capacitors",
                recommendation="Use capacitors rated for 2x the voltage (e.g., 16V cap for 5V circuit)"
            )

        return SafetyCheck(
            check_name="Component Ratings",
            risk_level=RiskLevel.SAFE,
            passed=True,
            message="Component ratings appear adequate",
            recommendation="Verify all components rated above operating conditions"
        )

    def _check_high_voltage(self, components: List[str]) -> SafetyCheck:
        """Check for high voltage present."""

        # Check for line voltage components
        hv_components = ['transformer', 'rectifier', 'ac', 'mains', '220v', '110v']

        for comp in components:
            comp_lower = comp.lower()
            if any(hv in comp_lower for hv in hv_components):
                return SafetyCheck(
                    check_name="High Voltage Present",
                    risk_level=RiskLevel.DANGER,
                    passed=False,
                    message="HIGH VOLTAGE PRESENT - Mains power detected!",
                    recommendation="DISCONNECT FROM MAINS before working! Discharge capacitors! Use isolation transformer!",
                    blocking=True
                )

        # Check for PoE (48V)
        if any('ethernet' in c.lower() or 'poe' in c.lower() for c in components):
            return SafetyCheck(
                check_name="High Voltage Present",
                risk_level=RiskLevel.WARNING,
                passed=False,
                message="PoE voltage (48V) may be present on Ethernet ports",
                recommendation="Disconnect PoE before working on circuit"
            )

        return SafetyCheck(
            check_name="High Voltage Present",
            risk_level=RiskLevel.SAFE,
            passed=True,
            message="No high voltage detected - appears to be low voltage DC",
            recommendation="Still verify with multimeter before touching"
        )

    def _check_esd_sensitivity(self, components: List[str]) -> SafetyCheck:
        """Check for ESD-sensitive components."""

        esd_sensitive = ['ic', 'chip', 'mcu', 'cpu', 'flash', 'ram', 'esp', 'atmega', 'mosfet', 'fet']

        sensitive_found = []
        for comp in components:
            comp_lower = comp.lower()
            if any(sens in comp_lower for sens in esd_sensitive):
                sensitive_found.append(comp)

        if sensitive_found:
            return SafetyCheck(
                check_name="ESD Sensitivity",
                risk_level=RiskLevel.CAUTION,
                passed=False,
                message=f"ESD-sensitive components detected: {len(sensitive_found)} components",
                recommendation="Use ESD wrist strap, work on anti-static mat, avoid wearing synthetic clothing"
            )

        return SafetyCheck(
            check_name="ESD Sensitivity",
            risk_level=RiskLevel.SAFE,
            passed=True,
            message="No highly ESD-sensitive components detected",
            recommendation="Still use basic ESD precautions"
        )

    def _check_reversibility(self, modification_plan: Any) -> SafetyCheck:
        """Check if modification is reversible."""

        if hasattr(modification_plan, 'reversibility'):
            reversibility = modification_plan.reversibility

            if 'irreversible' in reversibility.lower():
                return SafetyCheck(
                    check_name="Reversibility",
                    risk_level=RiskLevel.WARNING,
                    passed=False,
                    message="Modification is IRREVERSIBLE - cannot undo!",
                    recommendation="Double-check plan before proceeding, consider alternatives"
                )
            elif 'partially' in reversibility.lower():
                return SafetyCheck(
                    check_name="Reversibility",
                    risk_level=RiskLevel.CAUTION,
                    passed=True,
                    message="Modification is partially reversible",
                    recommendation="Document original state with photos before modifying"
                )

        return SafetyCheck(
            check_name="Reversibility",
            risk_level=RiskLevel.SAFE,
            passed=True,
            message="Modification appears reversible",
            recommendation="Document original state anyway"
        )

    def _load_voltage_limits(self) -> Dict[str, Tuple[float, float]]:
        """Load component voltage limits."""
        return {
            'ESP8266': (2.5, 3.6),
            'ESP32': (2.3, 3.6),
            'ATmega328P': (1.8, 5.5),
            'Arduino': (7.0, 12.0),  # Input voltage
            '5V_logic': (4.5, 5.5),
            '3.3V_logic': (3.0, 3.6)
        }

    def _load_current_limits(self) -> Dict[str, float]:
        """Load typical current limits."""
        return {
            'USB_2.0': 0.5,  # 500mA
            'USB_3.0': 0.9,  # 900mA
            'Arduino_3.3V_pin': 0.05,  # 50mA
            'Arduino_5V_pin': 0.2,  # 200mA typically
        }

    def _load_thermal_limits(self) -> Dict[str, float]:
        """Load thermal limits."""
        return {
            'regulator_max': 125,  # °C
            'ic_max': 85,  # °C typical consumer grade
            'capacitor_max': 105,  # °C for standard caps
        }

    def generate_safety_checklist(self, modification_plan: Any) -> List[str]:
        """Generate pre-modification safety checklist."""

        checklist = [
            "☐ Disconnect all power sources (battery, USB, DC jack)",
            "☐ Discharge all capacitors (especially if line voltage)",
            "☐ Verify workspace is non-conductive (wood/plastic table)",
            "☐ Use ESD wrist strap grounded to earth",
            "☐ Have multimeter ready for testing",
            "☐ Document original state with photos",
            "☐ Read modification plan completely before starting",
            "☐ Gather all required tools and parts",
            "☐ Verify replacement parts match specifications",
            "☐ Have good lighting and magnification if needed"
        ]

        # Add specific checks based on modification type
        plan_text = str(modification_plan).lower()

        if 'solder' in plan_text:
            checklist.extend([
                "☐ Soldering iron tip clean and tinned",
                "☐ Flux and solder wick available",
                "☐ Work in ventilated area (solder fumes)"
            ])

        if 'esp8266' in plan_text or 'esp32' in plan_text:
            checklist.extend([
                "☐ CRITICAL: Verify 3.3V power supply, NOT 5V!",
                "☐ Level shifters ready if interfacing with 5V logic",
                "☐ Have USB-UART adapter for programming"
            ])

        if 'firmware' in plan_text or 'flash' in plan_text:
            checklist.extend([
                "☐ Backup original firmware if possible",
                "☐ Verify firmware file checksum/hash",
                "☐ Have recovery plan if flash fails",
                "☐ Ensure stable power during flash (no interruptions!)"
            ])

        return checklist


# Global instance
safety_validator = SafetyValidator()
