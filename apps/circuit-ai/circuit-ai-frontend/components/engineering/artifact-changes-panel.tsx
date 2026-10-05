import { Minus, Pencil, Plus } from 'lucide-react';
import { changeKey, type ArtifactDiff, type KicadChange } from '@/lib/artifact-diff';

const icon = { added: Plus, removed: Minus, changed: Pencil } as const;
const tone = {
  added: 'text-emerald-700',
  removed: 'text-red-700',
  changed: 'text-amber-700',
} as const;

/**
 * Lists what differs between the two retained KiCad files. A diff is review evidence, not a verdict: nothing here
 * changes a blocker, an evidence state or an authority.
 */
export function ArtifactChangesPanel({
  kind,
  diff,
  loading,
  selectedKey = null,
  onSelect,
}: {
  kind: string;
  diff: ArtifactDiff | null;
  loading: boolean;
  selectedKey?: string | null;
  onSelect?: (key: string | null) => void;
}) {
  const heading = kind === 'pcb' ? 'Changes in the PCB' : 'Changes in the schematic';

  return (
    <section className="mt-5 border-t border-stone-200 pt-4" aria-label={heading} data-testid="artifact-changes">
      <div className="px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-400">{heading}</div>

      {loading ? <div className="px-2 pt-2 text-[11px] text-stone-500">Comparing the two files…</div> : null}

      {!loading && diff && !diff.available ? (
        <div className="mx-2 mt-2 rounded-md border border-dashed border-stone-300 p-2.5 text-[11px] leading-4 text-stone-500">
          Not compared. {diff.reason}
        </div>
      ) : null}

      {!loading && diff && diff.available ? (
        <>
          <div className="flex flex-wrap gap-x-3 px-2 pt-2 text-[11px] text-stone-600">
            <span className={tone.changed}>{diff.summary.changed} changed</span>
            <span className={tone.added}>{diff.summary.added} added</span>
            <span className={tone.removed}>{diff.summary.removed} removed</span>
          </div>
          {diff.changes.length === 0 ? <div className="px-2 pt-2 text-[11px] text-stone-500">The two files are identical.</div> : null}
          <ul className="m-0 mt-2 list-none space-y-1 p-0">
            {diff.changes.map((change: KicadChange, index) => {
              const Icon = icon[change.change];
              return (
                <li key={changeKey(change, index)}>
                  <button
                    type="button"
                    aria-pressed={selectedKey === changeKey(change, index)}
                    onClick={() => onSelect?.(selectedKey === changeKey(change, index) ? null : changeKey(change, index))}
                    className={`block w-full rounded-md px-2 py-1.5 text-left hover:bg-stone-50 ${selectedKey === changeKey(change, index) ? 'bg-stone-100' : ''}`}
                  >
                    <div className="flex items-start gap-1.5">
                      <Icon className={`mt-0.5 h-3 w-3 shrink-0 ${tone[change.change]}`} aria-hidden="true" />
                      <div className="min-w-0">
                        <div className="truncate text-[11px] font-medium text-stone-800">{change.label}</div>
                        {change.details.map((line) => <div key={line} className="text-[10px] leading-4 text-stone-500">{line}</div>)}
                      </div>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
          {diff.limits?.truncated ? <div className="px-2 pt-2 text-[10px] text-stone-500">Showing the first {diff.limits.max_changes} changes. The counts above are complete.</div> : null}
        </>
      ) : null}
    </section>
  );
}
