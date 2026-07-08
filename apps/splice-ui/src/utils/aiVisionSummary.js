export function dataUrlToBase64(dataUrl) {
  if (!dataUrl || typeof dataUrl !== "string") return "";
  const comma = dataUrl.indexOf(",");
  return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
}

export function summarizeDonorVisionReport(report) {
  if (!report || typeof report !== "object") {
    return { headline: "No donor vision run yet", blocks: [], gates: [], boards: [] };
  }
  const boards = Array.isArray(report.boards) ? report.boards : [];
  const applied = Number(report.applied_board_count || 0);
  const blocks = [];
  const gates = [];
  for (const row of boards) {
    const salvage = row.functional_salvage || {};
    for (const block of salvage.reusable_blocks || []) {
      blocks.push(block);
    }
    for (const gate of salvage.evidence_gates || []) {
      gates.push(gate);
    }
  }
  let headline = "Donor vision skipped";
  if (applied > 0) {
    headline = `Donor vision applied to ${applied} board${applied === 1 ? "" : "s"}`;
  } else if (boards.some((row) => row.mode === "dry_run")) {
    headline = "Photo received — Qwen dry-run (enable live + API key for full analysis)";
  } else if (boards.length) {
    headline = "Donor photo analyzed — review candidate evidence before build";
  }
  return { headline, blocks, gates, boards, applied };
}

export function summarizeVisionEnrichReport(report) {
  if (!report || typeof report !== "object") {
    return { headline: "No intake vision enrichment", notes: [], applied: false };
  }
  const notes = [];
  for (const row of report.candidates || []) {
    for (const note of row.observations || row.vision_evidence_notes || []) {
      notes.push(String(note));
    }
  }
  for (const row of report.applied_notes || report.evidence_notes || []) {
    notes.push(String(row));
  }
  const applied = Boolean(report.applied || report.apply_count || notes.length);
  return {
    headline: applied ? "Intake vision enrichment applied" : "Vision enrichment indexed attachments",
    notes: [...new Set(notes.filter(Boolean))],
    applied,
    mode: report.mode || report.provider || "",
  };
}

export function qwenReadyFromCapabilities(caps) {
  const circuit = caps?.circuit_ai || {};
  const status = circuit.qwen_board_vision_status || caps?.qwen_board_vision_status || {};
  return Boolean(status.ready_for_live_model || status.api_key_configured);
}
