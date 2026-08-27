export type StatusBlocker = {
  blocker_id: string;
  category: string;
  severity: 'error' | 'warning' | 'info';
  message: string;
  target_ids?: string[];
  required_inputs?: string[];
  required_evidence?: string[];
  source_ids?: string[];
};

export type NextAction = {
  action_id: string;
  priority: number;
  category: string;
  title: string;
  instruction: string;
  route: string;
  method?: string;
  blocker_ids?: string[];
  target_ids?: string[];
  required_inputs?: string[];
  evidence_to_capture?: string[];
  physical_action?: boolean;
  automatic_execution?: boolean;
};

export type EngineeringStatus = {
  project_id: string;
  overall_status: string;
  current_phase: string;
  blockers: StatusBlocker[];
  advisories: StatusBlocker[];
  blocker_groups: Record<string, string[]>;
  next_actions: NextAction[];
  next_action_id?: string | null;
  summary: Record<string, number | string | boolean | null | undefined>;
  metadata: Record<string, unknown>;
};

export type EngineeringStatusResponse = {
  ok?: boolean;
  project_id?: string;
  overall_status?: string;
  current_phase?: string;
  next_action?: NextAction | null;
  engineering_status?: EngineeringStatus;
  engineering_readiness?: Record<string, unknown> | null;
  error?: string;
  detail?: string;
};

export type PreparedEngineeringAction = {
  schema_version: string;
  project_id: string;
  action: NextAction;
  status: string;
  payload: Record<string, unknown>;
  blockers: string[];
  warnings: string[];
  metadata: Record<string, unknown>;
};

export type PreparedActionResponse = {
  ok?: boolean;
  project_id?: string;
  prepared_action?: PreparedEngineeringAction;
  automatic_execution?: boolean;
  physical_action?: boolean;
  fabrication_authorized?: boolean;
  flash_authorized?: boolean;
  power_on_authorized?: boolean;
  motion_authorized?: boolean;
  release_authorized?: boolean;
  error?: string;
  detail?: string;
};

export type ProjectSummary = {
  project_id: string;
  name: string;
  mode?: string;
  current_stage?: string;
  latest_revision: number;
  saved_at?: string;
  archived?: boolean;
  recovered?: boolean;
};

export type ProjectRevision = {
  revision: number;
  saved_at?: string;
  name?: string;
  current_stage?: string;
  review_id?: string | null;
  review_actor?: string | null;
};

export type ProjectEnvelope = {
  project_id?: string;
  revision?: number;
  saved_at?: string;
  snapshot?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  recovery?: Record<string, unknown>;
};

export type RevisionDiffResponse = {
  ok?: boolean;
  project_id?: string;
  base_revision?: number | string | null;
  candidate_revision?: number | string | null;
  next_action?: NextAction | null;
  engineering_revision_diff?: {
    opened_blockers?: StatusBlocker[];
    resolved_blockers?: StatusBlocker[];
    persistent_blockers?: StatusBlocker[];
    changed_blockers?: Array<Record<string, unknown>>;
    identity_changes?: Array<{
      category: string;
      added_ids?: string[];
      removed_ids?: string[];
      retained_ids?: string[];
    }>;
    artifact_changes?: Array<Record<string, unknown>>;
    execution_changes?: Array<Record<string, unknown>>;
    mechanical_changes?: Array<Record<string, unknown>>;
    physical_authorization_changes?: Array<Record<string, unknown>>;
    authority_regressions?: string[];
    summary?: Record<string, number | string | boolean | null>;
    metadata?: Record<string, unknown>;
  };
  error?: string;
  detail?: string;
};

export type EngineeringPlan = Record<string, unknown>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

export function extractEngineeringPlan(value: unknown): EngineeringPlan | null {
  if (!isRecord(value)) return null;

  const direct = value.engineeringPlan ?? value.engineering_plan;
  if (isRecord(direct)) return direct;

  const project = value.project;
  if (isRecord(project)) {
    const fromProject = extractEngineeringPlan(project);
    if (fromProject) return fromProject;
  }

  const snapshot = value.snapshot;
  if (isRecord(snapshot)) {
    const fromSnapshot = extractEngineeringPlan(snapshot);
    if (fromSnapshot) return fromSnapshot;
  }

  if (isRecord(value.machine_project) && (isRecord(value.engineering_status) || isRecord(value.engineering_readiness))) {
    return value;
  }

  return null;
}

export function safeParseEngineeringPlan(text: string): { plan: EngineeringPlan | null; error: string | null } {
  try {
    const parsed = JSON.parse(text) as unknown;
    const plan = extractEngineeringPlan(parsed) ?? (isRecord(parsed) ? parsed : null);
    return plan
      ? { plan, error: null }
      : { plan: null, error: 'The JSON must contain an engineering plan object.' };
  } catch (error: unknown) {
    return {
      plan: null,
      error: error instanceof Error ? `Invalid JSON: ${error.message}` : 'Invalid JSON.',
    };
  }
}

export function sortNextActions(actions: NextAction[] | undefined): NextAction[] {
  return [...(actions || [])].sort((a, b) => a.priority - b.priority || a.action_id.localeCompare(b.action_id));
}

export function statusTone(status: string | null | undefined) {
  const value = (status || '').toLowerCase();
  if (value === 'blocked' || value === 'failed') {
    return {
      border: 'border-rose-400/25',
      background: 'bg-rose-400/10',
      text: 'text-rose-100',
      dot: 'bg-rose-300',
    };
  }
  if (value === 'review' || value === 'candidate') {
    return {
      border: 'border-amber-300/25',
      background: 'bg-amber-300/10',
      text: 'text-amber-100',
      dot: 'bg-amber-300',
    };
  }
  return {
    border: 'border-emerald-300/25',
    background: 'bg-emerald-300/10',
    text: 'text-emerald-100',
    dot: 'bg-emerald-300',
  };
}

export function blockerTone(severity: StatusBlocker['severity']) {
  if (severity === 'error') return 'border-rose-400/20 bg-rose-500/8';
  if (severity === 'warning') return 'border-amber-400/20 bg-amber-500/8';
  return 'border-cyan-400/20 bg-cyan-500/8';
}

export function summarizeRevisionDiff(response: RevisionDiffResponse | null) {
  const diff = response?.engineering_revision_diff;
  const summary = diff?.summary || {};
  return {
    opened: Number(summary.opened_blocker_count || diff?.opened_blockers?.length || 0),
    resolved: Number(summary.resolved_blocker_count || diff?.resolved_blockers?.length || 0),
    persistent: Number(summary.persistent_blocker_count || diff?.persistent_blockers?.length || 0),
    artifacts: Number(summary.artifact_change_count || diff?.artifact_changes?.length || 0),
    execution: Number(summary.execution_change_count || diff?.execution_changes?.length || 0),
    mechanical: Number(summary.mechanical_change_count || diff?.mechanical_changes?.length || 0),
    physicalAuthorization: Number(
      summary.physical_authorization_change_count
      || diff?.physical_authorization_changes?.length
      || 0,
    ),
    identities: Number(summary.identity_change_category_count || diff?.identity_changes?.length || 0),
    authorityRegressions: Number(summary.authority_regression_count || diff?.authority_regressions?.length || 0),
  };
}

export function formatSavedAt(value: string | undefined) {
  if (!value) return 'Unknown time';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
