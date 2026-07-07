const STEPS = [
  { id: "visual", label: "Visual", hint: "KiCanvas preview" },
  { id: "truth", label: "Truth", hint: "DRC / quality" },
  { id: "readiness", label: "Readiness", hint: "BOM + fab" },
  { id: "exports", label: "Exports", hint: "Handoff" },
];

export default function DesignFlowStepper({ active = "visual" }) {
  const activeIndex = STEPS.findIndex((step) => step.id === active);

  return (
    <nav className="design-flow-stepper" aria-label="Design verification flow">
      {STEPS.map((step, index) => {
        const state = index < activeIndex ? "done" : index === activeIndex ? "current" : "upcoming";
        return (
          <div key={step.id} className={`design-flow-step design-flow-step-${state}`}>
            <span className="design-flow-num">{index + 1}</span>
            <div>
              <strong>{step.label}</strong>
              <span className="muted small">{step.hint}</span>
            </div>
            {index < STEPS.length - 1 && <span className="design-flow-arrow" aria-hidden>→</span>}
          </div>
        );
      })}
    </nav>
  );
}
