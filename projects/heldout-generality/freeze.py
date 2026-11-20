"""Freeze an out-of-sample, stratified PCB cohort from the upstream corpus.

This script is for creating a new lock only. Never re-select boards in a replay.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

CORPUS_REV = "1e999b4eefd5fdfcc90dc376d2882390245a8e0d"
SEED = "hs-generality-20261120-v1"
MAX_PADS = 450
MAX_SEGMENTS = 1100
PER_STRATUM = 2
STRATA = [(2, True), (2, False), (4, True), (4, False)]


def blob(repo: Path, path: str) -> bytes:
    if path.startswith("/") or ".." in Path(path).parts:
        raise ValueError("unsafe path")
    return subprocess.check_output(
        ["git", "-C", str(repo), "show", CORPUS_REV + ":" + path],
        timeout=90,
    )


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def choose(manifest: list[dict]) -> list[dict]:
    results, seen_repositories = [], set()
    for layers, clean in STRATA:
        candidates = [
            row for row in manifest
            if row["copper_layers"] == layers
            and (row["ref_drv"] == 0) == clean
            and row["pads"] <= MAX_PADS
            and row["segments"] <= MAX_SEGMENTS
            and row["parts"] >= 5
        ]
        candidates.sort(key=lambda row: sha((SEED + row["id"]).encode()))
        count = 0
        for row in candidates:
            if row["repo"] in seen_repositories:
                continue
            results.append({"id": row["id"], "stratum": f"{layers}layer-{'clean' if clean else 'inherited-drc'}", "metadata": row})
            seen_repositories.add(row["repo"])
            count += 1
            if count == PER_STRATUM:
                break
        if count != PER_STRATUM:
            raise ValueError("underpopulated stratum")
    return results


def freeze(repo: Path, destination: Path) -> dict:
    repo = repo.resolve(strict=True)
    revision = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, timeout=10,
    ).strip()
    if revision != CORPUS_REV:
        raise ValueError(f"corpus HEAD mismatch: {revision}")
    raw = blob(repo, "manifest.json")
    manifest = json.loads(raw)
    if len(manifest) != 235:
        raise ValueError("expected corpus size 235")
    selected = choose(manifest)
    for record in selected:
        prefix = "boards/" + record["id"] + "/"
        source = json.loads(blob(repo, prefix + "SOURCE.json"))
        if source["repo"] != record["metadata"]["repo"] or source["commit"] != record["metadata"]["commit"]:
            raise ValueError("original source provenance disagrees with manifest")
        files = ["board.kicad_pcb", "board.kicad_pro", "SOURCE.json"]
        tree = subprocess.check_output(
            ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", CORPUS_REV, "--", prefix],
            text=True, timeout=30,
        ).splitlines()
        if prefix + "board.kicad_dru" in tree:
            files.append("board.kicad_dru")
        licence = source.get("licence_file")
        if licence and prefix + licence in tree:
            files.append(licence)
        record["source_url"] = source.get("url")
        record["files_sha256"] = {name: sha(blob(repo, prefix + name)) for name in files}
    lock = {
        "schema": "hs.heldout_pcb_cohort.v1",
        "corpus_url": "https://github.com/punkfab/pcb-corpus",
        "corpus_commit": CORPUS_REV,
        "manifest_sha256": sha(raw),
        "seed": SEED,
        "selection": "SHA256(seed + id) ascending; 2 per (copper_layers x zero-versus-nonzero ref_drv), unique original repo; >=5 parts, <=450 pads, <=1100 segments",
        "case_count": len(selected),
        "cases": selected,
    }
    if destination.exists():
        raise FileExistsError("refusing to overwrite the frozen cohort")
    destination.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    return lock


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--corpus-repo", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path(__file__).with_name("cases.lock.json"))
    args = p.parse_args()
    result = freeze(args.corpus_repo, args.out)
    print("FROZEN", result["case_count"], "boards", result["manifest_sha256"])
