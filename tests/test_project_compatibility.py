from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_compatibility import (
    CompatibleProjectStore,
    LEGACY_UNVERSIONED_SCHEMA,
    UnsupportedProjectSchema,
    migrate_project_envelope,
)
from hardware_splicer.project_store import PROJECT_STORE_SCHEMA, ProjectStore

FIXTURE = Path(__file__).parent / "fixtures" / "project_snapshot_unversioned.json"


def _write_legacy_project(root: Path) -> None:
    project_dir = root / "legacy-demo"
    revisions = project_dir / "revisions"
    revisions.mkdir(parents=True)
    (revisions / "00000001.json").write_text(
        FIXTURE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (project_dir / "project.json").write_text(
        json.dumps(
            {
                "schema_version": PROJECT_STORE_SCHEMA,
                "project_id": "legacy-demo",
                "latest_revision": 1,
                "archived": False,
                "created_at": "2026-07-20T00:00:00+00:00",
                "saved_at": "2026-07-20T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )


def test_current_envelope_passes_without_data_loss() -> None:
    envelope = {
        "schema_version": PROJECT_STORE_SCHEMA,
        "project_id": "current-demo",
        "revision": 1,
        "saved_at": "2026-08-03T00:00:00+00:00",
        "snapshot": {"unknown_payload": {"keep": True}},
        "metadata": {"unknown_metadata": [1, 2, 3]},
        "unknown_envelope_field": "keep",
    }

    migrated = migrate_project_envelope(envelope)

    assert migrated == envelope
    assert migrated is not envelope


def test_unversioned_envelope_migrates_deterministically_and_preserves_unknown_fields(
    tmp_path: Path,
) -> None:
    _write_legacy_project(tmp_path)
    store = CompatibleProjectStore(tmp_path)

    loaded = store.load_latest_with_recovery("legacy-demo")

    assert loaded["schema_version"] == PROJECT_STORE_SCHEMA
    assert loaded["unknown_envelope_field"] == {"must_survive": True}
    assert loaded["snapshot"]["discipline_payloads"]["unknown_future_payload"] == {
        "must_survive": True,
        "nested": {"value": 7},
    }
    assert loaded["metadata"]["origin"] == "compatibility_fixture"
    assert loaded["metadata"]["unknown_metadata"] == {"must_survive": True}
    assert loaded["metadata"]["project_store_migration"] == {
        "source_schema": LEGACY_UNVERSIONED_SCHEMA,
        "target_schema": PROJECT_STORE_SCHEMA,
    }
    assert loaded["recovery"]["used"] is False

    assert migrate_project_envelope(loaded) == loaded


def test_unknown_named_schema_fails_closed() -> None:
    with pytest.raises(UnsupportedProjectSchema, match="project_snapshot.v2"):
        migrate_project_envelope(
            {
                "schema_version": "hardware_splicer.project_snapshot.v2",
                "project_id": "future-demo",
                "revision": 1,
                "snapshot": {},
            }
        )


def test_product_app_defaults_to_compatible_store_and_preserves_injected_store(
    tmp_path: Path,
) -> None:
    default_app = create_product_app()
    assert isinstance(default_app.state.project_store, CompatibleProjectStore)

    injected = ProjectStore(tmp_path)
    custom_app = create_product_app(injected)
    assert custom_app.state.project_store is injected
