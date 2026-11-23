const API_BASE: string = import.meta.env.VITE_API_BASE !== undefined
  ? import.meta.env.VITE_API_BASE : import.meta.env.DEV ? "/api" : "";

interface ErrorDetail {
  message?: string;
}

interface ErrorBody {
  detail?: string | ErrorDetail;
}

export interface DigitalStudyApiError extends Error {
  status?: number;
}

export interface DigitalCase {
  case_id: string;
  name: string;
  source_inputs_available: boolean;
  requirements: Record<string, unknown>;
}

export interface DigitalCasesResponse {
  cases: DigitalCase[];
  default_case_id?: string | null;
}

export interface DigitalProjectEnvelope {
  project_id: string;
  revision: number;
  saved_at?: string | null;
  snapshot: Record<string, unknown>;
}

export interface CreateDigitalProjectResponse {
  project: DigitalProjectEnvelope;
}

export type DigitalJobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | (string & {});

export interface DigitalJob {
  job_id: string;
  status: DigitalJobStatus;
  error?: {
    message?: string;
  } | null;
}

export interface DigitalJobEnvelopeResponse {
  job?: DigitalJob | null;
}

export interface DigitalCheckResult {
  passed?: boolean | null;
  actual?: number | string | boolean | null;
  limit?: number | string | boolean | null;
  unit?: string | null;
}

export interface DigitalStudyConstraint extends DigitalCheckResult {
  id?: string;
  label?: string;
  source?: string | null;
}

export interface DigitalStudySummary {
  case_id?: string;
  mass_g?: number;
  mass_margin_g?: number;
  centre_of_mass_mm?: number[];
  requirements?: Record<string, number | string | boolean | null>;
  metrics?: Record<string, number>;
  constraints?: DigitalStudyConstraint[];
  scope_limits?: string[];
  note?: string | null;
}

export interface DigitalStudyEntry {
  revision: number;
  run_id?: string | null;
  parent_revision?: number | null;
  change_request?: string | null;
  artifacts: Record<string, string>;
  summary: DigitalStudySummary;
}

export interface DigitalRequirementBounds {
  minimum?: number;
  maximum?: number;
}

export interface DigitalStudyRuntime {
  available: boolean;
  setup_hint?: string;
}

export interface DigitalStudyResponse {
  study: DigitalStudyEntry;
  history: DigitalStudyEntry[];
  jobs?: DigitalJob[];
  requirement_bounds?: Record<string, DigitalRequirementBounds>;
  runtime: DigitalStudyRuntime;
}

export interface SubmitDigitalRunPayload {
  base_revision: number;
  change_request: string;
  requirements: Record<string, number>;
  request_id: string;
}

export interface ProjectAssuranceClaim {
  claim_id?: string;
  id?: string;
  statement?: string;
  label?: string;
  predicate?: string;
  authority?: string | null;
  source?: string | null;
  source_id?: string | null;
  source_ref?: string | null;
  evidence_locator?: string | null;
  passed?: boolean | null;
  actual?: unknown;
  limit?: unknown;
  unit?: string | null;
  value?: unknown;
  units?: string | null;
}

export interface ProjectAssuranceOutput {
  kind?: "blocker" | (string & {});
  message?: string | null;
  summary?: string | null;
}

export interface ProjectAssurance {
  claims?: ProjectAssuranceClaim[];
  outputs?: ProjectAssuranceOutput[];
}

export interface ProjectAssuranceResponse {
  revision: number;
  assurance?: ProjectAssurance | null;
}

export interface ProjectMaterialSummary {
  assessment_id: string;
  source_revision: number;
}

export interface ProjectMaterialsResponse {
  assessments?: ProjectMaterialSummary[];
}

export interface PartSubstitutionOffer {
  name?: string;
  part_id?: string;
  authority?: string;
  source?: string;
}

