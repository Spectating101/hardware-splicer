/**
 * Documented Wokwi diagram.json (v1) -> source-preserving Hardware Splicer proposal.
 *
 * Both software suites support virtual circuit designs. This parser does NOT
 * imply part footprint/power compatibility, simulation success or physical
 * proof. Every unrecognized component and pin is retained, never removed.
 *
 * https://docs.wokwi.com/diagram-format
 */
const MAX_PARTS = 3000;
const MAX_CONNECTIONS = 20000;

// Conservative functional-family mappings: these are NOT exact physical BOM MPNs.
const PARTS = Object.freeze({
  "wokwi-esp32-devkit-v1": { moduleId: "esp32-devkit", family: "ESP32 DevKit family (variant not verified)" },
  "board-esp32-devkit-c-v4": { moduleId: "esp32-devkit", family: "ESP32 DevKit family (variant not verified)" },
  "wokwi-arduino-nano": { moduleId: "arduino-nano", family: "Arduino Nano family (variant not verified)" },
  "wokwi-dht22": { moduleId: "dht22", family: "DHT22 model (physical part unverified)" },
  "board-ssd1306": { moduleId: "ssd1306-128x64", family: "SSD1306 display (board variant not verified)" },
  "wokwi-hc-sr04": { moduleId: "hc-sr04", family: "HC-SR04 model (physical part unverified)" },
  "wokwi-servo": { moduleId: "sg90", family: "Generic virtual servo; NOT asserted SG90 physical identity" },
});
const SUPPORTED_FIXED = {
  "wokwi-dht22": new Set(["VCC","GND","SDA","NC"]),
  "board-ssd1306": new Set(["VCC","GND","SDA","SCL"]),
  "wokwi-hc-sr04": new Set(["VCC","GND","TRIG","ECHO"]),
  "wokwi-servo": new Set(["V+","GND","PWM"]),
};

function normalizePin(type, raw) {
  const pin = String(raw);
  if (!pin || pin.length > 80) return null;
  if (type === "wokwi-dht22") return { "SDA": "DATA", "VCC": "VCC", "GND": "GND" }[pin] || null;
  if (type === "board-ssd1306") return ["VCC","GND","SDA","SCL"].includes(pin) ? pin : null;
  if (type === "wokwi-hc-sr04") return ["VCC","GND","TRIG","ECHO"].includes(pin) ? pin : null;
  if (type === "wokwi-servo") return { "V+": "VCC", "GND": "GND", "PWM": "SIG" }[pin] || null;
  if (type === "wokwi-arduino-nano") {
    if (pin === "GND" || /^GND\.\d+$/.test(pin)) return "GND";
    if (pin === "5V" || pin === "3V3" || pin === "VIN") return pin;
    if (/^D[23]$/.test(pin)) return pin;
    if (["A0","A4","A5"].includes(pin)) return pin;
    return null; // HS's nano footprint declares only these pins
  }
  if (type === "wokwi-esp32-devkit-v1" || type === "board-esp32-devkit-c-v4") {
    if (pin === "GND" || /^GND\.\d+$/.test(pin)) return "GND";
    if (pin === "3V3" || pin === "VIN") return pin;
    const m = /^(?:GPIO|D)(2|4|5|15|16|17|18|21|22|23|34)$/.exec(pin);
    return m ? `GPIO${m[1]}` : null; // no unsupported pad aliases
  }
  return null;
}

const endpoint = (value, index, partsById) => {
  if (typeof value !== "string" || !value.includes(":")) {
    throw new Error(`Wokwi connection ${index + 1} needs partId:pin endpoints.`);
  }
  const i = value.indexOf(":");
  const partId = value.slice(0,i);
  const pin = value.slice(i+1);
  if (!partId || !pin || !partsById.has(partId)) {
    throw new Error(`Wokwi connection ${index + 1} refers to an unknown part or missing pin.`);
  }
  const part = partsById.get(partId);
  return {
    source_endpoint: value, source_part_id: partId, source_pin: pin,
    hs_pin_candidate: normalizePin(part.type, pin),
  };
};

export function isWokwiDiagramObject(raw) {
  return Boolean(raw && typeof raw === "object" && !Array.isArray(raw)
    && raw.version === 1 && Array.isArray(raw.parts) && Array.isArray(raw.connections));
}

