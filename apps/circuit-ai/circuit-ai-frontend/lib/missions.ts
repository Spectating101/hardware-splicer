// A fabrication mission as the backend reports it, and the plain words the page uses for it.
//
// The page has one job the numbers cannot do alone: make it obvious WHO said each thing. The person said what they
// want. The agent proposes. Hardware Splicer (HS) checks. A verdict is only as strong as whoever established it, so
// every verdict here carries that, in words, next to the verdict itself.

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

// --- who -------------------------------------------------------------------------------------------------------

export const WHO: Record<AuthorKind, { label: string; chip: string; dot: string }> = {
  human: { label: 'You', chip: 'border-amber-300/40 bg-amber-300/10 text-amber-100', dot: 'bg-amber-300' },
  agent: { label: 'Agent', chip: 'border-fuchsia-300/40 bg-fuchsia-400/10 text-fuchsia-100', dot: 'bg-fuchsia-300' },
  system: { label: 'Hardware Splicer', chip: 'border-cyan-300/40 bg-cyan-400/10 text-cyan-100', dot: 'bg-cyan-300' },
};

// --- the verdict ------------------------------------------------------------------------------------------------

export type Tone = 'ready' | 'checked-stop' | 'asserted' | 'stopped' | 'waiting' | 'working';

export const TONE: Record<Tone, { panel: string; label: string; bar: string }> = {
  ready: { panel: 'border-emerald-300/40 bg-emerald-950/30', label: 'text-emerald-200', bar: 'border-l-emerald-400' },
  'checked-stop': { panel: 'border-sky-300/40 bg-sky-950/30', label: 'text-sky-200', bar: 'border-l-sky-400' },
  asserted: { panel: 'border-dashed border-amber-300/60 bg-amber-950/20', label: 'text-amber-200', bar: 'border-l-amber-400' },
  stopped: { panel: 'border-slate-500/50 bg-slate-900/60', label: 'text-slate-200', bar: 'border-l-slate-400' },
  waiting: { panel: 'border-amber-300/40 bg-amber-950/30', label: 'text-amber-200', bar: 'border-l-amber-400' },
  working: { panel: 'border-cyan-300/30 bg-cyan-950/20', label: 'text-cyan-200', bar: 'border-l-cyan-400' },
};

type Verdict = { title: string; meaning: string; tone: Tone };

const TERMINAL: Record<string, Verdict> = {
  READY_FOR_HUMAN_BUILD: {
    title: 'Ready for you to build',
    meaning: 'HS’s software checks support this design. It has not been tried on real hardware.',
    tone: 'ready',
  },
  BLOCKED_NEEDS_PART_DATA: {
    title: 'Blocked: HS has no data for a part you listed',
    meaning: 'A part on your list is not in HS’s library, so it cannot be planned. Nothing was dropped to get around it.',
    tone: 'checked-stop',
  },
  BLOCKED_NEEDS_PHYSICAL_MEASUREMENT: {
    title: 'Blocked: a physical measurement is needed',
    meaning: 'Someone has to measure something on the real hardware before this can go further.',
    tone: 'asserted',
  },
  BLOCKED_NEEDS_REVERSE_ENGINEERING: {
    title: 'Blocked: a part has to be identified first',
    meaning: 'The agent says something on the hardware is not understood well enough to use.',
    tone: 'asserted',
  },
  BLOCKED_NEEDS_PROCUREMENT_EVIDENCE: {
    title: 'Blocked: sourcing evidence is needed',
    meaning: 'The agent says a part cannot be sourced on the evidence so far.',
    tone: 'asserted',
  },
  BLOCKED_UNSAFE: {
    title: 'Stopped: the agent flagged a safety concern',
    meaning: 'HS cannot check this kind of claim, so it is kept as the agent’s word and shown that way.',
    tone: 'asserted',
  },
  NO_FEASIBLE_ARCHITECTURE: {
    title: 'No workable design found',
    meaning: 'Every design tried failed its checks, and no repairs were left.',
    tone: 'stopped',
  },
  BUDGET_EXHAUSTED: {
    title: 'Stopped: the check budget ran out',
    meaning: 'The checks you allowed were used up before a design was shown ready.',
    tone: 'stopped',
  },
};

