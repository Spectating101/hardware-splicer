import { useEffect, useState } from "react";
import { fetchDigitalCases } from "./digitalStudyApi.js";
import { ReferenceDisplayComparison } from "./FieldDeckDisplayComparison.jsx";
import { fieldLabel } from "./digitalStudyLabels.js";
import "./digitalStudy.css";

import droneRender from "../../../../examples/drone_proving_ground/digital/reference/ASSEMBLY.png";
import deckRender from "../../../../projects/cyberdeck-real-trial-20261020/digital_v1/views/assembled.png";
import plotterRender from "../../../../projects/ender3-penplotter-digital/exports/device_render.png";

const previews = {
  "hs3g-b": [droneRender, "HS-3G-B reference assembly"],
  "fielddeck-7": [deckRender, "FieldDeck 7 enclosure and controls"],
  "fielddeck-5": [deckRender, "FieldDeck 7 donor enclosure for the 5-inch display swap"],
  "ender3-penplotter": [plotterRender, "Ender-3 pen plotter assembly"],
};

const titles = {
  "hs3g-b": "HS-3G-B drone",
  "fielddeck-7": "FieldDeck 7 cyberdeck",
  "fielddeck-5": "FieldDeck 5 display swap",
  "ender3-penplotter": "Ender-3 pen plotter",
};

export default function DigitalStudyLibrary({ online, onStart, busy }) {
  const [cases, setCases] = useState(null);
  const [selection, setSelection] = useState("");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!online) return;
    const controller = new AbortController();
    setError("");
    fetchDigitalCases(controller.signal).then((result) => {
      if (controller.signal.aborted) return;
      const available = result.cases.filter((item) => item.source_inputs_available);
      setCases(result.cases);
      setSelection(available.find((item) => item.case_id === result.default_case_id)?.case_id || available[0]?.case_id || "");
    }).catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [online, attempt]);

  async function start() {
    setError("");
    try { await onStart(selection); }
    catch (cause) { setError(cause.message); }
  }
  const selected = cases?.find((item) => item.case_id === selection);
  const preview = selected && previews[selected.case_id];
  const comparingDisplays = online && ["fielddeck-7", "fielddeck-5"].includes(selection);
  function choose(id) {
    setSelection(id);
    setError("");
  }
  return <section className="home-hero card study-library">
    <p className="eyebrow">Digital workshop</p>
    <h1>Choose a design to study</h1>
    <p className="muted">Open a working design, change a requirement, and compare what happens.</p>
    <div className="study-choice"><div>
    {online && cases ? <fieldset disabled={busy}>
      <legend>Available designs</legend>
      <div className="study-options">{cases.map((item) => <label key={item.case_id} className={item.case_id === selection ? "selected" : ""}>
        <input type="radio" name="study" value={item.case_id} checked={item.case_id === selection}
          disabled={!item.source_inputs_available} onChange={() => choose(item.case_id)} />
        <span>{titles[item.case_id] || item.name}<small>{item.source_inputs_available
          ? `${Object.keys(item.requirements).length} adjustable requirements` : "Source files unavailable"}</small></span>
      </label>)}</div>
    </fieldset> : online && !error ? <p role="status">Loading designs…</p> : null}
    {online && cases?.length === 0 && <p>No designs are registered.</p>}
    {!online && <p>Connect to the engineering backend to open a design.</p>}
    {selected && online && <p className="study-fields"><strong>Adjustable requirements</strong><br/>
      {Object.keys(selected.requirements).map(fieldLabel).join(" · ")}</p>}
    </div>
    {online && preview && <figure className="study-preview">
      <img src={preview[0]} alt={preview[1]} />
      <figcaption>{preview[1]}</figcaption>
    </figure>}
    </div>
    {comparingDisplays && <ReferenceDisplayComparison cases={cases} selection={selection} onSelect={choose} busy={busy} />}
    <div className="study-start">
      {error && <p role="alert" className="digital-error">{error}</p>}
      {online && error && !cases && <button onClick={() => setAttempt((n) => n + 1)}>Reload designs</button>}
      <button type="button" className="primary large" disabled={!online || !selected || busy} onClick={start}>
        {busy ? "Opening digital project…" : "Start digital design"}</button>
    </div>
  </section>;
}
