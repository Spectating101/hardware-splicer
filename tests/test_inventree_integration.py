"""Read-only upstream contract, inventory semantics and complete pagination."""
from decimal import Decimal
import json

import httpx
import pytest

from hardware_splicer.integrations.inventree import InvenTreeClient, InvenTreeError
from hardware_splicer.project_materials import import_inventree_materials
from hardware_splicer.project_store import ProjectStore, RevisionConflict


def responses():
    return {
        "part/99/": {"pk": 99, "name": "Drone", "assembly": True},
        "bom/": [{"pk": 1, "part": 99, "sub_part": 7, "quantity": "4"}],
        "part/7/": {"pk": 7, "name": "F1404 KV2900", "units": "", "active": True, "assembly": False},
        "company/part/manufacturer/": [{"pk": 2, "part": 7, "MPN": "F1404-KV2900", "manufacturer_detail": {"name": "T-Hobby"}}],
        "stock/": [
            {"pk": 10, "part": 7, "quantity": "3", "allocated": "1", "status": 10, "status_custom_key": 10},
            {"pk": 11, "part": 7, "quantity": "100", "allocated": "0", "status": 55, "status_custom_key": 55},
            {"pk": 12, "part": 7, "quantity": "100", "allocated": "0", "status": 50, "status_custom_key": 50},
        ],
        "company/part/": [{"pk": 3, "part": 7, "SKU": "motor-2900", "link": "https://parts.example/motor",
                          "available": 1000, "supplier_detail": {"name": "Example supplier"}}],
    }


def client_for(data, seen):
    def handle(request):
        seen.append(request)
        assert request.method == "GET"
        assert request.url.host == "inventory.example"
        assert request.headers["authorization"] == "Token private-test-token"
        path = request.url.path.removeprefix("/api/")
        value = data[path]
        if isinstance(value, list):
            # Deliberately clamp the requested limit: consumers must use count,
            # not assume the first short page is the complete inventory.
            offset = int(request.url.params.get("offset", 0))
            page = value[offset:offset+1]
            value = {"count": len(value), "next": "https://foreign.example/steal" if offset+1 < len(value) else None, "results": page}
        return httpx.Response(200, json=value)
    return InvenTreeClient("https://inventory.example/api/", "private-test-token", transport=httpx.MockTransport(handle))


def test_direct_bom_import_reconciles_healthy_unallocated_stock_and_cached_supplier_data(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    before = store.save("drone", {"projectName": "Drone", "physical_authority_granted": False}, expected_revision=0)
    seen = []
    result = import_inventree_materials(store, "drone", expected_revision=1, assembly_part_id=99,
                                       client=client_for(responses(), seen))
    record = result["assessment"]
    assert record["inventory_provenance"] == "inventree_http_read"
    line = record["report"]["lines"][0]
    assert Decimal(line["available_for_plan"]) == 2
    assert Decimal(line["shortage"]) == 2
    assert line["manufacturer"] == "T-Hobby" and line["mpn"] == "F1404-KV2900"
    assert line["supplier_references"][0]["reported_available"] == "1000"
    assert len(record["inventory"]["lots"]) == 3
    assert len([r for r in seen if r.url.path == "/api/stock/"]) == 3
    assert store.load("drone") == before
    assert "private-test-token" not in json.dumps(record)
    assert all(r.url.host == "inventory.example" for r in seen)
    assert not record["report"]["stock_reserved"]


def test_repeated_subpart_is_not_double_counted_and_build_quantity_is_applied(tmp_path):
    data = responses()
    data["bom/"].append({"pk": 8, "part": 99, "sub_part": 7, "quantity": "2"})
    client = client_for(data, [])
    requirements, inventory = client.read_assembly(99, build_quantity=2)
    assert [row.quantity for row in requirements] == [8, 4]
    assert len(inventory.lots) == 3


@pytest.mark.parametrize("change", ["missing_allocation", "custom_status", "installed", "building"])
def test_stock_without_clear_healthy_available_state_is_not_used(change):
    data = responses()
    stock = data["stock/"][0]
    if change == "missing_allocation":
        stock.pop("allocated")
    elif change == "custom_status":
        stock["status_custom_key"] = "needs-review"
    elif change == "installed":
        stock["belongs_to"] = 15
    else:
        stock["is_building"] = True
    _, capture = client_for(data, []).read_assembly(99)
    assert all(lot.condition != "ok" for lot in capture.lots)


@pytest.mark.parametrize("path,field,value", [
    ("bom/", "part", 100),
    ("stock/", "part", 88),
    ("company/part/", "part", 88),
    ("company/part/manufacturer/", "part", 88),
])
def test_upstream_records_from_other_parts_are_rejected(path, field, value):
    data = responses()
    data[path][0][field] = value
    with pytest.raises(InvenTreeError):
        client_for(data, []).read_assembly(99)


def test_nested_assembly_and_bom_adjustments_remain_visible():
    data = responses()
    data["part/7/"]["assembly"] = True
    data["bom/"][0]["attrition"] = "5"
    requirements, _ = client_for(data, []).read_assembly(99)
    assert requirements[0].acquisition == "make"
    assert "nested_assembly_not_expanded" in requirements[0].unresolved
    assert "bom_quantity_adjustment_requires_review:attrition" in requirements[0].unresolved


@pytest.mark.parametrize("mode", ["auth", "redirect", "incomplete", "repeat", "count_changed"])
def test_failures_do_not_create_partial_material_records(tmp_path, mode):
    calls = []
    def handle(request):
        calls.append(request)
        if request.url.path.endswith("/part/99/"):
            return httpx.Response(200, json={"pk": 99})
        if mode in {"auth", "redirect"}:
            return httpx.Response(401 if mode == "auth" else 302, headers={"Location": "https://foreign.example"},
                                  json={"secret": "private-test-token"})
        offset = int(request.url.params.get("offset", "0"))
        row = {"pk": 1, "part": 99, "sub_part": 7, "quantity": "4"}
        return httpx.Response(200, json={"count": 3 if mode == "count_changed" and offset else 2,
                                        "results": [row], "next": None if mode == "incomplete" else "/api/bom/?offset=1"})
    client = InvenTreeClient("https://inventory.example", "private-test-token", transport=httpx.MockTransport(handle))
    store = ProjectStore(tmp_path/"projects")
    original = store.save("drone", {"projectName": "Drone"}, expected_revision=0)
    with pytest.raises(InvenTreeError) as raised:
        import_inventree_materials(store, "drone", expected_revision=1, assembly_part_id=99, client=client)
    assert "private-test-token" not in str(raised.value)
    assert store.load("drone") == original
    assert not (store.root/"drone"/"material_assessments").exists()
    assert all(request.url.host == "inventory.example" for request in calls)


def test_stale_project_is_rejected_before_any_remote_request(tmp_path):
    store = ProjectStore(tmp_path/"projects")
    store.save("drone", {}, expected_revision=0)
    seen = []
    with pytest.raises(RevisionConflict):
        import_inventree_materials(store, "drone", expected_revision=2, assembly_part_id=99,
                                  client=client_for(responses(), seen))
    assert seen == []


@pytest.mark.parametrize("url", ["https://user:pass@inventory.example", "https://inventory.example?token=secret",
                                "http://inventory.example", "https://inventory.example/../escape", "file:///tmp/db"])
def test_credentials_and_unsafe_server_urls_are_rejected(url):
    with pytest.raises(ValueError):
        InvenTreeClient(url, "private-test-token")
