"use client";

import { create } from "zustand";
import type {
  PcbGeometry, ValidationIssue, DcAnalysis, ThermalMap, BomRisk,
} from "./cad-types";

export interface JarvisMsg {
  role: "user" | "jarvis";
  text: string;
  ts: number;
}

export interface LayerVis {
  name: string;
  visible: boolean;
  color: string;
}

export const DEFAULT_LAYERS: LayerVis[] = [
  { name: "F.Cu",         visible: true,  color: "#c84b4b" },
  { name: "B.Cu",         visible: true,  color: "#4b8fc8" },
  { name: "In1.Cu",       visible: true,  color: "#c8a04b" },
  { name: "In2.Cu",       visible: true,  color: "#4bc8a0" },
  { name: "F.Silkscreen", visible: true,  color: "#e8e8c8" },
  { name: "B.Silkscreen", visible: false, color: "#c8c8e8" },
  { name: "Edge.Cuts",    visible: true,  color: "#ffff66" },
  { name: "F.Mask",       visible: false, color: "#c84b4b" },
  { name: "B.Mask",       visible: false, color: "#4b8fc8" },
  { name: "Airwire",      visible: true,  color: "#7a9cff" },
];

export interface WorkbenchPipeline {
  parsed: boolean;
  validated: boolean;
  manufactured: boolean;
  validating: boolean;
  manufacturing: boolean;
}

/** Canvas lenses — overlays painted on the single 3D board. Each one is a
 *  data stream the backend provides; toggling a lens switches shader uniforms
 *  rather than swapping geometry. */
export interface Lenses {
  netFocus: boolean;
  drc: boolean;
  voltage: boolean;
  current: boolean;
  thermal: boolean;
  bom: boolean;
  peelMask: boolean;
  /** 0–1 — how far components lift off the board on a reflow-order explode. */
  explode: number;
}

export type RenderMode = "engineering" | "production";

/** Top-level UX mode. Determines which question the workspace is answering:
 *  inspect = "does this work?", iterate = "make it better", ship = "get it made". */
export type WorkbenchMode = "inspect" | "iterate" | "ship";

export interface SpiceResult {
  passed: boolean;
  minRailV: number | null;  // worst-case minimum on a power rail
  notes?: string[];
}

export interface DfmReport {
  score: number;       // 0–100
  critical: number;
  warnings: number;
  fab?: string;        // "JLCPCB 2-layer FR4"
}

export interface BomCost {
  unitUsd: number;
  qty: number;
  totalUsd: number;
  leadDays: number;
}

export const INITIAL_LENSES: Lenses = {
  netFocus: true,
  drc: true,
  voltage: false,
  current: false,
  thermal: false,
  bom: false,
  peelMask: false,
  explode: 0,
};

interface WorkbenchState {
  // Board data
  filename: string | null;
  file: File | null;
  geometry: PcbGeometry | null;
  issues: ValidationIssue[];
  nextSteps: string[];
  dfmNotes: string[];
  healthScore: number | null;

  // Backend analysis streams that feed lenses
  dcAnalysis: DcAnalysis | null;
  thermal: ThermalMap | null;
  bomRisk: BomRisk | null;

  // Pipeline flags
  pipeline: WorkbenchPipeline;

  // Layer & selection
  layers: LayerVis[];
  selectedRef: string | null;
  selectedNet: string | null;

  // Canvas lenses
  lenses: Lenses;

  // Canvas render mode — engineering (copper-primary, default) vs production
  // (opaque green mask, screenshot look). peelMask lens still wins on top of
  // both when active.
  renderMode: RenderMode;

  // Top-level UX mode — swaps side-panel content, not layout.
  mode: WorkbenchMode;

  // Downstream pipeline artefacts. Null until the corresponding backend call
  // returns. The header spine reads these to show real numbers at each stage.
  spiceResult: SpiceResult | null;
  dfmReport: DfmReport | null;
  bomCost: BomCost | null;

  // JARVIS
  jarvisMessages: JarvisMsg[];
  jarvisThinking: boolean;

  // UI
  drcOpen: boolean;

