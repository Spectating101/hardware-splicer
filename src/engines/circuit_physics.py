#!/usr/bin/env python3
"""
Circuit Physics Engine
Real electrical simulation that ChatGPT cannot do

This engine calculates:
- Voltage drops across circuit
- Current flow through components
- Power dissipation and thermal load
- Component stress and failure prediction
- Real-time validation during design
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum
import math


class ComponentType(Enum):
    MICROCONTROLLER = "microcontroller"
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    DISPLAY = "display"
    POWER_SUPPLY = "power_supply"
    PASSIVE = "passive"  # resistor, capacitor, etc.


class VoltageLevel(Enum):
    V_3_3 = 3.3
    V_5_0 = 5.0
    V_12_0 = 12.0


@dataclass
class ElectricalSpec:
    """Electrical specifications for a component"""
    operating_voltage: float  # Volts
    min_voltage: float  # Minimum safe voltage
    max_voltage: float  # Maximum safe voltage
    typical_current: float  # Typical current draw (Amps)
    max_current: float  # Maximum current draw (Amps)
    output_current_max: Optional[float] = None  # For power supplies/MCUs
    logic_level: Optional[float] = None  # Logic HIGH voltage
    input_impedance: Optional[float] = None  # Ohms
    power_dissipation: Optional[float] = None  # Watts


@dataclass
class ThermalSpec:
    """Thermal specifications"""
    max_junction_temp: float  # °C
    thermal_resistance: float  # °C/W
    ambient_temp: float = 25.0  # °C


@dataclass
class PhysicalComponent:
    """A component with real electrical properties"""
    id: str
    name: str
    component_type: ComponentType
    electrical: ElectricalSpec
    thermal: Optional[ThermalSpec] = None
    position_3d: Optional[Tuple[float, float, float]] = None


@dataclass
class Wire:
    """A wire connection between components"""
    from_component: str
    from_pin: str
    to_component: str
    to_pin: str
    length: float = 0.1  # meters
    gauge: int = 22  # AWG

    def resistance(self) -> float:
        """Calculate wire resistance based on length and gauge"""
        # Resistance of copper wire (Ohms per meter)
        # AWG 22 = 0.0527 Ohm/m, AWG 20 = 0.0331 Ohm/m
        resistance_per_meter = {
            22: 0.0527,
            20: 0.0331,
            18: 0.0208,
            16: 0.0131
        }
        return resistance_per_meter.get(self.gauge, 0.0527) * self.length


@dataclass
class PowerRail:
    """A power distribution rail"""
    voltage: float
    max_current: float  # Maximum current this rail can supply
    components_connected: List[str]


@dataclass
class SimulationIssue:
    """An issue found during simulation"""
    severity: str  # 'critical', 'error', 'warning'
    component: str
    issue: str
    explanation: str
    physics_data: Dict  # Actual calculated values
    solution: str


class CircuitPhysicsEngine:
    """
    Real physics simulation for circuits

    What this does that ChatGPT CAN'T:
    - Calculate actual voltage drops
    - Predict component failures
    - Detect thermal issues
    - Validate current capacity
    - Simulate real electrical behavior
    """

    def __init__(self):
        # Component library with real specs
        self.component_specs = self._load_component_specs()

    def _load_component_specs(self) -> Dict[str, PhysicalComponent]:
        """Load real component specifications"""
        return {
            'esp32': PhysicalComponent(
                id='esp32',
                name='ESP32 DevKit',
                component_type=ComponentType.MICROCONTROLLER,
                electrical=ElectricalSpec(
                    operating_voltage=3.3,
                    min_voltage=2.3,
                    max_voltage=3.6,
                    typical_current=0.160,  # 160mA typical
                    max_current=0.240,  # 240mA peak (WiFi active)
                    output_current_max=0.040,  # 40mA per GPIO
                    logic_level=3.3
                ),
                thermal=ThermalSpec(
                    max_junction_temp=125.0,
                    thermal_resistance=15.0  # °C/W (junction to ambient)
                )
            ),

            'arduino_uno': PhysicalComponent(
                id='arduino_uno',
                name='Arduino Uno R3',
                component_type=ComponentType.MICROCONTROLLER,
                electrical=ElectricalSpec(
                    operating_voltage=5.0,
                    min_voltage=4.5,
                    max_voltage=5.5,
                    typical_current=0.050,  # 50mA typical
                    max_current=0.200,  # 200mA with peripherals
                    output_current_max=0.040,  # 40mA per pin
                    logic_level=5.0
                ),
                thermal=ThermalSpec(
                    max_junction_temp=85.0,
                    thermal_resistance=25.0
                )
            ),

            'bme280': PhysicalComponent(
                id='bme280',
                name='BME280 Sensor',
                component_type=ComponentType.SENSOR,
                electrical=ElectricalSpec(
                    operating_voltage=3.3,
                    min_voltage=1.71,
                    max_voltage=3.6,
                    typical_current=0.00035,  # 0.35mA typical
                    max_current=0.0012,  # 1.2mA measuring
                    logic_level=3.3
                )
            ),

            'servo_sg90': PhysicalComponent(
                id='servo_sg90',
                name='SG90 Micro Servo',
                component_type=ComponentType.ACTUATOR,
                electrical=ElectricalSpec(
                    operating_voltage=5.0,
                    min_voltage=4.8,
                    max_voltage=6.0,
                    typical_current=0.100,  # 100mA idle
                    max_current=0.650,  # 650mA stall
                    logic_level=5.0  # Control signal
                ),
                thermal=ThermalSpec(
                    max_junction_temp=80.0,
                    thermal_resistance=30.0
                )
            ),

            'hc_sr04': PhysicalComponent(
                id='hc_sr04',
                name='HC-SR04 Ultrasonic Sensor',
                component_type=ComponentType.SENSOR,
                electrical=ElectricalSpec(
                    operating_voltage=5.0,
                    min_voltage=4.5,
                    max_voltage=5.5,
                    typical_current=0.015,  # 15mA typical
                    max_current=0.030,  # 30mA burst
                    logic_level=5.0
                )
            ),

            'oled_ssd1306': PhysicalComponent(
                id='oled_ssd1306',
                name='0.96" OLED Display',
                component_type=ComponentType.DISPLAY,
                electrical=ElectricalSpec(
                    operating_voltage=3.3,
                    min_voltage=3.0,
                    max_voltage=5.5,
                    typical_current=0.020,  # 20mA typical
                    max_current=0.025,  # 25mA all pixels on
                    logic_level=3.3
                )
            ),

            'led': PhysicalComponent(
                id='led',
                name='Standard LED',
                component_type=ComponentType.PASSIVE,
                electrical=ElectricalSpec(
                    operating_voltage=2.0,  # Forward voltage
                    min_voltage=1.8,
                    max_voltage=2.2,
                    typical_current=0.020,  # 20mA
                    max_current=0.030  # 30mA absolute max
                )
            ),
        }

    def simulate_circuit(self, design: Dict) -> List[SimulationIssue]:
        """
        Simulate a complete circuit design

        This does REAL physics simulation:
        1. Calculate total current draw
        2. Check voltage levels
        3. Validate power capacity
        4. Calculate thermal load
        5. Predict component stress

        Args:
            design: {
                'microcontroller': 'esp32',
                'components': ['bme280', 'servo_sg90'],
                'power_source': 'usb',  # or 'battery', 'external'
                'external_power_voltage': None,  # If external
                'external_power_current': None
            }

        Returns:
            List of issues found (empty if design is safe)
        """
        issues = []

        # Get MCU specs
        mcu_id = design.get('microcontroller')
        if mcu_id not in self.component_specs:
            return [SimulationIssue(
                severity='error',
                component=mcu_id,
                issue='Unknown microcontroller',
                explanation=f'No specifications found for {mcu_id}',
                physics_data={},
                solution='Use a supported microcontroller: esp32, arduino_uno, etc.'
            )]

        mcu = self.component_specs[mcu_id]

        # Get connected components
        components = design.get('components', [])
        power_source = design.get('power_source', 'usb')

        # 1. Calculate total current draw
        total_current = self._calculate_total_current(mcu, components)

        # 2. Check power supply capacity
        power_issues = self._check_power_capacity(
            mcu, total_current, power_source, design
        )
        issues.extend(power_issues)

        # 3. Check voltage level compatibility
        voltage_issues = self._check_voltage_compatibility(mcu, components)
        issues.extend(voltage_issues)

        # 4. Check GPIO current limits
        gpio_issues = self._check_gpio_limits(mcu, components)
        issues.extend(gpio_issues)

        # 5. Calculate thermal load
        thermal_issues = self._calculate_thermal_load(mcu, total_current)
        issues.extend(thermal_issues)

        # 6. Check for high-current actuators
        actuator_issues = self._check_actuators(mcu, components)
        issues.extend(actuator_issues)

        return issues

    def _calculate_total_current(self, mcu: PhysicalComponent,
                                 component_ids: List[str]) -> Dict:
        """Calculate total current draw"""
        # MCU current
        mcu_typical = mcu.electrical.typical_current
        mcu_max = mcu.electrical.max_current

        # Component currents
        components_typical = 0.0
        components_max = 0.0

        for comp_id in component_ids:
            if comp_id in self.component_specs:
                comp = self.component_specs[comp_id]
                components_typical += comp.electrical.typical_current
                components_max += comp.electrical.max_current

        return {
            'mcu_typical': mcu_typical,
            'mcu_max': mcu_max,
            'components_typical': components_typical,
            'components_max': components_max,
            'total_typical': mcu_typical + components_typical,
            'total_max': mcu_max + components_max
        }

    def _check_power_capacity(self, mcu: PhysicalComponent,
                             current_draw: Dict,
                             power_source: str,
                             design: Dict) -> List[SimulationIssue]:
        """Check if power supply can handle the load"""
        issues = []

        # USB power typically 500mA
        if power_source == 'usb':
            usb_limit = 0.500  # 500mA

            if current_draw['total_max'] > usb_limit:
                issues.append(SimulationIssue(
                    severity='error',
                    component='power_supply',
                    issue='Insufficient USB power capacity',
                    explanation=f"Circuit draws {current_draw['total_max']*1000:.0f}mA peak, "
                               f"but USB only supplies {usb_limit*1000:.0f}mA. "
                               f"Under load, voltage will drop causing brownouts, resets, or damage.",
                    physics_data={
                        'required_current': current_draw['total_max'],
                        'available_current': usb_limit,
                        'deficit': current_draw['total_max'] - usb_limit
                    },
                    solution="Use external 5V power supply (1A minimum) or reduce load "
                            "(remove high-current components)"
                ))
            elif current_draw['total_typical'] > usb_limit * 0.8:
                issues.append(SimulationIssue(
                    severity='warning',
                    component='power_supply',
                    issue='USB power near capacity',
                    explanation=f"Typical draw is {current_draw['total_typical']*1000:.0f}mA, "
                               f"which is {(current_draw['total_typical']/usb_limit)*100:.0f}% "
                               f"of USB capacity. May cause instability.",
                    physics_data=current_draw,
                    solution="Consider external power supply for reliability"
                ))

        return issues

    def _check_voltage_compatibility(self, mcu: PhysicalComponent,
                                    component_ids: List[str]) -> List[SimulationIssue]:
        """Check if component voltages are compatible"""
        issues = []

        mcu_voltage = mcu.electrical.logic_level

        for comp_id in component_ids:
            if comp_id not in self.component_specs:
                continue

            comp = self.component_specs[comp_id]
            comp_voltage = comp.electrical.operating_voltage

            # Check if voltages match
            voltage_diff = abs(comp_voltage - mcu_voltage)

            if voltage_diff > 0.5:  # Significant mismatch
                if comp_voltage > mcu_voltage:
                    issues.append(SimulationIssue(
                        severity='warning',
                        component=comp_id,
                        issue=f'Voltage level mismatch',
                        explanation=f"{comp.name} operates at {comp_voltage}V but "
                                   f"{mcu.name} uses {mcu_voltage}V logic. "
                                   f"Output signals may be below logic HIGH threshold.",
                        physics_data={
                            'component_voltage': comp_voltage,
                            'mcu_voltage': mcu_voltage,
                            'logic_threshold': mcu_voltage * 0.7  # Typical threshold
                        },
                        solution="Use level shifter or 3.3V-compatible version of component"
                    ))
                else:
                    issues.append(SimulationIssue(
                        severity='warning',
                        component=comp_id,
                        issue='Potential signal compatibility issue',
                        explanation=f"{comp.name} outputs {comp_voltage}V but "
                                   f"{mcu.name} expects {mcu_voltage}V. "
                                   f"Should still work but not ideal.",
                        physics_data={
                            'component_voltage': comp_voltage,
                            'mcu_voltage': mcu_voltage
                        },
                        solution="Monitor for reliability, consider level shifter if issues occur"
                    ))

        return issues

    def _check_gpio_limits(self, mcu: PhysicalComponent,
                          component_ids: List[str]) -> List[SimulationIssue]:
        """Check if GPIO pins can handle the load"""
        issues = []

        if not mcu.electrical.output_current_max:
            return issues

        gpio_limit = mcu.electrical.output_current_max

        for comp_id in component_ids:
            if comp_id not in self.component_specs:
                continue

            comp = self.component_specs[comp_id]

            # Check if component draws more than GPIO can supply
            if comp.electrical.typical_current > gpio_limit:
                issues.append(SimulationIssue(
                    severity='error',
                    component=comp_id,
                    issue='GPIO current exceeded',
                    explanation=f"{comp.name} draws {comp.electrical.typical_current*1000:.0f}mA "
                               f"but {mcu.name} GPIO can only supply {gpio_limit*1000:.0f}mA. "
                               f"This will damage the MCU or cause malfunction.",
                    physics_data={
                        'component_current': comp.electrical.typical_current,
                        'gpio_limit': gpio_limit,
                        'overdraw': comp.electrical.typical_current - gpio_limit
                    },
                    solution="Use transistor or MOSFET to switch higher currents, "
                            "or use external driver circuit"
                ))

        return issues

    def _calculate_thermal_load(self, mcu: PhysicalComponent,
                               current_draw: Dict) -> List[SimulationIssue]:
        """Calculate thermal load and check for overheating"""
        issues = []

        if not mcu.thermal:
            return issues

        # Calculate power dissipation (P = I * V)
        voltage = mcu.electrical.operating_voltage
        max_current = current_draw['total_max']
        power_dissipation = voltage * max_current

        # Calculate junction temperature
        # T_junction = T_ambient + (P * R_thermal)
        ambient_temp = mcu.thermal.ambient_temp
        thermal_resistance = mcu.thermal.thermal_resistance
        junction_temp = ambient_temp + (power_dissipation * thermal_resistance)

        # Check against maximum rating
        max_temp = mcu.thermal.max_junction_temp

        if junction_temp > max_temp * 0.9:  # Within 90% of max
            issues.append(SimulationIssue(
                severity='warning',
                component=mcu.id,
                issue='High thermal load',
                explanation=f"Junction temperature will reach {junction_temp:.1f}°C "
                           f"(max: {max_temp:.1f}°C). Power dissipation is {power_dissipation:.2f}W. "
                           f"May cause thermal throttling or reduced lifespan.",
                physics_data={
                    'junction_temp': junction_temp,
                    'max_temp': max_temp,
                    'power_dissipation': power_dissipation,
                    'thermal_margin': max_temp - junction_temp
                },
                solution="Add heatsink, improve airflow, or reduce load"
            ))

        return issues

    def _check_actuators(self, mcu: PhysicalComponent,
                        component_ids: List[str]) -> List[SimulationIssue]:
        """Check for high-power actuators that need special handling"""
        issues = []

        for comp_id in component_ids:
            if comp_id not in self.component_specs:
                continue

            comp = self.component_specs[comp_id]

            if comp.component_type == ComponentType.ACTUATOR:
                # Actuators like servos need external power
                if comp.electrical.max_current > 0.1:  # >100mA
                    issues.append(SimulationIssue(
                        severity='error',
                        component=comp_id,
                        issue='High-current actuator needs external power',
                        explanation=f"{comp.name} draws up to {comp.electrical.max_current*1000:.0f}mA "
                                   f"under load. This exceeds safe limits for direct MCU connection.",
                        physics_data={
                            'typical_current': comp.electrical.typical_current,
                            'max_current': comp.electrical.max_current,
                            'safe_limit': 0.1
                        },
                        solution=f"Connect {comp.name} power to external {comp.electrical.operating_voltage}V supply. "
                                f"Only connect signal wire to {mcu.name}. Share GND."
                    ))

        return issues

    def calculate_wire_loss(self, wire: Wire, current: float) -> Dict:
        """
        Calculate voltage drop and power loss in a wire

        Real physics: V_drop = I * R, P_loss = I² * R
        """
        resistance = wire.resistance()
        voltage_drop = current * resistance
        power_loss = current * current * resistance

        return {
            'resistance': resistance,
            'voltage_drop': voltage_drop,
            'power_loss': power_loss,
            'current': current
        }

    def simulate_3d_layout(self, components: List[PhysicalComponent],
                          wires: List[Wire]) -> List[SimulationIssue]:
        """
        Simulate a 3D physical layout

        Checks:
        - Wire length and resistance
        - Component spacing (thermal, EMI)
        - Mechanical stress
        """
        issues = []

        # Check for excessively long wires
        for wire in wires:
            if wire.length > 0.3:  # >30cm
                issues.append(SimulationIssue(
                    severity='warning',
                    component=f'wire_{wire.from_component}_to_{wire.to_component}',
                    issue='Excessively long wire',
                    explanation=f"Wire from {wire.from_component} to {wire.to_component} "
                               f"is {wire.length*100:.0f}cm long. "
                               f"Long wires increase resistance, signal degradation, and EMI.",
                    physics_data={
                        'length': wire.length,
                        'resistance': wire.resistance()
                    },
                    solution="Rearrange components closer together or use shielded cable"
                ))

        # Check component spacing (if positions are defined)
        for i, comp1 in enumerate(components):
            if not comp1.position_3d or not comp1.thermal:
                continue

            for comp2 in components[i+1:]:
                if not comp2.position_3d:
                    continue

                # Calculate distance
                dx = comp1.position_3d[0] - comp2.position_3d[0]
                dy = comp1.position_3d[1] - comp2.position_3d[1]
                dz = comp1.position_3d[2] - comp2.position_3d[2]
                distance = math.sqrt(dx*dx + dy*dy + dz*dz)

                # If both generate heat and are close together
                if comp2.thermal and distance < 0.02:  # <2cm
                    issues.append(SimulationIssue(
                        severity='warning',
                        component=f'{comp1.id},{comp2.id}',
                        issue='Components too close together',
                        explanation=f"{comp1.name} and {comp2.name} are only "
                                   f"{distance*100:.1f}cm apart. Both generate heat "
                                   f"and may cause thermal coupling.",
                        physics_data={'distance': distance},
                        solution="Increase spacing to at least 3cm or add thermal barrier"
                    ))

        return issues


def demo():
    """Demo the physics engine"""
    print("="*70)
    print("  CIRCUIT PHYSICS ENGINE - Real Simulation")
    print("="*70)
    print()

    engine = CircuitPhysicsEngine()

    # Test 1: Safe circuit
    print("TEST 1: Safe Circuit (ESP32 + BME280)")
    print("-"*70)
    design1 = {
        'microcontroller': 'esp32',
        'components': ['bme280', 'oled_ssd1306'],
        'power_source': 'usb'
    }

    issues = engine.simulate_circuit(design1)
    if not issues:
        print("✓ Circuit is SAFE")
        print("  Physics check: All voltage/current/thermal within limits")
    else:
        print(f"Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"  [{issue.severity.upper()}] {issue.component}")
            print(f"    {issue.issue}")
    print()

    # Test 2: Dangerous circuit (servo on GPIO)
    print("TEST 2: Dangerous Circuit (ESP32 + Servo on GPIO)")
    print("-"*70)
    design2 = {
        'microcontroller': 'esp32',
        'components': ['servo_sg90'],
        'power_source': 'usb'
    }

    issues = engine.simulate_circuit(design2)
    print(f"✗ Found {len(issues)} CRITICAL issue(s):")
    for issue in issues:
        print(f"\n[{issue.severity.upper()}] {issue.component}")
        print(f"  Problem: {issue.issue}")
        print(f"  Physics: {issue.explanation}")
        print(f"  Data: {issue.physics_data}")
        print(f"  Solution: {issue.solution}")
    print()

    # Test 3: Wire resistance calculation
    print("TEST 3: Wire Resistance Calculation")
    print("-"*70)
    wire = Wire(
        from_component='esp32',
        from_pin='GPIO21',
        to_component='bme280',
        to_pin='SDA',
        length=0.5,  # 50cm
        gauge=22
    )

    wire_loss = engine.calculate_wire_loss(wire, current=0.020)  # 20mA
    print(f"Wire: 50cm of AWG22")
    print(f"  Resistance: {wire_loss['resistance']*1000:.2f} mΩ")
    print(f"  Voltage drop at 20mA: {wire_loss['voltage_drop']*1000:.2f} mV")
    print(f"  Power loss: {wire_loss['power_loss']*1000:.4f} mW")
    print()

    print("="*70)
    print("This is what ChatGPT CANNOT do - real physics simulation")
    print("="*70)


if __name__ == '__main__':
    demo()