export function verdictOf(mission: Mission): Verdict {
  if (mission.terminal) {
    return TERMINAL[mission.terminal.state] || {
      title: mission.terminal.state.replace(/_/g, ' ').toLowerCase(),
      meaning: 'This mission has ended.',
      tone: 'stopped',
    };
  }
  if (!mission.accepted) {
    return {
      title: 'Waiting for you to accept',
      meaning: 'Nothing runs until you accept this mission. Accepting lets HS run its software checks within the budget below.',
      tone: 'waiting',
    };
  }
  const open = mission.needs.filter((need) => need.need_state !== 'resolved');
  if (mission.phase === 'EVIDENCE_REQUIRED' || open.length) {
    // A structured request has an answer form on this page. A free-text one is the agent asking in its own words
    // (photos, a nameplate, a manual): honest about what is being asked, and that this page cannot take the answer yet.
    if (open.length && open.every((need) => !need.request)) {
      return {
        title: 'Waiting for information from you',
        meaning: 'The agent says it cannot go on without the items below. This page has no form for them yet, so they are shown as the agent wrote them.',
        tone: 'waiting',
      };
    }
    return {
      title: 'Waiting for a measurement from you',
      meaning: 'The agent asked for something only a person can do. The mission resumes when you answer.',
      tone: 'waiting',
    };
  }
  if (mission.candidates.length === 0) {
    return { title: 'Accepted, not started', meaning: 'The agent has not proposed a design yet.', tone: 'working' };
  }
  return { title: 'In progress', meaning: 'The agent is proposing designs and HS is checking them.', tone: 'working' };
}

/** Who established the verdict, in the words a person needs to weigh it. */
export function groundingOf(terminal: MissionTerminal): { who: keyof typeof WHO; label: string; detail: string } {
  switch (terminal.grounding) {
    case 'hs_evaluation':
      return { who: 'system', label: 'HS checked this', detail: 'Established by HS’s own recorded checks of the design.' };
    case 'hs_inventory_reading':
      return { who: 'system', label: 'HS checked this', detail: 'Established by HS’s own reading of your parts list.' };
    case 'hs_budget':
      return { who: 'system', label: 'HS counted this', detail: 'The recorded checks used the whole budget.' };
    case 'hs_donor_contract':
    case 'hs_donor_reading':
      return { who: 'system', label: 'HS checked this', detail: 'Established by HS’s own reading of the donor hardware record.' };
    case 'agent_assertion':
      return { who: 'agent', label: 'The agent’s word, not checked', detail: 'HS cannot check this kind of claim. It is recorded as the agent’s assertion and nothing more.' };
    default:
      return { who: 'agent', label: 'Source not recorded', detail: 'This mission predates grounding labels, so who established it is not recorded.' };
  }
}

// --- the timeline -----------------------------------------------------------------------------------------------

const OPERATION: Record<string, string> = {
  device_plan: 'Wiring check',
  device_engineering: 'Engineering review',
  device_case: 'Enclosure',
  device_application: 'Firmware',
  device_application_run: 'Modeled firmware run',
};

export function operationName(operation: string) {
  return OPERATION[operation] || operation.replace(/_/g, ' ');
}

export function resultWords(evaluation: Evaluation) {
  const { errors, warnings } = evaluation.result;
  if (evaluation.operation === 'device_engineering') {
    return errors ? `${errors} limit${errors === 1 ? '' : 's'} exceeded` : `no limit exceeded${warnings ? `, ${warnings} to look at` : ''}`;
  }
  if (!errors && !warnings) return 'clean';
  return [errors ? `${errors} problem${errors === 1 ? '' : 's'}` : '', warnings ? `${warnings} to look at` : ''].filter(Boolean).join(', ');
}

