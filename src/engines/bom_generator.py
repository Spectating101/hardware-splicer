#!/usr/bin/env python3
"""
BOM (Bill of Materials) Generator

Production-ish BOM extraction for KiCad netlists.

Key behaviors:
- Parses KiCad S-expression and XML netlists (best-effort).
- Preserves procurement identity when provided via KiCad fields (MFR/MPN/Supplier/DigiKey/LCSC).
- Normalizes common passive values so grouping is stable (10k vs 10K, 0.1uF vs 100nF).
- Applies optional conservative mappings from `data/bom/bom_mappings.json`.
- Adds estimated pricing when requested (deterministic, mapping-first).

This module intentionally avoids “guessing” manufacturer part numbers for ICs/connectors unless
explicitly provided in netlist fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

from src.engines.kicad_sexp import parse_sexp_file, sexp_find_all


@dataclass
class BOMItem:
    references: List[str]
    value: str
    footprint: str
    quantity: int
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    mpn: Optional[str] = None
    part_number: Optional[str] = None  # supplier-specific (DigiKey/LCSC/...)
    description: Optional[str] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    supplier: Optional[str] = None
    supplier_link: Optional[str] = None


class BOMGenerator:
    SCHEMA_VERSION = 2

    _MFR_KEYS = {"mfr", "manufacturer", "mfg", "brand"}
    _MPN_KEYS = {"mpn", "manufacturer part number", "mfr part number", "part number", "pn"}
    _SUPPLIER_KEYS = {"supplier", "vendor"}
    _DIGIKEY_KEYS = {"digikey", "digikey pn", "digikey part number"}
    _LCSC_KEYS = {"lcsc", "lcsc pn", "lcsc part number"}

    DEFAULT_MAPPING_PATH = Path(__file__).resolve().parents[2] / "data" / "bom" / "bom_mappings.json"

    PRICE_ESTIMATES = {
        "resistor": 0.02,
        "capacitor": 0.03,
        "diode": 0.08,
        "transistor": 0.15,
        "ic": 5.00,
        "connector": 0.75,
        "other": 1.00,
    }

    def __init__(self, *, mapping_path: Optional[str] = None, overrides_path: Optional[str] = None):
        self.mapping_path = Path(mapping_path) if mapping_path else self.DEFAULT_MAPPING_PATH
        self._mappings: List[dict] = self._load_mappings(self.mapping_path)
        op = overrides_path or os.environ.get("CIRCUIT_AI_BOM_OVERRIDES_PATH", "").strip()
        self.overrides_path = Path(op) if op else None
        self._overrides: Dict[str, Dict[str, str]] = self._load_overrides(self.overrides_path) if self.overrides_path else {}

    def _cache_dir(self) -> Optional[Path]:
        if os.environ.get("CIRCUIT_AI_BOM_CACHE", "").strip() not in {"1", "true", "TRUE", "yes", "YES"}:
            return None
        d = os.environ.get("CIRCUIT_AI_BOM_CACHE_DIR", "").strip()
        if d:
            p = Path(d)
        else:
            p = Path(__file__).resolve().parents[2] / "data" / "cache" / "bom_cache"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _load_mappings(self, path: Path) -> List[dict]:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def _load_overrides(self, path: Optional[Path]) -> Dict[str, Dict[str, str]]:
        if not path:
            return {}
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    out: Dict[str, Dict[str, str]] = {}
                    for ref, fields in data.items():
                        if isinstance(ref, str) and isinstance(fields, dict):
                            out[ref.strip()] = {str(k): str(v) for k, v in fields.items()}
                    return out
        except Exception:
            pass
        return {}

    def _apply_overrides(self, ref: str, fields: Dict[str, str]) -> Dict[str, str]:
        if not ref or not self._overrides:
            return fields
        o = self._overrides.get(ref)
        if not o:
            return fields
        merged = dict(fields or {})
        for k, v in o.items():
            if k and v and k not in merged:
                merged[k] = v
        return merged

    def _canon_key(self, s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip()).lower()

    def _infer_category(self, ref: str, footprint: str) -> str:
        r = (ref or "").upper()
        fp = (footprint or "").lower()
        if r.startswith("R"):
            return "resistor"
        if r.startswith("C"):
            return "capacitor"
        if r.startswith("D") or r.startswith("LED"):
            return "diode"
        if r.startswith("Q"):
            return "transistor"
        if r.startswith("U"):
            return "ic"
        if r.startswith("J") or r.startswith("P"):
            return "connector"
        if "resistor" in fp:
            return "resistor"
        if "capacitor" in fp:
            return "capacitor"
        if "connector" in fp or "usb" in fp or "hdmi" in fp or "rj45" in fp:
            return "connector"
        return "other"

    def _normalize_value(self, value: str) -> str:
        v = re.sub(r"\s+", "", (value or "").strip())
        if not v:
            return v

        upper = v.upper()

        # Resistors: 4K7, 1R0, 10K, 100R, 0R
        m = re.fullmatch(r"(?P<a>\d+)(?P<unit>[RKM])(?P<b>\d*)", upper)
        if m:
            a = m.group("a")
            unit = m.group("unit")
            b = m.group("b") or ""
            if unit == "R":
                return f"{a}.{b}R".replace(".R", "R").rstrip(".")
            if unit == "K":
                return f"{a}.{b}K".replace(".K", "K").rstrip(".")
            if unit == "M":
                return f"{a}.{b}M".replace(".M", "M").rstrip(".")

        # Resistors: 4.7K style
        m = re.fullmatch(r"(?P<num>\d+(?:\.\d+)?)(?P<unit>[RKM])", upper)
        if m:
            num = m.group("num").rstrip("0").rstrip(".")
            return f"{num}{m.group('unit')}"

        # Capacitors: 0.1uF -> 100nF, 1u -> 1uF, 100n -> 100nF
        cap = upper.replace("UF", "U").replace("NF", "N").replace("PF", "P")
        m = re.fullmatch(r"(?P<num>\d+(?:\.\d+)?)(?P<unit>[UNP])F?", cap)
        if m:
            num = float(m.group("num"))
            unit = m.group("unit")
            if unit == "U":
                nf = num * 1000.0
                if abs(nf - round(nf)) < 1e-9:
                    return f"{int(round(nf))}nF"
                return f"{num:g}uF"
            if unit == "N":
                if abs(num - round(num)) < 1e-9:
                    return f"{int(round(num))}nF"
                return f"{num:g}nF"
            if unit == "P":
                if abs(num - round(num)) < 1e-9:
                    return f"{int(round(num))}pF"
                return f"{num:g}pF"

        return v

    def _extract_identity(self, fields: Dict[str, str]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        if not isinstance(fields, dict):
            return None, None, None, None
        norm = {self._canon_key(k): (v or "").strip() for k, v in fields.items() if k}
        mfr = next((norm[k] for k in norm if k in self._MFR_KEYS and norm[k]), None)
        mpn = next((norm[k] for k in norm if k in self._MPN_KEYS and norm[k]), None)
        supplier = next((norm[k] for k in norm if k in self._SUPPLIER_KEYS and norm[k]), None)
        pn = next((norm[k] for k in norm if k in self._DIGIKEY_KEYS and norm[k]), None)
        if not pn:
            pn = next((norm[k] for k in norm if k in self._LCSC_KEYS and norm[k]), None)
        return mfr, mpn, supplier, pn

    def parse_kicad_netlist(self, netlist_path: str) -> List[Dict[str, Any]]:
        p = Path(netlist_path)
        if not p.exists():
            return []

        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:4096]
        except Exception:
            head = ""

        # 0) KiCad XML netlist (kicadxml)
        if "<export" in head and "<components" in head and "<comp" in head:
            try:
                root = ET.parse(str(p)).getroot()
                comps: List[Dict[str, Any]] = []
                for comp in root.findall(".//components/comp"):
                    ref = (comp.get("ref") or "").strip()
                    value = (comp.findtext("value") or "").strip()
                    footprint = (comp.findtext("footprint") or "").strip()
                    fields: Dict[str, str] = {}
                    for f in comp.findall(".//fields/field"):
                        name = (f.get("name") or "").strip()
                        txt = (f.text or "").strip()
                        if name:
                            fields[name] = txt
                    fields = self._apply_overrides(ref, fields)
                    if ref:
                        comps.append({"reference": ref, "value": value, "footprint": footprint, "fields": fields})
                if comps:
                    return comps
            except Exception:
                pass

        # 1) KiCad S-expression netlist
        try:
            ast = parse_sexp_file(str(p))
            comps: List[Dict[str, Any]] = []
            for comp in sexp_find_all(ast, "comp"):
                ref = ""
                value = ""
                footprint = ""
                fields: Dict[str, str] = {}

                for child in comp:
                    if not isinstance(child, list) or len(child) < 2:
                        continue
                    head = child[0]
                    if head == "ref" and isinstance(child[1], str):
                        ref = child[1]
                    elif head == "value" and isinstance(child[1], str):
                        value = child[1]
                    elif head == "footprint" and isinstance(child[1], str):
                        footprint = child[1]
                    elif head == "fields":
                        for f in child[1:]:
                            if not isinstance(f, list) or not f or f[0] != "field":
                                continue
                            fname = ""
                            fval: Optional[str] = None
                            for sub in f[1:]:
                                if isinstance(sub, list) and len(sub) >= 2 and sub[0] == "name" and isinstance(sub[1], str):
                                    fname = sub[1]
                                elif isinstance(sub, str):
                                    fval = sub
                            if fname and fval is not None:
                                fields[fname] = fval

                if ref:
                    fields = self._apply_overrides(ref, fields)
                    comps.append({"reference": ref, "value": value, "footprint": footprint, "fields": fields})
            if comps:
                return comps
        except Exception:
            pass

        # 2) Regex fallback
        components: List[Dict[str, Any]] = []
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            comp_pattern = r"\(comp\s+\(ref\s+([^\)\s]+)\)\s+\(value\s+([^)]+)\)(?:\s+\(footprint\s+([^)]+)\))?"
            for match in re.finditer(comp_pattern, content):
                ref = match.group(1).strip().strip('"')
                value = match.group(2).strip().strip('"')
                footprint = match.group(3).strip().strip('"') if match.group(3) else ""
                fields = self._apply_overrides(ref, {})
                components.append({"reference": ref, "value": value, "footprint": footprint, "fields": fields})
        except Exception:
            return []
        return components

    def _apply_mappings(self, item: BOMItem) -> None:
        if not self._mappings:
            return
        value = item.value or ""
        footprint = item.footprint or ""
        category = item.category or ""

        for m in self._mappings:
            try:
                if m.get("category") and self._canon_key(m["category"]) != self._canon_key(category):
                    continue
                if m.get("value") and self._canon_key(m["value"]) != self._canon_key(value):
                    continue
                if m.get("value_re") and not re.search(m["value_re"], value, re.IGNORECASE):
                    continue
                if m.get("footprint_re") and not re.search(m["footprint_re"], footprint, re.IGNORECASE):
                    continue
                if not item.description and m.get("description"):
                    item.description = m["description"]
                if not item.supplier and m.get("supplier"):
                    item.supplier = m["supplier"]
                if not item.part_number and m.get("part_number"):
                    item.part_number = m["part_number"]
                if not item.manufacturer and m.get("manufacturer"):
                    item.manufacturer = m["manufacturer"]
                if not item.mpn and m.get("mpn"):
                    item.mpn = m["mpn"]
                if item.unit_price is None and isinstance(m.get("unit_price_estimate"), (int, float)):
                    item.unit_price = float(m["unit_price_estimate"])
                return
            except Exception:
                continue

    def group_components(self, components: List[Dict[str, Any]]) -> List[BOMItem]:
        grouped: Dict[Tuple[str, str, str, str, str, str], dict] = {}

        for comp in components:
            ref = (comp.get("reference") or "").strip()
            value = comp.get("value") or ""
            footprint = comp.get("footprint") or ""
            fields = comp.get("fields") or {}

            norm_value = self._normalize_value(value)
            norm_footprint = (footprint or "").strip()
            mfr, mpn, supplier, pn = self._extract_identity(fields)

            key = (
                norm_value or value,
                norm_footprint,
                self._canon_key(mfr or ""),
                self._canon_key(mpn or ""),
                self._canon_key(supplier or ""),
                self._canon_key(pn or ""),
            )

            if key not in grouped:
                grouped[key] = {
                    "references": [],
                    "value": norm_value or value,
                    "footprint": norm_footprint,
                    "ref0": ref,
                    "manufacturer": mfr,
                    "mpn": mpn,
                    "supplier": supplier,
                    "part_number": pn,
                }
            grouped[key]["references"].append(ref)

        out: List[BOMItem] = []
        for _, data in grouped.items():
            refs = sorted(data["references"])
            out.append(
                BOMItem(
                    references=refs,
                    value=data["value"],
                    footprint=data["footprint"],
                    quantity=len(refs),
                    category=self._infer_category(data.get("ref0") or "", data.get("footprint") or ""),
                    manufacturer=data.get("manufacturer"),
                    mpn=data.get("mpn"),
                    supplier=data.get("supplier"),
                    part_number=data.get("part_number"),
                )
            )
        return sorted(out, key=lambda x: x.references[0])

    def add_part_numbers(self, bom_items: List[BOMItem]) -> List[BOMItem]:
        for item in bom_items:
            self._apply_mappings(item)
            if item.part_number and not item.supplier_link:
                if item.supplier and self._canon_key(item.supplier) == "digikey":
                    item.supplier_link = f"https://www.digikey.com/en/products/detail/{item.part_number}"
        return bom_items

    def add_pricing(self, bom_items: List[BOMItem], include_pricing: bool = False) -> List[BOMItem]:
        if not include_pricing:
            return bom_items
        for item in bom_items:
            if item.unit_price is None:
                comp_type = item.category or "other"
                item.unit_price = float(self.PRICE_ESTIMATES.get(comp_type, 1.00))
            item.total_price = float(item.unit_price or 0.0) * int(item.quantity)
        return bom_items

    def generate_bom(self, netlist_path: str, include_pricing: bool = False) -> Dict[str, Any]:
        p = Path(netlist_path)
        cache_dir = self._cache_dir()
        cache_path: Optional[Path] = None
        if cache_dir and p.exists():
            mapping_bytes = b""
            try:
                if self.mapping_path.exists():
                    mapping_bytes = self.mapping_path.read_bytes()
            except Exception:
                mapping_bytes = b""
            h = hashlib.sha256()
            h.update(p.read_bytes())
            h.update(b"|pricing=" + str(bool(include_pricing)).encode("utf-8"))
            h.update(b"|mapping=" + hashlib.sha256(mapping_bytes).digest())
            cache_path = cache_dir / f"bom_{h.hexdigest()}.json"
            if cache_path.exists():
                try:
                    cached = json.loads(cache_path.read_text(encoding="utf-8"))
                    if isinstance(cached, dict) and cached.get("status") == "success":
                        cached["cache_hit"] = True
                        return cached
                except Exception:
                    pass

        components = self.parse_kicad_netlist(netlist_path)
        if not components:
            return {"status": "error", "message": "No components found in netlist", "items": []}

        bom_items = self.group_components(components)
        bom_items = self.add_part_numbers(bom_items)
        bom_items = self.add_pricing(bom_items, include_pricing)

        total_components = len(components)
        unique_parts = len(bom_items)
        total_cost = sum(float(item.total_price or 0.0) for item in bom_items)
        parts_with_numbers = sum(1 for item in bom_items if item.part_number)
        digikey_numbers = sum(
            1 for item in bom_items if item.part_number and item.supplier and self._canon_key(item.supplier) == "digikey"
        )

        missing_identity = [
            {
                "value": item.value,
                "footprint": item.footprint,
                "category": item.category,
                "suggestion": "Add KiCad fields like Manufacturer/MPN/Supplier/DigiKey/LCSC for procurement-grade BOM.",
            }
            for item in bom_items
            if not item.part_number and not item.mpn and (item.category in {"ic", "connector"})
        ]

        out = {
            "status": "success",
            "schema_version": self.SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cache_hit": False,
            "summary": {
                "total_components": total_components,
                "unique_parts": unique_parts,
                "parts_with_part_numbers": parts_with_numbers,
                "parts_with_digikey_numbers": digikey_numbers,
                "estimated_total_cost": total_cost if include_pricing else None,
            },
            "missing_identity": missing_identity,
            "items": [
                {
                    "references": item.references,
                    "value": item.value,
                    "footprint": item.footprint,
                    "quantity": item.quantity,
                    "category": item.category,
                    "manufacturer": item.manufacturer,
                    "mpn": item.mpn,
                    "part_number": item.part_number,
                    "supplier": item.supplier,
                    "supplier_link": item.supplier_link,
                    "description": item.description,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                }
                for item in bom_items
            ],
        }
        if cache_path:
            try:
                cache_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass
        return out

    def export_csv(self, bom: Dict[str, Any]) -> str:
        lines: List[str] = []
        lines.append(
            "Reference,Value,Footprint,Quantity,Category,Manufacturer,MPN,Part Number,Supplier,Unit Price,Total Price"
        )
        for item in bom.get("items", []) or []:
            refs = "+".join(item.get("references") or [])
            line = (
                f"{refs},{item.get('value','')},{item.get('footprint','')},{item.get('quantity','')},"
                f"{item.get('category','')},{item.get('manufacturer','')},{item.get('mpn','')},"
                f"{item.get('part_number','')},{item.get('supplier','')},"
                f"{item.get('unit_price','')},{item.get('total_price','')}"
            )
            lines.append(line)
        lines.append("")
        summary = bom.get("summary") or {}
        lines.append(f"Total Components,{summary.get('total_components')}")
        lines.append(f"Unique Parts,{summary.get('unique_parts')}")
        if summary.get("estimated_total_cost") is not None:
            lines.append(f"Estimated Total Cost,${float(summary.get('estimated_total_cost') or 0.0):.2f}")
        return "\n".join(lines)
