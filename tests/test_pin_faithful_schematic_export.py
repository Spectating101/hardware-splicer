from __future__ import annotations

import re
from pathlib import Path

from hardware_splicer.electronics_foundation_benchmark import load_electronics_bundle
from hardware_splicer.integrations.schematic_export import netlist_to_kicad_schematic
from hardware_splicer.netlist import CircuitNetlist

_BUNDLE = Path("experiments/electronics/esp32_hcsr04_level_shift_gpt56_sol.json")


def _safe_netlist() -> CircuitNetlist:
    bundle = load_electronics_bundle(_BUNDLE)
    return CircuitNetlist.from_dict(bundle["translated_design"])


def test_generated_schematic_embeds_real_catalog_pin_numbers_and_instances() -> None:
    text = netlist_to_kicad_schematic(_safe_netlist())

    assert '(number "GPIO16")' in text
    assert '(number "ECHO")' in text
    assert '(number "HV2")' in text
    assert re.search(r'\(pin "GPIO16" \(uuid "[0-9a-f-]+"\)\)', text)
    assert re.search(r'\(pin "ECHO" \(uuid "[0-9a-f-]+"\)\)', text)
    assert 'HSNET:U1_esp32_devkit' in text
    assert 'HSNET:S1_hc_sr04' in text


def test_generated_schematic_preserves_electrical_pin_types() -> None:
    text = netlist_to_kicad_schematic(_safe_netlist())

    # Catalog roles become KiCad electrical types rather than generic passive pins.
    assert re.search(r'\(pin output line .*\(name "ECHO" .*\(number "ECHO"\)\)', text)
    # GPIO16 is intentionally specialized as uart_rx in the persisted catalog, so the
    # exporter must preserve it as an input rather than broadening it back to digital_io.
    assert re.search(r'\(pin input line .*\(name "GPIO16 / RX2" .*\(number "GPIO16"\)\)', text)
    assert re.search(r'\(pin power_out line .*\(name "3V3" .*\(number "3V3"\)\)', text)
    assert re.search(r'\(pin power_in line .*\(name "VIN" .*\(number "VIN"\)\)', text)


def test_net_labels_attach_to_exact_pin_stubs_and_unused_signal_pins_get_no_connects() -> None:
    text = netlist_to_kicad_schematic(_safe_netlist())

    assert '(label "ECHO_5V"' in text
    assert '(label "ECHO_3V3"' in text
    assert '(label "TRIG_3V3"' in text
    assert '(label "TRIG_5V"' in text
    assert text.count("(no_connect") > 0
