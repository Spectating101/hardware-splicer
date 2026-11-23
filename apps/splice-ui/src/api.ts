const API_BASE: string =
  import.meta.env.VITE_API_BASE !== undefined
    ? import.meta.env.VITE_API_BASE
    : import.meta.env.DEV
      ? "/api"
      : "";

interface ErrorDetail {
  message?: string;
  error?: {
    message?: string;
  };
}

interface ErrorBody {
  detail?: string | ErrorDetail;
}

export type SceneGeometryStatus = "available" | "unavailable" | (string & {});

export interface SceneSummary {
  project_id: string;
  title: string;
  geometry_status: SceneGeometryStatus;
  revisions: unknown[];
  registered_cases?: string[];
}

export interface SceneRecord {
  path: string;
  label?: string;
  status?: string;
  data?: Record<string, unknown> | null;
}

export interface SceneRecordsResponse {
  records?: SceneRecord[];
}

export interface SceneManifestRevision {
  id: string;
  label?: string | null;
  glb?: string | null;
  parts?: string | null;
}

export interface SceneManifestSource {
  label?: string;
  href?: string | null;
  sha256?: string | null;
}

export interface SceneManifestCompare {
  base: string;
  target: string;
}

export interface SceneManifestFocus {
  part_id?: string;
  label?: string;
}

export interface SceneManifestTourStop {
  label: string;
  select?: string | null;
  revision?: string;
  explode: number;
  diff?: string;
}

export interface SceneManifest {
  schema?: "hardware_splicer.scene_manifest.v1" | (string & {});
  project_id: string;
  title: string;
  subtitle?: string | null;
  geometry_status?: SceneGeometryStatus;
  geometry_label?: string | null;
  geometry_note?: string | null;
  revisions?: SceneManifestRevision[];
  sources?: SceneManifestSource[];
  compare?: SceneManifestCompare | null;
  focus?: SceneManifestFocus | null;
  tour?: SceneManifestTourStop[] | null;
  [key: string]: unknown;
}

export interface HealthLlmPolicy {
  qwen_llm_first?: boolean;
}

export interface HealthResponse {
  ok?: boolean;
  version?: string;
  llm_policy?: HealthLlmPolicy | null;
}

export interface CatalogModulePin {
  id: string;
  label: string;
  role?: string;
}

export interface CatalogModule {
  id: string;
  label: string;
  category?: string;
  summary?: string;
  pins?: CatalogModulePin[];
}

export interface ModuleCatalogResponse {
  modules?: CatalogModule[];
}

export interface SpliceExample {
  id: string;
  label: string;
  goal: string;
  intake?: Record<string, unknown>;
}

export interface ExamplesResponse {
  examples?: SpliceExample[];
}

export interface DonorFixture {
  id: string;
  label: string;
  board_id?: string;
  headline?: string;
  intake_path?: string;
  suggested_uses?: string[];
}

export interface DonorFixturesResponse {
  fixtures?: DonorFixture[];
}

export interface ClarifierQuestion {
  id: string;
  prompt: string;
}

export interface ClarifyIntentResponse {
  enriched_intent?: Record<string, unknown> | null;
  questions?: ClarifierQuestion[];
  needs_clarification?: boolean;
  assumptions?: string[];
}

export interface SpliceAndBuildOptions {
  exportGerber?: boolean;
  outDir?: string | null;
}

export interface SpliceAndBuildResponse {
  [key: string]: unknown;
}

export interface SubmitJobOptions {
  exportGerber?: boolean;
  requestId?: string | null;
}

export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | (string & {});

export interface JobOptions {
  job_type?: "digital_study" | (string & {});
  payload?: {
    project_id?: string;
  };
}

export interface JobSummary {
  job_id: string;
  status?: JobStatus;
  project_name?: string | null;
  options?: JobOptions | null;
  error?: string | { message?: string } | null;
}

export interface FetchJobsOptions {
  status?: string | null;
  limit?: number;
}

export interface JobsListResponse {
  jobs?: JobSummary[];
}

export type BenchGateStatus = "closed" | "blocked" | (string & {});

export interface BenchGate {
  gate_id: string;
  status?: BenchGateStatus;
  critical?: boolean;
  prompt?: string;
  measurement?: {
    value?: string | number | null;
    unit?: string | null;
  } | null;
  requires_contract_edit?: boolean;
  interface_id?: string;
}

export type BenchEvidenceKind = "physical" | "simulated" | (string & {});

