"""Parts intelligence for a retained schematic revision.

Extracts the components the design actually carries. Lifecycle, stock, and
alternates are filled only by a configured provider, with source and as_of.
Authority is never implicitly upgraded: missing fields stay null with status
``not_checked``.
"""

from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from .bom_generator import _PART_HINTS, enrich_bom_with_jlcsearch
from .kicad_diff import KicadDiffError, extract_schematic_symbols
from .pcb.module_registry import _DATA_PATH as _MODULE_DATA_PATH
from .pcb.module_registry import _MODULE_ALIASES, _load_library, find_module
from .plan_to_graph import DATA_FILE as _CATALOG_RECIPES_PATH

SCHEMA_VERSION = "hardware_splicer.parts_intel.v1"
CATALOG_SOURCE = "hardware-splicer-catalog"
LOOKUP_CACHE_TTL_S = 15 * 60
LOOKUP_EXECUTOR_WORKERS = 4
PROVIDER_BREAKER_FAILURES = 3
PROVIDER_BREAKER_COOLDOWN_S = 60.0
LOOKUP_THREAD_PREFIX = "parts-intel-lookup"
# One shared pool. Python cannot kill a running provider thread; max_workers
# bounds concurrency, not the lifetime of a timed-out call.
_LOOKUP_EXECUTOR = ThreadPoolExecutor(
    max_workers=LOOKUP_EXECUTOR_WORKERS,
    thread_name_prefix=LOOKUP_THREAD_PREFIX,
)
_LOOKUP_CACHE: dict[tuple[str, str, str, tuple[tuple[str, str], ...]], tuple[float, dict[str, Any]]] = {}
_PROVIDER_BREAKERS: dict[str, dict[str, float | int]] = {}
_now_fn: Callable[[], float] = time.monotonic

_MPN_PROP_NAMES = frozenset(
    {
        "mpn",
        "manufacturer part number",
        "manufacturer_part_number",
        "mfr part",
    }
)
_MFR_PROP_NAMES = frozenset({"manufacturer", "mfr"})
_LCSC_PROP_NAMES = frozenset({"lcsc", "lcsc part", "jlcpcb part"})
_LIFECYCLE_VALUES = frozenset({"active", "nrnd", "obsolete", "unknown"})


class PartsExtractError(ValueError):
    """Malformed schematic. Message is short on purpose."""


@runtime_checkable
class PartsProvider(Protocol):
    name: str

    def lookup(self, query: Mapping[str, Any], *, timeout_s: float) -> dict[str, Any] | None: ...


def clear_lookup_cache() -> None:
    _LOOKUP_CACHE.clear()
    _PROVIDER_BREAKERS.clear()
    global _now_fn
    _now_fn = time.monotonic


def set_parts_intel_clock(now_fn: Callable[[], float] | None) -> None:
    """Tests inject a clock for breaker cooldown. ``None`` restores monotonic time."""

    global _now_fn
    _now_fn = now_fn or time.monotonic


def _jlc_parts_provider_enabled() -> bool:
    """Network JLC provider is opt-in. Absent/empty/'0' is off; only 1/true/yes enable it."""

    raw = os.environ.get("HARDWARE_SPLICER_JLC_ENRICH")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes"}


