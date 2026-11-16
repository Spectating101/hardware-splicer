#!/usr/bin/env python3
"""Create two controlled revisions of HS's existing SPI adapter PCB.

The revision difference is a *fixture-only* silkscreen annotation. The design
is never modified in HS's product tree, nor claimed to be production output.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def _git(root: Path, *args: str, commit=False, binary=False):
    env=os.environ.copy()
    if commit:
        env.update({
            "GIT_AUTHOR_NAME":"HS Controlled Benchmark",
            "GIT_AUTHOR_EMAIL":"hs-fixture@example.invalid",
            "GIT_COMMITTER_NAME":"HS Controlled Benchmark",
            "GIT_COMMITTER_EMAIL":"hs-fixture@example.invalid",
            "GIT_AUTHOR_DATE":"2026-11-05T00:00:00+00:00",
            "GIT_COMMITTER_DATE":"2026-11-05T00:00:00+00:00",
        })
    result=subprocess.run(
        ["git","-C",str(root),*args],env=env,
        capture_output=True,check=True,text=not binary,
    )
    return result.stdout if binary else result.stdout.strip()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args()
    repo=args.out.resolve()
    if repo.exists():
        raise SystemExit("Refusing to overwrite existing controlled fixture")
    repo.mkdir(parents=True)
    upstream=Path(__file__).resolve().parents[2]/"hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb"
    pcb=repo/upstream.name
    pcb.write_bytes(upstream.read_bytes())
    _git(repo,"init","-q")
    _git(repo,"add",pcb.name)
    _git(repo,"commit","-qm","baseline byte-for-byte copy of HS SPI adapter",commit=True)
    revision_a=_git(repo,"rev-parse","HEAD")
    source=pcb.read_text()
    annotation=(
        '\n\t(gr_text "HS DIFF FIXTURE: REVIEW ME"\n'
        '\t\t(at 125 110)\n'
        '\t\t(layer "F.SilkS")\n'
        '\t\t(uuid "9a1d6efa-cedb-458e-a365-076ae1cf4309")\n'
        '\t\t(effects (font (size 1 1) (thickness 0.15)))\n'
        '\t)\n'
    )
    assert source.rstrip().endswith(")")
    pcb.write_text(source.rstrip()[:-1]+annotation+")\n")
    _git(repo,"add",pcb.name)
    _git(repo,"commit","-qm","controlled F.SilkS annotation fixture",commit=True)
    revision_b=_git(repo,"rev-parse","HEAD")
    first=_git(repo,"show",revision_a+":"+pcb.name,binary=True)
    assert first==upstream.read_bytes()
    record={
        "fixture_only":True,
        "production_revision":False,
        "input_repository":str(repo),
        "pcb":str(pcb),
        "baseline_sha":revision_a,
        "controlled_revision_sha":revision_b,
        "original_source_sha256":hashlib.sha256(first).hexdigest(),
        "synthetic_change":"Only an F.SilkS text annotation; no electrical or mechanical changes",
        "baseline_is_byte_for_byte_hs_product":True,
    }
    (repo.parent/"kdif_fixture_manifest.json").write_text(json.dumps(record,indent=2)+"\n")
    print(json.dumps(record,indent=2))


if __name__=="__main__":
    main()
