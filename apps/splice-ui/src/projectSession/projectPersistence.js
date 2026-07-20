import { useCallback, useEffect, useRef, useState } from "react";
import {
  ACTIONS,
  PERSISTENCE_STATUS,
  projectSnapshot,
  sessionIsPersistable,
} from "./projectSession.js";

const API_BASE =
  import.meta.env.VITE_API_BASE !== undefined
    ? import.meta.env.VITE_API_BASE
    : import.meta.env.DEV
      ? "/api"
      : "";

async function parseJson(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body?.detail;
    const error = new Error(
      typeof detail === "string"
        ? detail
        : detail?.message || detail?.error?.message || res.statusText || `Request failed (${res.status})`,
    );
    error.status = res.status;
    error.type = detail?.type || detail?.error?.type || "request_failed";
    error.body = body;
    throw error;
  }
  return body;
}

export async function listPersistentProjects({ includeArchived = false } = {}) {
  const params = new URLSearchParams();
  if (includeArchived) params.set("include_archived", "true");
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return parseJson(await fetch(`${API_BASE}/v1/projects${suffix}`));
}

export async function loadPersistentProject(projectId, { revision = null } = {}) {
  const params = new URLSearchParams();
  if (revision !== null && revision !== undefined) params.set("revision", String(revision));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return parseJson(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}${suffix}`),
  );
}

export async function savePersistentProject(
  projectId,
  snapshot,
  { expectedRevision = null, metadata = {} } = {},
) {
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

export async function seedMachineProjectFromIntake(intake) {
  return parseJson(
    await fetch(`${API_BASE}/v1/machine-projects/from-intake`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ intake }),
    }),
  );
}

export async function duplicatePersistentProject(projectId, targetProjectId) {
  return parseJson(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/duplicate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_project_id: targetProjectId }),
    }),
  );
}

export async function archivePersistentProject(projectId, archived = true) {
  return parseJson(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/archive`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ archived: Boolean(archived) }),
    }),
  );
}

export async function deletePersistentProject(projectId) {
  return parseJson(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}`, {
      method: "DELETE",
    }),
  );
}

export function useProjectPersistence({ session, dispatch, enabled = true, debounceMs = 700 }) {
  const [projects, setProjects] = useState([]);
  const [listError, setListError] = useState(null);
  const [machineSeedError, setMachineSeedError] = useState(null);
  const timerRef = useRef(null);
  const pendingSerializedRef = useRef(null);
  const savedSerializedRef = useRef(null);
  const machineSeedRef = useRef(null);
  const activeProjectRef = useRef(session?.projectId || null);

  useEffect(() => {
    activeProjectRef.current = session?.projectId || null;
  }, [session?.projectId]);

  const refreshProjects = useCallback(async () => {
    if (!enabled) return [];
    try {
      const body = await listPersistentProjects();
      const next = body.projects || [];
      setProjects(next);
      setListError(null);
      return next;
    } catch (error) {
      setListError(error.message);
      return [];
    }
  }, [enabled]);

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  useEffect(() => {
    if (!enabled || !session?.projectId || !session?.intake || session?.machineProject) {
      return undefined;
    }
    let seedKey;
    try {
      seedKey = `${session.projectId}:${JSON.stringify(session.intake)}`;
    } catch (error) {
      setMachineSeedError(`Machine intake is not serializable: ${error.message}`);
      return undefined;
    }
    if (machineSeedRef.current === seedKey) return undefined;
    machineSeedRef.current = seedKey;
    let cancelled = false;
    seedMachineProjectFromIntake(session.intake)
      .then((body) => {
        if (cancelled || activeProjectRef.current !== session.projectId) return;
        dispatch({
          type: ACTIONS.SET_MACHINE_PROJECT,
          machineProject: body.project || null,
        });
        setMachineSeedError(null);
      })
      .catch((error) => {
        if (cancelled) return;
        machineSeedRef.current = null;
        setMachineSeedError(error.message);
      });
    return () => {
      cancelled = true;
    };
  }, [dispatch, enabled, session?.intake, session?.machineProject, session?.projectId]);

  useEffect(() => {
    if (!enabled || !sessionIsPersistable(session)) return undefined;

    const snapshot = projectSnapshot(session);
    let serialized;
    try {
      serialized = JSON.stringify(snapshot);
    } catch (error) {
      dispatch({
        type: ACTIONS.SET_PERSISTENCE,
        status: PERSISTENCE_STATUS.failed,
        error: `Project state is not serializable: ${error.message}`,
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
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      const projectId = session.projectId;
      const expectedRevision = Number(session.snapshotRevision || 0);
      dispatch({ type: ACTIONS.SET_PERSISTENCE, status: PERSISTENCE_STATUS.saving });
      try {
        const body = await savePersistentProject(projectId, snapshot, {
          expectedRevision,
          metadata: {
            client: "splice-ui",
            session_origin: session.sessionOrigin,
          },
        });
        if (activeProjectRef.current !== projectId) return;
        const envelope = body.project || {};
        savedSerializedRef.current = serialized;
        dispatch({
          type: ACTIONS.SET_PERSISTENCE,
          status: PERSISTENCE_STATUS.saved,
          revision: envelope.revision,
          savedAt: envelope.saved_at,
        });
        refreshProjects();
      } catch (error) {
        if (activeProjectRef.current !== projectId) return;
        dispatch({
          type: ACTIONS.SET_PERSISTENCE,
          status:
            error.status === 409
              ? PERSISTENCE_STATUS.conflict
              : PERSISTENCE_STATUS.failed,
          error: error.message,
        });
      } finally {
        if (pendingSerializedRef.current === serialized) {
          pendingSerializedRef.current = null;
        }
      }
    }, debounceMs);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [debounceMs, dispatch, enabled, refreshProjects, session]);

  const openProject = useCallback(
    async (projectId, { revision = null } = {}) => {
      dispatch({ type: ACTIONS.SET_PERSISTENCE, status: PERSISTENCE_STATUS.saving });
      try {
        const body = await loadPersistentProject(projectId, { revision });
        const envelope = body.project || {};
        const snapshot = envelope.snapshot || {};
        const recovery = envelope.recovery || {};
        savedSerializedRef.current = JSON.stringify(snapshot);
        pendingSerializedRef.current = null;
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
            error.status === 409
              ? PERSISTENCE_STATUS.conflict
              : PERSISTENCE_STATUS.failed,
          error: error.message,
        });
        throw error;
      }
    },
    [dispatch],
  );

  const duplicateProject = useCallback(
    async (projectId, targetProjectId) => {
      const body = await duplicatePersistentProject(projectId, targetProjectId);
      await refreshProjects();
      return body.project;
    },
    [refreshProjects],
  );

  const archiveProject = useCallback(
    async (projectId, archived = true) => {
      const body = await archivePersistentProject(projectId, archived);
      await refreshProjects();
      return body.project;
    },
    [refreshProjects],
  );

  const removeProject = useCallback(
    async (projectId) => {
      const body = await deletePersistentProject(projectId);
      await refreshProjects();
      return body;
    },
    [refreshProjects],
  );

  return {
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
