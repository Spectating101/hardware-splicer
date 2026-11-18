"""Build Fielddeck part selections from the delivered meshes and source records."""

from __future__ import annotations

import hashlib
import io
import itertools
import json
from pathlib import Path
import re
import struct
import zipfile

_BASE = "digital_v1"
_SWAP = "display_swap"
_GLB7 = f"{_BASE}/cad/FIELDDECK_7.glb"
_GLB5 = "FIELDDECK_5.glb"
_REPORT = f"{_BASE}/cad/geometry_report.json"
_STATUS = "docs/status/generated/fielddeck-display-swap-20261118.json"
_DISPLAY7 = "touch_display_2_manufacturer"
_DISPLAY5 = "touch_display_2_5inch_sc1975"
_BASIS = {
    "custom": "custom", "manufacturer_step": "vendor_step", "vendor_step": "vendor_step",
    "purchased_envelope": "envelope", "envelope": "envelope", "proxy": "proxy",
}
_COMPONENT_BYTES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
_STATES = {"vendor": "datasheet", "assumption": "assumed", "cad": "computed"}
_DIFF_STATES = ("unchanged", "changed", "added", "removed")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _archive_member(archive, name):
    paths = sorted(archive.namelist())
    for path in paths:
        if Path(path).name == name:
            prefix = Path(path).parent
            if prefix.name == "cad":
                prefix = prefix.parent
            siblings = {}
            for filename in ("geometry.json", "BOM.json"):
                member = (prefix / filename).as_posix()
                if member in paths:
                    siblings[filename] = (archive.read(member), member)
            return (archive.read(path), path), siblings
    for path in paths:
        if path.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(archive.read(path))) as nested:
                    found = _archive_member(nested, name)
            except zipfile.BadZipFile:
                continue
            if found:
                (data, member), siblings = found
                return (data, f"{path}!/{member}"), {
                    key: (value, f"{path}!/{member}") for key, (value, member) in siblings.items()
                }
    return None


def _swap_mesh(directory):
    for path in sorted(directory.rglob(_GLB5)):
        if path.is_file():
            prefix = path.parent.parent if path.parent.name == "cad" else path.parent
            siblings = {name: (record.read_bytes(), record.relative_to(directory.parent).as_posix())
                        for name in ("geometry.json", "BOM.json") if (record := prefix / name).is_file()}
            return (path.read_bytes(), path.relative_to(directory.parent).as_posix()), siblings
    for path in sorted(directory.rglob("*.zip")):
        try:
            with zipfile.ZipFile(path) as archive:
                found = _archive_member(archive, _GLB5)
        except zipfile.BadZipFile:
            continue
        if found:
            (data, member), siblings = found
            prefix = path.relative_to(directory.parent).as_posix()
            return (data, f"{prefix}!/{member}"), {
                key: (value, f"{prefix}!/{member}") for key, (value, member) in siblings.items()
            }
    return (None, None), {}


def _glb_chunks(data):
    magic, version, length = struct.unpack_from("<4sII", data)
    if (magic, version, length) != (b"glTF", 2, len(data)):
        raise ValueError("Expected a glTF 2.0 binary")
    chunks = {}
    offset = 12
    while offset < length:
        size, kind = struct.unpack_from("<I4s", data, offset)
        offset += 8
        chunks[kind] = memoryview(data)[offset:offset + size]
        offset += size
    return json.loads(bytes(chunks[b"JSON"])), chunks.get(b"BIN\0", memoryview(b""))


def _accessor(doc, binary, index):
    accessor = doc["accessors"][index]
    view = doc["bufferViews"][accessor["bufferView"]]
    # Fielddeck exports use dense, embedded position and index accessors.
    if accessor.get("sparse") or view.get("buffer", 0) != 0 or doc["buffers"][0].get("uri"):
        raise ValueError("Expected a dense accessor in the embedded GLB buffer")
    width = {"SCALAR": 1, "VEC3": 3}[accessor["type"]] * _COMPONENT_BYTES[accessor["componentType"]]
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    count = accessor["count"]
    stride = view.get("byteStride", width)
    if stride == width:
        return accessor, binary[start:start + count * width]
    return accessor, b"".join(binary[start + i * stride:start + i * stride + width] for i in range(count))


