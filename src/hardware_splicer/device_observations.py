"""Compare pasted bench output with a device plan's declared I2C addresses.

Stateless and read-only: no hardware, project or file is touched, and nothing is stored. The text is supplied by the
operator, so it is reported as operator-supplied; this module cannot tell whether it came from the planned hardware. An
acknowledge at an address is not a chip identity, a reading, or a check of supply, pull-ups or fit, and the result says
so. It changes no authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .device_plan import DevicePlanError, build_device_plan, module_library

SCHEMA = "hardware_splicer.device_bus_observation.v1"
MAX_TRANSCRIPT_CHARS = 48 * 1024
MAX_LINE_CHARS = 300
MAX_SCANS = 50

CLAIM_BOUNDARY = (
    "An acknowledge at an address shows that something answered there during one scan. It does not identify the chip, "
    "read a sensor, or check supply voltage, pull-ups, ground, the case or any other wiring. The text was supplied by "
    "the operator; this check cannot tell whether it came from the planned hardware."
)
NON_CLAIMS = [
    "A chip identity or part number.",
    "A sensor, display or clock reading.",
    "Supply voltage, pull-up value, ground or signal-level correctness.",
    "That the case fits, or that the build may be powered or used.",
    "That the text came from this hardware.",
]

_PREFIX = r"^(?:\s*(?:\[[^\]]{1,40}\]|\d{1,2}:\d{2}:\d{2}(?:[.,]\d{1,6})?)\s*(?:[>:-]\s*)?)?"
# These shapes are the diagnostic sketch's own output (firmware_scaffold.generate_i2c_diagnostic_source); a test keeps
# them in step with it.
_ACK = re.compile(_PREFIX + r"Observed ACK at 0x([0-9A-Fa-f]{2}); identity and function unverified\.\s*$")
_ERROR = re.compile(_PREFIX + r"Probe error (\d{1,3}) at 0x([0-9A-Fa-f]{2})\.\s*$")
_SUMMARY = re.compile(_PREFIX + r"Observed acknowledgements: (\d{1,3})\. No sensor readings or physical validation\.\s*$")
_INIT_FAILED = re.compile(_PREFIX + r"I2C initialization failed; no scan result\.\s*$")
_DECLARED = re.compile(_PREFIX + r"Declared possible addresses, NOT observations:((?: 0x[0-9A-Fa-f]{2})*)\s*$")
# These shapes are the application's own serial output (data/firmware_application/app_core.h); a test keeps them in step.
_BOOT = re.compile(_PREFIX + r"BOOT sensor=0x([0-9A-Fa-f]{2}) display=(?:0x([0-9A-Fa-f]{2})|NONE)\s*$")
_STATE = re.compile(
    _PREFIX + r"T=\d{1,10} STATE=(?:"
    r"(OK) TEMP_C=-?\d+\.\d{2} HUM_PCT=-?\d+\.\d PRES_HPA=-?\d+\.\d|"
    r"(STALE|FAULT_SENSOR_MISSING|FAULT_SENSOR_READ|FAULT_AMBIGUOUS_ADDRESS))\s*$"
)
_DISPLAY_MISSING = re.compile(_PREFIX + r"DISPLAY MISSING\s*$")
_RECOVERED = re.compile(_PREFIX + r"RECOVERED\s*$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
BME280_ID = "adafruit-bme280-stemma-qt"
SSD1306_ID = "ssd1306-096-i2c"


def _address(text: str) -> str:
    return f"0x{int(text, 16):02X}"


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate(transcript: Any) -> str:
    if not isinstance(transcript, str):
        raise DevicePlanError("the transcript must be text")
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        raise DevicePlanError(f"the transcript may be at most {MAX_TRANSCRIPT_CHARS} characters")
    if _CONTROL.search(transcript):
        raise DevicePlanError("the transcript contains control characters; paste the plain serial text")
    if any(len(line) > MAX_LINE_CHARS for line in transcript.splitlines()):
        raise DevicePlanError(f"a transcript line is longer than {MAX_LINE_CHARS} characters")
    return transcript


def _parse(transcript: str) -> tuple[list[dict[str, Any]], list[str] | None, int, dict[str, Any]]:
    """Split the text into scans. A scan is complete only when its summary line arrived and agrees with its lines.

    Lines the application prints are collected separately; the latest BOOT line is the one that counts.
    """

    scans: list[dict[str, Any]] = []
    declared: list[str] | None = None
    unrecognised = 0
    current: dict[str, Any] | None = None
    application: dict[str, Any] = {"boot": None, "states": {}, "latest_state": None, "display_missing": False, "recovered": False, "readings": 0}

    def open_scan() -> dict[str, Any]:
        return {"acknowledged": [], "errors": [], "complete": False, "consistent": False, "note": ""}

    def close(note: str, *, complete: bool, consistent: bool) -> None:
        nonlocal current
        assert current is not None
        current.update(complete=complete, consistent=consistent, note=note)
        scans.append(current)
        current = None

    for raw in transcript.splitlines():
        line = raw.strip()
        if not line:
            continue
        if (match := _DECLARED.match(line)):
            declared = sorted({_address(part) for part in match.group(1).split()})
            continue
        if (match := _ACK.match(line)):
            current = current or open_scan()
            address = _address(match.group(1))
            if address not in current["acknowledged"]:
                current["acknowledged"].append(address)
            continue
        if (match := _ERROR.match(line)):
            current = current or open_scan()
            current["errors"].append({"address": _address(match.group(2)), "code": int(match.group(1))})
            continue
        if (match := _SUMMARY.match(line)):
            current = current or open_scan()
            reported = int(match.group(1))
            if reported == len(current["acknowledged"]):
                close("", complete=True, consistent=True)
            else:
                close(
                    f"The scan's own total ({reported}) does not match the {len(current['acknowledged'])} acknowledge "
                    "lines pasted, so part of it is missing or altered.",
                    complete=True,
                    consistent=False,
                )
            continue
        if _INIT_FAILED.match(line):
            current = current or open_scan()
            close("The sketch reported that it could not start the I2C bus, so this scan has no result.", complete=False, consistent=False)
            continue
        if (match := _BOOT.match(line)):
            application["boot"] = {"sensor": _address(match.group(1)), "display": _address(match.group(2)) if match.group(2) else None}
            application["latest_state"] = None
            application["display_missing"] = match.group(2) is None
            continue
        if (match := _STATE.match(line)):
            state = match.group(1) or match.group(2)
            application["latest_state"] = state
            application["states"][state] = application["states"].get(state, 0) + 1
            if state == "OK":
                application["readings"] += 1
            continue
        if _DISPLAY_MISSING.match(line):
            application["display_missing"] = True
            continue
        if _RECOVERED.match(line):
            application["recovered"] = True
            continue
        unrecognised += 1
    if current is not None:
        close("The scan has no closing total line, so it may be cut short.", complete=False, consistent=False)
    return scans[-MAX_SCANS:], declared, unrecognised, application


def _application_row(library_id: str, addresses: list[str], application: dict[str, Any]) -> dict[str, Any] | None:
    """What the application's own serial output says about one module, or None when it says nothing about it."""

    boot = application["boot"]
    if library_id == BME280_ID:
        latest = application["latest_state"]
        if latest in {"FAULT_SENSOR_READ", "STALE"}:
            return {"status": "sensor_read_fault" if latest == "FAULT_SENSOR_READ" else "stale",
                    "acknowledged_at": [], "evidence": "application_fault",
                    "note": "The latest application state reports failed sensor readings; an earlier boot is not a current successful reading."}
        if latest == "FAULT_AMBIGUOUS_ADDRESS":
            return {"status": "ambiguous", "acknowledged_at": [], "evidence": "application_fault",
                    "note": "The latest application state reports more than one matching sensor address; an earlier boot does not resolve it."}
        if latest == "FAULT_SENSOR_MISSING":
            return {"status": "sensor_init_fault", "acknowledged_at": [], "evidence": "application_fault",
                    "note": "The application could not initialize a usable sensor. A chip may have answered but failed calibration; this does not establish absence. It cannot say why, and an earlier boot does not resolve it."}
        if boot and boot["sensor"] in addresses:
            return {"status": "acknowledged", "acknowledged_at": [boot["sensor"]], "evidence": "application_chip_id_match",
                    "note": f"The application reported that a chip identified itself as a BME280 (register 0xD0 read 0x60) at {boot['sensor']}."}
        return None
    if library_id == SSD1306_ID:
        if boot and boot["display"] in addresses:
            return {"status": "acknowledged", "acknowledged_at": [boot["display"]], "evidence": "application_presence_check",
                    "note": f"The application's presence check found something at {boot['display']}. That is an acknowledge, not a display identity."}
        if application["display_missing"] or (boot and boot["display"] is None):
            return {"status": "no_acknowledge", "acknowledged_at": [], "evidence": "application_fault",
                    "note": "The application reported the display missing: nothing acknowledged at any declared address."}
    return None


