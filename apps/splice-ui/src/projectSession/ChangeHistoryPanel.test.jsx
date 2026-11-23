import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ChangeHistoryPanel from "./ChangeHistoryPanel.jsx";
import { fetchChangeDossier } from "./digitalStudyApi";

vi.mock("./digitalStudyApi", () => ({ fetchChangeDossier: vi.fn() }));

const checks = (runtime, limit) => [
  { id: "work_runtime", passed: runtime >= limit, actual: runtime, limit, unit: "h" },
  { id: "ordinary_source_margin", passed: true, actual: 0.48, limit: 0.3, unit: "A" },
];
// Shaped like the replay's recorded Fielddeck 5 history: a failed target-only revision,
// then a modelled candidate applied natively.
const DOSSIER = {
  head_revision: 4, cite_linked: true,
  changes: [
    { proposal_sha256: "p1", policy_id: "portable-runtime-4h", policy_version: "1.0.0", policy_decision: "BLOCKED",
      base_revision: 1, base_checks: checks(3.166, 2.5), targets: [{ id: "work-runtime", fact: "metric.work_runtime_lower_h", operator: ">=", value: 4, unit: "h", actual: 3.166, passed: false }], review_verification: "replayed by Policy Lab verify here", unmet: [{ id: "work-runtime", explanation: "metric.work_runtime_lower_h is 3.166 h; target >= 4 h." }],
      requirement_changes: { minimum_work_runtime_h: { before: 2.5, after: 4 } },
      applied_revision: { revision: 2, run_id: "r2", requirements_met: false, checks: checks(3.166, 4),
        change_request: "Apply Policy Lab portable-runtime-4h proposal" },
      candidates: [], change_evidence: { packet_sha256: "a".repeat(64) } },
    { proposal_sha256: "p2", policy_id: "portable-runtime-4h-pi-load-candidate", policy_version: "1.0.0",
      policy_decision: "BLOCKED", base_revision: 2, base_checks: checks(3.166, 4), targets: [{ id: "work-runtime", fact: "metric.work_runtime_lower_h", operator: ">=", value: 4, unit: "h", actual: 3.166, passed: false }], unmet: [],
      requirement_changes: { pi_work_current_a: { before: 1, after: 0.697 } },
      applied_revision: { revision: 3, run_id: "r3", requirements_met: true, checks: checks(4.002, 4) },
      candidates: [{ id: "pi-work-load-budget", input: "pi_work_current_a", before: 1, after: 0.697,
        formula: "P_required = E_min / T", numbers: { before: 1, runtime_h: 3.166, work_system_power_w: 7.25 },
        physical_means: "unknown / not tested",
        native_outcome: { fact: "metric.work_runtime_lower_h", operator: ">=", required: 4, unit: "h", native_value: 4.002, met: true } }],
      change_evidence: null },
  ],
  cite_editions: [{ edition_id: "b".repeat(64), bound_revision: 3, stale_by_hs_head: true, issued_at: "2026-11-20T10:00:00Z",
    latest_check: { checked_at: "2026-11-20T10:05:00Z", status: "stale", head_revision: 4 } }],
};

beforeEach(() => { vi.resetAllMocks(); });

