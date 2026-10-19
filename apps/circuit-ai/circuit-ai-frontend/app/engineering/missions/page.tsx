'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ChevronRight, LoaderCircle, Plus } from 'lucide-react';
import { usePageTitle } from '@/components/use-page-title';
import {
  AcceptPanel,
  AgentHandoff,
  AskedForPanel,
  CandidatesPanel,
  NeedsPanel,
  VerdictPanel,
  SafetyPanel,
  WhoChip,
} from '@/components/engineering/mission-detail';
import { DeliveryPanel } from '@/components/engineering/mission-delivery';
import { DonorsPanel } from '@/components/engineering/mission-donors';
import { MissionStart } from '@/components/engineering/mission-start';
import { TimelinePanel } from '@/components/engineering/mission-timeline';
import { fetchMission, fetchMissions, fetchProjects, TONE, verdictOf, type Mission } from '@/lib/missions';

const PROJECT_KEY = 'hs-missions-project';
const POLL_MS = 5000;

function when(iso: string) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function readPreset(): { project: string; mission: string } {
  try {
    const query = new URLSearchParams(window.location.search);
    return { project: query.get('project') || window.localStorage.getItem(PROJECT_KEY) || '', mission: query.get('mission') || '' };
  } catch {
    return { project: '', mission: '' };
  }
}

