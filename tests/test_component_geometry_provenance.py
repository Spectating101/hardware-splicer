"""No catalog success, auto-wire success or synthetic pad fallback implies build authority."""
import pytest
from hardware_splicer.component_geometry_provenance import assess_build_graph_geometry
from hardware_splicer.plan_to_graph import splice_plan_to_build_graph
from hardware_splicer.catalog import CATALOG_BUILD_IDS


def test_curated_registry_geometry_is_still_unverified():
    report = assess_build_graph_geometry({"nodes": [
        {"id": "supply", "moduleId": "usb-power-5v"},
        {"id": "controller", "moduleId": "esp32-devkit"},
    ], "wires": []})
    assert report["status"] == "curated_geometry_requires_validation"
    assert report["curated_unverified_count"] == 2
    assert report["synthetic_fallback_count"] == 0
    assert not report["source_geometry_authenticated"]
    assert not report["fabrication_authorized"]
    assert all(x["vendor_footprint_authenticated"] is False for x in report["modules"])


def test_synthetic_pad_fallback_cannot_be_mistaken_for_manufacturer_part():
    report = assess_build_graph_geometry({"nodes": [
        {"id": "display", "moduleId": "ili9341_tft"},
        {"id": "power", "moduleId": "usb-power-5v"},
    ]})
    assert report["status"] == "synthetic_geometry_present"
    assert report["synthetic_fallback_count"] == 1
    display = next(x for x in report["modules"] if x["module_id"] == "ili9341_tft")
    assert display["geometry_class"] == "synthetic_fallback"
    assert display["footprint_identifier"].startswith("Circuit.AI:")
    assert not report["production_release_authorized"]


def test_unknown_module_is_explicitly_blocked():
    report = assess_build_graph_geometry({"nodes": [{"moduleId": "fictional_module_xyz"}]})
    assert report["status"] == "missing_module_identity"
    assert report["missing_module_count"] == 1
    assert not report["fabrication_authorized"]


def test_real_catalog_recipe_variants_are_classified_separately():
    rows = {}
    for build_id in CATALOG_BUILD_IDS:
        graph, _, _, _ = splice_plan_to_build_graph({"target": {"recommended_build_id": build_id}})
        rows[build_id] = assess_build_graph_geometry(graph)
    assert set(rows) == set(CATALOG_BUILD_IDS)
    assert rows["usb_fume_extractor"]["python_registry_only_count"] >= 1
    assert rows["room_display_station"]["synthetic_fallback_count"] >= 1
    assert rows["usb_fume_extractor"]["status"] == "registry_source_divergence_present"
    assert rows["sensor_logger"]["synthetic_fallback_count"] == 0
    assert all(not row["fabrication_authorized"] for row in rows.values())


@pytest.mark.parametrize("bad", [
    {"nodes": [{"id": "x"}]},
    {"nodes": [42]},
    {"nodes": "not-a-list"},
    {"nodes": [{"moduleId": "esp32-devkit"}] * 1001},
])
def test_malformed_graph_rejected(bad):
    with pytest.raises(ValueError):
        assess_build_graph_geometry(bad)

def test_python_footprint_and_serialized_library_are_not_equivalent():
    report = assess_build_graph_geometry({"nodes": [
        {"moduleId": "cooling_fan_5v"},
        {"moduleId": "ili9341_tft"},
    ]})
    fan, display = report["modules"]
    assert fan["geometry_class"] == "python_registry_only_unverified"
    assert fan["serialized_footprint_record_exists"] is False
    assert display["geometry_class"] == "synthetic_fallback"
    assert report["serialized_footprint_registry_count"] == 27
