import type { CadProjectSource } from "./cad-project";

export type CadTemplate = {
  id: string;
  name: string;
  description: string;
  productName?: string;
  productPitch?: string;
  demoNarration?: string[];
  sampleFiles?: {
    pcbPath: string;
    pcbFilename: string;
    netPath: string;
    netFilename: string;
  };
  source: CadProjectSource;
  starterChecklist: string[];
  defaultHints?: Record<string, unknown>;
};

export const cadTemplates: CadTemplate[] = [
  {
    id: "hero-usb-esp32-sensor",
    name: "Hero Demo: DeskSense USB Environmental Monitor",
    description: "A real product concept (USB-C powered ESP32 + sensor) that shows validate → visualize → export.",
    productName: "DeskSense",
    productPitch:
      "A USB-powered desktop environmental monitor that measures temperature/humidity/pressure, displays status, and can stream data over Wi‑Fi. Circuit‑AI validates the power tree and highlights copper/rail risks before you order boards.",
    demoNarration: [
      "Start from a product goal, not an upload prompt.",
      "Validate the power tree and see risks directly on the board.",
      "Export Gerbers + BOM to prove this is manufacturing-ready tooling.",
    ],
    source: { type: "template", templateId: "hero-usb-esp32-sensor" },
    sampleFiles: {
      pcbPath: "/demo/usb_esp32_sensor.kicad_pcb",
      pcbFilename: "usb_esp32_sensor.kicad_pcb",
      netPath: "/demo/usb_esp32_sensor.net",
      netFilename: "usb_esp32_sensor.net",
    },
    starterChecklist: [
      "Load the sample KiCad PCB + netlist",
      "Run Validate (uses realistic power + load hints)",
      "Click issues to highlight footprints/nets in 3D",
      "Export Gerbers ZIP + BOM (JSON/CSV)",
    ],
    defaultHints: {
      sources: [{ name: "USB_5V", net: "VBUS", gnd: "GND", volts: 5.0, max_current_a: 0.5 }],
      traces: [
        {
          name: "USB_TO_VIN",
          n1: "VBUS",
          n2: "VIN",
          spec: { length_m: 0.12, width_m: 0.2e-3, copper_oz: 1.0 },
        },
      ],
      ldos: [
        {
          name: "U2_LDO",
          vin_net: "VIN",
          vout_net: "+3V3",
          gnd_net: "GND",
          vout_nom_v: 3.3,
          dropout_v: 0.35,
          max_current_a: 0.8,
          r_theta_ja_c_per_w: 60.0,
          tj_max_c: 125.0,
          ambient_c: 25.0,
        },
      ],
      loads_cc: [
        { name: "ESP32", net: "+3V3", gnd: "GND", amps: 0.24, min_v_off: 2.3 },
        { name: "BME280", net: "+3V3", gnd: "GND", amps: 0.005 },
        { name: "OLED", net: "+3V3", gnd: "GND", amps: 0.02 },
      ],
      voltage_constraints: [{ name: "RAIL_3V3", net: "+3V3", gnd: "GND", min_v: 3.0, max_v: 3.6, severity: "error" }],
      notes: "This template intentionally uses an undersized USB→VIN trace to trigger a meaningful voltage-drop/dropout warning.",
    },
  },
  {
    id: "hero-drone-fc-power",
    name: "Hero Demo: QuadForge Drone Flight Controller + Power Board",
    description: "Drone-style high-current rails: validate copper/voltage drop, then export Gerbers + BOM.",
    productName: "QuadForge",
    productPitch:
      "A compact drone power + flight-controller carrier concept: battery input, 5V/3V3 regulation, IMU + receiver headers, and motor/ESC power distribution. Circuit‑AI highlights current/trace‑drop risks before you spin the board.",
    demoNarration: [
      "Start from a product build goal: a drone electronics stack.",
      "Validate high-current rails and see copper risk hotspots on the board.",
      "Export Gerbers + BOM to prove the workflow ends in manufacturing artifacts.",
    ],
    source: { type: "template", templateId: "hero-drone-fc-power" },
    sampleFiles: {
      pcbPath: "/demo/drone_fc_power.kicad_pcb",
      pcbFilename: "drone_fc_power.kicad_pcb",
      netPath: "/demo/drone_fc_power.net",
      netFilename: "drone_fc_power.net",
    },
    starterChecklist: [
      "Load the drone sample KiCad PCB + netlist",
      "Run Validate (battery rail + 5V/3V3 + loads)",
      "Click issues to highlight connectors/rails in 3D",
      "Export Gerbers ZIP + BOM (JSON/CSV)",
    ],
    defaultHints: {
      sources: [{ name: "BAT", net: "VBAT", gnd: "GND", volts: 16.0, max_current_a: 20.0 }],
      traces: [
        {
          name: "BAT_BUS",
          n1: "VBAT",
          n2: "VBAT_BUS",
          spec: { length_m: 0.08, width_m: 0.3e-3, copper_oz: 1.0 },
        },
      ],
      loads_cc: [
        { name: "FC_5V", net: "+5V", gnd: "GND", amps: 0.8 },
        { name: "FC_3V3", net: "+3V3", gnd: "GND", amps: 0.25 },
      ],
      voltage_constraints: [
        { name: "RAIL_5V", net: "+5V", gnd: "GND", min_v: 4.8, max_v: 5.2, severity: "error" },
        { name: "RAIL_3V3", net: "+3V3", gnd: "GND", min_v: 3.0, max_v: 3.6, severity: "error" },
      ],
      notes:
        "This demo intentionally undersizes the battery bus trace spec to trigger a trace-drop warning and demonstrate design iteration.",
    },
  },
  {
    id: "power-tree-esp32",
    name: "ESP32 Power Tree",
    description: "Start with a canonical 5V → 3V3 rail + brownout constraints and trace-drop targets.",
    source: { type: "template", templateId: "power-tree-esp32" },
    starterChecklist: [
      "Define sources (VBUS, battery, bench supply)",
      "Define loads (ESP32 peak current, peripherals)",
      "Set voltage constraints (+3V3 min/max)",
      "Import KiCad `.kicad_pcb` when ready",
      "Run Validate and address warnings/errors",
    ],
    defaultHints: {
      sources: [{ name: "VUSB", net: "VBUS", gnd: "GND", volts: 5.0, max_current_a: 0.5 }],
      loads_cc: [{ name: "ESP32", net: "+3V3", gnd: "GND", amps: 0.24, min_v_off: 2.3 }],
      voltage_constraints: [{ name: "RAIL_3V3", net: "+3V3", gnd: "GND", min_v: 3.0, max_v: 3.6, severity: "error" }],
      notes: "Tune currents and nets to match your design.",
    },
  },
  {
    id: "buck-regulator",
    name: "Buck Converter Review",
    description: "Template for switching regulator bring-up: rails, loads, and sanity checks.",
    source: { type: "template", templateId: "buck-regulator" },
    starterChecklist: [
      "Declare VIN/VOUT/GND nets",
      "Add expected load current and max trace drop policy",
      "Import KiCad board and validate copper/rail droop",
      "Generate BOM and Gerbers when green",
    ],
    defaultHints: {
      sources: [{ name: "VIN", net: "VIN", gnd: "GND", volts: 12.0, max_current_a: 2.0 }],
      loads_cc: [{ name: "LOAD", net: "+5V", gnd: "GND", amps: 1.0 }],
      voltage_constraints: [{ name: "RAIL_5V", net: "+5V", gnd: "GND", min_v: 4.75, max_v: 5.25, severity: "error" }],
    },
  },
  {
    id: "blank-review",
    name: "Blank Design Review",
    description: "Start a project first, then import KiCad and iterate through issues visually.",
    source: { type: "blank" },
    starterChecklist: ["Create project", "Import KiCad", "Validate", "Walk issues visually", "Export manufacturing package"],
  },
];
