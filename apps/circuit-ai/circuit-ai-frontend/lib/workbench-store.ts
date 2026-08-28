"use client";

import { create } from "zustand";
import type {
  PcbGeometry, ValidationIssue, DcAnalysis, ThermalMap, BomRisk,
  SafetyLevel, InventoryPart, SalvageModule, WiringSuggestion, ProjectSuggestion,
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

export interface Lenses {
  netFocus: boolean;
  drc: boolean;
  voltage: boolean;
  current: boolean;
  thermal: boolean;
  bom: boolean;
  peelMask: boolean;
  explode: number;
}

export type RenderMode = "engineering" | "production";
export type WorkbenchMode = "inspect" | "iterate" | "ship";

export interface SpiceResult {
  passed: boolean;
  minRailV: number | null;
  notes?: string[];
}

export interface DfmReport {
  score: number;
  critical: number;
  warnings: number;
  fab?: string;
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
  filename: string | null;
  file: File | null;
  geometry: PcbGeometry | null;
  issues: ValidationIssue[];
  nextSteps: string[];
  dfmNotes: string[];
  healthScore: number | null;
  dcAnalysis: DcAnalysis | null;
  thermal: ThermalMap | null;
  bomRisk: BomRisk | null;
  pipeline: WorkbenchPipeline;
  layers: LayerVis[];
  selectedRef: string | null;
  selectedNet: string | null;
  lenses: Lenses;
  renderMode: RenderMode;
  mode: WorkbenchMode;
  spiceResult: SpiceResult | null;
  dfmReport: DfmReport | null;
  bomCost: BomCost | null;
  jarvisMessages: JarvisMsg[];
  jarvisThinking: boolean;
  salvageModules: SalvageModule[];
  wiringSuggestions: WiringSuggestion[];
  projectSuggestions: ProjectSuggestion[];
  inventory: InventoryPart[];
  safetyLevel: SafetyLevel;
  drcOpen: boolean;
  loadFile(file: File, filename: string): void;
  setGeometry(g: PcbGeometry): void;
  setValidationResult(issues: ValidationIssue[], healthScore: number, nextSteps: string[], dfmNotes: string[]): void;
  setAnalysis(p: { dcAnalysis?: DcAnalysis | null; thermal?: ThermalMap | null; bomRisk?: BomRisk | null }): void;
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
  setSafetyLevel(level: SafetyLevel): void;
  setSalvageModules(modules: SalvageModule[]): void;
  setWiringSuggestions(wires: WiringSuggestion[]): void;
  setProjectSuggestions(projects: ProjectSuggestion[]): void;
  addInventoryPart(part: Omit<InventoryPart, "id" | "addedAt">): void;
  removeInventoryPart(id: string): void;
  clearInventory(): void;
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
  salvageModules: [],
  wiringSuggestions: [],
  projectSuggestions: [],
  inventory: [],
  safetyLevel: "safe",
  drcOpen: false,

  loadFile: (file, filename) => set({ file, filename, geometry: null, issues: [], healthScore: null, dcAnalysis: null, thermal: null, bomRisk: null, pipeline: { ...INITIAL_PIPELINE, parsed: true } }),
  setGeometry: (geometry) => set({ geometry }),
  setValidationResult: (issues, healthScore, nextSteps, dfmNotes) => set((s) => ({ issues, healthScore, nextSteps, dfmNotes, pipeline: { ...s.pipeline, validated: true, validating: false } })),
  setAnalysis: ({ dcAnalysis, thermal, bomRisk }) => set((s) => ({ dcAnalysis: dcAnalysis !== undefined ? dcAnalysis : s.dcAnalysis, thermal: thermal !== undefined ? thermal : s.thermal, bomRisk: bomRisk !== undefined ? bomRisk : s.bomRisk })),
  setManufactured: () => set((s) => ({ pipeline: { ...s.pipeline, manufactured: true, manufacturing: false } })),
  setPipelineFlag: (key, val) => set((s) => ({ pipeline: { ...s.pipeline, [key]: val } })),
  toggleLayer: (name) => set((s) => ({ layers: s.layers.map((l) => l.name === name ? { ...l, visible: !l.visible } : l) })),
  setSelectedRef: (ref) => set({ selectedRef: ref }),
  setSelectedNet: (net) => set({ selectedNet: net }),
  toggleLens: (key) => set((s) => ({ lenses: { ...s.lenses, [key]: !s.lenses[key] } as Lenses })),
  setLens: (key, value) => set((s) => ({ lenses: { ...s.lenses, [key]: value } })),
  setRenderMode: (mode) => set({ renderMode: mode }),
  setMode: (mode) => set({ mode }),
  setSpiceResult: (spiceResult) => set({ spiceResult }),
  setDfmReport: (dfmReport) => set({ dfmReport }),
  setBomCost: (bomCost) => set({ bomCost }),
  addJarvisMessage: (msg) => set((s) => ({ jarvisMessages: [...s.jarvisMessages.slice(-59), { ...msg, ts: Date.now() }] })),
  setJarvisThinking: (v) => set({ jarvisThinking: v }),
  toggleDrc: () => set((s) => ({ drcOpen: !s.drcOpen })),
  setSafetyLevel: (level) => set({ safetyLevel: level }),
  setSalvageModules: (modules) => set({ salvageModules: modules }),
  setWiringSuggestions: (wires) => set({ wiringSuggestions: wires }),
  setProjectSuggestions: (projects) => set({ projectSuggestions: projects }),
  addInventoryPart: (part) => set((s) => ({ inventory: [...s.inventory, { ...part, id: `inv_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`, addedAt: Date.now() }] })),
  removeInventoryPart: (id) => set((s) => ({ inventory: s.inventory.filter((p) => p.id !== id) })),
  clearInventory: () => set({ inventory: [] }),
  reset: () => set({ filename: null, file: null, geometry: null, issues: [], nextSteps: [], dfmNotes: [], healthScore: null, dcAnalysis: null, thermal: null, bomRisk: null, pipeline: { ...INITIAL_PIPELINE }, layers: DEFAULT_LAYERS, selectedRef: null, selectedNet: null, lenses: { ...INITIAL_LENSES }, renderMode: "engineering", mode: "inspect", spiceResult: null, dfmReport: null, bomCost: null, jarvisMessages: [], salvageModules: [], wiringSuggestions: [], projectSuggestions: [], inventory: [], safetyLevel: "safe", drcOpen: false }),
}));