/** Inspector fields generated from a tool's JSON input schema. Values are kept as text and parsed on Run. */
const PATHLIKE = /(^|_)(pcb|schematic|step|urdf|file|path|cad_file|netlist)$/;

export function fieldKind(spec = {}) {
  if (Array.isArray(spec.enum)) return "enum";
  if (spec.type === "boolean") return "boolean";
  if (spec.type === "number" || spec.type === "integer") return "number";
  if (spec.type === "string") return "string";
  return "json";
}

export function valuesFromArgs(schema, args = {}) {
  const out = {};
  for (const [name, spec] of Object.entries(schema?.properties ?? {})) {
    if (!(name in args)) continue;
    const kind = fieldKind(spec);
    const v = args[name];
    out[name] = kind === "json" ? JSON.stringify(v, null, 1) : kind === "boolean" ? Boolean(v) : String(v);
  }
  return out;
}

/** Text values -> arguments. Returns { args, errors } with one message per field that cannot be read. */
export function argsFromValues(schema, values = {}) {
  const args = {};
  const errors = {};
  const required = new Set(schema?.required ?? []);
  for (const [name, spec] of Object.entries(schema?.properties ?? {})) {
    const kind = fieldKind(spec);
    const raw = values[name];
    if (kind === "boolean") { if (raw !== undefined) args[name] = Boolean(raw); continue; }
    if (raw === undefined || String(raw).trim() === "") {
      if (required.has(name)) errors[name] = "Required";
      continue;
    }
    if (kind === "number") {
      const n = Number(raw);
      if (Number.isFinite(n)) args[name] = n; else errors[name] = "Enter a number";
    } else if (kind === "json") {
      try { args[name] = JSON.parse(raw); } catch { errors[name] = "Not valid JSON"; }
    } else {
      args[name] = String(raw);
    }
  }
  return { args, errors };
}

export function SchemaForm({ tool, values, errors, onChange, disabled }) {
  const props = Object.entries(tool.input_schema?.properties ?? {});
  const required = new Set(tool.input_schema?.required ?? []);
  if (!props.length) return <p className="wb-muted">This tool takes no inputs.</p>;
  const ordered = [...props].sort(([a], [b]) => Number(required.has(b)) - Number(required.has(a)) || (a === "project_id") - (b === "project_id"));
  return (
    <div className="wb-form">
      {ordered.map(([name, spec]) => {
        const kind = fieldKind(spec);
        const id = `bf-${tool.name}-${name}`;
        const err = errors?.[name];
        const common = { id, disabled, "aria-invalid": err ? true : undefined, "aria-describedby": err ? `${id}-err` : undefined };
        return (
          <div className={`wb-field kind-${kind}`} key={name}>
            {kind === "boolean" ? (
              <label className="wb-check" htmlFor={id}>
                <input type="checkbox" {...common} checked={Boolean(values[name])} onChange={(e) => onChange(name, e.target.checked)} />
                <span className="wb-field-name">{name}</span>
              </label>
            ) : (
              <label className="wb-field-label" htmlFor={id}>
                <span className="wb-field-name">{name}</span>
                {required.has(name) && <span className="wb-req">required</span>}
                <span className="wb-field-type">{spec.type ?? "json"}</span>
              </label>
            )}
            {kind === "enum" && (
              <select {...common} value={values[name] ?? ""} onChange={(e) => onChange(name, e.target.value)}>
                <option value="">—</option>
                {spec.enum.map((v) => <option key={String(v)} value={String(v)}>{String(v)}</option>)}
              </select>
            )}
            {(kind === "string" || kind === "number") && (
              <input {...common} type="text" inputMode={kind === "number" ? "decimal" : undefined} spellCheck={false}
                className={kind === "number" || PATHLIKE.test(name) ? "mono" : ""}
                placeholder={PATHLIKE.test(name) ? "path inside the repository" : ""}
                value={values[name] ?? ""} onChange={(e) => onChange(name, e.target.value)} />
            )}
            {kind === "json" && (
              <textarea {...common} className="mono" rows={Math.min(8, Math.max(2, String(values[name] ?? "").split("\n").length))}
                spellCheck={false} placeholder={spec.type === "array" ? "[ ]" : "{ }"}
                value={values[name] ?? ""} onChange={(e) => onChange(name, e.target.value)} />
            )}
            {spec.description && <p className="wb-field-help">{spec.description}</p>}
            {err && <p className="wb-field-err" id={`${id}-err`}>{err}</p>}
          </div>
        );
      })}
    </div>
  );
}
