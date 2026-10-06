import { BadgeCheck, Eye, EyeOff, LoaderCircle } from 'lucide-react';
import type { Candidate } from '@/lib/project-candidates';

function when(iso: string) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function checksLine(candidate: Candidate) {
  const checks = candidate.checks;
  if (!checks || !checks.ran) {
    return checks?.reason ? `Design-rule check did not run: ${checks.reason}` : 'Design-rule check did not run';
  }
  const label = candidate.kind === 'pcb' ? 'DRC' : 'ERC';
  const delta = checks.new_violations ?? 0;
  const after = checks.after?.total;
  return `${label} reports ${delta} new ${delta === 1 ? 'violation' : 'violations'}${typeof after === 'number' ? ` (${after} total)` : ''}`;
}

/**
 * Edits other people, or you, have proposed. A proposal is a suggestion held for review: the project's revisions do not
 * change when one is created, and nothing here accepts or applies it.
 */
export function ProposalsPanel({
  candidates,
  loading,
  previewId,
  onPreview,
}: {
  candidates: Candidate[];
  loading: boolean;
  previewId: string | null;
  onPreview: (candidate: Candidate | null) => void;
}) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-3" data-testid="proposals-panel">
      {loading && !candidates.length ? <div className="flex items-center gap-2 text-xs text-stone-500"><LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />Loading proposals</div> : null}
      {!loading && !candidates.length ? (
        <div className="rounded-md border border-dashed border-stone-300 p-3 text-xs leading-5 text-stone-500">
          No proposals yet. Choose Edit above the viewer, select a part, and describe a change. It is held here for review and does not alter the design.
        </div>
      ) : null}
      <ul className="m-0 list-none space-y-2 p-0">
        {candidates.map((candidate) => {
          const summary = candidate.diff?.summary;
          const previewing = previewId === candidate.candidate_id;
          const changes = candidate.diff?.changes || [];
          return (
            <li key={candidate.candidate_id} className={`rounded-md border bg-white p-2.5 ${previewing ? 'border-stone-900' : 'border-stone-200'}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-1 truncate text-xs font-medium text-stone-900">
                    {candidate.created_by}
                    {candidate.verified ? <BadgeCheck className="h-3 w-3 shrink-0 text-emerald-700" aria-label="Operator identity confirmed by the server" /> : null}
                  </div>
                  <div className="text-[10px] text-stone-500">{candidate.kind === 'pcb' ? 'PCB' : 'Schematic'} · from revision {candidate.base_revision}{when(candidate.created_at) ? ` · ${when(candidate.created_at)}` : ''}</div>
                </div>
                <span className="shrink-0 rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-900">Not applied</span>
              </div>

              {summary ? (
                <div className="mt-1.5 flex gap-2 text-[11px]">
                  <span className="text-emerald-700">+{summary.added}</span>
                  <span className="text-red-700">−{summary.removed}</span>
                  <span className="text-amber-700">~{summary.changed}</span>
                </div>
              ) : null}

              {candidate.applied?.length ? (
                <ul className="m-0 mt-1.5 list-none space-y-0.5 p-0 text-[11px] text-stone-600">
                  {candidate.applied.slice(0, 4).map((item, index) => (
                    <li key={index} className="truncate">{item.op}{item.target?.ref ? ` ${item.target.ref}` : ''}{item.detail ? ` · ${item.detail}` : ''}</li>
                  ))}
                  {candidate.applied.length > 4 ? <li className="text-stone-400">and {candidate.applied.length - 4} more</li> : null}
                </ul>
              ) : null}

              {changes.length ? <div className="mt-1.5 truncate text-[10px] text-stone-500" title={changes.map((change) => change.label).join('\n')}>{changes.slice(0, 3).map((change) => change.label).join(' · ')}</div> : null}
              <div className="mt-1.5 text-[10px] leading-4 text-stone-500">{checksLine(candidate)}. Reported for the reviewer; it does not accept or reject anything.</div>

              <button
                type="button"
                onClick={() => onPreview(previewing ? null : candidate)}
                className="mt-2 inline-flex h-7 items-center gap-1.5 rounded-md border border-stone-300 px-2.5 text-[11px] font-medium text-stone-700 hover:bg-stone-50"
              >
                {previewing ? <EyeOff className="h-3 w-3" aria-hidden="true" /> : <Eye className="h-3 w-3" aria-hidden="true" />}
                {previewing ? 'Stop previewing' : 'Preview in viewer'}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
