from unittest.mock import Mock

import requests

from scripts.data_collection.download_ic_datasheets import DatasheetDownloader


def test_pdf_url_returning_html_cannot_populate_cache(tmp_path, monkeypatch):
    part = {"name": "LCD1602", "manufacturer": "Generic", "url": "https://example.test/display.pdf"}
    downloader = DatasheetDownloader(tmp_path)
    cached = tmp_path / "LCD1602_Generic.pdf"
    response = Mock(content=b"<!DOCTYPE html><title>Product documentation</title>")
    fetch = Mock(return_value=response)
    monkeypatch.setattr(requests, "get", fetch)

    assert not downloader.download_datasheet(part)
    assert not cached.exists()

    cached.write_bytes(response.content)
    response.content = b"%PDF-1.4\n%%EOF"
    assert downloader.download_datasheet(part)
    assert cached.read_bytes() == response.content
    assert downloader.download_datasheet(part)
    assert fetch.call_count == 2
