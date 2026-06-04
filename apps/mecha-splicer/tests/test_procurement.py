from __future__ import annotations

from src.mecha_splicer.engines.catalog import MechanicalCatalog
from src.mecha_splicer.engines.procurement import apply_overrides, lock_bom


def test_procurement_pack_quantity(tmp_path):
    catalog_path = tmp_path / "catalog.jsonl"
    catalog_path.write_text(
        "\n".join(
            [
                '{"sku":"m3_screw_assorted","name":"M3 screws","unit":"ea","pack_size":1,"min_order_qty":1,"price_usd":6.0,"currency":"USD","url":""}',
            ]
        ),
        encoding="utf-8",
    )
    catalog = MechanicalCatalog(catalog_path)
    bom = [{"category": "fastener", "item": "M3 screws", "spec": "M3×12", "qty": 8, "notes": "", "sku": "m3_screw_assorted"}]
    locked = lock_bom(bom, catalog=catalog)
    assert locked[0].required_qty == 8
    assert locked[0].purchase_qty == 8
    assert locked[0].subtotal_usd == 48.0


def test_apply_overrides_by_item_contains():
    bom = [{"item": "M3 screws", "sku": "", "qty": 4}]
    overrides = {"by_item_contains": {"M3 screws": {"sku": "m3_screw_assorted", "price_usd": 6.0}}}
    out = apply_overrides(bom, overrides)
    assert out[0]["sku"] == "m3_screw_assorted"
    assert out[0]["price_usd"] == 6.0


def test_pack_sizing_rounds_up(tmp_path):
    catalog_path = tmp_path / "catalog.jsonl"
    catalog_path.write_text(
        "\n".join(
            [
                '{"sku":"m3_heatset_inserts_100","name":"M3 inserts","unit":"bag","pack_size":100,"min_order_qty":1,"price_usd":8.0,"currency":"USD","url":""}',
            ]
        ),
        encoding="utf-8",
    )
    catalog = MechanicalCatalog(catalog_path)
    bom = [{"category": "fastener", "item": "M3 heat-set inserts", "spec": "M3 heat-set", "qty": 120, "notes": "", "sku": "m3_heatset_inserts_100"}]
    locked = lock_bom(bom, catalog=catalog)
    assert locked[0].required_qty == 120
    assert locked[0].purchase_qty == 2
    assert locked[0].subtotal_usd == 16.0
