/**
 * Source-preserving review intake for artifacts produced by external design tools.
 * This module never writes into a canonical HS project or confers engineering truth.
 */
const MAX_TEXT_BYTES = 4 * 1024 * 1024;
const MAX_DOCUMENTS = 10000;

export function classifyExternalArtifact(name) {
  const lower = String(name || "").toLowerCase();
  if (/\.json$/.test(lower)) return "circuit-json";
  if (/\.(net|xml)$/.test(lower)) return "kicad-netlist";
  if (/\.csv$/.test(lower)) return "bom-csv";
  if (/\.(stl|step|stp)$/.test(lower)) return "mechanical-reference";
  if (/\.(ino|cpp|h|hpp)$/.test(lower)) return "firmware-reference";
  return "unsupported";
}

export function parseCircuitJsonArtifact(text) {
  if (typeof text !== "string" || text.length > MAX_TEXT_BYTES) {
    throw new Error("Circuit JSON file is empty or exceeds the 4 MB review limit.");
  }
  let raw;
  try { raw = JSON.parse(text); }
  catch { throw new Error("Invalid Circuit JSON: JSON syntax could not be parsed."); }
  const docs = Array.isArray(raw) ? raw : raw?.documents ?? raw?.circuit_json;
  if (!Array.isArray(docs) || docs.length < 1 || docs.length > MAX_DOCUMENTS) {
    throw new Error("Circuit JSON must contain 1–10,000 documents (array, documents or circuit_json).");
  }
  if (docs.some((item) => !item || typeof item !== "object" || Array.isArray(item) || typeof item.type !== "string")) {
    throw new Error("Circuit JSON documents require a string type and object structure.");
  }
  return docs;
}

export function parseBomCsvArtifact(text) {
  if (typeof text !== "string" || !text.trim() || text.length > MAX_TEXT_BYTES) {
    throw new Error("BOM CSV is empty or exceeds the 4 MB review limit.");
  }
  // RFC 4180: preserve quoted commas, newlines and doubled quotes.
  const rows = [];
  let fields = [], cell = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '"') {
      if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
      else if (quoted || cell.length === 0) quoted = !quoted;
      else throw new Error("BOM CSV has an unexpected quote.");
    } else if (char === "," && !quoted) {
      fields.push(cell); cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      fields.push(cell); cell = "";
      if (fields.some((part) => part.trim())) rows.push(fields);
      fields = [];
      if (char === "\r" && text[i + 1] === "\n") i++;
    } else {
      cell += char;
    }
    if (rows.length > 5001) throw new Error("BOM CSV exceeds the 5,000-row review limit.");
  }
  if (quoted) throw new Error("BOM CSV has an unterminated quoted field.");
  if (cell || fields.length) {
    fields.push(cell);
    if (fields.some((part) => part.trim())) rows.push(fields);
  }
  if (rows.length < 2) throw new Error("BOM CSV requires headers and at least one part.");
  const columns = rows.shift().map((x) => x.trim());
  const qtyIdx = columns.findIndex((x) => /^(qty|quantity|count)$/i.test(x));
  const partIdx = columns.findIndex((x) => /^(name|part|component|description|value|part name|manufacturer part number|mpn)$/i.test(x));
  if (qtyIdx < 0 || partIdx < 0) {
    throw new Error("BOM CSV needs a quantity column and a part/name/description column.");
  }
  const parts = [];
  for (const [index, row] of rows.entries()) {
    if (row.length !== columns.length) throw new Error(`BOM CSV row ${index + 2} has incorrect column count.`);
    // Some generators add a final summary row: it is not an extra physical part.
    if (row[0]?.trim().toUpperCase() === "TOTAL" && row[qtyIdx]?.trim() === "") continue;
    const qty = Number(row[qtyIdx]?.trim());
    const name = row[partIdx]?.trim() || "";
    if (!name || !Number.isSafeInteger(qty) || qty < 1) {
      throw new Error(`BOM CSV row ${index + 2} has a missing name or invalid quantity.`);
    }
    parts.push({ name, quantity: qty, raw: Object.fromEntries(columns.map((col, j) => [col, row[j]])) });
  }
  return { columns, parts, itemCount: parts.reduce((sum, p) => sum + p.quantity, 0) };
}

export function validateExternalFile(file) {
  if (!file || typeof file.name !== "string") throw new Error("Choose a source artifact.");
  const kind = classifyExternalArtifact(file.name);
  if (kind === "unsupported") throw new Error("Supported: Circuit JSON, KiCad .net, BOM .csv, STL/STEP and firmware .ino/.cpp/.h.");
  if (!Number.isFinite(file.size) || file.size === 0 || file.size > MAX_TEXT_BYTES) {
    throw new Error("Artifact must be nonempty and at most 4 MB for this local review.");
  }
  return kind;
}
