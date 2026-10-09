import type { AssemblyPlan } from '@/components/engineering/assembly-viewer';

export type ReclaimRow = { ref: string; what: string; package: string; verdict: string; evidence: string; datasheet: string; why: string };

const WANTED = new Set(['keep', 'test_first', 'identify', 'optional']);

/** What a plan says is worth taking, with how many of its measurements are written down. A row is a suggestion, never a clearance to reuse. */
export function reclaimRows(plan: AssemblyPlan): ReclaimRow[] {
  const rows: ReclaimRow[] = [];
  for (const part of plan.parts) {
    const salvage = part.salvage;
    if (!salvage || !WANTED.has(salvage.verdict) || part.do_not_populate) continue;
    const lookup = part.lookup;
    const evidence = lookup?.evidence && lookup.evidence.total ? `${lookup.evidence.recorded} of ${lookup.evidence.total} readings recorded` : '';
    rows.push({
      ref: part.ref,
      what: part.identity?.typed || part.identity?.mpn || part.value || '',
      package: part.footprint.split(':').pop() ?? part.footprint,
      verdict: salvage.label,
      evidence,
      datasheet: lookup?.match?.datasheet ?? '',
      why: salvage.reasons[0] ?? '',
    });
  }
  return rows;
}

/** One CSV cell. A cell a spreadsheet would run as a formula (it starts with = + - @ or a control character) gets a leading apostrophe. */
export function csvCell(value: string): string {
  const text = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(rows: ReclaimRow[]): string {
  const header = ['Label', 'What it is (as you read it)', 'Package', 'Advice', 'Measurements', 'Datasheet', 'Why'];
  const lines = [header, ...rows.map((r) => [r.ref, r.what, r.package, r.verdict, r.evidence, r.datasheet, r.why])];
  return `${lines.map((line) => line.map(csvCell).join(',')).join('\r\n')}\r\n`;
}
