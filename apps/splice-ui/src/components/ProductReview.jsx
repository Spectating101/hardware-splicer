import { useState } from "react";
import { BomPanel, InstructionsPanel, WiringPanel } from "../components/ProjectPanels.jsx";
import { deriveProjectReview, PROJECT_REVIEW_TABS } from "../projectSession/projectReviewModel.js";

function Missing({ children }) {
  return <p className="muted product-review__missing">{children}</p>;
}

function Details({ title, value }) {
  return <div><dt>{title}</dt><dd>{value || "Not provided"}</dd></div>;
}

/**
 * First-use project review: the same real package drives every discipline.
 * This is a reader, not an engineering authorizer or an alternate data store.
 */
export default function ProductReview({ session }) {
  const [tab, setTab] = useState("overview");
  const model = deriveProjectReview(session);
  const pkg = session.projectPackage || null;
  const activeTab = PROJECT_REVIEW_TABS.find((item) => item.id === tab) || PROJECT_REVIEW_TABS[0];
  const hasWiring = Boolean(model.wiring.narrative_markdown || model.wiring.topology_operators?.length);
  const hasMechanical = Object.keys(model.mechanism).length > 0;
  const hasCode = Object.keys(model.firmware).length > 0;
  const steps = Array.isArray(model.instructions.assembly_steps) ? model.instructions.assembly_steps : [];

  return (
    <section className="card product-review" data-testid="product-review" aria-label="Engineering review">
      <header className="product-review__header">
        <div>
          <p className="eyebrow">Project workspace</p>
          <h2>Engineering review</h2>
          <p className="muted small">
            {model.revision === null ? "Working project · revision not persisted" : `Saved revision ${model.revision}`}
            {model.dirty ? " · unsaved changes" : ""}
          </p>
        </div>
        <span className="chip">{model.mode}</span>
      </header>
      <div className="product-review__tabs" role="tablist" aria-label="Project disciplines">
        {PROJECT_REVIEW_TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={activeTab.id === item.id}
            className={activeTab.id === item.id ? "active" : ""}
            data-testid={`review-tab-${item.id}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" aria-label={activeTab.label} className="product-review__content" data-testid="review-content">
        {tab === "overview" && (
          <>
            <p className="product-review__goal">{model.goal || "Describe your project in Intake to begin."}</p>
            <dl className="product-review__facts">
              <Details title="Project" value={model.name} />
              <Details title="Design checks" value={model.softwareCheck} />
              <Details title="Physical measurements" value={model.physicalCheck} />
              <Details title="Power-on" value="Not authorized by this review" />
            </dl>
            {!model.hasPackage && (
              <Missing>Project created. Compile a design or complete a donor assessment to populate real engineering outputs. Nothing is fabricated for this view.</Missing>
            )}
            {model.blockers.length > 0 && (
              <div className="product-review__blockers" data-testid="review-blockers">
                <h3>Unresolved blockers</h3>
                <ul>{model.blockers.map((blocker, i) => <li key={i}>{blocker}</li>)}</ul>
              </div>
            )}
            <h3>Source identities</h3>
            {model.sources.length ? (
              <ul className="product-review__sources">
                {model.sources.map((source) => (
                  <li key={source.sha256}><strong>{source.id}</strong><code>{source.sha256}</code></li>
                ))}
              </ul>
            ) : (
              <Missing>No SHA-256 source identities are present in this package. Sources are not assumed verified.</Missing>
            )}
          </>
        )}
        {tab === "parts" && (
          model.parts.length ? (
            <>
              <p className="muted small">Generated BOM entries are proposals. Prices and donor specifications require independent sourcing or measurement.</p>
              <BomPanel pkg={pkg} />
            </>
          ) : <Missing>No parts list has been produced for this project.</Missing>
        )}
        {tab === "wiring" && (
          hasWiring ? (
            <>
              <p className="muted small">Proposed topology; review electrical ratings and unknown interfaces before physical wiring.</p>
              <WiringPanel pkg={pkg} />
            </>
          ) : <Missing>No wiring artifact is available. An absent wiring guide is not an approved pinout.</Missing>
        )}
        {tab === "mechanical" && (
          hasMechanical ? (
            <>
              <p className="muted small">Mechanical output is a design proposal, not a measured fit or fabricated part.</p>
              <dl className="product-review__facts">
                <Details title="Mechanism" value={model.mechanism.kind} />
                <Details title="Reported status" value={model.mechanism.status} />
                <Details title="Geometry limitations" value={model.mechanism.degraded_reason || model.mechanism.claim_boundary} />
              </dl>
              {Array.isArray(model.mechanism.outputs) && model.mechanism.outputs.length > 0 && (
                <ul className="clean-list">{model.mechanism.outputs.map((output, i) => <li key={i}><code>{String(output)}</code></li>)}</ul>
              )}
            </>
          ) : <Missing>No mechanical design or measured donor dimensions are attached yet.</Missing>
        )}
        {tab === "code" && (
          hasCode ? (
            <>
              <p className="muted small">Firmware scaffold only. Compilation, flashing, and device operation are not established here.</p>
              <dl className="product-review__facts">
                <Details title="Filename" value={model.firmware.filename} />
                <Details title="Claim boundary" value={model.firmware.claim_boundary} />
              </dl>
              {typeof model.firmware.source === "string" && (
                <pre className="product-review__code">{model.firmware.source.slice(0, 3000)}{model.firmware.source.length > 3000 ? "\n… (preview truncated)" : ""}</pre>
              )}
            </>
          ) : <Missing>No code or firmware scaffold has been generated for this project.</Missing>
        )}
        {tab === "build" && (
          steps.length ? (
            <>
              <p className="muted small">Proposed assembly steps. Do not energize or move hardware without separate physical validation and authorization.</p>
              <InstructionsPanel pkg={pkg} />
            </>
          ) : <Missing>No build instructions are available. Do not infer a safe assembly sequence.</Missing>
        )}
        {tab === "verify" && (
          <>
            <dl className="product-review__facts">
              <Details title="Software verification" value={model.softwareCheck} />
              <Details title="Copper" value={model.truth.copper.label} />
              <Details title="Bench" value={model.truth.bench.label} />
              <Details title="Physical proof" value={model.physicalCheck} />
            </dl>
            <p className="muted small">A clean KiCad DRC or simulated bench result does not verify physical safety. Use the separate Bench stage for evidence and authorization.</p>
            {model.blockers.length > 0 ? (
              <div className="product-review__blockers"><h3>Open blockers</h3><ul>{model.blockers.map((item, i) => <li key={i}>{item}</li>)}</ul></div>
            ) : <Missing>No explicit package blockers are listed; this is not a physical clearance.</Missing>}
            {model.handoff.available && model.handoff.url ? (
              <div className="product-review__handoff">
                <a className="secondary button-link" href={model.handoff.url} download>Download generated package</a>
                <p className="muted small">{model.revisionBound ? `Package metadata matches saved revision ${model.revision}.` : "Revision binding is not established by the available package metadata; inspect the exported files before relying on them."}</p>
              </div>
            ) : <Missing>{model.handoff.explanation}</Missing>}
          </>
        )}
      </div>
    </section>
  );
}
