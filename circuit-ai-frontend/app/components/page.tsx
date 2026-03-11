'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { BookOpen, CircuitBoard, Cpu, LoaderCircle, RefreshCcw, ShieldCheck, Sparkles, Wrench } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CopilotDock } from '@/components/copilot-dock';
import { StudioShell } from '@/components/studio-shell';
import { useStudioRuntime } from '@/components/studio-runtime';
import { usePageTitle } from '@/components/use-page-title';

type ComponentResponse = {
  total_components?: number;
  component_types?: string[];
};

type EducationalResponse = {
  total_content?: number;
  content?: Array<{
    title?: string;
    difficulty?: string;
    component_type?: string;
    estimated_time?: string;
  }>;
};

type RepairResponse = {
  total_guides?: number;
  guides?: Array<{
    component_type?: string;
    issue?: string;
    difficulty?: string;
    success_rate?: number;
  }>;
};

const navItems = [
  { href: '/', label: 'Overview' },
  { href: '/analyze', label: 'Analyze' },
  { href: '/components', label: 'Components' },
  { href: '/projects', label: 'Projects' },
  { href: '/cad', label: 'CAD' },
];

const fallbackTypes = ['ic_chip', 'capacitor', 'resistor', 'connector', 'transformer', 'diode'];

function panelHeading(eyebrow: string, title: string) {
  return (
    <div className="mb-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">{eyebrow}</div>
      <div className="mt-2 text-sm font-semibold text-white">{title}</div>
    </div>
  );
}

