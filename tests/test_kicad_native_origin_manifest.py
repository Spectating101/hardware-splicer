"""Source-origin manifest tests using actual KiCad/netlist fixtures."""
import pytest

from test_kicad_native_pin_geometry_audit import actual_input  # noqa: F401
from hardware_splicer.integrations.kicad_native_origin_manifest import (
    capture_native_identity_manifest, canonical_manifest_sha256,
)


def test_original_source_origin_manifest_has_all_36_instances(actual_input):
    sch, net, _ = actual_input
    manifest = capture_native_identity_manifest(sch, net)
    assert manifest["physical_instance_count"] == 36
    assert len({x["native_instance_key"] for x in manifest["instances"]}) == 36
    assert not manifest["external_converter_emission_authenticated"]
    assert not manifest["visual_electrical_merge_allowed"]
    assert not manifest["manufacturing_authorized"]
    assert len(canonical_manifest_sha256(manifest)) == 64


def test_native_symbol_uuid_tamper_rejected(actual_input):
    sch, net, _ = actual_input
    manifest = capture_native_identity_manifest(sch, net)
    original = manifest["instances"][0]["symbol_uuid"]
    assert original in sch
    with pytest.raises(ValueError, match="disagreement"):
        capture_native_identity_manifest(sch.replace(original, "00000000-0000-4000-8000-000000000000"), net)


def test_manifest_independent_of_converter_document_order(actual_input):
    sch, net, converter_docs = actual_input
    first = capture_native_identity_manifest(sch, net)
    assert first == capture_native_identity_manifest(sch, net)
    assert len(converter_docs) > 0


def test_identity_manifest_hash_changes_on_source_change(actual_input):
    sch, net, _ = actual_input
    original = capture_native_identity_manifest(sch, net)
    modified = capture_native_identity_manifest(sch + "\n", net)
    assert original["original_schematic_sha256"] != modified["original_schematic_sha256"]
    assert canonical_manifest_sha256(original) != canonical_manifest_sha256(modified)
