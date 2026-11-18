import { useEffect, useState } from "react";
import reference from "../../../../docs/status/generated/fielddeck-display-swap-20261118.json";
import { digitalArtifactUrl } from "./digitalStudyApi.js";

const referenceUrl = `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(reference, null, 2))}`;

const scenarios = {
  work_published_panel_power: "Ordinary work",
  stress_design_allocation: "Stress load",
  high_keyboard_demand: "High keyboard demand",
};

function range(values, unit) {
  return `${values.map((value) => value.toFixed(2)).join("–")} ${unit}`;
}

function Comparison({ evidence, source, reportUrl, reportLabel, choices }) {
  const [scenarioId, setScenarioId] = useState("work_published_panel_power");
  const { power, geometry, connections } = evidence;
  const scenario = power.scenarios.find((row) => row.scenario === scenarioId) ?? power.scenarios[0];
  const panels = [scenario.original_7inch, scenario.variant_5inch];
  const printedParts = geometry.exports.exported_parts;
  const displays = [
    { id: "fielddeck-7", label: "7-inch", part: reference.sources.baseline.selected_part },
    { id: "fielddeck-5", label: "5-inch", part: reference.compatible_reference.part },
  ];
  return <section className="display-comparison" aria-label="FieldDeck display comparison">
    <header>
      <div><h2>Compare FieldDeck displays</h2><p>{source}</p></div>
      <label>Power scenario
        <select value={scenario.scenario} onChange={(event) => setScenarioId(event.target.value)}>
          {power.scenarios.map((row) => <option key={row.scenario} value={row.scenario}>
            {scenarios[row.scenario] ?? row.scenario}
          </option>)}
        </select>
      </label>
    </header>
    <div className="display-table-wrap"><table>
      <caption>Calculated with {range(power.usable_energy_wh, "Wh")} of usable battery energy</caption>
      <thead><tr><th scope="col">Measure</th>
        {displays.map(({ id, label, part }) => <th key={id} scope="col">
          {choices ? <button type="button" aria-pressed={choices.selection === id}
            disabled={choices.busy || !choices.cases.some((item) => item.case_id === id && item.source_inputs_available)}
            onClick={() => choices.onSelect(id)}>{label}</button> : label}
          <small>{part}</small>
        </th>)}
      </tr></thead>
      <tbody>
        <tr><th scope="row">Battery runtime</th>{panels.map((panel, i) => <td key={i}>{range(panel.runtime_h, "h")}</td>)}</tr>
        <tr><th scope="row">Display power</th>{panels.map((panel, i) => <td key={i}>{panel.display_w.toFixed(2)} W</td>)}</tr>
        <tr><th scope="row">System power</th>{panels.map((panel, i) => <td key={i}>{panel.system_w.toFixed(2)} W</td>)}</tr>
        <tr><th scope="row">Supply margin</th>{panels.map((panel, i) => <td key={i}>{panel.source_margin_a.toFixed(2)} A</td>)}</tr>
      </tbody>
    </table></div>
    <details><summary>What changes with the 5-inch display?</summary>
      <h3>Enclosure parts to make</h3>
      <ul>{printedParts.map((item) => <li key={item.part}>{item.quantity} × {item.part.replaceAll("_", " ").replace(/ 1$/, "")}</li>)}</ul>
      <h3>Retained connection</h3>
      <ul>{connections.display.filter((item) => item.retained_part).map((item) =>
        <li key={item.from}>{item.retained_part} · {item.path}</li>)}</ul>
      <h3>Open checks</h3>
      <ul>{connections.display.map((item) => <li key={item.from}>{item.open_item}</li>)}</ul>
    </details>
    <a href={reportUrl} download={choices ? "fielddeck-display-comparison.json" : "power.json"}>{reportLabel}</a>
  </section>;
}

export function ReferenceDisplayComparison(choices) {
  return <Comparison evidence={reference} choices={choices} reportUrl={referenceUrl} reportLabel="Download reference calculations"
    source={`Reference designs · ${reference.date} · simulated`} />;
}

export function SavedDisplayComparison({ study }) {
  const [evidence, setEvidence] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const { artifacts } = study;
  const power = artifacts["revision/power.json"];
  const geometry = artifacts["revision/geometry.json"];
  const connections = artifacts["revision/connections.json"];
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      const entries = await Promise.all(Object.entries({ power, geometry, connections }).map(async ([key, path]) => {
        if (!path) throw new Error(`This revision has no ${key} report.`);
        const response = await fetch(digitalArtifactUrl(path), { signal: controller.signal });
        if (!response.ok) throw new Error(`Could not open the ${key} report (HTTP ${response.status}).`);
        return [key, await response.json()];
      }));
      const reports = Object.fromEntries(entries);
      if (!reports.power.scenarios?.length || !Array.isArray(reports.geometry.exports?.exported_parts)
          || !Array.isArray(reports.connections.display)) {
        throw new Error("The saved reports are missing comparison data.");
      }
      if (!controller.signal.aborted) setEvidence(reports);
    }
    load().catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [power, geometry, connections, attempt]);

  if (error) return <div><p role="alert">{error}</p><button type="button" onClick={() => {
    setError(""); setAttempt((value) => value + 1);
  }}>Retry comparison</button></div>;
  if (!evidence) return <p role="status">Opening this revision’s display comparison…</p>;
  return <Comparison evidence={evidence} source={`Saved revision ${study.revision} · simulated`} reportUrl={digitalArtifactUrl(power)}
    reportLabel="Download this revision’s power calculations" />;
}