def extract_components(schematic_text: str) -> list[dict[str, Any]]:
    """Return placed components. MPN/manufacturer/LCSC come only from properties."""

    try:
        symbols = extract_schematic_symbols(schematic_text)
    except KicadDiffError as exc:
        raise PartsExtractError(str(exc) or "malformed schematic") from exc
    components: list[dict[str, Any]] = []
    for item in symbols:
        props = dict(item.get("properties") or {})
        lib_props = dict(item.get("lib_properties") or {})
        fields = dict(item.get("fields") or {})
        mpn, mpn_name = _named_prop(props, _MPN_PROP_NAMES)
        manufacturer, _mfr_name = _named_prop(props, _MFR_PROP_NAMES)
        lcsc, _lcsc_name = _named_prop(props, _LCSC_PROP_NAMES)
        datasheet = _datasheet_value(props.get("Datasheet") or props.get("datasheet"))
        if datasheet is None:
            datasheet = _datasheet_value(lib_props.get("Datasheet") or lib_props.get("datasheet"))
        footprint = fields.get("footprint")
        if footprint is None:
            footprint = props.get("Footprint")
        if footprint == "":
            footprint = None
        in_bom = fields.get("in_bom")
        on_board = fields.get("on_board")
        components.append(
            {
                "ref": item.get("ref"),
                "uuid": item.get("uuid"),
                "value": fields.get("value") if fields.get("value") is not None else props.get("Value"),
                "lib_id": fields.get("lib_id"),
                "footprint": footprint,
                "datasheet": datasheet,
                "dnp": bool(fields.get("dnp")),
                "in_bom": True if in_bom is None else bool(in_bom),
                "on_board": True if on_board is None else bool(on_board),
                "properties": props,
                "mpn": mpn,
                "manufacturer": manufacturer,
                "lcsc": lcsc,
                "mpn_source": f"property:{mpn_name}" if mpn_name else None,
            }
        )
    return components


def build_bom(components: list[Mapping[str, Any]]) -> dict[str, Any]:
    buckets: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    order: list[tuple[Any, ...]] = []
    for component in components:
        key = (
            component.get("value"),
            component.get("footprint"),
            component.get("mpn"),
            component.get("lcsc"),
            bool(component.get("dnp")),
        )
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(component)
    groups: list[dict[str, Any]] = []
    unique_mpns: set[str] = set()
    missing_mpn_groups = 0
    dnp_components = 0
    excluded_components = 0
    for key in order:
        members = buckets[key]
        value, footprint, mpn, lcsc, dnp = key
        refs = sorted((str(row.get("ref") or "") for row in members), key=_natural_key)
        missing_mpn = mpn is None or str(mpn).strip() == ""
        not_in_bom = all(not row.get("in_bom") for row in members)
        if mpn:
            unique_mpns.add(str(mpn))
        if missing_mpn:
            missing_mpn_groups += 1
        dnp_components += sum(1 for row in members if row.get("dnp"))
        excluded_components += sum(1 for row in members if not row.get("in_bom"))
        manufacturers = [_blank_to_none(row.get("manufacturer")) for row in members]
        manufacturer = manufacturers[0] if manufacturers and all(item == manufacturers[0] for item in manufacturers) else None
        groups.append(
            {
                "value": value,
                "footprint": footprint,
                "mpn": mpn,
                "lcsc": lcsc,
                "manufacturer": manufacturer,
                "dnp": bool(dnp),
                "quantity": len(members),
                "refs": refs,
                "missing_mpn": missing_mpn,
                "not_in_bom": not_in_bom,
            }
        )
    return {
        "groups": groups,
        "summary": {
            "components": len(components),
            "groups": len(groups),
            "unique_mpns": len(unique_mpns),
            "missing_mpn_groups": missing_mpn_groups,
            "dnp_components": dnp_components,
            "excluded_components": excluded_components,
        },
    }


def _provider_set_fingerprint(providers: list[PartsProvider]) -> tuple[tuple[str, str], ...]:
    """Stable ordered identities: class name plus declared source name."""

    return tuple(
        (type(provider).__name__, str(getattr(provider, "name", "") or ""))
        for provider in providers
    )


def enrich_bom(
    groups: list[Mapping[str, Any]],
    providers: list[PartsProvider],
    *,
    timeout_s: float = 5.0,
    max_lookups: int = 50,
) -> list[dict[str, Any]]:
    """Attach availability records. Failures never raise."""

    now = _now()
    _evict_lookup_cache(now)
    lookups_used = 0
    out: list[dict[str, Any]] = []
    for group in groups:
        row = dict(group)
        mpn = _blank_to_none(row.get("mpn"))
        lcsc = _blank_to_none(row.get("lcsc"))
        manufacturer = _blank_to_none(row.get("manufacturer"))
        if mpn is None and lcsc is None:
            row["availability"] = {"status": "not_checked", "records": []}
            out.append(row)
            continue
        cache_key = (mpn or "", lcsc or "", manufacturer or "", _provider_set_fingerprint(providers))
        cached = _LOOKUP_CACHE.get(cache_key)
        if cached is not None and now - cached[0] < LOOKUP_CACHE_TTL_S:
            row["availability"] = dict(cached[1])
            out.append(row)
            continue
        if lookups_used >= max_lookups:
            row["availability"] = {
                "status": "not_checked",
                "records": [],
                "note": "lookup limit reached",
            }
            out.append(row)
            continue
        lookups_used += 1
        availability = _lookup_group(
            providers,
            mpn=mpn,
            lcsc=lcsc,
            manufacturer=manufacturer,
            timeout_s=timeout_s,
        )
        _LOOKUP_CACHE[cache_key] = (_now(), dict(availability))
        row["availability"] = availability
        out.append(row)
    return out