def _mesh_geometry(doc, binary, mesh):
    digest = hashlib.sha256()
    corners = []
    shape = []      # (vertex count, index count, decoded float positions) per primitive, for tolerant comparison
    for primitive in mesh["primitives"]:
        positions = indices = None
        digest.update(struct.pack("<I", primitive.get("mode", 4)))
        for index in (primitive["attributes"]["POSITION"], primitive.get("indices")):
            if index is None:
                digest.update(struct.pack("<II", 0, 0))
                continue
            accessor, values = _accessor(doc, binary, index)
            digest.update(struct.pack("<II", accessor["componentType"], accessor["count"]))
            digest.update(values)
            if accessor["type"] == "VEC3":
                lo, hi = accessor["min"], accessor["max"]
                corners.extend(itertools.product(*zip(lo, hi)))
                positions = (struct.unpack(f"<{accessor['count'] * 3}f", values)
                             if accessor["componentType"] == 5126 else None)
            else:
                code = {5121: "B", 5123: "H", 5125: "I"}[accessor["componentType"]]
                indices = struct.unpack(f"<{accessor['count']}{code}", values)
        shape.append(_triangle_signature(primitive.get("mode", 4), positions, indices))
    return digest.hexdigest(), corners, shape


def _triangle_signature(mode, positions, indices):
    """Triangulation-independent description of a triangle mesh.

    Re-exporting identical CAD can reorder vertices and split the same flat faces along a different
    diagonal, so byte, vertex-order or triangle-list comparisons report false changes. The signature
    keeps what does not depend on triangulation: the set of vertices (rounded to _VERTEX_TOLERANCE_MM),
    the total surface area and the enclosed signed volume. A mesh that is not a decodable indexed float
    triangle list yields None and always compares as changed.
    """
    if mode != 4 or positions is None or indices is None:
        return None
    step = _VERTEX_TOLERANCE_MM
    points = [positions[i:i + 3] for i in range(0, len(positions), 3)]
    vertices = frozenset(tuple(round(value / step) for value in point) for point in points)
    area = volume = 0.0
    for i in range(0, len(indices) - 2, 3):
        a, b, c = points[indices[i]], points[indices[i + 1]], points[indices[i + 2]]
        u = [b[k] - a[k] for k in range(3)]
        v = [c[k] - a[k] for k in range(3)]
        cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        area += 0.5 * (cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2) ** 0.5
        volume += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                   + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    return vertices, area, volume


def _transform(node, point):
    if "matrix" in node:
        matrix = node["matrix"]
        return tuple(sum(matrix[4 * j + i] * v for j, v in enumerate((*point, 1))) for i in range(3))
    x, y, z = (value * scale for value, scale in zip(point, node.get("scale", (1, 1, 1))))
    a, b, c, w = node.get("rotation", (0, 0, 0, 1))
    # Quaternion rotation followed by translation.
    u, v, t = 2 * (b * z - c * y), 2 * (c * x - a * z), 2 * (a * y - b * x)
    rotated = (x + w * u + b * t - c * v, y + w * v + c * u - a * t, z + w * t + a * v - b * u)
    return tuple(value + shift for value, shift in zip(rotated, node.get("translation", (0, 0, 0))))


def _bounds(points):
    axes = list(zip(*points))
    if axes:
        return [min(axis) for axis in axes] + [max(axis) for axis in axes]
    return None


def _centre(bounds):
    return [(lo + hi) / 2 for lo, hi in zip(bounds[:3], bounds[3:])]


def _nodes(data):
    if data is None:
        return {}
    doc, binary = _glb_chunks(data)
    meshes = [_mesh_geometry(doc, binary, mesh) for mesh in doc.get("meshes", [])]
    nodes = doc.get("nodes", [])
    parents = {child: i for i, node in enumerate(nodes) for child in node.get("children", [])}
    result = {}
    for i, node in enumerate(nodes):
        digest, points, shape = meshes[node["mesh"]] if "mesh" in node else (None, [], [])
        if points:
            for index in itertools.chain((i,), _ancestors(i, parents)):
                points = [_transform(nodes[index], point) for point in points]
        name = node.get("name")
        occurrence = 1
        while (name, occurrence) in result:
            occurrence += 1
        result[name, occurrence] = (i, digest, _bounds(points), node.get("extras", {}), shape)
    return result


