'use client';

import { describeEvent, WHO, type Mission } from '@/lib/missions';
import { WhoChip } from '@/components/engineering/mission-detail';

function clock(iso: string) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/** Everything that happened, in order, each line signed by who did it. This is the evidence trail. */
export function TimelinePanel({ mission }: { mission: Mission }) {
  const events = mission.events || [];
  return (
    <section className="rounded-2xl border border-white/10 bg-[#07111f]/70 p-5">
      <details open={events.length <= 16}>
        <summary className="flex cursor-pointer list-none flex-wrap items-baseline justify-between gap-x-4">
          <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-slate-300">What happened, in order</h3>
          <span className="text-xs text-slate-500">{events.length} {events.length === 1 ? 'event' : 'events'} · append-only, nothing here can be edited</span>
        </summary>
        <ol className="mt-4 space-y-0">
          {events.map((event, index) => (
            <li key={event.seq} className="relative flex gap-3 pb-4 last:pb-0">
              {index < events.length - 1 ? <span aria-hidden className="absolute left-[5px] top-4 h-full w-px bg-white/10" /> : null}
              <span aria-hidden className={`relative mt-1.5 h-[11px] w-[11px] shrink-0 rounded-full border-2 border-[#07111f] ${WHO[event.author.kind].dot}`} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <WhoChip who={event.author.kind} label={event.author.kind === 'system' ? 'Hardware Splicer' : `${WHO[event.author.kind].label} · ${event.author.id}`} />
                  <span className="text-[11px] text-slate-500">#{event.seq} · {clock(event.created_at)}</span>
                </div>
                <p className="mt-1 text-sm leading-6 text-slate-200">{describeEvent(event)}</p>
              </div>
            </li>
          ))}
        </ol>
      </details>
    </section>
  );
}
