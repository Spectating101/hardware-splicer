"""Pure, span-preserving KiCad schematic/PCB edit operations.

This engine only transforms text into a candidate. It never writes files, never
touches a project, and never promotes an engineering claim. Authority is never
implicitly upgraded. Every edit is intended to flow through diff and staged
review afterwards.
"""

from __future__ import annotations

import math
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .kicad_diff import KicadDiffError, parse_kicad_sexp, tokenize_kicad_sexp_spans

MAX_OPS = 200
MAX_BYTES = 16 * 1024 * 1024
MAX_ABS_MM = 1e5
MAX_TRACK_WIDTH_MM = 10.0
_UUID_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
_AUTHORITY_KEYS = frozenset({"authorized", "release", "power_on"})
_AT_FLAGS = frozenset({"unlocked", "locked"})
_SCH_FLAGS = frozenset({"dnp", "in_bom", "on_board", "exclude_from_sim"})
_SCH_ROTATIONS = frozenset({0, 90, 180, 270})
_LABEL_KINDS = {"local": "label", "global": "global_label"}
_LABEL_SHAPES = frozenset({"input", "output", "bidirectional", "tri_state", "passive"})
_BARE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_SCH_DELETE = frozenset(
    {"wire", "bus", "junction", "no_connect", "label", "global_label", "hierarchical_label", "symbol"}
)
_PCB_DELETE = frozenset({"segment", "via", "footprint"})
_SCH_OPS: dict[str, frozenset[str]] = {
    "set_property": frozenset({"op", "uuid", "ref", "name", "value"}),
    "move": frozenset({"op", "uuid", "ref", "x_mm", "y_mm"}),
    "rotate": frozenset({"op", "uuid", "ref", "degrees"}),
    "set_flag": frozenset({"op", "uuid", "ref", "flag", "value"}),
    "add_label": frozenset({"op", "text", "x_mm", "y_mm", "label_kind", "angle", "shape", "uuid_seed"}),
    "delete": frozenset({"op", "uuid", "ref"}),
}
_PCB_OPS: dict[str, frozenset[str]] = {
    "move": frozenset({"op", "uuid", "ref", "x_mm", "y_mm"}),
    "rotate": frozenset({"op", "uuid", "ref", "degrees"}),
    "set_track_width": frozenset({"op", "uuid", "width_mm"}),
    "set_property": frozenset({"op", "uuid", "ref", "name", "value"}),
    "delete": frozenset({"op", "uuid", "ref", "confirm"}),
}


class KicadEditError(ValueError):
    """Invalid edit request or malformed KiCad text. Message is short on purpose."""


@dataclass(frozen=True, slots=True)
class _Node:
    start: int
    end: int
    atom: str | None
    children: tuple["_Node", ...]

    def head(self) -> str | None:
        if self.atom is not None or not self.children:
            return None
        return self.children[0].atom


