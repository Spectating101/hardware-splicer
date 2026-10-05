"""Pure structural diff for KiCad schematic and PCB s-expression files.

The result is review evidence for a Compare / redline view. It never promotes an
engineering claim, never inherits an electrical contract, and never blocks a
release. Authority is never implicitly upgraded.
"""

from __future__ import annotations

import errno
import math
import os
import stat
from pathlib import Path
from typing import Any

from .build_files_security import max_kicad_content_bytes

SCHEMA_VERSION = "hardware_splicer.kicad_diff.v1"
MAX_CHANGES = 500
POSITION_QUANTUM_MM = 0.001
MAX_ABS_MM = 1e6
MAX_SEXPR_DEPTH = 200

_SCH_ROOT = "kicad_sch"
_PCB_ROOT = "kicad_pcb"
_SCH_TYPES = (
    "symbol",
    "wire",
    "bus",
    "junction",
    "label",
    "global_label",
    "hierarchical_label",
    "no_connect",
    "sheet",
)
_PCB_TYPES = ("footprint", "segment", "via", "zone", "board")
_TYPE_ORDER = {name: index for index, name in enumerate(_SCH_TYPES + _PCB_TYPES)}
_SPECIAL_PROPERTIES = frozenset(
    {"Reference", "Value", "Footprint", "Sheetname", "Sheetfile", "Sheet name", "Sheet file"}
)
_AT_FLAG_ATOMS = frozenset({"unlocked", "locked"})
_SHEET_NAME_KEYS = ("Sheetname", "Sheet name")
_SHEET_FILE_KEYS = ("Sheetfile", "Sheet file")
_WIDTH_KEYS = (
    "last_trace_width",
    "trace_min",
    "min_trace",
    "trace_width",
    "default_trace_width",
    "min_width",
)
_CLEARANCE_KEYS = (
    "trace_clearance",
    "clearance",
    "min_clearance",
    "default_clearance",
    "pad_to_mask_clearance",
)
_ESCAPE_MAP = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


class KicadDiffError(ValueError):
    """Malformed or unreadable KiCad input. Message is short on purpose."""


def parse_kicad_sexp(text: str) -> list[Any]:
    """Parse one KiCad s-expression document into a nested list tree."""

    return _parse_sexp(text)


def diff_kicad_text(kind: str, base_text: str, candidate_text: str) -> dict[str, Any]:
    """Structurally diff two KiCad documents. Pure: no I/O, no input mutation."""

    if kind not in {"schematic", "pcb"}:
        raise KicadDiffError("kind must be schematic or pcb")
    if not isinstance(base_text, str) or not isinstance(candidate_text, str):
        raise KicadDiffError("text inputs must be strings")
    if not base_text.strip() or not candidate_text.strip():
        raise KicadDiffError("empty KiCad text")

    base_items = _extract_items(kind, _parse_document(kind, base_text))
    candidate_items = _extract_items(kind, _parse_document(kind, candidate_text))
    changes, unchanged = _diff_items(kind, base_items, candidate_items)
    changes.sort(key=_change_sort_key)
    summary = {
        "added": sum(1 for row in changes if row["change"] == "added"),
        "removed": sum(1 for row in changes if row["change"] == "removed"),
        "changed": sum(1 for row in changes if row["change"] == "changed"),
        "unchanged": unchanged,
    }
    truncated = len(changes) > MAX_CHANGES
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "summary": summary,
        "changes": changes[:MAX_CHANGES],
        "limits": {"truncated": truncated, "max_changes": MAX_CHANGES},
    }


def diff_kicad_files(kind: str, base_path: str | Path, candidate_path: str | Path) -> dict[str, Any]:
    """Read two KiCad files and return the same report as `diff_kicad_text`."""

    return diff_kicad_text(kind, _read_kicad_path(base_path), _read_kicad_path(candidate_path))


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(os.fspath(path))))


def _path_is_symlink(path: Path) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(path).st_mode) or path.is_symlink()
    except OSError:
        return False


def _reject_symlinked_parents(path: Path) -> Path:
    lexical = _lexical_absolute(path)
    provided_dir = _lexical_absolute(path.parent)
    cursor = lexical.parent
    while True:
        if _path_is_symlink(cursor):
            raise KicadDiffError("symlinked path not allowed")
        if cursor == provided_dir or cursor.parent == cursor:
            break
        cursor = cursor.parent
    if _path_is_symlink(provided_dir):
        raise KicadDiffError("symlinked path not allowed")
    return lexical


