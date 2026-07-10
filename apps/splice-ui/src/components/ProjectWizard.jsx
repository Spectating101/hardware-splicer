import { useMemo, useState } from "react";
import { clarifyIntent, donorBoardVision, visionEnrichIntake } from "../api.js";
import {
  INITIAL_WIZARD,
  PART_TYPES,
  buildComposePayloadFromWizard,
  buildIntakeFromWizard,
  defaultPart,
  getWizardSteps,
  slugify,
} from "../intakeBuilder.js";
import { summarizeDonorVisionReport } from "../utils/aiVisionSummary.js";
import CanvasComposeStep from "./CanvasComposeStep.jsx";

function StepIndicator({ steps, currentId }) {
  const currentIndex = steps.findIndex((row) => row.id === currentId);
  return (
    <ol className="wizard-steps">
      {steps.map((step, index) => (
        <li
          key={step.id}
          className={
            index < currentIndex ? "done" : index === currentIndex ? "active" : ""
          }
        >
          <span className="wizard-step-num">{index + 1}</span>
          <span className="wizard-step-label">{step.label}</span>
        </li>
      ))}
    </ol>
  );
}

export default function ProjectWizard({
  donorFixtures,
  visionCapabilities = null,
  llmPolicy = null,
  onCancel,
  onBuild,
  building,
  buildError,
  stageLabel,
  embedded = false,
}) {
  const [wizard, setWizard] = useState({ ...INITIAL_WIZARD });
  const [stepId, setStepId] = useState("goal");
  const [clarifyLoading, setClarifyLoading] = useState(false);
  const [clarifyError, setClarifyError] = useState(null);
  const [enrichedIntent, setEnrichedIntent] = useState(null);
  const [visionLoading, setVisionLoading] = useState(false);
  const [visionError, setVisionError] = useState(null);

  const qwenLiveReady = Boolean(
    visionCapabilities?.circuit_ai?.qwen_board_vision_status?.ready_for_live_model,
  );
  const llmComposeReady = Boolean(llmPolicy?.qwen_llm_first);

  const steps = useMemo(() => getWizardSteps(wizard), [wizard]);
  const stepIndex = steps.findIndex((row) => row.id === stepId);

  const patchWizard = (patch) => setWizard((prev) => ({ ...prev, ...patch }));

  const goNext = async () => {
    setClarifyError(null);
    if (stepId === "goal") {
      if (!wizard.goal.trim() || wizard.goal.trim().length < 12) {
        setClarifyError("Describe your project in at least one full sentence.");
        return;
      }
      patchWizard({ projectName: slugify(wizard.projectName || wizard.goal) });
      setClarifyLoading(true);
      try {
        const report = await clarifyIntent({
          goal: wizard.goal.trim(),
          project_name: slugify(wizard.projectName || wizard.goal),
        });
        patchWizard({ clarifier: report });
        if (report.enriched_intent) setEnrichedIntent(report.enriched_intent);
        setStepId("clarify");
      } catch (err) {
        setClarifyError(err.message);
      } finally {
        setClarifyLoading(false);
      }
      return;
    }

    if (stepId === "clarify") {
      setClarifyLoading(true);
      try {
        const report = await clarifyIntent({
          goal: wizard.goal.trim(),
          project_name: slugify(wizard.projectName || wizard.goal),
          clarification_answers: wizard.answers,
        });
        patchWizard({ clarifier: report });
        if (report.enriched_intent) setEnrichedIntent(report.enriched_intent);
      } catch (err) {
        setClarifyError(err.message);
        setClarifyLoading(false);
        return;
      } finally {
        setClarifyLoading(false);
      }
    }

    if (stepId === "parts" && wizard.mode === "salvage") {
      const named = wizard.parts.filter((row) => row.name.trim());
      if (named.length === 0) {
        setClarifyError("Add at least one part you have on hand.");
        return;
      }
    }

    if (
      stepId === "design" &&
      wizard.designStrategy === "canvas" &&
      (wizard.selectedModuleIds || []).length < 2
    ) {
      setClarifyError("Pick at least two modules for canvas compose.");
      return;
    }

    if (stepId === "donor" && wizard.mode === "salvage" && !wizard.donorFixtureId) {
      setClarifyError("Pick a donor board profile (or switch to “design from scratch”).");
      return;
    }

    const next = steps[stepIndex + 1];
    if (next) setStepId(next.id);
  };

  const goBack = () => {
    setClarifyError(null);
    const prev = steps[stepIndex - 1];
    if (prev) setStepId(prev.id);
  };

  const handleBuild = () => {
    if (wizard.mode === "greenfield") {
      const payload = buildComposePayloadFromWizard(wizard, { enrichedIntent });
      onBuild(payload, { route: "compose" });
      return;
    }
    const intake = buildIntakeFromWizard(wizard, {
      donorFixtures,
      enrichedIntent,
      visionEnrichedIntake: wizard.visionEnrichedIntake,
    });
    onBuild(intake, { route: "splice" });
  };

  const handleDonorPhoto = (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      patchWizard({
        donorPhoto: { name: file.name, dataUrl: String(reader.result || "") },
        donorVisionReport: null,
      });
      setVisionError(null);
    };
    reader.readAsDataURL(file);
  };

  const runDonorVision = async () => {
    setVisionError(null);
    setVisionLoading(true);
    try {
      const intake = buildIntakeFromWizard(wizard, { donorFixtures, enrichedIntent });
      const result = await donorBoardVision(intake);
      patchWizard({ donorVisionReport: result });
    } catch (err) {
      setVisionError(err.message);
    } finally {
      setVisionLoading(false);
    }
  };

  const runVisionEnrich = async () => {
    setVisionError(null);
    setVisionLoading(true);
    try {
      const intake = buildIntakeFromWizard(wizard, {
        donorFixtures,
        enrichedIntent,
        visionEnrichedIntake: wizard.donorVisionReport?.intake,
      });
      const result = await visionEnrichIntake(intake, {
        apply: true,
        live: Boolean(wizard.visionLive),
      });
      patchWizard({
        visionEnrichedIntake: result.intake,
        visionEnrichReport: result.vision_evidence_report,
      });
    } catch (err) {
      setVisionError(err.message);
    } finally {
      setVisionLoading(false);
    }
  };

  const donorVisionSummary = summarizeDonorVisionReport(wizard.donorVisionReport?.donor_board_vision_report);

  const questions = wizard.clarifier?.questions || [];

  return (
    <div className={`wizard-shell ${embedded ? "wizard-shell--embedded" : ""}`}>
      <div className="wizard-header">
        <div>
          <h2>{embedded ? "Project intake" : "Start a hardware project"}</h2>
          <p className="muted">
            {embedded
              ? "Choose greenfield or salvage. This session stays in memory until you cancel or leave."
              : "Describe what you want — we’ll turn it into a splice plan and carrier board."}
          </p>
        </div>
        <button type="button" className="ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>

      <StepIndicator steps={steps} currentId={stepId} />

      <div className="wizard-body card">
        {stepId === "goal" && (
          <>
            <label className="field-label" htmlFor="goal">
              What do you want to build?
            </label>
            <textarea
              id="goal"
              className="field-textarea"
              rows={5}
              placeholder="Example: I want to splice the motor driver from a dead RC car into a small robot with an ESP32 and a front distance sensor."
              value={wizard.goal}
              onChange={(e) => patchWizard({ goal: e.target.value })}
            />
            <p className="hint">Plain English is fine. We’ll ask a few follow-ups if anything’s unclear.</p>
          </>
        )}

        {stepId === "clarify" && (
          <>
            <h3>Quick questions</h3>
            <p className="muted">These help the engine pick power rails and modules — skip only if you’re unsure.</p>
            {questions.length === 0 && (
              <p className="hint">Your description already has enough detail. Continue when ready.</p>
            )}
            {questions.map((q) => (
              <div key={q.id} className="field-block">
                <label className="field-label" htmlFor={`q-${q.id}`}>
                  {q.prompt}
                </label>
                <input
                  id={`q-${q.id}`}
                  value={wizard.answers[q.id] || ""}
                  onChange={(e) =>
                    patchWizard({
                      answers: { ...wizard.answers, [q.id]: e.target.value },
                    })
                  }
                  placeholder="Your answer"
                />
              </div>
            ))}
          </>
        )}

        {stepId === "mode" && (
          <>
            <h3>Choose your design path</h3>
            <div className="choice-grid">
              <button
                type="button"
                className={`choice-card ${wizard.mode === "greenfield" ? "active" : ""}`}
                onClick={() => patchWizard({ mode: "greenfield", donorFixtureId: "" })}
              >
                <strong>AI carrier design</strong>
                <span>Flux-class — describe a board, AI composes modules → KiCad</span>
              </button>
              <button
                type="button"
                className={`choice-card ${wizard.mode === "salvage" ? "active" : ""}`}
                onClick={() => patchWizard({ mode: "salvage" })}
              >
                <strong>Salvage / splice</strong>
                <span>Donor boards, bench gates, auditable bring-up (HS moat)</span>
              </button>
            </div>
          </>
        )}

        {stepId === "design" && (
          <CanvasComposeStep
            wizard={wizard}
            llmReady={llmComposeReady}
            onChange={(patch) => patchWizard(patch)}
          />
        )}

        {stepId === "parts" && (
          <>
            <h3>What parts do you have?</h3>
            <p className="muted">List salvaged or bin parts — motors, controllers, sensors, donor boards.</p>
            <ul className="parts-editor">
              {wizard.parts.map((row, index) => (
                <li key={index} className="parts-row">
                  <input
                    placeholder="Part name"
                    value={row.name}
                    onChange={(e) => {
                      const parts = [...wizard.parts];
                      parts[index] = { ...parts[index], name: e.target.value };
                      patchWizard({ parts });
                    }}
                  />
                  <select
                    value={row.type}
                    onChange={(e) => {
                      const parts = [...wizard.parts];
                      parts[index] = { ...parts[index], type: e.target.value };
                      patchWizard({ parts });
                    }}
                  >
                    {PART_TYPES.map((type) => (
                      <option key={type.id} value={type.id}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                  <input
                    placeholder="Notes (harness label, condition…)"
                    value={row.notes}
                    onChange={(e) => {
                      const parts = [...wizard.parts];
                      parts[index] = { ...parts[index], notes: e.target.value };
                      patchWizard({ parts });
                    }}
                  />
                  <button
                    type="button"
                    className="ghost small"
                    disabled={wizard.parts.length <= 1}
                    onClick={() => patchWizard({ parts: wizard.parts.filter((_, i) => i !== index) })}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="ghost"
              onClick={() => patchWizard({ parts: [...wizard.parts, defaultPart()] })}
            >
              + Add part
            </button>
          </>
        )}

        {stepId === "donor" && (
          <>
            <h3>Donor board + AI vision</h3>
            <p className="muted">
              Pick a donor profile, then optionally upload a board photo. AI extracts candidate reusable blocks and
              measurement gates — merged with fixture salvage when configured.
            </p>
            <div className="fixture-grid">
              {donorFixtures.map((fixture) => (
                <button
                  key={fixture.id}
                  type="button"
                  className={`fixture-card ${wizard.donorFixtureId === fixture.id ? "active" : ""}`}
                  onClick={() => patchWizard({ donorFixtureId: fixture.id, donorVisionReport: null })}
                >
                  <strong>{fixture.label}</strong>
                  <span>{fixture.headline || fixture.board_id}</span>
                  {fixture.suggested_uses?.length > 0 && (
                    <span className="fixture-tags">{fixture.suggested_uses.join(" · ")}</span>
                  )}
                </button>
              ))}
              {donorFixtures.length === 0 && (
                <p className="muted">No donor fixtures loaded from API.</p>
              )}
            </div>

            <div className="ai-upload-block">
              <label className="field-label" htmlFor="donor-photo">
                Donor board photo (optional)
              </label>
              <input
                id="donor-photo"
                type="file"
                accept="image/*"
                onChange={(e) => handleDonorPhoto(e.target.files?.[0])}
              />
              {wizard.donorPhoto?.dataUrl && (
                <div className="ai-photo-preview">
                  <img src={wizard.donorPhoto.dataUrl} alt="Donor board preview" />
                  <span className="muted small">{wizard.donorPhoto.name}</span>
                </div>
              )}
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={wizard.visionLive}
                  disabled={!qwenLiveReady}
                  onChange={(e) => patchWizard({ visionLive: e.target.checked })}
                />
                <span>
                  Run live Qwen vision {qwenLiveReady ? "" : "(configure API key to enable)"}
                </span>
              </label>
              <div className="ai-action-row">
                <button
                  type="button"
                  className="secondary"
                  disabled={visionLoading || (!wizard.donorFixtureId && !wizard.donorPhoto)}
                  onClick={runDonorVision}
                >
                  {visionLoading ? "Analyzing…" : "Analyze donor board with AI"}
                </button>
              </div>
              {donorVisionSummary.headline && wizard.donorVisionReport && (
                <div className="ai-inline-report">
                  <strong>{donorVisionSummary.headline}</strong>
                  {donorVisionSummary.blocks.length > 0 && (
                    <ul className="clean-list">
                      {donorVisionSummary.blocks.slice(0, 4).map((row) => (
                        <li key={row.block_id || row.name}>{row.name || row.block_id}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          </>
        )}

        {stepId === "power" && (
          <>
            <h3>Power & runtime</h3>
            <div className="field-grid">
              <div className="field-block">
                <label className="field-label" htmlFor="battery-v">
                  Battery voltage (V)
                </label>
                <input
                  id="battery-v"
                  type="number"
                  step="0.1"
                  value={wizard.batteryVoltage}
                  onChange={(e) => patchWizard({ batteryVoltage: e.target.value })}
                />
              </div>
              <div className="field-block">
                <label className="field-label" htmlFor="runtime">
                  Target runtime (minutes)
                </label>
                <input
                  id="runtime"
                  type="number"
                  value={wizard.runtimeMin}
                  onChange={(e) => patchWizard({ runtimeMin: e.target.value })}
                />
              </div>
              <div className="field-block">
                <label className="field-label" htmlFor="mass">
                  Approx. mass (kg, optional)
                </label>
                <input
                  id="mass"
                  type="number"
                  step="0.1"
                  value={wizard.massKg}
                  onChange={(e) => patchWizard({ massKg: e.target.value })}
                />
              </div>
            </div>
          </>
        )}

        {stepId === "review" && (
          <>
            <h3>Review & build</h3>
            <dl className="review-list">
              <div>
                <dt>Project</dt>
                <dd>{wizard.goal}</dd>
              </div>
              <div>
                <dt>Mode</dt>
                <dd>
                  {wizard.mode === "salvage"
                    ? "Salvage / splice"
                    : `AI design (${wizard.designStrategy === "canvas" ? "module canvas" : wizard.designStrategy === "heuristic" ? "heuristic" : "LLM-first"})`}
                </dd>
              </div>
              <div>
                <dt>Parts</dt>
                <dd>{wizard.parts.filter((p) => p.name.trim()).map((p) => p.name).join(", ") || "—"}</dd>
              </div>
              {wizard.mode === "salvage" && (
                <div>
                  <dt>Donor fixture</dt>
                  <dd>
                    {donorFixtures.find((f) => f.id === wizard.donorFixtureId)?.label || "—"}
                    {wizard.donorPhoto?.name ? ` · photo: ${wizard.donorPhoto.name}` : ""}
                  </dd>
                </div>
              )}
              <div>
                <dt>Power</dt>
                <dd>
                  {wizard.batteryVoltage} V · {wizard.runtimeMin} min runtime
                </dd>
              </div>
              {wizard.donorVisionReport && (
                <div>
                  <dt>AI donor vision</dt>
                  <dd>{donorVisionSummary.headline}</dd>
                </div>
              )}
            </dl>

            {wizard.mode === "greenfield" ? (
              <p className="hint">
                Build runs AI compose → KiCad compile → full PROJECT_PACKAGE with design verify, BOM, and bench
                session — same results shell as salvage builds.
              </p>
            ) : (
              <div className="ai-review-actions card nested">
              <h4>AI prep before compile</h4>
              <p className="muted small">
                Run intake vision enrichment to merge photo evidence, extracted notes, and clarifier output into the
                splice plan.
              </p>
              <button
                type="button"
                className="secondary"
                disabled={visionLoading || building}
                onClick={runVisionEnrich}
              >
                {visionLoading ? "Running vision prep…" : "Run AI vision prep"}
              </button>
              {wizard.visionEnrichReport && (
                <p className="hint small">
                  Vision enrichment staged — {(wizard.visionEnrichReport.applied_notes || []).length || "indexed"}{" "}
                  evidence notes ready for build.
                </p>
              )}
            </div>
            )}

            {building && (
              <div className="build-progress">
                <div className="spinner" aria-hidden />
                <p>{stageLabel || "Building your project…"}</p>
                <p className="muted small">KiCad compile usually takes 30–90 seconds.</p>
              </div>
            )}
            {buildError && <p className="error">{buildError}</p>}
          </>
        )}

        {(clarifyError || visionError) && <p className="error">{clarifyError || visionError}</p>}
      </div>

      <div className="wizard-footer">
        {stepIndex > 0 && (
          <button type="button" className="ghost" onClick={goBack} disabled={building || clarifyLoading}>
            Back
          </button>
        )}
        <div className="wizard-footer-spacer" />
        {stepId !== "review" ? (
          <button
            type="button"
            className="primary"
            onClick={goNext}
            disabled={building || clarifyLoading || visionLoading}
          >
            {clarifyLoading ? "Checking…" : visionLoading ? "AI running…" : "Continue"}
          </button>
        ) : (
          <button
            type="button"
            className="primary"
            onClick={handleBuild}
            disabled={building}
          >
            {building ? "Building…" : "Build my project"}
          </button>
        )}
      </div>
    </div>
  );
}
