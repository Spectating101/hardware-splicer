import type { CadProjectSource } from "./cad-project";

export type CadTemplate = {
  id: string;
  name: string;
  description: string;
  source: CadProjectSource;
  starterChecklist: string[];
  defaultHints?: Record<string, unknown>;
};

export const cadTemplates: CadTemplate[] = [
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

