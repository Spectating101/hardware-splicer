'use client';

import { type ChangeEvent, useState } from 'react';
import { Activity, Boxes, Crosshair, FileUp, Loader2, PackageSearch, Ruler, ShieldAlert, Target } from 'lucide-react';
import {
  constructorCandidateMap,
  constructorRequirements,
  constructorResources,
  constructorTarget,
  type RequirementState,
} from '@/lib/workbench-constructor-demo';
import { useMachineWorkbenchStore, type MechanicalGeometryEvidence } from '@/lib/machine-workbench-store';
import { useWorkbenchAccessStore } from '@/lib/workbench-access-store';
import { useWorkbenchBrepAnchorStore } from '@/lib/workbench-brep-anchor-store';
import { useWorkbenchPlacementStore } from '@/lib/workbench-placement-store';
import { cacheSessionStepSource, clearSessionStepSource } from '@/lib/workbench-session-step-sources';
import {
  getRegisteredWorkbenchStepSource,
  useWorkbenchProjectSourceStore,
} from '@/lib/workbench-project-sources';
import { importWorkbenchStepSource } from '@/lib/workbench-step-source-import';
import { DeclaredPlacementEditor } from '@/components/workbench/declared-placement-editor';

function requirementTone(state: RequirementState) {
  if (state === 'pass') return 'border-emerald-300/20 bg-emerald-300/[0.055] text-emerald-200';
  if (state === 'partial') return 'border-sky-300/20 bg-sky-300/[0.055] text-sky-200';
  if (state === 'blocked') return 'border-red-300/20 bg-red-300/[0.055] text-red-200';
  return 'border-amber-300/20 bg-amber-300/[0.055] text-amber-200';
}

function decisionTone(decision: string) {
  if (decision === 'reject') return 'text-red-300';
  if (decision === 'hold') return 'text-amber-300';
  if (decision === 'reuse' || decision === 'reuse_pending') return 'text-cyan-300';
  if (decision === 'buy') return 'text-violet-300';
  return 'text-orange-300';
}

