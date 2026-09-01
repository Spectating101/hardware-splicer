'use client';

import { Html } from '@react-three/drei';
import { Crosshair, Rotate3D } from 'lucide-react';
import { useState } from 'react';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';
import { useWorkbenchPlacementDraftStore } from '@/lib/workbench-placement-draft-store';

function rounded(value: number) {
  const result = Math.round(value * 100) / 100;
  return Object.is(result, -0) ? 0 : result;
}

function normalizedDegrees(value: number) {
  let result = value % 360;
  if (result > 180) result -= 360;
  if (result <= -180) result += 360;
  return rounded(result);
}

export function AssemblyPlacementPrecisionPad() {
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const tool = useWorkbenchPlacementDraftStore((state) => state.tool);
  const draft = useWorkbenchPlacementDraftStore(
    (state) => state.draftsByCandidate[activeCandidateId]?.[selectedEntityId],
  );
  const setDraft = useWorkbenchPlacementDraftStore((state) => state.setDraft);
  const [translationStep, setTranslationStep] = useState(1);
  const [rotationStep, setRotationStep] = useState(15);

  if (tool === 'select' || !draft) return null;

  function nudge(axis: number, direction: -1 | 1) {
    if (!draft) return;
    if (tool === 'move') {
      const next = [...draft.translationMm] as [number, number, number];
      next[axis] = rounded(next[axis] + translationStep * direction);
      setDraft({
        candidateId: draft.candidateId,
        entityId: draft.entityId,
        resourceId: draft.resourceId,
        modelId: draft.modelId,
        translationMm: next,
        rotationDegXyz: draft.rotationDegXyz,
      });
      return;
    }
    const next = [...draft.rotationDegXyz] as [number, number, number];
    next[axis] = normalizedDegrees(next[axis] + rotationStep * direction);
    setDraft({
      candidateId: draft.candidateId,
      entityId: draft.entityId,
      resourceId: draft.resourceId,
      modelId: draft.modelId,
      translationMm: draft.translationMm,
      rotationDegXyz: next,
    });
  }

  function resetCurrentVector() {
    if (!draft) return;
    setDraft({
      candidateId: draft.candidateId,
      entityId: draft.entityId,
      resourceId: draft.resourceId,
      modelId: draft.modelId,
      translationMm: tool === 'move' ? [0, 0, 0] : draft.translationMm,
      rotationDegXyz: tool === 'rotate' ? [0, 0, 0] : draft.rotationDegXyz,
    });
  }

  const steps = tool === 'move' ? [1, 5, 10] : [15, 45, 90];
  const activeStep = tool === 'move' ? translationStep : rotationStep;
  const setStep = tool === 'move' ? setTranslationStep : setRotationStep;
  const unit = tool === 'move' ? 'mm' : '°';

  return (
    <Html fullscreen style={{ pointerEvents: 'none' }}>
      <div className="pointer-events-auto absolute bottom-4 left-1/2 -translate-x-1/2 rounded-xl border border-white/10 bg-[#07101d]/94 p-2 shadow-2xl backdrop-blur" data-testid="assembly-placement-precision-pad">
        <div className="flex flex-wrap items-center justify-center gap-2">
          <div className="flex items-center gap-1.5 pr-1 text-[8px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            {tool === 'move' ? <Crosshair className="h-3 w-3" /> : <Rotate3D className="h-3 w-3" />}
            Precision {tool}
          </div>
          <div className="flex rounded-md border border-white/8 bg-black/20 p-0.5">
            {steps.map((step) => (
              <button
                key={step}
                type="button"
                onClick={() => setStep(step)}
                aria-pressed={activeStep === step}
                className={`rounded px-2 py-1 text-[8px] font-semibold ${activeStep === step ? 'bg-white/10 text-white' : 'text-slate-600 hover:text-slate-300'}`}
              >
                {step}{unit}
              </button>
            ))}
          </div>
          {['X', 'Y', 'Z'].map((axis, axisIndex) => (
            <div key={axis} className="flex items-center rounded-md border border-white/8 bg-black/20">
              <button type="button" onClick={() => nudge(axisIndex, -1)} aria-label={`Nudge ${tool} ${axis} negative ${activeStep}${unit}`} className="px-2 py-1 text-[9px] text-slate-500 hover:bg-white/5 hover:text-white">−</button>
              <span className="min-w-5 text-center text-[8px] font-semibold text-slate-400">{axis}</span>
              <button type="button" onClick={() => nudge(axisIndex, 1)} aria-label={`Nudge ${tool} ${axis} positive ${activeStep}${unit}`} className="px-2 py-1 text-[9px] text-slate-500 hover:bg-white/5 hover:text-white">+</button>
            </div>
          ))}
          <button type="button" onClick={resetCurrentVector} className="rounded-md border border-white/8 px-2 py-1 text-[8px] font-semibold uppercase tracking-[0.08em] text-slate-600 hover:bg-white/5 hover:text-slate-300">
            Zero {tool === 'move' ? 'T' : 'R'}
          </button>
        </div>
      </div>
    </Html>
  );
}
