const STEPS = [
  { n: "01", title: "Describe", body: "Goal, parts, donor board" },
  { n: "02", title: "Compile", body: "KiCad carrier + DRC" },
  { n: "03", title: "Verify", body: "Preview, BOM, fab readiness" },
  { n: "04", title: "Package", body: "Wiring, steps, zip" },
  { n: "05", title: "Gates", body: "Measure before power-on" },
];

export default function PipelineVisual() {
  return (
    <div className="pipeline-visual" aria-hidden>
      {STEPS.map((step, index) => (
        <div key={step.n} className="pipeline-step">
          <span className="pipeline-num">{step.n}</span>
          <div>
            <strong>{step.title}</strong>
            <span>{step.body}</span>
          </div>
          {index < STEPS.length - 1 && <span className="pipeline-arrow">→</span>}
        </div>
      ))}
    </div>
  );
}