export interface MaterialPartRecord {
  unit_id?: string;
  part_id?: string;
  component_id?: string;
  material_id?: string;
  stock_id?: string;
  name?: string;
  description?: string;
  specification?: string;
  mpn?: string;
  source?: string;
  origin?: string;
  knowledge_state?: string;
  geometry_ref?: string | null;
  catalog_part_id?: string | number | null;
  known_facts?: unknown;
  substitutions?: PartSubstitutionOffer[];
}

export interface MaterialAssessment {
  source_revision?: number;
  inventory?: {
    lots?: MaterialPartRecord[];
  } | null;
  requirements?: MaterialPartRecord[];
}

export interface MaterialAssessmentResponse {
  assessment?: MaterialAssessment | null;
}

export interface PartSubstitutionAssessment {
  assessment_id?: string;
  source_revision?: number;
  report?: {
    status?: string;
  } | null;
  specification?: {
    replace_part_id?: string;
    candidate?: PartSubstitutionOffer;
  } | null;
}

export interface PartSubstitutionResponse {
  assessment?: PartSubstitutionAssessment | null;
}

export type MachineReleaseBlocker =
  | string
  | {
      message?: string | null;
      summary?: string | null;
    };

export interface MachineReleaseAssessment {
  blockers?: MachineReleaseBlocker[];
}

export interface MachineReleaseAssessmentResponse {
  assessment?: MachineReleaseAssessment | null;
}

export interface DigitalCompareValueChange {
  before?: unknown;
  after?: unknown;
}

export interface DigitalCompareMetricChange {
  before?: number | number[] | null;
  after?: number | number[] | null;
  delta?: number | number[] | null;
}

export interface DigitalCompareConstraint {
  id: string;
  before?: DigitalCheckResult | null;
  after?: DigitalCheckResult | null;
  transition?: string;
}

export interface DigitalCompareResponse {
  before_revision: number;
  after_revision: number;
  same_engine_sources?: boolean | null;
  requirements_changes?: Record<string, DigitalCompareValueChange>;
  metrics?: Record<string, DigitalCompareMetricChange>;
  constraints?: DigitalCompareConstraint[];
}

export type EvidenceDeltaReasonKind =
  | "changed_dependency"
  | "rerun_result_differs"
  | "check_absent_in_candidate"
  | (string & {});

export interface EvidenceDeltaReason {
  kind?: EvidenceDeltaReasonKind;
  ids?: string[];
}

export interface EvidenceDeltaCheckMetadata extends DigitalCheckResult {
  kind?: "check" | (string & {});
  node_id?: string;
  summary?: string;
  revision?: number;
  run_id?: string | null;
  rerun?: (DigitalCheckResult & { revision?: number }) | null;
}

export interface EvidenceDeltaOutput {
  evidence_id: string;
  reasons?: EvidenceDeltaReason[];
  metadata?: EvidenceDeltaCheckMetadata | null;
}

export interface EvidenceDeltaChangedDependency {
  dependency_id: string;
  before?: unknown;
  after?: unknown;
}

export interface EvidenceDeltaFailingOutput extends DigitalCheckResult {
  node_id: string;
  summary: string;
  revision?: number;
  transition?: "regressed" | (string & {});
}

export interface EvidenceDeltaPackageRef {
  revision?: number;
  name?: string;
  path?: string;
  sha256?: string | null;
}

export interface EvidenceDeltaStudyChecks {
  base_revision?: number;
  candidate_revision?: number;
  changed_dependencies?: EvidenceDeltaChangedDependency[];
  failing_outputs?: EvidenceDeltaFailingOutput[];
  packages?: {
    before?: EvidenceDeltaPackageRef | null;
    after?: EvidenceDeltaPackageRef | null;
  } | null;
}

export interface EvidenceDeltaPayload {
  affected_outputs?: EvidenceDeltaOutput[];
  blocked_outputs?: EvidenceDeltaOutput[];
  retained_outputs?: EvidenceDeltaOutput[];
  study_checks?: EvidenceDeltaStudyChecks | null;
}

