import { describe, expect, it } from "vitest";
import { blockerStatus, revisionNoteText, statusText } from "./statusLanguage.js";

describe("status language", () => {
  it("renders backend tokens in words and keeps unknown tokens verbatim", () => {
    expect(statusText("downloaded_and_hash_identified_not_geometrically_validated"))
      .toBe("File downloaded and hash checked · geometry not validated");
    expect(statusText("some_new_state")).toBe("some_new_state");
    expect(statusText(null)).toBe("unknown");
  });
  it("says which check ran instead of 'verified'", () => {
    expect(revisionNoteText("Verified baseline")).toBe("Reference baseline loaded · source hashes match");
    expect(revisionNoteText("Raise the target")).toBe("Raise the target");
  });
  it("never lets 'no blockers' stand alone", () => {
    expect(blockerStatus({ blockersKnown: true, checks: null })).toBe("Backend blockers · none returned (not the same as passing) · no checks run");
    expect(blockerStatus({ blockersKnown: true, checks: { run: 3, failed: 1 } })).toMatch(/1 of 3 model checks failed$/);
    expect(blockerStatus({ blockersKnown: true, checks: { run: 2, failed: 0 } })).toMatch(/2 model checks passed, physical fit not tested$/);
    expect(blockerStatus({ blockersKnown: false })).toMatch(/unknown/);
    expect(blockerStatus({ blockersKnown: true, count: 2 })).toBe("Backend blockers · 2 returned");
  });
});