def _ancestors(index, parents):
    while index in parents:
        index = parents[index]
        yield index


# Re-exporting identical CAD can change mesh bytes (float rounding, buffer order) without changing the part.
# Parts count as unchanged only when topology matches exactly and every vertex and the placed bounds agree
# within these tolerances (millimetres); anything else is reported as changed.
_VERTEX_TOLERANCE_MM = 1e-3
_BOUNDS_TOLERANCE_MM = 1e-2
_MEASURE_TOLERANCE = 1e-6   # relative tolerance on surface area and enclosed volume


def _same_geometry(before, after):
    old_shape, new_shape = before[4], after[4]
    if not old_shape or len(old_shape) != len(new_shape) or None in old_shape or None in new_shape:
        return False
    old_total = (frozenset().union(*(part[0] for part in old_shape)),
                 sum(part[1] for part in old_shape), sum(part[2] for part in old_shape))
    new_total = (frozenset().union(*(part[0] for part in new_shape)),
                 sum(part[1] for part in new_shape), sum(part[2] for part in new_shape))
    if old_total[0] != new_total[0]:
        return False
    for old_value, new_value in zip(old_total[1:], new_total[1:]):
        if abs(old_value - new_value) > _MEASURE_TOLERANCE * max(1.0, abs(old_value)):
            return False
    old_bounds, new_bounds = before[2], after[2]
    if old_bounds is None or new_bounds is None:
        return old_bounds == new_bounds
    return all(abs(x - y) <= _BOUNDS_TOLERANCE_MM for x, y in zip(old_bounds, new_bounds))


def _diff(base, swap, available):
    counts = dict.fromkeys(_DIFF_STATES, 0)
    rows = []
    if available:
        for name, occurrence in dict.fromkeys([*base, *swap]):
            key = name, occurrence
            before = base.get(key)
            after = swap.get(key)
            old_hash = before[1] if before else None
            new_hash = after[1] if after else None
            if before is None:
                state = "added"
            elif after is None:
                state = "removed"
            else:
                state = "unchanged" if old_hash == new_hash or _same_geometry(before, after) else "changed"
            counts[state] += 1
            rows.append({"node_name": name, "occurrence": occurrence, "status": state,
                         "from_geometry_sha256": old_hash, "to_geometry_sha256": new_hash})
    return {"from_revision": "7", "to_revision": "5",
            "status": "available" if available else "unavailable", "nodes": rows, "counts": counts}


def _part_id(name, occurrence=1):
    if name in (_DISPLAY7, _DISPLAY5):
        slug = "display"
    else:
        slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-") or "node"
    return slug if occurrence == 1 else f"{slug}-{occurrence}"


def _bom_line(name, basis, revised_ids):
    if name in revised_ids:
        return name
    if name.startswith("display_spacer_") and "display_spacer_1" in revised_ids:
        return "display_spacer_1"
    if name.startswith("pi4_"):
        return "computer"
    return {
        _DISPLAY7: "display", _DISPLAY5: "display",
        "keyboard_nominal_envelope": "keyboard", "power_bank_nominal_envelope": "bank",
        "fan_envelope": "fan",
    }.get(name, "printed_parts" if basis == "custom" else None)


def _explode(name, extras, report, revision, radial):
    for record in (extras, report):
        if "explode_vector_mm" in record:
            return record["explode_vector_mm"], False
        if "explode_m" in record:
            return [value * 1000 for value in record["explode_m"]], False
    if revision == "7":
        # Explicit offsets in digital_v1/render_device.py's exploded view.
        if name.startswith("face_") or name in {"fan_guard", "fan_envelope", "fan_duct"}:
            return [0, 0, 110], False
        if name.startswith("keyboard_") or name == _DISPLAY7:
            return [0, 0, 65], False
        if name == "power_bank_nominal_envelope":
            return [0, 0, 24], False
    return radial, True


def _evidence(field, value=None, source_class=None, source=(None, None)):
    return {"field": field, "value": value, "state": _STATES.get(source_class, "unknown"),
            "source": source[0], "source_sha256": source[1]}


