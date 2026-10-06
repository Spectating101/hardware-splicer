import { CircleHelp, LoaderCircle, TriangleAlert } from 'lucide-react';
import type { BomGroup, PartsResult } from '@/lib/project-parts';

function availabilityText(group: BomGroup) {
  const availability = group.availability;
  if (!availability || availability.status === 'not_checked') return 'Availability not checked';
  if (availability.status === 'lookup_failed') return 'Lookup failed';
  if (availability.status === 'no_data') return 'No provider has data on this part';
  const record = availability.records?.[0];
  if (!record) return 'Checked';
  const stock = record.stock === null || record.stock === undefined ? null : `${record.stock.toLocaleString()} in stock`;
  const when = record.as_of ? ` as of ${record.as_of.slice(0, 10)}` : '';
  return `${[record.lifecycle, stock].filter(Boolean).join(' · ') || 'Checked'}${when} · ${record.source}`;
}

/**
 * The real parts of a retained schematic. Part identity comes only from the design's own properties, and anything a
 * provider says carries its source and date. A missing MPN is shown as missing, never guessed from the value.
 */
export function PartsPanel({
  result,
  loading,
  error,
  onCheckAvailability,
}: {
  result: PartsResult | null;
  loading: boolean;
  error: string;
  onCheckAvailability: () => void;
}) {
  const checked = Boolean(result?.enrichment?.performed);
  const checkNote = result?.enrichment?.requested && !checked ? (result.enrichment.reason || 'No parts provider answered.') : '';
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-3" data-testid="parts-panel">
      {loading && !result ? <div className="flex items-center gap-2 text-xs text-stone-500"><LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />Reading the schematic</div> : null}
      {error ? <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{error}</div> : null}
      {result && !result.available ? <div className="rounded-md border border-dashed border-stone-300 p-3 text-xs leading-5 text-stone-500">No parts list. {result.reason}</div> : null}

      {result?.available ? (
        <>
          {result.summary ? (
            <p className="mb-3 text-[11px] leading-4 text-stone-500">
              {result.summary.components} components in {result.summary.groups} lines
              {result.summary.missing_mpn_groups ? ` · ${result.summary.missing_mpn_groups} without an MPN` : ''}
              {result.summary.dnp_components ? ` · ${result.summary.dnp_components} not fitted` : ''}
            </p>
          ) : null}
          <button
            type="button"
            onClick={onCheckAvailability}
            disabled={loading}
            title="Looks each part number up in the providers this server has enabled. Nothing is sent until you click."
            className="mb-3 inline-flex h-7 items-center gap-1.5 rounded-md border border-stone-300 px-2.5 text-[11px] font-medium text-stone-700 hover:bg-stone-50 disabled:cursor-not-allowed disabled:text-stone-400"
          >
            {loading ? <LoaderCircle className="h-3 w-3 animate-spin" aria-hidden="true" /> : null}{checked ? 'Check again' : 'Check availability'}
          </button>
          {checkNote ? <p className="mb-3 text-[11px] leading-4 text-stone-500">{checkNote}</p> : null}
          <ul className="m-0 list-none space-y-2 p-0">
            {result.bom_groups.map((group) => (
              <li key={`${group.value}|${group.footprint}|${group.mpn}|${group.refs.join(',')}`} className="rounded-md border border-stone-200 bg-white p-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium text-stone-900">{group.value || 'Unnamed part'}</div>
                    <div className="truncate text-[10px] text-stone-500">{group.footprint || 'No footprint'}</div>
                  </div>
                  <span className="shrink-0 rounded bg-stone-100 px-1.5 py-0.5 text-[10px] font-medium text-stone-700">×{group.quantity}</span>
                </div>
                <div className="mt-1.5 truncate font-mono text-[10px] text-stone-500" title={group.refs.join(', ')}>{group.refs.join(' ')}</div>
                <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px]">
                  {group.mpn ? <span className="font-mono text-stone-700">{group.mpn}</span> : group.not_in_bom ? null : (
                    <span className="inline-flex items-center gap-1 text-amber-700"><TriangleAlert className="h-3 w-3" aria-hidden="true" />No MPN in the design</span>
                  )}
                  {group.dnp ? <span className="rounded border border-stone-300 px-1 text-stone-500">not fitted</span> : null}
                </div>
                <div className="mt-1.5 flex items-start gap-1 text-[10px] leading-4 text-stone-500">
                  <CircleHelp className="mt-0.5 h-3 w-3 shrink-0 text-stone-400" aria-hidden="true" />
                  <span>{availabilityText(group)}</span>
                </div>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}
