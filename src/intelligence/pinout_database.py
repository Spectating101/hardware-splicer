"""
IC Pinout Database System

Provides pin-level understanding for precise repair/modification instructions.
Enables instructions like:
- "Desolder pin 3 of U5"
- "Cut trace between pin 7 of IC2 and C15"
- "Bridge pin 12 to pin 15 with a wire"

This is THE most critical missing piece for real repair guidance.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum


class PinType(Enum):
    """Types of IC pins."""
    POWER = "power"
    GROUND = "ground"
    INPUT = "input"
    OUTPUT = "output"
    BIDIRECTIONAL = "bidirectional"
    ANALOG = "analog"
    CLOCK = "clock"
    RESET = "reset"
    PROGRAMMING = "programming"
    UNUSED = "unused"
    NC = "no_connect"


class PackageType(Enum):
    """IC package types."""
    DIP = "dip"  # Dual Inline Package
    SOIC = "soic"  # Small Outline IC
    TSSOP = "tssop"  # Thin Shrink Small Outline Package
    QFN = "qfn"  # Quad Flat No-leads
    QFP = "qfp"  # Quad Flat Package
    BGA = "bga"  # Ball Grid Array
    TO220 = "to220"  # Transistor Outline
    SOT23 = "sot23"  # Small Outline Transistor
    MODULE = "module"  # Pre-packaged module


@dataclass
class PinDefinition:
    """Definition of a single IC pin."""
    pin_number: int  # Physical pin number
    pin_name: str  # Name (e.g., "VCC", "TX", "GPIO2")
    pin_type: PinType
    description: str
    typical_voltage: Optional[float] = None  # Expected voltage in normal operation
    max_current_ma: Optional[float] = None  # Max current draw/source
    alternate_functions: List[str] = field(default_factory=list)  # Other modes
    typical_connections: List[str] = field(default_factory=list)  # What it usually connects to
    critical: bool = False  # If damaged, IC won't work


@dataclass
class ICPinout:
    """Complete pinout for an IC."""
    part_number: str
    manufacturer: str
    description: str
    package: PackageType
    pin_count: int
    pins: List[PinDefinition]
    common_variants: List[str] = field(default_factory=list)
    datasheet_url: Optional[str] = None
    notes: str = ""


class PinoutDatabase:
    """Database of IC pinouts for component identification."""

    def __init__(self):
        self._pinouts: Dict[str, ICPinout] = {}
        self._load_common_ics()

    def _load_common_ics(self):
        """Load pinouts for common ICs."""
        self._add_atmega328p()
        self._add_esp8266()
        self._add_esp32()
        self._add_lm7805()
        self._add_ams1117()
        self._add_ch340()
        self._add_cp2102()
        self._add_ft232()
        self._add_atmega16u2()
        self._add_w25q32()
        self._add_mx25l3233f()

    def _add_atmega328p(self):
        """ATmega328P microcontroller (Arduino Uno core)."""
        pins = [
            # Power
            PinDefinition(7, "VCC", PinType.POWER, "Power supply", 5.0, None, [], ["5V rail"], True),
            PinDefinition(8, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),
            PinDefinition(20, "AVCC", PinType.POWER, "Analog power", 5.0, None, [], ["5V rail + filter"], True),
            PinDefinition(22, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),

            # Crystal
            PinDefinition(9, "XTAL1", PinType.INPUT, "Crystal input", None, None, [], ["16MHz crystal"], True),
            PinDefinition(10, "XTAL2", PinType.OUTPUT, "Crystal output", None, None, [], ["16MHz crystal"], True),

            # Reset
            PinDefinition(1, "RESET", PinType.INPUT, "Reset (active low)", 5.0, None, ["PC6"], ["Pull-up resistor"], True),

            # UART
            PinDefinition(2, "PD0/RXD", PinType.INPUT, "UART receive", 5.0, None, ["PCINT16"], ["USB chip TX"], False),
            PinDefinition(3, "PD1/TXD", PinType.OUTPUT, "UART transmit", 5.0, None, ["PCINT17"], ["USB chip RX"], False),

            # I2C
            PinDefinition(27, "PC4/SDA", PinType.BIDIRECTIONAL, "I2C data", None, None, ["ADC4", "PCINT12"], ["I2C devices"], False),
            PinDefinition(28, "PC5/SCL", PinType.BIDIRECTIONAL, "I2C clock", None, None, ["ADC5", "PCINT13"], ["I2C devices"], False),

            # SPI
            PinDefinition(16, "PB2/SS", PinType.OUTPUT, "SPI slave select", None, None, ["PCINT2"], ["SPI devices"], False),
            PinDefinition(17, "PB3/MOSI", PinType.OUTPUT, "SPI data out", None, None, ["PCINT3"], ["SPI devices"], False),
            PinDefinition(18, "PB4/MISO", PinType.INPUT, "SPI data in", None, None, ["PCINT4"], ["SPI devices"], False),
            PinDefinition(19, "PB5/SCK", PinType.OUTPUT, "SPI clock", None, None, ["PCINT5"], ["SPI devices"], False),

            # GPIO (sample - full chip has 23 GPIO)
            PinDefinition(4, "PD2", PinType.BIDIRECTIONAL, "GPIO/INT0", None, 40.0, ["PCINT18"], ["General purpose"], False),
            PinDefinition(5, "PD3", PinType.BIDIRECTIONAL, "GPIO/INT1/PWM", None, 40.0, ["PCINT19", "OC2B"], ["General purpose"], False),
            PinDefinition(6, "PD4", PinType.BIDIRECTIONAL, "GPIO", None, 40.0, ["PCINT20"], ["General purpose"], False),
            PinDefinition(11, "PD5", PinType.BIDIRECTIONAL, "GPIO/PWM", None, 40.0, ["PCINT21", "OC0B"], ["General purpose"], False),
            PinDefinition(12, "PD6", PinType.BIDIRECTIONAL, "GPIO/PWM", None, 40.0, ["PCINT22", "OC0A"], ["General purpose"], False),
            PinDefinition(13, "PD7", PinType.BIDIRECTIONAL, "GPIO", None, 40.0, ["PCINT23"], ["General purpose"], False),
            PinDefinition(14, "PB0", PinType.BIDIRECTIONAL, "GPIO", None, 40.0, ["PCINT0"], ["General purpose"], False),
            PinDefinition(15, "PB1", PinType.BIDIRECTIONAL, "GPIO/PWM", None, 40.0, ["PCINT1", "OC1A"], ["General purpose"], False),

            # ADC
            PinDefinition(23, "PC0/ADC0", PinType.ANALOG, "Analog input 0", None, None, ["PCINT8"], ["Sensors"], False),
            PinDefinition(24, "PC1/ADC1", PinType.ANALOG, "Analog input 1", None, None, ["PCINT9"], ["Sensors"], False),
            PinDefinition(25, "PC2/ADC2", PinType.ANALOG, "Analog input 2", None, None, ["PCINT10"], ["Sensors"], False),
            PinDefinition(26, "PC3/ADC3", PinType.ANALOG, "Analog input 3", None, None, ["PCINT11"], ["Sensors"], False),

            # AREF
            PinDefinition(21, "AREF", PinType.INPUT, "ADC reference voltage", None, None, [], ["Filter capacitor"], False),
        ]

        self._pinouts["ATMEGA328P"] = ICPinout(
            part_number="ATMEGA328P",
            manufacturer="Microchip (Atmel)",
            description="8-bit AVR microcontroller (Arduino Uno)",
            package=PackageType.DIP,
            pin_count=28,
            pins=pins,
            common_variants=["ATMEGA328P-PU", "ATMEGA328P-AU", "ATMEGA328"],
            datasheet_url="https://ww1.microchip.com/downloads/en/DeviceDoc/ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf",
            notes="Most common Arduino microcontroller. Pin 1 has dot/notch indicator."
        )

    def _add_esp8266(self):
        """ESP8266 WiFi module (ESP-12E/F variant)."""
        pins = [
            # Power
            PinDefinition(1, "VCC", PinType.POWER, "Power supply (3.3V ONLY!)", 3.3, 300.0, [], ["3.3V regulator"], True),
            PinDefinition(9, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),

            # Critical boot pins
            PinDefinition(15, "GPIO0", PinType.BIDIRECTIONAL, "Boot mode select", 3.3, 12.0, ["Flash button"], ["Pull-up (flash mode=LOW)"], True),
            PinDefinition(2, "GPIO2", PinType.BIDIRECTIONAL, "Boot mode (must be HIGH)", 3.3, 12.0, ["Built-in LED"], ["Pull-up"], True),
            PinDefinition(3, "GPIO15", PinType.BIDIRECTIONAL, "Boot mode (must be LOW)", 3.3, 12.0, [], ["Pull-down"], True),

            # Enable/Reset
            PinDefinition(4, "EN/CH_PD", PinType.INPUT, "Chip enable (must be HIGH)", 3.3, None, [], ["Pull-up 10k"], True),
            PinDefinition(5, "RST", PinType.INPUT, "Reset (active LOW)", 3.3, None, [], ["Pull-up + reset button"], True),

            # UART
            PinDefinition(6, "TXD/GPIO1", PinType.OUTPUT, "UART transmit", 3.3, 12.0, ["Debug output"], ["USB serial RX"], False),
            PinDefinition(7, "RXD/GPIO3", PinType.INPUT, "UART receive", 3.3, 12.0, [], ["USB serial TX"], False),

            # SPI Flash (connected to external flash chip)
            PinDefinition(10, "GPIO6/SD_CLK", PinType.OUTPUT, "SPI flash clock (INTERNAL)", None, None, [], ["Flash chip"], True),
            PinDefinition(11, "GPIO7/SD_D0", PinType.BIDIRECTIONAL, "SPI flash data 0 (INTERNAL)", None, None, [], ["Flash chip"], True),
            PinDefinition(12, "GPIO8/SD_D1", PinType.BIDIRECTIONAL, "SPI flash data 1 (INTERNAL)", None, None, [], ["Flash chip"], True),
            PinDefinition(13, "GPIO11/SD_CMD", PinType.BIDIRECTIONAL, "SPI flash CMD (INTERNAL)", None, None, [], ["Flash chip"], True),

            # General GPIO
            PinDefinition(8, "GPIO4", PinType.BIDIRECTIONAL, "GPIO (safe to use)", 3.3, 12.0, ["I2C SDA"], ["General purpose"], False),
            PinDefinition(14, "GPIO5", PinType.BIDIRECTIONAL, "GPIO (safe to use)", 3.3, 12.0, ["I2C SCL"], ["General purpose"], False),
            PinDefinition(16, "GPIO12", PinType.BIDIRECTIONAL, "GPIO (MISO)", 3.3, 12.0, [], ["General purpose"], False),
            PinDefinition(17, "GPIO13", PinType.BIDIRECTIONAL, "GPIO (MOSI)", 3.3, 12.0, [], ["General purpose"], False),
            PinDefinition(18, "GPIO14", PinType.BIDIRECTIONAL, "GPIO (SCK)", 3.3, 12.0, [], ["General purpose"], False),
            PinDefinition(19, "GPIO16", PinType.BIDIRECTIONAL, "GPIO (deep sleep wake)", 3.3, 12.0, ["Connect to RST for wake"], ["General purpose"], False),

            # ADC
            PinDefinition(20, "ADC/TOUT", PinType.ANALOG, "Analog input (0-1V)", None, None, [], ["Voltage divider"], False),
        ]

        self._pinouts["ESP8266"] = ICPinout(
            part_number="ESP8266",
            manufacturer="Espressif",
            description="WiFi SoC module (ESP-12E/F)",
            package=PackageType.MODULE,
            pin_count=22,
            pins=pins,
            common_variants=["ESP-12E", "ESP-12F", "ESP-07", "ESP-01"],
            datasheet_url="https://www.espressif.com/sites/default/files/documentation/0a-esp8266ex_datasheet_en.pdf",
            notes="CRITICAL: 3.3V ONLY! 5V will destroy chip. GPIO6-11 connected to flash, don't use. Boot pins need correct pull-up/down."
        )

    def _add_esp32(self):
        """ESP32 WiFi+BT module (DevKit variant)."""
        pins = [
            # Power (ESP32 has multiple power pins)
            PinDefinition(1, "3V3", PinType.POWER, "Power supply (3.3V)", 3.3, 500.0, [], ["3.3V regulator"], True),
            PinDefinition(2, "EN", PinType.INPUT, "Chip enable", 3.3, None, [], ["Pull-up 10k"], True),
            PinDefinition(15, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),
            PinDefinition(38, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),

            # Critical boot pins
            PinDefinition(25, "GPIO0", PinType.BIDIRECTIONAL, "Boot mode (LOW=flash)", 3.3, 40.0, ["ADC2_CH1", "TOUCH1"], ["Pull-up"], True),

            # UART0 (programming)
            PinDefinition(34, "TXD0/GPIO1", PinType.OUTPUT, "UART0 TX (console)", 3.3, 40.0, [], ["USB serial RX"], False),
            PinDefinition(35, "RXD0/GPIO3", PinType.INPUT, "UART0 RX (console)", 3.3, 40.0, [], ["USB serial TX"], False),

            # Safe GPIO pins (commonly used)
            PinDefinition(30, "GPIO21", PinType.BIDIRECTIONAL, "GPIO (I2C SDA)", 3.3, 40.0, [], ["I2C devices"], False),
            PinDefinition(31, "GPIO22", PinType.BIDIRECTIONAL, "GPIO (I2C SCL)", 3.3, 40.0, [], ["I2C devices"], False),
            PinDefinition(29, "GPIO19", PinType.BIDIRECTIONAL, "GPIO (SPI MISO)", 3.3, 40.0, [], ["SPI devices"], False),
            PinDefinition(33, "GPIO23", PinType.BIDIRECTIONAL, "GPIO (SPI MOSI)", 3.3, 40.0, [], ["SPI devices"], False),
            PinDefinition(36, "GPIO18", PinType.BIDIRECTIONAL, "GPIO (SPI SCK)", 3.3, 40.0, [], ["SPI devices"], False),
            PinDefinition(24, "GPIO5", PinType.BIDIRECTIONAL, "GPIO (SPI CS)", 3.3, 40.0, [], ["SPI devices"], False),

            # ADC pins
            PinDefinition(4, "GPIO36/VP", PinType.ANALOG, "ADC1_CH0 (input only)", None, None, [], ["Sensors"], False),
            PinDefinition(5, "GPIO39/VN", PinType.ANALOG, "ADC1_CH3 (input only)", None, None, [], ["Sensors"], False),
            PinDefinition(6, "GPIO34", PinType.ANALOG, "ADC1_CH6 (input only)", None, None, [], ["Sensors"], False),
            PinDefinition(7, "GPIO35", PinType.ANALOG, "ADC1_CH7 (input only)", None, None, [], ["Sensors"], False),

            # Internal flash pins (DO NOT USE)
            PinDefinition(20, "GPIO6/SD_CLK", PinType.OUTPUT, "Flash clock (INTERNAL)", None, None, [], ["Flash chip"], True),
            PinDefinition(21, "GPIO7/SD_D0", PinType.BIDIRECTIONAL, "Flash data 0 (INTERNAL)", None, None, [], ["Flash chip"], True),
            PinDefinition(22, "GPIO8/SD_D1", PinType.BIDIRECTIONAL, "Flash data 1 (INTERNAL)", None, None, [], ["Flash chip"], True),
            PinDefinition(16, "GPIO9/SD_D2", PinType.BIDIRECTIONAL, "Flash data 2 (INTERNAL)", None, None, [], ["Flash chip"], True),
            PinDefinition(17, "GPIO10/SD_D3", PinType.BIDIRECTIONAL, "Flash data 3 (INTERNAL)", None, None, [], ["Flash chip"], True),
            PinDefinition(18, "GPIO11/SD_CMD", PinType.BIDIRECTIONAL, "Flash CMD (INTERNAL)", None, None, [], ["Flash chip"], True),
        ]

        self._pinouts["ESP32"] = ICPinout(
            part_number="ESP32",
            manufacturer="Espressif",
            description="WiFi+Bluetooth SoC module",
            package=PackageType.MODULE,
            pin_count=38,
            pins=pins,
            common_variants=["ESP32-WROOM-32", "ESP32-DevKitC", "ESP32-S2", "ESP32-C3"],
            datasheet_url="https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf",
            notes="CRITICAL: 3.3V ONLY! GPIO6-11 for flash (don't use). Some GPIO are input-only. Strapping pins affect boot."
        )

    def _add_lm7805(self):
        """LM7805 5V linear regulator."""
        pins = [
            PinDefinition(1, "INPUT", PinType.POWER, "Unregulated input (7-35V)", None, 1500.0, [], ["Input capacitor 10µF"], True),
            PinDefinition(2, "GROUND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),
            PinDefinition(3, "OUTPUT", PinType.POWER, "Regulated 5V output", 5.0, 1500.0, [], ["Output capacitor 100µF"], True),
        ]

        self._pinouts["LM7805"] = ICPinout(
            part_number="LM7805",
            manufacturer="Texas Instruments / STMicroelectronics",
            description="5V 1.5A linear voltage regulator",
            package=PackageType.TO220,
            pin_count=3,
            pins=pins,
            common_variants=["L7805", "MC7805", "UA7805"],
            datasheet_url="https://www.ti.com/lit/ds/symlink/lm340.pdf",
            notes="Gets HOT under load. Needs heatsink for >500mA. Input cap 10µF, output cap 100µF recommended. Pin order: IN-GND-OUT (facing flat side)."
        )

    def _add_ams1117(self):
        """AMS1117 3.3V LDO regulator (common on ESP boards)."""
        pins = [
            PinDefinition(1, "GND", PinType.GROUND, "Ground (tab also GND)", 0.0, None, [], ["Ground plane"], True),
            PinDefinition(2, "VOUT", PinType.POWER, "Regulated output (3.3V)", 3.3, 1000.0, [], ["Output cap 22µF"], True),
            PinDefinition(3, "VIN", PinType.POWER, "Unregulated input (4.5-15V)", None, 1000.0, [], ["Input cap 10µF"], True),
        ]

        self._pinouts["AMS1117"] = ICPinout(
            part_number="AMS1117-3.3",
            manufacturer="Advanced Monolithic Systems",
            description="3.3V 1A LDO regulator",
            package=PackageType.SOT23,
            pin_count=3,
            pins=pins,
            common_variants=["AMS1117-3.3", "AMS1117-5.0", "AMS1117-ADJ"],
            datasheet_url="http://www.advanced-monolithic.com/pdf/ds1117.pdf",
            notes="Extremely common on ESP8266/ESP32 boards. Tab is GND. Needs input/output caps (10µF/22µF). Gets warm under load."
        )

    def _add_ch340(self):
        """CH340 USB to serial chip (common on Arduino clones)."""
        pins = [
            PinDefinition(1, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),
            PinDefinition(4, "VCC", PinType.POWER, "Power supply (5V)", 5.0, 50.0, [], ["5V rail + 100nF cap"], True),

            # USB
            PinDefinition(5, "UD+", PinType.BIDIRECTIONAL, "USB D+", None, None, [], ["USB connector D+"], True),
            PinDefinition(6, "UD-", PinType.BIDIRECTIONAL, "USB D-", None, None, [], ["USB connector D-"], True),

            # UART
            PinDefinition(2, "TXD", PinType.OUTPUT, "UART transmit to MCU", 5.0, None, [], ["MCU RX pin"], False),
            PinDefinition(3, "RXD", PinType.INPUT, "UART receive from MCU", 5.0, None, [], ["MCU TX pin"], False),

            # Handshake
            PinDefinition(13, "CTS", PinType.INPUT, "Clear to send", 5.0, None, [], ["Optional handshake"], False),
            PinDefinition(14, "DSR", PinType.INPUT, "Data set ready", 5.0, None, [], ["Optional handshake"], False),
            PinDefinition(15, "RI", PinType.INPUT, "Ring indicator", 5.0, None, [], ["Optional handshake"], False),
            PinDefinition(16, "DCD", PinType.INPUT, "Data carrier detect", 5.0, None, [], ["Optional handshake"], False),
            PinDefinition(9, "DTR", PinType.OUTPUT, "Data terminal ready", 5.0, None, [], ["MCU reset via cap"], False),
            PinDefinition(10, "RTS", PinType.OUTPUT, "Request to send", 5.0, None, [], ["Optional handshake"], False),

            # Crystal
            PinDefinition(7, "XI", PinType.INPUT, "Crystal in (12MHz)", None, None, [], ["12MHz crystal"], True),
            PinDefinition(8, "XO", PinType.OUTPUT, "Crystal out", None, None, [], ["12MHz crystal"], True),

            # Config
            PinDefinition(11, "R232", PinType.INPUT, "RS232 mode select", 5.0, None, [], ["GND for TTL mode"], False),
        ]

        self._pinouts["CH340"] = ICPinout(
            part_number="CH340G",
            manufacturer="WCH (Jiangsu Qin Heng)",
            description="USB to UART bridge (Arduino clone)",
            package=PackageType.SOIC,
            pin_count=16,
            pins=pins,
            common_variants=["CH340G", "CH340C", "CH340E"],
            datasheet_url="https://cdn.sparkfun.com/datasheets/Dev/Arduino/Other/CH340DS1.PDF",
            notes="Common on cheap Arduino clones. Needs 12MHz crystal. DTR connected to MCU reset via 100nF cap for auto-reset."
        )

    def _add_cp2102(self):
        """CP2102 USB to serial (used on NodeMCU, some Arduinos)."""
        pins = [
            PinDefinition(1, "DCD", PinType.INPUT, "Data carrier detect", 3.3, None, [], ["Optional"], False),
            PinDefinition(2, "RI/CLK", PinType.INPUT, "Ring indicator", 3.3, None, [], ["Optional"], False),
            PinDefinition(3, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),
            PinDefinition(4, "D+", PinType.BIDIRECTIONAL, "USB D+", None, None, [], ["USB connector"], True),
            PinDefinition(5, "D-", PinType.BIDIRECTIONAL, "USB D-", None, None, [], ["USB connector"], True),
            PinDefinition(6, "VDD", PinType.POWER, "Power input (3.3V or 5V)", None, 100.0, [], ["USB 5V or 3.3V"], True),
            PinDefinition(7, "REGIN", PinType.POWER, "Regulator input (5V)", 5.0, None, [], ["USB 5V"], True),
            PinDefinition(8, "VBUS", PinType.INPUT, "USB bus sense", 5.0, None, [], ["USB 5V"], False),

            # UART
            PinDefinition(22, "TXD", PinType.OUTPUT, "UART transmit", 3.3, None, [], ["MCU RX"], False),
            PinDefinition(23, "RXD", PinType.INPUT, "UART receive", 3.3, None, [], ["MCU TX"], False),

            # Handshake
            PinDefinition(24, "RTS", PinType.OUTPUT, "Request to send", 3.3, None, [], ["Optional or MCU reset"], False),
            PinDefinition(25, "CTS", PinType.INPUT, "Clear to send", 3.3, None, [], ["Optional"], False),
            PinDefinition(26, "DSR", PinType.INPUT, "Data set ready", 3.3, None, [], ["Optional"], False),
            PinDefinition(27, "DTR", PinType.OUTPUT, "Data terminal ready", 3.3, None, [], ["Optional or MCU reset"], False),
        ]

        self._pinouts["CP2102"] = ICPinout(
            part_number="CP2102",
            manufacturer="Silicon Labs",
            description="USB to UART bridge (better quality)",
            package=PackageType.QFN,
            pin_count=28,
            pins=pins,
            common_variants=["CP2102", "CP2104"],
            datasheet_url="https://www.silabs.com/documents/public/data-sheets/CP2102-9.pdf",
            notes="Higher quality than CH340. No external crystal needed (internal oscillator). 3.3V I/O levels."
        )

    def _add_ft232(self):
        """FT232 USB to serial (high quality, used on official Arduino)."""
        pins = [
            # Power
            PinDefinition(4, "VCC", PinType.POWER, "Power supply (5V from USB)", 5.0, 50.0, [], ["USB 5V"], True),
            PinDefinition(7, "3V3OUT", PinType.POWER, "3.3V output (50mA max)", 3.3, 50.0, [], ["Decoupling cap"], False),
            PinDefinition(17, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),
            PinDefinition(18, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),
            PinDefinition(21, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),

            # USB
            PinDefinition(15, "USBDP", PinType.BIDIRECTIONAL, "USB D+", None, None, [], ["USB connector D+"], True),
            PinDefinition(16, "USBDM", PinType.BIDIRECTIONAL, "USB D-", None, None, [], ["USB connector D-"], True),

            # UART
            PinDefinition(1, "TXD", PinType.OUTPUT, "UART transmit", 3.3, None, [], ["MCU RX"], False),
            PinDefinition(5, "RXD", PinType.INPUT, "UART receive", 3.3, None, [], ["MCU TX"], False),

            # Handshake (used for MCU reset on Arduino)
            PinDefinition(2, "DTR", PinType.OUTPUT, "Data terminal ready", 3.3, None, [], ["MCU reset via 100nF"], False),
            PinDefinition(3, "RTS", PinType.OUTPUT, "Request to send", 3.3, None, [], ["Optional or GPIO0"], False),
            PinDefinition(6, "RI", PinType.INPUT, "Ring indicator", 3.3, None, [], ["Optional"], False),
            PinDefinition(9, "DSR", PinType.INPUT, "Data set ready", 3.3, None, [], ["Optional"], False),
            PinDefinition(10, "DCD", PinType.INPUT, "Data carrier detect", 3.3, None, [], ["Optional"], False),
            PinDefinition(11, "CTS", PinType.INPUT, "Clear to send", 3.3, None, [], ["Optional"], False),
        ]

        self._pinouts["FT232"] = ICPinout(
            part_number="FT232RL",
            manufacturer="FTDI",
            description="USB to UART bridge (official Arduino)",
            package=PackageType.SOIC,
            pin_count=28,
            pins=pins,
            common_variants=["FT232RL", "FT232R", "FT232H"],
            datasheet_url="https://ftdichip.com/wp-content/uploads/2020/08/DS_FT232R.pdf",
            notes="Gold standard USB-serial chip. Used on official Arduino Uno. DTR auto-reset via 100nF cap. 3.3V I/O."
        )

    def _add_atmega16u2(self):
        """ATmega16U2 USB-capable AVR (Arduino Uno USB chip)."""
        pins = [
            PinDefinition(3, "VCC", PinType.POWER, "Power supply (5V)", 5.0, None, [], ["5V rail"], True),
            PinDefinition(15, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),
            PinDefinition(31, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),

            # USB
            PinDefinition(4, "D+", PinType.BIDIRECTIONAL, "USB D+", None, None, [], ["USB connector D+"], True),
            PinDefinition(5, "D-", PinType.BIDIRECTIONAL, "USB D-", None, None, [], ["USB connector D-"], True),
            PinDefinition(6, "UGND", PinType.GROUND, "USB ground", 0.0, None, [], ["Ground plane"], True),
            PinDefinition(7, "UVCC", PinType.POWER, "USB power (5V)", 5.0, None, [], ["USB 5V + filter"], True),

            # UART to main MCU
            PinDefinition(20, "PD2/RXD1", PinType.INPUT, "UART receive from main MCU", None, None, [], ["ATmega328P TX"], False),
            PinDefinition(21, "PD3/TXD1", PinType.OUTPUT, "UART transmit to main MCU", None, None, [], ["ATmega328P RX"], False),

            # Programming (ISP)
            PinDefinition(10, "PB4/MISO", PinType.INPUT, "ISP MISO", None, None, [], ["ISP programmer"], False),
            PinDefinition(11, "PB5/MOSI", PinType.OUTPUT, "ISP MOSI", None, None, [], ["ISP programmer"], False),
            PinDefinition(12, "PB6/SCK", PinType.OUTPUT, "ISP SCK", None, None, [], ["ISP programmer"], False),

            # Reset
            PinDefinition(13, "RESET", PinType.INPUT, "Reset (active low)", 5.0, None, [], ["Pull-up"], True),
        ]

        self._pinouts["ATMEGA16U2"] = ICPinout(
            part_number="ATMEGA16U2",
            manufacturer="Microchip (Atmel)",
            description="USB-capable AVR (Arduino Uno USB chip)",
            package=PackageType.QFN,
            pin_count=32,
            pins=pins,
            common_variants=["ATMEGA16U2", "ATMEGA8U2"],
            datasheet_url="https://ww1.microchip.com/downloads/en/DeviceDoc/doc7799.pdf",
            notes="Acts as USB-serial bridge on Arduino Uno R3. Runs special firmware (Arduino-usbserial). Can be reprogrammed via ISP."
        )

    def _add_w25q32(self):
        """W25Q32 32Mbit SPI flash (common on ESP8266/ESP32)."""
        pins = [
            PinDefinition(1, "CS", PinType.INPUT, "Chip select (active low)", 3.3, None, [], ["MCU GPIO"], True),
            PinDefinition(2, "DO/IO1", PinType.BIDIRECTIONAL, "Data out (MISO)", 3.3, None, [], ["MCU MISO"], True),
            PinDefinition(3, "WP/IO2", PinType.BIDIRECTIONAL, "Write protect / IO2", 3.3, None, [], ["Pull-up or MCU"], False),
            PinDefinition(4, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),
            PinDefinition(5, "DI/IO0", PinType.BIDIRECTIONAL, "Data in (MOSI)", 3.3, None, [], ["MCU MOSI"], True),
            PinDefinition(6, "CLK", PinType.INPUT, "Clock", 3.3, None, [], ["MCU SCK"], True),
            PinDefinition(7, "HOLD/IO3", PinType.BIDIRECTIONAL, "Hold / IO3", 3.3, None, [], ["Pull-up or MCU"], False),
            PinDefinition(8, "VCC", PinType.POWER, "Power supply (3.3V)", 3.3, 25.0, [], ["3.3V + 100nF cap"], True),
        ]

        self._pinouts["W25Q32"] = ICPinout(
            part_number="W25Q32FVSSIG",
            manufacturer="Winbond",
            description="32Mbit (4MB) SPI flash memory",
            package=PackageType.SOIC,
            pin_count=8,
            pins=pins,
            common_variants=["W25Q32", "W25Q64", "W25Q128"],
            datasheet_url="https://www.winbond.com/resource-files/w25q32jv%20dtr%20revg%2003272018%20plus.pdf",
            notes="Common on ESP modules. Stores firmware/filesystem. Connected to ESP's SPI flash pins (GPIO6-11). Quad SPI capable."
        )

    def _add_mx25l3233f(self):
        """MX25L3233F 32Mbit SPI flash (alternative to W25Q32)."""
        pins = [
            PinDefinition(1, "CS", PinType.INPUT, "Chip select (active low)", 3.3, None, [], ["MCU GPIO"], True),
            PinDefinition(2, "SO/SIO1", PinType.BIDIRECTIONAL, "Serial out (MISO)", 3.3, None, [], ["MCU MISO"], True),
            PinDefinition(3, "WP/SIO2", PinType.BIDIRECTIONAL, "Write protect / IO2", 3.3, None, [], ["Pull-up"], False),
            PinDefinition(4, "GND", PinType.GROUND, "Ground", 0.0, None, [], ["Ground plane"], True),
            PinDefinition(5, "SI/SIO0", PinType.BIDIRECTIONAL, "Serial in (MOSI)", 3.3, None, [], ["MCU MOSI"], True),
            PinDefinition(6, "SCLK", PinType.INPUT, "Clock", 3.3, None, [], ["MCU SCK"], True),
            PinDefinition(7, "HOLD/SIO3", PinType.BIDIRECTIONAL, "Hold / IO3", 3.3, None, [], ["Pull-up"], False),
            PinDefinition(8, "VCC", PinType.POWER, "Power supply (3.3V)", 3.3, 30.0, [], ["3.3V + 100nF cap"], True),
        ]

        self._pinouts["MX25L3233F"] = ICPinout(
            part_number="MX25L3233F",
            manufacturer="Macronix",
            description="32Mbit (4MB) SPI flash memory",
            package=PackageType.SOIC,
            pin_count=8,
            pins=pins,
            common_variants=["MX25L3233F", "MX25L6433F", "MX25L12833F"],
            datasheet_url="https://www.macronix.com/Lists/Datasheet/Attachments/7426/MX25L3233F,%203V,%2032Mb,%20v1.6.pdf",
            notes="Alternative to Winbond W25Q series. Pin-compatible. Common on some ESP modules."
        )

    def get_pinout(self, part_number: str) -> Optional[ICPinout]:
        """Get pinout for a specific IC."""
        # Normalize part number
        part_normalized = part_number.upper().replace("-", "").replace("_", "")

        # Try exact match first
        if part_normalized in self._pinouts:
            return self._pinouts[part_normalized]

        # Try variants
        for pinout in self._pinouts.values():
            variants = [v.upper().replace("-", "").replace("_", "") for v in pinout.common_variants]
            if part_normalized in variants:
                return pinout

        return None

    def find_pin_by_name(self, part_number: str, pin_name: str) -> Optional[PinDefinition]:
        """Find a specific pin by name (e.g., 'VCC', 'GPIO0', 'TXD')."""
        pinout = self.get_pinout(part_number)
        if not pinout:
            return None

        pin_name_upper = pin_name.upper()
        for pin in pinout.pins:
            if pin_name_upper in pin.pin_name.upper():
                return pin

        return None

    def find_pins_by_type(self, part_number: str, pin_type: PinType) -> List[PinDefinition]:
        """Find all pins of a specific type."""
        pinout = self.get_pinout(part_number)
        if not pinout:
            return []

        return [pin for pin in pinout.pins if pin.pin_type == pin_type]

    def get_critical_pins(self, part_number: str) -> List[PinDefinition]:
        """Get all critical pins (chip won't work if damaged)."""
        pinout = self.get_pinout(part_number)
        if not pinout:
            return []

        return [pin for pin in pinout.pins if pin.critical]

    def get_programming_pins(self, part_number: str) -> List[PinDefinition]:
        """Get pins used for programming/flashing."""
        pinout = self.get_pinout(part_number)
        if not pinout:
            return []

        return [pin for pin in pinout.pins if pin.pin_type == PinType.PROGRAMMING]

    def search_by_component_name(self, component_name: str) -> Optional[ICPinout]:
        """Search for pinout by component detection name (e.g., 'Arduino-Uno' -> ATMEGA328P)."""
        mapping = {
            "ARDUINO-UNO": "ATMEGA328P",
            "ARDUINO": "ATMEGA328P",
            "ATMEGA328": "ATMEGA328P",
            "ESP8266": "ESP8266",
            "ESP-12": "ESP8266",
            "ESP12": "ESP8266",
            "ESP32": "ESP32",
            "NODEMCU": "ESP8266",
            "WEMOS": "ESP8266",
            "VOLTAGE-REGULATOR": "LM7805",  # Fallback
            "LM7805": "LM7805",
            "AMS1117": "AMS1117",
            "CH340": "CH340",
            "CP2102": "CP2102",
            "FT232": "FT232",
            "FLASH-MEMORY": "W25Q32",
            "W25Q": "W25Q32",
            "MX25L": "MX25L3233F",
        }

        component_normalized = component_name.upper().replace("-", "").replace("_", "")

        for key, part_number in mapping.items():
            if component_normalized in key or key in component_normalized:
                return self.get_pinout(part_number)

        return None

    def generate_wiring_instructions(self, ic1: str, pin1: str, ic2: str, pin2: str) -> str:
        """Generate human-readable wiring instructions."""
        pinout1 = self.get_pinout(ic1)
        pinout2 = self.get_pinout(ic2)

        if not pinout1 or not pinout2:
            return "ERROR: Unknown IC"

        pin_def1 = self.find_pin_by_name(ic1, pin1)
        pin_def2 = self.find_pin_by_name(ic2, pin2)

        if not pin_def1 or not pin_def2:
            return "ERROR: Unknown pin"

        return (
            f"Connect {pinout1.part_number} pin {pin_def1.pin_number} ({pin_def1.pin_name}) "
            f"to {pinout2.part_number} pin {pin_def2.pin_number} ({pin_def2.pin_name})"
        )


# Global singleton instance
pinout_database = PinoutDatabase()
