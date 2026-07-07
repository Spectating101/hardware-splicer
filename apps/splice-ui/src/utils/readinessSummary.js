export function buildReadinessSummary(pkg, benchSession) {
  const gates = pkg?.gates || {};
  const powerOk = Boolean(gates.power_on_authorized || benchSession?.power_on_authorized);
  const compileOk = gates.compile_ok !== false;
  const openCount =
    benchSession?.open_gate_count ??
    gates.open_gate_count ??
    (benchSession?.open_gates || []).length ??
    0;
  const criticalOpen = benchSession?.critical_open_count ?? gates.critical_open_count ?? 0;
  const verdict = String(gates.verdict || "UNKNOWN").replace(/_/g, " ");

  const issues = [];
  if (!compileOk) issues.push("KiCad compile or DRC needs review before handoff");
  if (openCount > 0) issues.push(`${openCount} bench measurement gate(s) still open`);
  if (criticalOpen > 0) issues.push(`${criticalOpen} critical gate(s) block power-on`);
  for (const row of gates.blockers || []) {
    if (row) issues.push(String(row));
  }

  const uniqueIssues = [...new Set(issues)].slice(0, 6);

  let headline;
  let subline;
  if (powerOk) {
    headline = "Controlled power-on authorized";
    subline = "Bench gates closed with compile truth on record. Operator still owns physical safety.";
  } else if (criticalOpen > 0 || openCount > 0) {
    headline = "Hold before power-on";
    subline = "Close bench measurements before energizing. Design verify shows compile and fab gaps.";
  } else if (!compileOk) {
    headline = "Review before fabrication or handoff";
    subline = "Compile truth or DRC is not clean. Use Design verify before sending to fab.";
  } else {
    headline = "Package compiled — verify readiness";
    subline = "Inspect design preview, BOM, fab coverage, then close any remaining gates.";
  }

  return {
    powerOk,
    compileOk,
    openCount,
    criticalOpen,
    verdict,
    headline,
    subline,
    issues: uniqueIssues,
  };
}