def parts_providers_from_env() -> list[PartsProvider]:
    providers: list[PartsProvider] = [OfflineCatalogProvider()]
    if _jlc_parts_provider_enabled():
        providers.append(JlcEnrichProvider())
    return providers


class OfflineCatalogProvider:
    """Datasheet / family hints from repo catalog data only. Never invents stock."""

    name = CATALOG_SOURCE

    def lookup(self, query: Mapping[str, Any], *, timeout_s: float) -> dict[str, Any] | None:
        del timeout_s
        mpn = _blank_to_none(query.get("mpn"))
        lcsc = _blank_to_none(query.get("lcsc"))
        manufacturer = _blank_to_none(query.get("manufacturer"))
        if mpn is None and lcsc is None:
            return None
        spec = _catalog_match(mpn=mpn, lcsc=lcsc, manufacturer=manufacturer)
        if spec is None:
            return None
        as_of = _catalog_as_of()
        if as_of is None:
            return None
        datasheet = _datasheet_value(spec.get("datasheetUrl") or spec.get("datasheet_url"))
        package = _blank_to_none(spec.get("package") or spec.get("footprint"))
        if package is None:
            hints = _PART_HINTS.get(str(spec.get("id") or "")) or {}
            package = _blank_to_none(hints.get("footprint"))
        alternates = _catalog_alternates(spec)
        if datasheet is None and not alternates and package is None:
            return None
        return {
            "source": CATALOG_SOURCE,
            "as_of": as_of,
            "lifecycle": None,
            "stock": None,
            "price_breaks": None,
            "datasheet_url": datasheet,
            "alternates": alternates,
            "package": package,
        }


class JlcEnrichProvider:
    """Adapts ``enrich_bom_with_jlcsearch``; maps only fields that function returns."""

    name = "jlcsearch"

    def lookup(self, query: Mapping[str, Any], *, timeout_s: float) -> dict[str, Any] | None:
        if not _jlc_parts_provider_enabled():
            return None
        try:
            from .integrations.jlcsearch_client import JlcSearchClient

            line = {
                "ref": "P1",
                "module_id": str(query.get("mpn") or query.get("lcsc") or ""),
                "mpn": str(query.get("mpn") or ""),
                "footprint": "",
                "supplier_sku": str(query.get("lcsc") or ""),
            }
            client = JlcSearchClient(timeout_s=float(timeout_s))
            bom = enrich_bom_with_jlcsearch({"lines": [line]}, client=client)
        except Exception:
            return None
        if not bom.get("jlc_enriched"):
            return None
        rows = list(bom.get("lines") or [])
        if not rows:
            return None
        if not _jlc_line_has_part_data(rows[0]):
            return None
        return _record_from_jlc_line(rows[0])


def _catalog_as_of() -> str | None:
    """UTC ISO mtime of the catalog JSON files. Never substitutes wall-clock now."""

    mtimes: list[float] = []
    for path in (_MODULE_DATA_PATH, _CATALOG_RECIPES_PATH):
        try:
            mtimes.append(Path(path).stat().st_mtime)
        except OSError:
            continue
    if not mtimes:
        return None
    return datetime.fromtimestamp(max(mtimes), tz=timezone.utc).isoformat()


def _catalog_identity_mpns(spec: Mapping[str, Any]) -> set[str]:
    module_id = str(spec.get("id") or "")
    values = [
        spec.get("partNumber"),
        spec.get("mpn"),
        (_PART_HINTS.get(module_id) or {}).get("mpn"),
    ]
    return {str(value).casefold() for value in values if _blank_to_none(value)}