def check_device_observations(spec: Any, transcript: Any) -> dict[str, Any]:
    """Recompute the plan from the spec, then compare the pasted scan with each module's declared addresses."""

    plan = build_device_plan(spec)
    try:
        spec_bytes = _json(spec)
    except (ValueError, TypeError, RecursionError) as exc:
        raise DevicePlanError("the spec must contain finite, JSON-compatible values") from exc
    text = _validate(transcript)
    library = {m["id"]: m for m in module_library()["modules"]}
    declared_by_module = {
        placed["id"]: (placed, [a.upper().replace("0X", "0x") for a in library[placed["module"]]["i2c"]["addresses"]])
        for placed in plan["modules"]
        if library[placed["module"]].get("i2c")
    }
    declared_everywhere = sorted({a for _placed, addresses in declared_by_module.values() for a in addresses})
    users: dict[str, list[str]] = {}
    for module_id, (_placed, addresses) in declared_by_module.items():
        for address in addresses:
            users.setdefault(address, []).append(module_id)

    scans, declared_in_text, unrecognised, application = _parse(text)
    app_seen = bool(application["boot"] or application["states"] or application["display_missing"])
    usable = [index for index, scan in enumerate(scans) if scan["complete"] and scan["consistent"]]
    used = usable[-1] if usable else None
    acks = set(scans[used]["acknowledged"]) if used is not None else set()
    errors = {row["address"] for row in scans[used]["errors"]} if used is not None else set()
    stable = None
    if len(usable) > 1:
        stable = len({tuple(sorted(scans[i]["acknowledged"])) for i in usable}) == 1

    modules = []
    for module_id, (placed, addresses) in declared_by_module.items():
        row: dict[str, Any] = {"id": module_id, "module": placed["module"], "name": placed.get("name") or library[placed["module"]]["name"],
                               "declared_addresses": addresses, "acknowledged_at": [], "status": "not_assessed", "note": ""}
        if used is None:
            row["note"] = "No complete scan was found, so nothing is concluded for this module."
        else:
            hit = [a for a in addresses if a in acks]
            row["acknowledged_at"] = hit
            if len(hit) > 1:
                row.update(status="ambiguous", note="More than one of this module's declared addresses answered. "
                           "That can mean two devices, or one that answers at both; this scan cannot tell which.")
            elif len(hit) == 1 and len(users[hit[0]]) > 1:
                others = ", ".join(sorted(set(users[hit[0]]) - {module_id}))
                row.update(status="shared_address", note=f"{hit[0]} answered, but {others} declares the same address, "
                           "so this scan cannot say which module answered.")
            elif len(hit) == 1:
                row.update(status="acknowledged", note=f"Something answered at {hit[0]}, an address this module declares.")
            elif any(a in errors for a in addresses):
                row.update(status="bus_error", note="The scan reported an I2C error at one of this module's declared "
                           "addresses and no acknowledge at any, so absence is not established.")
            else:
                row.update(status="no_acknowledge", note="Nothing answered at any address this module declares. This scan "
                           "cannot say why: wiring, power, an address setting or a different module are all possible.")
        from_app = _application_row(placed["module"], addresses, application) if app_seen else None
        if from_app is not None:
            row["application"] = {"status": from_app["status"], "acknowledged_at": from_app["acknowledged_at"],
                                  "evidence": from_app["evidence"], "note": from_app["note"]}
            if row["status"] == "not_assessed":
                row.update(status=from_app["status"], acknowledged_at=from_app["acknowledged_at"], note=from_app["note"],
                           evidence=from_app["evidence"])
            elif row["status"] != from_app["status"] or sorted(row["acknowledged_at"]) != sorted(from_app["acknowledged_at"]):
                row["note"] += f" The application's own output differs: {from_app['note']}"
                row["application"]["agrees"] = False
            else:
                row["application"]["agrees"] = True
        modules.append(row)

    unexpected = sorted(a for a in acks if a not in users)
    statuses = {row["status"] for row in modules}
    assessed = used is not None or any(row["status"] != "not_assessed" for row in modules)
    if not assessed or not modules:
        consistent = None
        statement = "No complete scan was found, so nothing is concluded about the wiring."
    elif any(row.get("application", {}).get("agrees") is False for row in modules):
        consistent = False
        statement = "The scan and the application's output disagree. An earlier successful scan does not resolve a later fault."
    elif statuses <= {"acknowledged"}:
        consistent = True
        statement = "Every module with declared addresses has something answering at one of them. That is all this scan shows."
    elif statuses & {"no_acknowledge", "ambiguous", "bus_error", "sensor_init_fault", "sensor_read_fault", "stale"}:
        consistent = False
        statement = "The scan differs from the plan for at least one module. See each module below; the scan cannot say why."
    else:
        consistent = None
        statement = "An address is shared between modules, so this scan cannot attribute every acknowledge."

    metadata_only = {
        "schema_version": SCHEMA,
        "provenance": "operator_supplied_text",
        "claim_boundary": CLAIM_BOUNDARY,
        "non_claims": NON_CLAIMS,
        "spec_sha256": _sha(spec_bytes),
        "plan_sha256": _sha(_json(plan)),
        "transcript_sha256": _sha(text.encode("utf-8")),
        "scans": [{"index": index, **scan} for index, scan in enumerate(scans)],
        "scan_used": used,
        "scans_stable": stable,
        "declared_addresses_in_transcript": declared_in_text,
        "declared_addresses_match_plan": (declared_in_text == declared_everywhere) if declared_in_text is not None else None,
        "unrecognised_lines": unrecognised,
        "modules": modules,
        "unexpected_acknowledgements": unexpected,
        "application": application if app_seen else None,
        "summary": {"assessed": assessed, "consistent_with_declared_addresses": consistent, "statement": statement},
        "firmware_authorized": False,
        "power_on_authorized": False,
        "physical_correctness": "UNPROVEN",
    }
    return metadata_only