def apply_edit_ops(kind: str, text: str, ops: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Apply edit operations by splicing source spans. Pure: no I/O."""

    if kind not in {"schematic", "pcb"}:
        raise KicadEditError("kind must be schematic or pcb")
    if not isinstance(text, str):
        raise KicadEditError("text must be a string")
    if _utf8_size(text) > MAX_BYTES:
        raise KicadEditError("input exceeds size limit")
    if isinstance(ops, (str, bytes)) or not isinstance(ops, Sequence):
        raise KicadEditError("ops must be a sequence")
    if len(ops) > MAX_OPS:
        raise KicadEditError("too many ops")
    _root_for(kind, text)

    current = text
    applied: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, raw in enumerate(ops):
        if not isinstance(raw, Mapping):
            raise KicadEditError(f"op {index} is not a mapping")
        current, record = _apply_one(kind, current, index, dict(raw))
        applied.append(record)
        _assert_balanced(current, index)
        if _utf8_size(current) > MAX_BYTES:
            raise KicadEditError(f"op {index} exceeded size limit")
    return {"text": current, "applied": applied, "warnings": warnings}


def _utf8_size(text: str) -> int:
    return len(text.encode("utf-8"))


def _assert_balanced(text: str, index: int) -> None:
    try:
        parse_kicad_sexp(text)
    except KicadDiffError:
        raise KicadEditError(f"op {index} produced unbalanced s-expression") from None


def _parse_tree(text: str) -> _Node:
    try:
        tokens = tokenize_kicad_sexp_spans(text)
    except KicadDiffError:
        raise KicadEditError("malformed s-expression") from None
    if not tokens:
        raise KicadEditError("malformed s-expression")
    stack: list[tuple[int, list[_Node]]] = []
    root: _Node | None = None
    for value, start, end in tokens:
        is_paren = end == start + 1 and value in "()" and text[start] == value
        if is_paren and value == "(":
            if not stack and root is not None:
                raise KicadEditError("malformed s-expression")
            stack.append((start, []))
            continue
        if is_paren and value == ")":
            if not stack:
                raise KicadEditError("unbalanced parentheses")
            node_start, children = stack.pop()
            node = _Node(node_start, end, None, tuple(children))
            if stack:
                stack[-1][1].append(node)
            elif root is not None:
                raise KicadEditError("malformed s-expression")
            else:
                root = node
            continue
        if not stack:
            raise KicadEditError("malformed s-expression")
        stack[-1][1].append(_Node(start, end, value, ()))
    if stack or root is None:
        raise KicadEditError("unbalanced parentheses")
    return root


def _root_for(kind: str, text: str) -> _Node:
    root = _parse_tree(text)
    expected = "kicad_sch" if kind == "schematic" else "kicad_pcb"
    if root.head() != expected:
        raise KicadEditError(f"not a KiCad {kind}")
    return root


def _apply_one(kind: str, text: str, index: int, op: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    table = _SCH_OPS if kind == "schematic" else _PCB_OPS
    name = op.get("op")
    if not isinstance(name, str) or name not in table:
        raise KicadEditError("unknown op")
    _reject_keys(op, table[name])
    if name == "add_label":
        return _op_add_label(text, index, op)
    if name == "set_property":
        return _op_set_property(kind, text, index, op)
    if name == "move":
        return _op_move(kind, text, index, op)
    if name == "rotate":
        return _op_rotate(kind, text, index, op)
    if name == "set_flag":
        return _op_set_flag(text, index, op)
    if name == "set_track_width":
        return _op_set_track_width(text, index, op)
    return _op_delete(kind, text, index, op)


def _reject_keys(op: Mapping[str, Any], allowed: frozenset[str]) -> None:
    keys = [key for key in op if not isinstance(key, str)]
    if keys:
        raise KicadEditError("unexpected field")
    present = set(op)
    if present & _AUTHORITY_KEYS:
        raise KicadEditError("authority field not allowed")
    extra = present - allowed
    if extra:
        raise KicadEditError("unexpected field")


def _record(
    index: int,
    op: str,
    node: _Node | None,
    *,
    uuid_value: str | None,
    ref: str | None,
    item_type: str,
    detail: str,
) -> dict[str, Any]:
    if node is not None:
        uuid_value = uuid_value if uuid_value is not None else _uuid_of(node)
        ref = ref if ref is not None else _ref_of(node)
        item_type = _item_type(node)
    return {
        "index": index,
        "op": op,
        "target": {"uuid": uuid_value, "ref": ref, "item_type": item_type},
        "detail": detail,
    }


def _named(node: _Node, name: str) -> _Node | None:
    for child in node.children:
        if child.atom is None and child.head() == name:
            return child
    return None


def _atom_at(node: _Node, index: int) -> str | None:
    if index < 0 or index >= len(node.children):
        return None
    return node.children[index].atom


def _uuid_of(node: _Node) -> str | None:
    for key in ("uuid", "tstamp"):
        child = _named(node, key)
        value = _atom_at(child, 1) if child is not None else None
        if value:
            return value
    return None


def _property_nodes(node: _Node) -> list[_Node]:
    return [child for child in node.children if child.head() == "property"]


def _property_name(prop: _Node) -> str | None:
    return _atom_at(prop, 1)


def _property_value_node(prop: _Node) -> _Node | None:
    if len(prop.children) >= 3 and prop.children[2].atom is not None:
        return prop.children[2]
    return None


def _ref_of(node: _Node) -> str | None:
    for prop in _property_nodes(node):
        if _property_name(prop) == "Reference":
            value = _property_value_node(prop)
            return None if value is None else value.atom
    for child in node.children:
        if child.head() != "fp_text" or _atom_at(child, 1) != "reference":
            continue
        return _atom_at(child, 2)
    return None


def _label_text(node: _Node) -> str | None:
    if _item_type(node) not in {"label", "global_label", "hierarchical_label"}:
        return None
    return _atom_at(node, 1) or None


def _ref_matches_label(root: _Node, ref: str) -> bool:
    for child in root.children[1:]:
        if child.atom is not None:
            continue
        if _label_text(child) == ref:
            return True
    return False


def _item_type(node: _Node) -> str:
    head = node.head()
    if head == "module":
        return "footprint"
    return head or "item"


def _instance_symbol(node: _Node) -> bool:
    return _item_type(node) == "symbol" and _named(node, "lib_id") is not None


def _top_items(root: _Node, kinds: frozenset[str], *, symbols_need_lib_id: bool) -> list[_Node]:
    items: list[_Node] = []
    for child in root.children[1:]:
        if child.atom is not None:
            continue
        head = _item_type(child)
        if head not in kinds:
            continue
        if head == "symbol" and symbols_need_lib_id and not _instance_symbol(child):
            continue
        items.append(child)
    return items


def _select(
    root: _Node,
    *,
    kinds: frozenset[str],
    uuid_value: str | None,
    ref: str | None,
    symbols_need_lib_id: bool,
) -> _Node:
    items = _top_items(root, kinds, symbols_need_lib_id=symbols_need_lib_id)
    if uuid_value is not None:
        matches = [item for item in items if _uuid_of(item) == uuid_value]
        if not matches:
            raise KicadEditError("unknown uuid")
        if len(matches) > 1:
            raise KicadEditError("ambiguous reference")
        return matches[0]
    if ref is None:
        raise KicadEditError("missing field")
    matches = [
        item
        for item in items
        if _item_type(item) in {"symbol", "footprint"} and _ref_of(item) == ref
    ]
    if len(matches) > 1:
        raise KicadEditError("ambiguous reference")
    if len(matches) == 1:
        return matches[0]
    if _ref_matches_label(root, ref):
        raise KicadEditError("ref addressing applies to symbols and footprints")
    raise KicadEditError("unknown reference")


def _require_id(op: Mapping[str, Any], index: int) -> tuple[str | None, str | None]:
    uuid_value = op.get("uuid")
    ref = op.get("ref")
    if uuid_value is not None and not isinstance(uuid_value, str):
        raise KicadEditError(f"op {index} has an invalid uuid")
    if ref is not None and not isinstance(ref, str):
        raise KicadEditError(f"op {index} has an invalid reference")
    if uuid_value:
        return uuid_value, None
    if ref:
        return None, ref
    raise KicadEditError("missing field")


def _coord(value: Any, index: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise KicadEditError("non-finite or out-of-range coordinate")
    number = float(value)
    if not math.isfinite(number) or abs(number) > MAX_ABS_MM:
        raise KicadEditError("non-finite or out-of-range coordinate")
    return number


def _fmt_mm(value: float) -> str:
    if not math.isfinite(value) or abs(value) > MAX_ABS_MM:
        raise KicadEditError("non-finite or out-of-range coordinate")
    text = format(value, ".6f").rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    if "e" in text.lower() or "E" in text:
        text = format(value, ".6f").rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _fmt_pos(value: float) -> str:
    return _fmt_mm(round(float(value), 4))


def _quote(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _indent_of(text: str, pos: int) -> str:
    line_start = text.rfind("\n", 0, pos) + 1
    index = line_start
    while index < pos and text[index] in " \t":
        index += 1
    return text[line_start:index]


def _deeper(indent: str) -> str:
    if "\t" in indent:
        return indent + "\t"
    if indent.endswith("  "):
        return indent + "  "
    if indent.endswith(" "):
        return indent + " "
    return indent + "\t"


def _top_indent(root: _Node, text: str) -> str:
    for child in root.children[1:]:
        if child.atom is not None:
            continue
        if "\n" in text[root.start : child.start]:
            indent = _indent_of(text, child.start)
            if indent:
                return indent
    return "\t"


def _splice(text: str, replacements: Sequence[tuple[int, int, str]]) -> str:
    if not replacements:
        return text
    ordered = sorted(replacements, key=lambda item: (item[0], item[1]))
    last = 0
    parts: list[str] = []
    for start, end, new in ordered:
        if start < last or end < start:
            raise KicadEditError("overlapping edits")
        parts.append(text[last:start])
        parts.append(new)
        last = end
    parts.append(text[last:])
    return "".join(parts)


def _at_number_nodes(at: _Node) -> list[_Node]:
    numbers: list[_Node] = []
    for child in at.children[1:]:
        if child.atom is None or child.atom in _AT_FLAGS:
            continue
        numbers.append(child)
    return numbers


def _parse_atom_float(atom: str) -> float:
    try:
        return float(atom)
    except ValueError:
        raise KicadEditError("malformed coordinate") from None


def _replace_xy(at: _Node, x_mm: float, y_mm: float) -> list[tuple[int, int, str]]:
    numbers = _at_number_nodes(at)
    if len(numbers) < 2:
        raise KicadEditError("missing at coordinates")
    return [
        (numbers[0].start, numbers[0].end, _fmt_mm(x_mm)),
        (numbers[1].start, numbers[1].end, _fmt_mm(y_mm)),
    ]


def _shift_xy(at: _Node, dx: float, dy: float) -> list[tuple[int, int, str]]:
    numbers = _at_number_nodes(at)
    if len(numbers) < 2:
        return []
    x_mm = _parse_atom_float(numbers[0].atom or "0") + dx
    y_mm = _parse_atom_float(numbers[1].atom or "0") + dy
    return _replace_xy(at, x_mm, y_mm)


def _require_bare_token(value: Any) -> str:
    if not isinstance(value, str) or _BARE_TOKEN_RE.fullmatch(value) is None:
        raise KicadEditError("invalid token")
    return value


def _first_at_flag(at: _Node) -> _Node | None:
    for child in at.children[1:]:
        if child.atom in _AT_FLAGS:
            return child
    return None


def _insert_angle_replacement(at: _Node, formatted: str) -> tuple[int, int, str]:
    flag = _first_at_flag(at)
    if flag is not None:
        return flag.start, flag.start, f"{formatted} "
    return at.end - 1, at.end - 1, f" {formatted}"


def _set_angle(text: str, at: _Node, degrees: float) -> str:
    numbers = _at_number_nodes(at)
    formatted = _fmt_mm(degrees)
    if len(numbers) >= 3:
        if numbers[2].atom == formatted:
            return text
        return _splice(text, [(numbers[2].start, numbers[2].end, formatted)])
    if abs(degrees) <= 1e-12:
        return text
    return _splice(text, [_insert_angle_replacement(at, formatted)])


def _norm_deg(value: float) -> float:
    wrapped = value % 360.0
    if wrapped < 0:
        wrapped += 360.0
    if wrapped == 0.0 or abs(wrapped - 360.0) <= 1e-12:
        return 0.0
    return wrapped


def _angle_delta_replacements(at: _Node, delta: float) -> list[tuple[int, int, str]]:
    numbers = _at_number_nodes(at)
    had_angle = len(numbers) >= 3
    old = _parse_atom_float(numbers[2].atom or "0") if had_angle else 0.0
    new = _norm_deg(old + delta)
    if not had_angle:
        if new == 0.0:
            return []
        return [_insert_angle_replacement(at, _fmt_mm(new))]
    formatted = _fmt_mm(new)
    if numbers[2].atom == formatted:
        return []
    return [(numbers[2].start, numbers[2].end, formatted)]


def _rotate_sch_point(dx: float, dy: float, degrees: float) -> tuple[float, float]:
    """Rotate a schematic-relative point about the symbol origin.

    KiCad schematic Y is down. +90 maps (dx, dy) -> (dy, -dx), matching
    KiCad's CCW screen rotation. (mirror x|y) is a sibling of (at) and is
    left untouched so rotate/mirror order stays KiCad's.
    """

    rad = math.radians(degrees)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    x_mm = dx * cos_a + dy * sin_a
    y_mm = -dx * sin_a + dy * cos_a
    return round(x_mm, 4), round(y_mm, 4)


def _pcb_rotate_ats(footprint: _Node) -> list[_Node]:
    ats: list[_Node] = []
    at = _named(footprint, "at")
    if at is not None:
        ats.append(at)
    for child in footprint.children:
        if child.head() not in {"pad", "property", "fp_text"}:
            continue
        child_at = _named(child, "at")
        if child_at is not None:
            ats.append(child_at)
    return ats


def _delete_node(text: str, node: _Node) -> str:
    start, end = node.start, node.end
    if text[end : end + 2] == "\r\n":
        end += 2
    elif text[end : end + 1] == "\n":
        end += 1
    line_start = text.rfind("\n", 0, start) + 1
    if text[line_start:start].strip() == "":
        start = line_start
    return text[:start] + text[end:]


def _op_set_property(
    kind: str, text: str, index: int, op: Mapping[str, Any]
) -> tuple[str, dict[str, Any]]:
    uuid_value, ref = _require_id(op, index)
    name = op.get("name")
    value = op.get("value")
    if not isinstance(name, str) or not isinstance(value, str):
        raise KicadEditError("missing field")
    if kind == "pcb" and name == "Reference":
        raise KicadEditError("cannot change Reference")
    root = _root_for(kind, text)
    kinds = frozenset({"symbol"}) if kind == "schematic" else frozenset({"footprint"})
    node = _select(
        root,
        kinds=kinds,
        uuid_value=uuid_value,
        ref=ref,
        symbols_need_lib_id=kind == "schematic",
    )
    for prop in _property_nodes(node):
        if _property_name(prop) != name:
            continue
        value_node = _property_value_node(prop)
        if value_node is None:
            raise KicadEditError("malformed property")
        if value_node.atom == value:
            edited = text
        else:
            edited = _splice(text, [(value_node.start, value_node.end, _quote(value))])
        return edited, _record(
            index,
            "set_property",
            node,
            uuid_value=uuid_value,
            ref=ref,
            item_type=_item_type(node),
            detail=f"set {name} to {value}",
        )
    edited = _insert_property(text, node, name, value, schematic=kind == "schematic")
    return edited, _record(
        index,
        "set_property",
        node,
        uuid_value=uuid_value,
        ref=ref,
        item_type=_item_type(node),
        detail=f"set {name} to {value}",
    )


def _insert_property(text: str, parent: _Node, name: str, value: str, *, schematic: bool) -> str:
    template = None
    last_prop = None
    for prop in _property_nodes(parent):
        last_prop = prop
        if _property_name(prop) == "Value":
            template = prop
    if template is None or last_prop is None:
        raise KicadEditError("no Value property to copy")
    if len(template.children) < 3:
        raise KicadEditError("malformed property")
    replacements = [
        (template.children[1].start - template.start, template.children[1].end - template.start, _quote(name)),
        (template.children[2].start - template.start, template.children[2].end - template.start, _quote(value)),
    ]
    uid_node = _named(template, "uuid")
    if uid_node is not None and len(uid_node.children) >= 2 and uid_node.children[1].atom is not None:
        new_uid = str(
            uuid.uuid5(_UUID_NS, f"kicad-edit-property:{_ref_of(parent) or ''}:{name}:{value}")
        )
        replacements.append(
            (
                uid_node.children[1].start - template.start,
                uid_node.children[1].end - template.start,
                _quote(new_uid),
            )
        )
    cloned = _splice(text[template.start : template.end], replacements)
    cloned_tree = _parse_tree(cloned)
    if schematic:
        cloned = _ensure_effects_hide(cloned, cloned_tree)
    else:
        cloned = _ensure_property_hide(cloned, cloned_tree)
    indent = _indent_of(text, template.start)
    nl = _newline(text)
    return text[: last_prop.end] + nl + indent + cloned + text[last_prop.end :]


def _ensure_effects_hide(text: str, prop: _Node) -> str:
    effects = _named(prop, "effects")
    if effects is None:
        return _ensure_property_hide(text, prop)
    if _named(effects, "hide") is not None:
        return text
    indent = _indent_of(text, effects.start)
    inner = _deeper(indent)
    nl = _newline(text)
    insert_at = effects.end - 1
    return text[:insert_at] + f"{nl}{inner}(hide yes){nl}{indent}" + text[insert_at:]


def _ensure_property_hide(text: str, prop: _Node) -> str:
    if _named(prop, "hide") is not None:
        return text
    indent = _indent_of(text, prop.start)
    inner = _deeper(indent)
    nl = _newline(text)
    insert_at = prop.end - 1
    return text[:insert_at] + f"{nl}{inner}(hide yes){nl}{indent}" + text[insert_at:]


def _op_move(kind: str, text: str, index: int, op: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    uuid_value, ref = _require_id(op, index)
    x_mm = _coord(op.get("x_mm"), index)
    y_mm = _coord(op.get("y_mm"), index)
    root = _root_for(kind, text)
    if kind == "schematic":
        kinds = frozenset({"symbol", "label", "global_label", "hierarchical_label"})
    else:
        kinds = frozenset({"footprint", "via"})
    node = _select(
        root,
        kinds=kinds,
        uuid_value=uuid_value,
        ref=ref,
        symbols_need_lib_id=kind == "schematic",
    )
    at = _named(node, "at")
    if at is None:
        raise KicadEditError("missing at coordinates")
    numbers = _at_number_nodes(at)
    if len(numbers) < 2:
        raise KicadEditError("missing at coordinates")
    old_x = _parse_atom_float(numbers[0].atom or "0")
    old_y = _parse_atom_float(numbers[1].atom or "0")
    replacements = _replace_xy(at, x_mm, y_mm)
    if kind == "schematic" and _item_type(node) == "symbol":
        dx = x_mm - old_x
        dy = y_mm - old_y
        if dx or dy:
            for prop in _property_nodes(node):
                prop_at = _named(prop, "at")
                if prop_at is not None:
                    replacements.extend(_shift_xy(prop_at, dx, dy))
    edited = _splice(text, replacements)
    return edited, _record(
        index,
        "move",
        node,
        uuid_value=uuid_value,
        ref=ref,
        item_type=_item_type(node),
        detail=f"moved to ({_fmt_mm(x_mm)},{_fmt_mm(y_mm)})",
    )


def _op_rotate(kind: str, text: str, index: int, op: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    uuid_value, ref = _require_id(op, index)
    degrees = _coord(op.get("degrees"), index)
    if kind == "schematic":
        if int(degrees) != degrees or int(degrees) not in _SCH_ROTATIONS:
            raise KicadEditError("invalid rotation")
        degrees = float(int(degrees))
        kinds = frozenset({"symbol"})
    else:
        kinds = frozenset({"footprint"})
    root = _root_for(kind, text)
    node = _select(
        root,
        kinds=kinds,
        uuid_value=uuid_value,
        ref=ref,
        symbols_need_lib_id=kind == "schematic",
    )
    at = _named(node, "at")
    if at is None:
        raise KicadEditError("missing at coordinates")
    replacements: list[tuple[int, int, str]] = []
    if kind == "schematic":
        numbers = _at_number_nodes(at)
        if len(numbers) < 2:
            raise KicadEditError("missing at coordinates")
        origin_x = _parse_atom_float(numbers[0].atom or "0")
        origin_y = _parse_atom_float(numbers[1].atom or "0")
        replacements.extend(_angle_delta_replacements(at, degrees))
        for prop in _property_nodes(node):
            prop_at = _named(prop, "at")
            if prop_at is None:
                continue
            prop_nums = _at_number_nodes(prop_at)
            if len(prop_nums) < 2:
                continue
            dx = _parse_atom_float(prop_nums[0].atom or "0") - origin_x
            dy = _parse_atom_float(prop_nums[1].atom or "0") - origin_y
            rel_x, rel_y = _rotate_sch_point(dx, dy, degrees)
            replacements.extend(
                [
                    (prop_nums[0].start, prop_nums[0].end, _fmt_pos(origin_x + rel_x)),
                    (prop_nums[1].start, prop_nums[1].end, _fmt_pos(origin_y + rel_y)),
                ]
            )
            replacements.extend(_angle_delta_replacements(prop_at, degrees))
    else:
        for target_at in _pcb_rotate_ats(node):
            replacements.extend(_angle_delta_replacements(target_at, degrees))
    edited = _splice(text, replacements)
    return edited, _record(
        index,
        "rotate",
        node,
        uuid_value=uuid_value,
        ref=ref,
        item_type=_item_type(node),
        detail=f"rotated to {_fmt_mm(degrees)}",
    )


def _op_set_flag(text: str, index: int, op: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    uuid_value, ref = _require_id(op, index)
    flag = op.get("flag")
    value = op.get("value")
    if flag not in _SCH_FLAGS:
        raise KicadEditError("invalid flag")
    if not isinstance(value, bool):
        raise KicadEditError("missing field")
    root = _root_for("schematic", text)
    node = _select(
        root,
        kinds=frozenset({"symbol"}),
        uuid_value=uuid_value,
        ref=ref,
        symbols_need_lib_id=True,
    )
    token = "yes" if value else "no"
    existing = _named(node, str(flag))
    if existing is not None:
        if len(existing.children) >= 2 and existing.children[1].atom is not None:
            if existing.children[1].atom == token:
                edited = text
            else:
                edited = _splice(
                    text, [(existing.children[1].start, existing.children[1].end, token)]
                )
        elif value:
            edited = text
        else:
            edited = _splice(text, [(existing.end - 1, existing.end - 1, f" {token}")])
    else:
        edited = _insert_flag(text, node, str(flag), token)
    return edited, _record(
        index,
        "set_flag",
        node,
        uuid_value=uuid_value,
        ref=ref,
        item_type="symbol",
        detail=f"set {flag} to {token}",
    )


def _insert_flag(text: str, node: _Node, flag: str, token: str) -> str:
    anchors = ("dnp", "on_board", "in_bom", "exclude_from_sim", "unit", "at")
    anchor = None
    for name in anchors:
        child = _named(node, name)
        if child is not None:
            anchor = child
            break
    indent = _indent_of(text, (anchor or node).start if anchor else node.children[0].start)
    if anchor is None:
        indent = _deeper(_indent_of(text, node.start))
        insert_at = node.end - 1
    else:
        indent = _indent_of(text, anchor.start)
        insert_at = anchor.end
    nl = _newline(text)
    return text[:insert_at] + f"{nl}{indent}({flag} {token})" + text[insert_at:]


def _op_set_track_width(text: str, index: int, op: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    uuid_value = op.get("uuid")
    if not isinstance(uuid_value, str) or not uuid_value:
        raise KicadEditError("missing field")
    width = _coord(op.get("width_mm"), index)
    if width <= 0 or width > MAX_TRACK_WIDTH_MM:
        raise KicadEditError("invalid width")
    root = _root_for("pcb", text)
    node = _select(
        root,
        kinds=frozenset({"segment"}),
        uuid_value=uuid_value,
        ref=None,
        symbols_need_lib_id=False,
    )
    width_node = _named(node, "width")
    if width_node is None or len(width_node.children) < 2 or width_node.children[1].atom is None:
        raise KicadEditError("missing width")
    formatted = _fmt_mm(width)
    if width_node.children[1].atom == formatted:
        edited = text
    else:
        edited = _splice(
            text, [(width_node.children[1].start, width_node.children[1].end, formatted)]
        )
    return edited, _record(
        index,
        "set_track_width",
        node,
        uuid_value=uuid_value,
        ref=None,
        item_type="segment",
        detail=f"set width to {formatted}",
    )


def _op_add_label(text: str, index: int, op: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    label_text = op.get("text")
    label_kind = op.get("label_kind")
    seed = op.get("uuid_seed")
    if not isinstance(label_text, str) or not isinstance(seed, str):
        raise KicadEditError("missing field")
    if label_kind not in _LABEL_KINDS:
        raise KicadEditError("invalid label_kind")
    if label_kind != "global" and "shape" in op:
        raise KicadEditError("unexpected field")
    x_mm = _coord(op.get("x_mm"), index)
    y_mm = _coord(op.get("y_mm"), index)
    angle = _coord(op.get("angle"), index) if "angle" in op else 0.0
    shape = op.get("shape", "input")
    if label_kind == "global":
        shape = _require_bare_token(shape)
        if shape not in _LABEL_SHAPES:
            raise KicadEditError("invalid shape")
    root = _root_for("schematic", text)
    uid = str(uuid.uuid5(_UUID_NS, f"{seed}+{label_text}+{_fmt_mm(x_mm)}+{_fmt_mm(y_mm)}"))
    nl = _newline(text)
    indent = _top_indent(root, text)
    deeper = _deeper(indent)
    head = _LABEL_KINDS[label_kind]
    lines = [f"{indent}({head} {_quote(label_text)}"]
    if label_kind == "global":
        lines.append(f"{deeper}(shape {shape})")
    lines.append(f"{deeper}(at {_fmt_mm(x_mm)} {_fmt_mm(y_mm)} {_fmt_mm(angle)})")
    lines.append(f"{deeper}(uuid {_quote(uid)})")
    lines.append(f"{indent})")
    block = nl.join(lines)
    close = root.end - 1
    if nl and text[close - len(nl) : close] == nl:
        insert = block + nl
    else:
        insert = nl + block + nl
    edited = text[:close] + insert + text[close:]
    return edited, _record(
        index,
        "add_label",
        None,
        uuid_value=uid,
        ref=None,
        item_type=head,
        detail=f"added {head} {label_text}",
    )


def _op_delete(kind: str, text: str, index: int, op: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    uuid_value, ref = _require_id(op, index)
    allowed = _SCH_DELETE if kind == "schematic" else _PCB_DELETE
    root = _root_for(kind, text)
    node = _select(
        root,
        kinds=allowed,
        uuid_value=uuid_value,
        ref=ref,
        symbols_need_lib_id=kind == "schematic",
    )
    item_type = _item_type(node)
    if kind == "pcb" and item_type == "footprint":
        if op.get("confirm") is not True:
            raise KicadEditError("footprint delete requires confirm")
    elif "confirm" in op:
        raise KicadEditError("unexpected field")
    edited = _delete_node(text, node)
    return edited, _record(
        index,
        "delete",
        node,
        uuid_value=uuid_value,
        ref=ref,
        item_type=item_type,
        detail=f"deleted {item_type}",
    )
