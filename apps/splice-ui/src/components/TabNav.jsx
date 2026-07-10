export default function TabNav({ tabs, activeId, onChange, badges = {} }) {
  return (
    <nav className="tab-nav" aria-label="Project stages" data-testid="stage-tab-nav">
      {tabs.map((tab) => {
        const disabled = tab.available === false;
        const complete = Boolean(tab.complete);
        return (
          <button
            key={tab.id}
            type="button"
            data-testid={`stage-tab-${tab.id}`}
            data-available={tab.available !== false ? "true" : "false"}
            data-complete={complete ? "true" : "false"}
            className={[
              activeId === tab.id ? "active" : "",
              tab.highlight ? "tab-highlight" : "",
              disabled ? "tab-disabled" : "",
              complete && activeId !== tab.id ? "tab-complete" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            onClick={() => {
              if (disabled) return;
              onChange(tab.id);
            }}
            disabled={disabled}
            title={disabled ? tab.blockedReason || "Not available yet" : tab.label}
            aria-current={activeId === tab.id ? "step" : undefined}
          >
            {complete && !disabled ? <span className="tab-check" aria-hidden>✓</span> : null}
            {tab.label}
            {badges[tab.id] != null && badges[tab.id] > 0 && (
              <span className="tab-badge">{badges[tab.id]}</span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
