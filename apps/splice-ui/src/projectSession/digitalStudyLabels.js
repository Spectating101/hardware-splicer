// Machine keys stay the source of truth; these only say them in words. Unmapped keys fall back
// to a mechanical reading of the key (snake or camel case, trailing unit word), never a guess.
const UNIT_WORDS = { a: "A", h: "h", mm: "mm", g: "g", w: "W", v: "V", s: "s", mah: "mAh", min: "min", usd: "USD", m: "m" };

const LABELS = {
  minimum_work_runtime_h: ["Minimum work runtime", "h"],
  minimum_supply_margin_a: ["Minimum supply margin", "A"],
  keyboard_current_a: ["Keyboard current", "A"],
  pi_work_current_a: ["Pi current at work load", "A"],
  work_runtime: ["Work runtime", "h"],
  ordinary_source_margin: ["Supply margin, ordinary load", "A"],
  high_keyboard_supply_limit: ["Supply margin, high keyboard demand", "A"],
  cad_kernel_available: ["CAD kernel available"],
  licensing_review_completed: ["Licensing review completed"],
  batteryVoltage: ["Battery voltage", "V"],
  runtimeMin: ["Minimum runtime", "min"],
  flight_time_goal_min: ["Flight time goal", "min"],
  budget_usd: ["Budget", "USD"],
  payload_mass_g: ["Payload mass", "g"],
  max_mass_g: ["Mass limit", "g"],
  gust_scale: ["Gust force scale", "×"],
  nominal_mass: ["Nominal mass", "g"],
};

function splitKey(key) {
  const words = String(key).replace(/([a-z0-9])([A-Z])/g, "$1_$2").toLowerCase().split(/[_\s]+/).filter(Boolean);
  const unit = words.length > 1 ? UNIT_WORDS[words.at(-1)] : undefined;
  if (unit) words.pop();
  const name = words.join(" ");
  return { label: name.charAt(0).toUpperCase() + name.slice(1), unit };
}

/** Readable name and unit for a machine key. */
export function keyLabel(key) {
  const mapped = LABELS[key];
  if (mapped) return { label: mapped[0], unit: mapped[1] };
  return splitKey(key);
}

/** "Minimum work runtime (h)": the form used for table headers and inputs. */
export function fieldLabel(key) {
  const { label, unit } = keyLabel(key);
  return label + (unit ? ` (${unit})` : "");
}

/** "Minimum work runtime · 3.5 h": a fact with its value in words. */
export function factText(key, value) {
  const { label, unit } = keyLabel(key);
  return `${label} · ${formatValue(value, unit)}`;
}

export function formatValue(value, unit) {
  if (value === undefined || value === null || value === "") return "unknown";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "object") return JSON.stringify(value);
  return `${value}${unit && unit !== "×" ? ` ${unit}` : unit === "×" ? "×" : ""}`;
}
