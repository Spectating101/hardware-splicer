import { Bot, CircleHelp, Cpu, Gauge, User } from 'lucide-react';

export type FindingProvenance = {
  kind: 'deterministic' | 'model_derived' | 'physical' | 'human' | 'unknown';
  basis?: string;
  source_ref?: string | null;
  authority_ceiling?: string;
  attested?: boolean;
  integrity_verified?: boolean;
};

export type ProjectFinding = {
  finding_id: string;
  category: 'object_blocker' | 'failed_check' | 'release_blocker' | 'measured_finding' | 'traceability_issue';
  object_id: string | null;
  text: string;
  provenance: FindingProvenance;
  /** Measurement records that report this finding cleared. A measurement claim, never closure or authority. */
  physical_evidence?: { evidence_id: string; relation: string; passed?: boolean; authority?: string }[];
};

const kinds = {
  deterministic: { label: 'Deterministic check', Icon: Cpu },
  model_derived: { label: 'Model-derived', Icon: Bot },
  human: { label: 'Human decision', Icon: User },
  physical: { label: 'Physical measurement', Icon: Gauge },
  unknown: { label: 'Provenance not recorded', Icon: CircleHelp },
} as const;

/**
 * Says how a finding was established, never whether it is correct. Anything the backend did not label shows as
 * "not recorded" rather than being guessed, and the chip carries no authority colour.
 */
export function ProvenanceChip({ provenance }: { provenance: FindingProvenance | null | undefined }) {
  const kind = provenance && provenance.kind in kinds ? provenance.kind : 'unknown';
  const base = kinds[kind];
  const label = kind === 'deterministic' && provenance?.attested === false
    ? 'Unattested stored check'
    : kind === 'physical' && provenance?.integrity_verified === true
      ? 'Integrity-checked physical record'
      : base.label;
  const Icon = base.Icon;
  const detail = [provenance?.basis, provenance?.source_ref ? `Source: ${provenance.source_ref}` : ''].filter(Boolean).join(' · ');
  return (
    <span
      title={detail || 'The stored project does not say how this finding was established.'}
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium ${kind === 'unknown' ? 'border-dashed border-stone-300 text-stone-500' : 'border-stone-300 bg-white text-stone-700'}`}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {label}
    </span>
  );
}

/** Match a finding the UI derived itself to the backend projection by text (and object when both name one). */
export function findProvenance(findings: ProjectFinding[], text: string, objectId?: string | null): FindingProvenance | null {
  const wanted = text.trim();
  const exact = findings.find((item) => item.text === wanted && (!objectId || !item.object_id || item.object_id === objectId));
  return exact ? exact.provenance : null;
}
