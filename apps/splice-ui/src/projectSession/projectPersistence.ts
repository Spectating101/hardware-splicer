import { useCallback, useEffect, useRef, useState } from "react";
import {
  ACTIONS,
  PERSISTENCE_STATUS,
  canonicalJson,
  createEmptySession,
  projectSessionReducer,
  projectSnapshot,
  sessionIsPersistable,
} from "./projectSession.js";

// ---- Types: the parts of the project API and session this module reads or writes. ----------

/** The save states this module dispatches; a project is never "ready" or "approved" here. */
export type PersistenceStatus = "idle" | "saving" | "saved" | "restored" | "conflict" | "failed";

// PERSISTENCE_STATUS (JavaScript) must list exactly these states: an added, removed or renamed key
// makes this line a type error. Its values equal its keys, so the narrowing below is sound.
type SameKeys<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;
const statusKeysMatch: SameKeys<keyof typeof PERSISTENCE_STATUS, PersistenceStatus> = true;
void statusKeysMatch;
const STATUS = PERSISTENCE_STATUS as { readonly [K in PersistenceStatus]: K };

/** An API failure: Error plus the HTTP status, the backend's error type and the parsed body. */
export interface RequestError extends Error {
  status: number;
  type: string;
  body: unknown;
}

/** A saved project as the API returns it (`body.project`). */
export interface ProjectEnvelope {
  project_id?: string;
  revision?: number;
  saved_at?: string;
  snapshot?: Record<string, unknown> & { machineProject?: unknown };
  recovery?: { used?: boolean };
  [key: string]: unknown;
}

/** One row of `GET /v1/projects`. */
export interface ProjectListRow {
  project_id: string;
  name?: string;
  mode?: string;
  current_stage?: string | null;
  latest_revision?: number | null;
  saved_at?: string | null;
  created_at?: string | null;
  archived?: boolean;
  recovered?: boolean;
  objective?: string | null;
  [key: string]: unknown;
}

export interface ProjectListBody { projects?: ProjectListRow[] }
export interface ProjectBody { project?: ProjectEnvelope }

/** The session fields this module reads. */
export interface PersistedSession {
  projectId?: string | null;
  projectName?: string;
  mode?: string;
  intake?: unknown;
  machineProject?: unknown;
  sessionOrigin?: string;
  snapshotRevision?: number | string | null;
  [key: string]: unknown;
}

export type PersistenceAction =
  | { type: typeof ACTIONS.SET_PERSISTENCE; status: PersistenceStatus; error?: string; revision?: number; savedAt?: string }
  | { type: typeof ACTIONS.SET_MACHINE_PROJECT; machineProject: unknown; derived: boolean }
  | {
      type: typeof ACTIONS.RESTORE_PROJECT_SNAPSHOT; projectId: string; snapshot: Record<string, unknown>;
      revision?: number; savedAt?: string; recovered: boolean;
    };

export interface ProjectPersistenceOptions {
  session: PersistedSession | null | undefined;
  dispatch: (action: PersistenceAction) => void;
  enabled?: boolean;
  debounceMs?: number;
}

export interface ProjectPersistence {
  listLoading: boolean;
  historicalProjectId: string | null;
  projects: ProjectListRow[];
  listError: string | null;
  machineSeedError: string | null;
  refreshProjects: () => Promise<ProjectListRow[]>;
  openProject: (projectId: string, options?: { revision?: number | null }) => Promise<ProjectEnvelope>;
  duplicateProject: (projectId: string, targetProjectId: string) => Promise<ProjectEnvelope | undefined>;
  archiveProject: (projectId: string, archived?: boolean) => Promise<ProjectEnvelope | undefined>;
  removeProject: (projectId: string) => Promise<unknown>;
}

const isRequestError = (error: unknown): error is RequestError =>
  error instanceof Error && typeof (error as Partial<RequestError>).status === "number";
const messageOf = (error: unknown): string => (error instanceof Error ? error.message : String(error));
const statusOf = (error: unknown): number | undefined => (isRequestError(error) ? error.status : undefined);

// ---- API ---------------------------------------------------------------------------------------

const API_BASE =
  import.meta.env.VITE_API_BASE !== undefined
    ? import.meta.env.VITE_API_BASE
    : import.meta.env.DEV
      ? "/api"
      : "";

interface ErrorDetail { message?: string; type?: string; error?: { message?: string; type?: string } }

async function parseJson<T>(res: Response): Promise<T> {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (body as { detail?: string | ErrorDetail } | null)?.detail;
    const error = new Error(
      typeof detail === "string"
        ? detail
        : detail?.message || detail?.error?.message || res.statusText || `Request failed (${res.status})`,
    ) as RequestError;
    error.status = res.status;
    error.type = (typeof detail === "object" && (detail?.type || detail?.error?.type)) || "request_failed";
    error.body = body;
    throw error;
  }
  return body as T;
}