export default function MissionsPage() {
  usePageTitle('Fabrication missions');
  const [projects, setProjects] = useState<{ project_id: string; name: string }[]>([]);
  const [project, setProject] = useState('');
  const [missions, setMissions] = useState<Mission[]>([]);
  const [selected, setSelected] = useState('');
  const [detail, setDetail] = useState<Mission | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [listOpen, setListOpen] = useState(false);
  const [creating, setCreating] = useState(false);

  // First paint: which project, which mission. The URL wins over what this browser remembers.
  useEffect(() => {
    const preset = readPreset();
    setSelected(preset.mission);
    fetchProjects()
      .then((rows) => {
        setProjects(rows);
        setProject(preset.project && rows.some((row) => row.project_id === preset.project) ? preset.project : rows[0]?.project_id || '');
      })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Could not load projects'));
  }, []);

  const refreshList = useCallback(async () => {
    if (!project) return;
    try {
      setMissions(await fetchMissions(project));
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load missions');
    }
  }, [project]);

  useEffect(() => {
    if (!project) return;
    try { window.localStorage.setItem(PROJECT_KEY, project); } catch { /* the choice just is not remembered */ }
    setLoading(true);
    refreshList().finally(() => setLoading(false));
    const timer = window.setInterval(refreshList, POLL_MS);
    return () => window.clearInterval(timer);
  }, [project, refreshList]);

  // Choose the newest mission when none is chosen yet.
  useEffect(() => {
    if (!selected && missions.length) setSelected(missions[0].mission_id);
  }, [missions, selected]);

  const listed = useMemo(() => missions.find((row) => row.mission_id === selected) || null, [missions, selected]);

  const loadDetail = useCallback(async () => {
    if (!project || !selected) return;
    try {
      setDetail(await fetchMission(project, selected));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load the mission');
    }
  }, [project, selected]);

  useEffect(() => {
    setDetail(null);
    loadDetail();
  }, [loadDetail]);

  // The agent works in the background; reload the open mission when the list shows it moved.
  useEffect(() => {
    if (listed && detail && listed.last_event_seq !== detail.last_event_seq) loadDetail();
  }, [listed, detail, loadDetail]);

  function choose(id: string) {
    setSelected(id);
    setListOpen(false);
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('project', project);
      url.searchParams.set('mission', id);
      window.history.replaceState(null, '', url);
    } catch { /* the address bar just does not follow */ }
  }

  function opened(mission: Mission) {
    setCreating(false);
    setMissions((rows) => [mission, ...rows.filter((row) => row.mission_id !== mission.mission_id)]);
    choose(mission.mission_id);
  }

  function updated(mission: Mission) {
    setMissions((rows) => rows.map((row) => (row.mission_id === mission.mission_id ? mission : row)));
    loadDetail();
  }

  return (
    <main className="hs-reset mx-auto grid min-h-[calc(100vh-3.5rem)] max-w-[1400px] gap-6 px-4 pb-24 pt-8 lg:grid-cols-[22rem_minmax(0,1fr)] lg:px-8">
      <aside aria-label="Missions" className="lg:sticky lg:top-20 lg:self-start">
        <h1 className="text-xl font-semibold text-white">Fabrication missions</h1>
        <p className="mt-1 text-sm leading-6 text-slate-400">
          You say what you want and what you have. An agent proposes designs. Hardware Splicer (HS) checks them. You decide.
        </p>
        <div className="mt-4 flex flex-wrap gap-2 text-[11px]">
          <WhoChip who="human" label="You decide" /> <WhoChip who="agent" label="Agent proposes" /> <WhoChip who="system" label="HS checks" />
        </div>

        <button
          type="button"
          onClick={() => { setCreating(true); setListOpen(false); }}
          disabled={!project}
          data-testid="new-mission"
          className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-full bg-amber-300 px-5 py-2.5 text-sm font-semibold text-stone-900 transition hover:bg-amber-200 disabled:opacity-40"
        >
          <Plus className="h-4 w-4" /> New mission
        </button>

        <label className="mt-4 block text-xs text-slate-400">
          Project
          <select
            value={project}
            onChange={(event) => { setProject(event.target.value); setSelected(''); setDetail(null); }}
            className="mt-1 w-full rounded-lg border border-white/15 bg-[#07111f] px-3 py-2 text-sm text-slate-100"
            data-testid="project-select"
          >
            {projects.length === 0 ? <option value="">No projects</option> : null}
            {projects.map((row) => <option key={row.project_id} value={row.project_id}>{row.name} ({row.project_id})</option>)}
          </select>
        </label>

        <button
          type="button"
          onClick={() => setListOpen((open) => !open)}
          aria-expanded={listOpen}
          className="mt-4 flex w-full items-center justify-between rounded-xl border border-white/15 bg-[#07111f] px-4 py-2.5 text-sm font-medium text-slate-100 lg:hidden"
        >
          <span>Switch mission ({missions.length})</span>
          <ChevronRight className={`h-4 w-4 transition ${listOpen ? 'rotate-90' : ''}`} />
        </button>

        <ul className={`mt-4 space-y-2 ${listOpen ? 'block' : 'hidden'} lg:block`} data-testid="mission-list">
          {missions.map((row) => {
            const verdict = verdictOf(row);
            const tone = TONE[verdict.tone];
            const active = !creating && row.mission_id === selected;
            return (
              <li key={row.mission_id}>
                <button
                  type="button"
                  onClick={() => { setCreating(false); choose(row.mission_id); }}
                  aria-current={active ? 'true' : undefined}
                  className={`group w-full rounded-xl border border-l-4 p-3 text-left transition ${tone.bar} ${active ? 'border-white/40 bg-white/[0.07]' : 'border-white/10 bg-[#07111f]/60 hover:border-white/25'}`}
                >
                  <span className={`block text-sm font-semibold leading-snug ${tone.label}`}>{verdict.title}</span>
                  <span className="mt-1 line-clamp-2 block text-xs leading-5 text-slate-300">{row.intake.goal}</span>
                  <span className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                    <span>{when(row.created_at)}</span>
                    <ChevronRight className="h-3.5 w-3.5 opacity-0 transition group-hover:opacity-100" />
                  </span>
                </button>
              </li>
            );
          })}
          {!loading && project && missions.length === 0 && !error ? (
            <li className="rounded-xl border border-dashed border-white/15 p-4 text-sm leading-6 text-slate-400">
              No missions in this project yet. An agent opens one for you from your goal and parts list.
            </li>
          ) : null}
        </ul>
      </aside>

      <section aria-label="Mission detail" className="min-w-0 space-y-4">
        {error ? (
          <p role="alert" className="flex items-start gap-2 rounded-xl border border-red-400/40 bg-red-950/40 px-4 py-3 text-sm text-red-100">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
          </p>
        ) : null}
        {creating && project ? <MissionStart projectId={project} onOpened={opened} onCancel={() => setCreating(false)} /> : null}
        {!creating && !detail && (loading || selected) && !error ? (
          <p className="flex items-center gap-2 text-sm text-slate-400"><LoaderCircle className="h-4 w-4 animate-spin" /> Loading…</p>
        ) : null}
        {detail && !creating ? (
          <>
            <header>
              <h2 data-testid="mission-goal" className="text-2xl font-semibold leading-snug text-white">{detail.intake.goal}</h2>
              <p className="mt-1 text-xs text-slate-500">Mission {detail.mission_id} · opened {when(detail.created_at)}</p>
            </header>
            <SafetyPanel mission={detail} />
            <VerdictPanel mission={detail} />
            <AcceptPanel mission={detail} onAccepted={updated} />
            <AgentHandoff mission={detail} />
            <NeedsPanel mission={detail} onChanged={loadDetail} />
            <DeliveryPanel mission={detail} onChanged={loadDetail} />
            <AskedForPanel mission={detail} />
            <DonorsPanel mission={detail} />
            <CandidatesPanel mission={detail} />
            <TimelinePanel mission={detail} />
          </>
        ) : null}
      </section>
    </main>
  );
}
