export type PcbBboxMm = {
  min_x: number;
  min_y: number;
  max_x: number;
  max_y: number;
  width: number;
  height: number;
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
    pads?: Array<{
      num: string;
      wx: number; // world-space mm
      wy: number;
      net: { id: number; name: string };
    }>;
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

