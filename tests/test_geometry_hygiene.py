from __future__ import annotations

from hardware_splicer.pcb.geometry_hygiene import clean_preview_geometry


def _seg(x1, y1, x2, y2, layer, net_id):
    return {
        "start": {"x": x1, "y": y1},
        "end": {"x": x2, "y": y2},
        "layer": layer,
        "net": {"id": net_id, "name": f"N{net_id}"},
    }


def _via(x, y, net_id):
    return {"x": x, "y": y, "size_mm": 0.8, "drill_mm": 0.4, "net": {"id": net_id, "name": f"N{net_id}"}}


def test_duplicate_vias_on_front_copper_only_are_removed_entirely() -> None:
    geometry = {
        "segments": [
            _seg(0, 0, 10, 0, "F.Cu", 1),
            _seg(10, 0, 20, 0, "F.Cu", 1),
        ],
        "vias": [_via(10, 0, 1), _via(10, 0, 1), _via(10, 0, 1)],
    }
    cleaned = clean_preview_geometry(geometry)
    assert cleaned["vias"] == []
    assert cleaned["geometry_hygiene"]["removed_via_count"] == 3
    assert cleaned["geometry_hygiene"]["findings"][0]["code"] == "REDUNDANT_NON_TRANSITION_VIAS_REMOVED"


def test_duplicate_real_layer_transition_collapses_to_one_via() -> None:
    geometry = {
        "segments": [
            _seg(0, 0, 10, 0, "F.Cu", 2),
            _seg(10, 0, 10, 10, "B.Cu", 2),
        ],
        "vias": [_via(10, 0, 2), _via(10, 0, 2)],
    }
    cleaned = clean_preview_geometry(geometry)
    assert len(cleaned["vias"]) == 1
    assert cleaned["geometry_hygiene"]["collapsed_duplicate_count"] == 1
    assert cleaned["geometry_hygiene"]["findings"][0]["code"] == "DUPLICATE_TRANSITION_VIA_COLLAPSED"


def test_unique_via_is_left_untouched() -> None:
    geometry = {"segments": [], "vias": [_via(1.25, 2.5, 3)]}
    cleaned = clean_preview_geometry(geometry)
    assert cleaned["vias"] == geometry["vias"]
    assert cleaned["geometry_hygiene"]["removed_via_count"] == 0