def _documented_evidence(name, design, refs, swap_source):
    fields = {
        "pi4_board_envelope": ("pi", "board_mm", "pi4_mechanical.pdf"),
        "keyboard_nominal_envelope": ("keyboard", "dimensions_mm", "keyboard_stock.html"),
        "power_bank_nominal_envelope": ("power_bank", "dimensions_mm", "powerbank_stock.html"),
        "fan_envelope": ("fan", "dimensions_mm", "fan_infosheet.pdf"),
    }
    assumptions = design.get("engineering_assumptions", {})
    if name in fields:
        section, field, capture = fields[name]
        value = design.get(section, {}).get(field)
        source = refs.get(capture, {})
        if value is not None and source:
            yield _evidence(field, value, "vendor", (source["url"], source.get("capture_sha256")))
        else:
            yield _evidence(field)
    if name in {_DISPLAY7, _DISPLAY5}:
        if name == _DISPLAY5:
            brief = swap_source.get("product_brief", {})
            step = swap_source.get("vendor_step", {})
            step_hash = step.get("archive_sha256")
            for field in ("documented_power_w", "landscape_glass_mm", "landscape_viewing_area_mm",
                          "landscape_mount_pitch_mm", "nominal_lug_depth_mm"):
                if field in brief:
                    yield _evidence(field, brief[field], "vendor", (brief["url"], brief.get("sha256")))
                else:
                    yield _evidence(field)
        else:
            brief = refs.get("touch_display2_7inch_brief.pdf", {})
            step = refs.get("touch_display2_7inch.step.zip", {})
            step_hash = step.get("capture_sha256")
            value = assumptions.get("display_w", {}).get("published")
            if value is not None and brief:
                yield _evidence("documented_power_w", value, "vendor", (brief["url"], brief.get("capture_sha256")))
            else:
                yield _evidence("documented_power_w")
        if step:
            yield _evidence("geometry_reference", "vendor_step", "vendor", (step["url"], step_hash))


def _parts(nodes, report, design, references, swap_source, swap_geometry, bom, revised_ids, origins, revision):
    base_origin, mesh_origin, design_origin, swap_origin = origins
    records = {row["name"]: row for row in report.get("parts", [])}
    exports = swap_geometry.get("exports", {}).get("exported_parts", [])
    revised = {row["part"]: row for row in exports}
    spacer = revised.get("display_spacer_1", {})
    refs = {row.get("research_capture"): row for row in references.get("sources", [])}
    extents = _bounds(point for _, _, bounds, _, _ in nodes.values()
                      if bounds for point in (bounds[:3], bounds[3:]))
    centre = _centre(extents) if extents else [0, 0, 0]
    groups = {}
    for (name, _), (_, _, bounds, _, _) in nodes.items():
        if name and name.startswith("pi4_") and bounds:
            groups.setdefault("pi4", []).extend((bounds[:3], bounds[3:]))
    parts = []
    used_ids = set()
    for (node_name, occurrence), (index, digest, bounds, extras, _) in nodes.items():
        name = node_name or ""
        record = records.get(name, {})
        kind = record.get("kind") or record.get("basis") or record.get("geometry_basis")
        revised_part = revised.get(name) or (spacer if name.startswith("display_spacer_") else None)
        if revision == "5" and name == _DISPLAY5 and swap_source.get("vendor_step"):
            kind = "vendor_step"
        elif revised_part:
            kind = revised_part.get("kind") or revised_part.get("basis") or kind
        basis = _BASIS.get(kind, "unknown")
        line = _bom_line(name, basis, revised_ids)
        item = bom.get(line, {})
        part_id = _part_id(node_name, occurrence)
        while part_id in used_ids:
            part_id = f"{part_id}-{index}"
        used_ids.add(part_id)
        group = "pi4" if name.startswith("pi4_") else part_id
        group_bounds = _bounds(groups.get(group, ())) or bounds
        radial = [round(pos - mid, 6) for pos, mid in zip(_centre(group_bounds), centre)] if group_bounds else [0, 0, 0]
        vector, derived = _explode(name, extras, record, revision, radial)
        evidence = [_evidence("physical_fit")]
        if bounds:
            evidence.append(_evidence("mesh_bounds_mm", bounds, "cad", mesh_origin))
        if revised_part and "dimensions_mm" in revised_part:
            evidence.append(_evidence("print_dimensions_mm", revised_part["dimensions_mm"], "cad", swap_origin))
        elif revision == "7" and "volume_mm3" in record:
            evidence.append(_evidence("nominal_volume_mm3", record["volume_mm3"], "cad", base_origin))
        evidence.extend(_documented_evidence(name, design, refs, swap_source))
        if name in {_DISPLAY7, _DISPLAY5} and "allocated" in design.get("engineering_assumptions", {}).get("display_w", {}):
            evidence.append(_evidence("allocated_power_w", design["engineering_assumptions"]["display_w"]["allocated"],
                                      "assumption", design_origin))
        label = (record.get("label") or extras.get("label")
                 or (item.get("description") if line not in {"computer", "printed_parts"} or name == "pi4_board_envelope" else None)
                 or name.replace("_", " ").title() or f"Node {index}")
        parts.append({"node_name": node_name, "node_index": index, "part_id": part_id, "label": label,
                      "geometry_basis": basis, "bom_line": line if item else None, "no_bom_line": not bool(item),
                      "group": group, "explode_vector_mm": vector, "explode_derived": derived,
                      "geometry_sha256": digest, "evidence": evidence})
    return parts


