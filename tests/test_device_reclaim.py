"""A read marking can suggest a library name, never identify or qualify a reclaimed part."""

from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer import device_reclaim as reclaim
from hardware_splicer.device_api import MAX_BODY_BYTES, create_device_router
from hardware_splicer.device_plan import module_library
from hardware_splicer.part_lookup import name_match_tier


def row(marking, ref="U1", kind="ic"):
    return {"ref": ref, "kind": kind, "marking": marking}


def test_real_library_match_preserves_the_read_marking_and_does_not_expand_chip_names():
    before = module_library()
    name = before["modules"][0]["name"]
    parts = [row(name.lower()), row("SSD1306", "U2"), row("ESP32-WROOM-32E", "U3"), row("", "U4")]
    original = deepcopy(parts)
    result = reclaim.match_reclaimed_parts({"parts": parts})
    assert result["parts"][0]["marking"] == name.lower()
    match = result["parts"][0]["matches"][0]
    assert match["module"] == "esp32-devkitc-v4" and match["tier"] == "exact"
    assert match["matched_field"] == "name" and match["name"] == name
    assert all(not item["matched"] and item["matches"] == [] for item in result["parts"][1:])
    assert "may already have" in result["note"] and "not proof" in result["note"]
    assert "library's" in result["note"] and "not your chip's" in result["note"]
    assert "compatibility" in result["note"] and "approves" in result["note"]
    assert parts == original and module_library() == before


@pytest.mark.parametrize("marking,name,tier", [
    ("NE555", "ne555", "exact"), ("NE555P", "NE555", "variant"),
    ("NE555", "NE555P", "variant"), ("STM32F103C8T6", "STM32F103C8Tx", "variant"),
    ("LM35", "LM358", None), ("74HC", "74HC00", None),
    ("NE555P", "NE555D", None), ("LM358", "LM3580", None), ("AB", "AB", None),
    ("STM32F103C8T6", "STM32F103CBTx", None),
])
def test_only_part_lookup_exact_and_variant_rules_are_shared(marking, name, tier, monkeypatch):
    assert name_match_tier(marking, name) == tier
    # Synthetic names exercise the rules without adding any production library parts.
    monkeypatch.setattr(reclaim, "module_library", lambda: {"modules": [{"id": "fixture", "name": name, "kind": "display"}]})
    found = reclaim.match_reclaimed_parts({"parts": [row(marking)]})["parts"][0]
    assert found["matched"] is (tier is not None)
    assert [m["tier"] for m in found["matches"]] == ([tier] if tier else [])


def test_explicit_mpn_is_supported_and_kind_is_reported_without_claiming_compatibility(monkeypatch):
    monkeypatch.setattr(reclaim, "module_library", lambda: {"modules": [
        {"id": "fixture", "name": "Fixture only", "mpn": "NE555", "kind": "display"},
    ]})
    found = reclaim.match_reclaimed_parts({"parts": [row("NE555P", kind="connector")]})["parts"][0]
    assert found["kind"] == "connector"
    assert found["matches"][0]["matched_field"] == "mpn"
    assert found["matches"][0]["tier"] == "variant"
    assert "compatible" not in found and "identified" not in found


@pytest.mark.parametrize("body", [
    None, [], {}, {"parts": None}, {"parts": [None]}, {"parts": [row("x" * 41)]},
    {"parts": [row("NE555\u200b")]}, {"parts": [row("NE555\n")]},
    {"parts": [row("NE555", ref="U1\u202e")]}, {"parts": [row("NE555", kind="ic\x00")]},
    {"parts": [row(float("nan"))]}, {"parts": [row(float("inf"))]},
    {"parts": [row(10**500)]}, {"parts": [row(True)]},
    {"parts": [row("NE555"), row("NE555")]}, {"parts": [row("", ref="")]},
    {"parts": [row("", kind="")]},
    {"parts": [row("", ref=str(i)) for i in range(301)]},
])
def test_bad_shapes_hidden_text_and_non_text_numbers_are_refused(body):
    with pytest.raises(reclaim.DeviceReclaimError):
        reclaim.match_reclaimed_parts(body)


def test_empty_list_and_printable_non_english_text_are_allowed():
    assert reclaim.match_reclaimed_parts({"parts": []})["parts"] == []
    found = reclaim.match_reclaimed_parts({"parts": [row("標記", ref="零件一", kind="其他")]})["parts"][0]
    assert found["marking"] == "標記" and not found["matched"]


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(create_device_router())
    return TestClient(app)


def test_endpoint_serves_the_real_matcher_and_clear_validation_errors(api):
    payload = {"parts": [row(module_library()["modules"][0]["name"]), row("LM358", "U2")]}
    response = api.post("/v1/devices/reclaim-matches", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True, **reclaim.match_reclaimed_parts(payload)}
    for body in ({"parts": "wrong"}, {"parts": [row("x\u200b")]}, {"parts": [row(10**500)]}):
        bad = api.post("/v1/devices/reclaim-matches", json=body)
        assert bad.status_code == 422 and bad.json()["detail"]["type"] == "invalid_reclaim_list"
    for body in (b"not json", b"\xff", b"[" * 1200 + b"]" * 1200):
        assert api.post("/v1/devices/reclaim-matches", content=body).status_code == 422


def test_endpoint_limits_declared_and_streamed_bodies(api):
    assert api.post("/v1/devices/reclaim-matches", content=b"x" * (MAX_BODY_BYTES + 1)).status_code == 413
    assert api.post("/v1/devices/reclaim-matches", content=b"{}", headers={"content-length": str(MAX_BODY_BYTES + 1)}).status_code == 413
    def pieces():
        for _ in range(20):
            yield b"x" * 8192
    assert api.post("/v1/devices/reclaim-matches", content=pieces()).status_code == 413


def test_product_endpoint_accepts_capture_plan_markings_without_changing_project_state(tmp_path, monkeypatch):
    from hardware_splicer.donor_capture import build_donor_salvage_plan
    from hardware_splicer.product_api import create_product_app
    from hardware_splicer.project_store import ProjectStore

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    name = module_library()["modules"][0]["name"]
    plan = build_donor_salvage_plan({
        "name": "Reported donor", "board": {"width_mm": 60, "length_mm": 40},
        "parts": [{"ref": "U1", "kind": "ic", "package": "SOIC", "marking": name, "x_mm": 20, "y_mm": 20}],
    })
    part = plan["parts"][0]
    assert part["identity"]["mpn"] is None
    payload = {"parts": [row(part["identity"]["typed"], part["ref"], part["component"])]}
    original_plan = deepcopy(plan)
    client = TestClient(create_product_app(ProjectStore(tmp_path / "store")))
    before = sorted(str(path) for path in tmp_path.rglob("*"))
    result = client.post("/v1/devices/reclaim-matches", json=payload)
    assert result.status_code == 200 and result.json()["parts"][0]["matched"]
    assert result.json()["parts"][0]["kind"] == "ic"
    assert sorted(str(path) for path in tmp_path.rglob("*")) == before
    assert plan == original_plan


def test_oversized_stream_is_stopped_before_reading_the_next_chunk():
    import asyncio
    from fastapi import HTTPException
    from hardware_splicer.device_api import _read_body

    class RequestPieces:
        headers = {}
        async def stream(self):
            yield b"x" * MAX_BODY_BYTES
            yield b"x"
            pytest.fail("read beyond the body limit")

    with pytest.raises(HTTPException) as caught:
        asyncio.run(_read_body(RequestPieces(), error_type="invalid_reclaim_list", label="reclaim list"))
    assert caught.value.status_code == 413
