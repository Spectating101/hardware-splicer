"""Rebuild the offline catalog and default returns from the adjacent CSV inputs."""

import csv
import json
import math
from pathlib import Path
from engineering.register import main as index_engineering


HERE = Path(__file__).resolve().parent
FX = 32.947
TWD_PER_UNIT = {"TWD": 1, "USD": FX, "IDR": FX / 18252}
WAGE = 600


def read(name):
    with (HERE / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write(name, rows):
    with (HERE / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def evaluate(row, quote):
    price, parts, process, minutes, shipping, fee, flat, hours, prototype = (
        float(row[k]) for k in ("price", "parts", "loss", "minutes", "ship", "fee", "flat", "hrs", "proto")
    )
    assert price > 0 and 0 <= fee < 1
    assert min(parts, process, minutes, shipping, flat, hours, prototype) >= 0
    production = parts + process + minutes / 60 * WAGE
    fixed = hours * WAGE + prototype
    recurring = production + shipping + fee * price + flat
    contribution = price - recurring
    first = production + fixed
    ask = None
    if quote and quote["currency"] in TWD_PER_UNIT:
        ask = float(quote["ask_native"]) * TWD_PER_UNIT[quote["currency"]]
    comparable = ask is not None and quote["comparison"] == "Same job"
    saving = ask - production if comparable else None
    matched_price = min(price, ask) if comparable else None
    batch25_spend = fixed + 25 * recurring
    batch25_result = 25 * price - batch25_spend
    sold = 17
    down_price = .8 * price
    made = sold if row["market"] == "Download" else 25
    stress = sold * (down_price * (1 - fee) - shipping - flat) - made * production - fixed
    fields = {
        "id": row["id"], "product": row["name"], "family": row["group"],
        "price_ntd": price, "price_usd": price / FX, "parts_ntd": parts,
        "build_cost_ntd": production, "build_cost_usd": production / FX,
        "launch_ntd": fixed, "first_internal_unit_ntd": first,
        "first_internal_unit_usd": first / FX, "recurring_cost_ntd": recurring,
        "contribution_ntd": contribution, "contribution_margin_pct": 100 * contribution / price,
        "sales_to_recover_launch": math.ceil(fixed / contribution) if contribution > 0 else None,
        "result_at_1_sale_ntd": contribution - fixed,
        "result_at_10_sales_ntd": 10 * contribution - fixed,
        "outlay_at_25_ntd": batch25_spend, "result_at_25_sales_ntd": batch25_result,
        "result_at_25_sales_usd": batch25_result / FX, "return_on_cost_25_pct": 100 * batch25_result / batch25_spend,
        "result_at_100_sales_ntd": 100 * contribution - fixed,
        "max_design_hours_supported_at_25": (25 * contribution - prototype) / WAGE,
        "max_additional_custom_hours_per_sale": max(0, contribution) / WAGE,
        "minimum_price_25_ntd": (production + shipping + flat + fixed / 25) / (1 - fee),
        "downside_stock_25_result_ntd": stress,
        "downside_build_to_order_result_ntd": sold * (down_price * (1 - fee) - shipping - flat - production) - fixed,
        "quoted_buy_ntd": ask,
        "price_capped_at_comparable_ntd": matched_price,
        "result_at_capped_price_25_ntd": 25 * (matched_price * (1 - fee) - production - shipping - flat) - fixed if comparable else None,
        "first_internal_unit_saving_ntd": ask - first if comparable else None,
        "repeat_internal_unit_saving_ntd": saving,
        "internal_qty_to_recover_design": max(1, math.ceil(fixed / saving)) if comparable and saving > 0 else None,
    }
    return {k: round(v, 2) if isinstance(v, float) else v for k, v in fields.items()}


def main():
    products = read("products.csv")
    ids = {r["id"] for r in products}
    assert len(ids) == len(products)
    assert len({r["name"].casefold() for r in products}) == len(products)
    quotes = read("purchase-comparisons.csv")
    comparisons = {r["id"]: r for r in quotes}
    assert len(comparisons) == len(quotes) and comparisons.keys() <= ids
    for q in quotes:
        assert q["comparison"] in {"Same job", "Partial scope"}
        assert float(q["ask_native"]) > 0 and q["url"].startswith("https://")
    returns = [evaluate(r, comparisons.get(r["id"])) for r in products]
    write("returns.csv", returns)
    index_engineering()
    products = read("products.csv")
    # Escape the JSON script boundary even if future supplier text contains HTML.
    listings = read("all-purchase-listings.csv")
    assert all(r["id"] in ids for r in listings)
    by_id = {r["id"]: r for r in products}
    listing_cases = []
    for q in listings:
        model = evaluate(by_id[q["id"]], q)
        listing_cases.append({
            "id": q["id"], "product": q["product"], "market_of_listing": q["country"],
            "comparator_item": q["item"], "scope": q["comparison"], "currency": q["currency"],
            "ask_native": q["ask_native"], "ask_ntd": model["quoted_buy_ntd"],
            "first_internal_build_ntd": model["first_internal_unit_ntd"],
            "first_internal_unit_saving_ntd": model["first_internal_unit_saving_ntd"],
            "repeat_internal_unit_saving_ntd": model["repeat_internal_unit_saving_ntd"],
            "internal_qty_to_recover_design": model["internal_qty_to_recover_design"],
            "hs_price_capped_at_ask_ntd": model["price_capped_at_comparable_ntd"],
            "result_at_capped_price_25_ntd": model["result_at_capped_price_25_ntd"],
            "caveat": q["caveat"], "url": q["url"],
        })
    write("buy-vs-build-by-listing.csv", listing_cases)
    data = json.dumps({"products": products, "quotes": comparisons, "listings": listings}, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    template = (HERE / "viewer.template.html").read_text(encoding="utf-8")
    assert template.count("<!--CATALOG_DATA-->") == 1
    (HERE / "index.html").write_text(template.replace("<!--CATALOG_DATA-->", data), encoding="utf-8")
    print(f"{len(products)} products, {len(quotes)} priced buying comparisons")


if __name__ == "__main__":
    main()
