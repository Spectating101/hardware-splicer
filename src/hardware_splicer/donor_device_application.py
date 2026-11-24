"""HS-owned passive input proposal templates; no firmware or physical authorization."""
from __future__ import annotations

import re
from pathlib import Path

from .device_firmware import _json, _sha
from .device_plan import DevicePlanError, module_library

ROOT = Path(__file__).resolve().parent / "data" / "firmware_application" / "donor"
DONOR_SCENARIOS = (
    "input_pullups", "released_boot", "held_boot", "bounce_press", "bounce_release",
    "held_no_repeat", "independent_inputs", "clock_wrap", "no_short_pulse", "restart_requires_settle",
)
BOUNDARY = (
    "Generated passive input adapter executed against a digital GPIO/clock shim. "
    "Not electrical validation, real GPIO-driver timing, physical debounce or a hardware test. "
    "Does not authorize flashing or power-on."
)


def donor_input_files(plan: dict, donor_modules: dict) -> tuple[dict, dict[str, bytes]]:
    """Bind only canonical planned controller pins to the frozen switch contacts."""
    board = next(m for m in plan["modules"] if m["kind"] == "mcu_board")
    catalog = next(m for m in module_library()["modules"] if m["id"] == board["module"])
    pins = {p["id"]: p for p in catalog["pins"]}
    inputs = []
    for placed in sorted((m for m in plan["modules"] if m["kind"] == "donor_passive"), key=lambda m: m["id"]):
        entry = donor_modules[placed["module"]]
        for signal in sorted(entry["donor_evidence"]["signals"], key=lambda s: s["name"]):
            if signal["protocol"]["value"] == "ground_reference":
                continue
            ends = []
            for wire in plan["wires"]:
                for a, b in ((wire["from"], wire["to"]), (wire["to"], wire["from"])):
                    if a["module"] == placed["id"] and a["pin_id"] == signal["name"]:
                        ends.append(b)
            if len(ends) != 1 or ends[0]["module"] != board["id"]:
                raise DevicePlanError("each donor input needs exactly one direct controller connection")
            pin = pins[ends[0]["pin_id"]]
            match = re.fullmatch(r"(?:IO|GP)(\d+)", pin["name"])
            if not match:
                raise DevicePlanError("donor input has no supported numeric GPIO binding")
            inputs.append({"index": len(inputs), "module": placed["id"], "donor_id": placed["module"],
                "signal": signal["name"], "contact_id": signal["contact_id"],
                "controller_pin_id": pin["id"], "printed_name": pin["name"], "gpio": int(match[1]),
                "frozen_donor_sha256": _sha(_json(entry["donor_evidence"])),
                "active_level": "low", "protocol": "switch_to_ground",
                "evidence_ids": sorted({eid for field in ("protocol", "controller_pin", "active_level", "voltage_max_v")
                                        for eid in signal[field]["evidence_ids"]})})
    if not inputs or len({i["gpio"] for i in inputs}) != len(inputs):
        raise DevicePlanError("donor inputs require distinct controller GPIOs")
    manifest = {"schema_version": "hardware_splicer.donor_input_proposal.v1", "inputs": inputs,
        "status": "PROPOSED", "behavior": "serial state reports, alongside the existing sensor monitor",
        "input_mode": "INPUT_PULLUP", "debounce_ms": 20,
        "assumptions": ["Internal pull-up selection and 20 ms sampled debounce are software design proposals, not measured donor facts.",
                        "Only sampled levels are checked; pulses between polls and electrical bounce are not measured.",
                        "Reports use stable numeric input indices; this manifest maps indices to frozen donor identities.",
                        "Open wire and released contact both read high; no continuity or stuck-contact diagnosis is claimed."],
        "claim_boundary": BOUNDARY, "physical_correctness": "UNPROVEN",
        "firmware_authorized": False, "power_on_authorized": False}
    mapping = {"PINS": ", ".join(str(i["gpio"]) for i in inputs), "COUNT": str(len(inputs))}
    files = {"DONOR_INPUTS.json": _json(manifest)}
    for source, target in (("donor_inputs.h", "src/donor_inputs.h"), ("Arduino.h", "test/donor_host/Arduino.h"),
                           ("harness.cpp", "test/donor_host/harness.cpp")):
        text = (ROOT / source).read_text()
        for key, value in mapping.items():
            text = text.replace("{{" + key + "}}", value)
        files[target] = text.encode()
    return manifest, files


def attach_donor_adapter(main: str) -> str:
    """Inject fixed HS calls, never source supplied in a spec or contract."""
    replacements = {
        '#include "app_core.h"': '#include "app_core.h"\n#include "donor_inputs.h"',
        "    Serial.begin(115200);": "    Serial.begin(115200);\n    hs_donor::begin();",
        "    g_app->loop_once();": "    hs_donor::tick();\n    g_app->loop_once();",
    }
    for old, new in replacements.items():
        if main.count(old) != 1:
            raise DevicePlanError("unsupported application adapter layout for donor inputs")
        main = main.replace(old, new)
    return main