def _catalog_identity_lcscs(spec: Mapping[str, Any]) -> set[str]:
    values = [spec.get("lcsc"), spec.get("jlc_lcsc"), spec.get("lcscPart")]
    return {str(value).casefold() for value in values if _blank_to_none(value)}


def _catalog_identity_matches(spec: Mapping[str, Any], *, mpn: str | None, lcsc: str | None) -> bool:
    mpn_needle = (mpn or "").casefold()
    lcsc_needle = (lcsc or "").casefold()
    if mpn_needle and mpn_needle in _catalog_identity_mpns(spec):
        return True
    if lcsc_needle and lcsc_needle in _catalog_identity_lcscs(spec):
        return True
    return False


def _catalog_manufacturer_confirms(spec: Mapping[str, Any], manufacturer: str | None) -> bool:
    spec_mfr = _blank_to_none(spec.get("manufacturer"))
    query_mfr = _blank_to_none(manufacturer)
    if spec_mfr is None:
        return query_mfr is None
    if query_mfr is None:
        return True
    return spec_mfr.casefold() == query_mfr.casefold()


def _catalog_match(
    *,
    mpn: str | None,
    manufacturer: str | None,
    lcsc: str | None = None,
) -> dict[str, Any] | None:
    """Match only on MPN or LCSC. Manufacturer never identifies a part by itself."""

    if _blank_to_none(mpn) is None and _blank_to_none(lcsc) is None:
        return None
    library = _load_library()
    for spec in library.values():
        if not isinstance(spec, Mapping):
            continue
        if not _catalog_identity_matches(spec, mpn=mpn, lcsc=lcsc):
            continue
        if not _catalog_manufacturer_confirms(spec, manufacturer):
            continue
        return dict(spec)
    needle = (mpn or "").casefold()
    if not needle:
        return None
    for module_id, hints in _PART_HINTS.items():
        if str(hints.get("mpn") or "").casefold() != needle:
            continue
        spec = dict(find_module(module_id) or {"id": module_id})
        if not _catalog_manufacturer_confirms(spec, manufacturer):
            continue
        return spec
    return None