export function describeEvent(event: MissionEvent): string {
  const text = (key: string) => (typeof event[key] === 'string' ? (event[key] as string) : '');
  switch (event.type) {
    case 'opened':
      return 'Mission opened with your goal, parts and budget.';
    case 'inventory_read': {
      const reading = event.reading as { left_out?: string[]; fragments?: unknown[] } | undefined;
      const left = reading?.left_out?.length || 0;
      return left
        ? `HS read your parts list. ${left} line${left === 1 ? '' : 's'} could not be matched: ${reading?.left_out?.join('; ')}.`
        : 'HS read your parts list and matched every line.';
    }
    case 'accepted':
      return 'Accepted. HS may now run its software checks within the budget.';
    case 'candidate_proposed': {
      const candidate = event.candidate as { id?: string; label?: string; rationale?: string } | undefined;
      return `Proposed design ${candidate?.id}: ${candidate?.label || ''}${candidate?.rationale ? ` — ${candidate.rationale}` : ''}`;
    }
    case 'evaluation_recorded': {
      const result = event.result as { errors?: number; warnings?: number } | undefined;
      const fake: Evaluation = {
        seq: event.seq,
        operation: text('operation'),
        result: { errors: result?.errors || 0, warnings: result?.warnings || 0, result_sha256: '', summary: '' },
        artifact: null,
      };
      return `${operationName(fake.operation)} of design ${text('candidate_id')}: ${resultWords(fake)}.`;
    }
    case 'repair_proposed':
      return `Proposed a repair to design ${text('candidate_id')}: ${text('rationale')}`;
    case 'evidence_required':
      return `Asked for evidence (${text('blocker').replace('BLOCKED_NEEDS_', '').replace('BLOCKED_', '').toLowerCase().replace(/_/g, ' ')}): ${text('need')}`;
    case 'evidence_supplied':
      return `Answered a measurement request: reading ${text('comparison').replace('_', ' ')} the expected range.`;
    case 'donor_read': {
      const donors = event.donors as unknown[] | undefined;
      const count = Array.isArray(donors) ? donors.length : 0;
      return count
        ? `HS read the record for ${count} ${count === 1 ? 'donor' : 'donors'} you named, as it stood before you accepted.`
        : 'HS looked for donor records and found none named.';
    }
    case 'finding_offered': {
      const finding = event.finding as { claim?: string } | undefined;
      return `Offered a finding about donor hardware: “${finding?.claim || 'see details'}” Recorded as an observation, not a measurement.`;
    }
    case 'terminal_proposed':
      return `Ended the mission: ${text('state').replace(/_/g, ' ').toLowerCase()}. ${text('reason')}`;
    case 'design_staged':
      return 'The design was opened as a project review. It becomes part of the project only if you accept that review.';
    default:
      return event.type.replace(/_/g, ' ');
  }
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

export async function fetchProjects(): Promise<{ project_id: string; name: string }[]> {
  const payload = await call<{ projects: { project_id: string; name: string }[] }>(
    '/api/proxy/engineering/projects', undefined, 'Could not load projects');
  return payload.projects || [];
}

export async function fetchMissions(projectId: string): Promise<Mission[]> {
  const payload = await call<{ missions: Mission[] }>(base(projectId), undefined, 'Could not load missions');
  return payload.missions || [];
}

export async function fetchMission(projectId: string, missionId: string): Promise<Mission> {
  const payload = await call<{ mission: Mission }>(`${base(projectId)}/${encodeURIComponent(missionId)}`, undefined, 'Could not load the mission');
  return payload.mission;
}

export async function acceptMission(projectId: string, missionId: string, token: string): Promise<Mission> {
  const payload = await call<{ mission: Mission }>(
    `${base(projectId)}/${encodeURIComponent(missionId)}/accept`,
    { method: 'POST', headers: { 'content-type': 'application/json', 'x-hs-operator-token': token }, body: '{}' },
    'Could not accept the mission',
  );
  return payload.mission;
}

export async function buildPackage(projectId: string, missionId: string): Promise<PackageManifest> {
  const payload = await call<{ package: PackageManifest }>(
    `${base(projectId)}/${encodeURIComponent(missionId)}/package`,
    { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' },
    'Could not build the package',
  );
  return payload.package;
}

export async function stageDesign(projectId: string, missionId: string, token: string): Promise<{ review_id: string }> {
  return call<{ review_id: string }>(
    `${base(projectId)}/${encodeURIComponent(missionId)}/stage`,
    { method: 'POST', headers: { 'content-type': 'application/json', 'x-hs-operator-token': token }, body: '{}' },
    'Could not open the review',
  );
}

export const packageUrl = (projectId: string, missionId: string) => `${base(projectId)}/${encodeURIComponent(missionId)}/package`;

// --- opening a mission --------------------------------------------------------------------------------------------

export type PartsReading = {
  fragments: {
    text: string;
    matches: { module: string; name: string; matched_on: string; basis: string; quantity: number }[];
    note?: string;
    unread?: string[];
  }[];
  controller: string | null;
  parts: string[];
  left_out: string[];
};

export async function readParts(text: string): Promise<PartsReading> {
  const payload = await call<{ parsed: PartsReading }>(
    '/api/proxy/engineering/devices/parts-reading',
    { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text }) },
    'Could not read the parts list',
  );
  return payload.parsed;
}

