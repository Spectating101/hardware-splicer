"""Landscape watch, offline: topic matching, the running register and the digest."""
from __future__ import annotations

from hardware_splicer import landscape_watch as lw


def test_new_items_are_matched_registered_once_and_written_to_the_digest(tmp_path, monkeypatch):
    feed = [{"source": "hacker_news", "title": "Show HN: an AI agent that lays out KiCad PCBs", "url": "https://example.org/a?ref=hn", "date": "2026-11-20"},
            {"source": "github", "title": "someone/robot-arm-kit: open source robot arm with Feetech servos", "url": "https://github.com/someone/robot-arm-kit", "stars": 40},
            {"source": "hackster", "title": "A cake recipe", "url": "https://example.org/cake"}]
    for name in ("hacker_news", "github", "rss", "reddit"):
        monkeypatch.setattr(lw, name, (lambda items: (lambda since: list(items)))(feed if name == "hacker_news" else []))
    first = lw.run(8, tmp_path)
    assert first["new"] == 2 and set(first["by_topic"]) <= set(lw.TOPICS)
    digest = (tmp_path / "digests").glob("*.md").__next__().read_text()
    assert "lays out KiCad PCBs" in digest and "cake" not in digest
    again = lw.run(8, tmp_path)
    assert again["new"] == 0 and again["register"] == 2  # the ?ref= query string does not make a second entry