export async function listPersistentProjects({ includeArchived = false }: { includeArchived?: boolean } = {}): Promise<ProjectListBody> {
  const params = new URLSearchParams();
  if (includeArchived) params.set("include_archived", "true");
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return parseJson(await fetch(`${API_BASE}/v1/projects${suffix}`));
}

export async function loadPersistentProject(projectId: string, { revision = null }: { revision?: number | null } = {}): Promise<ProjectBody> {
  const params = new URLSearchParams();
  if (revision !== null && revision !== undefined) params.set("revision", String(revision));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return parseJson(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}${suffix}`),
  );
}

export async function savePersistentProject(
  projectId: string,
  snapshot: unknown,
  { expectedRevision = null, metadata = {} }: { expectedRevision?: number | null; metadata?: Record<string, unknown> } = {},
): Promise<ProjectBody> {
  return parseJson(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/snapshot`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        snapshot,
        expected_revision: expectedRevision,
        metadata,
      }),
    }),
  );
}

export async function seedMachineProjectFromIntake(intake: unknown): Promise<{ project?: unknown }> {
  return parseJson(
    await fetch(`${API_BASE}/v1/machine-projects/from-intake`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ intake }),
    }),
  );
}

export async function duplicatePersistentProject(projectId: string, targetProjectId: string): Promise<ProjectBody> {
  return parseJson(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/duplicate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_project_id: targetProjectId }),
    }),
  );
}

export async function archivePersistentProject(projectId: string, archived = true): Promise<ProjectBody> {
  return parseJson(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/archive`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ archived: Boolean(archived) }),
    }),
  );
}

export async function deletePersistentProject(projectId: string): Promise<unknown> {
  return parseJson(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}`, {
      method: "DELETE",
    }),
  );
}

// ---- Hook --------------------------------------------------------------------------------------

