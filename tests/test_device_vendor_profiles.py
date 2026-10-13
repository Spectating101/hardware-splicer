"""A descriptor selects a vendor-host lane by name; the files, libraries and scenarios behind it are fixed in code."""
import copy
from pathlib import Path

import pytest

from hardware_splicer.device_parts import PartDescriptorError, available_parts, load_part, validate_part
from hardware_splicer.device_vendor_profiles import COMMON_FILES, VENDOR_PROFILES, vendor_files, vendor_profile

HOST = Path(__file__).resolve().parents[1] / "src" / "hardware_splicer" / "data" / "firmware_application" / "vendor_host"


def test_every_profile_file_exists_and_every_vendor_host_file_belongs_to_a_profile():
    shipped = {path.name for path in HOST.iterdir() if path.is_file()}
    claimed = set()
    for name in VENDOR_PROFILES:
        files = set(vendor_files(name))
        assert files <= shipped, sorted(files - shipped)
        claimed |= files
    assert claimed == shipped, f"unclaimed files would never ship: {sorted(shipped - claimed)}"
    assert set(COMMON_FILES) <= claimed


def test_a_profiles_compile_sources_are_files_it_ships():
    for name, profile in VENDOR_PROFILES.items():
        shipped = set(vendor_files(name))
        assert set(profile["model_sources"]) <= shipped and profile["harness"] in shipped, name
        assert len(profile["scenarios"]) == len(set(profile["scenarios"])), name


def test_every_shipped_descriptor_names_a_known_profile_or_none():
    for library_id, part in available_parts().items():
        adapter = part["adapter"]
        assert (adapter["vendor_host"] is True) == (adapter.get("vendor_profile") in VENDOR_PROFILES), library_id


@pytest.mark.parametrize(
    "change",
    [
        lambda a: a.update(vendor_profile="not-a-profile"),
        lambda a: a.update(vendor_profile="../../etc/passwd"),
        lambda a: a.pop("vendor_profile"),
        lambda a: a.update(vendor_host=False),  # a profile without a lane
    ],
)
def test_a_descriptor_cannot_name_a_profile_that_does_not_exist_or_attach_one_to_no_lane(change):
    part = copy.deepcopy(load_part("adafruit-bme280-stemma-qt"))
    change(part["adapter"])
    with pytest.raises(PartDescriptorError):
        validate_part(part)


def test_an_unknown_profile_is_refused_not_guessed():
    with pytest.raises(ValueError):
        vendor_profile("bme680")
