"""The front door's claim boundary must match the canonical claims JSON."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "docs" / "product" / "claims-and-nonclaims.v1.json"
FRONTEND = ROOT / "apps" / "circuit-ai" / "circuit-ai-frontend" / "lib" / "claim-boundary.ts"


def _strings(boundary: dict) -> list[str]:
    values = [boundary["authority"]["commit"], boundary["authority"]["package_sha256"], boundary["authority"]["physical_state"]]
    for item in boundary["supported"]:
        values += [item["claim"], item["evidence"]]
    values += boundary["unsupported_or_prohibited"]
    for needs in boundary["promotion_requirements"].values():
        values += needs
    return values


def test_frontend_claim_boundary_matches_canonical_json() -> None:
    boundary = json.loads(CLAIMS.read_text(encoding="utf-8"))
    source = FRONTEND.read_text(encoding="utf-8")
    missing = [value for value in _strings(boundary) if value not in source]
    assert not missing, f"claim-boundary.ts drifted from claims-and-nonclaims.v1.json: {missing}"
    assert f"asOf: '{boundary['as_of']}'" in source


def test_frontend_claim_boundary_has_no_extra_supported_claims() -> None:
    """A claim added only in the UI would be an unreviewed upgrade."""
    boundary = json.loads(CLAIMS.read_text(encoding="utf-8"))
    source = FRONTEND.read_text(encoding="utf-8")
    assert source.count("claim: '") == len(boundary["supported"])
