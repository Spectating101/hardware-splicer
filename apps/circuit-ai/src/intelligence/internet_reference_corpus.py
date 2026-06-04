"""Internet-sourced reference corpus for arbitrary-board authority growth.

These cases are intentionally public-reference only. They are useful for
training/evaluating visual intake, pinout extraction, and measurement planning,
but they must never grant measured repair authority without bench evidence.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


SCHEMA_VERSION = "internet_reference_corpus.v1"


def internet_dataset_sources() -> List[Dict[str, Any]]:
    """Return public sources that can feed the corpus without overclaiming authority."""

    return deepcopy(
        [
            {
                "source_id": "sparkfun_open_hardware",
                "name": "SparkFun open hardware repositories and product docs",
                "url": "https://github.com/sparkfun",
                "modality": ["schematic", "layout", "product_doc", "pinout"],
                "access": "public",
                "authority_use": ["reference_topology", "pinout_seed", "measurement_plan"],
                "limits": "Reference only; physical board revision and condition still require bench confirmation.",
            },
            {
                "source_id": "adafruit_pcb_design_files",
                "name": "Adafruit PCB design files and Learn pinouts",
                "url": "https://learn.adafruit.com/accessing-and-using-adafruit-pcb-design-files/overview",
                "modality": ["schematic", "layout", "product_doc", "pinout"],
                "access": "public",
                "authority_use": ["reference_topology", "resource_catalog", "measurement_plan"],
                "limits": "Reference only; Eagle/GitHub files do not prove the user's board is intact.",
            },
            {
                "source_id": "fpic",
                "name": "FICS PCB Image Collection",
                "url": "https://physicaldb.ece.ufl.edu/index.php/fics-pcb-image-collection-fpic/",
                "modality": ["pcb_photo", "component_annotation", "text_annotation"],
                "access": "registration_required",
                "authority_use": ["visual_candidate_training", "ocr_training", "component_detection_eval"],
                "limits": "Excellent visual corpus, but no direct repair/pinout authority without measurements.",
            },
            {
                "source_id": "pcb_component_detection",
                "name": "PCB Component Detection dataset",
                "url": "https://datasetninja.com/pcb-component-detection",
                "modality": ["pcb_photo", "component_bbox"],
                "access": "public_dataset",
                "authority_use": ["component_detection_eval", "salvage_visual_candidate_training"],
                "limits": "Component boxes support visual grounding, not electrical topology or safe reuse.",
            },
            {
                "source_id": "deeppcb_defects",
                "name": "DeepPCB and related PCB defect datasets",
                "url": "https://github.com/tangsanli5201/DeepPCB",
                "modality": ["defect_image", "defect_bbox", "template_pair"],
                "access": "public_dataset",
                "authority_use": ["defect_detection_eval", "hazard_visual_candidate_training"],
                "limits": "Mostly surface-defect inspection; not a functional repair/topology dataset.",
            },
            {
                "source_id": "open_repair_alliance",
                "name": "Open Repair Alliance repair attempts dataset",
                "url": "https://openrepair.org/open-data/downloads/",
                "modality": ["repair_record", "failure_mode", "outcome_prior"],
                "access": "public_dataset",
                "authority_use": ["failure_mode_prior", "repair_value_prior", "outcome_taxonomy"],
                "limits": "Strong repair priors, but no board-level topology or measurement evidence.",
            },
            {
                "source_id": "oshwa_api",
                "name": "OSHWA certified open source hardware API",
                "url": "https://certificationapi.oshwa.org/endpoints/",
                "modality": ["project_metadata", "documentation_link", "license_signal"],
                "access": "public_api",
                "authority_use": ["source_discovery", "documentation_discovery", "license_filtering"],
                "limits": "Discovery layer; docs must still be parsed and bench-gated.",
            },
        ]
    )


def internet_reference_cases() -> List[Dict[str, Any]]:
    """Return public-reference board cases that should remain evidence-gated."""

    cases = [
        _case(
            "sparkfun_ch340c_usb_serial_reference",
            "SparkFun CH340C USB-C serial breakout reference pinout",
            "https://www.sparkfun.com/sparkfun-serial-basic-breakout-ch340c-and-usb-c.html",
            "Use a CH340C USB-C serial adapter as a low-voltage UART debug/programming interface.",
            ["usb_serial", "connector", "power"],
            _board(
                components=[("u1", "CH340C USB-to-Serial bridge IC", "integrated_circuit"), ("u2", "AP2112 regulator", "regulator")],
                connectors=[("j1", "DTR/RXI/TXO/VCC/CTS/GND header", "header"), ("usb_c", "USB-C connector", "connector")],
                salvage="USB serial adapter reuse",
            ),
            [
                _connector(
                    "J1",
                    "SparkFun Serial Basic FTDI-style header",
                    [
                        ("1", "DTR", "dtr", None, None),
                        ("2", "RXI", "rxi", None, 3.3),
                        ("3", "TXO", "txo", None, 3.3),
                        ("4", "VCC", "vcc", 3.3, None),
                        ("5", "CTS", "cts", None, None),
                        ("6", "GND", "gnd", None, None),
                    ],
                )
            ],
        ),
        _case(
            "adafruit_bme280_sensor_reference",
            "Adafruit BME280 breakout I2C/SPI reference pinout",
            "https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout/pinouts",
            "Reuse a BME280 breakout as an environmental sensor module.",
            ["sensor_or_adc", "connector", "power"],
            _board(
                components=[("u1", "BME280 environmental sensor", "sensor")],
                connectors=[("j1", "VIN/GND/I2C/SPI header", "header")],
                salvage="I2C environmental sensor reuse",
            ),
            [
                _connector(
                    "J1",
                    "Adafruit BME280 breakout header",
                    [
                        ("VIN", "VIN", "vin", 3.3, None),
                        ("3VO", "3VO", "3v3", 3.3, None),
                        ("GND", "GND", "gnd", None, None),
                        ("SCK", "SCK/SCL", "i2c_scl", None, 3.3),
                        ("SDI", "SDI/SDA", "i2c_sda", None, 3.3),
                        ("SDO", "SDO", "spi_miso", None, 3.3),
                        ("CS", "CS", "spi_cs", None, 3.3),
                    ],
                )
            ],
        ),
        _case(
            "adafruit_drv8833_motor_driver_reference",
            "Adafruit DRV8833 motor driver breakout reference pinout",
            "https://learn.adafruit.com/adafruit-drv8833-dc-stepper-motor-driver-breakout-board/pinouts",
            "Reuse a DRV8833 breakout as a low-voltage dual motor driver.",
            ["actuator_driver", "motor_or_load", "power", "connector"],
            _board(
                components=[("u1", "DRV8833 dual motor driver", "motor_driver")],
                connectors=[("j1", "motor/control/power header", "header")],
                salvage="dual motor driver reuse",
            ),
            [
                _connector(
                    "J1",
                    "Adafruit DRV8833 breakout pins",
                    [
                        ("VMOTOR", "VMOTOR", "vin", None, None),
                        ("GND", "GND", "gnd", None, None),
                        ("AIN1", "AIN1", "ain1", None, 3.3),
                        ("AIN2", "AIN2", "ain2", None, 3.3),
                        ("BIN1", "BIN1", "bin1", None, 3.3),
                        ("BIN2", "BIN2", "bin2", None, 3.3),
                        ("SLP", "SLP", "slp", None, 3.3),
                        ("FLT", "FLT", "flt", None, 3.3),
                        ("AOUT1", "AOUT1", "aout1", None, None),
                        ("AOUT2", "AOUT2", "aout2", None, None),
                        ("BOUT1", "BOUT1", "bout1", None, None),
                        ("BOUT2", "BOUT2", "bout2", None, None),
                    ],
                )
            ],
        ),
        _case(
            "adafruit_mcp23017_gpio_reference",
            "Adafruit MCP23017 I2C GPIO expander reference pinout",
            "https://learn.adafruit.com/adafruit-mcp23017-i2c-gpio-expander/pinouts",
            "Reuse an MCP23017 board as an I2C GPIO expansion module.",
            ["i2c", "logic_io", "connector", "power"],
            _board(
                components=[("u1", "MCP23017 I2C GPIO expander", "integrated_circuit")],
                connectors=[("j1", "I2C/power/GPIO headers", "header")],
                salvage="GPIO expander reuse",
            ),
            [
                _connector(
                    "J1",
                    "MCP23017 I2C and GPIO pins",
                    [
                        ("VIN", "VIN", "vin", 3.3, None),
                        ("GND", "GND", "gnd", None, None),
                        ("SCL", "SCL", "i2c_scl", None, 3.3),
                        ("SDA", "SDA", "i2c_sda", None, 3.3),
                        ("RESET", "RESET", "enable", None, 3.3),
                        ("INTA", "INTA", "gpio", None, 3.3),
                        ("INTB", "INTB", "gpio", None, 3.3),
                        ("GPA0", "GPA0", "gpio", None, 3.3),
                        ("GPB0", "GPB0", "gpio", None, 3.3),
                    ],
                )
            ],
        ),
        _case(
            "sparkfun_qwiic_soil_moisture_reference",
            "SparkFun Qwiic Soil Moisture Sensor reference pinout",
            "https://learn.sparkfun.com/tutorials/qwiic-soil-moisture-sensor-hookup-guide/all",
            "Reuse a Qwiic soil moisture board as an I2C sensor input.",
            ["sensor_or_adc", "i2c", "connector", "power"],
            _board(
                components=[("u1", "capacitive soil moisture sensor front-end", "sensor")],
                connectors=[("qwiic", "Qwiic I2C connector", "connector")],
                salvage="Qwiic soil moisture sensor reuse",
            ),
            [
                _connector(
                    "J1",
                    "Qwiic I2C connector",
                    [
                        ("1", "GND", "gnd", None, None),
                        ("2", "3V3", "3v3", 3.3, None),
                        ("3", "SDA", "i2c_sda", None, 3.3),
                        ("4", "SCL", "i2c_scl", None, 3.3),
                    ],
                )
            ],
        ),
        _case(
            "sparkfun_qwiic_relay_reference",
            "SparkFun Qwiic Relay reference pinout",
            "https://learn.sparkfun.com/tutorials/qwiic-relay-hookup-guide/all",
            "Reuse a Qwiic relay board as a low-voltage switched-load module.",
            ["actuator_driver", "motor_or_load", "i2c", "connector", "power"],
            _board(
                components=[("k1", "relay", "relay"), ("u1", "I2C relay controller", "integrated_circuit")],
                connectors=[("qwiic", "Qwiic connector", "connector"), ("load", "NO/COM/NC terminal", "terminal")],
                salvage="I2C relay switched-load reuse",
            ),
            [
                _connector(
                    "J1",
                    "Qwiic control connector",
                    [
                        ("GND", "GND", "gnd", None, None),
                        ("3V3", "3V3", "3v3", 3.3, None),
                        ("SDA", "SDA", "i2c_sda", None, 3.3),
                        ("SCL", "SCL", "i2c_scl", None, 3.3),
                    ],
                ),
                _connector(
                    "J2",
                    "Relay load terminal",
                    [("NO", "NO", "load", None, None), ("COM", "COM", "load", None, None), ("NC", "NC", "load", None, None)],
                ),
            ],
        ),
        _case(
            "arduino_uno_rev3_headers_reference",
            "Arduino Uno Rev3 public header reference",
            "https://docs.arduino.cc/hardware/uno-rev3/",
            "Reuse an Arduino Uno-style board as a controller and GPIO host.",
            ["controller", "connector", "power", "logic_io"],
            _board(
                components=[("u1", "ATmega328P microcontroller", "microcontroller"), ("u2", "USB serial interface", "integrated_circuit")],
                connectors=[("power", "power header", "header"), ("digital", "digital GPIO header", "header"), ("analog", "analog input header", "header")],
                salvage="Arduino-compatible controller reuse",
            ),
            [
                _connector(
                    "POWER",
                    "Arduino Uno power header",
                    [("VIN", "VIN", "vin", None, None), ("5V", "5V", "5v", 5.0, None), ("3V3", "3V3", "3v3", 3.3, None), ("GND", "GND", "gnd", None, None)],
                ),
                _connector(
                    "DIGITAL",
                    "Arduino Uno digital header",
                    [("D0", "RXD", "rxd", None, 5.0), ("D1", "TXD", "txd", None, 5.0), ("D13", "SCK/LED", "gpio", None, 5.0)],
                ),
                _connector("ANALOG", "Arduino Uno analog header", [("A0", "A0", "gpio", None, 5.0), ("A4", "SDA", "i2c_sda", None, 5.0), ("A5", "SCL", "i2c_scl", None, 5.0)]),
            ],
        ),
        _case(
            "raspberry_pi_40pin_reference",
            "Raspberry Pi 40-pin GPIO public header reference",
            "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html",
            "Reuse a Raspberry Pi header as a controller-side GPIO and serial/I2C/SPI interface.",
            ["controller", "connector", "power", "logic_io", "i2c"],
            _board(
                components=[("soc", "Raspberry Pi application processor", "processor")],
                connectors=[("gpio", "40-pin GPIO header", "header")],
                salvage="GPIO controller interface reuse",
            ),
            [
                _connector(
                    "J8",
                    "Raspberry Pi 40-pin GPIO header subset",
                    [
                        ("1", "3V3", "3v3", 3.3, None),
                        ("2", "5V", "5v", 5.0, None),
                        ("3", "GPIO2/SDA", "i2c_sda", None, 3.3),
                        ("5", "GPIO3/SCL", "i2c_scl", None, 3.3),
                        ("6", "GND", "gnd", None, None),
                        ("8", "GPIO14/TXD", "txd", None, 3.3),
                        ("10", "GPIO15/RXD", "rxd", None, 3.3),
                        ("19", "GPIO10/MOSI", "mosi", None, 3.3),
                        ("21", "GPIO9/MISO", "miso", None, 3.3),
                        ("23", "GPIO11/SCLK", "sclk", None, 3.3),
                    ],
                )
            ],
        ),
        _case(
            "adafruit_powerboost_1000c_reference",
            "Adafruit PowerBoost 1000C charger/boost reference pinout",
            "https://learn.adafruit.com/adafruit-powerboost-1000c-load-share-usb-charge-boost/pinouts",
            "Evaluate a battery charger/boost board for reuse as a 5V supply module.",
            ["power", "battery", "connector"],
            _board(
                components=[("u1", "boost converter and LiPo charger", "power_management")],
                connectors=[("bat", "LiPo battery connector", "battery_connector"), ("out", "5V output pins", "header")],
                salvage="5V boost supply reuse after battery safety checks",
            ),
            [
                _connector(
                    "J1",
                    "PowerBoost power pins",
                    [
                        ("BAT", "BAT", "vin", None, None),
                        ("GND", "GND", "gnd", None, None),
                        ("5V", "5V", "5v", 5.0, None),
                        ("EN", "EN", "enable", None, 3.3),
                        ("LBO", "LBO", "fault", None, 3.3),
                    ],
                )
            ],
        ),
        _case(
            "adafruit_pam8302_audio_amp_reference",
            "Adafruit PAM8302 mono amplifier reference pinout",
            "https://learn.adafruit.com/adafruit-pam8302-mono-2-5w-class-d-audio-amplifier/pinouts",
            "Reuse a small Class-D amplifier board as an audio/load output module.",
            ["audio_output", "actuator_driver", "motor_or_load", "power", "connector"],
            _board(
                components=[("u1", "PAM8302 Class-D audio amplifier", "audio_amplifier")],
                connectors=[("in", "audio input pins", "header"), ("out", "speaker output pins", "terminal")],
                salvage="low-voltage audio amplifier reuse",
            ),
            [
                _connector(
                    "J1",
                    "PAM8302 input/output pins",
                    [
                        ("VIN", "VIN", "vin", 5.0, None),
                        ("GND", "GND", "gnd", None, None),
                        ("A+", "A+", "logic_input", None, None),
                        ("A-", "A-", "logic_input", None, None),
                        ("SPK+", "SPK+", "load", None, None),
                        ("SPK-", "SPK-", "load", None, None),
                    ],
                )
            ],
        ),
    ]
    return deepcopy(cases)


def _case(
    case_id: str,
    title: str,
    source_url: str,
    goal: str,
    capabilities: List[str],
    board_evidence: Dict[str, Any],
    connectors: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "case_id": case_id,
        "title": title,
        "source": {"url": source_url, "authority": "public_reference_only"},
        "payload": {
            "goal": goal,
            "target_authority_level": "production_repair",
            "strategy_mode": "constrained",
            "required_capabilities": capabilities,
            "board_evidence": board_evidence,
            "topology_evidence": {
                "schema_version": "topology_evidence.v1",
                "source": "public_reference_topology",
                "source_type": "public_reference_topology",
                "reference_uri": source_url,
                "connectors": connectors,
            },
            "use_reference_catalog": False,
        },
        "expected": {
            "reference_only": True,
            "measurement_plan_required": True,
            "can_use_measured_pinout": False,
            "can_use_electrical_simulation": False,
            "can_power_or_splice_now": False,
            "production_authorized": False,
        },
    }


def _board(
    *,
    components: List[tuple[str, str, str]],
    connectors: List[tuple[str, str, str]],
    salvage: str,
) -> Dict[str, Any]:
    return {
        "schema_version": "board_evidence.v1",
        "components": [{"id": item_id, "label": label, "kind": kind} for item_id, label, kind in components],
        "connectors": [{"id": item_id, "label": label, "kind": kind} for item_id, label, kind in connectors],
        "markings": [{"id": "m1", "label": label} for _, label, _ in components[:2]],
        "damage": [],
        "test_points": [],
        "salvage_candidates": [{"id": "s1", "label": salvage}],
    }


def _connector(ref: str, label: str, pins: List[tuple[str, str, str, float | None, float | None]]) -> Dict[str, Any]:
    return {
        "ref": ref,
        "label": label,
        "kind": "header",
        "pins": [
            {
                "pin": pin,
                "net": net,
                "role": role,
                **({"voltage": voltage} if voltage is not None else {}),
                **({"logic_voltage": logic_voltage} if logic_voltage is not None else {}),
            }
            for pin, net, role, voltage, logic_voltage in pins
        ],
    }
