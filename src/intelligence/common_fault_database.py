"""
Common Fault Database

Database of common electronics faults with:
- Symptoms
- Diagnostic tests
- Root causes
- Repair procedures
- Prevention tips

This enables the chatbot to provide expert-level diagnostics.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum


class FaultCategory(Enum):
    """Categories of faults."""
    POWER = "power"
    USB = "usb"
    PROGRAMMING = "programming"
    COMMUNICATION = "communication"
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    MEMORY = "memory"
    THERMAL = "thermal"


class Severity(Enum):
    """Fault severity levels."""
    CRITICAL = "critical"  # Device damaged, needs component replacement
    MAJOR = "major"  # Device non-functional but repairable
    MINOR = "minor"  # Device partially functional
    WARNING = "warning"  # Device works but has issues


@dataclass
class DiagnosticTest:
    """A diagnostic test to identify fault."""
    name: str
    description: str
    equipment_needed: List[str]  # ["multimeter", "oscilloscope", ...]
    steps: List[str]
    expected_result: str
    fault_indicated_if: str  # What result indicates this fault


@dataclass
class CommonFault:
    """A common fault pattern."""
    fault_id: str
    name: str
    category: FaultCategory
    severity: Severity

    # Symptoms user might report
    symptoms: List[str]

    # Visual indicators
    visual_signs: List[str]  # ["burned component", "bulging capacitor", ...]

    # Diagnostic tests
    diagnostic_tests: List[DiagnosticTest]

    # Root causes
    common_causes: List[str]

    # Affected components
    typical_components: List[str]

    # Repair procedure
    repair_steps: List[str]

    # Prevention
    prevention_tips: List[str]

    # Difficulty
    repair_difficulty: str  # "easy", "medium", "hard", "expert"
    estimated_time_minutes: int


class CommonFaultDatabase:
    """Database of common electronics faults."""

    def __init__(self):
        """Initialize database."""
        self.faults = self._build_fault_database()

    def _build_fault_database(self) -> Dict[str, CommonFault]:
        """Build comprehensive fault database."""
        faults = {}

        # FAULT 1: USB Chip Overheating
        faults['usb_chip_overheat'] = CommonFault(
            fault_id='usb_chip_overheat',
            name='USB-Serial Chip Overheating',
            category=FaultCategory.USB,
            severity=Severity.CRITICAL,
            symptoms=[
                'Computer doesn\'t recognize device',
                'USB port won\'t work',
                'Can\'t upload code',
                'Device gets hot when plugged in',
                'USB chip is very hot to touch'
            ],
            visual_signs=[
                'USB chip (CH340/CP2102/FT232) hot to touch',
                'Scorch marks around USB chip',
                'Damaged USB port pins'
            ],
            diagnostic_tests=[
                DiagnosticTest(
                    name='Touch Test',
                    description='Check if USB chip is hot',
                    equipment_needed=[],
                    steps=['Plug in USB cable', 'Wait 10 seconds', 'Carefully touch USB chip'],
                    expected_result='Chip should be warm but not hot',
                    fault_indicated_if='Chip is very hot (uncomfortable to touch)'
                ),
                DiagnosticTest(
                    name='Short Circuit Test',
                    description='Check for short between VCC and GND on USB chip',
                    equipment_needed=['multimeter'],
                    steps=[
                        'Disconnect USB',
                        'Set multimeter to resistance mode',
                        'Probe between VCC pin and GND pin of USB chip'
                    ],
                    expected_result='Resistance > 10kΩ',
                    fault_indicated_if='Resistance < 100Ω (indicates short)'
                )
            ],
            common_causes=[
                'Shorted USB chip (internal damage)',
                'ESD damage from improper handling',
                'Overvoltage on USB pins',
                'Power supply surge'
            ],
            typical_components=['CH340G', 'CP2102', 'FT232RL', 'ATmega16U2'],
            repair_steps=[
                '**IMMEDIATELY** disconnect USB cable',
                'Visually inspect USB chip for damage',
                'Test for short circuit with multimeter',
                'If shorted: USB chip must be replaced (requires hot air station)',
                'Alternative: Use external USB-serial adapter connected to RX/TX pins',
                'If using adapter: Remove damaged USB chip to prevent conflicts'
            ],
            prevention_tips=[
                'Use quality USB cables',
                'Don\'t hot-plug while circuit is powered',
                'Add ESD protection diodes on USB lines',
                'Use USB hub with overcurrent protection'
            ],
            repair_difficulty='hard',
            estimated_time_minutes=60
        )

        # FAULT 2: Voltage Regulator Failure
        faults['voltage_regulator_failure'] = CommonFault(
            fault_id='voltage_regulator_failure',
            name='Voltage Regulator Not Outputting Correct Voltage',
            category=FaultCategory.POWER,
            severity=Severity.MAJOR,
            symptoms=[
                'Device won\'t power on',
                'LED dim or not lighting',
                'Microcontroller not working',
                'Voltage regulator very hot',
                'Random resets'
            ],
            visual_signs=[
                'Voltage regulator chip very hot',
                'Burned PCB around regulator',
                'Bulging output capacitor'
            ],
            diagnostic_tests=[
                DiagnosticTest(
                    name='Output Voltage Test',
                    description='Measure voltage regulator output',
                    equipment_needed=['multimeter'],
                    steps=[
                        'Connect power supply',
                        'Measure voltage at output pin of regulator',
                        'Compare to expected voltage (5V or 3.3V)'
                    ],
                    expected_result='Output within ±5% of rated voltage',
                    fault_indicated_if='Output voltage wrong or zero'
                ),
                DiagnosticTest(
                    name='Input Voltage Test',
                    description='Check if regulator has input voltage',
                    equipment_needed=['multimeter'],
                    steps=['Measure voltage at input pin of regulator'],
                    expected_result='Input voltage present (7-12V for 5V reg)',
                    fault_indicated_if='No input voltage - problem is upstream'
                )
            ],
            common_causes=[
                'Shorted output (downstream component failure)',
                'Insufficient input voltage',
                'Damaged regulator from overcurrent',
                'No decoupling capacitors',
                'Reverse polarity connection'
            ],
            typical_components=['LM7805', 'LM7833', 'AMS1117-3.3', 'AMS1117-5.0'],
            repair_steps=[
                'Measure input voltage - must be 2V above output minimum',
                'Measure output voltage with no load',
                'If output OK with no load: problem is downstream short',
                'Find shorted component downstream',
                'If output still wrong: replace voltage regulator',
                'Add/replace input and output capacitors (100nF + 10µF)'
            ],
            prevention_tips=[
                'Always use input and output decoupling caps',
                'Add overcurrent protection',
                'Use heatsink for high current applications',
                'Check polarity before connecting power'
            ],
            repair_difficulty='medium',
            estimated_time_minutes=30
        )

        # FAULT 3: Crystal Oscillator Not Working
        faults['crystal_not_oscillating'] = CommonFault(
            fault_id='crystal_not_oscillating',
            name='Crystal Oscillator Not Oscillating',
            category=FaultCategory.PROGRAMMING,
            severity=Severity.MAJOR,
            symptoms=[
                'Can\'t upload bootloader',
                'Device not responding',
                'External clock not working',
                'Timer functions not working'
            ],
            visual_signs=[
                'Cracked crystal',
                'Missing load capacitors',
                'Cold solder joints on crystal pins'
            ],
            diagnostic_tests=[
                DiagnosticTest(
                    name='Oscilloscope Test',
                    description='Check for oscillation on crystal pins',
                    equipment_needed=['oscilloscope'],
                    steps=[
                        'Set oscilloscope to appropriate frequency (16MHz typical)',
                        'Probe crystal pin (use 10x probe, minimal loading)',
                        'Look for sine wave'
                    ],
                    expected_result='Clean sine wave at crystal frequency',
                    fault_indicated_if='No oscillation or irregular waveform'
                ),
                DiagnosticTest(
                    name='Visual Inspection',
                    description='Check crystal and load capacitors',
                    equipment_needed=['magnifying glass'],
                    steps=[
                        'Inspect crystal for cracks',
                        'Check load capacitors are installed',
                        'Verify capacitor values (typically 22pF)'
                    ],
                    expected_result='Crystal intact, capacitors present',
                    fault_indicated_if='Cracked crystal or missing capacitors'
                )
            ],
            common_causes=[
                'Incorrect load capacitors (wrong value)',
                'Missing load capacitors',
                'Cracked crystal from mechanical stress',
                'MCU fuse bits set wrong (using internal oscillator)',
                'Bad solder joints on crystal'
            ],
            typical_components=['16MHz crystal', '8MHz crystal', 'Load capacitors (18-22pF)'],
            repair_steps=[
                'Check if MCU fuse bits configured for external crystal',
                'Measure load capacitor values (should match crystal spec)',
                'Reflow solder joints on crystal pins',
                'If still not working: replace crystal',
                'Verify load capacitors are correct value',
                'Check PCB traces for breaks'
            ],
            prevention_tips=[
                'Use correct load capacitors (match crystal datasheet)',
                'Keep crystal traces short',
                'Don\'t run other signals near crystal',
                'Protect crystal from mechanical stress',
                'Add ground plane under crystal'
            ],
            repair_difficulty='medium',
            estimated_time_minutes=45
        )

        # FAULT 4: Electrolytic Capacitor Failure
        faults['capacitor_failure'] = CommonFault(
            fault_id='capacitor_failure',
            name='Electrolytic Capacitor Failed',
            category=FaultCategory.POWER,
            severity=Severity.MAJOR,
            symptoms=[
                'Device unstable',
                'Random resets',
                'Won\'t power on',
                'Humming sound',
                'Capacitor bulging'
            ],
            visual_signs=[
                'Bulging capacitor top',
                'Leaking electrolyte',
                'Burst capacitor',
                'Discolored PCB under capacitor'
            ],
            diagnostic_tests=[
                DiagnosticTest(
                    name='Visual Inspection',
                    description='Check capacitor physical condition',
                    equipment_needed=[],
                    steps=['Look at top of capacitor for bulging', 'Check for leaking fluid'],
                    expected_result='Flat top, no leakage',
                    fault_indicated_if='Bulging top, leaking, or burst'
                ),
                DiagnosticTest(
                    name='ESR Test',
                    description='Measure ESR (Equivalent Series Resistance)',
                    equipment_needed=['ESR meter or LCR meter'],
                    steps=['Desolder one lead of capacitor', 'Measure ESR with meter'],
                    expected_result='ESR < 1Ω for good low-ESR cap',
                    fault_indicated_if='ESR > 5Ω indicates failed capacitor'
                )
            ],
            common_causes=[
                'Age (capacitors dry out over time)',
                'Overvoltage',
                'High temperature operation',
                'Reverse polarity',
                'Ripple current exceeding rating'
            ],
            typical_components=['Electrolytic capacitors 10µF-1000µF'],
            repair_steps=[
                'Identify failed capacitor(s)',
                'Note polarity before removing',
                'Desolder old capacitor',
                'Clean any leaked electrolyte from PCB',
                'Install new capacitor with correct polarity',
                'Use same or higher voltage rating',
                'Use low-ESR type for power supplies'
            ],
            prevention_tips=[
                'Use quality capacitors',
                'Derate voltage (use 50% of max rating)',
                'Keep capacitors cool',
                'Use polymer caps for long life',
                'Check polarity before soldering'
            ],
            repair_difficulty='easy',
            estimated_time_minutes=15
        )

        # FAULT 5: Bootloader Corrupted
        faults['bootloader_corrupted'] = CommonFault(
            fault_id='bootloader_corrupted',
            name='Bootloader Corrupted or Missing',
            category=FaultCategory.PROGRAMMING,
            severity=Severity.MINOR,
            symptoms=[
                'Can\'t upload sketches via USB',
                'Device powers on but no response to upload',
                'Serial port shows gibberish',
                'Reset doesn\'t enter bootloader'
            ],
            visual_signs=[],
            diagnostic_tests=[
                DiagnosticTest(
                    name='Reset Test',
                    description='Check if bootloader runs after reset',
                    equipment_needed=['USB cable'],
                    steps=[
                        'Connect USB',
                        'Press reset button',
                        'Watch TX LED - should blink briefly'
                    ],
                    expected_result='TX LED blinks for 1-2 seconds after reset',
                    fault_indicated_if='No LED blink - bootloader not running'
                )
            ],
            common_causes=[
                'Bootloader overwritten by sketch',
                'Fuse bits changed',
                'Flash corruption from power loss during upload',
                'Wrong board selected during upload'
            ],
            typical_components=['Microcontroller with bootloader (ATmega328P, ATmega32U4)'],
            repair_steps=[
                'You need an ISP programmer (Arduino as ISP, USBasp, etc.)',
                'Connect ISP programmer to ICSP header',
                'Use Arduino IDE: Tools > Burn Bootloader',
                'Wait for completion',
                'Test upload via USB',
                'Alternative: Upload sketch via ISP (no bootloader needed)'
            ],
            prevention_tips=[
                'Don\'t write to boot section in sketches',
                'Use "Upload Using Programmer" carefully',
                'Maintain stable power during uploads',
                'Keep backup programmer handy'
            ],
            repair_difficulty='medium',
            estimated_time_minutes=20
        )

        return faults

    def find_faults_by_symptoms(self, symptoms: List[str]) -> List[CommonFault]:
        """
        Find faults matching given symptoms.

        Args:
            symptoms: List of symptoms user reported

        Returns:
            List of matching faults, sorted by likelihood
        """
        matches = []

        for fault in self.faults.values():
            # Calculate match score
            score = 0
            for symptom in symptoms:
                symptom_lower = symptom.lower()

                # Check if symptom matches any fault symptoms
                for fault_symptom in fault.symptoms:
                    if symptom_lower in fault_symptom.lower() or fault_symptom.lower() in symptom_lower:
                        score += 10
                        break

                # Check visual signs
                for visual_sign in fault.visual_signs:
                    if symptom_lower in visual_sign.lower() or visual_sign.lower() in symptom_lower:
                        score += 5
                        break

            if score > 0:
                matches.append((score, fault))

        # Sort by score (highest first)
        matches.sort(key=lambda x: x[0], reverse=True)

        return [fault for score, fault in matches]

    def get_diagnostic_tests(self, fault_id: str) -> List[DiagnosticTest]:
        """Get diagnostic tests for specific fault."""
        if fault_id not in self.faults:
            return []

        return self.faults[fault_id].diagnostic_tests

    def get_repair_procedure(self, fault_id: str) -> List[str]:
        """Get repair steps for specific fault."""
        if fault_id not in self.faults:
            return []

        return self.faults[fault_id].repair_steps

    def get_all_faults_in_category(self, category: FaultCategory) -> List[CommonFault]:
        """Get all faults in a category."""
        return [fault for fault in self.faults.values() if fault.category == category]


# Global singleton
common_fault_database = CommonFaultDatabase()
