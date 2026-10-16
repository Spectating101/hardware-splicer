"""Immutable supplier quote snapshots and bounded BOM costing.

Procurement data influences architecture decisions but does not establish that a
part will actually be available at purchase time. Quotes are retained as
supplier/source claims with currency, quantity, stock and lead-time context.
This module has no checkout/order/payment capability.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from .fabrication_operator import FabricationValidationError


@dataclass(frozen=True)
class ProcurementQuote:
    quote_id: str
    supplier_id: str
    part_key: str
    manufacturer_part_number: str | None
    currency: str
    unit_price: str
    minimum_order_quantity: int
    stock_quantity: int | None
    lead_time_days: int | None
    observed_at: str
    valid_until: str | None
    source_ref: str
    metadata: Mapping[str, Any]

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["metadata"] = _canonical(dict(self.metadata))
        value.update({
            "schema": "hardware_splicer.procurement_quote_snapshot.v1",
            "evidence_class": "supplier_claim_snapshot",
            "purchase_authorized": False,
            "order_submitted": False,
        })
        return value


class ProcurementQuoteBook:
    def __init__(self) -> None:
        self._quotes: dict[str, ProcurementQuote] = {}

    def add(
        self,
        *,
        quote_id: str,
        supplier_id: str,
        part_key: str,
        currency: str,
        unit_price: str | int | float | Decimal,
        minimum_order_quantity: int = 1,
        stock_quantity: int | None = None,
        lead_time_days: int | None = None,
        manufacturer_part_number: str | None = None,
        observed_at: str | None = None,
        valid_until: str | None = None,
        source_ref: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> ProcurementQuote:
        qid = _id(quote_id, "quote_id")
        if qid in self._quotes:
            raise FabricationValidationError("procurement quote id already exists")
        price = _money(unit_price)
        if type(minimum_order_quantity) is not int or not 1 <= minimum_order_quantity <= 10**9:
            raise FabricationValidationError("minimum_order_quantity must be a positive integer")
        if stock_quantity is not None and (type(stock_quantity) is not int or stock_quantity < 0):
            raise FabricationValidationError("stock_quantity must be a non-negative integer or null")
        if lead_time_days is not None and (type(lead_time_days) is not int or not 0 <= lead_time_days <= 36500):
            raise FabricationValidationError("lead_time_days must be a non-negative bounded integer or null")
        stamp = _timestamp(observed_at or datetime.now(timezone.utc).isoformat(), "observed_at")
        expiry = _timestamp(valid_until, "valid_until") if valid_until is not None else None
        if expiry is not None and expiry < stamp:
            raise FabricationValidationError("valid_until must not precede observed_at")
        mpn = None if manufacturer_part_number is None else _text(manufacturer_part_number, "manufacturer_part_number", 256)
        quote = ProcurementQuote(
            quote_id=qid,
            supplier_id=_id(supplier_id, "supplier_id"),
            part_key=_id(part_key, "part_key"),
            manufacturer_part_number=mpn,
            currency=_currency(currency),
            unit_price=format(price, "f"),
            minimum_order_quantity=minimum_order_quantity,
            stock_quantity=stock_quantity,
            lead_time_days=lead_time_days,
            observed_at=stamp.isoformat(),
            valid_until=expiry.isoformat() if expiry is not None else None,
            source_ref=_text(source_ref, "source_ref", 1024),
            metadata=_canonical(dict(metadata or {})),
        )
        self._quotes[qid] = quote
        return quote

    def list_public(self, *, part_key: str | None = None, supplier_id: str | None = None) -> list[dict[str, Any]]:
        values = self._quotes.values()
        if part_key is not None:
            wanted = _id(part_key, "part_key")
            values = [row for row in values if row.part_key == wanted]
        if supplier_id is not None:
            supplier = _id(supplier_id, "supplier_id")
            values = [row for row in values if row.supplier_id == supplier]
        return [row.public_dict() for row in sorted(values, key=lambda row: (row.part_key, row.supplier_id, row.quote_id))]

    def cost_bom(
        self,
        *,
        lines: Sequence[Mapping[str, Any]],
        currency: str,
        as_of: str | None = None,
        require_known_stock: bool = False,
    ) -> dict[str, Any]:
        if isinstance(lines, (str, bytes, bytearray)) or not isinstance(lines, Sequence) or not lines:
            raise FabricationValidationError("BOM costing requires a non-empty line list")
        if len(lines) > 10000:
            raise FabricationValidationError("BOM costing exceeds line limit")
        wanted_currency = _currency(currency)
        at = _timestamp(as_of or datetime.now(timezone.utc).isoformat(), "as_of")
        result_lines: list[dict[str, Any]] = []
        total = Decimal("0")
        complete = True
        for index, raw in enumerate(lines):
            if not isinstance(raw, Mapping):
                raise FabricationValidationError(f"BOM line {index} must be an object")
            part_key = _id(raw.get("part_key"), f"BOM line {index} part_key")
            quantity = raw.get("quantity")
            if type(quantity) is not int or not 1 <= quantity <= 10**9:
                raise FabricationValidationError(f"BOM line {index} quantity must be a positive integer")
            candidates = []
            for quote in self._quotes.values():
                if quote.part_key != part_key or quote.currency != wanted_currency:
                    continue
                if quote.valid_until is not None and _timestamp(quote.valid_until, "valid_until") < at:
                    continue
                buy_quantity = max(quantity, quote.minimum_order_quantity)
                if require_known_stock and quote.stock_quantity is None:
                    continue
                if quote.stock_quantity is not None and quote.stock_quantity < buy_quantity:
                    continue
                line_cost = _money(quote.unit_price) * buy_quantity
                candidates.append((line_cost, quote.lead_time_days if quote.lead_time_days is not None else 10**9, quote, buy_quantity))
            candidates.sort(key=lambda item: (item[0], item[1], item[2].supplier_id, item[2].quote_id))
            if not candidates:
                complete = False
                result_lines.append({
                    "part_key": part_key,
                    "required_quantity": quantity,
                    "status": "UNPRICED",
                    "selected_quote_id": None,
                })
                continue
            line_cost, _lead, quote, buy_quantity = candidates[0]
            total += line_cost
            result_lines.append({
                "part_key": part_key,
                "required_quantity": quantity,
                "purchase_quantity": buy_quantity,
                "status": "QUOTE_SELECTED_FOR_ESTIMATE",
                "selected_quote_id": quote.quote_id,
                "supplier_id": quote.supplier_id,
                "unit_price": quote.unit_price,
                "currency": quote.currency,
                "estimated_line_cost": format(line_cost, "f"),
                "stock_quantity_snapshot": quote.stock_quantity,
                "lead_time_days_snapshot": quote.lead_time_days,
                "observed_at": quote.observed_at,
            })
        payload = {
            "schema": "hardware_splicer.procurement_bom_estimate.v1",
            "currency": wanted_currency,
            "as_of": at.isoformat(),
            "lines": result_lines,
            "complete": complete,
            "estimated_total": format(total, "f"),
            "quote_count_considered": len(self._quotes),
            "price_guaranteed": False,
            "stock_guaranteed": False,
            "purchase_authorized": False,
            "order_submitted": False,
        }
        payload["estimate_sha256"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return payload


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise FabricationValidationError(f"{field} must be an ISO timestamp")
    token = value.strip()
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError as exc:
        raise FabricationValidationError(f"{field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _money(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise FabricationValidationError("unit_price must be a decimal number") from exc
    if not result.is_finite() or result < 0 or result > Decimal("1000000000000"):
        raise FabricationValidationError("unit_price is outside bounded range")
    return result


def _currency(value: Any) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError("currency must be a string")
    code = value.strip().upper()
    if len(code) != 3 or not code.isalpha() or not code.isascii():
        raise FabricationValidationError("currency must be a three-letter code")
    return code


def _canonical(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise FabricationValidationError("procurement metadata must be canonical JSON") from exc


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned


def _text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum or any(ord(ch) < 32 for ch in cleaned):
        raise FabricationValidationError(f"{field} must be bounded printable text")
    return cleaned
