#!/usr/bin/env python3
"""Build a hash-sealed review/manufacturing package from the canonical KiCad files."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from design_checks import RECEIPT_INPUTS


HERE = Path(__file__).resolve().parent
SCHEMATIC = HERE / "spi_flash_adapter_v1.kicad_sch"
BOARD = HERE / "spi_flash_adapter_v1.kicad_pcb"
COPY_FILES = (
    "README.md",
    "verification.json",
    *RECEIPT_INPUTS.values(),
    "generate_schematic.py",
    "generate_pcb.py",
    "route_pcb.py",
    "build_package.py",
)
FIXED_ZIP_TIME = (2026, 9, 15, 0, 0, 0)


def run(*args: str) -> None:
    environment = dict(os.environ)
    environment["SOURCE_DATE_EPOCH"] = "1789430400"
    subprocess.run(list(args), check=True, env=environment)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_generated_timestamps(root: Path) -> None:
    """Remove KiCad wall-clock fields while preserving valid textual EDA outputs."""

    replacements = (
        (r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:?\d{2}", "2026-09-15T00:00:00+08:00"),
        (r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "2026-09-15 00:00:00"),
        (r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}", "2026/09/15 00:00:00"),
    )
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text()
        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text)
        path.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "out" / "spi_flash_adapter_v1-review-package.zip",
    )
    args = parser.parse_args()

    run(sys.executable, str(HERE / "verify_design.py"))
    with tempfile.TemporaryDirectory(prefix="hs-spi-package-") as temporary:
        root = Path(temporary) / "spi_flash_adapter_v1"
        manufacturing = root / "manufacturing"
        review = root / "review"
        manufacturing.mkdir(parents=True)
        review.mkdir()

        for name in COPY_FILES:
            shutil.copy2(HERE / name, root / name)

        run(
            "kicad-cli",
            "sch",
            "export",
            "svg",
            str(SCHEMATIC),
            "--black-and-white",
            "-o",
            str(review),
        )
        run(
            "kicad-cli",
            "pcb",
            "export",
            "gerbers",
            str(BOARD),
            "--layers",
            "F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,Edge.Cuts",
            "--precision",
            "6",
            "-o",
            str(manufacturing),
        )
        run(
            "kicad-cli",
            "pcb",
            "export",
            "drill",
            str(BOARD),
            "--format",
            "excellon",
            "--excellon-units",
            "mm",
            "--excellon-separate-th",
            "-o",
            str(manufacturing),
        )
        run(
            "kicad-cli",
            "pcb",
            "export",
            "pos",
            str(BOARD),
            "--format",
            "csv",
            "--units",
            "mm",
            "--side",
            "both",
            "--exclude-fp-th",
            "--exclude-dnp",
            "-o",
            str(manufacturing / "spi_flash_adapter_v1-positions.csv"),
        )
        run(
            "kicad-cli",
            "pcb",
            "export",
            "svg",
            str(BOARD),
            "--layers",
            "F.Cu,F.Silkscreen,Edge.Cuts",
            "--page-size-mode",
            "2",
            "--mode-single",
            "-o",
            str(review / "spi_flash_adapter_v1-top.svg"),
        )
        normalize_generated_timestamps(manufacturing)
        normalize_generated_timestamps(review)

        payloads = sorted(path for path in root.rglob("*") if path.is_file())
        sums = "".join(
            f"{digest(path)}  {path.relative_to(root).as_posix()}\n" for path in payloads
        )
        (root / "SHA256SUMS.txt").write_text(sums)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                relative = Path(root.name) / path.relative_to(root)
                info = zipfile.ZipInfo(relative.as_posix(), FIXED_ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes(), compresslevel=9)

    print(f"wrote {args.output}")
    print(f"sha256 {digest(args.output)}")


if __name__ == "__main__":
    main()
