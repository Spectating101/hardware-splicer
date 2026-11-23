// Compile-time guard, checked by `npm run typecheck`: approval words outside the backend's own
// vocabulary are type errors. If one of these lines stops being an error, someone has widened a
// state union to include a readiness or approval claim; that is a bug, not progress.
import type { BenchState, CopperState, DesignState, OverallState } from "./deriveProjectTruth";
import type { EvidenceState, EvidenceTone } from "./deriveEvidenceTruth";
import type { TransitionKind } from "./checkTransition";

// @ts-expect-error a project is never simply "ready"
export const overallReady: OverallState = "ready";
// @ts-expect-error nor "approved"
export const overallApproved: OverallState = "approved";
// @ts-expect-error evidence is verified by the backend, never "proven" by the UI
export const evidenceProven: EvidenceState = "proven";
// @ts-expect-error a simulated pass is not a physical pass
export const benchPassed: BenchState = "passed";
// @ts-expect-error copper is a fab candidate at most
export const copperReleased: CopperState = "released";
// @ts-expect-error a clean DRC is not a design approval
export const designApproved: DesignState = "approved";
// @ts-expect-error there is no success tone; tones are neutral, warn or fail
export const toneSuccess: EvidenceTone = "success";
// @ts-expect-error a check transition is not a grade
export const transitionGood: TransitionKind = "good";