export interface BenchSubmissionApplied {
  ok?: boolean;
  reason?: string;
  error?: string;
  unresolved_fields?: string[];
}

export interface BenchSession {
  readiness?: unknown;
  open_gate_count?: number | null;
  critical_open_count?: number | null;
  power_on_authorized?: boolean | null;
  level?: string | null;
  gates?: BenchGate[];
  open_gates?: BenchGate[];
  simulated?: boolean | null;
  evidence_kind?: BenchEvidenceKind | null;
  physical_capture?: boolean | null;
  capture_provenance?: "physical" | (string & {}) | null;
  instrument_capture?: boolean | null;
  validated_physical_capture?: boolean | null;
  source?: string | null;
  project_name?: string | null;
  build_id?: string | null;
  evidence_integrations?: Record<string, unknown> | null;
  last_submission?: {
    applied?: BenchSubmissionApplied[];
  } | null;
  [key: string]: unknown;
}

export type BenchCaptureMeasurementKind = "voltage" | "current" | (string & {});

export interface BenchCaptureTemplateMeasurement {
  gate_id?: string;
  kind?: BenchCaptureMeasurementKind;
  target?: string;
  notes?: string;
  value?: string | number | null;
  unit?: string;
  status?: string;
  critical?: boolean;
}

export interface BenchCaptureTemplate {
  capture_id?: string;
  project_name?: string;
  build_id?: string;
  template_path?: string;
  instruments?: unknown[];
  artifacts?: Array<Record<string, unknown>>;
  policy?: unknown;
  measurements?: BenchCaptureTemplateMeasurement[];
}

export interface BenchCaptureTemplateResponse extends BenchCaptureTemplate {
  template?: BenchCaptureTemplate;
}

export interface BenchSubmitCaptureResponse {
  ok?: boolean;
  error?: string;
  mapped_count?: number;
  bench_session?: BenchSession | null;
}

export interface DrcFixup {
  edge_pad_extra_mm?: number;
  module_gap_extra_mm?: number;
  via_clearance_mm?: number;
  [key: string]: unknown;
}

export interface DrcFixAttempt {
  attempt: number;
  kicad_drc_errors: number;
  kicad_drc_warnings?: number;
  fix_buckets?: string[];
  drc_fixup?: DrcFixup | null;
}

export interface DrcViolation {
  severity?: string;
  type?: string;
  description?: string;
  message?: string;
}

export interface DesignQuality {
  kicad_drc_errors?: number | string | null;
  drc_errors?: number | string | null;
  kicad_drc_warnings?: number | string | null;
  drc_warnings?: number | string | null;
  copper_tier?: string | null;
  fab_recommendation?: string | null;
  compile_ok?: boolean | null;
  drc_pass?: boolean | null;
  build_ready?: boolean | null;
  fabrication_ready?: boolean | null;
  electrical_safety_pass?: boolean | null;
  circuit_readiness?: unknown;
  build_id?: string | null;
  has_kicad_pcb?: boolean | null;
  drc_fix_loop?: {
    resolved?: boolean;
    attempts?: DrcFixAttempt[];
  } | null;
  violations?: DrcViolation[];
  [key: string]: unknown;
}

export interface AgentLoopRound {
  round: number;
  mode?: string;
  kicad_drc_errors: number;
  kicad_drc_warnings?: number;
  violation_types?: string[];
  engine_drc_fix_loop?: {
    attempts?: unknown[];
  } | null;
}

export interface AgentLoopResult {
  manual_retries_used?: number;
  resolved?: boolean;
  final_kicad_drc_errors?: number | string | null;
  copper_tier?: string | null;
  fab_recommendation?: string | null;
  rounds?: AgentLoopRound[];
}

export interface BomLine {
  ref?: string;
  module_id?: string;
  description?: string;
  qty?: number | null;
  source?: string;
  jlc_lcsc?: string;
  jlc_mpn?: string;
}

export interface TopologyOperator {
  operator_id?: string;
  operator_type?: string;
  inputs?: string[];
  outputs?: string[];
}

