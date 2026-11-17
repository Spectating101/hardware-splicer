// KiCad footprint names, body envelopes, and pad positions (local mm from center).
// Sync footprint names with hardware_splicer/bom_generator.py _PART_HINTS.
//
// The per-module geometry is NOT edited here. It comes from
// src/hardware_splicer/data/module_footprints.json (the one source of truth shared with the
// Python engine) through module-footprint-data.generated.ts, which is written by
// scripts/export_module_footprints_ts.py.

import type { ModuleSpec } from "./module-library";
import {
  MODULE_FOOTPRINT_DATA,
  type ModuleFit,
  type ModuleFootprintMeta,
  type ModulePadDef,
} from "./module-footprint-data.generated";

export type { ModuleFit, ModuleFootprintMeta, ModulePadDef };

const P = 2.54;

export const MODULE_FOOTPRINTS: Record<string, ModuleFootprintMeta> = MODULE_FOOTPRINT_DATA;

/** Synthetic two-column placeholder for a module that has no registered footprint. */
function dualCol(left: string[], right: string[], xSpan = P * 4): ModulePadDef[] {
  const rows = Math.max(left.length, right.length);
  const y0 = -((rows - 1) * P) / 2;
  const xL = -xSpan / 2;
  const xR = xSpan / 2;
  const pads: ModulePadDef[] = [];
  for (let i = 0; i < left.length; i++) pads.push({ pinId: left[i], x: xL, y: y0 + i * P });
  for (let i = 0; i < right.length; i++) pads.push({ pinId: right[i], x: xR, y: y0 + i * P });
  return pads;
}

export function resolveModuleFootprint(moduleId: string): string {
  return MODULE_FOOTPRINTS[moduleId]?.kicadFootprint ?? `Circuit.AI:${moduleId}`;
}

export function resolveModuleBodyMm(moduleId: string): { w: number; h: number } | null {
  return MODULE_FOOTPRINTS[moduleId]?.bodyMm ?? null;
}

/**
 * Whether the module's footprint was checked against the real part. A module without a
 * registered footprint is drawn with a synthetic placeholder and is never verified.
 */
export function resolveModuleFit(moduleId: string): ModuleFit {
  return (
    MODULE_FOOTPRINTS[moduleId]?.fit ?? {
      status: "unverified_variant",
      reason: "No registered footprint: a synthetic two-column placeholder is used.",
    }
  );
}

export function resolveModulePads(moduleId: string, spec?: ModuleSpec): ModulePadDef[] | null {
  const custom = MODULE_FOOTPRINTS[moduleId]?.pads;
  if (custom?.length) return custom;
  if (!spec?.pins?.length) return null;
  const half = Math.ceil(spec.pins.length / 2);
  return dualCol(
    spec.pins.slice(0, half).map((p) => p.id),
    spec.pins.slice(half).map((p) => p.id),
  );
}

export function boundsFromPads(pads: ModulePadDef[], margin = 3): { w: number; h: number } {
  if (!pads.length) return { w: 10, h: 10 };
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const pad of pads) {
    minX = Math.min(minX, pad.x);
    maxX = Math.max(maxX, pad.x);
    minY = Math.min(minY, pad.y);
    maxY = Math.max(maxY, pad.y);
  }
  return {
    w: Math.max(maxX - minX + margin * 2, 8),
    h: Math.max(maxY - minY + margin * 2, 8),
  };
}
