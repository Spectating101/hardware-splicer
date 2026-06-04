/**
 * Robust S-expression tokenizer + parser for KiCad files.
 *
 * KiCad `.kicad_pcb` / `.kicad_sch` / `.kicad_mod` files are S-expressions:
 *   (node "string-arg" 123 4.5 (child "..." ...) ...)
 *
 * The prior regex-based parser silently dropped `(gr_arc ...)`, `(zone ...)`,
 * custom pad primitives, and anything with multi-line nesting. This module is
 * a proper recursive-descent parser so every token in the file is accessible.
 *
 * Inspired by (but independently written from) KiCanvas's sexpr parser (MIT).
 */

export type SAtom = string | number;
export type SValue = SAtom | SList;

export interface SList {
  /** First token of the list, always a bare symbol (e.g. "footprint", "pad"). */
  head: string;
  /** Remaining children in order (atoms and nested lists). */
  rest: SValue[];
}

export function isSList(v: SValue | undefined): v is SList {
  return typeof v === "object" && v !== null && "head" in v;
}

/* ── Tokenizer ─────────────────────────────────────────────────────────── */

type TokLParen = { kind: "(" };
type TokRParen = { kind: ")" };
type TokString = { kind: "str"; value: string };
type TokAtom = { kind: "atom"; value: string };
type Token = TokLParen | TokRParen | TokString | TokAtom;

function tokenize(src: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  const n = src.length;

  while (i < n) {
    const c = src.charCodeAt(i);

    // Whitespace (space, tab, CR, LF)
    if (c === 32 || c === 9 || c === 13 || c === 10) {
      i++;
      continue;
    }

    // Paren
    if (c === 40 /* ( */) { tokens.push({ kind: "(" }); i++; continue; }
    if (c === 41 /* ) */) { tokens.push({ kind: ")" }); i++; continue; }

    // Quoted string — KiCad uses `\"` and `\\` escapes
    if (c === 34 /* " */) {
      let j = i + 1;
      let out = "";
      while (j < n) {
        const cc = src.charCodeAt(j);
        if (cc === 92 /* \ */ && j + 1 < n) {
          const nxt = src[j + 1];
          if (nxt === '"' || nxt === "\\") {
            out += nxt;
            j += 2;
            continue;
          }
          if (nxt === "n") { out += "\n"; j += 2; continue; }
          out += nxt;
          j += 2;
          continue;
        }
        if (cc === 34 /* " */) break;
        out += src[j];
        j++;
      }
      tokens.push({ kind: "str", value: out });
      i = j + 1; // past closing "
      continue;
    }

    // Bare atom — up to whitespace or paren
    let j = i;
    while (j < n) {
      const cc = src.charCodeAt(j);
      if (cc === 32 || cc === 9 || cc === 13 || cc === 10 ||
          cc === 40 || cc === 41 || cc === 34) break;
      j++;
    }
    if (j > i) {
      tokens.push({ kind: "atom", value: src.slice(i, j) });
      i = j;
      continue;
    }

    // Unreachable — defensive advance
    i++;
  }

  return tokens;
}

/* ── Parser ────────────────────────────────────────────────────────────── */

function atomToValue(tok: TokAtom | TokString): SAtom {
  if (tok.kind === "str") return tok.value;
  // Try number (KiCad uses plain decimal, optionally negative/scientific)
  const v = tok.value;
  if (/^-?\d+(\.\d+)?([eE][-+]?\d+)?$/.test(v)) {
    const num = Number(v);
    if (!Number.isNaN(num)) return num;
  }
  return v;
}

export function parseSexpr(src: string): SList {
  const toks = tokenize(src);
  let pos = 0;

  function parseList(): SList {
    // caller has consumed "("
    const first = toks[pos];
    if (!first) throw new Error("Unexpected EOF after '('");
    // Head must be an atom-like symbol.
    let head: string;
    if (first.kind === "atom" || first.kind === "str") {
      head = first.value;
      pos++;
    } else {
      // Anonymous list — rare in KiCad but handle gracefully
      head = "";
    }

    const rest: SValue[] = [];
    while (pos < toks.length) {
      const t = toks[pos];
      if (t.kind === ")") { pos++; return { head, rest }; }
      if (t.kind === "(") { pos++; rest.push(parseList()); continue; }
      rest.push(atomToValue(t));
      pos++;
    }
    throw new Error(`Unterminated list '(${head} ...)'`);
  }

  // Find the first top-level list
  while (pos < toks.length && toks[pos].kind !== "(") pos++;
  if (pos >= toks.length) {
    return { head: "", rest: [] };
  }
  pos++; // consume "("
  return parseList();
}

/* ── Tree helpers ──────────────────────────────────────────────────────── */

/** All direct child lists whose head matches `name`. */
export function childrenNamed(list: SList, name: string): SList[] {
  const out: SList[] = [];
  for (const child of list.rest) {
    if (isSList(child) && child.head === name) out.push(child);
  }
  return out;
}

/** First direct child list with the given head, or undefined. */
export function firstChild(list: SList, name: string): SList | undefined {
  for (const child of list.rest) {
    if (isSList(child) && child.head === name) return child;
  }
  return undefined;
}

/** Read positional atoms from a list as strings (numbers coerced to strings). */
export function atomStr(v: SValue | undefined): string | undefined {
  if (v === undefined) return undefined;
  if (typeof v === "string") return v;
  if (typeof v === "number") return String(v);
  return undefined;
}

export function atomNum(v: SValue | undefined): number | undefined {
  if (typeof v === "number") return v;
  if (typeof v === "string") {
    const n = Number(v);
    return Number.isFinite(n) ? n : undefined;
  }
  return undefined;
}

/** Convenience: get `(name VAL)` → VAL as string. */
export function stringProp(list: SList, name: string): string | undefined {
  const c = firstChild(list, name);
  if (!c) return undefined;
  return atomStr(c.rest[0]);
}

/** Convenience: get `(name VAL)` → VAL as number. */
export function numberProp(list: SList, name: string): number | undefined {
  const c = firstChild(list, name);
  if (!c) return undefined;
  return atomNum(c.rest[0]);
}

/**
 * Walk every list in the tree (depth-first), calling visit for each.
 * Useful for collecting e.g. all `(segment ...)` anywhere in the file.
 */
export function walk(list: SList, visit: (node: SList) => void): void {
  visit(list);
  for (const child of list.rest) {
    if (isSList(child)) walk(child, visit);
  }
}
