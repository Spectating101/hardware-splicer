from __future__ import annotations

import io
import json
import urllib.error
import urllib.parse

import pytest

from hardware_splicer import ruten_listings as rl


class _Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _detail(pid: str, price: int = 450, high: int | None = None) -> dict:
    return {"ProdId": pid, "ProdName": f"item {pid}", "PriceRange": [price, high or price], "SoldQty": 3, "StockQty": 9}


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(rl.time, "sleep", lambda s: None)


def _serve(monkeypatch, search_ids: list[str], details: dict[str, dict]):
    calls = []

    def fake(req, timeout):
        url = req.full_url
        calls.append(url)
        if "/search/" in url:
            return _Reply(json.dumps({"Rows": [{"Id": i} for i in search_ids]}).encode())
        ids = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["id"][0].split(",")
        return _Reply(json.dumps([details[i] for i in ids]).encode())

    monkeypatch.setattr(rl.urllib.request, "urlopen", fake)
    return calls


def test_search_joins_search_and_detail(monkeypatch, no_sleep):
    _serve(monkeypatch, ["11", "22"], {"11": _detail("11"), "22": _detail("22", 600)})
    client = rl.RutenClient()
    rows = rl.search("JGA25-370 encoder", client=client)
    assert [r["id"] for r in rows] == ["11", "22"]
    assert rows[0]["url"] == "https://www.ruten.com.tw/item/11/"
    assert rows[1]["price_twd"] == 600 and rows[1]["price_range"] == [600, 600]
    assert client.requests == 2


def test_masked_price_is_flagged(monkeypatch, no_sleep):
    _serve(monkeypatch, ["1", "2"], {"1": _detail("1", 993800), "2": _detail("2", 450)})
    rows = rl.search("x", client=rl.RutenClient())
    assert rows[0]["price_masked"] is True
    assert rows[1]["price_masked"] is False


def test_detail_batches_of_twenty(monkeypatch, no_sleep):
    ids = [str(i) for i in range(45)]
    calls = _serve(monkeypatch, ids, {i: _detail(i) for i in ids})
    rows = rl.search("x", limit=45, client=rl.RutenClient())
    assert len(rows) == 45
    assert sum("/prod/v2/" in c for c in calls) == 3


def test_network_error_retried_http_error_not(monkeypatch, no_sleep):
    attempts = []

    def flaky(req, timeout):
        attempts.append(1)
        if len(attempts) < 3:
            raise urllib.error.URLError("Temporary failure in name resolution")
        return _Reply(b'{"Rows": []}')

    monkeypatch.setattr(rl.urllib.request, "urlopen", flaky)
    assert rl.search("x", client=rl.RutenClient()) == []
    assert len(attempts) == 3

    attempts.clear()

    def http_500(req, timeout):
        attempts.append(1)
        raise urllib.error.HTTPError(req.full_url, 500, "err", {}, None)

    monkeypatch.setattr(rl.urllib.request, "urlopen", http_500)
    with pytest.raises(urllib.error.HTTPError):
        rl.search("x", client=rl.RutenClient())
    assert len(attempts) == 1
