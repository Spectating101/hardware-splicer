import { useMemo, useState } from "react";
import { groupByCategory } from "./studioCanvas.js";

export default function ModuleLibrary({ modules, onAdd, disabled }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");

  const categories = useMemo(() => {
    const set = new Set((modules || []).map((m) => m.category || "other"));
    return ["all", ...[...set].sort()];
  }, [modules]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (modules || []).filter((row) => {
      if (category !== "all" && row.category !== category) return false;
      if (!q) return true;
      const hay = `${row.id} ${row.label} ${row.summary || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }, [modules, query, category]);

  const groups = useMemo(() => groupByCategory(filtered), [filtered]);

  return (
    <aside className="studio-library card">
      <header className="studio-library__header">
        <h2>Module library</h2>
        <p className="muted small">KiCad-footprinted modules from the engine registry.</p>
      </header>

      <input
        type="search"
        className="studio-library__search"
        placeholder="Search modules…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={disabled}
      />

      <div className="studio-library__filters">
        {categories.map((cat) => (
          <button
            key={cat}
            type="button"
            className={`chip small ${category === cat ? "active" : ""}`}
            onClick={() => setCategory(cat)}
            disabled={disabled}
          >
            {cat}
          </button>
        ))}
      </div>

      <div className="studio-library__list">
        {groups.map(([cat, rows]) => (
          <section key={cat} className="studio-library__group">
            <h3>{cat}</h3>
            {rows.map((row) => (
              <button
                key={row.id}
                type="button"
                className="studio-library__item"
                onClick={() => onAdd(row)}
                disabled={disabled}
                title={row.summary || row.id}
              >
                <strong>{row.label}</strong>
                <span className="mono small">{row.id}</span>
                <span className="muted small">{row.pins?.length || 0} pins</span>
              </button>
            ))}
          </section>
        ))}
        {!filtered.length && <p className="muted small">No modules match.</p>}
      </div>
    </aside>
  );
}
