"""Stateless compile-only diagnostic packages derived from catalog device plans.

No project, interface authority, compiler or hardware is accessed here. The
verified/donor PlatformIO backend and its authorization gate are unchanged.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from typing import Any

from .device_plan import DevicePlanError, build_device_plan, module_library
from .firmware_scaffold import generate_i2c_diagnostic_source

SCHEMA = "hardware_splicer.device_firmware_proposal.v1"
PLATFORM = "espressif32@6.10.0"
BOUNDARY = "Compile-only proposal. No flashing, powering, measurements or physical authorization."


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_shared_i2c_bus(
    plan: dict[str, Any],
    *,
    bus_error: str = "diagnostic source requires exactly one explicitly wired shared I2C bus",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Trace I2C peripherals onto controller GPIOs and list declared address alternatives.

    Bindings map ``sda``/``scl`` to ``{module, pin_id, printed_name, gpio}``.
    Declarations keep library address alternatives and their basis; they are not
    chosen addresses or evidence of identity.
    """
    mcu = next(m for m in plan["modules"] if m["kind"] == "mcu_board")
    library = {m["id"]: m for m in module_library()["modules"]}
    pins = {(m["id"], p["id"]): p for m in plan["modules"] for p in m["logical_pins"]}
    adjacency: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for wire in plan["wires"]:
        a, b = ((wire[end]["module"], wire[end]["pin_id"]) for end in ("from", "to"))
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)

    def controller_for(node: tuple[str, str]) -> tuple[str, str]:
        seen, pending = set(), [node]
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            pending.extend(adjacency.get(current, set()) - seen)
        controllers = {n for n in seen if n[0] == mcu["id"] and "gpio" in pins[n]["roles"]}
        if len(controllers) != 1:
            raise DevicePlanError("each I2C signal needs exactly one explicitly connected controller GPIO")
        return controllers.pop()

    selected: dict[str, set[tuple[str, str]]] = {"sda": set(), "scl": set()}
    declarations = []
    for placed in plan["modules"]:
        entry = library[placed["module"]]
        if not entry.get("i2c"):
            continue
        for signal in selected:
            matches = [p for p in placed["logical_pins"] if f"i2c_{signal}" in p["roles"]]
            if len(matches) != 1:
                raise DevicePlanError("each peripheral must declare one data and one clock pin")
            selected[signal].add(controller_for((placed["id"], matches[0]["id"])))
        declarations.append({"module": placed["id"], "library_id": placed["module"],
                             "possible_addresses": entry["i2c"]["addresses"],
                             "basis": entry["i2c"]["address_basis"], "sources": placed["sources"]})
    if not declarations or any(len(nodes) != 1 for nodes in selected.values()):
        raise DevicePlanError(bus_error)
    bindings = {}
    for signal, nodes in selected.items():
        node = next(iter(nodes))
        pin = pins[node]
        match = re.fullmatch(r"IO(\d+)", pin["name"])
        if not match:
            raise DevicePlanError("the chosen GPIO has no supported numeric binding")
        bindings[signal] = {"module": node[0], "pin_id": node[1], "printed_name": pin["name"], "gpio": int(match[1])}
    if bindings["sda"]["gpio"] == bindings["scl"]["gpio"]:
        raise DevicePlanError("data and clock must use distinct GPIOs")
    return bindings, declarations


def build_device_firmware(spec: Any) -> tuple[dict[str, Any], bytes]:
    """Recompute from spec; never credit caller-supplied plan/findings/authority."""
    plan = build_device_plan(spec)
    try:
        spec_bytes = _json(spec)
    except (ValueError, TypeError, RecursionError) as exc:
        raise DevicePlanError("the spec must contain finite, JSON-compatible values") from exc
    blockers = [f for f in plan["findings"] if f["severity"] in {"error", "warning"}]
    if blockers:
        raise DevicePlanError("Resolve wiring checks before exporting diagnostic source: " + ", ".join(sorted({f["rule"] for f in blockers})))
    mcu = next(m for m in plan["modules"] if m["kind"] == "mcu_board")
    if mcu["module"] != "esp32-devkitc-v4":
        raise DevicePlanError("diagnostic source supports only the catalog ESP32-DevKitC V4")
    bindings, declarations = resolve_shared_i2c_bus(plan)

    source = generate_i2c_diagnostic_source(sda=bindings["sda"]["gpio"], scl=bindings["scl"]["gpio"],
                                          declared_addresses=[a for d in declarations for a in d["possible_addresses"]])
    files = {
        "src/main.cpp": source.encode(),
        "platformio.ini": f"[env:diagnostic]\nplatform = {PLATFORM}\nboard = esp32dev\nframework = arduino\nmonitor_speed = 115200\n".encode(),
        "DEVICE_SPEC.json": spec_bytes,
        "DEVICE_PLAN.json": _json(plan),
        "README.md": ("# Compile-only I2C diagnostic proposal\n\n" + BOUNDARY + "\n\n"
                      "Compile with PlatformIO Core 6.1.18: `pio run -e diagnostic`. Do not upload from this package.\n"
                      "Board profile esp32dev is a software compile target, not proof of exact hardware identity.\n"
                      "Review exact hardware, supplies, grounds and pull-ups separately before any physical operation.\n"
                      "No automatic scan: serial 's' requests a probe only after that separate review. This command is not an authorization gate.\n"
                      "Address probes drive the bus; they are not electrically inert or universally safe.\n"
                      "Declared addresses are alternatives, not readings or evidence of identity. An ACK is not a functional sensor test.\n"
                      "The package includes no binary and makes no compilation claim until a separate compiler result exists.\n").encode(),
    }
    metadata = {"schema_version": SCHEMA, "claim_boundary": BOUNDARY,
                "status": "COMPILE_ONLY_PROPOSAL", "compilation": "NOT_RUN", "physical_correctness": "UNPROVEN",
                "firmware_authorized": False, "power_on_authorized": False,
                "target": {"platform": PLATFORM, "board": "esp32dev", "framework": "arduino"},
                "pins": bindings, "declared_devices": declarations, "observations": [],
                "spec_sha256": _sha(files["DEVICE_SPEC.json"]), "plan_sha256": _sha(files["DEVICE_PLAN.json"]),
                "files": {name: {"sha256": _sha(data), "size_bytes": len(data)} for name, data in sorted(files.items())}}
    files["FIRMWARE_PROPOSAL.json"] = _json(metadata)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return metadata, output.getvalue()
