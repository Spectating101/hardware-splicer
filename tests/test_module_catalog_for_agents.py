"""An agent cannot design with a part it cannot find. The catalog must be searchable and small."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_STATE_DIR", str(tmp_path / "state"))
    return TestClient(create_product_app())


def test_the_default_catalog_response_is_unchanged(client) -> None:
    body = client.get("/v1/modules/catalog").json()

    assert body["count"] == 50
    assert "summary" in body["modules"][0]


def test_a_compact_catalog_lists_every_part_by_id_label_and_category_in_a_few_kilobytes(client) -> None:
    response = client.get("/v1/modules/catalog", params={"compact": "true"})
    body = response.json()

    assert body["count"] == 50 and len(body["modules"]) == 50
    assert set(body["modules"][0]) <= {"id", "label", "category", "i2c_addresses"}
    assert {"id", "label", "category"} <= set(body["modules"][0])
    assert len(response.text) < 9000 < len(client.get("/v1/modules/catalog").text) / 3


def test_search_matches_the_id_or_the_label_ignoring_case_and_returns_the_compact_form(client) -> None:
    ids = lambda q: [m["id"] for m in client.get("/v1/modules/catalog", params={"q": q}).json()["modules"]]  # noqa: E731

    assert "ds3231_rtc" in ids("DS3231")
    assert "usb-power-5v" in ids("usb")
    assert ids("zzz-no-such-part") == []
    assert all(set(m) <= {"id", "label", "category", "i2c_addresses"} for m in client.get("/v1/modules/catalog", params={"q": "usb"}).json()["modules"])


def test_a_part_whose_i2c_address_is_sourced_says_so_and_others_do_not(client) -> None:
    by_id = {m["id"]: m for m in client.get("/v1/modules/catalog", params={"compact": "true"}).json()["modules"]}

    assert by_id["bme280"]["i2c_addresses"] == ["0x77", "0x76"]
    assert by_id["ds3231_rtc"]["i2c_addresses"] == ["0x68"]
    assert "i2c_addresses" not in by_id["sg90"]
    assert "i2c_addresses" not in by_id["bmp280"], "no sourced address, so none is stated"


def test_the_count_with_a_search_is_the_number_of_matches(client) -> None:
    body = client.get("/v1/modules/catalog", params={"q": "usb"}).json()

    assert body["count"] == len(body["modules"]) >= 1
    assert json.dumps(body)
