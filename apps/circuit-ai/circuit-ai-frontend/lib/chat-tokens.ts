/** Inline tokens that bridge chat ↔ canvas.
 *
 *   [ref:U3]        — clickable chip that selects component U3 and flies to it
 *   [net:VCC]       — highlights net VCC across the board
 *   [issue:42]      — opens the DRC console and focuses issue #42
 *
 * We keep the grammar dirt-simple on purpose: it survives markdown, it survives
 * roundtrips through the LLM, and the regex below is the only source of truth.
 * If you find yourself adding escape-handling, back off and reconsider.
 */

export type ChatChipKind = "ref" | "net" | "issue";

export type ChatToken =
  | { kind: "text"; value: string }
  | { kind: ChatChipKind; value: string; raw: string };

const CHIP_RE = /\[(ref|net|issue):([^\]\s]+)\]/g;

export function tokenize(text: string): ChatToken[] {
  const out: ChatToken[] = [];
  let cursor = 0;
  for (const m of text.matchAll(CHIP_RE)) {
    const idx = m.index ?? 0;
    if (idx > cursor) {
      out.push({ kind: "text", value: text.slice(cursor, idx) });
    }
    out.push({
      kind: m[1] as ChatChipKind,
      value: m[2],
      raw: m[0],
    });
    cursor = idx + m[0].length;
  }
  if (cursor < text.length) {
    out.push({ kind: "text", value: text.slice(cursor) });
  }
  return out;
}

/** Convenience — build a chip string for the composer. */
export function chipToken(kind: ChatChipKind, value: string): string {
  return `[${kind}:${value}]`;
}
