"""Index verified batch manifests and render an offline, searchable engineering reader."""

import csv
import html
import io
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

HERE = Path(__file__).resolve().parent
CAT = HERE.parent
LABELS = {
    "field-wave": "Field and aquaculture instruments",
    "marine-wave": "Tank inspection and ROV accessories",
    "savings-wave": "Farm and lab purchase alternatives",
    "imaging-wave": "Camera and lighting fixtures",
    "scanner-wave": "Film digitizing and camera positioning",
    "shop-wave": "Craft tooling",
    "bench-wave": "Workshop devices and access aids",
    "robot-wave": "Teaching robot components",
    "reuse-wave": "Replayed HS design releases",
    "signal-wave": "Electrical signals and controls",
    "studio-wave": "Studio equipment",
    "fixture-wave": "Reusable shop fixtures",
    "platform-wave": "Complete platform feasibility",
    "harvest-wave": "Farm and process tooling",
    "metrology-wave": "Workshop metrology fixtures",
    "margin-wave": "Products near break-even",
}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    stream = io.StringIO(newline="")
    w = csv.DictWriter(stream, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    path.write_bytes(stream.getvalue().encode())


def excerpt(path, fragment):
    text = path.read_text()
    if not fragment:
        return text
    lines = text.splitlines()
    for i, line in enumerate(lines):
        heading = re.fullmatch(r"(#{1,6})\s+(.+)", line)
        if not heading:
            continue
        if heading[2].strip().casefold() == fragment.casefold():
            for j in range(i + 1, len(lines)):
                if re.match(r"^#{1," + str(len(heading[1])) + r"}\s", lines[j]):
                    break
            else:
                j = len(lines)
            return "\n".join(lines[i:j])
    raise ValueError(f"Missing report section {fragment} in {path}")


def markdown(text, path):
    engine = MarkdownIt("commonmark", {"html": False}).enable("table")
    tokens = engine.parse(text)

    def rebase(tokens):
        for t in tokens:
            if t.type in {"link_open", "image"}:
                attr = "href" if t.type == "link_open" else "src"
                ref = t.attrGet(attr)
                parts = urlsplit(ref)
                if not parts.scheme and not parts.netloc and parts.path:
                    target = (path.parent / unquote(parts.path)).resolve()
                    t.attrSet(
                        attr,
                        os.path.relpath(target, HERE)
                        + ("#" + parts.fragment if parts.fragment else ""),
                    )
            # Demote headings within a product section, keeping the document outline usable.
            if t.type in {"heading_open", "heading_close"}:
                t.tag = "h" + str(min(6, 2 + int(t.tag[1:])))
            if t.children:
                rebase(t.children)

    rebase(tokens)
    return engine.renderer.render(tokens, engine.options, {})


def checked_report(folder, ref):
    relative, _, fragment = ref.partition("#")
    path = (folder / relative).resolve()
    if (
        not path.is_relative_to(folder.resolve())
        or path.suffix != ".md"
        or not path.is_file()
    ):
        raise ValueError(f"Invalid report path {ref} under {folder}")
    content = excerpt(path, fragment)
    return path, fragment, content


def published(products):
    records = {}
    for p in products:
        ident = p["id"]
        if (HERE / ident / "README.md").is_file():
            records[ident] = (
                ident,
                "Original engineering trials",
                p["engineering"],
                p["test"],
                "README.md",
            )
    for manifest in sorted(HERE.glob("*-wave/manifest.csv")):
        folder = manifest.parent
        if not (folder / "verify.py").is_file():
            raise ValueError(f"No replay for {folder}")
        for m in read_csv(manifest):
            ident = m["id"]
            if ident in records or not all(
                m.get(k, "").strip()
                for k in ("id", "title", "engineering", "physical_check", "report")
            ):
                raise ValueError(f"Missing or duplicate evidence for {ident}")
            records[ident] = (
                folder.name,
                LABELS[folder.name],
                m["engineering"],
                m["physical_check"],
                m["report"],
            )
    if not records.keys() <= {p["id"] for p in products}:
        raise ValueError("Unrecognized catalog ID")
    return records


def main():
    products = read_csv(CAT / "products.csv")
    returns = {r["id"]: r for r in read_csv(CAT / "returns.csv")}
    records = published(products)
    coverage = []
    articles = {}
    esc = html.escape
    for p in products:
        ident = p["id"]
        r = returns[ident]
        positive = float(r["result_at_25_sales_ntd"]) > 0
        item = {
            "id": ident,
            "product": p["name"],
            "family": p["group"],
            "result_at_25_sales_ntd": r["result_at_25_sales_ntd"],
            "return_on_cost_25_pct": r["return_on_cost_25_pct"],
            "result_at_capped_price_25_ntd": r["result_at_capped_price_25_ntd"],
            "repeat_internal_saving_ntd": r["repeat_internal_unit_saving_ntd"],
            "extra_minutes_per_unit_before_batch_loss": round(
                float(r["result_at_25_sales_ntd"]) / 250, 2
            )
            if positive
            else "",
            "positive_at_25": "yes" if positive else "no",
            "published_digital_trial": "no",
            "study_group": "",
            "engineering_report": "",
            "engineering_result": "",
            "physical_check": p["test"],
        }
        if ident in records:
            name, group, result, physical, ref = records[ident]
            folder = HERE / name
            path, frag, content = checked_report(folder, ref)
            relpath = str(path.relative_to(HERE)) + ("#" + frag if frag else "")
            p.update(
                engineering_path="engineering/" + relpath,
                engineering=result,
                engineering_physical_check=physical,
            )
            item.update(
                published_digital_trial="yes",
                study_group=group,
                engineering_report=relpath,
                engineering_result=result,
                physical_check=physical,
            )
            links = f'<a href="{esc(relpath)}">Original report</a>'
            if name.endswith("-wave"):
                links += f' · <a href="{name}/verify.py">Group replay script</a>'
            articles[ident] = (
                f'<article id="{ident}"><h2>{ident} · {esc(p["name"])}</h2><p class="muted">{esc(group)} · {float(r["return_on_cost_25_pct"]):.1f}% modeled return at 25 sales</p>{markdown(content, path)}<p>{links} · <a href="#top">Back to index</a></p></article>'
            )
        elif p["engineering_path"]:
            raise ValueError(f"Published path without a registered trial: {ident}")
        else:
            p["engineering_physical_check"] = ""
        coverage.append(item)
    write_csv(CAT / "products.csv", products)
    write_csv(HERE / "coverage.csv", coverage)
    tested = [r for r in coverage if r["published_digital_trial"] == "yes"]
    tested.sort(key=lambda r: -float(r["return_on_cost_25_pct"]))
    positive_total = sum(r["positive_at_25"] == "yes" for r in coverage)
    positive_checked = sum(r["positive_at_25"] == "yes" for r in tested)
    header = f"{len(tested)} of {len(products)} catalog offers have replayable digital trials. They cover {positive_checked} of {positive_total} offers with a positive modeled result at 25 sales. Each product keeps its original cost assumptions. Physical performance and paid demand are open."
    links = []
    for item in tested:
        i = item["id"]
        links.append(
            f'<tr><td><a href="#{i}">{i} · {esc(item["product"])}</a></td><td>{esc(item["study_group"])}</td><td>{float(item["result_at_25_sales_ntd"]):,.0f}</td><td>{float(item["return_on_cost_25_pct"]):.1f}%</td></tr>'
        )
    decision_path = HERE / "build-decisions.md"
    decisions = markdown(decision_path.read_text(), decision_path)
    reader = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hardware Splicer engineering trials</title><style>
    *{{box-sizing:border-box}}body{{font:16px/1.52 system-ui,sans-serif;color:#20312e;background:#f8f8f3;max-width:1120px;margin:auto;padding:1.5rem}}h1,h2{{font-family:Georgia,serif;line-height:1.16}}h1{{font-size:2.5rem}}h2{{font-size:1.75rem}}a{{color:#075747}}article{{padding:1rem clamp(.8rem,3vw,2.5rem);margin:1.5rem 0;background:white;border-top:3px solid #397963;overflow-wrap:anywhere}}article table{{display:block;max-width:100%;overflow-x:auto}}img{{max-width:100%;height:auto}}pre,.scroll{{overflow:auto}}table{{border-collapse:collapse}}td,th{{border-bottom:1px solid #cbd4ce;padding:.4rem .65rem;text-align:left}}th{{background:#dce9df}}.muted{{color:#50645a}}code{{overflow-wrap:anywhere}}</style>
    <main id="top"><nav><a href="#decisions">Build decisions</a> · <a href="../index.html">Manufacturing catalog</a> · <a href="coverage.csv">All 270 offers and coverage (CSV)</a> · <a href="README.md">Replay instructions</a></nav><h1>Engineering trials</h1><p>{header}</p><p>Select a product to see its design, control case, results and physical acceptance check.</p><div class="scroll"><table><thead><tr><th>Product</th><th>Study group</th><th>25-sale profit, NT$</th><th>ROI</th></tr></thead><tbody>{"".join(links)}</tbody></table></div><article id="decisions">{decisions}</article>{"".join(articles[r["id"]] for r in tested)}</main></html>"""
    (HERE / "trials.html").write_text(reader)
    print(header)


if __name__ == "__main__":
    main()