def _read_kicad_path(path: str | Path) -> str:
    given = Path(path)
    lexical = _reject_symlinked_parents(given)
    limit = max_kicad_content_bytes()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(os.fspath(lexical), flags)
    except OSError as exc:
        if getattr(exc, "errno", None) in {errno.ELOOP, errno.EMLINK}:
            raise KicadDiffError("symlinked path not allowed") from None
        raise KicadDiffError("cannot read file") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise KicadDiffError("not a readable file")
        if info.st_size > limit:
            raise KicadDiffError("file exceeds size limit")
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining > 0:
            piece = os.read(fd, remaining)
            if not piece:
                break
            chunks.append(piece)
            remaining -= len(piece)
    finally:
        os.close(fd)
    return b"".join(chunks).decode("utf-8", errors="replace")


def _tokenize_sexp(text: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    length = len(text)
    depth = 0
    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char in "()":
            if char == "(":
                depth += 1
                if depth > MAX_SEXPR_DEPTH:
                    raise KicadDiffError("input nested too deeply")
            else:
                depth -= 1
            tokens.append(char)
            index += 1
            continue
        if char == '"':
            index += 1
            chars: list[str] = []
            closed = False
            while index < length:
                current = text[index]
                if current == "\\":
                    if index + 1 >= length:
                        raise KicadDiffError("unclosed string")
                    escaped = text[index + 1]
                    chars.append(_ESCAPE_MAP.get(escaped, escaped))
                    index += 2
                    continue
                if current == '"':
                    tokens.append("".join(chars))
                    index += 1
                    closed = True
                    break
                chars.append(current)
                index += 1
            if not closed:
                raise KicadDiffError("unclosed string")
            continue
        start = index
        while index < length and not text[index].isspace() and text[index] not in "()\"":
            index += 1
        tokens.append(text[start:index])
    return tokens


def _parse_sexp(text: str) -> list[Any]:
    tokens = _tokenize_sexp(text)
    if not tokens:
        raise KicadDiffError("malformed s-expression")
    stack: list[list[Any]] = []
    root: list[Any] | None = None
    for token in tokens:
        if token == "(":
            if len(stack) >= MAX_SEXPR_DEPTH:
                raise KicadDiffError("input nested too deeply")
            if not stack and root is not None:
                raise KicadDiffError("unexpected trailing content")
            node: list[Any] = []
            if stack:
                stack[-1].append(node)
            stack.append(node)
            continue
        if token == ")":
            if not stack:
                raise KicadDiffError("unbalanced parentheses")
            finished = stack.pop()
            if not stack:
                if root is not None:
                    raise KicadDiffError("unexpected trailing content")
                root = finished
            continue
        if not stack:
            raise KicadDiffError("unexpected trailing content")
        stack[-1].append(token)
    if stack or root is None:
        raise KicadDiffError("unbalanced parentheses")
    return root


def _parse_document(kind: str, text: str) -> list[Any]:
    tree = _parse_sexp(text)
    expected = _SCH_ROOT if kind == "schematic" else _PCB_ROOT
    if not tree or tree[0] != expected:
        raise KicadDiffError(f"not a KiCad {kind}")
    return tree


def _require_finite_mm(value: float) -> float:
    if not math.isfinite(value) or abs(value) > MAX_ABS_MM:
        raise KicadDiffError("non-finite or out-of-range coordinate")
    return value


def _round_mm(value: float) -> float:
    bounded = _require_finite_mm(float(value))
    rounded = round(bounded / POSITION_QUANTUM_MM) * POSITION_QUANTUM_MM
    rounded = round(rounded, 3)
    return 0.0 if rounded == 0.0 else rounded


def _parse_num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    parsed: float | None
    if isinstance(value, (int, float)):
        parsed = float(value)
    elif isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
    else:
        return None
    return _require_finite_mm(parsed)


def _parse_geometry_num(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        raise KicadDiffError("malformed coordinate")
    if isinstance(value, (int, float)):
        parsed = float(value)
    elif isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            raise KicadDiffError("malformed coordinate") from None
    else:
        raise KicadDiffError("malformed coordinate")
    return _require_finite_mm(parsed)


def _flag(value: Any, default: bool | None = None) -> bool | None:
    if value in {"yes", "true", "1"}:
        return True
    if value in {"no", "false", "0"}:
        return False
    if isinstance(value, bool):
        return value
    return default


def _atom(node: Any) -> str | None:
    if isinstance(node, list) and node and isinstance(node[0], str):
        return node[0]
    return None


def _child(node: list[Any], name: str) -> list[Any] | None:
    for item in node[1:]:
        if isinstance(item, list) and item and item[0] == name:
            return item
    return None


def _child_value(node: list[Any], name: str) -> Any:
    child = _child(node, name)
    if child is None or len(child) < 2:
        return None
    return child[1]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _uuid_of(node: list[Any]) -> str | None:
    for key in ("uuid", "tstamp"):
        value = _child_value(node, key)
        if value is not None and str(value):
            return str(value)
    return None


def _at_xyr(node: list[Any]) -> tuple[float | None, float | None, float | None]:
    child = _child(node, "at")
    if child is None:
        return None, None, None
    numbers: list[float] = []
    for token in child[1:]:
        if isinstance(token, list):
            continue
        text = str(token)
        if text in _AT_FLAG_ATOMS:
            continue
        numbers.append(_parse_geometry_num(text))
    x = _round_mm(numbers[0]) if len(numbers) >= 1 else None
    y = _round_mm(numbers[1]) if len(numbers) >= 2 else None
    rotation = _round_mm(numbers[2]) if len(numbers) >= 3 else 0.0
    return x, y, rotation


def _xy_pair(node: list[Any] | None) -> tuple[float | None, float | None]:
    if node is None:
        return None, None
    if len(node) < 3:
        raise KicadDiffError("malformed coordinate")
    return _round_mm(_parse_geometry_num(node[1])), _round_mm(_parse_geometry_num(node[2]))


def _pts(node: list[Any]) -> list[tuple[float, float]]:
    pts = _child(node, "pts")
    if pts is None:
        return []
    points: list[tuple[float, float]] = []
    for item in pts[1:]:
        if not isinstance(item, list) or not item or item[0] != "xy":
            raise KicadDiffError("malformed coordinate")
        x, y = _xy_pair(item)
        if x is None or y is None:
            raise KicadDiffError("malformed coordinate")
        points.append((x, y))
    return points


def _geometry_child_num(node: list[Any], name: str) -> float | None:
    child = _child(node, name)
    if child is None:
        return None
    if len(child) < 2:
        raise KicadDiffError("malformed coordinate")
    return _round_mm(_parse_geometry_num(child[1]))


def _bbox(points: list[tuple[float, float]]) -> dict[str, float] | None:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "min_x": min(xs),
        "min_y": min(ys),
        "max_x": max(xs),
        "max_y": max(ys),
    }


def _point_bbox(x: float | None, y: float | None) -> dict[str, float] | None:
    if x is None or y is None:
        return None
    return {"min_x": x, "min_y": y, "max_x": x, "max_y": y}


def _properties(node: list[Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in node[1:]:
        if not isinstance(item, list) or len(item) < 3 or item[0] != "property":
            continue
        name = str(item[1])
        values[name] = str(item[2])
    if "Reference" not in values or "Value" not in values:
        for item in node[1:]:
            if not isinstance(item, list) or len(item) < 3 or item[0] != "fp_text":
                continue
            kind = str(item[1])
            if kind == "reference" and "Reference" not in values:
                values["Reference"] = str(item[2])
            elif kind == "value" and "Value" not in values:
                values["Value"] = str(item[2])
    return values


def _item(
    *,
    item_type: str,
    ref: str | None = None,
    uuid: str | None = None,
    label: str,
    x_mm: float | None = None,
    y_mm: float | None = None,
    bbox_mm: dict[str, float] | None = None,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "item_type": item_type,
        "ref": ref,
        "uuid": uuid,
        "label": label,
        "x_mm": x_mm,
        "y_mm": y_mm,
        "bbox_mm": bbox_mm,
        "fields": fields or {},
    }


def _fmt_xy(x: float, y: float) -> str:
    return f"({_fmt_num(x)},{_fmt_num(y)})"


def _fmt_num(value: float) -> str:
    text = f"{_round_mm(value):.3f}".rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _fmt_flag(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "none" if value is None else str(value)


def _named_flag(node: list[Any], name: str, *, default: bool = False) -> bool:
    child = _child(node, name)
    if child is None:
        return default
    if len(child) < 2:
        return True
    if isinstance(child[1], list):
        return default
    flagged = _flag(child[1])
    return default if flagged is None else flagged


def _effects_hide(node: list[Any]) -> bool:
    effects = _child(node, "effects")
    search = effects if effects is not None else node
    return _named_flag(search, "hide", default=False)


def _prop(props: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        if key in props:
            return props[key]
    return None


def _zone_layer_list(node: list[Any]) -> list[str]:
    layers: list[str] = []
    seen: set[str] = set()

    def _add(value: Any) -> None:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            layers.append(text)

    single = _child_value(node, "layer")
    if single is not None:
        _add(single)
    group = _child(node, "layers")
    if group is not None:
        for item in group[1:]:
            if not isinstance(item, list):
                _add(item)
    return layers


def _as_points(value: Any) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    if not isinstance(value, list):
        return points
    for item in value:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            points.append((float(item[0]), float(item[1])))
    return points


def _identity_text(kind: str, item: dict[str, Any]) -> str:
    if item.get("ref"):
        return str(item["ref"])
    fields = item["fields"]
    if kind == "pcb":
        net = fields.get("net")
        layer = fields.get("layer") or ""
        if net is not None or layer:
            return f"{net}+{layer}"
    return str(fields.get("text") or "")


def _full_geometry(item: dict[str, Any]) -> tuple[Any, ...]:
    fields = item["fields"]
    pts = _as_points(fields.get("points") or fields.get("outline"))
    if pts:
        geom: Any = tuple(pts)
    else:
        geom = (item.get("x_mm"), item.get("y_mm"))
    return (
        geom,
        fields.get("size"),
        fields.get("drill"),
        fields.get("width"),
        tuple(fields.get("layers") or ()),
    )


def _extract_items(kind: str, tree: list[Any]) -> list[dict[str, Any]]:
    if kind == "schematic":
        return _extract_schematic(tree)
    return _extract_pcb(tree)


def _extract_schematic(tree: list[Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for node in tree[1:]:
        name = _atom(node)
        if not isinstance(node, list) or name is None:
            continue
        if name == "symbol":
            item = _schematic_symbol(node)
            if item is not None:
                items.append(item)
        elif name in {"wire", "bus"}:
            item = _schematic_wire(node, name)
            if item is not None:
                items.append(item)
        elif name == "junction":
            items.append(_schematic_point(node, "junction", "junction"))
        elif name in {"label", "global_label", "hierarchical_label"}:
            items.append(_schematic_label(node, name))
        elif name == "no_connect":
            items.append(_schematic_point(node, "no_connect", "no_connect"))
        elif name == "sheet":
            items.append(_schematic_sheet(node))
    return items


def _schematic_symbol(node: list[Any]) -> dict[str, Any] | None:
    if _child(node, "lib_id") is None:
        return None
    props = _properties(node)
    ref = props.get("Reference")
    value = props.get("Value")
    x_mm, y_mm, rotation = _at_xyr(node)
    mirror_node = _child(node, "mirror")
    mirror = str(mirror_node[1]) if mirror_node is not None and len(mirror_node) > 1 else None
    unit_raw = _parse_num(_child_value(node, "unit"))
    fields: dict[str, Any] = {
        "value": value,
        "lib_id": _text(_child_value(node, "lib_id")),
        "footprint": props.get("Footprint"),
        "rotation": rotation if rotation is not None else 0.0,
        "mirror": mirror,
        "unit": int(unit_raw) if unit_raw is not None else 1,
        "dnp": _named_flag(node, "dnp", default=False),
        "in_bom": _named_flag(node, "in_bom", default=True),
        "exclude_from_sim": _named_flag(node, "exclude_from_sim", default=False),
        "on_board": _named_flag(node, "on_board", default=True),
    }
    for key, val in props.items():
        if key not in _SPECIAL_PROPERTIES:
            fields[f"property:{key}"] = val
    label = " ".join(part for part in (ref, value) if part)
    return _item(
        item_type="symbol",
        ref=ref,
        uuid=_uuid_of(node),
        label=label or "symbol",
        x_mm=x_mm,
        y_mm=y_mm,
        bbox_mm=_point_bbox(x_mm, y_mm),
        fields=fields,
    )


def _schematic_wire(node: list[Any], item_type: str) -> dict[str, Any] | None:
    points = _pts(node)
    if len(points) < 2:
        return None
    (x1, y1), (x2, y2) = points[0], points[-1]
    bbox = _bbox(points)
    return _item(
        item_type=item_type,
        uuid=_uuid_of(node),
        label=f"Wire {_fmt_xy(x1, y1)}->{_fmt_xy(x2, y2)}",
        x_mm=x1,
        y_mm=y1,
        bbox_mm=bbox,
        fields={
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "points": [list(point) for point in points],
        },
    )


def _schematic_label(node: list[Any], item_type: str) -> dict[str, Any]:
    text = str(node[1]) if len(node) > 1 and not isinstance(node[1], list) else ""
    x_mm, y_mm, rotation = _at_xyr(node)
    pos = f" at {_fmt_xy(x_mm, y_mm)}" if x_mm is not None and y_mm is not None else ""
    fields: dict[str, Any] = {
        "text": text,
        "rotation": rotation if rotation is not None else 0.0,
        "hide": _effects_hide(node),
    }
    shape = _text(_child_value(node, "shape"))
    if item_type in {"global_label", "hierarchical_label"} or shape is not None:
        fields["shape"] = shape
    return _item(
        item_type=item_type,
        ref=text or None,
        uuid=_uuid_of(node),
        label=f'Label "{text}"{pos}',
        x_mm=x_mm,
        y_mm=y_mm,
        bbox_mm=_point_bbox(x_mm, y_mm),
        fields=fields,
    )


def _schematic_point(node: list[Any], item_type: str, label: str) -> dict[str, Any]:
    x_mm, y_mm, _rotation = _at_xyr(node)
    return _item(
        item_type=item_type,
        uuid=_uuid_of(node),
        label=label,
        x_mm=x_mm,
        y_mm=y_mm,
        bbox_mm=_point_bbox(x_mm, y_mm),
    )


def _schematic_sheet(node: list[Any]) -> dict[str, Any]:
    props = _properties(node)
    name = _prop(props, _SHEET_NAME_KEYS)
    filename = _prop(props, _SHEET_FILE_KEYS)
    x_mm, y_mm, _rotation = _at_xyr(node)
    return _item(
        item_type="sheet",
        ref=name,
        uuid=_uuid_of(node),
        label=name or filename or "sheet",
        x_mm=x_mm,
        y_mm=y_mm,
        bbox_mm=_point_bbox(x_mm, y_mm),
        fields={"name": name, "file": filename},
    )


def _extract_pcb(tree: list[Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = [_pcb_board(tree)]
    for node in tree[1:]:
        name = _atom(node)
        if not isinstance(node, list) or name is None:
            continue
        if name in {"footprint", "module"}:
            items.append(_pcb_footprint(node))
        elif name == "segment":
            item = _pcb_segment(node)
            if item is not None:
                items.append(item)
        elif name == "via":
            items.append(_pcb_via(node))
        elif name == "zone":
            items.append(_pcb_zone(node))
    return items


def _pcb_board(tree: list[Any]) -> dict[str, Any]:
    layers = _child(tree, "layers")
    layer_count = 0
    if layers is not None:
        layer_count = sum(1 for item in layers[1:] if isinstance(item, list) and item)
    setup = _child(tree, "setup")
    width = None
    clearance = None
    if setup is not None:
        for key in _WIDTH_KEYS:
            raw = _parse_num(_child_value(setup, key))
            if raw is not None:
                width = _round_mm(raw)
                break
        for key in _CLEARANCE_KEYS:
            raw = _parse_num(_child_value(setup, key))
            if raw is not None:
                clearance = _round_mm(raw)
                break
    fields: dict[str, Any] = {"layer_count": layer_count}
    if width is not None:
        fields["width"] = width
    if clearance is not None:
        fields["clearance"] = clearance
    return _item(item_type="board", label="board", fields=fields)


def _pcb_footprint(node: list[Any]) -> dict[str, Any]:
    lib_id = str(node[1]) if len(node) > 1 and not isinstance(node[1], list) else None
    props = _properties(node)
    ref = props.get("Reference")
    value = props.get("Value")
    x_mm, y_mm, rotation = _at_xyr(node)
    layer = _text(_child_value(node, "layer"))
    fields: dict[str, Any] = {
        "value": value,
        "footprint": lib_id,
        "layer": layer,
        "rotation": rotation if rotation is not None else 0.0,
        "locked": _named_flag(node, "locked", default=False),
        "placed": _named_flag(node, "placed", default=True),
    }
    for key, val in props.items():
        if key not in _SPECIAL_PROPERTIES:
            fields[f"property:{key}"] = val
    label = " ".join(part for part in (ref, value) if part) or lib_id or "footprint"
    return _item(
        item_type="footprint",
        ref=ref,
        uuid=_uuid_of(node),
        label=label,
        x_mm=x_mm,
        y_mm=y_mm,
        bbox_mm=_point_bbox(x_mm, y_mm),
        fields=fields,
    )


def _pcb_segment(node: list[Any]) -> dict[str, Any] | None:
    x1, y1 = _xy_pair(_child(node, "start"))
    x2, y2 = _xy_pair(_child(node, "end"))
    if x1 is None or y1 is None or x2 is None or y2 is None:
        return None
    width = _geometry_child_num(node, "width")
    net = _child_value(node, "net")
    layer = _text(_child_value(node, "layer"))
    fields: dict[str, Any] = {
        "layer": layer,
        "width": width,
        "net": str(net) if net is not None else None,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "points": [[x1, y1], [x2, y2]],
    }
    net_s = f" net {net}" if net is not None else ""
    width_s = f" w{_fmt_num(width)}" if width is not None else ""
    return _item(
        item_type="segment",
        uuid=_uuid_of(node),
        label=f"Track {layer or '?'}{net_s} {_fmt_xy(x1, y1)}->{_fmt_xy(x2, y2)}{width_s}",
        x_mm=x1,
        y_mm=y1,
        bbox_mm=_bbox([(x1, y1), (x2, y2)]),
        fields=fields,
    )


def _pcb_via(node: list[Any]) -> dict[str, Any]:
    x_mm, y_mm, _rotation = _at_xyr(node)
    size = _geometry_child_num(node, "size")
    drill = _geometry_child_num(node, "drill")
    net = _child_value(node, "net")
    layers = _child(node, "layers")
    layer = None
    if layers is not None and len(layers) > 1:
        layer = " ".join(str(part) for part in layers[1:] if not isinstance(part, list))
    fields: dict[str, Any] = {
        "size": size,
        "drill": drill,
        "net": str(net) if net is not None else None,
        "layer": layer,
        "locked": _named_flag(node, "locked", default=False),
        "free": _named_flag(node, "free", default=False),
    }
    net_s = f" net {net}" if net is not None else ""
    pos = f" at {_fmt_xy(x_mm, y_mm)}" if x_mm is not None and y_mm is not None else ""
    size_s = ""
    if size is not None and drill is not None:
        size_s = f" {_fmt_num(size)}/{_fmt_num(drill)}"
    return _item(
        item_type="via",
        uuid=_uuid_of(node),
        label=f"Via{net_s}{pos}{size_s}",
        x_mm=x_mm,
        y_mm=y_mm,
        bbox_mm=_point_bbox(x_mm, y_mm),
        fields=fields,
    )


def _pcb_zone(node: list[Any]) -> dict[str, Any]:
    net = _child_value(node, "net")
    net_name = _text(_child_value(node, "net_name"))
    layers = _zone_layer_list(node)
    layer = ",".join(layers) if layers else None
    name = _text(_child_value(node, "name"))
    polygon = _child(node, "polygon")
    points = _pts(polygon) if polygon is not None else []
    bbox = _bbox(points)
    if bbox is not None:
        x_mm = _round_mm((bbox["min_x"] + bbox["max_x"]) / 2)
        y_mm = _round_mm((bbox["min_y"] + bbox["max_y"]) / 2)
    elif points:
        x_mm, y_mm = points[0]
    else:
        x_mm = y_mm = None
    fields: dict[str, Any] = {
        "net": str(net) if net is not None else None,
        "net_name": net_name,
        "layer": layer,
        "layers": layers,
        "name": name,
        "outline": [list(point) for point in points],
        "fill": _named_flag(node, "fill", default=False),
        "connect_pads": _named_flag(node, "connect_pads", default=False),
    }
    title = name or net_name or "zone"
    on = f" on {layer}" if layer else ""
    return _item(
        item_type="zone",
        ref=name or net_name,
        uuid=_uuid_of(node),
        label=f"Zone {title}{on}",
        x_mm=x_mm,
        y_mm=y_mm,
        bbox_mm=bbox,
        fields=fields,
    )


def _fallback_key(kind: str, item: dict[str, Any]) -> tuple[Any, ...]:
    return (item["item_type"], _identity_text(kind, item), _full_geometry(item))


def _item_distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    ax, ay = left.get("x_mm"), left.get("y_mm")
    bx, by = right.get("x_mm"), right.get("y_mm")
    if None in (ax, ay, bx, by):
        return float("inf")
    return (ax - bx) ** 2 + (ay - by) ** 2


def _pair_nearest(
    unmatched_base: list[dict[str, Any]],
    unmatched_cand: list[dict[str, Any]],
    kind: str,
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    leftover_base: list[dict[str, Any]] = []
    leftover_cand: list[dict[str, Any]] = []
    groups_base = _index_by(
        unmatched_base,
        lambda item: (item["item_type"], _identity_text(kind, item)),
    )
    groups_cand = _index_by(
        unmatched_cand,
        lambda item: (item["item_type"], _identity_text(kind, item)),
    )
    keys = set(groups_base) | set(groups_cand)
    for key in keys:
        _item_type, identity = key
        bases = list(groups_base.get(key, []))
        cands = list(groups_cand.get(key, []))
        if not identity:
            leftover_base.extend(bases)
            leftover_cand.extend(cands)
            continue
        while bases and cands:
            best_i = best_j = 0
            best = float("inf")
            for i, base_item in enumerate(bases):
                for j, cand_item in enumerate(cands):
                    dist = _item_distance(base_item, cand_item)
                    if dist < best:
                        best = dist
                        best_i, best_j = i, j
            pairs.append((bases.pop(best_i), cands.pop(best_j)))
        leftover_base.extend(bases)
        leftover_cand.extend(cands)
    return pairs, leftover_base, leftover_cand


def _index_by(items, key_fn) -> dict[Any, list[dict[str, Any]]]:
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(key_fn(item), []).append(item)
    return grouped


def _pair_groups(
    base_groups: dict[Any, list[dict[str, Any]]],
    candidate_groups: dict[Any, list[dict[str, Any]]],
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    leftover_base: list[dict[str, Any]] = []
    leftover_candidate: list[dict[str, Any]] = []
    keys = set(base_groups) | set(candidate_groups)
    for key in keys:
        bases = list(base_groups.get(key, []))
        cands = list(candidate_groups.get(key, []))
        while bases and cands:
            pairs.append((bases.pop(0), cands.pop(0)))
        leftover_base.extend(bases)
        leftover_candidate.extend(cands)
    return pairs, leftover_base, leftover_candidate


def _diff_items(
    kind: str,
    base_items: list[dict[str, Any]],
    candidate_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    # Pass 1: match by uuid/tstamp when both sides still carry that identity.
    uuid_pairs, unmatched_base, unmatched_cand = _pair_groups(
        _index_by((item for item in base_items if item.get("uuid")), lambda item: item.get("uuid")),
        _index_by((item for item in candidate_items if item.get("uuid")), lambda item: item.get("uuid")),
    )
    pairs = list(uuid_pairs)
    # Items that never had a uuid, or whose uuid exists on only one side, stay
    # unmatched and are rematched below by fallback identity.
    unmatched_base.extend(item for item in base_items if not item.get("uuid"))
    unmatched_cand.extend(item for item in candidate_items if not item.get("uuid"))

    # Pass 2: leftover items from both sides, including uuid-stripped KiCad 6/8 pairs.
    fallback_pairs, unmatched_base, unmatched_cand = _pair_groups(
        _index_by(unmatched_base, lambda item: _fallback_key(kind, item)),
        _index_by(unmatched_cand, lambda item: _fallback_key(kind, item)),
    )
    pairs.extend(fallback_pairs)
    nearest_pairs, unmatched_base, unmatched_cand = _pair_nearest(
        unmatched_base, unmatched_cand, kind
    )
    pairs.extend(nearest_pairs)

    changes: list[dict[str, Any]] = []
    unchanged = 0
    for base_item, cand_item in pairs:
        details = _field_details(base_item, cand_item)
        if details:
            changes.append(_change_row("changed", cand_item, base_item, cand_item, details))
        else:
            unchanged += 1
    for item in unmatched_base:
        changes.append(_change_row("removed", item, item, None, _presence_details("removed", item)))
    for item in unmatched_cand:
        changes.append(_change_row("added", item, None, item, _presence_details("added", item)))
    return changes, unchanged


def _field_details(base_item: dict[str, Any], cand_item: dict[str, Any]) -> list[str]:
    details: list[str] = []
    if base_item.get("ref") != cand_item.get("ref"):
        details.append(f"reference {base_item.get('ref')} -> {cand_item.get('ref')}")
    base_x, base_y = base_item.get("x_mm"), base_item.get("y_mm")
    cand_x, cand_y = cand_item.get("x_mm"), cand_item.get("y_mm")
    point_item = base_item["item_type"] in {
        "symbol",
        "footprint",
        "label",
        "global_label",
        "hierarchical_label",
        "junction",
        "no_connect",
        "via",
        "sheet",
    }
    if point_item and (base_x, base_y) != (cand_x, cand_y) and None not in (base_x, base_y, cand_x, cand_y):
        details.append(f"moved from {_fmt_xy(base_x, base_y)} to {_fmt_xy(cand_x, cand_y)}")

    base_fields = base_item["fields"]
    cand_fields = cand_item["fields"]
    names = sorted(set(base_fields) | set(cand_fields), key=lambda name: (name.startswith("property:"), name))
    endpoint_keys = {"x1", "y1", "x2", "y2"}
    skip_generic = set(endpoint_keys) | {"outline", "points", "layers"}
    base_pts = _as_points(base_fields.get("points") or base_fields.get("outline"))
    cand_pts = _as_points(cand_fields.get("points") or cand_fields.get("outline"))
    vertex_details = False
    if base_pts and cand_pts and len(base_pts) == len(cand_pts) and base_pts != cand_pts:
        for index, (old_pt, new_pt) in enumerate(zip(base_pts, cand_pts), start=1):
            if old_pt != new_pt:
                details.append(f"vertex {index} moved from {_fmt_xy(*old_pt)} to {_fmt_xy(*new_pt)}")
                vertex_details = True
    elif (base_pts or cand_pts) and base_pts != cand_pts and not point_item:
        details.append(
            "endpoints "
            f"{_fmt_xy(base_fields.get('x1', 0.0), base_fields.get('y1', 0.0))}"
            f"-{_fmt_xy(base_fields.get('x2', 0.0), base_fields.get('y2', 0.0))}"
            " -> "
            f"{_fmt_xy(cand_fields.get('x1', 0.0), cand_fields.get('y1', 0.0))}"
            f"-{_fmt_xy(cand_fields.get('x2', 0.0), cand_fields.get('y2', 0.0))}"
        )
    if base_item["item_type"] == "zone" and base_fields.get("outline") != cand_fields.get("outline"):
        bbox = cand_item.get("bbox_mm") or {}
        if bbox:
            details.append(
                "outline changed "
                f"{_fmt_xy(bbox['min_x'], bbox['min_y'])}-{_fmt_xy(bbox['max_x'], bbox['max_y'])}"
            )
        else:
            details.append("outline changed")
    elif (
        not vertex_details
        and not point_item
        and any(base_fields.get(key) != cand_fields.get(key) for key in endpoint_keys)
        and not (base_pts or cand_pts)
    ):
        details.append(
            "endpoints "
            f"{_fmt_xy(base_fields.get('x1', 0.0), base_fields.get('y1', 0.0))}"
            f"-{_fmt_xy(base_fields.get('x2', 0.0), base_fields.get('y2', 0.0))}"
            " -> "
            f"{_fmt_xy(cand_fields.get('x1', 0.0), cand_fields.get('y1', 0.0))}"
            f"-{_fmt_xy(cand_fields.get('x2', 0.0), cand_fields.get('y2', 0.0))}"
        )
    for name in names:
        if name in skip_generic:
            continue
        old = base_fields.get(name)
        new = cand_fields.get(name)
        if old == new:
            continue
        if name.startswith("property:"):
            details.append(f"property {name.split(':', 1)[1]} {old} -> {new}")
        elif isinstance(old, bool) or isinstance(new, bool):
            details.append(f"{name} {_fmt_flag(old)} -> {_fmt_flag(new)}")
        else:
            details.append(f"{name} {old} -> {new}")
    return details


def _presence_details(change: str, item: dict[str, Any]) -> list[str]:
    x_mm, y_mm = item.get("x_mm"), item.get("y_mm")
    if x_mm is None or y_mm is None:
        points = _as_points(item["fields"].get("points") or item["fields"].get("outline"))
        if points:
            x_mm, y_mm = points[0]
    if x_mm is None or y_mm is None:
        return [item.get("label") or item["item_type"]]
    if change == "removed":
        return [f"was at {_fmt_xy(x_mm, y_mm)}"]
    return [f"at {_fmt_xy(x_mm, y_mm)}"]


def _public_side(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    body = {
        "item_type": item["item_type"],
        "ref": item["ref"],
        "uuid": item["uuid"],
        "label": item["label"],
        "x_mm": item["x_mm"],
        "y_mm": item["y_mm"],
        "bbox_mm": item["bbox_mm"],
    }
    body.update(item["fields"])
    return body


def _change_row(
    change: str,
    identity: dict[str, Any],
    base_item: dict[str, Any] | None,
    cand_item: dict[str, Any] | None,
    details: list[str],
) -> dict[str, Any]:
    x_mm = identity.get("x_mm")
    y_mm = identity.get("y_mm")
    position = {"x_mm": x_mm, "y_mm": y_mm} if x_mm is not None and y_mm is not None else None
    return {
        "change": change,
        "item_type": identity["item_type"],
        "ref": identity["ref"],
        "uuid": identity["uuid"],
        "label": identity["label"],
        "base": _public_side(base_item),
        "candidate": _public_side(cand_item),
        "position": position,
        "bbox_mm": identity.get("bbox_mm"),
        "details": details,
    }


def _change_sort_key(change: dict[str, Any]) -> tuple[Any, ...]:
    position = change.get("position") or {}
    return (
        _TYPE_ORDER.get(change["item_type"], 999),
        change.get("ref") or "",
        position.get("x_mm") if position.get("x_mm") is not None else float("inf"),
        position.get("y_mm") if position.get("y_mm") is not None else float("inf"),
        change.get("uuid") or "",
        change["change"],
    )
