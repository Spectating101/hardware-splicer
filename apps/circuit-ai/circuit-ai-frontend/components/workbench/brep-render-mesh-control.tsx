'use client';

import { Box, CheckCircle2, Loader2, TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { BrepSurfaceAnchorControl } from '@/components/workbench/brep-surface-anchor-control';
import {
  useMachineWorkbenchStore,
  type BrepRenderMeshEvidence,
  type ConstructorCandidateId,
  type MechanicalGeometryEvidence,
} from '@/lib/machine-workbench-store';
import type { DeclaredPlacementEvidence } from '@/lib/workbench-placement-store';
import { getSessionStepSource } from '@/lib/workbench-session-step-sources';

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function tuple3(value: unknown): [number, number, number] | null {
  if (!Array.isArray(value) || value.length !== 3) return null;
  const rows = value.map(Number);
  return rows.every(Number.isFinite) ? rows as [number, number, number] : null;
}

function sameTuple(left: [number, number, number], right: [number, number, number]) {
  return left.every((value, index) => value === right[index]);
}

export function BrepRenderMeshControl({
  candidateId,
  resourceId,
  resourceName,
  entityId,
  evidence,
  placement,
}: {
  candidateId: ConstructorCandidateId;
  resourceId: string;
  resourceName: string;
  entityId: string;
  evidence: MechanicalGeometryEvidence;
  placement: DeclaredPlacementEvidence;
}) {
  const meshEvidence = useMachineWorkbenchStore(
    (state) => state.plannerProjections[candidateId]?.brepRenderMeshByEntity?.[entityId],
  );
  const setBrepRenderMeshEvidence = useMachineWorkbenchStore((state) => state.setBrepRenderMeshEvidence);
  const clearBrepRenderMeshEvidence = useMachineWorkbenchStore((state) => state.clearBrepRenderMeshEvidence);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);
  const [state, setState] = useState<'idle' | 'loading' | 'success' | 'unknown' | 'error'>('idle');
  const [message, setMessage] = useState('');

  const source = getSessionStepSource(candidateId, resourceId);
  const sourceReady = Boolean(
    source
    && source.modelId === evidence.modelId
    && source.contentHash === evidence.contentHash
    && source.contentHash.startsWith('sha256:'),
  );
  const meshCurrent = Boolean(
    meshEvidence
    && meshEvidence.resourceId === resourceId
    && meshEvidence.modelId === placement.modelId
    && meshEvidence.contentHash === evidence.contentHash
    && meshEvidence.frameId === placement.frameId
    && meshEvidence.placementId === placement.placementId
    && sameTuple(meshEvidence.translationMm, placement.translationMm)
    && sameTuple(meshEvidence.rotationDegXyz, placement.rotationDegXyz),
  );

  async function generateMesh() {
    if (!source || !sourceReady) {
      setState('unknown');
      setMessage('Exact render mesh needs the original hash-bound STEP source in this browser session. Re-attach the source first.');
      return;
    }

    clearBrepRenderMeshEvidence(candidateId, entityId);
    setState('loading');
    setMessage('Tessellating the declared placed STEP solid in isolated CadQuery/OCCT…');
    try {
      const response = await fetch('/api/proxy/engineering/mechanical/geometry/brep/mesh', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          project_id: 'deck-001',
          source: {
            source_id: source.sourceId,
            model_id: source.modelId,
            content_hash: source.contentHash,
            content: source.content,
          },
          placement: {
            placement_id: placement.placementId,
            object_id: placement.entityId,
            model_id: placement.modelId,
            target_frame: placement.frameId,
            translation_mm: placement.translationMm,
            rotation_deg_xyz: placement.rotationDegXyz,
            authority: 'declared',
          },
          tolerance_mm: 0.5,
          angular_tolerance_rad: 0.1,
        }),
        cache: 'no-store',
      });
      const payload = record(await response.json());
      if (!response.ok || payload.ok !== true) throw new Error(String(payload.error || `BREP mesh HTTP ${response.status}`));
      if (payload.raw_step_bytes_returned !== false || payload.render_evidence_only !== true) {
        throw new Error('HS BREP mesh response violated the render-only/raw-source boundary.');
      }
      const report = record(payload.brep_mesh);
      if (payload.exact_brep_mesh_evaluated !== true || report.status !== 'ready') {
        const required = Array.isArray(report.required_evidence) ? report.required_evidence.map(record) : [];
        const reason = String(required[0]?.reason || 'CadQuery/OCCT did not produce bounded render geometry.');
        setState('unknown');
        setMessage(`Exact mesh UNKNOWN · ${reason}`);
        return;
      }
      if (report.content_hash !== source.contentHash || report.model_id !== source.modelId) {
        throw new Error('HS BREP mesh identity no longer matches the canonical STEP source.');
      }
      if (report.frame_id !== placement.frameId || report.placement_id !== placement.placementId) {
        throw new Error('HS BREP mesh placement identity disagrees with the current declared pose.');
      }

      const rawVertices = Array.isArray(report.vertices_mm) ? report.vertices_mm : [];
      const rawTriangles = Array.isArray(report.triangles) ? report.triangles : [];
      const vertexCount = Number(report.vertex_count);
      const triangleCount = Number(report.triangle_count);
      if (!Number.isInteger(vertexCount) || vertexCount <= 0 || vertexCount > 25_000 || rawVertices.length !== vertexCount) {
        throw new Error('HS BREP mesh vertex payload violates the bounded render contract.');
      }
      if (!Number.isInteger(triangleCount) || triangleCount <= 0 || triangleCount > 50_000 || rawTriangles.length !== triangleCount) {
        throw new Error('HS BREP mesh triangle payload violates the bounded render contract.');
      }
      const vertices = rawVertices.map(tuple3);
      if (vertices.some((row) => row === null)) throw new Error('HS BREP mesh contains malformed vertex coordinates.');
      const triangles = rawTriangles.map((row) => {
        if (!Array.isArray(row) || row.length !== 3) return null;
        const values = row.map(Number);
        return values.every((value) => Number.isInteger(value) && value >= 0 && value < vertexCount)
          ? values as [number, number, number]
          : null;
      });
      if (triangles.some((row) => row === null)) throw new Error('HS BREP mesh contains malformed triangle indices.');

      const next: BrepRenderMeshEvidence = {
        entityId,
        resourceId,
        sourceId: source.sourceId,
        modelId: source.modelId,
        contentHash: source.contentHash,
        frameId: placement.frameId,
        placementId: placement.placementId,
        translationMm: placement.translationMm,
        rotationDegXyz: placement.rotationDegXyz,
        vertexCount,
        triangleCount,
        verticesMm: vertices as [number, number, number][],
        triangles: triangles as [number, number, number][],
        toleranceMm: Number(report.tolerance_mm),
        angularToleranceRad: Number(report.angular_tolerance_rad),
        kernel: String(report.kernel || 'cadquery_occt'),
        axisMapping: 'step_xyz_to_scene_xzy',
        renderEvidenceOnly: true,
        fullAssemblyCollision: false,
        physicalMeasurement: false,
        fabricationAuthorized: false,
      };
      setBrepRenderMeshEvidence(candidateId, next);
      window.setTimeout(requestFrameSelection, 0);
      setState('success');
      setMessage(`${vertexCount.toLocaleString()} vertices · ${triangleCount.toLocaleString()} triangles · placed ${placement.frameId} render evidence.`);
    } catch (error: unknown) {
      setState('error');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <>
      <div className="mt-2 rounded-lg border border-cyan-300/10 bg-cyan-300/[0.025] p-2" data-testid="brep-render-mesh-control">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-cyan-200/80">
            <Box className="h-3 w-3" /> Exact BREP display mesh
          </div>
          <span className="text-[8px] uppercase tracking-[0.1em] text-slate-600">OCCT tessellation · render only</span>
        </div>
        <div className="mt-1 text-[8px] leading-4 text-slate-500">
          {meshCurrent
            ? `${resourceName} is rendered from the hash-bound STEP solid at the current declared pose.`
            : sourceReady
              ? 'Generate bounded triangle evidence for this exact source + declared pose. Changing the pose invalidates this mesh.'
              : 'Re-attach the original STEP source in this browser session before exact tessellation.'}
        </div>
        <button
          type="button"
          onClick={generateMesh}
          disabled={state === 'loading' || !sourceReady}
          className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-cyan-300/15 bg-cyan-300/[0.04] px-2 py-1.5 text-[9px] font-semibold uppercase tracking-[0.08em] text-cyan-200 hover:bg-cyan-300/[0.08] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {state === 'loading' ? <Loader2 className="h-3 w-3 animate-spin" /> : meshCurrent ? <CheckCircle2 className="h-3 w-3" /> : <Box className="h-3 w-3" />}
          {meshCurrent ? 'Regenerate exact mesh' : 'Generate exact mesh'}
        </button>
        {message ? <div className={`mt-1.5 text-[9px] leading-4 ${state === 'success' ? 'text-emerald-300/75' : state === 'unknown' ? 'text-amber-300/75' : state === 'error' ? 'text-red-300/80' : 'text-slate-500'}`}>{message}</div> : null}
        {!meshCurrent && meshEvidence ? (
          <div className="mt-1 text-[8px] leading-4 text-amber-200/55"><TriangleAlert className="mr-1 inline h-2.5 w-2.5" />A previous exact mesh is stale for this pose and is not rendered.</div>
        ) : null}
        <div className="mt-1 text-[8px] leading-4 text-cyan-100/45">Triangle evidence improves visual geometry only. It does not prove whole-assembly collision freedom, fit, service access, structural safety, measurement truth, or fabrication authority.</div>
      </div>
      {meshCurrent ? (
        <BrepSurfaceAnchorControl
          candidateId={candidateId}
          entityId={entityId}
          resourceId={resourceId}
          resourceName={resourceName}
        />
      ) : null}
    </>
  );
}
