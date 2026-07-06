/** Build a simple Mermaid flowchart from synthesis topology operators. */

export function topologyToMermaid(ops) {
  if (!Array.isArray(ops) || ops.length === 0) return "";
  const lines = ["flowchart LR"];
  ops.forEach((op, index) => {
    const nodeId = `n${index}`;
    const label = `${op.operator_id || `op${index}`} (${op.operator_type || "operator"})`
      .replace(/"/g, "'")
      .replace(/[[\]]/g, " ");
    lines.push(`  ${nodeId}["${label}"]`);
    if (index > 0) {
      lines.push(`  n${index - 1} --> ${nodeId}`);
    }
  });
  return lines.join("\n");
}