export default function ComponentsPage() {
  usePageTitle('Component Intelligence | Circuit.AI');
  const { setFocusedComponent } = useStudioRuntime();
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const [componentData, setComponentData] = useState<ComponentResponse | null>(null);
  const [educationData, setEducationData] = useState<EducationalResponse | null>(null);
  const [repairData, setRepairData] = useState<RepairResponse | null>(null);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setErrorMessage(null);

      try {
        const [componentsRes, educationRes, repairRes] = await Promise.all([
          fetch(`${apiBaseUrl}/components`, { cache: 'no-store' }),
          fetch(`${apiBaseUrl}/educational`, { cache: 'no-store' }),
          fetch(`${apiBaseUrl}/repair`, { cache: 'no-store' }),
        ]);

        const [componentsJson, educationJson, repairJson] = await Promise.all([
          componentsRes.ok ? componentsRes.json() : Promise.resolve({}),
          educationRes.ok ? educationRes.json() : Promise.resolve({}),
          repairRes.ok ? repairRes.json() : Promise.resolve({}),
        ]);

        if (!active) return;
        setComponentData(componentsJson);
        setEducationData(educationJson);
        setRepairData(repairJson);

        if (!componentsRes.ok && !educationRes.ok && !repairRes.ok) {
          setErrorMessage(`Live component intelligence is unavailable at ${apiBaseUrl}. Fallback summary loaded.`);
        }
      } catch (error) {
        if (!active) return;
        console.error('Failed to load component intelligence', error);
        setErrorMessage(`Live component intelligence is unavailable at ${apiBaseUrl}. Fallback summary loaded.`);
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [apiBaseUrl]);

  const componentTypes = useMemo(
    () => componentData?.component_types?.length ? componentData.component_types : fallbackTypes,
    [componentData],
  );
  const educationalItems = educationData?.content || [];
  const repairGuides = repairData?.guides || [];
  const activeType = componentTypes.includes(selectedType || '') ? selectedType || componentTypes[0] : componentTypes[0];
  const relatedEducation = useMemo(
    () => educationalItems.filter((item) => !activeType || item.component_type === activeType),
    [activeType, educationalItems],
  );
  const relatedRepair = useMemo(
    () => repairGuides.filter((guide) => !activeType || guide.component_type === activeType),
    [activeType, repairGuides],
  );

  useEffect(() => {
    setFocusedComponent(activeType || null);
  }, [activeType, setFocusedComponent]);

  return (
    <StudioShell
      eyebrow="Workbench"
      title="Browse component intelligence inside a component atlas."
      description="The center behaves like a selectable parts field, with focused context pushed into the side inspector and the lower tray."
      status={loading ? 'Refreshing part intelligence' : `${componentData?.total_components || componentTypes.length} component types indexed`}
      activeHref="/components"
      navItems={navItems}
      actions={
        <>
          <Button asChild className="rounded-full bg-white text-slate-950 hover:bg-slate-100">
            <Link href="/analyze">
              <CircuitBoard className="mr-2 h-4 w-4" />
              Back to analyze
            </Link>
          </Button>
          <Button asChild variant="outline" className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10">
            <Link href="/projects">
              <Sparkles className="mr-2 h-4 w-4" />
              Project planning
            </Link>
          </Button>
        </>
      }
      left={
        <div className="space-y-5">
          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            {panelHeading('Source', 'Workspace feed')}
            <div className="text-sm leading-6 text-slate-400">
              Pulls from <span className="text-white">/components</span>, <span className="text-white">/educational</span>, and <span className="text-white">/repair</span> when available.
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            {panelHeading('Counts', 'Reference stats')}
            <div className="grid gap-3">
              {[
                ['Tracked types', loading ? '...' : String(componentData?.total_components || componentTypes.length)],
                ['Educational overlays', String(educationData?.total_content || educationalItems.length || 0)],
                ['Repair guides', String(repairData?.total_guides || repairGuides.length || 0)],
              ].map(([label, value]) => (
                <div key={label} className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
                  <div className="mt-2 text-lg font-semibold text-white">{value}</div>
                </div>
              ))}
            </div>
          </div>

          {errorMessage ? (
            <div className="rounded-[1.5rem] border border-amber-400/20 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
              {errorMessage}
            </div>
          ) : null}
        </div>
      }
      main={
        <div className="grid h-full grid-rows-[44px_minmax(0,1fr)] bg-white/5">
          <div className="flex items-center justify-between border-b border-white/8 bg-[#08111e] px-4">
            <div className="flex items-center gap-2">
              {['Atlas', 'Clusters', 'Overlays'].map((item, index) => (
                <button
                  key={item}
                  type="button"
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium ${index === 0 ? 'bg-cyan-300/15 text-cyan-100' : 'text-slate-400 hover:bg-white/6 hover:text-white'}`}
                >
                  {item}
                </button>
              ))}
            </div>
            <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
              {loading ? 'Syncing' : 'Atlas ready'}
            </div>
          </div>

          <div className="relative min-h-0 overflow-hidden bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.11),transparent_24%),linear-gradient(180deg,#0b1323_0%,#0b1627_100%)] p-3">
            <div className="pointer-events-none absolute right-6 top-16 z-10 hidden rounded-[1rem] border border-white/10 bg-[#081423]/88 px-3 py-2 text-xs font-medium text-slate-300 backdrop-blur xl:block">
              atlas scan active
            </div>

            <div className="pointer-events-none absolute bottom-4 right-4 z-10 hidden max-w-sm rounded-[1rem] border border-white/10 bg-[#081423]/88 p-3 text-sm leading-6 text-slate-300 backdrop-blur xl:block">
              Focus one node at a time. The side dock holds the active summary and the lower tray holds deeper education and repair material.
            </div>

            <div className="grid h-full grid-rows-[76px_minmax(0,1fr)] overflow-hidden rounded-[1.25rem] border border-white/10 bg-[#09111d]">
              <div className="flex items-center justify-between border-b border-white/10 px-4">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Atlas field</div>
                  <div className="mt-1 text-sm font-semibold text-white">Selectable component nodes</div>
                </div>
                <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs text-cyan-100">
                  {activeType.replaceAll('_', ' ')}
                </div>
              </div>

              <div className="min-h-0 overflow-y-auto p-5">
                <div className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
                  {componentTypes.map((type, index) => {
                    const active = type === activeType;
                    return (
                      <button
                        key={type}
                        type="button"
                        onClick={() => setSelectedType(type)}
                        className={`group rounded-[1.35rem] border p-5 text-left transition-all ${
                          active
                            ? 'border-cyan-300/35 bg-[linear-gradient(180deg,#132344,#0d1a31)] shadow-[0_24px_44px_rgba(8,145,178,0.16)]'
                            : 'border-white/10 bg-[linear-gradient(180deg,#0f1b35,#091423)] hover:-translate-y-0.5 hover:border-white/18 hover:bg-[linear-gradient(180deg,#122244,#0b1730)]'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-3">
                            <div className={`flex h-12 w-12 items-center justify-center rounded-2xl border ${active ? 'border-cyan-300/30 bg-cyan-400/12 text-cyan-100' : 'border-white/10 bg-white/[0.04] text-cyan-200'}`}>
                              <Cpu className="h-5 w-5" />
                            </div>
                            <div>
                              <div className="text-base font-semibold text-white">{type.replaceAll('_', ' ')}</div>
                              <div className="mt-1 text-[11px] uppercase tracking-[0.22em] text-slate-500">node {index + 1}</div>
                            </div>
                          </div>
                          <div className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${active ? 'bg-cyan-300/14 text-cyan-100' : 'bg-[#081423] text-slate-400'}`}>
                            {active ? 'focused' : 'ready'}
                          </div>
                        </div>

                        <div className="mt-5 grid gap-2 sm:grid-cols-3">
                          {['Overlay', 'Reference', 'Repair'].map((label) => (
                            <div key={label} className="rounded-xl border border-white/8 bg-[#081423] px-3 py-2 text-xs font-medium text-slate-300">
                              {label}
                            </div>
                          ))}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      }
      bottom={
        <div className="grid h-full grid-rows-[40px_minmax(0,1fr)]">
          <div className="flex items-center gap-2 border-b border-white/8 bg-[#08111d] px-4">
            {['Education', 'Repair', 'Reference'].map((item, index) => (
              <button
                key={item}
                type="button"
                className={`rounded-lg px-3 py-1.5 text-xs font-medium ${index === 0 ? 'bg-cyan-300/15 text-cyan-100' : 'text-slate-400 hover:bg-white/6 hover:text-white'}`}
              >
                {item}
              </button>
            ))}
          </div>

          <div className="grid min-h-0 gap-px lg:grid-cols-2">
            <div className="min-h-0 overflow-y-auto bg-[#07101d] p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
                <BookOpen className="h-4 w-4 text-cyan-300" />
                Related education
              </div>
              <div className="grid gap-3">
                {(relatedEducation.length ? relatedEducation : educationalItems.slice(0, 4)).slice(0, 4).map((item, index) => (
                  <div key={`${item.title || 'education'}-${index}`} className="rounded-[1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-3">
                    <div className="text-sm font-semibold text-white">{item.title || 'Untitled content'}</div>
                    <div className="mt-2 text-sm leading-6 text-slate-400">
                      {item.component_type ? item.component_type.replaceAll('_', ' ') : activeType.replaceAll('_', ' ')}
                      {item.estimated_time ? ` • ${item.estimated_time}` : ''}
                    </div>
                  </div>
                ))}
                {!educationalItems.length ? (
                  <div className="rounded-[1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-3 text-sm leading-6 text-slate-400">
                    No educational items are loaded for the current session.
                  </div>
                ) : null}
              </div>
            </div>

            <div className="min-h-0 overflow-y-auto bg-[#07101d] p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
                <Wrench className="h-4 w-4 text-cyan-300" />
                Related repair
              </div>
              <div className="grid gap-3">
                {(relatedRepair.length ? relatedRepair : repairGuides.slice(0, 4)).slice(0, 4).map((guide, index) => (
                  <div key={`${guide.component_type || 'repair'}-${guide.issue || index}`} className="rounded-[1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-3">
                    <div className="text-sm font-semibold text-white">
                      {guide.component_type ? guide.component_type.replaceAll('_', ' ') : activeType.replaceAll('_', ' ')}
                    </div>
                    <div className="mt-2 text-sm leading-6 text-slate-400">
                      {guide.issue || 'Repair path unavailable'}
                      {guide.success_rate !== undefined ? ` • ${Math.round(guide.success_rate * 100)}%` : ''}
                    </div>
                  </div>
                ))}
                {!repairGuides.length ? (
                  <div className="rounded-[1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-3 text-sm leading-6 text-slate-400">
                    No repair guides are loaded for the current session.
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      }
      right={
        <CopilotDock
          modeLabel="Components"
          objective="Use the agent to explain the focused node, decide whether it is reusable or repairable, and move the board toward a coherent parts understanding."
          status={loading ? 'Syncing' : activeType.replaceAll('_', ' ')}
          messages={[
            {
              role: 'agent',
              body: `The atlas is focused on ${activeType.replaceAll('_', ' ')}. I can explain what it does, where it belongs, and whether it should feed repair, reuse, or project planning.`,
            },
            {
              role: 'user',
              body: `Tell me whether ${activeType.replaceAll('_', ' ')} is worth salvaging and what the next useful interpretation step should be.`,
            },
            errorMessage
              ? {
                  role: 'system',
                  body: errorMessage,
                }
              : {
                  role: 'agent',
                  body: `The deeper educational and repair material stays in the lower tray. Keep the atlas visual and let me narrate the meaning from here.`,
                },
          ]}
          prompts={[
            `Explain ${activeType.replaceAll('_', ' ')}`,
            'Show repair implications',
            'Suggest reusable modules',
            'Prepare project routes',
          ]}
          links={[
            { href: '/analyze', label: 'Return to analyze' },
            { href: '/projects', label: 'Open project board' },
          ]}
          footer={
            <div className="rounded-[0.95rem] border border-white/10 bg-[#0b1628] p-3 text-sm leading-6 text-slate-300">
              Indexed types: {componentData?.total_components || componentTypes.length}. Education overlays: {educationData?.total_content || educationalItems.length || 0}. Repair paths: {repairData?.total_guides || repairGuides.length || 0}.
            </div>
          }
        />
      }
    />
  );
}
