export type CadProjectSource =
  | { type: "blank" }
  | { type: "demo" }
  | { type: "kicad"; filename: string }
  | { type: "template"; templateId: string };

export type CadProject = {
  id: string;
  name: string;
  createdAt: string;
  lastOpenedAt: string;
  source: CadProjectSource;
};

const STORAGE_KEY = "circuit-ai:cad:projects:v1";
const ACTIVE_KEY = "circuit-ai:cad:activeProjectId:v1";

function nowIso() {
  return new Date().toISOString();
}

function safeParse<T>(s: string | null): T | null {
  if (!s) return null;
  try {
    return JSON.parse(s) as T;
  } catch {
    return null;
  }
}

export function loadProjects(): CadProject[] {
  if (typeof window === "undefined") return [];
  return safeParse<CadProject[]>(window.localStorage.getItem(STORAGE_KEY)) ?? [];
}

export function saveProjects(projects: CadProject[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
}

export function getActiveProjectId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACTIVE_KEY);
}

export function setActiveProjectId(id: string | null) {
  if (id) window.localStorage.setItem(ACTIVE_KEY, id);
  else window.localStorage.removeItem(ACTIVE_KEY);
}

export function createProject(name: string, source: CadProjectSource = { type: "blank" }): CadProject {
  const id = crypto.randomUUID ? crypto.randomUUID() : `p_${Math.random().toString(16).slice(2)}`;
  const t = nowIso();
  return { id, name, createdAt: t, lastOpenedAt: t, source };
}

export function upsertProject(projects: CadProject[], project: CadProject): CadProject[] {
  const next = [...projects];
  const idx = next.findIndex((p) => p.id === project.id);
  if (idx >= 0) next[idx] = project;
  else next.unshift(project);
  return next;
}

export function touchProject(p: CadProject): CadProject {
  return { ...p, lastOpenedAt: nowIso() };
}
