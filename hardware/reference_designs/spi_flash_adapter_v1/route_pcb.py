#!/usr/bin/env python3
"""Route the SPI adapter using a pinned Freerouting release and import to KiCad."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import tempfile
from pathlib import Path

import pcbnew

from generate_pcb import build_board


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "spi_flash_adapter_v1.kicad_pcb"
EXPECTED_ROUTER_VERSION = "Freerouting v2.4.1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--freerouting",
        required=True,
        type=Path,
        help="path to the Freerouting v2.4.1 launcher",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    router = args.freerouting.resolve()
    if not router.is_file():
        raise SystemExit(f"Freerouting launcher does not exist: {router}")

    version = subprocess.run(
        [str(router), "-h"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).stdout
    if EXPECTED_ROUTER_VERSION not in version:
        raise SystemExit(
            f"expected {EXPECTED_ROUTER_VERSION!r} in router output; got:\n{version}"
        )

    with tempfile.TemporaryDirectory(prefix="hs-spi-route-") as temporary:
        temporary_path = Path(temporary)
        unrouted = temporary_path / "spi_flash_adapter_v1_unrouted.kicad_pcb"
        netlist = temporary_path / "spi_flash_adapter_v1.xml"
        design = temporary_path / "spi_flash_adapter_v1.dsn"
        session = temporary_path / "spi_flash_adapter_v1.ses"

        subprocess.run(
            [
                "kicad-cli",
                "sch",
                "export",
                "netlist",
                str(HERE / "spi_flash_adapter_v1.kicad_sch"),
                "--format",
                "kicadxml",
                "-o",
                str(netlist),
            ],
            check=True,
        )
        board = build_board(netlist)
        pcbnew.SaveBoard(str(unrouted), board)
        if not pcbnew.ExportSpecctraDSN(board, str(design)):
            raise SystemExit("KiCad failed to export the Specctra DSN")

        completed = subprocess.run(
            [
                str(router),
                "-de",
                str(design),
                "-do",
                str(session),
                "--gui.enabled=false",
                "--router.copperToEdgeClearanceUm=500",
                "-mp",
                "50",
                "-mt",
                "1",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if "0 unrouted and 0 violations" not in completed.stdout:
            raise SystemExit(f"router did not report complete routing:\n{completed.stdout}")
        if not session.is_file():
            raise SystemExit("router did not create a Specctra session")
        if not pcbnew.ImportSpecctraSES(board, str(session)):
            raise SystemExit("KiCad failed to import the Specctra session")

        args.output.parent.mkdir(parents=True, exist_ok=True)
        pcbnew.SaveBoard(str(args.output), board)

    print(f"wrote {args.output}")
    print(f"sha256 {sha256(args.output)}")


if __name__ == "__main__":
    main()
