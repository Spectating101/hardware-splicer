from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer import plan_to_graph


def test_catalog_recipes_resource_is_present_and_loadable() -> None:
    data_path = Path(plan_to_graph.__file__).resolve().parent / "data" / "catalog_recipes.json"

    assert data_path.is_file(), f"missing packaged catalog recipes: {data_path}"
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "hardware_splicer.catalog_recipes.v1"
    assert len(payload["supported_build_ids"]) >= 4
    assert set(payload["supported_build_ids"]) == set(payload["recipes"])


def test_catalog_recipe_loader_exposes_known_builds() -> None:
    plan_to_graph.load_catalog_data.cache_clear()
    build_ids = plan_to_graph.supported_build_ids()

    assert "automatic_plant_watering" in build_ids
    assert "bench_power_adapter" in build_ids
    assert plan_to_graph.load_catalog_data()["recipes"]["automatic_plant_watering"]["modules"]
