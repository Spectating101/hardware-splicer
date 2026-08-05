'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  Archive,
  ArrowRight,
  Bot,
  BrainCircuit,
  Check,
  CheckCircle2,
  CirclePlay,
  FileArchive,
  FileUp,
  FolderKanban,
  History,
  LoaderCircle,
  MessageSquareText,
  PackageCheck,
  RefreshCw,
  RotateCcw,
  Save,
  Send,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  X,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePageTitle } from '@/components/use-page-title';
import {
  getProxyErrorMessage,
  isProxyFailure,
  readJsonPayload,
  type ProxyErrorPayload,
} from '@/lib/proxy-client';

type JsonRecord = Record<string, unknown>;
type BusyKind =
  | 'projects'
  | 'create'
  | 'load'
  | 'brief'
  | 'upload'
  | 'proposal'
  | 'turn'
  | 'decision'
  | 'preview'
  | 'repair'
  | 'package'
  | null;
type Mode = 'greenfield' | 'repair' | 'validation' | 'robotics';
type Decision = 'accepted' | 'rejected';
type UploadState = 'pending' | 'uploading' | 'uploaded' | 'failed';

type UploadItem = {
  id: string;
  file: File;
  state: UploadState;
  error?: string;
};

type ProjectSummary = {
  project_id?: string;
  name?: string;
  project_name?: string;
  revision?: number;
  archived?: boolean;
  saved_at?: string;
};

type ProjectEnvelope = {
  project_id?: string;
  revision?: number;
  snapshot?: JsonRecord;
  saved_at?: string;
};

type ProjectResponse = { ok?: boolean; project?: ProjectEnvelope };
type ProjectsResponse = { ok?: boolean; projects?: ProjectSummary[] };
type SessionResponse = { ok?: boolean; revision?: number; session?: JsonRecord };
type ActionResponse = { ok?: boolean; revision?: number; action?: JsonRecord };
type RepairResponse = {
  ok?: boolean;
  revision?: number;
  repair_session?: JsonRecord;
  parent_action?: JsonRecord;
  idempotent?: boolean;
};
type PackageResponse = {
  ok?: boolean;
  revision?: number;
  package?: JsonRecord;
  packages?: JsonRecord[];
  idempotent?: boolean;
};

const templates: Array<{
  id: Mode;
  title: string;
  detail: string;
  starter: string;
}> = [
  {
    id: 'greenfield',
    title: 'Build something new',
    detail: 'Start from requirements, references, parts, and constraints.',
    starter: 'Design a buildable hardware system from the supplied requirements and engineering evidence.',
  },
  {
    id: 'validation',
    title: 'Validation fixture',
    detail: 'Prepare an adapter, test board, socket fixture, or lab interface.',
    starter: 'Prepare a pre-fabrication validation fixture with explicit voltage domains, interfaces, tests, and bring-up blockers.',
  },
  {
    id: 'repair',
    title: 'Repair or inherit',
    detail: 'Work from an existing board, incomplete files, measurements, and symptoms.',
    starter: 'Understand and safely repair or adapt the existing hardware without inventing missing evidence.',
  },
  {
    id: 'robotics',
    title: 'Robot or machine',
    detail: 'Coordinate electrical, mechanical, firmware, and physical bring-up.',
    starter: 'Design or revise a mechatronic system with traceable interfaces and controlled physical bring-up.',
  },
];

const previewActions = new Set(['run_guided_plan', 'run_compose']);
const MAX_FILE_BYTES = 16 * 1024 * 1024;

function record(value: unknown): JsonRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonRecord
    : {};
}

function rows(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((row): row is JsonRecord => Boolean(row) && typeof row === 'object' && !Array.isArray(row))
    : [];
}

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((row) => String(row || '')).filter(Boolean)
    : [];
}

function text(value: unknown, fallback = '—') {
  return value === undefined || value === null || value === '' ? fallback : String(value);
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 72);
}

