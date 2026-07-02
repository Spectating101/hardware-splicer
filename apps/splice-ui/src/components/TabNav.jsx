export default function TabNav({ tabs, activeId, onChange, badges = {} }) {
  return (
    <nav className="tab-nav" aria-label="Project sections">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={activeId === tab.id ? "active" : ""}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
          {badges[tab.id] != null && badges[tab.id] > 0 && (
            <span className="tab-badge">{badges[tab.id]}</span>
          )}
        </button>
      ))}
    </nav>
  );
}
