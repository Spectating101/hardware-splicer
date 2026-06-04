import type { SafetyLevel } from "@/lib/cad-types";
import type { BoardEvidence, BoardEvidenceTrust } from "./board-evidence";

export type RepairAuthorityStatus =
  | "visual_only"
  | "needs_measurements"
  | "measurement_backed"
  | "authoritative_low_risk"
  | "blocked";

export type RepairAuthorityGateStatus = "pass" | "warn" | "fail";

export interface RepairMeasurementEvidence {
  measurement_id?: string;
  type?: string;
  target?: string;
  value?: unknown;
  unit?: string;
  notes?: string;
  confidence?: number;
  created_at?: string;
}

export interface RepairAuthorityGate {
  id: string;
  label: string;
  status: RepairAuthorityGateStatus;
  score: number;
  reason: string;
}

export interface RepairAuthority {
  status: RepairAuthorityStatus;
  score: number;
  summary: string;
  safety_level: SafetyLevel;
  supported_decisions: string[];
  blocked_decisions: string[];
  required_measurements: string[];
  measurement_summary: {
    count: number;
    continuity: number;
    resistance: number;
    voltage: number;
    current: number;
    functional: number;
    passed: number;
    failed: number;
    contradictory: number;
    quality: "none" | "text_only" | "typed" | "bench_recorded" | "failed" | "contradictory";
  };
  gates: RepairAuthorityGate[];
}

interface RepairAuthorityInput {
  boardEvidence?: BoardEvidence | null;
  evidenceTrust?: BoardEvidenceTrust | null;
  measurements?: RepairMeasurementEvidence[];
  verifierStatus?: string;
  verifierSafety?: SafetyLevel;
}

type MeasurementCategory = "continuity" | "resistance" | "voltage" | "current" | "functional";
type MeasurementQuality = RepairAuthority["measurement_summary"]["quality"];

const GENERIC_MEASUREMENT_TYPES = new Set(["", "measurement", "reading", "bench", "check", "test"]);

function textOf(measurement: RepairMeasurementEvidence): string {
  return `${measurement.type ?? ""} ${measurement.target ?? ""} ${measurement.value ?? ""} ${measurement.unit ?? ""} ${measurement.notes ?? ""}`.toLowerCase();
}

function includesAny(text: string, terms: string[]): boolean {
  return terms.some((term) => text.includes(term));
}

function gate(
  id: string,
  label: string,
  status: RepairAuthorityGateStatus,
  score: number,
  reason: string,
): RepairAuthorityGate {
  return {
    id,
    label,
    status,
    score: Number(Math.max(0, Math.min(1, score)).toFixed(2)),
    reason,
  };
}