export type MissionIntakeDraft = {
  goal: string;
  inventory: string[];
  constraints: string[];
  budgets?: { max_operator_jobs?: number; max_candidates?: number; max_repairs_per_candidate?: number };
};

/** Open a mission as the person: no author is sent, because the backend names the verified token's owner. */
export async function openMission(projectId: string, intake: MissionIntakeDraft, token: string): Promise<Mission> {
  const payload = await call<{ mission: Mission }>(
    base(projectId),
    { method: 'POST', headers: { 'content-type': 'application/json', 'x-hs-operator-token': token }, body: JSON.stringify({ intake }) },
    'Could not open the mission',
  );
  return payload.mission;
}

// --- the staged review --------------------------------------------------------------------------------------------

export type StagedReview = {
  review_id: string;
  status: string;
  base_revision: number;
  summary?: { snapshot_fields_changed?: number };
  decision?: { actor?: string; accepted_revision?: number | null; decided_at?: string } | null;
};

const reviewBase = (projectId: string, reviewId: string) =>
  `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/reviews/${encodeURIComponent(reviewId)}`;

export async function fetchReview(projectId: string, reviewId: string): Promise<StagedReview> {
  const payload = await call<{ review: StagedReview }>(reviewBase(projectId, reviewId), undefined, 'Could not load the review');
  return payload.review;
}

export async function decideReview(projectId: string, reviewId: string, decision: 'accepted' | 'rejected', token: string): Promise<StagedReview> {
  const payload = await call<{ review: StagedReview }>(
    `${reviewBase(projectId, reviewId)}/decision`,
    // `actor` is required by the route's schema but ignored: a design staged from a mission takes its decider from the token.
    { method: 'POST', headers: { 'content-type': 'application/json', 'x-hs-operator-token': token }, body: JSON.stringify({ decision, actor: 'operator-token', note: '' }) },
    'Could not record the decision',
  );
  return payload.review;
}

// --- answering a measurement request -----------------------------------------------------------------------------

export type Reading = { quantity: string; value: number; unit: string };

/** The person types the reading; the backend builds the evidence envelope, so no hash is computed here. */
export async function answerNeed(
  projectId: string, missionId: string, needSeq: number, values: Reading[] | { log: string }, token: string, expectedEventSeq: number,
): Promise<Mission> {
  const payload = await call<{ mission: Mission }>(
    `${base(projectId)}/${encodeURIComponent(missionId)}/needs/${needSeq}/answer`,
    { method: 'POST', headers: { 'content-type': 'application/json', 'x-hs-operator-token': token },
      body: JSON.stringify({ values, expected_event_seq: expectedEventSeq }) },
    'Could not record the reading',
  );
  return payload.mission;
}
