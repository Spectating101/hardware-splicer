"""Use HS substitution checks on the sourced Fielddeck display interface."""
from copy import deepcopy

def assess_interfaces(mount, evidence, baseline_geometry, *, evaluator=None):
    """Produce one documented compatible interface case and one blocked case.

    The reference scope is the panel bay and Pi 4 display interface. The full
    assembly power scenario and reimported native geometry are checked separately.
    """
    if evaluator is None:
        from hardware_splicer.part_substitution import evaluate_substitution
        evaluator = evaluate_substitution
    lane_note = evidence["lane_note"]
    compatibility = evidence["interface_doc"]
    original = next(row for row in baseline_geometry["parts"] if row["kind"] == "manufacturer_step")
    lo_x, lo_y, lo_z, hi_x, hi_y, hi_z = original["bounds_mm"]
    glass = mount["glass_mm"]
    center_x, center_y = 155, 210
    workspace_minimum = [0, 0, 0]
    workspace_maximum = [310, 285.7, 64]
    old_dsi = {"port_id": "video", "kind": "signal", "direction": "input",
               "connector": "Raspberry Pi standard 15-way display FFC", "protocol": "Raspberry Pi DSI 2-lane"}
    # Exact pin numbering and voltage limits are deliberately left open.
    # The manufacturer's compatibility statement applies to the supplied kits.
    board = {"part_id": "pi4", "name": "Raspberry Pi 4 Model B", "manufacturer": "Raspberry Pi", "mpn": "SC0193",
             "functions": ["display_host"], "dimensions_mm": [56, 85.7, 17.6], "position_mm": [4, 198, 7],
             "ports": [{**old_dsi, "direction": "output"}]}
    display = {"part_id": "display", "name": "7-inch Raspberry Pi Touch Display 2", "manufacturer": "Raspberry Pi",
               "mpn": "SC1635", "functions": ["video", "touch"], "ports": [old_dsi],
               "position_mm": [lo_x, lo_y, lo_z], "dimensions_mm": [hi_x - lo_x, hi_y - lo_y, hi_z - lo_z],
               "mount": {"holes_mm": [[round(x-lo_x, 3), round(y-lo_y, 3)]
                                     for x,y in baseline_geometry["display_case_mount_centres_mm"]],
                         "hole_diameter_mm": 2.0, "plane_z_mm": 5.5, "fastener": "M2.5 nominal"}}
    five = {**display, "part_id": "sc1975", "mpn": "SC1975", "name": "5-inch Raspberry Pi Touch Display 2",
            "position_mm": None, "dimensions_mm": [*glass, evidence["product_brief"]["nominal_lug_depth_mm"]],
            "mount": {"holes_mm": [[round(x-center_x+glass[0]/2, 3), round(y-center_y+glass[1]/2, 3)]
                                  for x,y in mount["mount_xy_mm"]],
                      "hole_diameter_mm": 2.5, "plane_z_mm": 0, "fastener": "M2.5 nominal"}}
    ten = {**five, "part_id": "touch-display-2-10", "mpn": None, "name": "10-inch Raspberry Pi Touch Display 2",
           "dimensions_mm": [248.1, 166.9, 15.5], "mount": None,
           "ports": [{**old_dsi, "connector": "Raspberry Pi mini 22-way display FFC",
                      "protocol": "Raspberry Pi DSI 4-lane"}]}
    graph = {"parts": [board, display], "replace_part_id": "display",
             "connections": [{"connection_id": "display-ribbon", "from": {"part_id":"pi4", "port_id":"video"},
                              "to": {"part_id":"display", "port_id":"video"}}],
             "enclosure": {"minimum_mm": workspace_minimum, "maximum_mm": workspace_maximum}}
    first = deepcopy(graph) | {"candidate": five}
    negative = deepcopy(graph) | {"candidate": ten}
    positive_report = evaluator(first)
    negative_report = evaluator(negative)
    if not any(row["kind"] == "mount_adapter" for row in positive_report["required_adaptations"]):
        raise ValueError("Expected a changed mounting interface for SC1975.")
    if negative_report["status"] != "blocked" or not any(
            row["code"] == "protocol_mismatch" and row["status"] == "fail" for row in negative_report["checks"]):
        raise ValueError("The 10-inch/2-lane incompatibility was not caught.")
    return {
        "scope": "Display interface splice. The generic evaluator uses a lower-corner envelope; the authored CAD centres the replacement glass.",
        "candidate": {
            "specification": first, "substitution": positive_report,
            "manufacturer_kit_compatibility": {"status":"documented_for_pi4", "source":compatibility},
        },
        "negative_control": {
            "specification": negative, "substitution": negative_report,
            "manufacturer_kit_compatibility": {"status":"incompatible_with_pi4", "source":compatibility,
                                                 "lane_source":lane_note},
        },
        "connections": [
            {"from":"Pi 4 DISPLAY", "to":"SC1975 DSI", "path":"Existing 15-way to 15-way FFC format",
             "retained_part":"Adafruit 1648, 300 mm", "status":"documented_interface",
             "open_item":"Installed cable exit, bend and strain relief remain to be checked."},
            {"from":"Pi 4 GPIO 5 V and GND", "to":"SC1975 power input",
             "path":"Supplied GPIO lead with the retained extension concept", "status":"documented_interface",
             "open_item":"Confirm extension contact rating and delivered voltage; exact port limits are not published in the retained brief."},
        ],
        "physical_validation_performed": False,
    }