export interface ProjectPackageGates {
  compile_ok?: boolean | null;
  kicad_drc_errors?: number | string | null;
  kicad_drc_warnings?: number | string | null;
  copper_tier?: string | null;
  fab_recommendation?: string | null;
  build_ready?: boolean | null;
  fabrication_ready?: boolean | null;
  open_gate_count?: number | string | null;
  critical_open_count?: number | string | null;
  power_on_authorized?: boolean | null;
  verdict?: "POWER_ON_AUTHORIZED" | (string & {}) | null;
  blockers?: string[];
  simulated?: boolean | null;
  evidence_kind?: BenchEvidenceKind | null;
  physical_capture?: boolean | null;
  capture_provenance?: "physical" | (string & {}) | null;
  instrument_capture?: boolean | null;
  validated_physical_capture?: boolean | null;
}

export interface ProjectPackage {
  build_dir?: string | null;
  info?: {
    project_name?: string | null;
    goal?: string | null;
    summary?: string | null;
    build_id?: string | null;
    archetype?: string | null;
    cost_estimate_usd?: number | null;
    clarifier?: { needs_clarification?: boolean } | null;
    assumptions?: string[];
  } | null;
  gates?: ProjectPackageGates | null;
  bom?: {
    lines?: BomLine[];
    line_count?: number;
    estimated_total_usd?: number | null;
  } | null;
  wiring?: {
    topology_operators?: TopologyOperator[];
    narrative_markdown?: string | null;
  } | null;
  instructions?: {
    assembly_steps?: Array<string | { body?: string; title?: string }>;
    bringup_markdown?: string | null;
  } | null;
  firmware_scaffold?: Record<string, unknown> | null;
  mechanism_pack?: Record<string, unknown> | null;
  mechatronics_authority?: Record<string, unknown> | null;
  mechatronics?: {
    firmware_scaffold?: Record<string, unknown> | null;
    mechanism_pack?: Record<string, unknown> | null;
    mechatronics_authority?: Record<string, unknown> | null;
  } | null;
  evidence_integrations?: Record<string, unknown> | null;
  [key: string]: unknown;
}

export interface StudioGraph {
  nodes?: unknown[];
  edges?: unknown[];
  phrase?: string;
  composeMode?: string;
}

export interface RequestFidelityMissingPart {
  module_id?: string;
  names?: string[] | null;
  requested?: number;
  in_design?: number;
}

export interface JobBuildResult {
  requirements_met?: boolean | null;
  build_dir?: string | null;
  project_name?: string | null;
  goal?: string | null;
  mode?: "salvage" | (string & {}) | null;
  project_package?: ProjectPackage | null;
  bench_session?: BenchSession | null;
  compose_result?: Record<string, unknown> | null;
  compose?: Record<string, unknown> | null;
  design_quality?: DesignQuality | null;
  agent_loop?: AgentLoopResult | null;
  salvage_package?: Record<string, unknown> | null;
  donor_context?: unknown;
  studio_graph?: StudioGraph | null;
  design_quality_gate?: {
    request_fidelity?: {
      status?: "mismatch" | (string & {}) | null;
      missing_parts?: RequestFidelityMissingPart[] | null;
    } | null;
  } | null;
  evidence_integrations?: Record<string, unknown> | null;
  [key: string]: unknown;
}

export interface JobResultResponse {
  ok?: boolean;
  result?: JobBuildResult | null;
}

export type ComposeMode = "llm_first" | (string & {});

export interface ComposeResponse {
  ok?: boolean;
  mode?: ComposeMode | null;
  compose_mode?: string | null;
  build_id?: string | null;
  build_dir?: string | null;
  out_dir?: string | null;
  phrase?: string | null;
  goal?: string | null;
  project_name?: string | null;
  wire_only?: boolean;
  module_ids?: string[];
  attempts?: unknown[];
  artifacts?: {
    kicad_pcb?: string | null;
    [key: string]: unknown;
  } | null;
  graph?: {
    nodes?: unknown[];
    wires?: unknown[];
    drc_fixup?: DrcFixup | null;
  } | null;
  design_quality?: DesignQuality | null;
  agent_loop?: AgentLoopResult | null;
  violations?: DrcViolation[];
  project_package?: ProjectPackage | null;
  [key: string]: unknown;
}

export interface ComposeAgentLoopOptions {
  maxManualRetries?: number;
  finalizePackage?: boolean;
  projectName?: string | null;
}

export interface RenderProjectPackageOptions {
  source?: string;
}

export interface RenderProjectPackageResponse {
  package: ProjectPackage;
}

export interface ComposePhraseOptions {
  allowLlmFirst?: boolean;
  exportGerber?: boolean;
  wireOnly?: boolean;
  moduleIds?: string[] | null;
}

export type BuildFileKind = "pcb" | "schematic" | (string & {});