def _catalog_alternates(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    stated = spec.get("alternates") or spec.get("alternate_mpns") or spec.get("family_alternates")
    alternates: list[dict[str, Any]] = []
    if isinstance(stated, list):
        for item in stated:
            if isinstance(item, Mapping) and item.get("mpn"):
                alternates.append(
                    {
                        "mpn": str(item["mpn"]),
                        "manufacturer": _blank_to_none(item.get("manufacturer")),
                        "reason": str(item.get("reason") or "catalog alternate"),
                    }
                )
            elif isinstance(item, str) and item.strip():
                alternates.append({"mpn": item.strip(), "manufacturer": None, "reason": "catalog alternate"})
    family = _blank_to_none(spec.get("family"))
    if family:
        for other in _load_library().values():
            if not isinstance(other, Mapping):
                continue
            if str(other.get("id") or "") == str(spec.get("id") or ""):
                continue
            if _blank_to_none(other.get("family")) != family:
                continue
            other_mpn = _blank_to_none(other.get("partNumber") or other.get("mpn"))
            if other_mpn is None:
                other_mpn = _blank_to_none((_PART_HINTS.get(str(other.get("id") or "")) or {}).get("mpn"))
            if other_mpn is None:
                continue
            alternates.append(
                {
                    "mpn": other_mpn,
                    "manufacturer": _blank_to_none(other.get("manufacturer")),
                    "reason": "same catalog family",
                }
            )
    spec_id = str(spec.get("id") or "")
    for alias, target in _MODULE_ALIASES.items():
        if spec_id not in {alias, target}:
            continue
        other_id = target if spec_id == alias else alias
        other = find_module(other_id) or {}
        other_mpn = _blank_to_none(other.get("partNumber") or other.get("mpn"))
        if other_mpn is None:
            other_mpn = _blank_to_none((_PART_HINTS.get(other_id) or {}).get("mpn"))
        if other_mpn is None:
            continue
        alternates.append(
            {
                "mpn": other_mpn,
                "manufacturer": _blank_to_none(other.get("manufacturer")),
                "reason": "catalog alias",
            }
        )
    return alternates


def _jlc_line_has_part_data(line: Mapping[str, Any]) -> bool:
    if line.get("lifecycle") in _LIFECYCLE_VALUES:
        return True
    stock = line.get("stock")
    if stock is not None and str(stock).strip() != "":
        return True
    if line.get("price_breaks") or line.get("price") is not None:
        return True
    if _datasheet_value(line.get("datasheet_url") or line.get("datasheet")):
        return True
    alternates = line.get("alternates")
    if isinstance(alternates, list) and alternates:
        return True
    if _blank_to_none(line.get("package") or line.get("jlc_cpl_footprint")):
        return True
    if _blank_to_none(line.get("lcsc") or line.get("jlc_lcsc")):
        return True
    if _blank_to_none(line.get("jlc_mpn") or line.get("mpn_returned")):
        return True
    return False


def _record_from_jlc_line(line: Mapping[str, Any]) -> dict[str, Any]:
    lifecycle = line.get("lifecycle")
    if lifecycle not in _LIFECYCLE_VALUES:
        lifecycle = None
    stock = line.get("stock")
    try:
        stock_i = int(stock) if stock is not None else None
    except (TypeError, ValueError):
        stock_i = None
    datasheet = _datasheet_value(line.get("datasheet_url") or line.get("datasheet"))
    package = _blank_to_none(line.get("package") or line.get("jlc_cpl_footprint"))
    raw_breaks = line.get("price_breaks")
    price_breaks = raw_breaks if isinstance(raw_breaks, list) else None
    raw_alts = line.get("alternates")
    alternates: list[dict[str, Any]] = []
    if isinstance(raw_alts, list):
        for item in raw_alts:
            if isinstance(item, Mapping) and item.get("mpn"):
                alternates.append(
                    {
                        "mpn": str(item["mpn"]),
                        "manufacturer": _blank_to_none(item.get("manufacturer")),
                        "reason": str(item.get("reason") or ""),
                    }
                )
    return {
        "source": "jlcsearch",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "lifecycle": lifecycle,
        "stock": stock_i,
        "price_breaks": price_breaks,
        "datasheet_url": datasheet,
        "alternates": alternates,
        "package": package,
        "lcsc": _blank_to_none(line.get("lcsc") or line.get("jlc_lcsc")),
        "mpn_returned": _blank_to_none(line.get("jlc_mpn") or line.get("mpn_returned")),
    }


def _lookup_group(
    providers: list[PartsProvider],
    *,
    mpn: str | None,
    lcsc: str | None,
    manufacturer: str | None,
    timeout_s: float,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if mpn:
        query["mpn"] = mpn
    if lcsc:
        query["lcsc"] = lcsc
    if manufacturer:
        query["manufacturer"] = manufacturer
    records: list[dict[str, Any]] = []
    failure_reason: str | None = None
    provenance_failed = False
    for provider in providers:
        name = str(getattr(provider, "name", "provider"))
        skip_reason = _breaker_skip_reason(name)
        if skip_reason:
            failure_reason = failure_reason or skip_reason
            continue
        try:
            record = _invoke_lookup(provider, query, timeout_s)
        except Exception as exc:
            _breaker_note_failure(name)
            failure_reason = failure_reason or _safe_reason(exc)
            continue
        _breaker_note_success(name)
        if record is None:
            continue
        if not isinstance(record, Mapping):
            continue
        public = _public_record(record)
        if public is None:
            provenance_failed = True
            continue
        records.append(public)
    if records:
        return {"status": "checked", "records": records}
    if failure_reason:
        return {"status": "lookup_failed", "records": [], "reason": failure_reason}
    if provenance_failed:
        return {
            "status": "lookup_failed",
            "records": [],
            "note": "provider returned a record without source and date",
        }
    return {"status": "no_data", "records": []}


def _invoke_lookup(
    provider: PartsProvider,
    query: Mapping[str, Any],
    timeout_s: float,
) -> dict[str, Any] | None:
    future = _LOOKUP_EXECUTOR.submit(provider.lookup, dict(query), timeout_s=timeout_s)
    try:
        return future.result(timeout=timeout_s)
    except FuturesTimeout as exc:
        future.cancel()
        raise TimeoutError("timeout") from exc


def _parseable_iso8601(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return text


def _public_record(record: Mapping[str, Any]) -> dict[str, Any] | None:
    source = record.get("source")
    if not isinstance(source, str) or not source.strip():
        return None
    as_of = _parseable_iso8601(record.get("as_of"))
    if as_of is None:
        return None
    lifecycle = record.get("lifecycle")
    if lifecycle not in _LIFECYCLE_VALUES:
        lifecycle = None
    stock = record.get("stock")
    try:
        stock_i = int(stock) if stock is not None else None
    except (TypeError, ValueError):
        stock_i = None
    public = {
        "source": source.strip(),
        "as_of": as_of,
        "lifecycle": lifecycle,
        "stock": stock_i,
        "price_breaks": record.get("price_breaks") if isinstance(record.get("price_breaks"), list) else None,
        "datasheet_url": _datasheet_value(record.get("datasheet_url")),
        "alternates": list(record.get("alternates") or []) if isinstance(record.get("alternates"), list) else [],
        "package": _blank_to_none(record.get("package")),
    }
    lcsc = _blank_to_none(record.get("lcsc"))
    mpn_returned = _blank_to_none(record.get("mpn_returned"))
    if lcsc:
        public["lcsc"] = lcsc
    if mpn_returned:
        public["mpn_returned"] = mpn_returned
    return public


def _named_prop(props: Mapping[str, Any], names: frozenset[str]) -> tuple[str | None, str | None]:
    wanted = {_norm_prop_name(name) for name in names}
    for key, value in props.items():
        if _norm_prop_name(str(key)) not in wanted:
            continue
        text = str(value).strip() if value is not None else ""
        if text and text != "~":
            return text, str(key)
    return None, None


def _norm_prop_name(name: str) -> str:
    return " ".join(name.replace("_", " ").casefold().split())


def _datasheet_value(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text or text == "~":
        return None
    lower = text.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return text
    if "://" in text:
        return None
    if "." in Path(text).name:
        return text
    return None


def _natural_key(text: str) -> tuple[Any, ...]:
    parts = re.split(r"(\d+)", text or "")
    key: list[tuple[int, Any]] = []
    for part in parts:
        if part.isdigit():
            key.append((1, int(part)))
        else:
            key.append((0, part.casefold()))
    return tuple(key)


def _blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_reason(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError):
        return "timeout"
    text = str(exc).strip() or exc.__class__.__name__
    if "/" in text or "\\" in text:
        return exc.__class__.__name__
    return text[:160]


def _now() -> float:
    return _now_fn()


def _breaker_state(name: str) -> dict[str, float | int]:
    state = _PROVIDER_BREAKERS.get(name)
    if state is None:
        state = {"consecutive_failures": 0, "skipped_until": 0.0}
        _PROVIDER_BREAKERS[name] = state
    return state


def _breaker_skip_reason(name: str) -> str | None:
    state = _breaker_state(name)
    if float(state["skipped_until"]) > _now():
        return "provider temporarily skipped after repeated failures"
    return None


def _breaker_note_failure(name: str) -> None:
    state = _breaker_state(name)
    failures = int(state["consecutive_failures"]) + 1
    state["consecutive_failures"] = failures
    if failures >= PROVIDER_BREAKER_FAILURES:
        state["skipped_until"] = _now() + PROVIDER_BREAKER_COOLDOWN_S


def _breaker_note_success(name: str) -> None:
    state = _breaker_state(name)
    state["consecutive_failures"] = 0
    state["skipped_until"] = 0.0


def _evict_lookup_cache(now: float) -> None:
    expired = [key for key, (stamp, _payload) in _LOOKUP_CACHE.items() if now - stamp >= LOOKUP_CACHE_TTL_S]
    for key in expired:
        _LOOKUP_CACHE.pop(key, None)
