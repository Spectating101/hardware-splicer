// The slice of the mission API the read-only review sheet needs: types as the backend reports them, and two GETs.
// Nothing here starts, accepts, answers, stages or builds a mission.

export type AuthorKind = 'human' | 'agent' | 'system';
export type Author = { kind: AuthorKind; id: string };

export type Evaluation = {
  seq: number;
  operation: string;
  result: { errors: number; warnings: number; result_sha256: string; summary: string };
  artifact: string | null;
};

export type MissionCandidate = {
  id: string;
  kind: string;
  label: string;
  rationale: string;
  repairs: number;
  covers_inventory: boolean;
  uncovered_inventory: string[];
  not_in_inventory: string[];
  violated_requirements: string[];
  evaluations: Evaluation[];
  spec?: Record<string, unknown>;
  /** What the design says about the donors named in the intake. Naming a donor is a reference, not proof of wiring. */
  donor_coverage?: {
    used_donors: string[];
    missing_required_donors: string[];
    covers_required_donors: boolean;
    unverified_used_donors: { donor_id: string; missing_facts: string[] }[];
  };
  /** Fields the agent wrote that HS's planner did not recognise. They are kept, and not checked. */
  spec_diagnostics?: { scope: string; unrecognized_fields: string[] };
};

/** A danger the agent put on the record. The agent's word only: HS cannot check it, and none recorded is not "safe". */
export type MissionSafetyConcern = {
  need_seq: number;
  state: 'open' | 'resolved' | 'contradicted';
  candidate_id: string | null;
  concern: string;
  grounding: string | null;
  author: Author | null;
};

export type MissionNeed = {
  seq: number;
  blocker: string;
  need: string;
  candidate_id: string | null;
  request: {
    kind: string;
    target: string;
    quantity?: string;
    instructions: string;
    expected?: { min: number; max: number; unit: string };
  } | null;
  need_state: 'open' | 'resolved' | 'contradicted';
  answered_by: number | null;
};

export type MissionTerminal = {
  state: string;
  reason: string;
  candidate_id: string | null;
  cites: number[];
  grounding: string | null;
  physical_evidence_required?: string[];
};

export type MissionEvent = {
  seq: number;
  type: string;
  author: Author;
  created_at: string;
  [key: string]: unknown;
};

export type Mission = {
  mission_id: string;
  project_id: string;
  intake: {
    goal: string;
    constraints: string[];
    inventory: string[];
    requirements?: { path: string; equals: unknown }[];
    measurements?: Record<string, unknown>;
  };
  budgets: {
    max_candidates: number;
    max_operator_jobs: number;
    max_repairs_per_candidate: number;
    operator_jobs_used: number;
  };
  created_at: string;
  phase: string;
  accepted: { by: Author; at: string } | null;
  inventory: { reading?: { left_out?: string[] }; draft?: { ok: boolean; plan_errors: number; plan_warnings: number } } | null;
  donors?: MissionDonor[];
  candidates: MissionCandidate[];
  terminal: MissionTerminal | null;
  staged: { review_id: string; package_sha256: string } | null;
  needs: MissionNeed[];
  safety_concerns?: MissionSafetyConcern[];
  last_event_seq: number;
  physical_correctness: string;
  firmware_authorized: boolean;
  power_on_authorized: boolean;
  events?: MissionEvent[];
};

export type DonorFact = {
  value: unknown;
  grade: string | null;
  epistemic_state: string;
  review_state: string;
  evidence_ids: string[];
  unit: string | null;
};

export type DonorFinding = {
  seq: number;
  claim: string;
  method: string;
  source: string;
  signal: string | null;
  grade: string;
  artifacts: { name: string; sha256: string }[];
  author: Author;
};