export interface BuildFileEntry {
  relative: string;
  name: string;
  kind?: BuildFileKind;
}

export interface BuildFilesListResponse {
  files?: BuildFileEntry[];
}

export interface BuildFileContentResponse {
  content?: string;
}

export type IntegrationStatus =
  | "wired"
  | "core"
  | "opt_in"
  | "partial"
  | "documented"
  | "reference"
  | "planned"
  | (string & {});

export interface IntegrationCatalogItem {
  id: string;
  name: string;
  url: string;
  status: IntegrationStatus;
  claim: string;
  hook: string;
  layer: string;
  license: string;
  priority: string;
}

export interface IntegrationsCatalogResponse {
  thesis: string;
  wired_count: number;
  total_count: number;
  integrations: IntegrationCatalogItem[];
}

export type BuildArtifactKind = "human_view" | (string & {});

export interface BuildArtifactEntry {
  relative: string;
  label?: string;
  name?: string;
  kind?: BuildArtifactKind;
}

export interface BuildArtifactsListResponse {
  artifacts?: BuildArtifactEntry[];
}

export interface ExportCircuitJsonResponse {
  circuit_json?: unknown[] | null;
}

export interface RunBuildAutorouteResponse {
  autoroute?: {
    ok?: boolean;
    skipped?: boolean;
    reason?: string;
  } | null;
}

export interface FetchBuildBomOptions {
  enrich?: boolean;
}

export interface BuildBomResponse {
  lines?: BomLine[];
  line_count: number;
  source: string;
  jlc_enriched?: boolean;
}

export type FabArtifactStatus =
  | "present"
  | "missing"
  | "optional"
  | "planned"
  | (string & {});

export interface FabManifestArtifact {
  id: string;
  label: string;
  status?: FabArtifactStatus;
  present?: boolean;
  optional?: boolean;
  planned?: boolean;
  optional_note?: string;
}

export interface FabManifestResponse {
  present_count: number;
  optional_present_count?: number;
  note?: string;
  artifacts: FabManifestArtifact[];
}

export interface ExportBuildViewsResponse {
  ok?: boolean;
  skipped?: boolean;
  reason?: string;
}

export interface RecheckBuildOptions {
  refreshPackage?: boolean;
  exportViews?: boolean;
}

export interface RecheckBuildResponse {
  drc?: {
    skipped?: boolean;
    reason?: string;
    pass?: boolean;
    errors?: number | null;
    warnings?: number | null;
  } | null;
  [key: string]: unknown;
}

export interface ComposeCanvasOptions {
  wireOnly?: boolean;
  exportGerber?: boolean;
}

export interface NetlistCompileOptions {
  circuitJson?: unknown;
  netlist?: unknown;
  kicadNetlistText?: string;
  buildId?: string;
  exportGerber?: boolean;
}

export type NetlistFixtureType = "kicad_netlist" | (string & {});

export interface NetlistFixtureSummary {
  id: string;
  description?: string;
  module_ids?: string[];
  type?: NetlistFixtureType;
}

export interface NetlistFixturesResponse {
  fixtures?: NetlistFixtureSummary[];
}

export interface NetlistFixtureDetail {
  description?: string;
  kicad_netlist_text?: string;
  circuit_json?: unknown;
}

export interface QwenBoardVisionStatus {
  ready_for_live_model?: boolean;
  api_key_configured?: boolean;
  model?: string;
  provider?: string;
  model_rotation?: string[];
}

export interface VisionCapabilitiesResponse {
  circuit_ai?: {
    qwen_board_vision_status?: QwenBoardVisionStatus | null;
  } | null;
  qwen_board_vision_status?: QwenBoardVisionStatus | null;
}

export interface VisionEnrichOptions {
  apply?: boolean;
  live?: boolean;
}

export interface VisionEvidenceReport {
  candidates?: Array<{
    observations?: unknown[];
    vision_evidence_notes?: unknown[];
  }>;
  applied_notes?: unknown[];
  evidence_notes?: unknown[];
  applied?: boolean;
  apply_count?: number;
  mode?: string;
  provider?: string;
}

export interface VisionEnrichResponse {
  intake?: Record<string, unknown>;
  vision_evidence_report?: VisionEvidenceReport | null;
}

export type DonorVisionMode = "dry_run" | (string & {});

export interface DonorBoardVisionBlock {
  block_id?: string;
  name?: string;
  verdict?: string;
  notes?: string;
}

