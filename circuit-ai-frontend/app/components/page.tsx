'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { BookOpen, CircuitBoard, Cpu, Sparkles, Wrench } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CopilotDock } from '@/components/copilot-dock';
import { StudioCommandBar } from '@/components/studio-command-bar';
import { StudioShell } from '@/components/studio-shell';
import { useStudioRuntime } from '@/components/studio-runtime';
import { usePageTitle } from '@/components/use-page-title';
import { WorkbenchCanvas, type WorkbenchCanvasNode } from '@/components/workbench-canvas';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload, type ProxyErrorPayload } from '@/lib/proxy-client';
import { referenceComponentTypes, referenceEducationalContent, referenceRepairGuides } from '@/lib/reference-data';

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

const atlasPositions = [
  { x: '16%', y: '18%' },
  { x: '72%', y: '18%' },
  { x: '16%', y: '66%' },
  { x: '70%', y: '68%' },
  { x: '44%', y: '12%' },
  { x: '42%', y: '74%' },
];

const atlasTones = ['cyan', 'amber', 'emerald', 'slate', 'cyan', 'amber'] as const;

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
  const backendTarget = process.env.NEXT_PUBLIC_API_URL || 'the configured proxy backend';
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
          fetch('/api/proxy/components', { cache: 'no-store' }),
          fetch('/api/proxy/educational', { cache: 'no-store' }),
          fetch('/api/proxy/repair', { cache: 'no-store' }),
        ]);

        const [componentsJson, educationJson, repairJson] = await Promise.all([
          readJsonPayload<ComponentResponse | ProxyErrorPayload>(componentsRes),
          readJsonPayload<EducationalResponse | ProxyErrorPayload>(educationRes),
          readJsonPayload<RepairResponse | ProxyErrorPayload>(repairRes),
        ]);

        if (!active) return;
        const componentsUnavailable = isProxyFailure(componentsJson);
        const educationUnavailable = isProxyFailure(educationJson);
        const repairUnavailable = isProxyFailure(repairJson);

        setComponentData(componentsUnavailable ? null : componentsJson as ComponentResponse | null);
        setEducationData(educationUnavailable ? null : educationJson as EducationalResponse | null);
        setRepairData(repairUnavailable ? null : repairJson as RepairResponse | null);

        const failedResponses = [componentsUnavailable, educationUnavailable, repairUnavailable].filter(Boolean).length;
        if (failedResponses > 0) {
          const detail = [
            getProxyErrorMessage(componentsUnavailable ? componentsJson : null, ''),
            getProxyErrorMessage(educationUnavailable ? educationJson : null, ''),
            getProxyErrorMessage(repairUnavailable ? repairJson : null, ''),
          ].find(Boolean);

          setErrorMessage(
            detail || (
              failedResponses === 3
                ? `Live component intelligence is unavailable at ${backendTarget}. Local reference dataset is active and clearly labeled.`
                : `Some component feeds are unavailable at ${backendTarget}. Live data is mixed with the local reference dataset where needed.`
            ),
          );
        }
      } catch {
        if (!active) return;
        setErrorMessage(`Live component intelligence is unavailable at ${backendTarget}. Local reference dataset is active and clearly labeled.`);
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [backendTarget]);

  const componentTypes = useMemo(
    () => componentData?.component_types?.length ? componentData.component_types : referenceComponentTypes,
    [componentData],
  );
  const educationalItems = useMemo(() => educationData?.content?.length ? educationData.content : referenceEducationalContent, [educationData]);
  const repairGuides = useMemo(() => repairData?.guides?.length ? repairData.guides : referenceRepairGuides, [repairData]);
  const feedMode = componentData ? 'Live API' : 'Local reference dataset';
  const activeType = componentTypes.includes(selectedType || '') ? selectedType || componentTypes[0] : componentTypes[0];
  const relatedEducation = useMemo(
    () => educationalItems.filter((item) => !activeType || item.component_type === activeType),
    [activeType, educationalItems],
  );
  const relatedRepair = useMemo(
    () => repairGuides.filter((guide) => !activeType || guide.component_type === activeType),
    [activeType, repairGuides],
  );
  const stageNodes = useMemo<WorkbenchCanvasNode[]>(
    () => componentTypes.slice(0, atlasPositions.length).map((type, index) => ({
      id: type,
      title: type.replaceAll('_', ' '),
      description: [
        `${educationalItems.filter((item) => item.component_type === type).length} education items`,
        `${repairGuides.filter((guide) => guide.component_type === type).length} repair guides`,
        type === activeType ? 'currently selected' : 'click to focus',
      ].join(' • '),
      badge: type === activeType ? 'focus' : feedMode === 'Live API' ? 'live' : 'reference',
      x: atlasPositions[index]?.x || '50%',
      y: atlasPositions[index]?.y || '50%',
      tone: atlasTones[index % atlasTones.length],
      active: type === activeType,
      onClick: () => setSelectedType(type),
    })),
    [activeType, componentTypes, educationalItems, feedMode, repairGuides],
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
      commandBar={(
        <StudioCommandBar
          modeLabel="Components"
          objective="Turn raw part families into usable hardware knowledge, repair guidance, and reusable modules without leaving the shared stage."
          context={`Current focus: ${activeType.replaceAll('_', ' ')} • ${feedMode}.`}
          status={loading ? 'syncing' : 'atlas primed'}
          badges={['atlas-first', 'repair-aware', 'education-linked']}
        />
      )}
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
              Source: <span className="text-white">{feedMode}</span>. Live routes are <span className="text-white">/components</span>, <span className="text-white">/educational</span>, and <span className="text-white">/repair</span>.
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
        <WorkbenchCanvas
          toolbar={['Atlas', 'Clusters', 'Overlays']}
          activeToolbar="Atlas"
          toolbarStatus={loading ? 'Syncing' : 'Atlas ready'}
          stageLabel="Component atlas"
          stageTitle="Read parts as a spatial knowledge field."
          stageSummary={`${feedMode}: each visible node is backed by loaded component, education, and repair records rather than decorative placeholders.`}
          badge={activeType.replaceAll('_', ' ')}
          metrics={[
            { label: 'Tracked types', value: String(componentData?.total_components || componentTypes.length), tone: 'cyan' },
            { label: 'Education', value: String(educationData?.total_content || educationalItems.length || 0), tone: 'amber' },
            { label: 'Repair', value: String(repairData?.total_guides || repairGuides.length || 0), tone: 'emerald' },
            { label: 'Source', value: feedMode, tone: 'slate' },
          ]}
          notes={[
            'The node map is data-driven: click a family to filter the education and repair trays.',
            feedMode === 'Live API' ? 'Live API records are active.' : 'Reference data is local and labeled because the backend feed is not reachable.',
          ]}
          actions={[
            { href: '/analyze', label: 'Return to analyze' },
            { href: '/projects', label: 'Project board' },
          ]}
          nodes={stageNodes}
        >
          <div className="w-full max-w-2xl rounded-[1.4rem] border border-white/12 bg-[linear-gradient(180deg,rgba(10,20,35,0.92),rgba(7,17,30,0.96))] p-6 shadow-[0_28px_70px_rgba(2,6,23,0.44)]">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-[1.4rem] border border-cyan-300/18 bg-cyan-300/10 text-cyan-100">
                  <Cpu className="h-7 w-7" />
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Focused node</div>
                  <div className="mt-2 text-2xl font-semibold text-white">{activeType.replaceAll('_', ' ')}</div>
                  <div className="mt-2 max-w-xl text-sm leading-6 text-slate-300">
                    {relatedEducation[0]?.title || relatedRepair[0]?.issue || 'Use the side dock and lower tray to expand this component into repair and project context.'}
                  </div>
                </div>
              </div>
              <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-100">
                active selection
              </div>
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <div className="rounded-[1rem] border border-white/10 bg-[#081423] p-4">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Education hits</div>
                <div className="mt-2 text-xl font-semibold text-white">{relatedEducation.length || educationalItems.length || 0}</div>
              </div>
              <div className="rounded-[1rem] border border-white/10 bg-[#081423] p-4">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Repair paths</div>
                <div className="mt-2 text-xl font-semibold text-white">{relatedRepair.length || repairGuides.length || 0}</div>
              </div>
              <div className="rounded-[1rem] border border-white/10 bg-[#081423] p-4">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">State</div>
                <div className="mt-2 text-xl font-semibold text-white">{loading ? 'Syncing' : 'Ready'}</div>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              {(relatedEducation.length ? relatedEducation : educationalItems.slice(0, 2)).slice(0, 3).map((item, index) => (
                <div key={`${item.title || 'education-chip'}-${index}`} className="rounded-full border border-white/10 bg-[#081423] px-3 py-2 text-xs text-slate-300">
                  {item.title || `${activeType.replaceAll('_', ' ')} reference`}
                </div>
              ))}
            </div>
          </div>
        </WorkbenchCanvas>
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
                    No educational items are loaded for the current focus.
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
                    No repair guides are loaded for the current focus.
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
          objective="Use the assistant context to explain the focused node, decide whether it is reusable or repairable, and move the board toward a coherent parts understanding."
          status={loading ? 'Syncing' : activeType.replaceAll('_', ' ')}
          messages={[
            {
              role: 'agent',
                  body: `The atlas is focused on ${activeType.replaceAll('_', ' ')} from the ${feedMode.toLowerCase()}. Use this panel to interpret the selected family and decide whether it should feed repair, reuse, or project planning.`,
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
                  body: `The deeper educational and repair material stays in the lower tray. The current source is ${feedMode}.`,
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
              Source: {feedMode}. Indexed types: {componentData?.total_components || componentTypes.length}. Education overlays: {educationData?.total_content || educationalItems.length || 0}. Repair paths: {repairData?.total_guides || repairGuides.length || 0}.
            </div>
          }
        />
      }
    />
  );
}
