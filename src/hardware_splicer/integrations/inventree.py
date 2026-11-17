"""Read-only InvenTree REST integration; no stock allocations or supplier orders."""
from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal
import hashlib
import ipaddress
import json
import math
import os
import time as clock
from urllib.parse import urlsplit

import httpx

from ..project_materials import InventoryCapture, InventoryLot, MaterialRequirement, SupplierReference

UPSTREAM = "https://github.com/inventree/InvenTree/tree/8f8502d0d9e0cebb726430746e39327c51845a8a"


class InvenTreeError(RuntimeError):
    pass


def _pk(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("InvenTree identifiers must be positive integers")
    return value


def _quantity(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("InvenTree quantity is missing or invalid")
    number = Decimal(str(value))
    if not number.is_finite() or number < 0 or number > 1_000_000:
        raise ValueError("InvenTree quantity exceeds supported bounds")
    return number


def _text(value):
    return value if isinstance(value, str) else ""


class InvenTreeClient:
    def __init__(self, base_url: str, token: str, *, transport=None, timeout_s=5.0, budget_s=60.0):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or "%" in parsed.path or ".." in parsed.path.split("/")):
            raise ValueError("InvenTree URL must be an HTTP URL without credentials, query or fragment")
        if parsed.scheme == "http":
            try:
                local = ipaddress.ip_address(parsed.hostname).is_loopback
            except ValueError:
                local = parsed.hostname == "localhost"
            if not local:
                raise ValueError("Use HTTPS for a remote InvenTree server")
        if not isinstance(token, str) or not token.strip() or "\n" in token or "\r" in token:
            raise ValueError("An InvenTree read-only access token is required")
        self.base_url = base_url.rstrip("/")
        if self.base_url.endswith("/api"):
            self.base_url = self.base_url[:-4]
        self._token = token
        self._transport = transport
        self._timeout = min(float(timeout_s), 15.0)
        self._budget = min(float(budget_s), 120.0)
        if not math.isfinite(self._timeout) or not math.isfinite(self._budget) or self._timeout <= 0 or self._budget <= 0:
            raise ValueError("InvenTree timeouts must be positive")

    @classmethod
    def from_env(cls):
        url = os.getenv("HARDWARE_SPLICER_INVENTREE_URL", "")
        token = os.getenv("HARDWARE_SPLICER_INVENTREE_TOKEN", "")
        if not url or not token:
            raise InvenTreeError("Configure HARDWARE_SPLICER_INVENTREE_URL and HARDWARE_SPLICER_INVENTREE_TOKEN")
        return cls(url, token)

    def read_assembly(self, assembly_part_id: int, *, build_quantity: int = 1) -> tuple[list[MaterialRequirement], InventoryCapture]:
        _pk(assembly_part_id)
        if isinstance(build_quantity, bool) or not isinstance(build_quantity, int) or not 1 <= build_quantity <= 100:
            raise ValueError("build_quantity must be between 1 and 100")
        deadline, hashes = clock.monotonic() + self._budget, {}
        calls = 0
        with httpx.Client(transport=self._transport, follow_redirects=False, trust_env=False) as client:
            def get(path, params=None):
                nonlocal calls
                calls += 1
                remaining = deadline - clock.monotonic()
                if calls > 256 or remaining <= 0:
                    raise InvenTreeError("InvenTree import exceeded its request/time budget")
                try:
                    with client.stream("GET", self.base_url + "/api/" + path,
                                       params=params, headers={"Authorization": "Token " + self._token, "Accept": "application/json"},
                                       timeout=min(self._timeout, remaining)) as response:
                        if response.status_code != 200:
                            raise InvenTreeError(f"InvenTree GET {path} failed (HTTP {response.status_code})")
                        content = bytearray()
                        for chunk in response.iter_bytes():
                            content.extend(chunk)
                            if len(content) > 2_000_000 or clock.monotonic() > deadline:
                                raise InvenTreeError("InvenTree response exceeded its size/time budget")
                        data = json.loads(content)
                        key = path + ("?" + str(httpx.QueryParams(params)) if params else "")
                        hashes[key] = hashlib.sha256(content).hexdigest()
                        return data
                except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError):
                    raise InvenTreeError(f"InvenTree GET {path} could not return valid JSON") from None

            def rows(path, params):
                collected, seen, expected = [], set(), None
                for _ in range(20):
                    page = get(path, {**params, "limit": 100, "offset": len(collected)})
                    if isinstance(page, list):
                        if collected:
                            raise InvenTreeError("InvenTree pagination changed response shape")
                        items, total, more = page, len(page), False
                    elif isinstance(page, dict):
                        items, total, more = page.get("results"), page.get("count"), page.get("next") is not None
                        if isinstance(total, bool) or not isinstance(total, int) or not 0 <= total <= 2000:
                            raise InvenTreeError("InvenTree result count is invalid or too large")
                    else:
                        raise InvenTreeError("InvenTree list response is invalid")
                    if not isinstance(items, list) or len(collected) + len(items) > 2000:
                        raise InvenTreeError("InvenTree result page is invalid or too large")
                    if expected is not None and total != expected:
                        raise InvenTreeError("InvenTree inventory changed during pagination; retry the capture")
                    expected = total
                    for item in items:
                        if not isinstance(item, dict):
                            raise InvenTreeError("InvenTree result row is invalid")
                        identity = _pk(item.get("pk"))
                        if identity in seen:
                            raise InvenTreeError("InvenTree repeated an item during pagination")
                        seen.add(identity)
                        collected.append(item)
                    if len(collected) == total and not more:
                        return collected
                    if not items or not more or len(collected) >= total:
                        raise InvenTreeError("InvenTree returned incomplete pagination")
                    # Build the next fixed-origin request ourselves; never follow
                    # a server-provided next URL with the authentication header.
                raise InvenTreeError("InvenTree pagination exceeded its limit")

            assembly = get(f"part/{assembly_part_id}/")
            if not isinstance(assembly, dict) or assembly.get("pk") != assembly_part_id:
                raise InvenTreeError("InvenTree assembly identity differs from request")
            bom = rows("bom/", {"part": assembly_part_id, "inherited": "false"})
            if not bom or len(bom) > 500:
                raise InvenTreeError("Expected 1–500 direct BOM lines")
            part_ids = {_pk(row.get("sub_part")) for row in bom}
            if len(part_ids) > 50:
                raise InvenTreeError("An import supports at most 50 distinct direct BOM parts")
            parts, identities, lots, suppliers = {}, {}, [], []
            for part_id in sorted(part_ids):
                part = get(f"part/{part_id}/")
                if not isinstance(part, dict) or part.get("pk") != part_id:
                    raise InvenTreeError("InvenTree part identity differs from request")
                parts[part_id] = part
                manufacturers = rows("company/part/manufacturer/", {"part": part_id, "manufacturer_detail": "true"})
                pairs = set()
                for item in manufacturers:
                    if item.get("part") != part_id:
                        raise InvenTreeError("InvenTree returned a manufacturer part from another part")
                    detail = item.get("manufacturer_detail") or {}
                    if not isinstance(detail, dict):
                        raise InvenTreeError("Invalid InvenTree manufacturer detail")
                    pair = (_text(detail.get("name")).strip(), _text(item.get("MPN")).strip())
                    if all(pair):
                        pairs.add(pair)
                identities[part_id] = next(iter(pairs)) if len(pairs) == 1 else ("", "")
                unit = _text(part.get("units")).strip() or "ea"
                for stock in rows("stock/", {"part": part_id, "in_stock": "true"}):
                    if stock.get("part") != part_id:
                        raise InvenTreeError("InvenTree returned stock from another part")
                    condition = {10: "ok", 50: "unchecked", 55: "damaged", 85: "unchecked"}.get(stock.get("status"), "unavailable")
                    # Current InvenTree emits the built-in numeric status as
                    # status_custom_key too; only a distinct key is custom.
                    custom_status = stock.get("status_custom_key") not in (None, "", stock.get("status"))
                    if (custom_status or stock.get("is_building") is True
                            or stock.get("in_stock") is False or stock.get("belongs_to") is not None
                            or stock.get("sales_order") is not None or stock.get("allocated") is None):
                        condition = "unchecked"
                    expires = stock.get("expiry_date")
                    expiry = datetime.combine(datetime.fromisoformat(expires).date(), time.min, timezone.utc) if expires else None
                    mfr, mpn = identities[part_id]
                    lots.append(InventoryLot(stock_id=str(stock["pk"]), catalog_part_id=part_id,
                                             quantity=_quantity(stock.get("quantity")), allocated=_quantity(stock["allocated"]) if stock.get("allocated") is not None else Decimal(0),
                                             manufacturer=mfr, mpn=mpn, unit=unit, condition=condition,
                                             expires_at=expiry, source_ref=self.base_url + f"/api/stock/{stock['pk']}/"))
                for offer in rows("company/part/", {"part": part_id, "supplier_detail": "true"}):
                    if offer.get("part") != part_id:
                        raise InvenTreeError("InvenTree returned a supplier record from another part")
                    detail = offer.get("supplier_detail") or {}
                    if not isinstance(detail, dict):
                        raise InvenTreeError("Invalid InvenTree supplier detail")
                    suppliers.append(SupplierReference(catalog_part_id=part_id, supplier=_text(detail.get("name")),
                                                       sku=_text(offer.get("SKU")), url=_text(offer.get("link")),
                                                       reported_available=_quantity(offer["available"]) if offer.get("available") is not None else None))
            requirements = []
            for row in bom:
                if row.get("part") != assembly_part_id:
                    raise InvenTreeError("InvenTree BOM line belongs to another assembly")
                part_id = row["sub_part"]
                part, unresolved = parts[part_id], []
                if part.get("assembly"):
                    unresolved.append("nested_assembly_not_expanded")
                if part.get("virtual"):
                    unresolved.append("virtual_part_has_no_physical_identity")
                if part.get("active") is not True:
                    unresolved.append("part_active_status_not_confirmed")
                if row.get("optional") or row.get("consumable"):
                    unresolved.append("conditional_bom_line_requires_review")
                for field in ("setup_quantity", "attrition", "rounding_multiple"):
                    if row.get(field) not in (None, "", 0, "0", "0.00000", "0.000000"):
                        unresolved.append("bom_quantity_adjustment_requires_review:" + field)
                manufacturer, mpn = identities[part_id]
                requirements.append(MaterialRequirement(
                    material_id="bom-" + str(row["pk"]), description=part.get("name") or str(part_id),
                    quantity=_quantity(row.get("quantity")) * build_quantity,
                    unit=_text(part.get("units")).strip() or "ea", catalog_part_id=part_id,
                    manufacturer=manufacturer, mpn=mpn, unresolved=unresolved,
                    acquisition="make" if part.get("assembly") else "buy",
                    source_ref=self.base_url + f"/api/bom/{row['pk']}/"))
        capture = InventoryCapture(source="inventree", source_url=self.base_url,
                                   captured_at=datetime.now(timezone.utc), lots=lots,
                                   suppliers=suppliers, response_sha256=hashes)
        return requirements, capture