export interface DonorBoardVisionGate {
  gate_id?: string;
  name?: string;
  requirement?: string;
}

export interface DonorBoardVisionBoard {
  board_id?: string;
  mode?: DonorVisionMode;
  source_artifact?: string;
  analysis?: {
    mode?: DonorVisionMode;
  } | null;
  functional_salvage?: {
    reusable_blocks?: DonorBoardVisionBlock[];
    evidence_gates?: DonorBoardVisionGate[];
  } | null;
}

export interface DonorBoardVisionReport {
  applied_board_count?: number;
  boards?: DonorBoardVisionBoard[];
}

export interface DonorBoardVisionResponse {
  intake?: {
    circuit?: unknown;
    evidence_notes?: unknown;
    [key: string]: unknown;
  } | null;
  donor_board_vision_report?: DonorBoardVisionReport | null;
}

async function parseJson<T>(res: Response): Promise<T> {
  const body = (await res.json().catch(() => ({}))) as unknown;
  if (!res.ok) {
    const detail = (body as ErrorBody | null | undefined)?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.error?.message || detail?.message || res.statusText;
    throw new Error(message || `Request failed (${res.status})`);
  }
  return body as T;
}

export function sceneRevisionUrl(projectId: string, revision: string): string {
  return `${API_BASE}/v1/scenes/${encodeURIComponent(projectId)}/${encodeURIComponent(revision)}`;
}

export async function fetchScenes(signal?: AbortSignal): Promise<SceneSummary[]> {
  const res = await fetch(`${API_BASE}/v1/scenes`, { signal });
  return parseJson<SceneSummary[]>(res);
}

export async function fetchSceneRecords(projectId: string, signal?: AbortSignal): Promise<SceneRecordsResponse> {
  const res = await fetch(`${API_BASE}/v1/scenes/${encodeURIComponent(projectId)}/records`, { signal });
  return parseJson<SceneRecordsResponse>(res);
}

export async function fetchSceneManifest(projectId: string, signal?: AbortSignal): Promise<SceneManifest> {
  const res = await fetch(`${API_BASE}/v1/scenes/${encodeURIComponent(projectId)}`, { signal });
  return parseJson<SceneManifest>(res);
}

/** One pair of parts the fit engine measured: overlapping, touching, tight or near. */
export interface SceneFitPair {
  a: string;
  b: string;
  kind: "overlap" | "touching" | "tight" | "near";
  basis: [string, string];
  stand_in: boolean;
  gap_mm: number;
  precision_mm: number;
  overlap_mm3: number | null;
  overlap_computed: boolean;
}

/** GET /v1/scenes/{id}/{revision}/fit: the CAD model measured, never a physical result. */
export interface SceneFit {
  project_id: string;
  revision: string;
  schema: string;
  version: string;
  basis: string;
  size_mm: [number, number, number] | null;
  parts_measured: number;
  parts_unmatched: string[];
  pairs: SceneFitPair[];
  counts: Record<string, number>;
  not_computed: { what: string; parts: string[]; why: string }[];
  method: Record<string, unknown>;
}

export async function fetchSceneFit(projectId: string, revision: string, signal?: AbortSignal): Promise<SceneFit> {
  const res = await fetch(`${sceneRevisionUrl(projectId, revision)}/fit`, { signal });
  return parseJson<SceneFit>(res);
}

/** GET /v1/scenes/{id}/evidence: the records a scene lists, normalised by kind. */
export interface SceneEvidence {
  project_id: string;
  records: ({ kind: string; label: string; source: string; sha256?: string; error?: string } & Record<string, unknown>)[];
}

export async function fetchSceneEvidence(projectId: string, signal?: AbortSignal): Promise<SceneEvidence> {
  const res = await fetch(`${API_BASE}/v1/scenes/${encodeURIComponent(projectId)}/evidence`, { signal });
  return parseJson<SceneEvidence>(res);
}

/** One KiCad DRC/ERC violation, traced to the parts it touches. */
export interface KicadViolation {
  group: string;
  type: string | null;
  severity: string | null;
  description: string | null;
  items: string[];
  parts: string[];
  part_ids: string[];
}

export interface KicadReport {
  kicad_version: string | null;
  counts: Record<string, number>;
  total: number;
  violations: KicadViolation[];
}

/** GET /v1/scenes/{id}/{revision}/kicad: KiCad's own checks on the revision's board files. */
export interface SceneKicadChecks {
  project_id: string;
  revision: string;
  board: string;
  schematic: string | null;
  drc: KicadReport | null;
  erc: KicadReport | null;
}

