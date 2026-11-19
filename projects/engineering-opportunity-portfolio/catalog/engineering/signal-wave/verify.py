"""Replay the catalog's electrical reference models and check their shipped CSV witnesses."""

import argparse
import csv
import json
import tempfile
from pathlib import Path
import circuits

HERE = Path(__file__).resolve().parent
MODELS = {
    "P038": circuits.logger,
    "P043": circuits.harness,
    "P065": circuits.capture,
    "P067": circuits.winding,
    "P070": circuits.decades,
    "P071": circuits.kelvin,
    "P074": circuits.pedal,
    "P075": circuits.mux,
    "P213": circuits.tally,
    "P214": circuits.pads,
    "P215": circuits.held_keys,
    "P219": circuits.held_keys,
    "P222": circuits.journal,
    "P223": circuits.timer,
    "P066": circuits.servo,
    "P073": circuits.uart,
    "P211": circuits.attenuator,
    "P212": circuits.headphones,
    "P218": circuits.access_button,
}


def write_rows(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(fields)
        w.writerows(rows)


def generate(out):
    if not __debug__:
        raise SystemExit(
            "Run Python with assertions enabled for the engineering checks."
        )
    designs = json.loads((HERE / "cases.json").read_text())
    if designs.keys() != MODELS.keys():
        raise ValueError("Study registration differs from input configuration")
    manifest = []
    for ident, design in designs.items():
        folder = out / ident
        folder.mkdir(parents=True, exist_ok=True)
        fields, trace, metrics = MODELS[ident](design["inputs"])
        write_rows(folder / "trace.csv", fields, trace)
        (folder / "results.json").write_text(json.dumps(metrics, indent=2) + "\n")
        results = "\n".join(
            f"| {k.replace('_', ' ')} | {v} |" for k, v in metrics.items()
        )
        report = (
            f"# {ident} · {design['name']}\n\n{design['trial']}\n\n"
            f"**Signal path.** {design['connection']}.\n\n"
            f"| Simulated result | Value |\n|---|---|\n{results}\n\n"
            f"**Bench acceptance.** {design['physical']}\n\n"
            "Each trace is synthetic. The component values, timing and contacts are design inputs. "
            "These files exercise the specified subsystem before selecting and measuring real hardware.\n\n"
            "[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)\n"
        )
        (folder / "README.md").write_text(report)
        manifest.append(
            (
                ident,
                design["name"],
                "Digital signal model. " + design["trial"],
                design["physical"],
                f"{ident}/README.md",
            )
        )
    write_rows(
        out / "manifest.csv",
        ["id", "title", "engineering", "physical_check", "report"],
        manifest,
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--publish", action="store_true")
    if p.parse_args().publish:
        generate(HERE)
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)
        generate(dest)
        for source in (f for f in dest.rglob("*") if f.is_file()):
            target = HERE / source.relative_to(dest)
            if source.read_bytes() != target.read_bytes():
                raise ValueError(f"Replay differs from shipped record {target}")
    print(f"{len(MODELS)} signal models replayed with adverse controls")


if __name__ == "__main__":
    main()
