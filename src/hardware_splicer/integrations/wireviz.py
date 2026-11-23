"""Optional offline WireViz CLI boundary; accepts only HS-generated documents."""
from __future__ import annotations

import csv
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

MAX_OUTPUT_BYTES = 4_000_000


class WireVizError(RuntimeError):
    pass


def render_wireviz(document: str) -> dict:
    executable = os.getenv("HARDWARE_SPLICER_WIREVIZ_EXECUTABLE") or shutil.which("wireviz")
    if not executable or not shutil.which("dot"):
        raise WireVizError("WireViz and Graphviz are required for --render; the wireviz document and cut list work without them")
    with tempfile.TemporaryDirectory(prefix="hs-wireviz-") as scratch:
        root = Path(scratch)
        source = root / "harness.wireviz"
        source.write_text(document, encoding="utf-8")
        try:
            version = subprocess.run([executable, "--version"], cwd=root, capture_output=True, text=True, timeout=10)
            if version.returncode != 0 or "wireviz" not in version.stdout.casefold():
                raise WireVizError("WireViz version probe failed")
            result = subprocess.run([executable, "-f", "st", str(source)], cwd=root,
                                    capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WireVizError("WireViz execution failed or timed out") from exc
        if result.returncode != 0:
            raise WireVizError("WireViz could not render the generated harness")
        outputs = {}
        for key, name in (("svg", "harness.svg"), ("bom_tsv", "harness.bom.tsv")):
            path = root / name
            if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= MAX_OUTPUT_BYTES:
                raise WireVizError("WireViz output missing or over limit")
            outputs[key] = path.read_text(encoding="utf-8")
        validate_svg(outputs["svg"])
        outputs["bom_tsv"] = spreadsheet_safe_tsv(outputs["bom_tsv"])
        return {"status": "rendered", "version": version.stdout.strip()[:256],
                "input_sha256": hashlib.sha256(document.encode()).hexdigest(),
                "output_sha256": {key: hashlib.sha256(value.encode()).hexdigest() for key, value in outputs.items()},
                "outputs": outputs}


def spreadsheet_safe_tsv(value: str) -> str:
    """Retain native BOM values as text, including embedded tabs/newlines."""
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t")
    for row in csv.reader(io.StringIO(value), delimiter="\t"):
        writer.writerow(["'" + cell if cell.lstrip().startswith(("=", "+", "-", "@")) or cell.startswith(("\t", "\r", "\n")) else cell for cell in row])
    return output.getvalue()


def validate_svg(svg: str) -> None:
    """Reject active/external content before retaining or serving a native SVG."""
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise WireVizError("WireViz output is not valid SVG") from exc
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise WireVizError("WireViz output is not an SVG document")
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].casefold()
        if tag in {"script", "foreignobject", "image", "use", "a", "style"}:
            raise WireVizError("WireViz SVG contains active or external elements")
        for key, value in element.attrib.items():
            attribute = key.rsplit("}", 1)[-1].casefold()
            if attribute.startswith("on") or attribute in {"href", "src"} or "url(" in value.casefold():
                raise WireVizError("WireViz SVG contains active or external attributes")
