import { MODULE_CATALOG } from "../moduleCatalog.js";

export default function CanvasComposeStep({ wizard, llmReady, onChange }) {
  const selected = new Set(wizard.selectedModuleIds || []);

  const toggleModule = (moduleId) => {
    const next = new Set(selected);
    if (next.has(moduleId)) next.delete(moduleId);
    else next.add(moduleId);
    onChange({ selectedModuleIds: [...next] });
  };

  return (
    <div className="design-studio-step">
      <h3>AI design studio</h3>
      <p className="muted">
        Flux-class path: describe the board and let Qwen pick modules, or choose modules manually and auto-wire through
        the same compose spine.
      </p>

      <div className="choice-grid">
        <button
          type="button"
          className={`choice-card ${wizard.designStrategy === "llm" ? "active" : ""}`}
          onClick={() => onChange({ designStrategy: "llm" })}
        >
          <strong>AI-first compose</strong>
          <span>Natural language → module graph → KiCad (recommended)</span>
        </button>
        <button
          type="button"
          className={`choice-card ${wizard.designStrategy === "canvas" ? "active" : ""}`}
          onClick={() => onChange({ designStrategy: "canvas" })}
        >
          <strong>Module canvas</strong>
          <span>Pick modules — engine auto-wires and compiles</span>
        </button>
        <button
          type="button"
          className={`choice-card ${wizard.designStrategy === "heuristic" ? "active" : ""}`}
          onClick={() => onChange({ designStrategy: "heuristic" })}
        >
          <strong>Offline heuristic</strong>
          <span>Regex module picker only — no LLM</span>
        </button>
      </div>

      {wizard.designStrategy === "llm" && (
        <p className="hint">
          {llmReady
            ? "Qwen LLM-first compose is ready — your goal sentence drives module selection and DRC-checked compile."
            : "LLM keys not configured — build will fall back to heuristic scratch compose unless you configure Qwen."}
        </p>
      )}

      {wizard.designStrategy === "canvas" && (
        <>
          <p className="muted small">Select at least two modules. The engine wires and compiles to KiCad.</p>
          <div className="module-pick-grid">
            {MODULE_CATALOG.map((row) => (
              <button
                key={row.id}
                type="button"
                className={`fixture-card compact ${selected.has(row.id) ? "active" : ""}`}
                onClick={() => toggleModule(row.id)}
              >
                <strong>{row.label}</strong>
                <span className="mono small">{row.id}</span>
                <span className="chip small">{row.category}</span>
              </button>
            ))}
          </div>
          <p className="hint small">{selected.size} module(s) selected</p>
        </>
      )}
    </div>
  );
}
