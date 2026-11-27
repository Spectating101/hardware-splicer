"""Landscape watch, offline: topic matching, the running register and the digest."""
from __future__ import annotations

from hardware_splicer import landscape_watch as lw


def test_new_items_are_matched_registered_once_and_written_to_the_digest(tmp_path, monkeypatch):
    feed = [{"source": "hacker_news", "title": "Show HN: an AI agent that lays out KiCad PCBs", "url": "https://example.org/a?ref=hn", "date": "2026-11-20"},
            {"source": "github", "title": "someone/robot-arm-kit: open source robot arm with Feetech servos", "url": "https://github.com/someone/robot-arm-kit", "stars": 40},
            {"source": "hackster", "title": "A cake recipe", "url": "https://example.org/cake"}]
    for name in ("hacker_news", "github", "github_established", "rss", "reddit", "atlas"):
        monkeypatch.setattr(lw, name, (lambda items: (lambda since: list(items)))(feed if name == "hacker_news" else []))
    first = lw.run(8, tmp_path)
    assert first["new"] == 2 and set(first["by_topic"]) <= set(lw.TOPICS)
    digest = (tmp_path / "digests").glob("*.md").__next__().read_text()
    assert "lays out KiCad PCBs" in digest and "cake" not in digest
    again = lw.run(8, tmp_path)
    assert again["new"] == 0 and again["register"] == 2  # the ?ref= query string does not make a second entry


def test_the_atlas_source_reads_mapped_products_and_keeps_the_hardware_ones(tmp_path, monkeypatch):
    import json

    run_dir = tmp_path / "atlas" / "signals-delta-20261128" / "newly-possible"
    run_dir.mkdir(parents=True)
    (run_dir / "products.json").write_text(json.dumps([
        {"catalog_id": "github:schlae/cm5-reveng", "purpose": "A reverse-engineered schematic and KiCad layout for the Raspberry Pi CM5",
         "inputs": "[]", "outputs": "['KiCad project']", "stars": "838", "post": "15000"},
        {"catalog_id": "github:dorianborian/sesame-robot", "purpose": "Printable parts and ESP32 firmware for an eight-servo walking robot",
         "inputs": "[]", "outputs": "[]", "stars": "5081"},
        {"catalog_id": "github:someone/photo-manager", "purpose": "A desktop photo manager", "inputs": "[]", "outputs": "[]", "stars": "4000"}]))
    items = lw.atlas(None, tmp_path / "atlas")
    assert {i["url"] for i in items} == {"https://github.com/schlae/cm5-reveng", "https://github.com/dorianborian/sesame-robot",
                                         "https://github.com/someone/photo-manager"}
    for name in ("hacker_news", "github", "github_established", "rss", "reddit"):
        monkeypatch.setattr(lw, name, lambda since: [])
    monkeypatch.setattr(lw, "ATLAS_DIR", tmp_path / "atlas")
    result = lw.run(8, tmp_path / "state")
    assert result["new"] == 2  # the photo manager matches no hardware topic
    assert lw.atlas(None, tmp_path / "missing") == []