export async function fetchSceneKicad(projectId: string, revision: string, signal?: AbortSignal): Promise<SceneKicadChecks> {
  const res = await fetch(`${sceneRevisionUrl(projectId, revision)}/kicad`, { signal });
  return parseJson<SceneKicadChecks>(res);
}

export type SceneDecisionKind = "needs_bench_test" | "accept_risk" | "waive" | "ask_agent";

export interface SceneDecision {
  finding_id: string;
  decision: SceneDecisionKind;
  note: string;
  at: string;
}

export async function fetchSceneDecisions(projectId: string, signal?: AbortSignal): Promise<Record<string, SceneDecision>> {
  const res = await fetch(`${API_BASE}/v1/scenes/${encodeURIComponent(projectId)}/decisions`, { signal });
  return (await parseJson<{ decisions: Record<string, SceneDecision> }>(res)).decisions;
}

export async function postSceneDecision(projectId: string, findingId: string, decision: SceneDecisionKind, note = ""): Promise<SceneDecision> {
  const res = await fetch(`${API_BASE}/v1/scenes/${encodeURIComponent(projectId)}/decisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ finding_id: findingId, decision, note }),
  });
  return parseJson<SceneDecision>(res);
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  return parseJson<HealthResponse>(res);
}

export async function fetchModuleCatalog(): Promise<ModuleCatalogResponse> {
  const res = await fetch(`${API_BASE}/v1/modules/catalog`);
  return parseJson<ModuleCatalogResponse>(res);
}

export async function fetchExamples(): Promise<ExamplesResponse> {
  const res = await fetch(`${API_BASE}/v1/examples/splice-intakes`);
  return parseJson<ExamplesResponse>(res);
}

export async function fetchDonorFixtures(): Promise<DonorFixturesResponse> {
  const res = await fetch(`${API_BASE}/v1/examples/donor-fixtures`);
  return parseJson<DonorFixturesResponse>(res);
}

export async function clarifyIntent(intent: Record<string, unknown>): Promise<ClarifyIntentResponse> {
  const res = await fetch(`${API_BASE}/v1/intent/clarify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intent }),
  });
  return parseJson<ClarifyIntentResponse>(res);
}

export async function spliceAndBuild(
  intake: Record<string, unknown>,
  { exportGerber = false, outDir = null }: SpliceAndBuildOptions = {},
): Promise<SpliceAndBuildResponse> {
  const res = await fetch(`${API_BASE}/v1/splice-and-build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      intake,
      export_gerber: exportGerber,
      ...(outDir ? { out_dir: outDir } : {}),
    }),
  });
  return parseJson<SpliceAndBuildResponse>(res);
}

export async function submitSpliceJob(
  intake: Record<string, unknown>,
  { exportGerber = false, requestId = null }: SubmitJobOptions = {},
): Promise<JobSummary> {
  const res = await fetch(`${API_BASE}/v1/jobs/splice-build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      intake,
      export_gerber: exportGerber,
      ...(requestId ? { request_id: requestId } : {}),
    }),
  });
  return parseJson<JobSummary>(res);
}

export async function fetchJobs({ status = null, limit = 20 }: FetchJobsOptions = {}): Promise<JobsListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set("status", status);
  const res = await fetch(`${API_BASE}/v1/jobs?${params}`);
  return parseJson<JobsListResponse>(res);
}

export async function fetchJob(jobId: string): Promise<JobSummary> {
  const res = await fetch(`${API_BASE}/v1/jobs/${encodeURIComponent(jobId)}`);
  return parseJson<JobSummary>(res);
}

export async function fetchJobResult(jobId: string): Promise<JobResultResponse> {
  const res = await fetch(`${API_BASE}/v1/jobs/${encodeURIComponent(jobId)}/result`);
  return parseJson<JobResultResponse>(res);
}

export function jobBundleUrl(jobId: string): string {
  const base = API_BASE || "";
  return `${base}/v1/jobs/${encodeURIComponent(jobId)}/bundle`;
}

/** GET URL for zipping an already-generated build/package directory (no recompile). */
export function buildPackageArchiveUrl(buildDir?: string | null): string {
  const base = API_BASE || "";
  const params = new URLSearchParams({ build_dir: String(buildDir || "") });
  return `${base}/v1/build-files/package-archive?${params.toString()}`;
}

