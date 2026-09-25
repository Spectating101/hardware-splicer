#!/usr/bin/env python3
"""Bisect KiCad load failures in the generated ProofPod schematic.

Diagnostic only: this does not grant design authority and always exits zero after
printing the matrix so CI can continue to the fail-closed canonical verifier.
"""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
from pathlib import Path

import kicad_sch_api as ksa


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("proofpod_generator", HERE / "generate_schematic.py")
GEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GEN)


def loadable(path: Path) -> tuple[bool, str]:
    out = path.with_suffix(".xml")
    result = subprocess.run(
        ["kicad-cli", "sch", "export", "netlist", str(path), "--format", "kicadxml", "-o", str(out)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return result.returncode == 0, result.stdout.strip()


def single_symbol(lib_id: str, reference: str, value: str, footprint: str, properties: dict, output: Path) -> None:
    sch = ksa.create_schematic(f"PF-001 load diagnostic {reference}")
    sch.library.add_library_path(HERE / "HardwareSplicer.kicad_sym")
    kwargs = dict(properties)
    if footprint:
        kwargs["footprint"] = footprint
    sch.components.add(lib_id, reference, value, position=(80, 80), **kwargs)
    sch.save(output)


def main() -> None:
    seen: set[str] = set()
    rows: list[tuple[str, str, bool, str]] = []
    with tempfile.TemporaryDirectory(prefix="proofpod-load-bisect-") as td:
        root = Path(td)
        for index, (lib_id, ref, value, _position, footprint, properties) in enumerate(GEN.PARTS):
            if lib_id in seen:
                continue
            seen.add(lib_id)
            path = root / f"{index:02d}-{ref}.kicad_sch"
            try:
                single_symbol(lib_id, ref, value, footprint, properties, path)
                ok, detail = loadable(path)
            except Exception as exc:
                ok, detail = False, f"{type(exc).__name__}: {exc}"
            rows.append((lib_id, ref, ok, detail))

        all_parts = ksa.create_schematic("PF-001 all-components load diagnostic")
        all_parts.library.add_library_path(HERE / "HardwareSplicer.kicad_sym")
        for lib_id, ref, value, position, footprint, properties in GEN.PARTS:
            kwargs = dict(properties)
            if footprint:
                kwargs["footprint"] = footprint
            all_parts.components.add(lib_id, ref, value, position=position, **kwargs)
        all_path = root / "all-components.kicad_sch"
        all_parts.save(all_path)
        all_ok, all_detail = loadable(all_path)

    print("PF-001 KiCad symbol load matrix")
    for lib_id, ref, ok, detail in rows:
        print(f"{'PASS' if ok else 'FAIL'}\t{ref}\t{lib_id}\t{detail}")
    print(f"{'PASS' if all_ok else 'FAIL'}\tALL_COMPONENTS_NO_WIRING\t{all_detail}")


if __name__ == "__main__":
    main()
