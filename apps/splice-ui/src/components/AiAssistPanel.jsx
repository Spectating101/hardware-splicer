import { useMemo } from "react";
import { summarizeDonorVisionReport, summarizeVisionEnrichReport } from "../utils/aiVisionSummary.js";
import { StatusPill } from "./ProjectPanels.jsx";

function BlockList({ blocks }) {
  if (!blocks?.length) return <p className="muted small">No reusable blocks identified yet.</p>;
  return (
    <ul className="clean-list ai-block-list">
      {blocks.map((row) => (
        <li key={row.block_id || row.name}>
          <strong>{row.name || row.block_id}</strong>
          {row.verdict && <span className="chip small">{row.verdict}</span>}
          {row.notes && <span className="muted small"> — {row.notes}</span>}
        </li>
      ))}
    </ul>
  );
}

function GateList({ gates }) {
  if (!gates?.length) return <p className="muted small">No measurement gates from vision yet.</p>;
  return (
    <ul className="clean-list">
      {gates.map((row) => (
        <li key={row.gate_id || row.name}>
          <code>{row.gate_id || row.name}</code>
          {row.requirement && <span className="muted"> — {row.requirement}</span>}
        </li>
      ))}
    </ul>
  );
}

export default function AiAssistPanel({
  capabilities = null,
  donorVisionReport = null,
  visionEnrichReport = null,
  clarifier = null,
  compact = false,
}) {
  const donorSummary = useMemo(() => summarizeDonorVisionReport(donorVisionReport), [donorVisionReport]);
  const enrichSummary = useMemo(() => summarizeVisionEnrichReport(visionEnrichReport), [visionEnrichReport]);
  const qwenStatus = capabilities?.circuit_ai?.qwen_board_vision_status || {};
  const liveReady = Boolean(qwenStatus.ready_for_live_model);

  return (
    <div className={`ai-assist-panel ${compact ? "compact" : ""}`}>
      <section className="card ai-status-card">
        <div className="card-header">
          <h3>AI-assisted bring-up</h3>
          <StatusPill ok={liveReady} label={liveReady ? "Live vision ready" : "Offline / dry-run"} />
        </div>
        <p className="muted small">
          Qwen board vision, intent clarification, and evidence extraction — candidate evidence only. Bench gates and
          compile truth stay deterministic.
        </p>
        {qwenStatus.model && (
          <p className="hint small">
            Provider: <code>{qwenStatus.provider || "qwen"}</code> · model rotation:{" "}
            {(qwenStatus.model_rotation || [qwenStatus.model]).slice(0, 2).join(", ")}
          </p>
        )}
      </section>

      {clarifier && (
        <section className="card">
          <h3>Intent clarification</h3>
          <p className="muted small">
            {clarifier.needs_clarification ? "Follow-up answers shaped the intake." : "Goal parsed without blockers."}
          </p>
          {clarifier.assumptions?.length > 0 && (
            <ul className="clean-list">
              {clarifier.assumptions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="card">
        <h3>Donor board vision</h3>
        <p className="lead small">{donorSummary.headline}</p>
        {donorSummary.boards.map((row) => (
          <div key={row.board_id} className="ai-board-row">
            <div className="ai-board-meta">
              <strong>{row.board_id}</strong>
              <span className="chip small">{row.mode || "pending"}</span>
              {row.source_artifact && <span className="muted small mono">{row.source_artifact}</span>}
            </div>
            {row.analysis?.mode === "dry_run" && (
              <p className="hint">
                Photo staged for Qwen — set <code>visionLive</code> and configure API keys for live board evidence.
              </p>
            )}
          </div>
        ))}
        <h4>Reusable blocks</h4>
        <BlockList blocks={donorSummary.blocks} />
        <h4>Evidence gates</h4>
        <GateList gates={donorSummary.gates} />
      </section>

      <section className="card">
        <h3>Intake vision enrichment</h3>
        <p className="lead small">{enrichSummary.headline}</p>
        {enrichSummary.notes.length > 0 ? (
          <ul className="clean-list">
            {enrichSummary.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : (
          <p className="muted small">Upload bench or donor photos in the wizard to index parts and evidence notes.</p>
        )}
      </section>
    </div>
  );
}
