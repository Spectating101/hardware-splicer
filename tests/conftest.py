"""Shared pytest configuration."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from datetime import datetime, timezone, tzinfo

import pytest

# Optional ``cad`` extra. Tests marked ``requires_cadquery`` / ``requires_trimesh``
# are skipped, with a reason, when the package cannot be found.
_OPTIONAL_CAD_MODULES = {
    "requires_cadquery": "cadquery",
    "requires_trimesh": "trimesh",
}


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def pytest_configure(config: pytest.Config) -> None:
    for marker, module in _OPTIONAL_CAD_MODULES.items():
        config.addinivalue_line(
            "markers",
            f"{marker}: skipped when the optional '{module}' package (cad extra) is not installed",
        )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    missing = {
        marker: module
        for marker, module in _OPTIONAL_CAD_MODULES.items()
        if not _module_available(module)
    }
    for item in items:
        for marker, module in missing.items():
            if item.get_closest_marker(marker) is not None:
                item.add_marker(
                    pytest.mark.skip(
                        reason=f"requires optional '{module}' package (install the cad extra)"
                    )
                )


@pytest.fixture(autouse=True)
def _fast_compile_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests fast; integration tests opt in to autoroute."""
    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "0")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_PHRASE_EXPAND", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_BUILD_PICK", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_MODULE_PICK", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_COMPOSE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_LLM_FIRST", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_WORKSHOP", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_SALVAGE_RESOLVE", "heuristic")
    monkeypatch.setattr(
        "hardware_splicer.integrations.qwen_text_client.qwen_configured",
        lambda: False,
    )


@pytest.fixture
def authorization_clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[datetime], None]:
    """Control the audited assessor's clock, without replacing any validation logic.

    Opt-in only: unrelated tests and the process clock stay untouched. The audited
    assessor forwards one instant to the real ledger and physical-evidence checks,
    including fresh status/action revalidation. Test teardown restores the clock.
    """
    from hardware_splicer import audited_physical_evidence

    def set_time(value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("authorization test clock requires a timezone-aware datetime")
        instant = value.astimezone(timezone.utc)

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz: tzinfo | None = None) -> datetime:
                if tz is None:
                    return instant.astimezone().replace(tzinfo=None)
                return instant.astimezone(tz)

        monkeypatch.setattr(audited_physical_evidence, "datetime", FixedDateTime)

    # After the fixture's evidence capture/review, before its September expiry.
    set_time(datetime(2026, 8, 4, 3, tzinfo=timezone.utc))
    return set_time


@pytest.fixture
def assume_clean_kicad_erc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate a test from the real KiCad ERC outcome on the emitted schematic.

    KiCad ERC failures veto build_ready (see test_kicad_erc_trust_gate.py). Every catalog build
    passes real ERC (test_catalog_erc_clean.py), so only tests that compile non-catalog designs
    that still report real ERC errors use this fixture, to state that assumption explicitly: the
    scratch relay/MOSFET/level-shifter compose (open load terminals and an ESP32 RX pin auto-wired
    as a driver), the synthesized 5V-control bridge (open MOSFET load terminals) and the TP4056
    battery-power lowering (open charger/battery terminals), and the two Enabot donor-drive
    intakes (a customised rover netlist that is no longer the robot_drive_base recipe, so its
    open L298N terminals and 5V pin are real findings). Those designs have no recipe to declare
    their load terminals, so recipe-specific no-connects correctly do not apply to them.
    """
    monkeypatch.setattr(
        "hardware_splicer.netlist.compile.run_kicad_cli_erc",
        lambda *a, **k: {"pass": True, "skipped": False, "errors": 0, "warnings": 0, "violations": [], "report_path": None},
    )
