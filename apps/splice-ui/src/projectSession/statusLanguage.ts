// One vocabulary for status on the bench. Every status phrase says what it covers and where it
// came from; backend tokens are rendered in words, and the raw token stays available verbatim.

export type KnownStatusToken =
  | "downloaded_and_hash_identified_not_geometrically_validated"
  | "available"
  | "unavailable"
  | "read"
  | "missing"
  | "unreadable";

export type KnownRevisionNote =
  | "Verified native baseline"
  | "Verified baseline";

export interface BlockerChecksSummary {
  run: number;
  failed: number;
}

export interface BlockerStatusInput {
  blockersKnown: boolean;
  count?: number;
  checks?: BlockerChecksSummary | null;
}

// Backend status tokens → words. Unknown tokens fall back to the token itself.
const STATUS_TOKENS: Record<KnownStatusToken, string> = {
  downloaded_and_hash_identified_not_geometrically_validated: "File downloaded and hash checked · geometry not validated",
  available: "Geometry available",
  unavailable: "Geometry unavailable",
  read: "Record read",
  missing: "Record missing",
  unreadable: "Record unreadable",
};

export function statusText(token?: KnownStatusToken | (string & {}) | null): string {
  if (token === undefined || token === null || token === "") return "unknown";
  return (STATUS_TOKENS as Record<string, string | undefined>)[token] ?? String(token);
}

// System-written revision notes → what the backend actually did when it wrote them.
// "Verified" in these notes means the backend's own seal and source checks ran; it is not a
// statement about the design, so the words say which check ran.
const REVISION_NOTES: Record<KnownRevisionNote, string> = {
  "Verified native baseline": "Baseline run · native study stages ran and the package was sealed with hashes",
  "Verified baseline": "Reference baseline loaded · source hashes match",
};

export function revisionNoteText(note?: KnownRevisionNote | (string & {}) | null): string {
  if (!note) return "";
  return (REVISION_NOTES as Record<string, string | undefined>)[note] ?? note;
}

/**
 * The backend-blocker line, always paired with what was checked. "None returned" is never a pass.
 * @param blockersKnown  the assurance and release answers arrived
 * @param count          blockers the backend returned
 * @param checks         { run: number, failed: number } study checks for this revision, or null
 */
export function blockerStatus({ blockersKnown, count = 0, checks = null }: BlockerStatusInput): string {
  if (!blockersKnown) return "Backend blockers · unknown (no answer from the backend)";
  if (count) return `Backend blockers · ${count} returned`;
  const checked = !checks || !checks.run ? "no checks run"
    : checks.failed ? `${checks.failed} of ${checks.run} model check${checks.run === 1 ? "" : "s"} failed`
      : `${checks.run} model check${checks.run === 1 ? "" : "s"} passed, physical fit not tested`;
  return `Backend blockers · none returned (not the same as passing) · ${checked}`;
}