export function parseWokwiDiagramArtifact(text) {
  let doc;
  try { doc = JSON.parse(text); } catch { throw new Error("Invalid Wokwi diagram.json syntax."); }
  if (!isWokwiDiagramObject(doc)) {
    throw new Error("Not a Wokwi diagram.json v1 with parts and connections.");
  }
  if (doc.parts.length === 0 || doc.parts.length > MAX_PARTS || doc.connections.length > MAX_CONNECTIONS) {
    throw new Error("Wokwi diagram exceeds limits or contains no parts.");
  }
  const source = new Map();
  const nodes = [];
  for (const [i, part] of doc.parts.entries()) {
    if (!part || typeof part.id !== "string" || !part.id ||
        typeof part.type !== "string" || !part.type || part.id.length > 120) {
      throw new Error(`Wokwi part ${i+1} needs a unique ID and type.`);
    }
    if (source.has(part.id)) throw new Error(`Duplicate Wokwi part ID ${part.id}.`);
    source.set(part.id, part);
    const match = PARTS[part.type];
    nodes.push({
      source_part_id: part.id, source_type: part.type,
      hs_module_candidate: match?.moduleId ?? null,
      match_authority: match ? "functional_family_only" : "unmapped",
      matching_note: match?.family || "No corresponding HS module proven",
      source_attributes: part.attrs && typeof part.attrs === "object" && !Array.isArray(part.attrs) ? part.attrs : {},
    });
  }
  const connections = doc.connections.map((row,i) => {
    if (!Array.isArray(row) || row.length < 2 || row.length > 4) {
      throw new Error(`Wokwi connection ${i+1} must contain two endpoint fields.`);
    }
    const from = endpoint(row[0],i,source);
    const to = endpoint(row[1],i,source);
    return {
      id: `wokwi-wire-${i+1}`,
      from, to,
      mapping_complete: Boolean(from.hs_pin_candidate && to.hs_pin_candidate
        && PARTS[source.get(from.source_part_id).type]
        && PARTS[source.get(to.source_part_id).type]),
      original_wire_color: typeof row[2] === "string" ? row[2] : null,
    };
  });
  const mapped = nodes.filter(n=>n.hs_module_candidate);
  const mappedConnections = connections.filter(w=>w.mapping_complete);
  const unresolved = nodes.filter(n=>!n.hs_module_candidate).map(n=>n.source_part_id);
  const unresolvedPins = connections.filter(w=>!w.mapping_complete)
    .map(w=>({ wire: w.id, from: w.from.source_endpoint, to: w.to.source_endpoint }));
  return {
    provider: "wokwi",
    schema_version: "wokwi-diagram-v1",
    authority: "external_simulation_proposal",
    original_part_count: nodes.length,
    original_connection_count: connections.length,
    mapped_part_count: mapped.length,
    mapped_connection_count: mappedConnections.length,
    unmapped_part_ids: unresolved,
    unmapped_connections: unresolvedPins,
    status: unresolved.length || unresolvedPins.length ? "partial_mapping" : "family_mapping_only",
    nodes, connections,
    // This is a normalized source proposal, NOT a compilable HS graph or a simulated circuit.
    original_editor: typeof doc.editor === "string" ? doc.editor : "unknown",
    note: "Wokwi simulation is not a physical component, MCU variant, electrical rail, or bench verification. No part was dropped.",
  };
}

export function compareWokwiCandidateToHsBom(proposal, bomLines) {
  if (!Array.isArray(bomLines) || bomLines.length === 0) {
    return {status:"unavailable", missing:[], excess:[], matches:[], note:"No compiled HS BOM for comparison."};
  }
  const counts = (proposal.nodes || []).reduce((acc,node)=>{
    if(node.hs_module_candidate)acc[node.hs_module_candidate]=(acc[node.hs_module_candidate]||0)+1;
    return acc;
  },{});
  const hs = {};
  for (const row of bomLines) {
    const mid = String(row?.module_id || "");
    if (mid) hs[mid] = (hs[mid] || 0) + Number(row?.qty ?? row?.quantity ?? 1);
  }
  const missing=[],excess=[],matches=[];
  for (const id of new Set([...Object.keys(counts),...Object.keys(hs)])){
    const a=counts[id]||0, b=hs[id]||0;
    if(a<b)missing.push({module:id,wokwi:a,hs:b});
    else if(a>b)excess.push({module:id,wokwi:a,hs:b});
    else matches.push({module:id,count:a});
  }
  return {
    status: missing.length || excess.length || proposal.unmapped_part_ids.length
      ? "review_required" : "family_quantity_parity",
    missing, excess, matches, unmapped: proposal.unmapped_part_ids,
    note:"Family-level quantity comparison. Physical donor identity, power, wiring and unmodelled peripherals still require review.",
  };
}
