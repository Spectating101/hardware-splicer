"""Per-part descriptors rendered into the generated application's part-specific headers.

A descriptor states what is specific to one I2C part: its addresses, whether it can identify itself,
the channels it reports with their plausible ranges, and where each claim comes from. Everything else
(the fault-handling engine and the host fault scenarios) is generic and reads the two generated
headers. A descriptor is a cited extract, not evidence: it stays ``UNREVIEWED_EXTRACT`` until a person
reviews it, and nothing here changes any authority flag.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

SCHEMA = "hardware_splicer.part_descriptor.v1"
PARTS_DIR = Path(__file__).resolve().parent / "data" / "parts"
REVIEW_STATES = {"UNREVIEWED_EXTRACT"}

_ADDRESS = re.compile(r"^0x[0-9A-F]{2}$")
_SHORT = re.compile(r"^[a-z][a-z0-9_]{0,15}$")
_KEY = re.compile(r"^[A-Z][A-Z0-9_]{0,15}$")
_CONST = re.compile(r"^k[A-Za-z0-9]{1,24}$")
_WORD = re.compile(r"^[A-Za-z][A-Za-z ]{0,23}$")
_UNIT = re.compile(r"^(%|[A-Za-z]{1,8})$")
_SERIAL_FORMAT = re.compile(r"^%\.([1-9])f$")
_DISPLAY_FORMAT = re.compile(r"^%\.[1-9]f( (%%|[A-Za-z]{1,8}))?$")
_MARKER = re.compile(r"^[ A-Za-z%]{1,8}$")
_NO_BREAK = re.compile(r"^[^\r\n]{1,400}$")


class PartDescriptorError(ValueError):
    """A part descriptor is malformed or unsafe to render into generated source."""


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise PartDescriptorError(message)


def _text(value: Any, label: str, pattern: re.Pattern = _NO_BREAK) -> str:
    _need(isinstance(value, str) and bool(pattern.match(value)), f"{label} is missing or not allowed")
    return value


def _number(value: Any, label: str) -> float:
    _need(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value), f"{label} must be a finite number")
    return float(value)


def validate_part(part: Any) -> dict[str, Any]:
    _need(isinstance(part, dict), "a part descriptor must be an object")
    _need(part.get("schema_version") == SCHEMA, "unsupported part descriptor schema")
    _text(part.get("library_id"), "library_id", re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$"))
    _text(part.get("chip"), "chip", re.compile(r"^[A-Za-z0-9]{2,16}$"))
    _need(part.get("review_status") in REVIEW_STATES, "review_status must be UNREVIEWED_EXTRACT")
    addresses = part.get("addresses")
    _need(isinstance(addresses, list) and len(addresses) == 2, "exactly two declared addresses are supported")
    for address in addresses:
        _need(isinstance(address, str) and bool(_ADDRESS.match(address)) and int(address, 16) < 0x80, "addresses must be 7-bit values like 0x23")
    _need(addresses[0] != addresses[1], "the two addresses must differ")
    identity = part.get("identity")
    if identity is not None:
        _need(isinstance(identity, dict), "identity must be null or an object")
        _text(identity.get("register"), "identity.register", _ADDRESS)
        _text(identity.get("value"), "identity.value", _ADDRESS)
        _text(identity.get("citation"), "identity.citation")
    else:
        _text(part.get("identity_note"), "identity_note")
    _text(part.get("bounds_citation"), "bounds_citation")
    channels = part.get("channels")
    _need(isinstance(channels, list) and 1 <= len(channels) <= 3, "one to three channels are supported")
    seen: set[tuple[str, str]] = set()
    for index, channel in enumerate(channels):
        _need(isinstance(channel, dict), f"channel {index} must be an object")
        _text(channel.get("short"), f"channel {index} short", _SHORT)
        _text(channel.get("field"), f"channel {index} field", _SHORT)
        _text(channel.get("key"), f"channel {index} key", _KEY)
        _text(channel.get("label"), f"channel {index} label", _WORD)
        _text(channel.get("unit"), f"channel {index} unit", _UNIT)
        _text(channel.get("serial_format"), f"channel {index} serial_format", _SERIAL_FORMAT)
        _text(channel.get("display_format"), f"channel {index} display_format", _DISPLAY_FORMAT)
        _text(channel.get("display_marker"), f"channel {index} display_marker", _MARKER)
        _text(channel.get("min_const"), f"channel {index} min_const", _CONST)
        _text(channel.get("max_const"), f"channel {index} max_const", _CONST)
        low, high = _number(channel.get("min"), "min"), _number(channel.get("max"), "max")
        good, probe = _number(channel.get("good"), "good"), _number(channel.get("out_of_range_probe"), "out_of_range_probe")
        _need(low < high, f"channel {index} needs min < max")
        _need(low <= good <= high, f"channel {index} fixture reading must lie inside its range")
        _need(probe < low or probe > high, f"channel {index} out_of_range_probe must lie outside its range")
        # Each name must be unique within its own namespace across channels; short and field may coincide.
        for namespace, name in (("short", channel["short"]), ("field", channel["field"]), ("key", channel["key"]),
                                ("const", channel["min_const"]), ("const", channel["max_const"])):
            _need((namespace, name) not in seen, f"duplicate {namespace} name {name}")
            seen.add((namespace, name))
    adapter = part.get("adapter")
    _need(isinstance(adapter, dict), "adapter is required")
    _text(adapter.get("template"), "adapter.template", re.compile(r"^[a-z0-9_]+\.cpp\.tmpl$"))
    _text(adapter.get("driver"), "adapter.driver")
    libs = adapter.get("lib_deps")
    _need(isinstance(libs, list) and bool(libs), "adapter.lib_deps must list the PlatformIO dependencies")
    for lib in libs:
        _text(lib, "adapter.lib_deps entry", re.compile(r"^[A-Za-z0-9_./ -]{1,60} @ [0-9]+\.[0-9]+\.[0-9]+$"))
    _need(isinstance(adapter.get("vendor_host"), bool), "adapter.vendor_host must be a boolean")
    return part


def available_parts() -> dict[str, dict[str, Any]]:
    parts: dict[str, dict[str, Any]] = {}
    for path in sorted(PARTS_DIR.glob("*.json")):
        part = validate_part(json.loads(path.read_text(encoding="utf-8")))
        _need(part["library_id"] not in parts, f"duplicate part {part['library_id']}")
        parts[part["library_id"]] = part
    return parts


def load_part(library_id: str) -> dict[str, Any]:
    try:
        return available_parts()[library_id]
    except KeyError:
        raise PartDescriptorError(f"no part descriptor for {library_id}") from None


def _lit(value: float) -> str:
    text = repr(float(value))
    _need("e" not in text and "inf" not in text and "nan" not in text, "numbers must render as plain decimals")
    return text + "f"


def _fmt(format_text: str, value: float) -> str:
    return format_text % value


def _reading(channels: list[dict[str, Any]], overrides: dict[int, str] | None = None) -> str:
    cells = []
    for index, channel in enumerate(channels):
        cells.append((overrides or {}).get(index, _lit(channel["good"])))
    return "Reading{" + ", ".join(cells) + "}"


def render_traits(part: dict[str, Any]) -> str:
    """The part-specific half of the application core: Reading, ranges, plausibility and line formats."""
    channels = part["channels"]
    lines = [
        f"// Part-specific definitions for the {part['chip']}. Generated from its part descriptor; do not edit by hand.",
        "// The descriptor is a cited extract and stays UNREVIEWED_EXTRACT until a person reviews it.",
        "#pragma once",
        "",
        "#include <cmath>",
        "#include <cstddef>",
        "#include <cstdint>",
        "#include <cstdio>",
        "",
        "// " + part["bounds_citation"],
    ]
    for channel in channels:
        lines.append(f"static constexpr float {channel['min_const']} = {_lit(channel['min'])};")
        lines.append(f"static constexpr float {channel['max_const']} = {_lit(channel['max'])};")
    lines += ["", "struct Reading {"]
    lines += [f"    float {channel['field']};" for channel in channels]
    lines += ["};", ""]
    lines += ["// Used by the host tests; the application itself never needs it.", "[[maybe_unused]] static Reading reading_filled(float value) {", "    return Reading{" + ", ".join(["value"] * len(channels)) + "};", "}", ""]
    lines.append("static bool reading_is_plausible(const Reading& reading) {")
    nan_terms = " || ".join(f"std::isnan(reading.{channel['field']})" for channel in channels)
    lines.append(f"    if ({nan_terms}) return false;")
    for channel in channels:
        f, lo, hi = channel["field"], channel["min_const"], channel["max_const"]
        lines.append(f"    if (reading.{f} < {lo} || reading.{f} > {hi}) return false;")
    lines += ["    return true;", "}", ""]
    ok_format = "T=%u STATE=OK " + " ".join(f"{c['key']}={c['serial_format']}" for c in channels)
    args = ", ".join(f"reading.{c['field']}" for c in channels)
    lines += [
        "static void format_ok_line(char* line, size_t size, uint32_t now, const Reading& reading) {",
        f'    std::snprintf(line, size, "{ok_format}", (unsigned)now, {args});',
        "}",
        "",
        "static void format_display_lines(const Reading& reading, char* l2, char* l3, char* l4, size_t size) {",
    ]
    for slot, name in enumerate(("l2", "l3", "l4")):
        if slot < len(channels):
            lines.append(f'    std::snprintf({name}, size, "{channels[slot]["display_format"]}", reading.{channels[slot]["field"]});')
        else:
            lines.append(f"    {name}[0] = '\\0';")
    lines += ["}", ""]
    return "\n".join(lines)


def render_fixtures(part: dict[str, Any]) -> str:
    """The part-specific half of the host harness: addresses, identity, fixture readings and bound cases."""
    channels = part["channels"]
    identity = part["identity"]
    addr_a, addr_b = part["addresses"]
    ok_suffix = "".join(f" {c['key']}=" + _fmt(c["serial_format"], c["good"]) for c in channels)
    regex_cells = []
    for channel in channels:
        digits = int(_SERIAL_FORMAT.match(channel["serial_format"]).group(1))
        regex_cells.append(f"{channel['key']}=-?[0-9]+\\.[0-9]" + (f"{{{digits}}}" if digits > 1 else ""))
    good_display = ["STATE OK"] + [_fmt(c["display_format"], c["good"]) for c in channels]
    good_display += [""] * (4 - len(good_display))
    markers = [c["display_marker"] for c in channels] + [""] * (3 - len(channels))
    lines = [
        f"// Part fixtures for the {part['chip']}. Generated from its part descriptor; do not edit by hand.",
        "",
        f"static const uint8_t kAddrA = {addr_a};  // first declared address, the default",
        f"static const uint8_t kAddrB = {addr_b};",
        "static const uint8_t kSensorAddrs[] = {kAddrA, kAddrB};",
        f"static constexpr bool kHasIdentity = {'true' if identity else 'false'};",
        f"static constexpr uint8_t kChipId = {identity['value'] if identity else '0x00'};",
        "",
        f"static const Reading kGood = {_reading(channels)};",
        f'static const char* const kGoodLineSuffix = "{ok_suffix}";',
        f'static const char* const kOkMarker = "STATE=OK {channels[0]["key"]}=";',
        'static const char* const kOkLineRegex = R"(^T=[0-9]+ STATE=OK ' + " ".join(regex_cells) + '$)";',
        "static const char* const kGoodDisplay[4] = {" + ", ".join(f'"{text}"' for text in good_display) + "};",
        "static const char* const kDisplayMarkers[3] = {" + ", ".join(f'"{text}"' for text in markers) + "};",
        "",
        "struct BoundCase {",
        "    const char* name;",
        "    Reading value;",
        "    bool accept;",
        "};",
        "struct OutOfRangeCase {",
        "    const char* name;",
        "    Reading value;",
        "    const char* must_not_log;",
        "    const char* detail;",
        "};",
        "",
        "static const BoundCase kBoundCases[] = {",
    ]
    for index, channel in enumerate(channels):
        short = channel["short"]
        for suffix, value, accept in (
            ("min_edge", _lit(channel["min"]), True),
            ("min_beyond", _lit(round(channel["min"] - 0.01, 2)), False),
            ("max_edge", _lit(channel["max"]), True),
            ("max_beyond", _lit(round(channel["max"] + 0.01, 2)), False),
        ):
            lines.append(f'    {{"{short}_{suffix}", {_reading(channels, {index: value})}, {"true" if accept else "false"}}},')
    for index, channel in enumerate(channels):
        if index >= 1:
            lines.append(f'    {{"nan_{channel["short"]}_only", {_reading(channels, {index: "std::nanf(\"\")"})}, false}},')
    lines += ["};", "", "static const OutOfRangeCase kOutOfRangeCases[] = {"]
    for index, channel in enumerate(channels):
        probe = channel["out_of_range_probe"]
        marker = f"{channel['key']}=" + _fmt(channel["serial_format"], probe)
        detail = f"{channel['label']} outside {channel['min']:g}..{channel['max']:g} {channel['unit']} was logged as a reading"
        lines.append(f'    {{"{channel["label"]}", {_reading(channels, {index: _lit(probe)})}, "{marker}", "{detail}"}},')
    lines += ["};", ""]
    return "\n".join(lines)
