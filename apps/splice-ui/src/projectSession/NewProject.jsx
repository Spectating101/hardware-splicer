import { useState } from "react";
import ProjectWizard from "../components/ProjectWizard.jsx";
import DigitalStudyLibrary from "./DigitalStudyLibrary.jsx";

const ENTRIES = [
  ["goal", "Start from a goal", "Describe what it should do; the intake asks for the rest."],
  ["parts", "Start from parts you have", "List the units you own, salvaged or bought, and what is known about them."],
  ["reference", "Start from a reference study", "Open a registered design with saved geometry and simulation."],
];

export default function NewProject({ online, busy, onStartStudy, onComplete, onCancel, initialEntry = "goal", ...wizardProps }) {
  const [entry, setEntry] = useState(initialEntry);
  const [units, setUnits] = useState([{ unit_id: "unit-1", name: "", source: "owned", known_facts: "" }]);
  const [goal, setGoal] = useState("");
  const [nextId, setNextId] = useState(2);
  function update(index, field, value) {
    setUnits((rows) => rows.map((row, i) => i === index ? { ...row, [field]: value } : row));
  }
  function submitParts(event) {
    event.preventDefault();
    if (units.some((row) => !row.name.trim())) return;
    onComplete({ intake: { goal: goal.trim(), project_name: goal.trim() || "Parts project", mode: "greenfield",
      owned_units: units.map((row) => ({ ...row, name: row.name.trim() })) } });
  }
  return <div className="new-project" data-testid="new-project">
    <header className="projects-heading"><h1>New project</h1><button className="ghost" onClick={onCancel}>Cancel</button></header>
    <p className="muted">Not saved yet. Submit an intake or start a reference study to create a project.</p>
    <ul className="project-entry-list" aria-label="Project starting points">
      {ENTRIES.map(([id, label, detail]) =>
        <li key={id}><button type="button" className="project-entry" aria-label={label} aria-pressed={entry === id} aria-describedby={`entry-${id}-detail`}
          onClick={() => setEntry(id)}>
          <span className="project-entry-mark" aria-hidden="true" />
          <span className="project-entry-label">{label}</span>
          <span className="project-entry-detail" id={`entry-${id}-detail`}>{detail}</span>
        </button></li>)}
    </ul>
    {entry === "goal" && <div data-testid="stage-intake"><ProjectWizard {...wizardProps} embedded initialMode="greenfield"
      onCancel={onCancel} onCompleteIntake={onComplete} /></div>}
    {entry === "parts" && <form className="owned-unit-editor" onSubmit={submitParts}>
      <h2>Owned units</h2>
      <p>Each row is one specific owned unit. A catalogue part describes a model; it does not mean you own a unit.</p>
      <p className="muted">Unit origins and known facts will be saved with the project intake.</p>
      {units.map((row, index) => <fieldset key={row.unit_id}>
        <legend>Owned unit {index + 1}</legend>
        <label>Name<input required value={row.name} onChange={(e) => update(index, "name", e.target.value)} /></label>
        <label>Source<select value={row.source} onChange={(e) => update(index, "source", e.target.value)}>
          <option value="owned">owned</option><option value="salvaged">salvaged</option><option value="bought">bought</option>
        </select></label>
        <label>Known facts<textarea value={row.known_facts} placeholder="Unknown facts can stay empty" onChange={(e) => update(index, "known_facts", e.target.value)} /></label>
        <p>Catalogue part: unknown · Knowledge state: unknown · Geometry: not linked</p>
        <button type="button" className="ghost" disabled={units.length === 1} onClick={() => setUnits(units.filter((_, i) => i !== index))}>Remove unit {index + 1}</button>
      </fieldset>)}
      <button type="button" className="secondary" onClick={() => {
        setUnits([...units, { unit_id: `unit-${nextId}`, name: "", source: "owned", known_facts: "" }]); setNextId(nextId + 1);
      }}>Add owned unit</button>
      <label>Goal or requirements (optional)<textarea value={goal} onChange={(e) => setGoal(e.target.value)} /></label>
      <button className="primary" type="submit" disabled={!online}>Create project from parts</button>
    </form>}
    {entry === "reference" && <DigitalStudyLibrary online={online} busy={busy} onStart={onStartStudy} />}
  </div>;
}