export type MissionDonor = {
  donor_id: string;
  label: string;
  optional: boolean;
  contract_state: 'unknown' | 'partial' | 'verified' | 'rejected' | string;
  can_generate_firmware: boolean;
  missing_facts: string[];
  capabilities: { role: string; grade: string | null }[];
  signals: { name: string; direction: string; contact_id: string; voltage_max_v: DonorFact; active_level: DonorFact; controller_pin: DonorFact; protocol: DonorFact }[];
  findings: DonorFinding[];
  person_measurements: unknown[];
};

export type PackageManifest = {
  package_sha256: string;
  candidate_id: string;
  deliverables: Record<string, { status: string; reason?: string; checks?: string[]; note?: string }>;
  files: Record<string, { sha256: string; size_bytes: number }>;
};

const OPERATION: Record<string, string> = {
  device_plan: 'Wiring check',
  device_engineering: 'Engineering review',
  device_case: 'Enclosure',
  device_application: 'Firmware',
  device_application_run: 'Modeled firmware run',
  intact_reuse: 'Intact reuse software check',
};

export function operationName(operation: string) {
  return OPERATION[operation] || operation.replace(/_/g, ' ');
}

// --- the calls --------------------------------------------------------------------------------------------------

type Payload<T> = { ok?: boolean; error?: string; detail?: string | { message?: string } } & T;

function failure(payload: Payload<object> | null, fallback: string) {
  const detail = payload?.detail;
  if (payload?.error) return payload.error;
  if (typeof detail === 'string' && detail) return detail;
  if (detail && typeof detail === 'object' && typeof detail.message === 'string') return detail.message;
  return fallback;
}

async function call<T>(url: string, init: RequestInit | undefined, fallback: string): Promise<T> {
  const response = await fetch(url, { cache: 'no-store', ...init });
  let payload: (Payload<T> | null) = null;
  try {
    payload = (await response.json()) as Payload<T>;
  } catch {
    payload = null;
  }
  // The proxy turns an upstream refusal into HTTP 200 with ok:false, so both must be checked.
  if (!response.ok || !payload || payload.ok === false) throw new Error(failure(payload, fallback));
  return payload as T;
}

const base = (projectId: string) => `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/missions`;

export async function fetchMission(projectId: string, missionId: string): Promise<Mission> {
  const payload = await call<{ mission: Mission }>(`${base(projectId)}/${encodeURIComponent(missionId)}`, undefined, 'Could not load the mission');
  return payload.mission;
}

/** Files are a read-only backend inventory, not an agent's delivery claim or proof of fabrication. */
export type MissionRetainedFile = {
  kind: string;
  candidate_id: string;
  operation: string;
  evaluation_seq: number;
  current: boolean;
  status: 'available' | 'unavailable';
  sha256: string | null;
  presentation: string;
  scope?: string;
  producer_attribution?: string;
  download_path: string | null;
};

export type MissionDeliveryInspection = {
  schema_version: string;
  mission_id: string;
  project_id: string;
  last_event_seq: number;
  recorded_files: MissionRetainedFile[];
  prototype_package: {
    status: 'available' | 'blocked' | 'not_generated' | 'unavailable';
    scan_complete: boolean;
    retained_packages: {
      sha256: string;
      size_bytes: number;
      scope: string;
      producer_attribution: string;
      deliverables: PackageManifest['deliverables'];
      download_path: string;
    }[];
  };
  unresolved_needs: MissionNeed[];
  safety_concerns: MissionSafetyConcern[];
  physical_correctness: string;
  sale_readiness: string;
  inspection_generated_artifacts: boolean;
  file_presence_proves_agent_delivery: boolean;
};

/** GET is non-generating. Unlike the older package GET it does not build missing artifacts. */
export async function inspectMissionDelivery(projectId: string, missionId: string): Promise<MissionDeliveryInspection> {
  const payload = await call<{ delivery: MissionDeliveryInspection }>(
    base(projectId) + '/' + encodeURIComponent(missionId) + '/delivery',
    undefined,
    'Could not inspect retained mission output',
  );
  return payload.delivery;
}
