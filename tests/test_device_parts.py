"""Part descriptors: a part is a cited extract rendered into generated headers, never trusted text."""
import copy

import pytest

from hardware_splicer.device_parts import (
    PartDescriptorError, available_parts, load_part, render_fixtures, render_traits, validate_part,
)
from hardware_splicer.device_plan import module_library

BME280 = "adafruit-bme280-stemma-qt"


def test_shipped_descriptors_validate_cite_their_sources_and_match_the_catalogue():
    parts = available_parts()
    assert BME280 in parts
    catalogue = {m["id"]: m for m in module_library()["modules"]}
    for library_id, part in parts.items():
        assert part["review_status"] == "UNREVIEWED_EXTRACT"
        assert part["bounds_citation"].strip()
        assert part["addresses"] == catalogue[library_id]["i2c"]["addresses"]
    assert parts[BME280]["identity"]["value"] == "0x60"


def test_rendering_is_deterministic_and_keeps_the_lines_the_bug_benchmark_targets():
    bme = load_part(BME280)
    assert render_traits(bme) == render_traits(copy.deepcopy(bme))
    assert render_fixtures(bme) == render_fixtures(copy.deepcopy(bme))
    traits = render_traits(bme)
    for line in (
        "static constexpr float kTempMaxC = 85.0f;",
        "    if (std::isnan(reading.temp_c) || std::isnan(reading.hum_pct) || std::isnan(reading.pres_hpa)) return false;",
        "    if (reading.hum_pct < kHumMinPct || reading.hum_pct > kHumMaxPct) return false;",
    ):
        assert line in traits
    fixtures = render_fixtures(bme)
    assert "static constexpr bool kHasIdentity = true;" in fixtures


def _mutated(name, change):
    def apply(part):
        change(part)
        return part
    apply.__name__ = name
    return apply


@pytest.mark.parametrize(
    "change",
    [
        _mutated("quote_in_serial_format", lambda p: p["channels"][0].update(serial_format='%.1f"')),
        _mutated("newline_in_display_format", lambda p: p["channels"][0].update(display_format="%.1f lx\n#define X 1")),
        _mutated("lowercase_key", lambda p: p["channels"][0].update(key="temp_c")),
        _mutated("code_in_key", lambda p: p["channels"][0].update(key='TEMP_C"; system("x"); //')),
        _mutated("code_in_const", lambda p: p["channels"][0].update(min_const="k0; int x")),
        _mutated("min_not_below_max", lambda p: p["channels"][0].update(min=10.0, max=10.0)),
        _mutated("fixture_outside_range", lambda p: p["channels"][0].update(good=500.0)),
        _mutated("probe_inside_range", lambda p: p["channels"][0].update(out_of_range_probe=20.0)),
        _mutated("non_finite_bound", lambda p: p["channels"][0].update(max=float("inf"))),
        _mutated("boolean_as_number", lambda p: p["channels"][0].update(good=True)),
        _mutated("three_addresses", lambda p: p.update(addresses=["0x77", "0x76", "0x40"])),
        _mutated("same_address_twice", lambda p: p.update(addresses=["0x77", "0x77"])),
        _mutated("not_7_bit", lambda p: p.update(addresses=["0x77", "0xFF"])),
        _mutated("claims_reviewed", lambda p: p.update(review_status="REVIEWED")),
        _mutated("no_channels", lambda p: p.update(channels=[])),
        _mutated("four_channels", lambda p: p.update(channels=p["channels"] * 4)),
        _mutated("unpinned_library", lambda p: p["adapter"].update(lib_deps=["adafruit/Adafruit SSD1306"])),
        _mutated("template_path_escape", lambda p: p["adapter"].update(template="../../etc/passwd.cpp.tmpl")),
        _mutated("newline_in_citation", lambda p: p.update(bounds_citation="ok\n#include <evil.h>")),
        _mutated("wrong_schema", lambda p: p.update(schema_version="other")),
        _mutated("identity_neither_given_nor_explained", lambda p: p.update(identity=None)),
    ],
)
def test_the_validator_refuses_text_that_could_reach_generated_source(change):
    part = change(copy.deepcopy(load_part(BME280)))
    with pytest.raises(PartDescriptorError):
        validate_part(part)


def test_the_two_names_of_a_channel_may_coincide_but_not_repeat_across_channels():
    part = copy.deepcopy(load_part(BME280))
    part["channels"][1]["field"] = part["channels"][0]["field"]
    with pytest.raises(PartDescriptorError, match="duplicate field"):
        validate_part(part)
