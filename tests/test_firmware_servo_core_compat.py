"""The generated servo sketch must build on both generations of the ESP32 Arduino core.

arduino-esp32 2.x configures PWM with ledcSetup + ledcAttachPin and writes by channel. 3.x removed
those two, attaches with ledcAttach(pin, freq, resolution) and writes by pin. Each stub header below
declares only what that generation really provides, so a call to the other generation's API fails to
compile, as it does with the real toolchain (checked against cores 2.0.17 and 3.3.12).
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.firmware_scaffold import generate_firmware_scaffold

COMMON = """
#pragma once
#include <stdint.h>
#include <stddef.h>
struct SerialClass { void begin(unsigned long); int printf(const char*, ...); };
extern SerialClass Serial;
void delay(unsigned long);
"""
CORE_API = {
    2: """
#define ESP_ARDUINO_VERSION_MAJOR 2
double ledcSetup(uint8_t channel, double freq, uint8_t resolution_bits);
void ledcAttachPin(uint8_t pin, uint8_t channel);
void ledcWrite(uint8_t channel, uint32_t duty);
""",
    3: """
#define ESP_ARDUINO_VERSION_MAJOR 3
bool ledcAttach(uint8_t pin, uint32_t freq, uint8_t resolution);
bool ledcWrite(uint8_t pin, uint32_t duty);
""",
}

pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="g++ is needed to check the sketch syntax")


def _sketch() -> str:
    graph = compose_build_graph_from_module_ids(["esp32-devkit", "sg90", "sg90", "usb-power-5v"])["graph"]
    return generate_firmware_scaffold(build_id="generic_low_voltage_build", build_graph=graph)["source"]


def _compile(tmp_path, core: int, source: str) -> subprocess.CompletedProcess:
    include = tmp_path / f"core{core}"
    include.mkdir(exist_ok=True)
    (include / "Arduino.h").write_text(COMMON + CORE_API[core])
    sketch = tmp_path / f"sketch{core}_{abs(hash(source))}.cpp"
    sketch.write_text(source)
    return subprocess.run(
        ["g++", "-std=c++17", "-fsyntax-only", f"-I{include}", str(sketch)], capture_output=True, text=True
    )


@pytest.mark.parametrize("core", [2, 3])
def test_the_generated_servo_sketch_builds_against_each_core_generation(tmp_path, core) -> None:
    result = _compile(tmp_path, core, _sketch())

    assert result.returncode == 0, result.stderr


def test_the_stub_for_each_core_really_rejects_the_other_generations_calls(tmp_path) -> None:
    old_api = "#include <Arduino.h>\nvoid f(){ ledcSetup(0, 50, 16); ledcAttachPin(15, 0); }\n"
    new_api = "#include <Arduino.h>\nvoid f(){ ledcAttach(15, 50, 16); }\n"

    assert _compile(tmp_path, 2, old_api).returncode == 0
    assert _compile(tmp_path, 3, old_api).returncode != 0
    assert _compile(tmp_path, 3, new_api).returncode == 0
    assert _compile(tmp_path, 2, new_api).returncode != 0


def test_the_serial_line_ends_with_a_newline_escape_not_a_literal_backslash_n() -> None:
    [line] = [row for row in _sketch().splitlines() if "Serial.printf" in row]

    assert line.endswith('\\n", PAN_PIN, TILT_PIN);')
    assert "\\\\n" not in line