export async function benchStatus(buildDir: string): Promise<BenchSession> {
  const res = await fetch(`${API_BASE}/v1/splice-bench/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson<BenchSession>(res);
}

export async function benchSubmit(
  buildDir: string,
  measurements: ReadonlyArray<Record<string, unknown>>,
): Promise<BenchSession> {
  const res = await fetch(`${API_BASE}/v1/splice-bench/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, measurements }),
  });
  return parseJson<BenchSession>(res);
}

export async function benchCaptureTemplate(buildDir: string): Promise<BenchCaptureTemplateResponse> {
  const res = await fetch(`${API_BASE}/v1/splice-bench/capture-template`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson<BenchCaptureTemplateResponse>(res);
}

export async function benchSubmitCapture(
  buildDir: string,
  capture: Record<string, unknown>,
): Promise<BenchSubmitCaptureResponse> {
  const res = await fetch(`${API_BASE}/v1/splice-bench/submit-capture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, capture }),
  });
  return parseJson<BenchSubmitCaptureResponse>(res);
}

export async function composeBuild(payload: Record<string, unknown>): Promise<ComposeResponse> {
  const res = await fetch(`${API_BASE}/v1/compose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      export_gerber: false,
      ...payload,
    }),
  });
  return parseJson<ComposeResponse>(res);
}

export async function composeAgentLoop(
  payload: Record<string, unknown>,
  { maxManualRetries = 2, finalizePackage = false, projectName = null }: ComposeAgentLoopOptions = {},
): Promise<ComposeResponse> {
  const res = await fetch(`${API_BASE}/v1/compose/agent-loop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      export_gerber: false,
      max_manual_retries: maxManualRetries,
      finalize_package: finalizePackage,
      ...(projectName ? { project_name: projectName } : {}),
      ...payload,
    }),
  });
  return parseJson<ComposeResponse>(res);
}

export async function renderProjectPackage(
  buildDir: string,
  { source = "compose" }: RenderProjectPackageOptions = {},
): Promise<RenderProjectPackageResponse> {
  const res = await fetch(`${API_BASE}/v1/project-package/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, source }),
  });
  return parseJson<RenderProjectPackageResponse>(res);
}

export async function submitComposeJob(
  payload: Record<string, unknown>,
  { exportGerber = false, requestId = null }: SubmitJobOptions = {},
): Promise<JobSummary> {
  const res = await fetch(`${API_BASE}/v1/jobs/compose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...payload,
      export_gerber: exportGerber,
      ...(requestId ? { request_id: requestId } : {}),
    }),
  });
  return parseJson<JobSummary>(res);
}

export async function composePhrase(
  phrase: string,
  { allowLlmFirst = false, exportGerber = false, wireOnly = false, moduleIds = null }: ComposePhraseOptions = {},
): Promise<ComposeResponse> {
  const res = await fetch(`${API_BASE}/v1/compose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      phrase,
      allow_llm_first: allowLlmFirst,
      export_gerber: exportGerber,
      wire_only: wireOnly,
      ...(moduleIds ? { module_ids: moduleIds } : {}),
    }),
  });
  return parseJson<ComposeResponse>(res);
}

export async function listBuildFiles(buildDir: string): Promise<BuildFilesListResponse> {
  const res = await fetch(`${API_BASE}/v1/build-files/list`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson<BuildFilesListResponse>(res);
}

export async function fetchBuildFileContent(
  buildDir: string,
  relative: string,
): Promise<BuildFileContentResponse> {
  const res = await fetch(`${API_BASE}/v1/build-files/content`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, relative }),
  });
  return parseJson<BuildFileContentResponse>(res);
}

