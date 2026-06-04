from pathlib import Path

from src.engines.mechanical_catalog import build_candidate_boms, load_catalog_jsonl


def test_load_catalog_jsonl_and_build_candidates(tmp_path: Path):
    p = tmp_path / "catalog.jsonl"
    p.write_text(
        "\n".join(
            [
                '{"id":"kit_3018_cnc","name":"3018 kit","category":"kit","specs":{},"price_twd":2500,"currency":"TWD","url":"x","seller":"s","notes":""}',
                '{"id":"estop_button","name":"E-stop","category":"safety","specs":{},"price_twd":120,"currency":"TWD","url":"x","seller":"s","notes":""}',
                '{"id":"endstop_switch","name":"endstop","category":"endstop","specs":{},"price_twd":20,"currency":"TWD","url":"x","seller":"s","notes":""}',
                '{"id":"probe_holder_spring","name":"probe mount","category":"tooling","specs":{},"price_twd":180,"currency":"TWD","url":"x","seller":"s","notes":""}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    catalog = load_catalog_jsonl(p)
    assert len(catalog) == 4
    res = build_candidate_boms(catalog=catalog, work_area_mm=(100, 100), accuracy_mm=0.25, prefer="cheapest")
    assert "candidates" in res
    assert len(res["candidates"]) >= 2
    # Candidate A total should at least include the known priced items.
    cand_a = res["candidates"][0]
    assert cand_a["total_twd"] >= 2500