def _links(status, calculations, bom, bom_source, swap_source, revision, parts):
    present = {part["part_id"] for part in parts}
    compatible = status.get("compatible_reference", {})
    connections = status.get("connections", {}).get("display", [])
    links = [
        ("display-ribbon", "DSI FFC", "pi4-dsi", "display", "dsi"),
        ("display-power", "Display GPIO power", "pi4-gpio", "display", "gpio_extensions"),
        ("pi-power", "Pi USB-C power", "power-bank-nominal-envelope", "pi4-usb-c", "power_cable"),
        ("keyboard-usb", "Keyboard USB", "keyboard-nominal-envelope", "pi4-board-envelope", None),
        ("fan-usb", "Fan USB", "fan-envelope", "pi4-board-envelope", None),
    ]
    open_items = {}
    for index, (interface_id, _, _, _, line) in enumerate(links):
        items = list(compatible.get("open_checks", [])) if index == 0 else []
        if items:
            open_items[interface_id] = [(reason, _STATUS) for reason in items]
        if revision == "5" and index < 2 and index < len(connections):
            if reason := connections[index].get("open_item"):
                open_items.setdefault(interface_id, []).append((reason, _STATUS))
        if reason := bom.get(line, {}).get("open_issue"):
            open_items.setdefault(interface_id, []).append((reason, bom_source))
    targets = {
        "bank ports/button and built-in cable not dimensioned": ("part_id", "power-bank-nominal-envelope"),
        "keyboard underside/pad retention and cable bend not manufacturer CAD": ("part_id", "keyboard-nominal-envelope"),
        "display lug thread/engagement nominal only": ("part_id", "display"),
        "GPIO extension contact current rating/retention unverified": ("interface_id", "display-power"),
        "flexible cable bends/routing not solid-interference verified": ("interface_id", "display-ribbon"),
    }
    blockers = []
    for reason in calculations.get("open_digital_fit_items", []):
        if reason in targets:
            binding, target = targets[reason]
            blockers.append({"reason": reason, binding: target, "source": f"{_BASE}/analysis/calculations.json"})
    if revision == "7":
        for line, part_id in (("m25_6", "display"), ("keyboard_pads", "keyboard-nominal-envelope")):
            if reason := bom.get(line, {}).get("open_issue"):
                blockers.append({"reason": reason, "part_id": part_id, "source": bom_source})
    blockers.extend({"reason": reason, "interface_id": interface_id, "source": source}
                    for interface_id, items in open_items.items() for reason, source in items)
    interfaces = []
    for interface_id, label, source_id, target_id, line in links:
        interface = {
            "interface_id": interface_id, "label": label, "from_part_id": source_id, "to_part_id": target_id,
            "endpoints_present": {source_id, target_id} <= present, "bom_line": line if line in bom else None,
            "open_checks": [reason for reason, _ in open_items.get(interface_id, ())],
        }
        if interface_id in {"display-ribbon", "display-power"} and swap_source.get("interface_doc"):
            interface["source"] = swap_source["interface_doc"]
        interfaces.append(interface)
    control = status.get("incompatible_control")
    alternates = [{"part_id": "display", **control, "source": _STATUS}] if control else []
    return interfaces, blockers, alternates