function requestIdentity(prefix: string) {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function closedGate(value: unknown) {
  return value === true ? 'authorized' : 'closed';
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MiB`;
}

function replaceAction(session: JsonRecord | null, actionId: string, action: JsonRecord) {
  if (!session) return session;
  return {
    ...session,
    actions: rows(session.actions).map((row) => text(row.action_id, '') === actionId ? action : row),
  };
}

function projectName(snapshot: JsonRecord | null, fallback = '') {
  return text(snapshot?.projectName || snapshot?.name, fallback);
}

export default function CanonicalProjectStudioPage() {
  usePageTitle('Project Studio | Hardware Splicer');
  const fileInput = useRef<HTMLInputElement>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState('');
  const [name, setName] = useState('');
  const [mission, setMission] = useState('');
  const [mode, setMode] = useState<Mode>('validation');
  const [revision, setRevision] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<JsonRecord | null>(null);
  const [session, setSession] = useState<JsonRecord | null>(null);
  const [sessionId, setSessionId] = useState('');
  const [packages, setPackages] = useState<JsonRecord[]>([]);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState<BusyKind>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const sources = rows(snapshot?.engineeringSources);
  const parserRuns = rows(snapshot?.engineeringSourceParserRuns);
  const requirements = rows(session?.requirements);
  const candidates = rows(session?.architecture_candidates);
  const actions = rows(session?.actions);
  const turns = rows(session?.conversationTurns);
  const openQuestions = strings(session?.open_questions);
  const failedActions = actions.filter((action) => text(action.status, '') === 'failed');
  const proposedActions = actions.filter((action) => text(action.status, '') === 'proposed');
  const latestCandidate = candidates[0] || null;
  const activeProject = Boolean(projectId && revision && snapshot);

  const blockers = useMemo(() => {
    const values = [...openQuestions];
    for (const action of failedActions) {
      const result = record(action.tool_result);
      const errorRecord = record(result.error);
      const summary = record(result.summary);
      const message = text(errorRecord.message || summary.error, 'Software preview failed.');
      if (!values.includes(message)) values.push(message);
    }
    for (const turn of turns) {
      for (const blocker of strings(turn.blockers)) {
        if (!values.includes(blocker)) values.push(blocker);
      }
    }
    return values;
  }, [failedActions, openQuestions, turns]);

  const stages = [
    { label: 'Brief', done: activeProject, detail: activeProject ? 'Project revision exists' : 'Create or resume a project' },
    { label: 'Evidence', done: sources.length > 0, detail: sources.length ? `${sources.length} registered sources` : 'Add files and references' },
    { label: 'Candidate', done: Boolean(session), detail: session ? `${candidates.length} candidate${candidates.length === 1 ? '' : 's'}` : 'Generate grounded proposals' },
    {
      label: 'Review',
      done: actions.some((action) => ['accepted', 'rejected', 'completed', 'failed'].includes(text(action.status, ''))),
      detail: failedActions.length ? `${failedActions.length} preview failure${failedActions.length === 1 ? '' : 's'}` : 'Review and validate actions',
    },
    { label: 'JARVIS', done: turns.length > 0, detail: turns.length ? `${turns.length} persisted turn${turns.length === 1 ? '' : 's'}` : 'Ask what is blocked or next' },
    { label: 'Package', done: packages.length > 0, detail: packages.length ? `${packages.length} export${packages.length === 1 ? '' : 's'}` : 'Create a reviewable handoff' },
  ];

  const nextMove = !activeProject
    ? 'Create or resume a project.'
    : sources.length === 0
      ? 'Add at least one engineering source or file.'
      : !session
        ? 'Generate a source-grounded candidate.'
        : proposedActions.length > 0
          ? 'Review the proposed engineering actions.'
          : failedActions.length > 0
            ? 'Create a bounded repair successor or ask JARVIS about the failure.'
            : turns.length === 0
              ? 'Ask JARVIS for the next evidence-backed decision.'
              : packages.length === 0
                ? 'Export the current revision as an Engineering Package.'
                : 'Continue resolving blockers; the package does not authorize physical action.';

  async function loadProjectList() {
    setBusy('projects');
    try {
      const response = await fetch('/api/proxy/engineering/projects', { cache: 'no-store' });
      const payload = await readJsonPayload<ProjectsResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) return;
      setProjects((payload as ProjectsResponse).projects || []);
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    void loadProjectList();
  }, []);

  async function refreshProject(id = projectId) {
    if (!id.trim()) return;
    const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(id.trim())}`, { cache: 'no-store' });
    const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
    if (!response.ok || isProxyFailure(payload)) {
      throw new Error(getProxyErrorMessage(payload, `Could not load ${id}.`));
    }
    const envelope = (payload as ProjectResponse).project || {};
    const nextSnapshot = record(envelope.snapshot);
    const nextRevision = Number(envelope.revision);
    if (!Number.isInteger(nextRevision) || nextRevision < 1) {
      throw new Error('The project returned no valid revision.');
    }
    const sessions = rows(nextSnapshot.engineeringAiSessions);
    const nextSession = sessions.length ? sessions[sessions.length - 1] : null;
    setProjectId(id.trim());
    setSnapshot(nextSnapshot);
    setRevision(nextRevision);
    setName(projectName(nextSnapshot, id.trim()));
    setMission(text(nextSnapshot.mission, ''));
    const loadedMode = text(nextSnapshot.mode, 'validation');
    setMode(templates.some((template) => template.id === loadedMode) ? loadedMode as Mode : 'validation');
    setSession(nextSession);
    setSessionId(text(nextSession?.session_id, ''));

    const packageResponse = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(id.trim())}/engineering-packages`, { cache: 'no-store' });
    const packagePayload = await readJsonPayload<PackageResponse | ProxyErrorPayload>(packageResponse);
    if (packageResponse.ok && !isProxyFailure(packagePayload)) {
      setPackages((packagePayload as PackageResponse).packages || []);
    } else {
      setPackages([]);
    }
  }

  async function loadProject(id = projectId) {
    if (!id.trim()) {
      setError('Choose a project or enter its ID.');
      return;
    }
    setBusy('load');
    setError(null);
    setNotice(null);
    try {
      await refreshProject(id);
      setNotice('Loaded the latest revision and active engineering context.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project load failed.');
    } finally {
      setBusy(null);
    }
  }

  async function createProject() {
    const selectedTemplate = templates.find((template) => template.id === mode) || templates[0];
    const finalName = name.trim() || 'Untitled hardware project';
    const finalMission = mission.trim() || selectedTemplate.starter;
    const generatedId = projectId.trim() || `${slugify(finalName) || 'hardware-project'}-${Math.random().toString(36).slice(2, 7)}`;
    setBusy('create');
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(generatedId)}/snapshot`, {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          expected_revision: 0,
          snapshot: {
            projectId: generatedId,
            projectName: finalName,
            name: finalName,
            mission: finalMission,
            mode,
            currentStage: 'source_intake',
            constraints: {},
            engineeringSources: [],
            engineeringSourceUploads: [],
            engineeringSourceParserRuns: [],
            engineeringParsedSources: [],
            engineeringAiSessions: [],
            engineeringPackages: [],
            fabrication_authorized: false,
            firmware_flash_authorized: false,
            flash_authorized: false,
            power_on_authorized: false,
            motion_authorized: false,
            operational_authorized: false,
            release_authorized: false,
            engineeringReadiness: {
              fabrication_authorized: false,
              flash_authorized: false,
              power_on_authorized: false,
              motion_authorized: false,
              release_authorized: false,
            },
          },
          metadata: {
            source: 'canonical_project_studio',
            onboarding_template: mode,
            automatic_authorization: false,
            physical_authority_unchanged: true,
          },
        }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not create the project.'));
      }
      setProjectId(generatedId);
      setName(finalName);
      setMission(finalMission);
      await refreshProject(generatedId);
      await loadProjectList();
      setNotice('Project created. Add evidence before asking the system to engineer from it.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project creation failed.');
    } finally {
      setBusy(null);
    }
  }

  async function saveBrief() {
    if (!activeProject || !snapshot || !revision) return;
    setBusy('brief');
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/snapshot`, {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          expected_revision: revision,
          snapshot: {
            ...snapshot,
            projectId,
            projectName: name.trim() || projectId,
            name: name.trim() || projectId,
            mission: mission.trim(),
            mode,
          },
          metadata: {
            source: 'canonical_project_studio_brief',
            automatic_authorization: false,
            physical_authority_unchanged: true,
          },
        }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'The project brief could not be saved.'));
      }
      await refreshProject(projectId);
      setNotice('Project brief saved as a new revision.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Brief save failed.');
    } finally {
      setBusy(null);
    }
  }

  function addFiles(files: File[]) {
    setUploads((current) => [
      ...current,
      ...files.map((file): UploadItem => ({
        id: `${file.name}-${file.size}-${file.lastModified}-${Math.random()}`,
        file,
        state: file.size > MAX_FILE_BYTES ? 'failed' : 'pending',
        error: file.size > MAX_FILE_BYTES ? 'File exceeds the current 16 MiB limit.' : undefined,
      })),
    ]);
  }

  async function uploadPending() {
    if (!activeProject || !revision) {
      setError('Create or load a project before uploading evidence.');
      return;
    }
    const pending = uploads.filter((item) => item.state === 'pending' || item.state === 'failed')
      .filter((item) => item.file.size <= MAX_FILE_BYTES);
    if (!pending.length) return;
    setBusy('upload');
    setError(null);
    setNotice(null);
    let expectedRevision = revision;
    try {
      for (const item of pending) {
        setUploads((current) => current.map((row) => row.id === item.id ? { ...row, state: 'uploading', error: undefined } : row));
        const form = new FormData();
        form.append('file', item.file, item.file.name);
        form.append('expected_revision', String(expectedRevision));
        form.append('authority_ceiling', 'declared');
        form.append('captured_at', '');
        form.append('metadata_json', JSON.stringify({
          intake_surface: 'canonical_project_studio',
          browser_file_type: item.file.type || null,
          browser_last_modified_ms: item.file.lastModified,
        }));
        const response = await fetch(
          `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/sources/ingest-file`,
          { method: 'POST', body: form, cache: 'no-store' },
        );
        const payload = await readJsonPayload<JsonRecord | ProxyErrorPayload>(response);
        if (!response.ok || isProxyFailure(payload)) {
          throw new Error(getProxyErrorMessage(payload, `Could not upload ${item.file.name}.`));
        }
        expectedRevision = Number(record(payload).revision || expectedRevision);
        setUploads((current) => current.map((row) => row.id === item.id ? { ...row, state: 'uploaded' } : row));
      }
      await refreshProject(projectId);
      setNotice('Evidence registered. File identity is proven; engineering truth still depends on parsing and review.');
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Evidence upload failed.';
      setError(message);
      setUploads((current) => current.map((row) => row.state === 'uploading' ? { ...row, state: 'failed', error: message } : row));
    } finally {
      setBusy(null);
    }
  }

  async function createProposal() {
    if (!activeProject || !revision) return;
    if (!mission.trim()) {
      setError('Write a concrete project mission first.');
      return;
    }
    setBusy('proposal');
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/ai-sessions`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          mission: mission.trim(),
          expected_revision: revision,
          constraints: record(snapshot?.constraints),
          model_profile: 'deep_synthesis',
          max_actions: 8,
        }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<SessionResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'The project candidate could not be generated.'));
      }
      const body = payload as SessionResponse;
      const nextSession = record(body.session);
      setSession(nextSession);
      setSessionId(text(nextSession.session_id, ''));
      setRevision(Number(body.revision));
      await refreshProject(projectId);
      setNotice('Candidate created as a proposal. Nothing has been fabricated, flashed, powered, or moved.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Candidate generation failed.');
    } finally {
      setBusy(null);
    }
  }

  async function decideAction(actionId: string, decision: Decision) {
    if (!revision || !sessionId) return;
    setBusy('decision');
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/ai-sessions/${encodeURIComponent(sessionId)}/actions/${encodeURIComponent(actionId)}/decision`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            expected_revision: revision,
            decision,
            reviewer: 'human',
            note: decision === 'accepted'
              ? 'Accepted as a proposal only. Preview remains a separate action.'
              : 'Rejected in the canonical Project Studio.',
          }),
          cache: 'no-store',
        },
      );
      const payload = await readJsonPayload<ActionResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'The action decision could not be recorded.'));
      }
      const body = payload as ActionResponse;
      setSession((current) => replaceAction(current, actionId, record(body.action)));
      setRevision(Number(body.revision));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Action decision failed.');
    } finally {
      setBusy(null);
    }
  }

  async function executePreview(actionId: string) {
    if (!revision || !sessionId) return;
    setBusy('preview');
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/ai-sessions/${encodeURIComponent(sessionId)}/actions/${encodeURIComponent(actionId)}/execute-preview`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ expected_revision: revision }),
          cache: 'no-store',
        },
      );
      const payload = await readJsonPayload<ActionResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'The software preview could not run.'));
      }
      const body = payload as ActionResponse;
      setSession((current) => replaceAction(current, actionId, record(body.action)));
      setRevision(Number(body.revision));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Software preview failed.');
    } finally {
      setBusy(null);
    }
  }

  async function proposeRepair(actionId: string) {
    if (!revision || !sessionId) return;
    setBusy('repair');
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/ai-sessions/${encodeURIComponent(sessionId)}/actions/${encodeURIComponent(actionId)}/repair`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ expected_revision: revision, max_actions: 6 }),
          cache: 'no-store',
        },
      );
      const payload = await readJsonPayload<RepairResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'A bounded repair successor could not be proposed.'));
      }
      const body = payload as RepairResponse;
      const repairSession = record(body.repair_session);
      setSession(repairSession);
      setSessionId(text(repairSession.session_id, ''));
      setRevision(Number(body.revision));
      setNotice('Repair created as a separate successor. The failed result remains immutable.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Repair proposal failed.');
    } finally {
      setBusy(null);
    }
  }

  async function askJarvis() {
    if (!revision || !sessionId || !question.trim()) return;
    setBusy('turn');
    setError(null);
    try {
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/ai-sessions/${encodeURIComponent(sessionId)}/turns`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            expected_revision: revision,
            message: question.trim(),
            client_request_id: requestIdentity('studio-turn'),
            max_proposals: 2,
          }),
          cache: 'no-store',
        },
      );
      const payload = await readJsonPayload<SessionResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'JARVIS could not answer from the current revision.'));
      }
      const body = payload as SessionResponse;
      setSession(record(body.session));
      setRevision(Number(body.revision));
      setQuestion('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'JARVIS turn failed.');
    } finally {
      setBusy(null);
    }
  }

  async function exportPackage() {
    if (!revision) return;
    const sourceRevision = revision;
    setBusy('package');
    setError(null);
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/engineering-packages`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ expected_revision: sourceRevision }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<PackageResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'The Engineering Package could not be created.'));
      }
      const body = payload as PackageResponse;
      const packageRecord = record(body.package);
      setRevision(Number(body.revision));
      setPackages((current) => [
        ...current.filter((row) => text(row.package_id, '') !== text(packageRecord.package_id, '')),
        packageRecord,
      ]);
      setNotice(body.idempotent
        ? `Verified the existing package for source revision ${sourceRevision}.`
        : `Created a deterministic package from source revision ${sourceRevision}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Package export failed.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="min-h-screen bg-[#030812] px-3 py-4 text-slate-100 sm:px-5 lg:px-7">
      <div className="mx-auto max-w-[1900px]">
        <header className="rounded-[1.75rem] border border-white/10 bg-[linear-gradient(135deg,#07111f,#09182a)] px-5 py-5 shadow-[0_24px_80px_rgba(2,6,23,0.38)]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-4">
              <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-100">
                <BrainCircuit className="h-7 w-7" />
              </div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.26em] text-cyan-300">Hardware Splicer</div>
                <h1 className="mt-1 text-2xl font-semibold text-white">Project Studio</h1>
                <p className="mt-1 max-w-4xl text-sm leading-6 text-slate-400">
                  Start with intent and evidence. Keep proposals, deterministic checks, repairs, JARVIS briefings, and handoff packages inside one revisioned project.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link href="/engineering"><Button variant="outline">Engineering inspector</Button></Link>
              <Link href="/engineering/source-lab"><Button variant="outline">Advanced source tools</Button></Link>
              <Link href="/engineering/packages"><Button variant="outline"><FileArchive className="mr-2 h-4 w-4" />Package workspace</Button></Link>
            </div>
          </div>
        </header>

        {error ? (
          <div className="mt-4 flex items-start gap-3 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm text-rose-100">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
          </div>
        ) : null}
        {notice ? (
          <div className="mt-4 flex items-start gap-3 rounded-2xl border border-emerald-300/20 bg-emerald-300/10 p-4 text-sm text-emerald-100">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> {notice}
          </div>
        ) : null}

        <div className="mt-5 grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)_360px]">
          <aside className="space-y-4">
            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Workspace</div>
                  <h2 className="mt-1 text-sm font-semibold text-white">Resume a project</h2>
                </div>
                <Button size="sm" variant="outline" onClick={loadProjectList} disabled={busy === 'projects'}>
                  {busy === 'projects' ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                </Button>
              </div>
              <div className="mt-4 space-y-2">
                {projects.length ? projects.map((project) => {
                  const id = text(project.project_id, '');
                  const active = id === projectId;
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => void loadProject(id)}
                      className={`w-full rounded-2xl border p-3 text-left transition-colors ${active ? 'border-cyan-300/25 bg-cyan-300/10' : 'border-white/8 bg-[#030812] hover:border-white/15'}`}
                    >
                      <div className="truncate text-sm font-semibold text-white">{text(project.name || project.project_name, id)}</div>
                      <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-slate-500">
                        <span className="truncate">{id}</span>
                        <span>r{text(project.revision, '—')}</span>
                      </div>
                    </button>
                  );
                }) : (
                  <div className="rounded-2xl border border-dashed border-white/10 p-5 text-center text-xs text-slate-500">No persisted projects found.</div>
                )}
              </div>
            </section>

            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-4">
              <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Progress</div>
              <div className="mt-4 space-y-3">
                {stages.map((stage, index) => (
                  <div key={stage.label} className="flex items-start gap-3">
                    <div className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold ${stage.done ? 'border-emerald-300/25 bg-emerald-300/10 text-emerald-100' : 'border-white/10 bg-[#030812] text-slate-500'}`}>
                      {stage.done ? <Check className="h-3.5 w-3.5" /> : index + 1}
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-white">{stage.label}</div>
                      <div className="mt-1 text-[11px] leading-4 text-slate-500">{stage.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </aside>

          <section className="space-y-5">
            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-fuchsia-300">1 · Define the work</div>
                  <h2 className="mt-2 text-lg font-semibold text-white">What are you trying to build, verify, repair, or understand?</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-400">Choose a starting pattern, then describe the outcome in ordinary engineering language.</p>
                </div>
                {activeProject ? (
                  <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1.5 text-xs text-cyan-100">Revision {revision}</div>
                ) : null}
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {templates.map((template) => (
                  <button
                    key={template.id}
                    type="button"
                    onClick={() => {
                      setMode(template.id);
                      if (!mission.trim()) setMission(template.starter);
                    }}
                    className={`rounded-2xl border p-4 text-left transition-colors ${mode === template.id ? 'border-fuchsia-300/25 bg-fuchsia-300/10' : 'border-white/8 bg-[#030812] hover:border-white/15'}`}
                  >
                    <div className="text-sm font-semibold text-white">{template.title}</div>
                    <div className="mt-2 text-xs leading-5 text-slate-400">{template.detail}</div>
                  </button>
                ))}
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                <label className="text-xs font-semibold text-slate-300">
                  Project name
                  <input
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="Low-voltage DUT validation adapter"
                    className="mt-2 w-full rounded-xl border border-white/10 bg-[#030812] px-3 py-2.5 text-sm text-white outline-none focus:border-fuchsia-300/40"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-300">
                  Project ID <span className="font-normal text-slate-500">optional on creation</span>
                  <input
                    value={projectId}
                    onChange={(event) => setProjectId(event.target.value)}
                    placeholder="generated from the name"
                    disabled={activeProject}
                    className="mt-2 w-full rounded-xl border border-white/10 bg-[#030812] px-3 py-2.5 text-sm text-white outline-none disabled:text-slate-500"
                  />
                </label>
              </div>
              <label className="mt-4 block text-xs font-semibold text-slate-300">
                Mission and constraints
                <textarea
                  value={mission}
                  onChange={(event) => setMission(event.target.value)}
                  rows={5}
                  placeholder="Describe what success means, what already exists, and the most important constraints."
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-[#030812] px-4 py-3 text-sm leading-6 text-white outline-none focus:border-fuchsia-300/40"
                />
              </label>
              <div className="mt-4 flex flex-wrap justify-end gap-2">
                {!activeProject ? (
                  <Button onClick={createProject} disabled={busy !== null}>
                    {busy === 'create' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <FolderKanban className="mr-2 h-4 w-4" />}
                    Create project
                  </Button>
                ) : (
                  <Button onClick={saveBrief} disabled={busy !== null}>
                    {busy === 'brief' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                    Save brief as revision
                  </Button>
                )}
              </div>
            </section>

            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-300">2 · Add evidence</div>
                  <h2 className="mt-2 text-lg font-semibold text-white">Drop the files the project must actually respect</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-400">Datasheets, drawings, KiCad files, requirements, photos, test limits, firmware manifests, and prior project records all belong here.</p>
                </div>
                <div className="text-xs text-slate-500">{sources.length} registered · {parserRuns.length} parser runs</div>
              </div>
              <div
                className="mt-5 rounded-2xl border border-dashed border-cyan-300/25 bg-cyan-300/[0.04] p-7 text-center"
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  addFiles(Array.from(event.dataTransfer.files));
                }}
              >
                <FileUp className="mx-auto h-8 w-8 text-cyan-200" />
                <div className="mt-3 text-sm font-semibold text-white">Drop files or select them</div>
                <div className="mt-2 text-xs text-slate-500">Up to 16 MiB per file in the current multipart path. Upload establishes identity, not truth.</div>
                <input
                  ref={fileInput}
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(event) => {
                    addFiles(Array.from(event.target.files || []));
                    event.target.value = '';
                  }}
                />
                <Button className="mt-4" variant="outline" onClick={() => fileInput.current?.click()} disabled={!activeProject}>
                  Select evidence
                </Button>
              </div>
              {uploads.length ? (
                <div className="mt-4 space-y-2">
                  {uploads.map((item) => (
                    <div key={item.id} className="flex items-center gap-3 rounded-xl border border-white/8 bg-[#030812] px-3 py-2.5 text-xs">
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium text-slate-200">{item.file.name}</div>
                        <div className="mt-1 text-slate-500">{formatBytes(item.file.size)} · {item.state}</div>
                        {item.error ? <div className="mt-1 text-rose-200">{item.error}</div> : null}
                      </div>
                      {item.state === 'uploaded' ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : null}
                      {item.state === 'uploading' ? <LoaderCircle className="h-4 w-4 animate-spin text-cyan-300" /> : null}
                      <button type="button" onClick={() => setUploads((current) => current.filter((row) => row.id !== item.id))} className="text-slate-500 hover:text-white"><X className="h-4 w-4" /></button>
                    </div>
                  ))}
                </div>
              ) : null}
              <div className="mt-4 flex justify-end">
                <Button onClick={uploadPending} disabled={!activeProject || busy !== null || !uploads.some((item) => item.state === 'pending' || item.state === 'failed')}>
                  {busy === 'upload' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <UploadCloud className="mr-2 h-4 w-4" />}
                  Register pending files
                </Button>
              </div>
            </section>

            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-amber-300">3 · Generate and review</div>
                  <h2 className="mt-2 text-lg font-semibold text-white">Turn the brief and evidence into a reviewable candidate</h2>
                </div>
                <Button onClick={createProposal} disabled={!activeProject || busy !== null}>
                  {busy === 'proposal' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                  {session ? 'Generate another candidate' : 'Generate candidate'}
                </Button>
              </div>

              {!session ? (
                <div className="mt-5 rounded-2xl border border-dashed border-white/10 bg-[#030812] p-8 text-center text-sm text-slate-500">
                  No active candidate yet. The system will use the current project revision and registered source identities.
                </div>
              ) : (
                <div className="mt-5 space-y-5">
                  <article className="rounded-2xl border border-fuchsia-300/20 bg-fuchsia-300/5 p-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-fuchsia-200">{text(session.session_kind, 'project proposal')}</div>
                        <h3 className="mt-2 text-base font-semibold text-white">{text(latestCandidate?.title, 'Engineering candidate')}</h3>
                        <p className="mt-2 text-sm leading-6 text-slate-300">{text(latestCandidate?.summary || session.summary, 'No summary returned.')}</p>
                      </div>
                      <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-100">proposal</span>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-400">
                      <span className="rounded-full border border-white/10 px-3 py-1">{requirements.length} requirements</span>
                      <span className="rounded-full border border-white/10 px-3 py-1">{candidates.length} candidates</span>
                      <span className="rounded-full border border-white/10 px-3 py-1">{actions.length} actions</span>
                    </div>
                  </article>

                  <div className="grid gap-4 lg:grid-cols-2">
                    {requirements.slice(0, 6).map((requirement) => (
                      <div key={text(requirement.id)} className="rounded-2xl border border-white/8 bg-[#030812] p-4">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-200">{text(requirement.id)}</div>
                        <div className="mt-2 text-sm leading-6 text-slate-300">{text(requirement.statement)}</div>
                        <div className="mt-2 text-[10px] text-slate-500">Sources: {strings(requirement.source_ids).join(', ') || 'none declared'}</div>
                      </div>
                    ))}
                  </div>

                  <div className="space-y-3">
                    {actions.map((action) => {
                      const actionId = text(action.action_id, '');
                      const status = text(action.status, 'proposed');
                      const actionType = text(action.action_type, '');
                      const result = record(action.tool_result);
                      const canPreview = status === 'accepted' && previewActions.has(actionType) && !action.tool_result;
                      const canRepair = status === 'failed' && previewActions.has(actionType);
                      return (
                        <article key={actionId} className="rounded-2xl border border-white/10 bg-[#030812] p-4">
                          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-200">{actionType}</span>
                                <span className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-slate-400">{status}</span>
                              </div>
                              <h4 className="mt-2 text-sm font-semibold text-white">{text(action.title)}</h4>
                              <p className="mt-2 text-xs leading-5 text-slate-400">{text(action.rationale)}</p>
                              {result.status ? (
                                <div className={`mt-3 rounded-xl border p-3 text-xs ${result.status === 'failed' ? 'border-rose-300/20 bg-rose-300/5 text-rose-100' : 'border-emerald-300/20 bg-emerald-300/5 text-emerald-100'}`}>
                                  <div className="font-semibold">Software preview: {text(result.status)}</div>
                                  <div className="mt-1 text-slate-300">{text(record(result.error).message || record(result.summary).error || record(result.summary).ok, 'Result persisted.')}</div>
                                </div>
                              ) : null}
                            </div>
                            <div className="flex shrink-0 flex-wrap gap-2">
                              {status === 'proposed' ? (
                                <>
                                  <Button size="sm" variant="outline" onClick={() => decideAction(actionId, 'rejected')} disabled={busy !== null}>Reject</Button>
                                  <Button size="sm" onClick={() => decideAction(actionId, 'accepted')} disabled={busy !== null}><Check className="mr-2 h-3.5 w-3.5" />Accept proposal</Button>
                                </>
                              ) : null}
                              {canPreview ? (
                                <Button size="sm" onClick={() => executePreview(actionId)} disabled={busy !== null}><CirclePlay className="mr-2 h-3.5 w-3.5" />Run software preview</Button>
                              ) : null}
                              {canRepair ? (
                                <Button size="sm" variant="outline" onClick={() => proposeRepair(actionId)} disabled={busy !== null}><RotateCcw className="mr-2 h-3.5 w-3.5" />Propose repair</Button>
                              ) : null}
                            </div>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                </div>
              )}
            </section>

            <section className="rounded-3xl border border-cyan-300/15 bg-[#07111f] p-5">
              <div className="flex items-start gap-3">
                <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-100"><Bot className="h-5 w-5" /></div>
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-300">4 · Ask JARVIS</div>
                  <h2 className="mt-2 text-lg font-semibold text-white">Ask from the exact project revision</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-400">Use JARVIS for evidence-backed explanations, blockers, and next decisions. Suggested changes return as proposals.</p>
                </div>
              </div>
              {session ? (
                <>
                  <div className="mt-5 space-y-4">
                    {turns.map((turn) => (
                      <article key={text(turn.turn_id)} className="rounded-2xl border border-white/8 bg-[#030812] p-4">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">You</div>
                        <div className="mt-2 text-sm text-slate-200">{text(turn.user_message)}</div>
                        <div className="mt-4 border-l-2 border-cyan-300/30 pl-4">
                          <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-200">JARVIS · {text(turn.answer_kind)}</div>
                          <div className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">{text(turn.assistant_answer)}</div>
                        </div>
                      </article>
                    ))}
                  </div>
                  <textarea
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    rows={4}
                    placeholder="What is still unsupported? Which action should we review next? Is this ready for fabrication?"
                    className="mt-5 w-full rounded-2xl border border-white/10 bg-[#030812] px-4 py-3 text-sm leading-6 text-white outline-none focus:border-cyan-300/40"
                  />
                  <div className="mt-3 flex justify-end">
                    <Button onClick={askJarvis} disabled={!question.trim() || busy !== null}>
                      {busy === 'turn' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                      Ask from revision {revision}
                    </Button>
                  </div>
                </>
              ) : (
                <div className="mt-5 rounded-2xl border border-dashed border-white/10 bg-[#030812] p-7 text-center text-sm text-slate-500">Generate a project candidate before opening the revision-grounded conversation.</div>
              )}
            </section>

            <section className="rounded-3xl border border-emerald-300/15 bg-[#07111f] p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-emerald-300">5 · Handoff</div>
                  <h2 className="mt-2 text-lg font-semibold text-white">Export the current engineering history</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-400">The package captures source descriptors, requirements, candidates, decisions, software results, repairs, JARVIS briefings, blockers, hashes, and authority state.</p>
                </div>
                <Button onClick={exportPackage} disabled={!activeProject || busy !== null}>
                  {busy === 'package' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Archive className="mr-2 h-4 w-4" />}
                  Export revision {revision ?? '—'}
                </Button>
              </div>
              <div className="mt-5 space-y-3">
                {packages.length ? packages.map((packageRecord) => {
                  const packageId = text(packageRecord.package_id, '');
                  const href = `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/engineering-packages/${encodeURIComponent(packageId)}/download`;
                  return (
                    <article key={packageId} className="rounded-2xl border border-emerald-300/15 bg-emerald-300/5 p-4">
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                        <div className="min-w-0">
                          <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-200">Source revision {text(packageRecord.source_revision)}</div>
                          <div className="mt-2 break-all font-mono text-xs text-white">{packageId}</div>
                          <div className="mt-2 text-[10px] text-slate-500">ZIP SHA-256: {text(packageRecord.zip_sha256)}</div>
                        </div>
                        <a href={href} download><Button size="sm"><PackageCheck className="mr-2 h-3.5 w-3.5" />Verified ZIP</Button></a>
                      </div>
                    </article>
                  );
                }) : (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-[#030812] p-7 text-center text-sm text-slate-500">No package exported from this project yet.</div>
                )}
              </div>
            </section>
          </section>

          <aside className="space-y-4">
            <section className="rounded-3xl border border-cyan-300/15 bg-cyan-300/[0.04] p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-cyan-100"><ArrowRight className="h-4 w-4" />Next best move</div>
              <p className="mt-3 text-sm leading-6 text-slate-300">{nextMove}</p>
            </section>

            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Project truth</div>
              <div className="mt-4 space-y-3 text-xs">
                <div className="flex justify-between gap-3"><span className="text-slate-500">Project</span><span className="text-right text-slate-200">{activeProject ? projectName(snapshot, projectId) : 'Not created'}</span></div>
                <div className="flex justify-between gap-3"><span className="text-slate-500">Revision</span><span className="text-slate-200">{revision ?? '—'}</span></div>
                <div className="flex justify-between gap-3"><span className="text-slate-500">Sources</span><span className="text-slate-200">{sources.length}</span></div>
                <div className="flex justify-between gap-3"><span className="text-slate-500">Candidates</span><span className="text-slate-200">{candidates.length}</span></div>
                <div className="flex justify-between gap-3"><span className="text-slate-500">Pending proposals</span><span className="text-slate-200">{proposedActions.length}</span></div>
                <div className="flex justify-between gap-3"><span className="text-slate-500">Packages</span><span className="text-slate-200">{packages.length}</span></div>
              </div>
            </section>

            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-white"><ShieldCheck className="h-4 w-4 text-emerald-300" />Physical authority</div>
              <div className="mt-4 space-y-2 text-xs">
                {[
                  ['Fabrication', snapshot?.fabrication_authorized],
                  ['Flashing', snapshot?.firmware_flash_authorized],
                  ['Power-on', snapshot?.power_on_authorized],
                  ['Motion', snapshot?.motion_authorized],
                  ['Operation', snapshot?.operational_authorized],
                  ['Release', snapshot?.release_authorized],
                ].map(([label, value]) => (
                  <div key={String(label)} className="flex items-center justify-between rounded-xl border border-white/8 bg-[#030812] px-3 py-2.5">
                    <span className="text-slate-400">{String(label)}</span>
                    <span className={value === true ? 'text-amber-200' : 'text-emerald-200'}>{closedGate(value)}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex items-start gap-2 rounded-xl border border-amber-300/15 bg-amber-300/5 p-3 text-[11px] leading-5 text-amber-100/80">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                AI proposals, software previews, conversation, and package export do not open physical gates.
              </div>
            </section>

            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-white"><MessageSquareText className="h-4 w-4 text-amber-300" />Open blockers</div>
              <div className="mt-4 space-y-2">
                {blockers.length ? blockers.slice(0, 10).map((blocker) => (
                  <div key={blocker} className="rounded-xl border border-amber-300/15 bg-amber-300/5 p-3 text-xs leading-5 text-amber-100/80">{blocker}</div>
                )) : (
                  <div className="rounded-xl border border-dashed border-white/10 p-5 text-center text-xs text-slate-500">No blocker has been recorded yet. That does not imply readiness.</div>
                )}
              </div>
            </section>

            <section className="rounded-3xl border border-white/10 bg-[#07111f] p-5">
              <button type="button" onClick={() => setAdvancedOpen((open) => !open)} className="flex w-full items-center justify-between gap-3 text-left">
                <div className="flex items-center gap-2 text-sm font-semibold text-white"><History className="h-4 w-4 text-slate-400" />Advanced details</div>
                <span className="text-xs text-slate-500">{advancedOpen ? 'Hide' : 'Show'}</span>
              </button>
              {advancedOpen ? (
                <div className="mt-4 space-y-3 break-all font-mono text-[10px] leading-5 text-slate-500">
                  <div>project_id: {projectId || '—'}</div>
                  <div>session_id: {sessionId || '—'}</div>
                  <div>session_kind: {text(session?.session_kind, '—')}</div>
                  <div>context_sha256: {text(session?.context_sha256, '—')}</div>
                  <div className="flex flex-col gap-2 pt-2 font-sans text-xs">
                    <Link href="/engineering/ai-studio" className="text-cyan-200 hover:text-white">Open technical AI Studio</Link>
                    <Link href="/engineering/jarvis" className="text-cyan-200 hover:text-white">Open dedicated JARVIS console</Link>
                    <Link href="/engineering/uploads" className="text-cyan-200 hover:text-white">Open multipart upload workspace</Link>
                  </div>
                </div>
              ) : null}
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
