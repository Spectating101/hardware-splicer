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
  }>;
  segments: Array<{
    start: { x: number; y: number };
    end: { x: number; y: number };
    width_mm: number | null;
    layer: string;
    net: { id: number | null; name: string };
  }>;
};

export type ValidationIssue = {
  severity: "critical" | "error" | "warning" | "info" | string;
  component: string;
  issue: string;
  solution: string;
  physics?: unknown;
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
};