export function useProjectPersistence({ session, dispatch, enabled = true, debounceMs = 700 }: ProjectPersistenceOptions): ProjectPersistence {
  const [projects, setProjects] = useState<ProjectListRow[]>([]);
  const [firstListLoaded, setFirstListLoaded] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [machineSeedError, setMachineSeedError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scheduledProjectRef = useRef<string | null>(null);
  const pendingSerializedRef = useRef<string | null>(null);
  const savedSerializedRef = useRef<string | null>(null);
  const machineSeedRef = useRef<string | null>(null);
  const activeProjectRef = useRef<string | null>(session?.projectId || null);
  // A project opened at an explicit revision is read-only: saving an older one would fork history.
  const historicalProjectRef = useRef<string | null>(null);
  const [historicalProjectId, setHistoricalProjectId] = useState<string | null>(null);

  useEffect(() => {
    activeProjectRef.current = session?.projectId || null;
  }, [session?.projectId]);

  const refreshProjects = useCallback(async (): Promise<ProjectListRow[]> => {
    if (!enabled) return [];
    try {
      const body = await listPersistentProjects();
      const next = body.projects || [];
      setProjects(next);
      setListError(null);
      return next;
    } catch (error) {
      setListError(messageOf(error));
      return [];
    } finally {
      setFirstListLoaded(true);
    }
  }, [enabled]);

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  useEffect(() => {
    if (!enabled || !session?.projectId || !session?.intake || session?.machineProject) {
      return undefined;
    }
    const projectId = session.projectId;
    let seedKey: string;
    try {
      seedKey = `${projectId}:${JSON.stringify(session.intake)}`;
    } catch (error) {
      setMachineSeedError(`Machine intake is not serializable: ${messageOf(error)}`);
      return undefined;
    }
    if (machineSeedRef.current === seedKey) return undefined;
    machineSeedRef.current = seedKey;
    let cancelled = false;
    // A reopened project whose snapshot predates machine models gets one derived from its intake.
    // It is shown, not saved: it reaches storage only with the next real edit.
    const reopened = session.sessionOrigin === "persistent_project" && Number(session.snapshotRevision) > 0;
    const baseline = savedSerializedRef.current;
    const unedited = reopened && baseline === canonicalJson(projectSnapshot(session));
    seedMachineProjectFromIntake(session.intake)
      .then((body) => {
        if (cancelled || activeProjectRef.current !== projectId) return;
        const machineProject = body.project || null;
        if (unedited && savedSerializedRef.current === baseline) {
          savedSerializedRef.current = canonicalJson(projectSnapshot({ ...session, machineProject }));
        }
        dispatch({
          type: ACTIONS.SET_MACHINE_PROJECT,
          machineProject,
          derived: reopened,
        });
        setMachineSeedError(null);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        machineSeedRef.current = null;
        setMachineSeedError(messageOf(error));
      });
    return () => {
      cancelled = true;
    };
  }, [dispatch, enabled, session?.intake, session?.machineProject, session?.projectId]);

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  useEffect(() => {
    // A pending save belongs to one project. Leaving that project (cancel, reset, switch)
    // discards it; ordinary re-renders of the same project must not.
    if (timerRef.current && scheduledProjectRef.current !== (session?.projectId || null)) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
      pendingSerializedRef.current = null;
    }
    if (!enabled || session?.mode === "digital" || !sessionIsPersistable(session) || !session?.projectId) return undefined;
    if (historicalProjectRef.current && historicalProjectRef.current === session.projectId) return undefined;

    const snapshot = projectSnapshot(session);
    let serialized: string;
    try {
      serialized = canonicalJson(snapshot);
    } catch (error) {
      dispatch({
        type: ACTIONS.SET_PERSISTENCE,
        status: STATUS.failed,
        error: `Project state is not serializable: ${messageOf(error)}`,
      });
      return undefined;
    }

    if (
      serialized === savedSerializedRef.current ||
      serialized === pendingSerializedRef.current
    ) {
      return undefined;
    }

    pendingSerializedRef.current = serialized;
    scheduledProjectRef.current = session.projectId;
    if (timerRef.current) clearTimeout(timerRef.current);
    const projectId = session.projectId;
    timerRef.current = setTimeout(async () => {
      timerRef.current = null;
      const expectedRevision = Number(session.snapshotRevision || 0);
      dispatch({ type: ACTIONS.SET_PERSISTENCE, status: STATUS.saving });
      try {
        const body = await savePersistentProject(projectId, snapshot, {
          expectedRevision,
          metadata: {
            client: "splice-ui",
            session_origin: session.sessionOrigin,
          },
        });
        if (activeProjectRef.current !== projectId) return;
        const envelope: ProjectEnvelope = body.project || {};
        savedSerializedRef.current = serialized;
        dispatch({
          type: ACTIONS.SET_PERSISTENCE,
          status: STATUS.saved,
          revision: envelope.revision,
          savedAt: envelope.saved_at,
        });
        refreshProjects();
      } catch (error) {
        if (activeProjectRef.current !== projectId) return;
        dispatch({
          type: ACTIONS.SET_PERSISTENCE,
          status:
            statusOf(error) === 409
              ? STATUS.conflict
              : STATUS.failed,
          error: messageOf(error),
        });
      } finally {
        if (pendingSerializedRef.current === serialized) {
          pendingSerializedRef.current = null;
        }
      }
    }, debounceMs);
    return undefined;
  }, [debounceMs, dispatch, enabled, refreshProjects, session]);

  const openProject = useCallback(
    async (projectId: string, { revision = null }: { revision?: number | null } = {}): Promise<ProjectEnvelope> => {
      dispatch({ type: ACTIONS.SET_PERSISTENCE, status: STATUS.saving });
      try {
        const body = await loadPersistentProject(projectId, { revision });
        const envelope: ProjectEnvelope = body.project || {};
        const snapshot = envelope.snapshot || {};
        const recovery = envelope.recovery || {};
        // Compare future saves with the snapshot as the session will hold it, so loading
        // (key order, default fields) never counts as a change.
        const restored = projectSessionReducer(createEmptySession(), {
          type: ACTIONS.RESTORE_PROJECT_SNAPSHOT, projectId: envelope.project_id || projectId, snapshot,
          revision: envelope.revision, savedAt: envelope.saved_at, recovered: Boolean(recovery.used),
        });
        savedSerializedRef.current = canonicalJson(projectSnapshot(restored));
        pendingSerializedRef.current = null;
        historicalProjectRef.current = revision !== null && revision !== undefined
          ? envelope.project_id || projectId : null;
        setHistoricalProjectId(historicalProjectRef.current);
        machineSeedRef.current = snapshot.machineProject ? "restored" : null;
        dispatch({
          type: ACTIONS.RESTORE_PROJECT_SNAPSHOT,
          projectId: envelope.project_id || projectId,
          snapshot,
          revision: envelope.revision,
          savedAt: envelope.saved_at,
          recovered: Boolean(recovery.used),
        });
        return envelope;
      } catch (error) {
        dispatch({
          type: ACTIONS.SET_PERSISTENCE,
          status:
            statusOf(error) === 409
              ? STATUS.conflict
              : STATUS.failed,
          error: messageOf(error),
        });
        throw error;
      }
    },
    [dispatch],
  );

  const duplicateProject = useCallback(
    async (projectId: string, targetProjectId: string) => {
      const body = await duplicatePersistentProject(projectId, targetProjectId);
      await refreshProjects();
      return body.project;
    },
    [refreshProjects],
  );

  const archiveProject = useCallback(
    async (projectId: string, archived = true) => {
      const body = await archivePersistentProject(projectId, archived);
      await refreshProjects();
      return body.project;
    },
    [refreshProjects],
  );

  const removeProject = useCallback(
    async (projectId: string) => {
      const body = await deletePersistentProject(projectId);
      await refreshProjects();
      return body;
    },
    [refreshProjects],
  );

  return {
    listLoading: enabled && !firstListLoaded,
    historicalProjectId,
    projects,
    listError,
    machineSeedError,
    refreshProjects,
    openProject,
    duplicateProject,
    archiveProject,
    removeProject,
  };
}
