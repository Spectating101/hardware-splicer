/** How the workbench files HS's tools, and inputs that run against files tracked in this repository. */

export const TOOL_GROUPS = [
  ["Board", ["hs_component_board", "hs_plan_circuit", "hs_review_kicad_schematic", "hs_route_copper", "hs_trace_current",
    "hs_check_board_parts", "hs_import_eagle_module"]],
  ["Sizing", ["hs_device_review", "hs_battery_runtime", "hs_energy_budget", "hs_prop_hover", "hs_check_propulsion",
    "hs_pick_propulsion", "hs_size_arm_actuators", "hs_size_rover_drive", "hs_rocker_bogie"]],
  ["Mechanical", ["hs_step_fit", "hs_fem_screen", "hs_arm_kinematics", "hs_motion_sweep", "hs_rover_chassis"]],
  ["Salvage and parts", ["hs_junk_lookup", "hs_what_can_i_build", "hs_salvage_resources", "hs_identify_part",
    "hs_price_parts", "hs_bom_check", "hs_route_economics"]],
  ["Research", ["hs_prior_art_search", "hs_capability_search", "hs_read_board", "hs_external_tools"]],
  ["Projects", ["hs_project_open", "hs_project_status", "hs_project_record", "hs_project_write_artifact",
    "hs_project_link_design", "hs_device_lab", "hs_record_outcome"]],
];

const GROUP_OF = new Map(TOOL_GROUPS.flatMap(([group, names]) => names.map((n) => [n, group])));
export const groupOf = (name) => GROUP_OF.get(name) ?? "Other";

export const ROLE_LABELS = {
  routing: "Routing", checking: "Checking", cad: "CAD", interface: "Interface", fab: "Fabrication",
  data: "Data", direction: "Direction",
};

/** Readable name: hs_size_rover_drive -> "Size rover drive". The tool id stays visible beside it. */
export function toolTitle(name) {
  const words = name.replace(/^hs_/, "").split("_");
  const text = words.join(" ")
    .replace(/\bkicad\b/g, "KiCad").replace(/\bbom\b/g, "BOM").replace(/\bstep\b/g, "STEP")
    .replace(/\bfem\b/g, "FEM");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const BUS_A = "projects/hs-bus-a/kicad/hs_bus_a";

export const EXAMPLES = {
  hs_review_kicad_schematic: { schematic: `${BUS_A}.kicad_sch` },
  hs_trace_current: { pcb: `${BUS_A}.kicad_pcb`, net_currents_a: { "/VIN_12V": 5, "/DXL_VDD1": 2.5, "/DXL_VDD2": 2.5, "/DXL_VDD3": 2.5 } },
  hs_step_fit: { step: "tests/fixtures/step_fit/overlap_demo.step", density_g_cm3: { "*": 1.24 } },
  hs_junk_lookup: { needs: ["drive_motors", "camera", "wifi_compute", "battery_cells"] },
  hs_what_can_i_build: { have: ["esp32-devkitc-v4", "adafruit-bh1750-stemma-qt"] },
  hs_identify_part: { marking: "AMS1117" },
  hs_size_arm_actuators: { links_mm: [150, 150], payload_kg: 0.2, supply_v: 12, max_stall_share: 0.5 },
  hs_size_rover_drive: { mass_kg: 1.2, wheel_mm: 80, speed_m_s: 0.4, slope_deg: 10 },
  hs_device_review: { example: "esp32_oled_bme280_usb" },
  hs_battery_runtime: { capacity_mah: 2600, period_s: 600, sleep_ua: 10, phases: [{ label: "LoRa transmit", ma: 120, seconds: 0.5 }] },
  hs_capability_search: { query: "fem screening" },
  hs_prior_art_search: { query: "smartphone robot rover", sources: ["hs_own"], limit: 20 },
  hs_external_tools: {},
};

export const OUTCOME_LABEL = {
  clean: "clean", failed: "failed", recorded: "recorded", not_run: "not run", unknown: "not recorded",
};
