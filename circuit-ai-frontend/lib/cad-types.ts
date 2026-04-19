export type PcbBboxMm = {
  min_x: number;
  min_y: number;
  max_x: number;
  max_y: number;
  width: number;
  height: number;
};

export type PcbPadShape = "circle" | "oval" | "rect" | "roundrect" | "trapezoid" | "custom";
export type PcbPadType = "smd" | "thru_hole" | "np_thru_hole" | "connect";

export type PcbPad = {
  num: string;
  wx: number; // world-space mm (rotated footprint frame)
  wy: number;
  net: { id: number; name: string };
  /** world rotation = footprint.rot + pad.rot */
  wrot_deg?: number;
  shape?: PcbPadShape;
  size_w_mm?: number; // local-frame width (before world rotation)
  size_h_mm?: number;
  drill_mm?: number;   // >0 for thru-hole pads
  roundrect_ratio?: number;
  type?: PcbPadType;
};

export type PcbSilkLine = {
  layer: string; // "F.SilkS" | "B.SilkS"
  start: { x: number; y: number };
  end: { x: number; y: number };
  width_mm: number;
};

export type PcbSilkArc = {
  layer: string;
  start: { x: number; y: number };
  mid: { x: number; y: number };
  end: { x: number; y: number };
  width_mm: number;
};

export type PcbSilkText = {
  layer: string;
  text: string;
  at: { x: number; y: number; rot_deg: number };
  size_mm: number;
};

export type PcbZone = {
  layer: string;
  net_id: number;
  net_name: string;
  /** Polygon rings in world mm. Multiple rings = disjoint fill islands. */
  polygons: Array<Array<{ x: number; y: number }>>;
};

export type PcbEdgeArc = {
  start: { x: number; y: number };
  mid: { x: number; y: number };
  end: { x: number; y: number };
};

export type PcbEdgeLine = {
  start: { x: number; y: number };
  end: { x: number; y: number };
};

export type PcbGeometry = {
  board: { bbox_mm: PcbBboxMm | null };
  nets: Array<{ id: number; name: string }>;
  footprints: Array<{
    ref: string;
    value: string;
    footprint: string;
    layer: string;
    at: { x: number; y: number; rot_deg: number };
    pads?: PcbPad[];
  }>;
  segments: Array<{
    start: { x: number; y: number };
    end: { x: number; y: number };
    width_mm: number | null;
    layer: string;
    net: { id: number | null; name: string };
  }>;
  vias?: Array<{
    x: number;
    y: number;
    size_mm: number;
    drill_mm: number;
    net: { id: number; name: string };
  }>;
  zones?: PcbZone[];
  silkLines?: PcbSilkLine[];
  silkArcs?: PcbSilkArc[];
  silkText?: PcbSilkText[];
  edgeArcs?: PcbEdgeArc[];
  edgeLines?: PcbEdgeLine[];
};

export type ValidationIssue = {
  severity: "critical" | "error" | "warning" | "info" | string;
  component: string;
  issue: string;
  solution: string;
  physics?: unknown;
};

/** DC analysis produced by the backend's MNA solver. Optional — only present
 *  when the board has a recognisable power source (battery/LDO/DCDC). */
export type DcAnalysis = {
  /** Node voltage per net id (volts). */
  node_voltages?: Record<string, number>;
  /** Branch current per segment id or "netId:segIndex" key (amps). */
  branch_currents?: Record<string, number>;
  /** Per-power-rail summary. */
  rails?: Array<{ net_id: number; name: string; v_nom: number; v_drop_max_mv: number }>;
};

/** Simple thermal projection per component ref (°C junction temp). */
export type ThermalMap = Record<string, { tj_c: number; derate_pct: number }>;

/** Supply-chain risk per component ref (0–1, where 1 = highest risk). */
export type BomRisk = Record<
  string,
  { risk: number; lead_days?: number; price_usd?: number; mpn?: string }
>;

/* ──────────────── DIY / reuse domain types ──────────────── */

/** Traffic-light safety classification surfaced by the AI on every response.
 *  - `safe`:    TTL / battery-level / <12V. Render freely.
 *  - `caution`: 12–60V DC, medium-current, or anything a beginner can still handle
 *               with a heads-up. Render with a visible caution banner.
 *  - `hazard`:  Mains voltage (>60V AC), lithium packs >10Wh, CRT flyback, RF >1W,
 *               bulk caps >400V. Render behind an "are you qualified" gate. */
export type SafetyLevel = "safe" | "caution" | "hazard";

/** One functional block identified on a salvage target. Produced by the vision
 *  call (`/api/jarvis/identify`) or the salvage planner. */
export type SalvageModule = {
  id: string;
  kind: "power" | "mcu" | "radio" | "sensor" | "driver" | "connector" | "passive" | "unknown";
  label: string;                      // "5V buck regulator", "ESP32-WROOM"
  description: string;                // plain-English what it does
  safety: SafetyLevel;
  /** Normalized image-space bounding box, 0–1 on each axis. */
  bbox?: { x: number; y: number; w: number; h: number };
  /** Pins the user can probably expose to reuse the module. */
  pins?: Array<{ name: string; role: string; voltage?: string }>;
  /** Free-text extraction recipe from the planner. */
  extraction?: string;
  warnings?: string[];
};

/** One wire the AI proposes on the Build canvas. `from`/`to` reference
 *  `<module_id>.<pin_name>` in the current project. */
export type WiringSuggestion = {
  id: string;
  from: string;
  to: string;
  purpose: string;                    // "5V supply", "I2C SDA", "GND return"
  safety: SafetyLevel;
  warnings?: string[];
};

/** A project recommendation surfaced from a parts inventory. */
export type ProjectSuggestion = {
  id: string;
  title: string;
  difficulty: "beginner" | "intermediate" | "advanced";
  summary: string;
  requiredModules: string[];          // labels matched against inventory
  optionalModules?: string[];
  estimatedTimeHours?: number;
  safety: SafetyLevel;
};

/** A single item in the user's parts inventory. Typed by hand, scanned from a
 *  photo, or adopted from a past board scan. */
export type InventoryPart = {
  id: string;
  label: string;
  kind: SalvageModule["kind"];
  source: "typed" | "scan" | "salvage";
  qty: number;
  notes?: string;
  photoUrl?: string;
  addedAt: number;
};

export type ValidateKiCadResponse = {
  status: string;
  next_steps: string[];
  manufacturing_ready: boolean;
  validation: {
    issues_count: number;
    critical: number;
    errors: number;
    warnings: number;
    issues: ValidationIssue[];
  };
  pcb_geometry?: PcbGeometry;
  dc_analysis?: DcAnalysis;
  thermal?: ThermalMap;
  bom_risk?: BomRisk;
};