function normalizeId(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function tuple3(value: unknown): [number, number, number] | null {
  if (!Array.isArray(value) || value.length !== 3) return null;
  const rows = value.map(Number);
  return rows.every(Number.isFinite) ? rows as [number, number, number] : null;
}

function normalizeMillimeters(value: [number, number, number], units: string) {
  if (units === 'mm') return value;
  if (units === 'm') return value.map((row) => row * 1000) as [number, number, number];
  return null;
}

export function ConstructorDock() {
  const [geometryState, setGeometryState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [geometryMessage, setGeometryMessage] = useState('');
  const tab = useMachineWorkbenchStore((state) => state.constructorDockTab);
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const selectedResourceId = useMachineWorkbenchStore((state) => state.selectedResourceId);
  const plannerSource = useMachineWorkbenchStore((state) => state.plannerSource);
  const plannerMessage = useMachineWorkbenchStore((state) => state.plannerMessage);
  const plannerProjection = useMachineWorkbenchStore((state) => state.plannerProjections[state.activeCandidateId]);
  const setTab = useMachineWorkbenchStore((state) => state.setConstructorDockTab);
  const setSelectedResourceId = useMachineWorkbenchStore((state) => state.setSelectedResourceId);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const setMechanicalGeometryEvidence = useMachineWorkbenchStore((state) => state.setMechanicalGeometryEvidence);
  const clearBrepRenderMeshEvidence = useMachineWorkbenchStore((state) => state.clearBrepRenderMeshEvidence);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);
  const setGeometryReport = useWorkbenchPlacementStore((state) => state.setGeometryReport);
  const clearPlacement = useWorkbenchPlacementStore((state) => state.clearPlacement);
  const clearAccessForEntity = useWorkbenchAccessStore((state) => state.clearAccessForEntity);
  const clearAnchorsForEntity = useWorkbenchBrepAnchorStore((state) => state.clearAnchorsForEntity);
  const projectSourceState = useWorkbenchProjectSourceStore();
  const setProjectRevision = useWorkbenchProjectSourceStore((state) => state.setProjectRevision);
  const setRegisteredSource = useWorkbenchProjectSourceStore((state) => state.setRegisteredSource);
  const clearRegisteredSource = useWorkbenchProjectSourceStore((state) => state.clearRegisteredSource);
  const activeCandidate = constructorCandidateMap.get(activeCandidateId) ?? constructorCandidateMap.get('balanced');
  const livePlanner = plannerSource === 'live' && Boolean(plannerProjection);
  const liveSelected = new Set((plannerProjection?.selectedResourceIds ?? []).map(normalizeId));
  const selectedResource = constructorResources.find((resource) => resource.id === selectedResourceId) ?? null;
  const selectedGeometry = selectedResource?.mappedEntityId
    ? plannerProjection?.mechanicalGeometryByEntity?.[selectedResource.mappedEntityId]
    : undefined;
  const geometryForSelectedResource = selectedGeometry?.resourceId === selectedResource?.id ? selectedGeometry : undefined;
  const registeredSource = selectedResource
    ? getRegisteredWorkbenchStepSource(projectSourceState, activeCandidateId, selectedResource.id)
    : null;
  const projectBound = projectSourceState.status === 'bound'
    && Boolean(projectSourceState.projectId)
    && Number.isInteger(projectSourceState.revision)
    && Number(projectSourceState.revision) >= 1;
  const projectIntent = projectSourceState.status !== 'unbound';

  function inspectResource(resourceId: string, mappedEntityId?: string) {
    setSelectedResourceId(resourceId);
    setGeometryState('idle');
    setGeometryMessage('');
    if (mappedEntityId) {
      setSelectedEntityId(mappedEntityId);
      window.setTimeout(requestFrameSelection, 0);
    }
  }

  async function importStepEnvelope(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !selectedResource?.mappedEntityId) return;

    if (projectIntent && !projectBound) {
      setGeometryState('error');
      setGeometryMessage(`Durable project binding is not ready: ${projectSourceState.message}`);
      return;
    }

    setGeometryState('loading');
    setGeometryMessage(
      projectBound
        ? `Registering ${file.name}, then parsing the stored project blob with Hardware-Splicer…`
        : `Parsing ${file.name} with Hardware-Splicer in this browser session…`,
    );
    try {
      const imported = await importWorkbenchStepSource({
        file,
        candidateId: activeCandidateId,
        resourceId: selectedResource.id,
        entityId: selectedResource.mappedEntityId,
        projectBinding: projectBound
          ? {
              projectId: projectSourceState.projectId as string,
              revision: projectSourceState.revision as number,
            }
          : null,
      });
      const geometry = imported.mechanicalGeometry;
      const models = Array.isArray(geometry.models) ? geometry.models : [];
      const model = record(models[0]);
      const boundingBox = record(model.bounding_box);
      const rawSize = tuple3(boundingBox.size);
      const rawMinimum = tuple3(boundingBox.minimum);
      const rawMaximum = tuple3(boundingBox.maximum);
      const units = String(boundingBox.units || model.units || 'unknown');
      if (!rawSize || !rawMinimum || !rawMaximum) throw new Error('STEP source did not produce a bounded Cartesian-point envelope.');
      const sizeMm = normalizeMillimeters(rawSize, units);
      const minimumMm = normalizeMillimeters(rawMinimum, units);
      const maximumMm = normalizeMillimeters(rawMaximum, units);
      if (!sizeMm || !minimumMm || !maximumMm) throw new Error(`STEP length units are ${units}; explicit millimetre/metre units are required before spatial scaling.`);
      if (sizeMm.some((value) => value <= 0)) throw new Error('STEP envelope has a zero-size axis; HS will not promote it to a 3D resource envelope.');
      if (
        String(model.source_id || '') !== imported.sourceId
        || String(model.model_id || '') !== imported.modelId
        || String(model.content_hash || '') !== imported.contentHash
      ) {
        throw new Error('Mechanical geometry identity disagrees with the imported STEP source transaction.');
      }

      const unresolved = Array.isArray(model.unresolved)
        ? model.unresolved.map((row) => {
            const item = record(row);
            return { field: typeof item.field === 'string' ? item.field : undefined, reason: typeof item.reason === 'string' ? item.reason : undefined };
          })
        : [];
      const evidence: MechanicalGeometryEvidence = {
        entityId: selectedResource.mappedEntityId,
        resourceId: selectedResource.id,
        sourceId: imported.sourceId,
        modelId: imported.modelId,
        contentHash: imported.contentHash,
        authority: 'declared',
        units: 'mm',
        sizeMm,
        minimumMm,
        maximumMm,
        pointCount: Number(boundingBox.point_count || model.cartesian_point_count || 0),
        unresolved,
        stepPointEnvelopeOnly: true,
        fullBrepCollision: false,
        fabricationAuthorized: false,
      };

      const priorGeometry = geometryForSelectedResource;
      const sourceIdentityChanged = Boolean(
        priorGeometry
        && (
          priorGeometry.contentHash !== evidence.contentHash
          || priorGeometry.sourceId !== evidence.sourceId
          || priorGeometry.modelId !== evidence.modelId
        ),
      );
      if (sourceIdentityChanged) {
        clearAccessForEntity(activeCandidateId, selectedResource.mappedEntityId);
        clearAnchorsForEntity(activeCandidateId, selectedResource.mappedEntityId);
        clearBrepRenderMeshEvidence(activeCandidateId, selectedResource.mappedEntityId);
        clearPlacement(activeCandidateId, selectedResource.mappedEntityId);
      }

      if (imported.durable) {
        clearSessionStepSource(activeCandidateId, selectedResource.id);
        if (imported.revision === null) throw new Error('Registered STEP import completed without a durable project revision.');
        setProjectRevision(imported.projectId, imported.revision);
        setRegisteredSource({
          candidateId: activeCandidateId,
          resourceId: selectedResource.id,
          entityId: selectedResource.mappedEntityId,
          projectId: imported.projectId,
          sourceId: imported.sourceId,
          modelId: imported.modelId,
          contentHash: imported.contentHash,
          revision: imported.revision,
          sourceMaterialization: 'registered_project',
        });
      } else {
        clearRegisteredSource(activeCandidateId, selectedResource.id);
        if (imported.content === null) throw new Error('Session STEP import lost its bounded raw source cache.');
        cacheSessionStepSource({
          candidateId: activeCandidateId,
          resourceId: selectedResource.id,
          entityId: selectedResource.mappedEntityId,
          sourceId: evidence.sourceId,
          modelId: evidence.modelId,
          contentHash: evidence.contentHash,
          content: imported.content,
        });
      }

      setGeometryReport(activeCandidateId, selectedResource.id, geometry);
      setMechanicalGeometryEvidence(activeCandidateId, evidence);
      setSelectedEntityId(selectedResource.mappedEntityId);
      window.setTimeout(requestFrameSelection, 0);
      setGeometryState('success');
      setGeometryMessage(
        `${sizeMm.map((value) => Math.round(value * 100) / 100).join(' × ')} mm · ${evidence.pointCount} STEP points · DECLARED envelope · ${imported.durable ? `registered project source at revision ${imported.revision}` : 'session-inline source'}.${sourceIdentityChanged ? ' Prior placement and dependent exact evidence were invalidated; re-place this source.' : ''}`,
      );
    } catch (error: unknown) {
      setGeometryState('error');
      setGeometryMessage(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <aside className="flex h-full min-h-0 flex-col border-r border-white/10 bg-[#07101d]">
      <div className="border-b border-white/10 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-300">Constructor</div>
          <span title={plannerMessage} className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-[0.1em] ${livePlanner ? 'border-emerald-300/20 bg-emerald-300/8 text-emerald-200' : plannerSource === 'loading' ? 'border-sky-300/20 bg-sky-300/8 text-sky-200' : 'border-amber-300/15 bg-amber-300/[0.05] text-amber-200/75'}`}>
            <Activity className="h-2.5 w-2.5" /> {livePlanner ? 'live planner' : plannerSource}
          </span>
        </div>
        <div className={`mt-2 rounded-md border px-2 py-1.5 text-[8px] leading-4 ${projectSourceState.status === 'bound' ? 'border-emerald-300/15 bg-emerald-300/[0.035] text-emerald-200/70' : projectSourceState.status === 'error' ? 'border-red-300/15 bg-red-300/[0.035] text-red-200/70' : projectSourceState.status === 'loading' ? 'border-sky-300/15 bg-sky-300/[0.035] text-sky-200/70' : 'border-white/8 bg-white/[0.02] text-slate-600'}`} data-testid="workbench-project-provenance">
          {projectSourceState.message}
        </div>
        <div className="mt-2 flex rounded-lg border border-white/10 bg-black/20 p-0.5">
          <button type="button" onClick={() => setTab('target')} className={`flex flex-1 items-center justify-center gap-2 rounded-md px-2 py-2 text-[10px] font-medium ${tab === 'target' ? 'bg-cyan-300/10 text-cyan-100' : 'text-slate-500 hover:text-white'}`}>
            <Target className="h-3.5 w-3.5" /> Target
          </button>
          <button type="button" onClick={() => setTab('resources')} className={`flex flex-1 items-center justify-center gap-2 rounded-md px-2 py-2 text-[10px] font-medium ${tab === 'resources' ? 'bg-cyan-300/10 text-cyan-100' : 'text-slate-500 hover:text-white'}`}>
            <Boxes className="h-3.5 w-3.5" /> Resources
          </button>
        </div>
      </div>

      {tab === 'target' ? (
        <div className="min-h-0 flex-1 overflow-auto p-3">
          <div className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.035] p-3">
            <div className="flex items-start gap-2">
              <Target className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" />
              <div>
                <div className="text-xs font-semibold text-white">{constructorTarget.title}</div>
                <p className="mt-1 text-[10px] leading-4 text-slate-400">{constructorTarget.prompt}</p>
              </div>
            </div>
          </div>

          {livePlanner ? (
            <div className="mt-3 rounded-lg border border-emerald-300/15 bg-emerald-300/[0.035] p-2.5">
              <div className="flex items-center justify-between gap-3 text-[9px] font-semibold uppercase tracking-[0.13em] text-emerald-200/80">
                <span>resource_strategy.v1</span>
                <span>{Math.round((plannerProjection?.coverageScore ?? 0) * 100)}% capability coverage</span>
              </div>
              <div className="mt-1 text-[10px] leading-4 text-slate-400">{plannerProjection?.readinessReason}</div>
              {(plannerProjection?.missingCapabilities.length ?? 0) > 0 ? <div className="mt-1 text-[9px] text-amber-300/75">Missing: {plannerProjection?.missingCapabilities.join(', ')}</div> : null}
            </div>
          ) : (
            <div className="mt-3 rounded-lg border border-amber-300/10 bg-amber-300/[0.025] px-2.5 py-2 text-[9px] leading-4 text-amber-100/55">{plannerMessage}</div>
          )}

          <div className="mt-4 flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Target contract projection</span>
            <span className="text-[10px] text-slate-600">{activeCandidate?.name}</span>
          </div>
          <div className="mt-2 space-y-1.5">
            {constructorRequirements.map((requirement) => {
              const state = activeCandidate?.requirementStates[requirement.id] ?? 'unknown';
              return (
                <div key={requirement.id} className="rounded-lg border border-white/8 bg-white/[0.02] px-2.5 py-2">
                  <div className="flex items-center gap-2">
                    <span className={`rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] ${requirementTone(state)}`}>{state}</span>
                    <span className="min-w-0 flex-1 truncate text-[10px] font-medium text-slate-200">{requirement.label}</span>
                    {requirement.hard ? <ShieldAlert className="h-3 w-3 shrink-0 text-slate-600" /> : null}
                  </div>
                  <div className="mt-1 pl-[52px] text-[10px] text-slate-600">{requirement.target}</div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto p-3">
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-white/8 bg-white/[0.02] px-2.5 py-2 text-[10px] leading-4 text-slate-500">
            <PackageSearch className="h-3.5 w-3.5 shrink-0" /> {livePlanner ? 'Candidate membership below is selected by the live resource planner.' : 'Owned, salvaged, procurable and designed parts share one resource pool.'}
          </div>

          {selectedResource?.mappedEntityId ? (
            <div className="mb-3 rounded-lg border border-cyan-300/12 bg-cyan-300/[0.025] p-2.5" data-testid="step-geometry-import">
              <div className="flex items-start gap-2">
                <Ruler className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cyan-300" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-[10px] font-semibold text-slate-200">Spatial evidence · {selectedResource.name}</div>
                    <span className={`rounded border px-1.5 py-0.5 text-[7px] font-semibold uppercase tracking-[0.1em] ${registeredSource ? 'border-emerald-300/20 bg-emerald-300/[0.05] text-emerald-200' : 'border-white/8 bg-white/[0.02] text-slate-600'}`}>
                      {registeredSource ? 'registered source' : 'session source'}
                    </span>
                  </div>
                  {geometryForSelectedResource ? (
                    <div className="mt-1 text-[9px] leading-4 text-emerald-200/75">
                      STEP envelope attached: {geometryForSelectedResource.sizeMm.join(' × ')} mm · {geometryForSelectedResource.pointCount} points · DECLARED
                    </div>
                  ) : (
                    <div className="mt-1 text-[9px] leading-4 text-slate-500">Attach a text STEP/STP model. HS will use only its parsed point envelope. When a project is bound, the source is registered and reparsed from the server-side content-addressed blob before it becomes workbench evidence.</div>
                  )}
                  <div className="mt-2 flex items-center gap-2">
                    <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-cyan-300/15 bg-cyan-300/[0.04] px-2 py-1.5 text-[9px] font-semibold uppercase tracking-[0.1em] text-cyan-200 hover:bg-cyan-300/[0.08]">
                      {geometryState === 'loading' ? <Loader2 className="h-3 w-3 animate-spin" /> : <FileUp className="h-3 w-3" />}
                      {geometryForSelectedResource ? 'Replace STEP' : 'Attach STEP'}
                      <input type="file" accept=".step,.stp,model/step" className="sr-only" disabled={geometryState === 'loading' || (projectIntent && !projectBound)} onChange={importStepEnvelope} aria-label={`Attach STEP geometry for ${selectedResource.name}`} />
                    </label>
                    <span className="text-[8px] uppercase tracking-[0.1em] text-slate-600">point envelope · no BREP authority</span>
                  </div>
                  {geometryMessage ? <div className={`mt-1.5 text-[9px] leading-4 ${geometryState === 'error' ? 'text-red-300/80' : geometryState === 'success' ? 'text-emerald-300/75' : 'text-slate-500'}`}>{geometryMessage}</div> : null}
                  {geometryForSelectedResource ? (
                    <DeclaredPlacementEditor
                      key={`${activeCandidateId}-${selectedResource.id}-${geometryForSelectedResource.contentHash}`}
                      candidateId={activeCandidateId}
                      resourceId={selectedResource.id}
                      resourceName={selectedResource.name}
                      entityId={selectedResource.mappedEntityId}
                      modelId={geometryForSelectedResource.modelId}
                      evidence={geometryForSelectedResource}
                    />
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}

          <div className="space-y-2">
            {constructorResources.map((resource) => {
              const selected = selectedResourceId === resource.id;
              const used = livePlanner ? liveSelected.has(normalizeId(resource.id)) : activeCandidate?.resourceIds.includes(resource.id);
              const geometry = resource.mappedEntityId ? plannerProjection?.mechanicalGeometryByEntity?.[resource.mappedEntityId] : undefined;
              const hasGeometry = geometry?.resourceId === resource.id;
              const durable = Boolean(getRegisteredWorkbenchStepSource(projectSourceState, activeCandidateId, resource.id));
              return (
                <button
                  key={resource.id}
                  type="button"
                  onClick={() => inspectResource(resource.id, resource.mappedEntityId)}
                  className={`w-full rounded-lg border p-2.5 text-left transition ${selected ? 'border-cyan-300/25 bg-cyan-300/[0.06]' : used ? 'border-white/12 bg-white/[0.03] hover:border-cyan-300/15' : 'border-white/7 bg-black/10 opacity-60 hover:opacity-90'}`}
                >
                  <div className="flex items-start gap-2">
                    <Crosshair className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${used ? 'text-cyan-300' : 'text-slate-600'}`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-[10px] font-medium text-slate-100">{resource.name}</span>
                        {used ? <span className="rounded bg-cyan-300/8 px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-[0.1em] text-cyan-300">{livePlanner ? 'planner selected' : 'candidate'}</span> : null}
                        {hasGeometry ? <span className="rounded bg-emerald-300/8 px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-[0.1em] text-emerald-300">{durable ? 'registered STEP' : 'STEP envelope'}</span> : null}
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-[9px] uppercase tracking-[0.12em] text-slate-600">
                        <span>{resource.kind}</span><span>·</span><span className={decisionTone(resource.decision)}>{resource.decision}</span><span>·</span><span>{resource.costNtd ? `NT$${resource.costNtd.toLocaleString()}` : 'owned'}</span>
                      </div>
                      <p className="mt-1.5 text-[10px] leading-4 text-slate-500">{resource.note}</p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </aside>
  );
}