function textValue(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function categoryFromType(type: unknown): MeasurementCategory | undefined {
  const text = textValue(type);
  if (!text || GENERIC_MEASUREMENT_TYPES.has(text)) return undefined;
  if (includesAny(text, ["continuity", "beep"])) return "continuity";
  if (includesAny(text, ["resistance", "ohm", "impedance"])) return "resistance";
  if (includesAny(text, ["voltage", "volt", "rail"])) return "voltage";
  if (includesAny(text, ["current", "amp", "draw"])) return "current";
  if (includesAny(text, ["functional", "function", "boot", "logic", "signal", "scope", "oscilloscope", "output"])) return "functional";
  return undefined;
}

function categoryFromText(measurement: RepairMeasurementEvidence): MeasurementCategory | undefined {
  const text = textOf(measurement);
  if (includesAny(text, ["continuity", "beep"])) return "continuity";
  if (includesAny(text, ["resistance", "ohm", "Ω", "kohm", "mohm"])) return "resistance";
  if (includesAny(text, ["voltage", "volt", " v", "rail", "vbus", "3v3", "3.3v", "5v", "12v"])) return "voltage";
  if (includesAny(text, ["current draw", "draw", "amp", " ma", " a "])) return "current";
  if (includesAny(text, ["functional", "works", "boot", "enumerates", "signal present", "output present", "oscilloscope", "logic"])) return "functional";
  return undefined;
}

function categoryForMeasurement(measurement: RepairMeasurementEvidence): MeasurementCategory | undefined {
  const typed = categoryFromType(measurement.type);
  if (typed) return typed;
  const type = textValue(measurement.type);
  if (type && !GENERIC_MEASUREMENT_TYPES.has(type)) return undefined;
  return categoryFromText(measurement);
}

function categoryCounts(measurements: RepairMeasurementEvidence[]) {
  const counts = { continuity: 0, resistance: 0, voltage: 0, current: 0, functional: 0 };
  for (const measurement of measurements) {
    const category = categoryForMeasurement(measurement);
    if (category) counts[category] += 1;
  }
  return counts;
}

function parseNumber(measurement: RepairMeasurementEvidence): number | undefined {
  if (typeof measurement.value === "number" && Number.isFinite(measurement.value)) return measurement.value;
  const text = `${measurement.value ?? ""} ${measurement.unit ?? ""}`.toString();
  const match = text.match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : undefined;
}

function valueAndUnitText(measurement: RepairMeasurementEvidence): string {
  return `${measurement.value ?? ""} ${measurement.unit ?? ""}`.toLowerCase();
}

function resistanceOhms(measurement: RepairMeasurementEvidence): number | undefined {
  const value = parseNumber(measurement);
  if (value === undefined) return undefined;
  const text = valueAndUnitText(measurement);
  if (includesAny(text, ["kohm", "kΩ", "k ohm", "k "])) return value * 1000;
  if (includesAny(text, ["megohm", "mohm", "mΩ", "m ohm"])) return value * 1_000_000;
  return value;
}

function voltageVolts(measurement: RepairMeasurementEvidence): number | undefined {
  const value = parseNumber(measurement);
  if (value === undefined) return undefined;
  const text = valueAndUnitText(measurement);
  if (includesAny(text, ["mv", "millivolt"])) return value / 1000;
  return value;
}

function hasGroundTarget(text: string): boolean {
  return includesAny(text, ["ground", "gnd", "0v"]);
}

function hasPowerTarget(text: string): boolean {
  return includesAny(text, ["power", "rail", "vbus", "5v", "3v3", "3.3v", "12v", "vin", "vcc", "batt", "battery", "input", "usb"]);
}

function hasPowerGroundTarget(text: string): boolean {
  return hasGroundTarget(text) && hasPowerTarget(text);
}

function hasRailTarget(text: string): boolean {
  return includesAny(text, ["rail", "vbus", "5v", "3v3", "3.3v", "12v", "vin", "vcc", "batt", "battery", "input", "usb power"]);
}

function hasNegatedShort(text: string): boolean {
  return includesAny(text, ["no short", "no-short", "not short", "not a short", "no beep", "open circuit", "open to ground"]);
}

function hasPositiveText(text: string): boolean {
  return includesAny(text, [
    "pass",
    "passed",
    "ok",
    "stable",
    "within",
    "normal",
    "works",
    "working",
    "boots",
    "booted",
    "enumerates",
    "detected",
    "signal present",
    "output present",
    "expected",
    "no short",
    "no-short",
    "open circuit",
  ]);
}

function isShortFailureMeasurement(measurement: RepairMeasurementEvidence): boolean {
  const text = textOf(measurement);
  if (hasNegatedShort(text)) return false;
  if (includesAny(text, ["dead short", "short to ground", "shorted to ground", "shorted rail", "0 ohm", "0Ω", "0.0 ohm"])) return true;

  const category = categoryForMeasurement(measurement);
  if ((category === "resistance" || category === "continuity") && hasPowerGroundTarget(text)) {
    const ohms = resistanceOhms(measurement);
    if (ohms !== undefined && ohms <= 1) return true;
    if (category === "continuity" && includesAny(text, ["beep", "closed", "continuity present"])) return true;
  }
  return false;
}

function isDangerousFailureMeasurement(measurement: RepairMeasurementEvidence): boolean {
  const text = textOf(measurement);
  return isShortFailureMeasurement(measurement)
    || includesAny(text, ["overcurrent", "over-current", "excess current", "smoke", "burning", "hot", "thermal shutdown", "sparking"]);
}

function hasMeasurementFailure(measurement: RepairMeasurementEvidence): boolean {
  const text = textOf(measurement);
  if (isShortFailureMeasurement(measurement) || isDangerousFailureMeasurement(measurement)) return true;
  if (includesAny(text, ["fail", "failed", "unstable", "brownout", "drops out", "collapses", "no boot", "does not boot", "not booting", "not working"])) return true;

  const category = categoryForMeasurement(measurement);
  if (category === "voltage" && hasRailTarget(text)) {
    const volts = voltageVolts(measurement);
    if (volts !== undefined && volts <= 0.1) return true;
  }
  return false;
}

function isPositiveMeasurement(measurement: RepairMeasurementEvidence): boolean {
  return hasPositiveText(textOf(measurement)) && !hasMeasurementFailure(measurement);
}

function hasBadShort(measurements: RepairMeasurementEvidence[]): boolean {
  return measurements.some(isShortFailureMeasurement);
}

function hasNoShortEvidence(measurements: RepairMeasurementEvidence[]): boolean {
  return measurements.some((measurement) => {
    const text = textOf(measurement);
    const category = categoryForMeasurement(measurement);
    if ((category !== "continuity" && category !== "resistance") || !hasPowerGroundTarget(text) || hasMeasurementFailure(measurement)) {
      return false;
    }
    const ohms = resistanceOhms(measurement);
    if (ohms !== undefined) return ohms > 10;
    return hasNegatedShort(text) || (hasPositiveText(text) && includesAny(text, ["no short", "no-short", "resistance to ground"]));
  });
}

function hasStableRailEvidence(measurements: RepairMeasurementEvidence[]): boolean {
  return measurements.some((measurement) => {
    const text = textOf(measurement);
    if (categoryForMeasurement(measurement) !== "voltage" || !hasRailTarget(text) || hasMeasurementFailure(measurement)) return false;
    const volts = voltageVolts(measurement);
    if (volts !== undefined && volts > 0.1 && volts < 60 && hasPositiveText(text)) return true;
    return hasPositiveText(text) && includesAny(text, ["stable", "within", "ok", "pass", "normal"]);
  });
}

function hasFunctionalEvidence(measurements: RepairMeasurementEvidence[]): boolean {
  return measurements.some((measurement) => {
    const text = textOf(measurement);
    if (categoryForMeasurement(measurement) !== "functional" || hasMeasurementFailure(measurement)) return false;
    return hasPositiveText(text);
  });
}

function measurementDiagnostics(measurements: RepairMeasurementEvidence[], noShort: boolean, stableRail: boolean, functional: boolean): {
  passed: number;
  failed: number;
  contradictory: number;
  quality: MeasurementQuality;
} {
  const failed = measurements.filter(hasMeasurementFailure).length;
  const passed = measurements.filter(isPositiveMeasurement).length;
  const badShort = hasBadShort(measurements);
  const contradictory = (badShort && noShort ? 1 : 0) + (failed && (noShort || stableRail || functional) ? 1 : 0);
  const typed = measurements.filter((measurement) => Boolean(categoryFromType(measurement.type))).length;
  const quality: MeasurementQuality = contradictory
    ? "contradictory"
    : failed
      ? "failed"
      : !measurements.length
        ? "none"
        : typed === measurements.length
          ? "bench_recorded"
          : typed
            ? "typed"
            : "text_only";
  return { passed, failed, contradictory, quality };
}

function requiredMeasurements(
  checks: { noShort: boolean; stableRail: boolean; functional: boolean; failed: number; contradictory: number },
  evidenceTrust?: BoardEvidenceTrust | null,
): string[] {
  const required = new Set<string>();
  if (checks.failed || checks.contradictory) required.add("Resolve failed or contradictory measurements before authorizing repair decisions.");
  if (!checks.noShort) required.add("Continuity/no-short check on power rails and ground.");
  if (!checks.noShort) required.add("Unpowered resistance measurement between power input and ground.");
  if (!checks.stableRail) required.add("Current-limited voltage measurement on expected rails.");
  if (!checks.functional) required.add("Functional output or symptom reproduction test after safe power-up.");
  for (const item of evidenceTrust?.required_evidence ?? []) {
    const text = item.toLowerCase();
    const isMeasurement = includesAny(text, ["measurement", "continuity", "resistance", "voltage", "power-on", "power on", "current limit", "rail", "functional"]);
    if (!isMeasurement) continue;
    if (checks.noShort && includesAny(text, ["continuity", "resistance", "power and ground"])) continue;
    if (checks.stableRail && includesAny(text, ["voltage", "rail", "current limit"])) continue;
    if (checks.functional && includesAny(text, ["functional", "power-on", "power on"])) continue;
    required.add(item);
  }
  return Array.from(required).slice(0, 10);
}

export function evaluateRepairAuthority(input: RepairAuthorityInput): RepairAuthority {
  const measurements = input.measurements ?? [];
  const counts = categoryCounts(measurements);
  const measurementCount = measurements.length;
  const badShort = hasBadShort(measurements);
  const noShort = hasNoShortEvidence(measurements);
  const stableRail = hasStableRailEvidence(measurements);
  const functional = hasFunctionalEvidence(measurements);
  const diagnostics = measurementDiagnostics(measurements, noShort, stableRail, functional);
  const dangerousFailure = measurements.some(isDangerousFailureMeasurement);
  const trustScore = input.evidenceTrust?.score ?? 0;
  const hazard = input.verifierSafety === "hazard"
    || input.boardEvidence?.components?.some((component) => component.safety === "hazard")
    || input.boardEvidence?.damage?.some((damage) => damage.severity === "critical");

  const gates: RepairAuthorityGate[] = [
    input.evidenceTrust && trustScore >= 0.68
      ? gate("visual_evidence", "Visual evidence", "pass", trustScore, `Board evidence trust is ${Math.round(trustScore * 100)}%.`)
      : gate("visual_evidence", "Visual evidence", trustScore >= 0.42 ? "warn" : "fail", trustScore, "Visual evidence is not strong enough by itself."),
    measurementCount
      ? gate("measurement_presence", "Measurement presence", "pass", Math.min(1, measurementCount / 4), `${measurementCount} measurement(s) recorded across ${Object.values(counts).filter(Boolean).length} typed category/categories.`)
      : gate("measurement_presence", "Measurement presence", "fail", 0, "No bench measurements are attached."),
    diagnostics.failed || diagnostics.contradictory
      ? gate("measurement_integrity", "Measurement integrity", "fail", 0, `${diagnostics.failed} failed and ${diagnostics.contradictory} contradictory measurement signal(s) found.`)
      : measurementCount
        ? gate("measurement_integrity", "Measurement integrity", "pass", diagnostics.quality === "bench_recorded" ? 1 : 0.75, `Measurement quality is ${diagnostics.quality}.`)
        : gate("measurement_integrity", "Measurement integrity", "fail", 0, "No measurement integrity can be established without readings."),
    noShort
      ? gate("no_short", "No-short evidence", "pass", 1, "Power/ground no-short evidence is recorded.")
      : gate("no_short", "No-short evidence", badShort ? "fail" : "warn", badShort ? 0 : 0.35, badShort ? "A short-like measurement was recorded." : "No explicit no-short evidence yet."),
    stableRail
      ? gate("rail_voltage", "Rail voltage", "pass", 1, "Rail voltage evidence is recorded.")
      : gate("rail_voltage", "Rail voltage", "warn", 0.35, "No current-limited rail voltage measurement yet."),
    functional
      ? gate("functional_test", "Functional test", "pass", 1, "Functional/signal evidence is recorded.")
      : gate("functional_test", "Functional test", "warn", 0.35, "No functional output or symptom reproduction test yet."),
    input.verifierStatus && !["blocked", "safety_hold"].includes(input.verifierStatus)
      ? gate("verifier", "Verifier", input.verifierStatus === "pass_with_gates" || input.verifierStatus === "needs_review" ? "pass" : "warn", 0.8, `Verifier status is ${input.verifierStatus}.`)
      : gate("verifier", "Verifier", "warn", 0.4, "Deep verifier has not approved the evidence package yet."),
    hazard
      ? gate("safety", "Safety", "fail", 0, "Hazard or critical damage evidence blocks repair authority.")
      : gate("safety", "Safety", "pass", 1, "No hazard-level evidence is present."),
  ];

  const weighted = gates.reduce((total, item) => {
    const statusWeight = item.status === "pass" ? 1 : item.status === "warn" ? 0.55 : 0;
    return total + item.score * statusWeight;
  }, 0) / gates.length;
  const score = Number(Math.max(0, Math.min(1, weighted)).toFixed(2));

  let status: RepairAuthorityStatus = "needs_measurements";
  if (hazard || badShort || diagnostics.failed || diagnostics.contradictory) {
    status = "blocked";
  } else if (!measurementCount) {
    status = "visual_only";
  } else if (noShort && stableRail && functional && score >= 0.78) {
    status = "authoritative_low_risk";
  } else if ((noShort || stableRail) && measurementCount >= 2) {
    status = "measurement_backed";
  }

  const safety_level: SafetyLevel = hazard || badShort || dangerousFailure
    ? "hazard"
    : status === "visual_only" || status === "blocked"
      ? "caution"
      : input.verifierSafety ?? "caution";
  const required = requiredMeasurements({
    noShort,
    stableRail,
    functional,
    failed: diagnostics.failed,
    contradictory: diagnostics.contradictory,
  }, input.evidenceTrust);
  return {
    status,
    score,
    summary: status === "authoritative_low_risk"
      ? "Measurement-backed low-risk repair authority is available for the checked claims."
      : status === "measurement_backed"
        ? "Some repair claims are measurement-backed, but more checks are required before authoritative decisions."
        : status === "visual_only"
          ? "This is still visual-only guidance; do not treat repair or reuse decisions as authoritative."
          : status === "blocked"
            ? "Repair authority is blocked by safety or short-circuit evidence."
            : "Bench measurements are required before this can become repair-authoritative.",
    safety_level,
    supported_decisions: status === "authoritative_low_risk"
      ? ["low-risk repair decision for measured claims", "documented reuse decision", "case outcome recommendation"]
      : status === "measurement_backed"
        ? ["measurement-backed triage", "next diagnostic step selection", "limited low-voltage reuse planning"]
        : status === "blocked"
          ? ["human safety review", "fault isolation planning"]
          : ["visual triage", "measurement checklist generation", "human review"],
    blocked_decisions: status === "authoritative_low_risk"
      ? ["unmeasured hidden-net claims", "high-voltage or lithium-pack repair authority without qualified procedure"]
      : ["safe-to-power authorization", "safe-to-cut authorization", "final repair diagnosis", "production repair release"],
    required_measurements: required,
    measurement_summary: { count: measurementCount, ...counts, ...diagnostics },
    gates,
  };
}
