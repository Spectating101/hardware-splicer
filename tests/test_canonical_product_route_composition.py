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
    "/v1/engineering/physical-evidence/envelopes/build",
    "/v1/engineering/physical-evidence/ledger/build-entry",
    "/v1/engineering/physical-evidence/audited-assess",
    "/v1/engineering/physical-evidence/audited-release-assess",
    "/v1/engineering/physical-evidence/apply-save",
    "/v1/engineering/physical-evidence/audited-apply-save",
}


def _path_counts(app) -> dict[str, int]:
    counts: dict[str, int] = {}
    for route in app.routes:
        path = getattr(route, "path", None)
        if path:
            counts[path] = counts.get(path, 0) + 1
    return counts


def test_canonical_product_app_mounts_advanced_engineering_routes_once(tmp_path) -> None:
    app = create_product_app(ProjectStore(tmp_path / "projects"))
    paths = set(app.openapi()["paths"])
    counts = _path_counts(app)

    assert REQUIRED_PATHS <= paths
    assert all(counts[path] == 1 for path in REQUIRED_PATHS)


def test_extended_product_app_is_route_compatible_without_duplicates(tmp_path) -> None:
    canonical = create_product_app(ProjectStore(tmp_path / "canonical"))
    extended = create_extended_product_app(ProjectStore(tmp_path / "extended"))

    assert set(canonical.openapi()["paths"]) == set(extended.openapi()["paths"])
    extended_counts = _path_counts(extended)
    assert all(extended_counts[path] == 1 for path in REQUIRED_PATHS)
