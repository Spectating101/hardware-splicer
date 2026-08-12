from __future__ import annotations

from hardware_splicer.extended_product_api import create_extended_product_app
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


REQUIRED_PATHS = {
    "/v1/engineering/actions/prepare",
    "/v1/engineering/execution/capabilities",
    "/v1/engineering/mechanical/schema",
    "/v1/engineering/mechanical/geometry/apply",
    "/v1/engineering/mechanical/fit/check",
    "/v1/engineering/mechanical/fit/apply",
    "/v1/engineering/physical-evidence/schema",
    "/v1/engineering/physical-evidence/assess",
    "/v1/engineering/physical-evidence/attach",
    "/v1/engineering/physical-evidence/release-assess",
    "/v1/engineering/physical-evidence/raw-files/schema",
    "/v1/engineering/physical-evidence/raw-files/hash",
    "/v1/engineering/physical-evidence/raw-files/hash-attested",
    "/v1/engineering/physical-evidence/envelopes/build",
    "/v1/engineering/physical-evidence/envelopes/build-attested",
    "/v1/engineering/physical-evidence/ledger/build-entry",
    "/v1/engineering/physical-evidence/audited-assess",
    "/v1/engineering/physical-evidence/audited-release-assess",
    "/v1/engineering/physical-evidence/attested/schema",
    "/v1/engineering/physical-evidence/attested-audited-assess",
    "/v1/engineering/physical-evidence/attested-audited-release-assess",
    "/v1/engineering/physical-evidence/apply-save",
    "/v1/engineering/physical-evidence/audited-apply-save",
    "/v1/engineering/physical-evidence/attested-audited-apply-save",
}


def _api_operation_counts(app) -> dict[tuple[str, str], int]:
    """Count concrete FastAPI route registrations without recursing into internals.

    FastAPI's OpenAPI builder is the source of truth for path presence. This helper
    separately verifies that no HTTP method/path pair was registered more than once.
    APIRouter.include_router() flattens API routes onto app.routes, so recursive
    traversal can double-prefix or otherwise misread Starlette implementation detail.
    """

    counts: dict[tuple[str, str], int] = {}
    for route in app.routes:
        path = getattr(route, "path_format", None) or getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        for raw_method in methods:
            method = str(raw_method).upper()
            if method in {"HEAD", "OPTIONS"}:
                continue
            key = (str(path), method)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _duplicate_required_operations(app) -> dict[str, dict[str, int]]:
    counts = _api_operation_counts(app)
    duplicates: dict[str, dict[str, int]] = {}
    for path in sorted(REQUIRED_PATHS):
        repeated = {
            method: count
            for (registered_path, method), count in counts.items()
            if registered_path == path and count > 1
        }
        if repeated:
            duplicates[path] = repeated
    return duplicates


def test_canonical_product_app_mounts_advanced_engineering_routes_once(tmp_path) -> None:
    app = create_product_app(ProjectStore(tmp_path / "projects"))
    paths = set(app.openapi()["paths"])

    assert REQUIRED_PATHS <= paths
    assert _duplicate_required_operations(app) == {}


def test_extended_product_app_is_route_compatible_without_duplicates(tmp_path) -> None:
    canonical = create_product_app(ProjectStore(tmp_path / "canonical"))
    extended = create_extended_product_app(ProjectStore(tmp_path / "extended"))

    assert set(canonical.openapi()["paths"]) == set(extended.openapi()["paths"])
    assert _duplicate_required_operations(extended) == {}
