import type { PcbGeometry, ValidateKiCadResponse } from "./cad-types";

export const demoGeometry: PcbGeometry = {
  board: {
    bbox_mm: { min_x: 0, min_y: 0, max_x: 60, max_y: 40, width: 60, height: 40 },
  },
  nets: [
    { id: 0, name: "" },
    { id: 1, name: "GND" },
    { id: 2, name: "+3V3" },
  ],
  footprints: [
    {
      ref: "U1",
      value: "ESP32",
      footprint: "Module:ESP32-WROOM",
      layer: "F.Cu",
      at: { x: 30, y: 20, rot_deg: 0 },
    },
    {
      ref: "R1",
      value: "150R",
      footprint: "Resistor_SMD:R_0603_1608Metric",
      layer: "F.Cu",
      at: { x: 18, y: 12, rot_deg: 0 },
    },
    {
      ref: "C1",
      value: "10uF",
      footprint: "Capacitor_SMD:C_0603_1608Metric",
      layer: "F.Cu",
      at: { x: 42, y: 27, rot_deg: 90 },
    },
  ],
  segments: [
    {
      start: { x: 5, y: 20 },
      end: { x: 55, y: 20 },
      width_mm: 0.25,
      layer: "F.Cu",
      net: { id: 2, name: "+3V3" },
    },
    {
      start: { x: 5, y: 10 },
      end: { x: 55, y: 10 },
      width_mm: 0.25,
      layer: "F.Cu",
      net: { id: 1, name: "GND" },
    },
  ],
};

export const demoValidation: ValidateKiCadResponse = {
  status: "validation_warning",
  manufacturing_ready: false,
  next_steps: ["Review warnings", "Consider fixes for optimal performance"],
  validation: {
    issues_count: 2,
    critical: 0,
    errors: 0,
    warnings: 2,
    issues: [
      {
        severity: "warning",
        component: "TRACE::VCC_MAIN",
        issue: "High trace voltage drop",
        solution: "Increase trace width to ~1.20mm (currently 0.25mm)",
        physics: { current_a: 2.0, vdrop_v: 0.35, recommended_width_m: 0.0012 },
      },
      {
        severity: "warning",
        component: "R1",
        issue: "Resistor power rating exceeded",
        solution: "Replace with 1/2W resistor footprint/value",
        physics: { actual_power_w: 0.31, rated_power_w: 0.25 },
      },
    ],
  },
  pcb_geometry: demoGeometry,
};