  // Actions
  loadFile(file: File, filename: string): void;
  setGeometry(g: PcbGeometry): void;
  setValidationResult(
    issues: ValidationIssue[],
    healthScore: number,
    nextSteps: string[],
    dfmNotes: string[]
  ): void;
  setAnalysis(p: {
    dcAnalysis?: DcAnalysis | null;
    thermal?: ThermalMap | null;
    bomRisk?: BomRisk | null;
  }): void;
  setManufactured(): void;
  setPipelineFlag(key: keyof WorkbenchPipeline, val: boolean): void;
  toggleLayer(name: string): void;
  setSelectedRef(ref: string | null): void;
  setSelectedNet(net: string | null): void;
  toggleLens<K extends keyof Lenses>(key: K): void;
  setLens<K extends keyof Lenses>(key: K, value: Lenses[K]): void;
  setRenderMode(mode: RenderMode): void;
  setMode(mode: WorkbenchMode): void;
  setSpiceResult(r: SpiceResult | null): void;
  setDfmReport(r: DfmReport | null): void;
  setBomCost(c: BomCost | null): void;
  addJarvisMessage(msg: Omit<JarvisMsg, "ts">): void;
  setJarvisThinking(v: boolean): void;
  toggleDrc(): void;
  reset(): void;
}

const INITIAL_PIPELINE: WorkbenchPipeline = {
  parsed: false,
  validated: false,
  manufactured: false,
  validating: false,
  manufacturing: false,
};

export const useWorkbenchStore = create<WorkbenchState>((set) => ({
  filename: null,
  file: null,
  geometry: null,
  issues: [],
  nextSteps: [],
  dfmNotes: [],
  healthScore: null,
  dcAnalysis: null,
  thermal: null,
  bomRisk: null,
  pipeline: { ...INITIAL_PIPELINE },
  layers: DEFAULT_LAYERS,
  selectedRef: null,
  selectedNet: null,
  lenses: { ...INITIAL_LENSES },
  renderMode: "engineering",
  mode: "inspect",
  spiceResult: null,
  dfmReport: null,
  bomCost: null,
  jarvisMessages: [],
  jarvisThinking: false,
  drcOpen: false,

  loadFile: (file, filename) =>
    set({
      file,
      filename,
      geometry: null,
      issues: [],
      healthScore: null,
      dcAnalysis: null,
      thermal: null,
      bomRisk: null,
      pipeline: { ...INITIAL_PIPELINE, parsed: true },
    }),

  setGeometry: (geometry) => set({ geometry }),

  setValidationResult: (issues, healthScore, nextSteps, dfmNotes) =>
    set((s) => ({
      issues,
      healthScore,
      nextSteps,
      dfmNotes,
      pipeline: { ...s.pipeline, validated: true, validating: false },
    })),

  setAnalysis: ({ dcAnalysis, thermal, bomRisk }) =>
    set((s) => ({
      dcAnalysis: dcAnalysis !== undefined ? dcAnalysis : s.dcAnalysis,
      thermal: thermal !== undefined ? thermal : s.thermal,
      bomRisk: bomRisk !== undefined ? bomRisk : s.bomRisk,
    })),

  setManufactured: () =>
    set((s) => ({
      pipeline: { ...s.pipeline, manufactured: true, manufacturing: false },
    })),

  setPipelineFlag: (key, val) =>
    set((s) => ({ pipeline: { ...s.pipeline, [key]: val } })),

  toggleLayer: (name) =>
    set((s) => ({
      layers: s.layers.map((l) =>
        l.name === name ? { ...l, visible: !l.visible } : l
      ),
    })),

  setSelectedRef: (ref) => set({ selectedRef: ref }),
  setSelectedNet: (net) => set({ selectedNet: net }),

  toggleLens: (key) =>
    set((s) => ({
      lenses: { ...s.lenses, [key]: !s.lenses[key] } as Lenses,
    })),

  setLens: (key, value) =>
    set((s) => ({ lenses: { ...s.lenses, [key]: value } })),

  setRenderMode: (mode) => set({ renderMode: mode }),
  setMode: (mode) => set({ mode }),
  setSpiceResult: (spiceResult) => set({ spiceResult }),
  setDfmReport: (dfmReport) => set({ dfmReport }),
  setBomCost: (bomCost) => set({ bomCost }),

  addJarvisMessage: (msg) =>
    set((s) => ({
      jarvisMessages: [
        ...s.jarvisMessages.slice(-59),
        { ...msg, ts: Date.now() },
      ],
    })),

  setJarvisThinking: (v) => set({ jarvisThinking: v }),
  toggleDrc: () => set((s) => ({ drcOpen: !s.drcOpen })),

  reset: () =>
    set({
      filename: null,
      file: null,
      geometry: null,
      issues: [],
      nextSteps: [],
      dfmNotes: [],
      healthScore: null,
      dcAnalysis: null,
      thermal: null,
      bomRisk: null,
      pipeline: { ...INITIAL_PIPELINE },
      layers: DEFAULT_LAYERS,
      selectedRef: null,
      selectedNet: null,
      lenses: { ...INITIAL_LENSES },
      renderMode: "engineering",
      mode: "inspect",
      spiceResult: null,
      dfmReport: null,
      bomCost: null,
      jarvisMessages: [],
      drcOpen: false,
    }),
}));
