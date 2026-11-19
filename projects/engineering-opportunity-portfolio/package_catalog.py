"""Package the current catalog and its historical evidence as a reproducible offline ZIP."""

import argparse
import csv
from html.parser import HTMLParser
import io
import posixpath
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import unquote, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "catalog"
ARCHIVE = ROOT / "archive"
SUPPORT = "archive/supporting-records/"
DEFAULT_OUTPUT = ROOT / "HS-manufacturing-catalog.zip"
START = """Hardware Splicer manufacturing catalog

Extract the entire ZIP, then open catalog/index.html in your browser.
Browse tested designs in catalog/engineering/trials.html.
Edit unit-economics assumptions in catalog/HS-manufacturing-catalog.xlsx.
Read catalog/engineering/README.md for optional engineering replay instructions.

The earlier edition and its 620-configuration index are in archive/.
Its supporting records include the original cost sheets, engineering examples
and comparisons. Links to the dock and plotter open their packaged design releases.
External supplier and upstream project websites require an internet connection.
"""

# Historical documents refer to these project files using checkout-relative links.
# Keeping that directory layout makes their spreadsheets, examples and source portable.
SUPPORT_FILES = (
    "arm-solder-cell/BUILD_OR_BUY.md",
    "arm-solder-cell/cost-inputs.csv",
    "arm-solder-cell/header.json",
    "arm-solder-cell/outputs/margin-review-20261119/margin-comparison.xlsx",
    "bench-probe-fixture/geometry.json",
    "cabinet-logger-digital/README.md",
    "cabinet-logger-digital/buy-or-build.md",
    "cabinet-logger-digital/demo.csv",
    "cabinet-logger-digital/firmware/boot.py",
    "cabinet-logger-digital/firmware/code.py",
    "cabinet-logger-digital/firmware/sample.py",
    "cabinet-logger-digital/layout.py",
    "cabinet-logger-digital/layout.step",
    "cabinet-logger-digital/logger.py",
    "engineering-opportunity-portfolio/expanded-market-comparison.md",
    "engineering-opportunity-portfolio/four-wire-seed-examples.zip",
    "engineering-opportunity-portfolio/machine-value-trials/digital-checks.json",
    "engineering-opportunity-portfolio/machine-value-trials/pcb_envelope_carrier_candidate.step",
    "engineering-opportunity-portfolio/machine-value-trials/README.md",
    "engineering-opportunity-portfolio/market-screen-2026-11-18.md",
    "engineering-opportunity-portfolio/offer-comparison.csv",
    "engineering-opportunity-portfolio/taiwan-lab-seeds.md",
)
# These three references have an equivalent entry point elsewhere in the release.
CHECKOUT_LINKS = {
    SUPPORT
    + "ender3-penplotter-digital/README.md": "catalog/engineering/reuse-wave/P002/README.md",
    SUPPORT
    + "pcb-inspection-nest/README.md": "catalog/engineering/reuse-wave/P001/README.md",
    SUPPORT
    + "engineering-opportunity-portfolio/product-index.md": "catalog/index.html",
}
# Bare destinations used by the project's inline Markdown links and images.
MARKDOWN_LINK = re.compile(r"(?<=\]\()([^)\s]+)(?=\))")


def input_files():
    sources = {}
    for directory in (CATALOG, ARCHIVE):
        for path in directory.rglob("*"):
            relative = path.relative_to(ROOT)
            if any(
                part.startswith(".") or part == "__pycache__" for part in relative.parts
            ):
                continue
            if path.suffix in {".pyc", ".pyo", ".tmp", ".bak"} or path.name.endswith(
                "~"
            ):
                continue
            if path.is_file():
                sources[relative.as_posix()] = path
    for relative in SUPPORT_FILES:
        sources[SUPPORT + relative] = ROOT.parent / relative
    return sources


def member_bytes(name, source):
    content = source.read_bytes()
    if not (name.startswith(SUPPORT) and name.endswith(".md")):
        return content
    parent = posixpath.dirname(name)

    def portable_link(match):
        original = match.group()
        canonical = posixpath.normpath(posixpath.join(parent, original))
        if canonical in CHECKOUT_LINKS:
            return posixpath.relpath(CHECKOUT_LINKS[canonical], parent)
        return original

    return MARKDOWN_LINK.sub(portable_link, content.decode()).encode()


class HtmlLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        self.targets.extend(
            value for key, value in attrs if value and key in {"href", "src"}
        )


def verify_release(bundle):
    if bundle.testzip():
        raise ValueError("Archive checksum failure")
    files = set(bundle.namelist())
    directories = {str(parent) for name in files for parent in Path(name).parents}
    for name in files:
        if name.endswith(".html"):
            links = HtmlLinks()
            links.feed(bundle.read(name).decode())
            links.close()
            targets = links.targets
        elif name.endswith(".md"):
            targets = MARKDOWN_LINK.findall(bundle.read(name).decode())
        else:
            continue
        for target in targets:
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            destination = posixpath.normpath(
                posixpath.join(posixpath.dirname(name), unquote(parsed.path))
            )
            if destination not in files and destination not in directories:
                raise ValueError(f"Missing offline link in {name}: {target}")
    rows = csv.DictReader(io.StringIO(bundle.read("catalog/products.csv").decode()))
    for row in rows:
        if row["engineering_path"]:
            bundle.getinfo("catalog/" + row["engineering_path"].split("#", 1)[0])


def build(output=DEFAULT_OUTPUT):
    output = Path(output).resolve()
    if any(output.is_relative_to(root) for root in (CATALOG, ARCHIVE)):
        raise ValueError(
            "Choose an output path outside the catalog and archive source directories."
        )
    sources = input_files()
    if output in sources.values():
        raise ValueError(f"The output would overwrite an input: {output}")
    with NamedTemporaryFile(dir=output.parent, suffix=".zip", delete=False) as staging:
        temp = Path(staging.name)
    try:
        with ZipFile(temp, "w") as bundle:
            for name in sorted([*sources, "START-HERE.txt"]):
                content = (
                    START.encode()
                    if name == "START-HERE.txt"
                    else member_bytes(name, sources[name])
                )
                # Fixed ZIP epoch, Unix permissions and order remove checkout and clock differences.
                info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                bundle.writestr(
                    info, content, compress_type=ZIP_DEFLATED, compresslevel=5
                )
        with ZipFile(temp) as saved:
            verify_release(saved)
        temp.chmod(0o644)
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build(parser.parse_args().output)
