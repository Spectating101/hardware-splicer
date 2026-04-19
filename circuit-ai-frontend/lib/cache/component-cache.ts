// Simple file-backed JSON cache for Jarvis identifications + project suggestions.
// Keyed by sha256 of the request (image bytes for vision, JSON-stringified
// inventory for projects). SQLite upgrade deferred until volume warrants it.
//
// Cache lives under .next/cache/jarvis/ by default (.gitignored in Next projects).

import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";

const CACHE_ROOT = process.env.JARVIS_CACHE_DIR
  ?? path.join(process.cwd(), ".next", "cache", "jarvis");

const CACHE_MAX_AGE_MS = 1000 * 60 * 60 * 24 * 30; // 30 days

export interface CacheEntry<T> {
  key: string;
  value: T;
  createdAt: number;
  model: string;
}

export function hashBuffer(buf: ArrayBuffer | Uint8Array | Buffer): string {
  const h = createHash("sha256");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  h.update(Buffer.isBuffer(buf) ? buf : Buffer.from(buf as any));
  return h.digest("hex").slice(0, 24);
}

export function hashString(input: string): string {
  return createHash("sha256").update(input).digest("hex").slice(0, 24);
}

async function ensureRoot(namespace: string): Promise<string> {
  const dir = path.join(CACHE_ROOT, namespace);
  await fs.mkdir(dir, { recursive: true });
  return dir;
}

export async function cacheGet<T>(namespace: string, key: string): Promise<CacheEntry<T> | null> {
  try {
    const dir = await ensureRoot(namespace);
    const file = path.join(dir, `${key}.json`);
    const raw = await fs.readFile(file, "utf8");
    const entry = JSON.parse(raw) as CacheEntry<T>;
    if (Date.now() - entry.createdAt > CACHE_MAX_AGE_MS) return null;
    return entry;
  } catch {
    return null;
  }
}

export async function cacheSet<T>(namespace: string, key: string, value: T, model: string): Promise<void> {
  const dir = await ensureRoot(namespace);
  const file = path.join(dir, `${key}.json`);
  const entry: CacheEntry<T> = { key, value, createdAt: Date.now(), model };
  await fs.writeFile(file, JSON.stringify(entry), "utf8");
}
