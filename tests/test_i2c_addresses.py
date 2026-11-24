"""I2C address facts for splice-library parts come from the sourced device library, never from guesses."""

from __future__ import annotations

from hardware_splicer.i2c_addresses import i2c_addresses_for


def test_a_part_with_a_selectable_address_lists_the_factory_default_first_and_why() -> None:
    info = i2c_addresses_for("bme280")

    assert info["addresses"] == ["0x77", "0x76"]
    assert info["default"] == "0x77"
    assert "Bosch datasheet" in info["basis"]
    assert info["selectable"] is True


def test_a_part_whose_address_cannot_change_is_not_selectable() -> None:
    info = i2c_addresses_for("ds3231_rtc")

    assert info["addresses"] == ["0x68"]
    assert info["selectable"] is False


def test_the_other_sourced_parts_resolve_to_their_chip_addresses() -> None:
    assert i2c_addresses_for("bh1750")["addresses"] == ["0x23", "0x5C"]
    assert i2c_addresses_for("ssd1306-128x64")["addresses"] == ["0x3C", "0x3D"]


def test_a_part_with_no_sourced_address_is_unknown_not_guessed() -> None:
    for module_id in ("bmp280", "ds1307_rtc", "lcd_16x2_i2c", "mcp4725-dac", "esp32-devkit", "sg90", "no-such-part"):
        assert i2c_addresses_for(module_id) is None, module_id


def test_every_mapped_part_exists_in_both_libraries() -> None:
    from hardware_splicer.i2c_addresses import SPLICE_TO_DEVICE_LIBRARY
    from hardware_splicer.pcb.module_registry import find_module

    for splice_id in SPLICE_TO_DEVICE_LIBRARY:
        assert find_module(splice_id) is not None, splice_id
        assert i2c_addresses_for(splice_id) is not None, splice_id
