"""Compile product reports with measured results and existing catalog economics."""
import csv
import json

from build import ROOT

CATALOG = ROOT.parents[1]


def load_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def money(value):
    value = float(value)
    return f"{'-' if value < 0 else ''}NT${abs(value):,.2f}"


def purchase_context(row):
    quote = row["quoted_buy_ntd"]
    first = row["first_internal_unit_ntd"]
    repeat = row["build_cost_ntd"]
    if not quote:
        return (f"The catalog estimates {money(first)} for the first internal unit and {money(repeat)} per recurring build. "
                "It has no delivered comparator quote for a functionally equivalent unit.")
    cost = (f"The catalog lists a comparator at {money(quote)}, a first internal unit at {money(first)}, "
            f"and recurring build cost of {money(repeat)}. Match the host interface, included parts, coverage and calibration needs before crediting savings.")
    qty = row["internal_qty_to_recover_design"]
    if qty:
        cost += (f" Under those assumptions the modeled saving per repeat build is {money(row['repeat_internal_unit_saving_ntd'])}. "
                 f" It takes {qty} internal units to recover design costs.")
    return cost


def write_reports():
    products = load_csv(CATALOG/"products.csv")
    returns = load_csv(CATALOG/"returns.csv")
    notes = json.loads((ROOT/"study-notes.json").read_text(encoding="utf-8"))
    outcomes = json.loads((ROOT/"results.json").read_text(encoding="utf-8"))
    docs = ROOT/"reports"
    docs.mkdir(exist_ok=True)
    with (ROOT/"manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(("id", "title", "engineering", "physical_check", "report"))
        for product, revisions in outcomes.items():
            note = notes[product]
            title = products[product]["name"]
            result = float(returns[product]["result_at_25_sales_ntd"])
            catalog_price = float(returns[product]["price_ntd"])
            report = f"reports/{product}.md"
            writer.writerow((product,title,note["finding"],note["physical"],report))
            rows = [
                f"# {product} {title}", "",
                note["finding"], "", note["method"], "", note["source"], "",
                f"[Revised full-size SVG](../artifacts/{product}/revised.svg) · "
                f"[Baseline full-size SVG](../artifacts/{product}/baseline.svg)", "",
                "## Digital acceptance", "",
                "| Metric | Target | Baseline | Revised |", "| --- | --- | --- | --- |",
            ]
            for metric, revised in revisions["revised"].items():
                initial = revisions["baseline"][metric]
                relation = revised["relation"]
                rows.append(f"| {metric} | {relation} {revised['target']:g} {revised['unit']} | "
                            f"{initial['value']:g} {'pass' if initial['pass'] else 'fail'} | "
                            f"{revised['value']:g} {'pass' if revised['pass'] else 'fail'} |")
            rows += ["", "## Pattern and first physical check", "", note["use"], "", note["physical"],
                     "", f"The catalog models a price of NT${catalog_price:,.2f} and a 25-sale result of "
                     f"{'-' if result < 0 else ''}NT${abs(result):,.2f}. The design trial changes engineering evidence. "
                     "The estimate still uses the catalog’s original budget and demand assumptions.",
                     "", purchase_context(returns[product]), "", "[Catalog products](../../../products.csv) · [Catalog returns](../../../returns.csv)", ""]
            replay = {"P076": "touch", "P078": "readings", "P107": "indicator"}.get(product)
            if replay:
                rows[8] += f" · [Revised synthetic readings](../artifacts/{product}/revised-{replay}.csv)"
            (ROOT/report).write_text("\n".join(rows), encoding="utf-8")


if __name__ == "__main__":
    write_reports()
