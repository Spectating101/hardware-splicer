import type { SafetyLevel, SalvageModule } from "@/lib/cad-types";

export const BOARD_EVIDENCE_SCHEMA_VERSION = "board_evidence.v1" as const;

export type BoardEvidenceMode =
  | "native_vision"
  | "local_cv_ocr"
  | "evidence_bridge"
  | "text_reasoner"
  | "manual";

export type BoardEvidenceKind = SalvageModule["kind"] | "ic" | "module" | "damaged_area" | "test_point";

export interface NormalizedBbox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface BoardEvidenceImage {
  mediaType?: string;
  sizeBytes?: number;
  sha256?: string;
  width?: number;
  height?: number;
  description?: string;
}

export interface BoardEvidenceComponent {
  id: string;
  label: string;
  kind: BoardEvidenceKind | string;
  confidence?: number;
  bbox?: NormalizedBbox;
  markings?: string[];
  role?: string;
  safety?: SafetyLevel;
  evidence?: string[];
  warnings?: string[];
}

export interface BoardEvidenceRegion {
  id: string;
  label: string;
  kind: "power" | "logic" | "connector_bank" | "rf" | "damage" | "unknown" | string;
  confidence?: number;
  bbox?: NormalizedBbox;
  evidence?: string[];
}

export interface BoardEvidenceDamage {
  id: string;
  label: string;
  severity: "cosmetic" | "suspect" | "critical" | "unknown";
  bbox?: NormalizedBbox;
  evidence?: string[];
  recommended_checks?: string[];
}

export interface BoardEvidenceConnector {
  id: string;
  label: string;
  confidence?: number;
  bbox?: NormalizedBbox;
  probable_pins?: Array<{ name: string; role?: string; voltage?: string }>;
  evidence?: string[];
}

export interface BoardEvidenceTestPoint {
  id: string;
  label: string;
  confidence?: number;
  bbox?: NormalizedBbox;
  expected_signal?: string;
  evidence?: string[];
}

export interface BoardEvidenceSalvageCandidate {
  id: string;
  label: string;
  kind: string;
  confidence?: number;
  bbox?: NormalizedBbox;
  rationale?: string;
  required_checks?: string[];
  risks?: string[];
}

export interface BoardEvidence {
  schema_version: typeof BOARD_EVIDENCE_SCHEMA_VERSION;
  source: {
    provider: string;
    mode: BoardEvidenceMode;
    model?: string;
    raw_pixels_sent_to_provider: boolean;
    backend_ok?: boolean;
    generated_at: string;
    cost_usd_estimate?: number;
    cache_key?: string;
  };
  image?: BoardEvidenceImage;
  components: BoardEvidenceComponent[];
  markings: Array<{ text: string; component_id?: string; confidence?: number; bbox?: NormalizedBbox }>;
  regions: BoardEvidenceRegion[];
  damage: BoardEvidenceDamage[];
  connectors: BoardEvidenceConnector[];
  test_points: BoardEvidenceTestPoint[];
  salvage_candidates: BoardEvidenceSalvageCandidate[];
  recommended_checks: string[];
  uncertainty: {
    level: "low" | "medium" | "high";
    reasons: string[];
    missing_evidence: string[];
    next_actions: string[];
  };
}

export type EvidenceGateStatus = "pass" | "warn" | "fail";

export interface BoardEvidenceTrustGate {
  id: string;
  label: string;
  status: EvidenceGateStatus;
  score: number;
  reason: string;
}

export interface BoardEvidenceTrust {
  score: number;
  level: "high" | "medium" | "low";
  launch_readiness: "private_alpha_candidate" | "experimental_mvp" | "demo_only" | "blocked";
  summary: string;
  supported_uses: string[];
  blocked_uses: string[];
  strengths: string[];
  blockers: string[];
  required_evidence: string[];
  gates: BoardEvidenceTrustGate[];
}

type JsonRecord = Record<string, unknown>;

export const BOARD_EVIDENCE_OUTPUT_INSTRUCTION = `
Also include a "board_evidence" object when image or board evidence is present.
Use schema_version "${BOARD_EVIDENCE_SCHEMA_VERSION}" and normalize all boxes to 0-1 image coordinates.
The board_evidence object must use these array keys exactly: components, markings, regions, damage, connectors, test_points, salvage_candidates.
Do not put localized parts under a board_evidence.detections key.
Capture components, markings, regions, damage, connectors, test_points, salvage_candidates,
recommended_checks, and uncertainty. Prefer "unknown" plus missing_evidence over invented part IDs,
pinouts, nets, voltage rails, or repair certainty. Do not use product knowledge to name exact ICs
unless their markings are legible in the image.
`.trim();

function asRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function numberValue(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function stringArray(value: unknown): string[] {
  return asArray(value)
    .map((entry) => stringValue(entry))
    .filter((entry): entry is string => Boolean(entry));
}

function uniqueStrings(values: Array<string | undefined>): string[] {
  return values
    .filter((entry): entry is string => Boolean(entry))
    .filter((entry, index, all) => all.indexOf(entry) === index);
}

function normalizedBox(x: number, y: number, w: number, h: number): NormalizedBbox {
  return {
    x: Number(Math.max(0, Math.min(1, x)).toFixed(4)),
    y: Number(Math.max(0, Math.min(1, y)).toFixed(4)),
    w: Number(Math.max(0, Math.min(1, w)).toFixed(4)),
    h: Number(Math.max(0, Math.min(1, h)).toFixed(4)),
  };
}

export function normalizeEvidenceBbox(raw: unknown, width?: number, height?: number): NormalizedBbox | undefined {
  const record = asRecord(raw);
  const objectX = numberValue(record.x);
  const objectY = numberValue(record.y);
  const objectW = numberValue(record.w);
  const objectH = numberValue(record.h);
  if (objectX !== undefined && objectY !== undefined && objectW !== undefined && objectH !== undefined) {
    return normalizedBox(objectX, objectY, objectW, objectH);
  }

  const left = numberValue(record.left);
  const top = numberValue(record.top);
  const right = numberValue(record.right);
  const bottom = numberValue(record.bottom);
  if (left !== undefined && top !== undefined && right !== undefined && bottom !== undefined) {
    return normalizeEvidenceBbox([left, top, right, bottom], width, height);
  }
  if (Array.isArray(record.bbox_2d)) return normalizeEvidenceBbox(record.bbox_2d, width, height);

  const bbox = Array.isArray(raw) ? raw.map(numberValue) : [];
  if (bbox.length !== 4 || bbox.some((value) => value === undefined)) return undefined;
  const [x1, y1, x2, y2] = bbox as number[];
  if (width && height && Math.max(x1, y1, x2, y2) > 1) {
    return normalizedBox(x1 / width, y1 / height, (x2 - x1) / width, (y2 - y1) / height);
  }
  if (x2 <= x1 || y2 <= y1) return normalizedBox(x1, y1, x2, y2);
  return normalizedBox(x1, y1, x2 - x1, y2 - y1);
}

function uncertaintyLevel(reviewRequired: boolean, quality?: string, componentCount = 0): "low" | "medium" | "high" {
  if (componentCount === 0) return "high";
  if (reviewRequired) return "medium";
  if (!quality) return "medium";
  if (["low", "candidate", "unknown"].includes(quality.toLowerCase())) return "high";
  if (quality.toLowerCase() === "medium") return "medium";
  return "low";
}

export function buildBoardEvidenceFromLocalAnalyzer(opts: {
  analysis: unknown;
  image?: BoardEvidenceImage;
  backendOk: boolean;
  cacheKey?: string;
}): BoardEvidence {
  const root = asRecord(opts.analysis);
  const detections = asArray(root.detections);
  const quality = stringValue(root.detection_quality);
  const reviewRequired = Boolean(root.review_required);
  const certainty = asRecord(root.certainty);
  const missingEvidence = stringArray(certainty.missing_evidence);
  const nextActions = stringArray(certainty.next_actions);
  const width = opts.image?.width;
  const height = opts.image?.height;

  const components: BoardEvidenceComponent[] = detections.map((entry, index) => {
    const det = asRecord(entry);
    const text = stringValue(det.text);
    const id = String(det.id ?? `D${index + 1}`);
    return {
      id,
      label: text ?? stringValue(det.class_name) ?? "unknown",
      kind: stringValue(det.class_name) ?? "unknown",
      confidence: numberValue(det.confidence),
      bbox: normalizeEvidenceBbox(det.bbox, width, height),
      markings: text ? [text] : [],
      evidence: [
        stringValue(det.method) ? `method:${stringValue(det.method)}` : undefined,
        numberValue(det.quality_score) !== undefined ? `quality:${numberValue(det.quality_score)}` : undefined,
      ].filter((item): item is string => Boolean(item)),
    };
  });

  const markings = [
    ...stringArray(root.markings).map((text) => ({ text })),
    ...components.flatMap((component) => (component.markings ?? []).map((text) => ({
      text,
      component_id: component.id,
      confidence: component.confidence,
      bbox: component.bbox,
    }))),
  ].filter((entry, index, all) => all.findIndex((candidate) => candidate.text === entry.text) === index);

  const reasons = [
    quality ? `local analyzer detection_quality=${quality}` : undefined,
    reviewRequired ? "local analyzer marked review_required=true" : undefined,
    !opts.backendOk ? "local analyzer failed or returned unusable JSON" : undefined,
  ].filter((entry): entry is string => Boolean(entry));

  return {
    schema_version: BOARD_EVIDENCE_SCHEMA_VERSION,
    source: {
      provider: "local_analyzer",
      mode: "local_cv_ocr",
      raw_pixels_sent_to_provider: false,
      backend_ok: opts.backendOk,
      generated_at: new Date().toISOString(),
      cache_key: opts.cacheKey,
    },
    image: opts.image,
    components,
    markings,
    regions: [],
    damage: [],
    connectors: components
      .filter((component) => String(component.kind).toLowerCase().includes("connector"))
      .map((component) => ({
        id: component.id,
        label: component.label,
        confidence: component.confidence,
        bbox: component.bbox,
        evidence: component.evidence,
      })),
    test_points: [],
    salvage_candidates: [],
    recommended_checks: nextActions.length ? nextActions : ["Verify component labels against the board photo before reuse."],
    uncertainty: {
      level: uncertaintyLevel(reviewRequired, quality, components.length),
      reasons,
      missing_evidence: missingEvidence,
      next_actions: nextActions,
    },
  };
}

export function isBoardEvidence(value: unknown): value is BoardEvidence {
  const record = asRecord(value);
  return record.schema_version === BOARD_EVIDENCE_SCHEMA_VERSION;
}

function safetyValue(value: unknown): SafetyLevel | undefined {
  const raw = stringValue(value);
  return raw === "safe" || raw === "caution" || raw === "hazard" ? raw : undefined;
}

function kindFromLabel(label: string): string {
  const normalized = label.toLowerCase();
  if (normalized.includes("connector") || normalized.includes("header") || normalized.includes("usb") || normalized.includes("jack")) return "connector";
  if (normalized.includes("resistor") || normalized === "res" || normalized.startsWith("r")) return "passive";
  if (normalized.includes("capacitor") || normalized === "cap" || normalized.startsWith("c")) return "passive";
  if (normalized.includes("ic") || normalized.includes("chip") || normalized.includes("mcu") || normalized.includes("controller")) return "ic";
  if (normalized.includes("test point") || normalized.startsWith("tp")) return "test_point";
  if (normalized.includes("damage") || normalized.includes("burn")) return "damaged_area";
  return "unknown";
}

function componentFromRecord(entry: unknown, index: number, prefix: string, width?: number, height?: number): BoardEvidenceComponent {
  const component = asRecord(entry);
  const label = (
    stringValue(component.label) ??
    stringValue(component.name) ??
    stringValue(component.type) ??
    stringValue(component.class_name) ??
    stringValue(component.part_number) ??
    stringValue(component.ocr_text) ??
    stringValue(component.text) ??
    "unknown"
  );
  const id = String(component.id ?? component.refdes ?? component.reference ?? `${prefix}${index + 1}`);
  const marking = (
    stringValue(component.marking) ??
    stringValue(component.text) ??
    stringValue(component.ocr_text) ??
    stringValue(component.part_number)
  );
  const evidence = uniqueStrings([
    ...stringArray(component.evidence),
    stringValue(component.source),
    stringValue(component.method) ? `method:${stringValue(component.method)}` : undefined,
  ]);
  return {
    id,
    label,
    kind: stringValue(component.kind) ?? stringValue(component.class_name) ?? kindFromLabel(label),
    confidence: numberValue(component.confidence),
    bbox: normalizeEvidenceBbox(component.bbox ?? component.bbox_2d, width, height),
    markings: uniqueStrings([...stringArray(component.markings), marking]),
    role: stringValue(component.role) ?? stringValue(component.description),
    safety: safetyValue(component.safety),
    evidence,
    warnings: stringArray(component.warnings),
  };
}

function markingFromRecord(entry: unknown, componentId?: string, confidence?: number, bbox?: NormalizedBbox, width?: number, height?: number): BoardEvidence["markings"][number] | null {
  if (typeof entry === "string") {
    const text = stringValue(entry);
    return text ? { text, component_id: componentId, confidence, bbox } : null;
  }
  const record = asRecord(entry);
  const text = stringValue(record.text) ?? stringValue(record.marking) ?? stringValue(record.ocr_text) ?? stringValue(record.part_number);
  if (!text) return null;
  return {
    text,
    component_id: stringValue(record.component_id) ?? stringValue(record.componentId) ?? componentId,
    confidence: numberValue(record.confidence) ?? confidence,
    bbox: normalizeEvidenceBbox(record.bbox ?? record.bbox_2d, width, height) ?? bbox,
  };
}

function connectorFromRecord(entry: unknown, index: number, width?: number, height?: number): BoardEvidenceConnector {
  const record = asRecord(entry);
  const label = stringValue(record.label) ?? stringValue(record.name) ?? stringValue(record.type) ?? "unknown connector";
  return {
    id: String(record.id ?? `J${index + 1}`),
    label,
    confidence: numberValue(record.confidence),
    bbox: normalizeEvidenceBbox(record.bbox ?? record.bbox_2d, width, height),
    probable_pins: asArray(record.probable_pins ?? record.pins).map((pin) => {
      const pinRecord = asRecord(pin);
      return {
        name: stringValue(pinRecord.name) ?? "unknown",
        role: stringValue(pinRecord.role),
        voltage: stringValue(pinRecord.voltage),
      };
    }),
    evidence: stringArray(record.evidence),
  };
}

function regionFromRecord(entry: unknown, index: number, width?: number, height?: number): BoardEvidenceRegion {
  const record = asRecord(entry);
  const label = stringValue(record.label) ?? stringValue(record.name) ?? stringValue(record.type) ?? "unknown region";
  return {
    id: String(record.id ?? `R${index + 1}`),
    label,
    kind: stringValue(record.kind) ?? stringValue(record.type) ?? "unknown",
    confidence: numberValue(record.confidence),
    bbox: normalizeEvidenceBbox(record.bbox ?? record.bbox_2d, width, height),
    evidence: stringArray(record.evidence),
  };
}

function damageFromRecord(entry: unknown, index: number, width?: number, height?: number): BoardEvidenceDamage {
  const record = asRecord(entry);
  const severity = stringValue(record.severity);
  return {
    id: String(record.id ?? `X${index + 1}`),
    label: stringValue(record.label) ?? stringValue(record.type) ?? "unknown damage",
    severity: severity === "cosmetic" || severity === "suspect" || severity === "critical" || severity === "unknown" ? severity : "unknown",
    bbox: normalizeEvidenceBbox(record.bbox ?? record.bbox_2d, width, height),
    evidence: stringArray(record.evidence),
    recommended_checks: stringArray(record.recommended_checks),
  };
}

function testPointFromRecord(entry: unknown, index: number, width?: number, height?: number): BoardEvidenceTestPoint {
  const record = asRecord(entry);
  return {
    id: String(record.id ?? `TP${index + 1}`),
    label: stringValue(record.label) ?? stringValue(record.name) ?? "unknown test point",
    confidence: numberValue(record.confidence),
    bbox: normalizeEvidenceBbox(record.bbox ?? record.bbox_2d, width, height),
    expected_signal: stringValue(record.expected_signal),
    evidence: stringArray(record.evidence),
  };
}

function salvageFromRecord(entry: unknown, index: number, width?: number, height?: number): BoardEvidenceSalvageCandidate {
  if (typeof entry === "string") {
    const label = stringValue(entry) ?? "unknown salvage candidate";
    return {
      id: `M${index + 1}`,
      label,
      kind: kindFromLabel(label),
      required_checks: [],
      risks: [],
    };
  }
  const record = asRecord(entry);
  const label = (
    stringValue(record.label) ??
    stringValue(record.name) ??
    stringValue(record.candidate) ??
    stringValue(record.component_id) ??
    stringValue(record.componentId) ??
    stringValue(record.type) ??
    "unknown salvage candidate"
  );
  return {
    id: String(record.id ?? `M${index + 1}`),
    label,
    kind: stringValue(record.kind) ?? kindFromLabel(label),
    confidence: numberValue(record.confidence),
    bbox: normalizeEvidenceBbox(record.bbox ?? record.bbox_2d, width, height),
    rationale: stringValue(record.rationale) ?? stringValue(record.description),
    required_checks: uniqueStrings([
      ...stringArray(record.required_checks),
      stringValue(record.extraction),
    ]),
    risks: stringArray(record.risks ?? record.warnings),
  };
}

function dedupeComponents(components: BoardEvidenceComponent[]): BoardEvidenceComponent[] {
  const seen = new Set<string>();
  return components.filter((component) => {
    const bbox = component.bbox ? `${component.bbox.x}:${component.bbox.y}:${component.bbox.w}:${component.bbox.h}` : "";
    const key = `${component.label}|${bbox || component.kind}`.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function dedupeSalvageCandidates(candidates: BoardEvidenceSalvageCandidate[]): BoardEvidenceSalvageCandidate[] {
  const seen = new Set<string>();
  return candidates.filter((candidate) => {
    const bbox = candidate.bbox ? `${candidate.bbox.x}:${candidate.bbox.y}:${candidate.bbox.w}:${candidate.bbox.h}` : "";
    const key = `${candidate.label}|${bbox || candidate.kind}`.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

const EXACT_PART_TOKEN_RE = /\b(?=[A-Z0-9-]*\d)[A-Z][A-Z0-9-]{4,}\b/g;
const UNSUPPORTED_EXACT_CLAIM_WARNING = "Unsupported exact part claim: readable marking evidence is required before trusting exact IC/manufacturer IDs.";

function normalizedClaimText(value: string): string {
  return value.toUpperCase().replace(/[^A-Z0-9]+/g, "");
}

function exactPartTokens(text: string | undefined): string[] {
  if (!text) return [];
  const matches = text.toUpperCase().match(EXACT_PART_TOKEN_RE) ?? [];
  return uniqueStrings(matches.filter((token) => token.length >= 5));
}

function markingTexts(evidence: Pick<BoardEvidence, "components" | "markings">): string[] {
  return uniqueStrings([
    ...asArray(evidence.markings)
      .map((entry) => stringValue(asRecord(entry).text))
      .filter((entry): entry is string => Boolean(entry)),
    ...asArray(evidence.components).flatMap((component) => stringArray(asRecord(component).markings)),
  ]);
}

function tokenSupportedByMarking(token: string, markings: string[]): boolean {
  const normalizedToken = normalizedClaimText(token);
  return markings.some((marking) => {
    const normalizedMarking = normalizedClaimText(marking);
    return normalizedMarking.length >= 3
      && (normalizedMarking.includes(normalizedToken) || normalizedToken.includes(normalizedMarking));
  });
}

export function scrubUnsupportedExactPartClaims(text: string | undefined, evidence: Pick<BoardEvidence, "components" | "markings">): {
  text: string | undefined;
  unsupportedTokens: string[];
  warnings: string[];
} {
  if (!text) return { text, unsupportedTokens: [], warnings: [] };
  const markings = markingTexts(evidence);
  const unsupportedTokens = exactPartTokens(text).filter((token) => !tokenSupportedByMarking(token, markings));
  if (!unsupportedTokens.length) return { text, unsupportedTokens: [], warnings: [] };

  let scrubbed = text;
  for (const token of unsupportedTokens) {
    scrubbed = scrubbed.replace(new RegExp(`\\b${token.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}\\b`, "gi"), "unverified part ID");
  }
  return {
    text: scrubbed,
    unsupportedTokens,
    warnings: [UNSUPPORTED_EXACT_CLAIM_WARNING],
  };
}

function enforceExactClaimPolicy(evidence: BoardEvidence): BoardEvidence {
  const components = evidence.components.map((component) => {
    const labelScrub = scrubUnsupportedExactPartClaims(component.label, evidence);
    const roleScrub = scrubUnsupportedExactPartClaims(component.role, evidence);
    const unsupportedTokens = uniqueStrings([...labelScrub.unsupportedTokens, ...roleScrub.unsupportedTokens]);
    return {
      ...component,
      label: labelScrub.text ?? component.label,
      role: roleScrub.text ?? component.role,
      warnings: uniqueStrings([
        ...(component.warnings ?? []),
        ...labelScrub.warnings,
        ...roleScrub.warnings,
        unsupportedTokens.length ? `Unverified exact token(s): ${unsupportedTokens.join(", ")}` : undefined,
      ]),
    };
  });

  const salvage_candidates = evidence.salvage_candidates.map((candidate) => {
    const labelScrub = scrubUnsupportedExactPartClaims(candidate.label, { ...evidence, components });
    const rationaleScrub = scrubUnsupportedExactPartClaims(candidate.rationale, { ...evidence, components });
    const unsupportedTokens = uniqueStrings([...labelScrub.unsupportedTokens, ...rationaleScrub.unsupportedTokens]);
    return {
      ...candidate,
      label: labelScrub.text ?? candidate.label,
      rationale: rationaleScrub.text ?? candidate.rationale,
      risks: uniqueStrings([
        ...(candidate.risks ?? []),
        ...labelScrub.warnings,
        ...rationaleScrub.warnings,
        unsupportedTokens.length ? `Unverified exact token(s): ${unsupportedTokens.join(", ")}` : undefined,
      ]),
    };
  });

  const unsupportedExactClaims = [
    ...components.flatMap((component) => component.warnings ?? []),
    ...salvage_candidates.flatMap((candidate) => candidate.risks ?? []),
  ].some((warning) => warning.includes("Unsupported exact part claim") || warning.includes("Unverified exact token"));

  return {
    ...evidence,
    components,
    salvage_candidates,
    recommended_checks: uniqueStrings([
      ...evidence.recommended_checks,
      unsupportedExactClaims ? "Capture readable package markings before trusting exact IC, manufacturer, pinout, or datasheet claims." : undefined,
    ]),
    uncertainty: {
      ...evidence.uncertainty,
      missing_evidence: uniqueStrings([
        ...evidence.uncertainty.missing_evidence,
        unsupportedExactClaims ? "Readable marking evidence for exact part/manufacturer claims." : undefined,
      ]),
      reasons: uniqueStrings([
        ...evidence.uncertainty.reasons,
        unsupportedExactClaims ? "Exact-looking part claims were scrubbed because markings did not support them." : undefined,
      ]),
    },
  };
}

export function buildBoardEvidenceFromModelResult(opts: {
  result: unknown;
  provider: string;
  mode: BoardEvidenceMode;
  model?: string;
  rawPixelsSent: boolean;
  image?: BoardEvidenceImage;
  cacheKey?: string;
  costUsdEstimate?: number;
}): BoardEvidence {
  const result = asRecord(opts.result);
  const evidence = asRecord(result.board_evidence);
  const evidenceSource = asRecord(evidence.source);
  const width = opts.image?.width;
  const height = opts.image?.height;

  const componentInputs = [
    ...asArray(evidence.components),
    ...asArray(evidence.detections),
    ...asArray(result.components),
    ...asArray(result["components/modules"]),
  ];
  const components = dedupeComponents(componentInputs.map((entry, index) => componentFromRecord(entry, index, "C", width, height)));

  const markings = [
    ...asArray(evidence.markings).map((entry) => markingFromRecord(entry, undefined, undefined, undefined, width, height)).filter((entry): entry is BoardEvidence["markings"][number] => Boolean(entry)),
    ...components.flatMap((component) => (component.markings ?? []).map((text) => ({
      text,
      component_id: component.id,
      confidence: component.confidence,
      bbox: component.bbox,
    }))),
  ].filter((entry, index, all) => all.findIndex((candidate) => candidate.text === entry.text && candidate.component_id === entry.component_id) === index);

  const connectors = [
    ...asArray(evidence.connectors).map((entry, index) => connectorFromRecord(entry, index, width, height)),
    ...components
      .filter((component) => String(component.kind).toLowerCase().includes("connector"))
      .map((component) => ({
        id: component.id,
        label: component.label,
        confidence: component.confidence,
        bbox: component.bbox,
        evidence: component.evidence,
      })),
  ];

  const salvageCandidates = dedupeSalvageCandidates([
    ...asArray(evidence.salvage_candidates).map((entry, index) => salvageFromRecord(entry, index, width, height)),
    ...asArray(result.modules).map((entry, index) => salvageFromRecord(entry, index, width, height)),
  ]);

  const uncertainty = asRecord(evidence.uncertainty);
  const copiedLocalEvidence = stringValue(evidenceSource.provider) === "local_analyzer" && opts.provider !== "local_analyzer";

  const missingEvidence = [
    components.length || salvageCandidates.length ? undefined : "No model-localized components or salvage modules were returned.",
    copiedLocalEvidence ? "Model returned or copied local analyzer board_evidence; normalized output was rebuilt from model-level fields where possible." : undefined,
    ...stringArray(uncertainty.missing_evidence),
  ].filter((entry): entry is string => Boolean(entry));
  const reasons = uniqueStrings([
    copiedLocalEvidence ? "model board_evidence source was local_analyzer, not native model evidence" : undefined,
    ...stringArray(uncertainty.reasons),
  ]);
  const level = uncertainty.level === "low" || uncertainty.level === "medium" || uncertainty.level === "high"
    ? uncertainty.level
    : missingEvidence.length ? "high" : "medium";

  return enforceExactClaimPolicy({
    schema_version: BOARD_EVIDENCE_SCHEMA_VERSION,
    source: {
      provider: opts.provider,
      mode: opts.mode,
      model: opts.model,
      raw_pixels_sent_to_provider: opts.rawPixelsSent,
      generated_at: new Date().toISOString(),
      cost_usd_estimate: opts.costUsdEstimate,
      cache_key: opts.cacheKey,
    },
    image: asRecord(evidence.image).mediaType ? evidence.image as BoardEvidenceImage : opts.image,
    components,
    markings,
    regions: asArray(evidence.regions).map((entry, index) => regionFromRecord(entry, index, width, height)),
    damage: asArray(evidence.damage).map((entry, index) => damageFromRecord(entry, index, width, height)),
    connectors,
    test_points: asArray(evidence.test_points).map((entry, index) => testPointFromRecord(entry, index, width, height)),
    salvage_candidates: salvageCandidates,
    recommended_checks: uniqueStrings([
      ...stringArray(evidence.recommended_checks),
      ...stringArray(result.recommended_checks),
    ]),
    uncertainty: {
      level,
      reasons,
      missing_evidence: missingEvidence,
      next_actions: stringArray(uncertainty.next_actions),
    },
  });
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function roundedScore(value: number): number {
  return Number(clamp01(value).toFixed(2));
}

function gate(
  id: string,
  label: string,
  status: EvidenceGateStatus,
  score: number,
  reason: string,
): BoardEvidenceTrustGate {
  return { id, label, status, score: roundedScore(score), reason };
}

function gateScore(gates: BoardEvidenceTrustGate[]): number {
  if (!gates.length) return 0;
  const weights: Record<EvidenceGateStatus, number> = { pass: 1, warn: 0.55, fail: 0 };
  return gates.reduce((sum, item) => sum + (weights[item.status] * item.score), 0) / gates.length;
}

function withDefaults(items: string[], defaults: string[]): string[] {
  return uniqueStrings([...items, ...defaults]).slice(0, 10);
}

export function evaluateBoardEvidenceTrust(evidence: BoardEvidence): BoardEvidenceTrust {
  const components = asArray(evidence.components) as BoardEvidenceComponent[];
  const salvage = asArray(evidence.salvage_candidates) as BoardEvidenceSalvageCandidate[];
  const componentsWithBbox = components.filter((component) => Boolean(component.bbox)).length;
  const salvageWithBbox = salvage.filter((candidate) => Boolean(candidate.bbox)).length;
  const localizedCount = componentsWithBbox + salvageWithBbox;
  const visibleClaimCount = components.length + salvage.length;
  const markings = asArray(evidence.markings) as BoardEvidence["markings"];
  const connectors = asArray(evidence.connectors) as BoardEvidenceConnector[];
  const testPoints = asArray(evidence.test_points) as BoardEvidenceTestPoint[];
  const damage = asArray(evidence.damage) as BoardEvidenceDamage[];
  const uncertainty = asRecord(evidence.uncertainty);
  const highUncertainty = uncertainty?.level === "high";
  const source = asRecord(evidence.source);
  const rawPixels = source.raw_pixels_sent_to_provider === true;
  const sourceMode = stringValue(source.mode);
  const sourceProvider = stringValue(source.provider);
  const nativeVision = rawPixels && sourceMode === "native_vision";
  const copiedAnalyzerOnly = sourceProvider === "local_analyzer" || sourceMode === "local_cv_ocr";
  const safetyHold = damage.some((item) => item.severity === "critical")
    || components.some((item) => item.safety === "hazard");
  const unsupportedExactClaims = [
    ...components.flatMap((component) => component.warnings ?? []),
    ...salvage.flatMap((candidate) => candidate.risks ?? []),
  ].some((warning) => warning.includes("Unsupported exact part claim") || warning.includes("Unverified exact token"));

  const gates: BoardEvidenceTrustGate[] = [
    visibleClaimCount
      ? gate(
          "visible_localization",
          "Visible localization",
          localizedCount ? "pass" : "warn",
          localizedCount ? Math.min(1, localizedCount / 6) : 0.45,
          localizedCount
            ? `${localizedCount} localized visible item(s) include image-space boxes.`
            : `${visibleClaimCount} visible item(s) were named, but none has a usable box.`,
        )
      : gate("visible_localization", "Visible localization", "fail", 0, "No localized components or salvage candidates were returned."),
    nativeVision
      ? gate("native_pixels", "Native image evidence", "pass", 1, `${sourceProvider ?? "model"} received raw image pixels.`)
      : gate(
          "native_pixels",
          "Native image evidence",
          copiedAnalyzerOnly ? "warn" : "fail",
          copiedAnalyzerOnly ? 0.45 : 0.2,
          copiedAnalyzerOnly
            ? "Evidence came from local CV/OCR only; model-level visual reasoning should review it."
            : "No raw image evidence was confirmed for the model response.",
        ),
    markings.length
      ? gate("readable_markings", "Readable markings", "pass", Math.min(1, markings.length / 4), `${markings.length} marking(s) were captured.`)
      : gate("readable_markings", "Readable markings", "warn", 0.35, "No readable markings; exact part IDs and pinouts remain unsupported."),
    connectors.length || testPoints.length
      ? gate(
          "io_evidence",
          "Connector/test-point evidence",
          "pass",
          Math.min(1, (connectors.length + testPoints.length) / 4),
          `${connectors.length} connector(s), ${testPoints.length} test point(s).`,
        )
      : gate("io_evidence", "Connector/test-point evidence", "warn", 0.35, "No connectors or test points were localized for measurement planning."),
    highUncertainty
      ? gate("uncertainty", "Uncertainty disclosure", "warn", 0.45, "The evidence itself reports high uncertainty.")
      : gate("uncertainty", "Uncertainty disclosure", "pass", uncertainty.level === "low" ? 1 : 0.7, `Uncertainty is ${stringValue(uncertainty.level) ?? "medium"}.`),
    safetyHold
      ? gate("safety_gate", "Safety gate", "fail", 0, "Critical damage or hazard evidence requires safety hold.")
      : gate("safety_gate", "Safety gate", "pass", damage.length ? 0.75 : 1, damage.length ? `${damage.length} damage/risk region(s) should be reviewed.` : "No critical visual safety hold was detected."),
    unsupportedExactClaims
      ? gate("exact_claims", "Exact claim policy", "warn", 0.35, "Exact part/manufacturer claims were scrubbed because readable markings did not support them.")
      : gate("exact_claims", "Exact claim policy", "pass", 1, "No unsupported exact IC/manufacturer claim was detected."),
    gate("electrical_validation", "Electrical validation", "fail", 0, "Image-only evidence has no continuity, voltage, resistance, or power-on measurements."),
  ];

  const baseScore = gateScore(gates);
  const missingEvidence = stringArray(uncertainty.missing_evidence);
  const requiredEvidence = withDefaults(missingEvidence, [
    "Reverse-side photo or board file for hidden nets.",
    "Continuity checks for connector pins and suspected rails.",
    "Unpowered resistance check between power and ground before powering.",
    "Voltage measurements on known rails under current limit.",
    "Readable close-up crops for important IC markings.",
  ]);
  const blockers = [
    visibleClaimCount ? undefined : "No visible board elements were localized.",
    rawPixels ? undefined : "No confirmed native image pass for the reasoning model.",
    highUncertainty ? "High uncertainty from the board evidence." : undefined,
    safetyHold ? "Safety hold from hazard/critical damage evidence." : undefined,
    unsupportedExactClaims ? "Exact-looking part claims need readable marking evidence before they can be trusted." : undefined,
    "No electrical measurements are attached yet.",
  ].filter((item): item is string => Boolean(item));
  const strengths = [
    localizedCount ? `${localizedCount} localized item(s) can be reviewed on the image.` : undefined,
    nativeVision ? "Native vision model saw the raw board photo." : undefined,
    markings.length ? `${markings.length} marking(s) captured for follow-up.` : undefined,
    connectors.length ? `${connectors.length} connector(s) found for IO planning.` : undefined,
    salvage.length ? `${salvage.length} salvage candidate(s) generated.` : undefined,
  ].filter((item): item is string => Boolean(item));

  let launch_readiness: BoardEvidenceTrust["launch_readiness"] = "experimental_mvp";
  if (safetyHold || !visibleClaimCount) {
    launch_readiness = "blocked";
  } else if (!nativeVision || baseScore < 0.35) {
    launch_readiness = "demo_only";
  } else if (baseScore >= 0.68 && !highUncertainty && !unsupportedExactClaims && localizedCount >= 4 && (markings.length || connectors.length)) {
    launch_readiness = "private_alpha_candidate";
  }

  const score = roundedScore(baseScore);
  const level: BoardEvidenceTrust["level"] = score >= 0.68 ? "high" : score >= 0.42 ? "medium" : "low";
  const supported_uses = launch_readiness === "blocked"
    ? ["human review", "data capture triage"]
    : ["portfolio demo", "candidate component review", "salvage planning draft", "measurement checklist generation"];
  const blocked_uses = [
    "autonomous repair diagnosis",
    "safe-to-cut or safe-to-power authorization",
    "exact pinout/voltage claims without measurement",
    "production AOI release",
  ];

  return {
    score,
    level,
    launch_readiness,
    summary: launch_readiness === "private_alpha_candidate"
      ? "Strong image-grounded evidence for a private alpha, but electrical checks still gate reuse decisions."
      : launch_readiness === "experimental_mvp"
        ? "Useful image-grounded evidence for an experimental MVP; measurement evidence is required before trusting repair or reuse decisions."
        : launch_readiness === "demo_only"
          ? "Usable as a demo/capture artifact, but evidence is too thin for trusted board decisions."
          : "Blocked for trusted use until visible localization and safety evidence improve.",
    supported_uses,
    blocked_uses,
    strengths,
    blockers: blockers.slice(0, 8),
    required_evidence: requiredEvidence,
    gates,
  };
}
