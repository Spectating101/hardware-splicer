#!/usr/bin/env python3
"""Fetch PCB component detection checkpoints from known upstream sources."""

from __future__ import annotations

import argparse
import json
import hashlib
import importlib.util
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import shutil


def _load_remote_catalog() -> tuple[dict[str, str], ...]:
    resolver_path = Path(__file__).resolve().parents[1] / "src" / "vision" / "model_resolver.py"
    spec = importlib.util.spec_from_file_location("_circuit_ai_model_resolver", resolver_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load model resolver from {resolver_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.list_remote_pcb_models()


MODEL_DIR = Path("models/pcb")
KNOWN_SHA = {
    # Upstream repository-provided checksum for baseline model (known good).
    "yolo11n_best_thawed.pt": "be7f320411e9f8bc75d2925e46c6516e1b2387819df1f672bf3b50ec546184f8",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _format_time_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


def _download(url: str, destination: Path) -> None:
    tmp = destination.with_suffix(destination.suffix + ".tmp")
    urllib.request.urlretrieve(url, tmp)
    shutil.move(tmp, destination)


def _write_card(
    model_path: Path,
    source_url: str,
    checksum: Optional[str],
    overwrite: bool = False,
) -> Path:
    if not checksum:
        checksum = _sha256(model_path)

    card_path = model_path.with_suffix(model_path.suffix + ".card.json")
    if card_path.exists() and not overwrite:
        existing = card_path.read_text(encoding="utf-8")
        try:
            existing_json = json.loads(existing)
            if isinstance(existing_json, dict) and existing_json.get("sha256") == checksum:
                return card_path
        except Exception:
            pass

    payload = {
        "model_id": model_path.stem,
        "file": str(model_path),
        "sha256": checksum,
        "source": {
            "repository": "https://github.com/aryan-programmer/pcb-fault-detection",
            "path": str(model_path.name),
            "url": source_url,
            "retrieved_at": _format_time_iso(),
        },
        "task": "PCB component detection",
        "updated_by": "scripts/fetch_pcb_component_model.py",
    }
    card_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return card_path


def _prepare_destinations(model_file: str) -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return MODEL_DIR / model_file


def fetch_model(entry: dict[str, Any], overwrite: bool = False) -> tuple[bool, str]:
    remote_file = entry["file"]
    url = entry["url"]
    expected = KNOWN_SHA.get(remote_file)
    destination = _prepare_destinations(remote_file)

    if destination.exists() and not overwrite:
        digest = _sha256(destination)
        if expected and digest != expected:
            return False, f"exists but checksum mismatch (expected {expected}, got {digest}); use --overwrite"
        if not expected:
            print(f"skip exists {destination}")
            return True, f"already exists: {destination}"
        if destination.stat().st_size > 0 and digest == expected:
            print(f"skip exists (verified) {destination}")
            return True, f"already exists and matches expected checksum: {destination}"

    print(f"downloading {url} -> {destination}")
    _download(url, destination)

    digest = _sha256(destination)
    if expected and digest != expected:
        destination.unlink(missing_ok=True)
        return False, f"checksum mismatch: expected {expected}, got {digest}"

    card_path = _write_card(destination, url, expected, overwrite=overwrite)
    return True, f"saved {destination} and {card_path}"


def resolve_candidates(*requested: str) -> list[dict[str, Any]]:
    catalog = list(_load_remote_catalog())
    if not requested:
        return catalog

    requested_set = set(requested)
    selected: list[dict[str, Any]] = []
    for item in catalog:
        if item["file"] in requested_set or item["url"] in requested_set:
            selected.append(item)
    if not selected:
        raise ValueError(f"none of requested models found in catalog: {', '.join(sorted(requested_set))}")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch PCB component detection models")
    parser.add_argument("--model", action="append", help="file name or URL to fetch; repeatable")
    parser.add_argument("--all", action="store_true", help="fetch all catalog remote models")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace any existing file even if checksums do not match",
    )
    args = parser.parse_args()

    if not args.all and not args.model:
        parser.error("use --all or --model to specify at least one model")

    try:
        candidates = resolve_candidates(*args.model) if args.model else list(_load_remote_catalog())
    except ValueError as error:
        print(str(error))
        return 2

    errors = 0
    for candidate in candidates:
        ok, message = fetch_model(candidate, overwrite=args.overwrite)
        print(message)
        if not ok:
            errors += 1

    if errors:
        print(f"fetch completed with {errors} error(s)")
        return 1
    print("fetch completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