describe("ChangeHistoryPanel", () => {
  it("shows each decision verbatim, the failed revision as failed, and the candidate's native outcome", async () => {
    fetchChangeDossier.mockResolvedValue({ change_dossier: DOSSIER });
    const onOpenRevision = vi.fn();
    render(<ChangeHistoryPanel projectId="digital-x" latestRevision={4} onOpenRevision={onOpenRevision} />);
    const [first, second] = await screen.findAllByTestId("change-entry");
    // The decision names the revision it reviewed and why; the application is a separate HS step.
    expect(within(first).getByTestId("change-decision")).toHaveTextContent(
      "Policy Lab decision on revision 1: BLOCKED (Work runtime, lower estimate 3.166 h < 4 h)");
    expect(first).toHaveTextContent("Policy portable-runtime-4h 1.0.0");
    // Policy Lab's sentence is quoted verbatim (<q> draws the quotation marks).
    expect(first).toHaveTextContent("Policy Lab says:metric.work_runtime_lower_h is 3.166 h; target >= 4 h.");
    expect(first.querySelector(".change-quote q")).toHaveTextContent("metric.work_runtime_lower_h is 3.166 h; target >= 4 h.");
    const applied = within(first).getByTestId("change-applied");
    expect(applied).toHaveTextContent("as revision 2");
    expect(applied).toHaveTextContent("Record shows: HS change request Apply Policy Lab portable-runtime-4h proposal · review check: replayed by Policy Lab verify here");
    expect(applied).not.toHaveTextContent("BLOCKED");
    expect(first).toHaveTextContent("Minimum work runtime · 2.5 → 4 h");
    // Same derivation as the revision compare: the limit rose, the measured value did not move.
    expect(first).toHaveTextContent("Work runtime: Newly fails: requirement increased");
    expect(first).toHaveTextContent("Measured 3.166 h, unchanged · target 4 h, up from 2.5 h");
    expect(first).not.toHaveTextContent("minimum_work_runtime_h 2.5");
    const raw = within(first).getByText("Machine keys and raw values").closest("details");
    expect(raw).not.toHaveAttribute("open");
    expect(raw).toHaveTextContent('minimum_work_runtime_h{"before":2.5,"after":4}');
    expect(first).toHaveTextContent(`sha256 ${"a".repeat(16)}`);
    expect(second).toHaveTextContent("Not exported for this change.");
    const candidate = within(second).getByTestId("change-candidate");
    expect(candidate).toHaveTextContent("Pi current at work load · 1 → 0.697 A");
    expect(within(second).getByTestId("change-decision")).toHaveTextContent(
      "Policy Lab decision on revision 2: BLOCKED (Work runtime, lower estimate 3.166 h < 4 h) · proposed modelled candidate pi-work-load-budget");
    expect(within(second).getByTestId("change-applied")).toHaveTextContent(
      "as revision 3 · native outcome: Work runtime, lower estimate 4.002 h against ≥ 4 h, meets the target (modeled, not measured)");
    expect(within(second).getByTestId("change-applied")).toHaveTextContent("HS change request not recorded");
    expect(candidate).toHaveTextContent("Work system power · 7.25 W");
    expect(candidate).toHaveTextContent("Pi current at work load, before · 1 A");
    expect(candidate).toHaveTextContent("Physical means of reaching this value: unknown / not tested");
    const link = within(second).getByRole("link", { name: "revision 3" });
    expect(link).toHaveAttribute("href", "/projects/digital-x?rev=3");
    fireEvent.click(link);
    expect(onOpenRevision).toHaveBeenCalledWith(3);
    const cite = screen.getByTestId("cite-state");
    expect(cite).toHaveTextContent("bound to revision 3 · stale: HS is at revision 4");
    expect(cite).toHaveTextContent("Last currency check 2026-11-20 10:05 UTC: stale against revision 4");
    const text = screen.getByTestId("change-history").textContent.toLowerCase();
    for (const word of [/\bready\b/, /\bapproved\b/, /\bfix(es|ed)?\b/]) expect(text).not.toMatch(word);
  });

  it("says plainly when nothing is recorded and Cite is not linked", async () => {
    fetchChangeDossier.mockResolvedValue({ change_dossier: { changes: [], cite_editions: [], cite_linked: false, head_revision: 1 } });
    render(<ChangeHistoryPanel projectId="digital-x" latestRevision={1} />);
    expect(await screen.findByText("No Policy Lab change is recorded for this project.")).toBeInTheDocument();
    expect(screen.getByTestId("cite-state")).toHaveTextContent("Cite dossier · not linked.");
  });

  it("reports a missed or unknown candidate outcome and an unapplied proposal", async () => {
    const missed = structuredClone(DOSSIER);
    missed.changes[1].candidates[0].native_outcome = { ...missed.changes[1].candidates[0].native_outcome, native_value: 3.9, met: false };
    missed.changes[0].applied_revision = null;
    fetchChangeDossier.mockResolvedValue({ change_dossier: missed });
    render(<ChangeHistoryPanel projectId="digital-x" latestRevision={4} />);
    const [first, second] = await screen.findAllByTestId("change-entry");
    expect(first).toHaveTextContent("Not applied to any saved revision.");
    expect(second).toHaveTextContent("Work runtime, lower estimate 3.9 h against ≥ 4 h, misses the target");
  });

  it("shows the error rather than an empty history", async () => {
    fetchChangeDossier.mockRejectedValue(new Error("The project is not a digital study with saved runs."));
    render(<ChangeHistoryPanel projectId="plain" latestRevision={2} />);
    expect(await screen.findByRole("status")).toHaveTextContent("Change history · unknown. The project is not a digital study");
  });
});