def build_parts_sidecar(project_dir, revision) -> dict:
    """Read Fielddeck records and return a sidecar without writing any inputs or outputs.

    Revisions 7 and 5 select the assembly shown. When both GLBs are available,
    the diff always runs from Fielddeck 7 to Fielddeck 5.
    """
    revision = str(revision).lower().removeprefix("fielddeck").strip(" _-")
    if revision not in {"7", "5"}:
        raise ValueError("Expected Fielddeck revision 7 or 5")
    project = Path(project_dir).resolve()
    missing = []

    def read(path, source):
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            missing.append(source)
            return None, (None, None)
        return data, (source, _sha(data))

    def record(path, source=None):
        data, origin = read(path, source or path.relative_to(project).as_posix())
        return (json.loads(data) if data is not None else {}), origin

    base_data, base_mesh_origin = read(project / _GLB7, _GLB7)
    (swap_data, swap_path), siblings = _swap_mesh(project / _SWAP)
    if swap_data is None:
        missing.append(f"{_SWAP}/**/{_GLB5} (including ZIP members)")
    swap_mesh_origin = (swap_path, _sha(swap_data) if swap_data is not None else None)
    status_path = next((parent / _STATUS for parent in project.parents if (parent / _STATUS).is_file()),
                       project.parent.parent / _STATUS)
    status, status_origin = record(status_path, _STATUS)
    report, report_origin = record(project / _REPORT)
    design, design_origin = record(project / _BASE / "design.json")
    references, _ = record(project / _BASE / "sources/references.json")
    swap_source, _ = record(project / _SWAP / "sources/evidence.json")
    swap_source = swap_source or status.get("sources", {})
    base_bom, (bom_source, _) = record(project / _BASE / "bom.json")
    calculations, _ = record(project / _BASE / "analysis/calculations.json")
    bom = {item["id"]: item for item in base_bom.get("items", [])}

    swap_geometry, swap_geometry_origin = {}, (None, None)
    revised_ids = set()
    if revision == "5":
        swap_geometry, swap_geometry_origin = status.get("geometry", {}), status_origin
        if "geometry.json" in siblings:
            data, source = siblings["geometry.json"]
            swap_geometry, swap_geometry_origin = json.loads(data), (source, _sha(data))
        if "BOM.json" in siblings:
            data, bom_source = siblings["BOM.json"]
            swap_bom = json.loads(data)
            revised_ids = {item["id"] for item in swap_bom.get("items", []) if item["id"] not in bom}
            bom = {item["id"]: item for item in swap_bom.get("items", [])}
        else:
            revised_ids = {row["part"] for row in swap_geometry.get("exports", {}).get("exported_parts", [])}
            bom.update({name: {"id": name} for name in revised_ids})
            if "display" in bom and swap_source.get("product_brief"):
                bom["display"] = {"id": "display", "description": "Raspberry Pi Touch Display 2, 5-inch (SC1975)"}

    base_nodes, swap_nodes = _nodes(base_data), _nodes(swap_data)
    mesh_origin = base_mesh_origin if revision == "7" else swap_mesh_origin
    parts = _parts(base_nodes if revision == "7" else swap_nodes, report, design, references,
                   swap_source, swap_geometry, bom, revised_ids,
                   (report_origin, mesh_origin, design_origin, swap_geometry_origin), revision)
    interfaces, blockers, alternates = _links(status, calculations, bom, bom_source, swap_source, revision, parts)
    if revision == "5" and "BOM.json" in siblings:
        for line in ("display", "m25_6"):
            if reason := bom.get(line, {}).get("open_issue"):
                blockers.append({"reason": reason, "part_id": "display", "source": bom_source})
    return {
        "schema_version": "hardware_splicer.parts_sidecar.v1",
        "revision": revision, "units": "mm", "glb_native_units": "mm", "glb_scale_to_mm": 1,
        "glb_source": mesh_origin[0], "glb_sha256": mesh_origin[1],
        "parts": parts, "interfaces": interfaces, "blockers": blockers, "alternates": alternates,
        "revision_diff": _diff(base_nodes, swap_nodes, base_data is not None and swap_data is not None),
        "missing_inputs": missing,
    }