export async function fetchDesignQuality(buildDir: string): Promise<DesignQuality> {
  const res = await fetch(`${API_BASE}/v1/build-files/design-quality`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson<DesignQuality>(res);
}

export async function fetchIntegrationsCatalog(): Promise<IntegrationsCatalogResponse> {
  const res = await fetch(`${API_BASE}/v1/integrations/catalog`);
  return parseJson<IntegrationsCatalogResponse>(res);
}

export async function listBuildArtifacts(buildDir: string): Promise<BuildArtifactsListResponse> {
  const res = await fetch(`${API_BASE}/v1/build-files/artifacts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson<BuildArtifactsListResponse>(res);
}

export async function exportCircuitJson(buildDir: string): Promise<ExportCircuitJsonResponse> {
  const res = await fetch(`${API_BASE}/v1/build-files/circuit-json`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson<ExportCircuitJsonResponse>(res);
}

export async function downloadBuildArtifact(buildDir: string, relative: string): Promise<void> {
  const res = await fetch(`${API_BASE}/v1/build-files/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, relative }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      detail?: string & { message?: string };
    };
    throw new Error(body?.detail?.message || body?.detail || res.statusText);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = relative.split("/").pop() || "artifact";
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function runBuildAutoroute(buildDir: string): Promise<RunBuildAutorouteResponse> {
  const res = await fetch(`${API_BASE}/v1/build-files/autoroute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, confirm: true }),
  });
  return parseJson<RunBuildAutorouteResponse>(res);
}

export async function fetchBuildBom(
  buildDir: string,
  { enrich = false }: FetchBuildBomOptions = {},
): Promise<BuildBomResponse> {
  const res = await fetch(`${API_BASE}/v1/build-files/bom`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, enrich }),
  });
  return parseJson<BuildBomResponse>(res);
}

export async function fetchFabManifest(buildDir: string): Promise<FabManifestResponse> {
  const res = await fetch(`${API_BASE}/v1/build-files/fab-manifest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson<FabManifestResponse>(res);
}

export async function exportBuildViews(buildDir: string): Promise<ExportBuildViewsResponse> {
  const res = await fetch(`${API_BASE}/v1/build-files/export-views`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson<ExportBuildViewsResponse>(res);
}

export async function recheckBuildAfterKicad(
  buildDir: string,
  { refreshPackage = true, exportViews = true }: RecheckBuildOptions = {},
): Promise<RecheckBuildResponse> {
  const res = await fetch(`${API_BASE}/v1/build-files/recheck`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      build_dir: buildDir,
      refresh_package: refreshPackage,
      export_views: exportViews,
    }),
  });
  return parseJson<RecheckBuildResponse>(res);
}

export async function composeCanvas(
  nodes: ReadonlyArray<Record<string, unknown>>,
  wires: ReadonlyArray<Record<string, unknown>>,
  { wireOnly = false, exportGerber = false }: ComposeCanvasOptions = {},
): Promise<ComposeResponse> {
  const res = await fetch(`${API_BASE}/v1/compose-canvas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      nodes,
      wires,
      wire_only: wireOnly,
      export_gerber: exportGerber,
    }),
  });
  return parseJson<ComposeResponse>(res);
}

export async function netlistCompile({
  circuitJson,
  netlist,
  kicadNetlistText,
  buildId = "generic_low_voltage_build",
  exportGerber = false,
}: NetlistCompileOptions = {}): Promise<ComposeResponse> {
  const res = await fetch(`${API_BASE}/v1/netlist-compile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...(circuitJson ? { circuit_json: circuitJson } : {}),
      ...(netlist ? { netlist } : {}),
      ...(kicadNetlistText ? { kicad_netlist_text: kicadNetlistText } : {}),
      build_id: buildId,
      export_gerber: exportGerber,
    }),
  });
  return parseJson<ComposeResponse>(res);
}

export async function fetchNetlistFixtures(): Promise<NetlistFixturesResponse> {
  const res = await fetch(`${API_BASE}/v1/examples/netlist-fixtures`);
  return parseJson<NetlistFixturesResponse>(res);
}

export async function fetchNetlistFixture(fixtureId: string): Promise<NetlistFixtureDetail> {
  const res = await fetch(`${API_BASE}/v1/examples/netlist-fixtures/${encodeURIComponent(fixtureId)}`);
  return parseJson<NetlistFixtureDetail>(res);
}

export async function fetchVisionCapabilities(): Promise<VisionCapabilitiesResponse> {
  const res = await fetch(`${API_BASE}/v1/vision/capabilities`);
  return parseJson<VisionCapabilitiesResponse>(res);
}

export async function visionEnrichIntake(
  intake: Record<string, unknown>,
  { apply = true, live = false }: VisionEnrichOptions = {},
): Promise<VisionEnrichResponse> {
  const res = await fetch(`${API_BASE}/v1/vision/enrich-intake`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intake, apply, live }),
  });
  return parseJson<VisionEnrichResponse>(res);
}

export async function donorBoardVision(intake: Record<string, unknown>): Promise<DonorBoardVisionResponse> {
  const res = await fetch(`${API_BASE}/v1/donor-board-vision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intake }),
  });
  return parseJson<DonorBoardVisionResponse>(res);
}