export interface EvidenceDeltaResponse {
  base_revision: number;
  candidate_revision: number;
  evidence_delta?: EvidenceDeltaPayload | null;
}

export interface EngineeringPackageSummary {
  package_id: string;
  source_revision?: number | null;
}

export interface EngineeringPackagesResponse {
  packages?: EngineeringPackageSummary[];
}

export interface EngineeringRevisionDiffResponse {
  opened_blockers?: unknown[];
  resolved_blockers?: unknown[];
  identity_changes?: unknown[];
  artifact_changes?: unknown[];
  mechanical_changes?: unknown[];
  authority_regressions?: unknown[];
}

export interface ChangeDossierCheck extends DigitalCheckResult {
  id: string;
}

export interface ChangeDossierTarget {
  fact?: string | null;
  operator?: string | null;
  value?: unknown;
  actual?: unknown;
  passed?: boolean | null;
}

export interface ChangeDossierUnmet {
  id: string;
  explanation?: string | null;
}

export interface ChangeDossierAppliedRevision {
  revision: number;
  requirements_met?: boolean | null;
  checks: ChangeDossierCheck[];
  change_request?: string | null;
}

export interface ChangeDossierNativeOutcome {
  fact?: string | null;
  operator?: string | null;
  required?: unknown;
  native_value?: unknown;
  met?: boolean | null;
}

export interface ChangeDossierCandidate {
  id: string;
  input: string;
  before?: unknown;
  after?: unknown;
  formula?: string | null;
  numbers?: Record<string, unknown> | null;
  physical_means: string;
  native_outcome?: ChangeDossierNativeOutcome | null;
}

export interface ChangeDossierEntry {
  proposal_sha256: string;
  policy_id: string;
  policy_version: string;
  policy_decision: string;
  base_revision: number;
  base_checks?: ChangeDossierCheck[];
  targets?: ChangeDossierTarget[];
  unmet?: ChangeDossierUnmet[];
  requirement_changes?: Record<string, DigitalCompareValueChange>;
  applied_revision?: ChangeDossierAppliedRevision | null;
  review_verification?: string | null;
  candidates?: ChangeDossierCandidate[];
  change_evidence?: {
    packet_sha256?: string | null;
  } | null;
}

export interface ChangeDossierCiteEdition {
  edition_id: string;
  bound_revision: number;
  stale_by_hs_head?: boolean;
  issued_at?: string | null;
  latest_check?: {
    checked_at?: string | null;
    status: string;
    head_revision?: number | null;
  } | null;
}

export interface ChangeDossier {
  head_revision?: number;
  cite_linked?: boolean;
  changes: ChangeDossierEntry[];
  cite_editions: ChangeDossierCiteEdition[];
}

export interface ChangeDossierResponse {
  change_dossier?: ChangeDossier | null;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, options);
  const body = (await response.json().catch(() => ({}))) as unknown;
  if (!response.ok) {
    const detail = (body as ErrorBody).detail;
    const error = new Error(typeof detail === "string" ? detail : detail?.message || `Request failed (${response.status})`) as DigitalStudyApiError;
    error.status = response.status;
    throw error;
  }
  return body as T;
}

export const fetchDigitalCases = (signal?: AbortSignal): Promise<DigitalCasesResponse> => request<DigitalCasesResponse>("/v1/digital/cases", { signal });

export const createDigitalProject = (caseId: string): Promise<CreateDigitalProjectResponse> => request<CreateDigitalProjectResponse>("/v1/digital/projects", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ case_id: caseId }),
});

export const fetchDigitalStudy = (projectId: string, signal?: AbortSignal): Promise<DigitalStudyResponse> =>
  request<DigitalStudyResponse>(`/v1/projects/${encodeURIComponent(projectId)}/digital`, { signal });

export const submitDigitalRun = (projectId: string, payload: SubmitDigitalRunPayload): Promise<DigitalJobEnvelopeResponse> =>
  request<DigitalJobEnvelopeResponse>(`/v1/projects/${encodeURIComponent(projectId)}/digital/runs`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });

export const fetchDigitalJob = (jobId: string, signal?: AbortSignal): Promise<DigitalJob> => request<DigitalJob>(`/v1/jobs/${encodeURIComponent(jobId)}`, { signal });
export const cancelDigitalJob = (jobId: string): Promise<DigitalJobEnvelopeResponse> => request<DigitalJobEnvelopeResponse>(`/v1/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
export const digitalArtifactUrl = (path?: string | null): string | undefined => path ? `${API_BASE}${path}` : undefined;

export const fetchProjectAssurance = (projectId: string, revision: number | string, signal?: AbortSignal): Promise<ProjectAssuranceResponse> =>
  request<ProjectAssuranceResponse>(`/v1/projects/${encodeURIComponent(projectId)}/engineering/assurance?revision=${revision}`, { signal });
export const fetchProjectMaterials = (projectId: string, signal?: AbortSignal): Promise<ProjectMaterialsResponse> =>
  request<ProjectMaterialsResponse>(`/v1/projects/${encodeURIComponent(projectId)}/materials`, { signal });
export const fetchMaterialAssessment = (projectId: string, assessmentId: string, signal?: AbortSignal): Promise<MaterialAssessmentResponse> =>
  request<MaterialAssessmentResponse>(`/v1/projects/${encodeURIComponent(projectId)}/materials/${encodeURIComponent(assessmentId)}`, { signal });
export const fetchPartSubstitution = (projectId: string, assessmentId: string, signal?: AbortSignal): Promise<PartSubstitutionResponse> =>
  request<PartSubstitutionResponse>(`/v1/projects/${encodeURIComponent(projectId)}/parts/substitutions/${encodeURIComponent(assessmentId)}`, { signal });
export const assessMachineRelease = (project: Record<string, unknown>, signal?: AbortSignal): Promise<MachineReleaseAssessmentResponse> => request<MachineReleaseAssessmentResponse>("/v1/machine-projects/assess-release", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project }), signal,
});
export const fetchDigitalCompare = (projectId: string, before: number | string, after: number | string, signal?: AbortSignal): Promise<DigitalCompareResponse> =>
  request<DigitalCompareResponse>(`/v1/projects/${encodeURIComponent(projectId)}/digital/compare?before_revision=${before}&after_revision=${after}`, { signal });
export const fetchEvidenceDelta = (projectId: string, base: number | string, candidate: number | string, signal?: AbortSignal): Promise<EvidenceDeltaResponse> =>
  request<EvidenceDeltaResponse>(`/v1/projects/${encodeURIComponent(projectId)}/engineering/assurance/evidence-delta`, {
    method: "POST", headers: { "Content-Type": "application/json" }, signal,
    body: JSON.stringify({ base_revision: base, candidate_revision: candidate }),
  });
export const fetchEngineeringPackages = (projectId: string, signal?: AbortSignal): Promise<EngineeringPackagesResponse> =>
  request<EngineeringPackagesResponse>(`/v1/projects/${encodeURIComponent(projectId)}/engineering-packages`, { signal });
export const engineeringPackageUrl = (projectId: string, packageId: string): string =>
  `${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/engineering-packages/${encodeURIComponent(packageId)}/download`;
export const fetchEngineeringRevisionDiff = (projectId: string, base: number | string, candidate: number | string, signal?: AbortSignal): Promise<EngineeringRevisionDiffResponse> => request<EngineeringRevisionDiffResponse>("/v1/engineering/revisions/diff", {
  method: "POST", headers: { "Content-Type": "application/json" }, signal,
  body: JSON.stringify({ project_id: projectId, base_revision: base, candidate_revision: candidate }),
});
export const fetchChangeDossier = (projectId: string, signal?: AbortSignal): Promise<ChangeDossierResponse> =>
  request<ChangeDossierResponse>(`/v1/projects/${encodeURIComponent(projectId)}/change-dossier`, { signal });
