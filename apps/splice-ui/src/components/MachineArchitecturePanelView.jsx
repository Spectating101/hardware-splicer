import { useMemo, useState } from "react";

function title(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function authorityLabel(value) {
  return title(value || "unknown");
}

function domainClass(domain) {
  return `machine-domain machine-domain--${domain || "system"}`;
}

function projectIssues(project) {
  const issues = [];
  for (const requirement of project?.requirements || []) {
    if (!(requirement.verification_method_ids || []).length) {
      issues.push({
        code: "unverified_requirement",
        objectId: requirement.requirement_id,
        message: `${requirement.requirement_id} has no verification method`,
      });
    }
  }
  for (const contract of project?.interfaces || []) {
    const unresolved = (contract.contracts || []).flatMap((row) => row.unresolved_fields || []);
    if (unresolved.length) {
      issues.push({
        code: "unresolved_interface",
        objectId: contract.interface_id,
        message: `${contract.interface_id}: ${[...new Set(unresolved)].join(", ")}`,
      });
    }
  }
  return issues;
}

export default function MachineArchitecturePanel({ project, onOpenDiscipline }) {
  const subsystems = project?.subsystems || [];
  const [selectedId, setSelectedId] = useState(() =>
    subsystems.find((row) => row.subsystem_id !== "system")?.subsystem_id ||
    subsystems[0]?.subsystem_id ||
    null,
  );

  const selected = useMemo(
    () => subsystems.find((row) => row.subsystem_id === selectedId) || subsystems[0] || null,
    [selectedId, subsystems],
  );
  const components = useMemo(
    () =>
      (project?.components || []).filter(
        (row) => !selected || row.subsystem_id === selected.subsystem_id,
      ),
    [project?.components, selected],
  );
  const requirements = useMemo(
    () =>
      (project?.requirements || []).filter((row) => {
        if (!selected) return true;
        const allocated = row.allocated_to || [];
        return (
          allocated.includes(selected.subsystem_id) ||
          (selected.requirement_ids || []).includes(row.requirement_id)
        );
      }),
    [project?.requirements, selected],
  );
  const interfaces = useMemo(
    () =>
      (project?.interfaces || []).filter((row) => {
        if (!selected) return true;
        const objectIds = (row.endpoints || []).map((endpoint) => endpoint.object_id);
        return (
          objectIds.includes(selected.subsystem_id) ||
          components.some((component) => objectIds.includes(component.component_id))
        );
      }),
    [components, project?.interfaces, selected],
  );
  const issues = useMemo(() => projectIssues(project), [project]);

  if (!project) {
    return (
      <section className="card empty-card" data-testid="machine-architecture-empty">
        <h3>Machine architecture</h3>
        <p className="muted small">
          Finish Intake to seed purpose, requirements, subsystems, components, and constraints.
        </p>
      </section>
    );
  }

  return (
    <section className="card machine-architecture" data-testid="machine-architecture-panel">
      <header className="machine-architecture__header">
        <div>
          <p className="eyebrow">Complete machine</p>
          <h2>{project.name}</h2>
          <p className="muted">{project.purpose}</p>
        </div>
        <div className="machine-architecture__metrics" aria-label="Machine project counts">
          <span><strong>{subsystems.length}</strong> subsystems</span>
          <span><strong>{project.components?.length || 0}</strong> components</span>
          <span><strong>{project.requirements?.length || 0}</strong> requirements</span>
          <span><strong>{project.verifications?.length || 0}</strong> verifications</span>
        </div>
      </header>

      <div className="machine-architecture__layout">
        <nav className="machine-architecture__tree" aria-label="Machine subsystems">
          <p className="sidebar-label">Architecture</p>
          {subsystems.map((subsystem) => (
            <button
              key={subsystem.subsystem_id}
              type="button"
              className={`project-button ${selected?.subsystem_id === subsystem.subsystem_id ? "active" : ""}`}
              onClick={() => setSelectedId(subsystem.subsystem_id)}
              data-testid={`machine-subsystem-${subsystem.subsystem_id}`}
            >
              <strong>{subsystem.name}</strong>
              <span className={domainClass(subsystem.domain)}>{title(subsystem.domain)}</span>
            </button>
          ))}
        </nav>

        <div className="machine-architecture__detail">
          {selected && (
            <>
              <div className="machine-architecture__section-heading">
                <div>
                  <p className="eyebrow">{title(selected.domain)}</p>
                  <h3>{selected.name}</h3>
                  <p className="muted small">{selected.purpose || "Purpose not yet declared."}</p>
                </div>
                {onOpenDiscipline && selected.domain !== "system" && (
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => onOpenDiscipline(selected.domain, selected)}
                  >
                    Open {title(selected.domain)} workspace
                  </button>
                )}
              </div>

              <div className="machine-architecture__groups">
                <div>
                  <h4>Components</h4>
                  {components.length ? (
                    <div className="machine-object-list">
                      {components.map((component) => (
                        <article key={component.component_id} className="fixture-card">
                          <strong>{component.name}</strong>
                          <span>{component.role || title(component.domain)}</span>
                          <small>
                            {title(component.source)} · {authorityLabel(component.authority)}
                          </small>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="muted small">No components allocated yet.</p>
                  )}
                </div>

                <div>
                  <h4>Allocated requirements</h4>
                  {requirements.length ? (
                    <div className="machine-object-list">
                      {requirements.map((requirement) => (
                        <article key={requirement.requirement_id} className="fixture-card">
                          <strong>{requirement.requirement_id}</strong>
                          <span>{requirement.statement}</span>
                          <small>{title(requirement.kind)} · {authorityLabel(requirement.authority)}</small>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="muted small">No requirements allocated to this subsystem.</p>
                  )}
                </div>

                <div>
                  <h4>Interfaces</h4>
                  {interfaces.length ? (
                    <div className="machine-object-list">
                      {interfaces.map((interfaceRow) => {
                        const unresolved = (interfaceRow.contracts || []).flatMap(
                          (row) => row.unresolved_fields || [],
                        );
                        return (
                          <article key={interfaceRow.interface_id} className="fixture-card">
                            <strong>{interfaceRow.name}</strong>
                            <span>{title(interfaceRow.kind)}</span>
                            <small>
                              {unresolved.length
                                ? `Unresolved: ${[...new Set(unresolved)].join(", ")}`
                                : authorityLabel(interfaceRow.authority)}
                            </small>
                          </article>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="muted small">
                      No interfaces inferred. Add explicit contracts rather than relying on architecture adjacency.
                    </p>
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        <aside className="machine-architecture__traceability">
          <h4>Traceability</h4>
          <p className="muted small">
            Lifecycle: <strong>{title(project.lifecycle_state)}</strong>
          </p>
          <p className="muted small">
            Requested release: <strong>{title(project.requested_release_state)}</strong>
          </p>
          {issues.length ? (
            <div className="machine-issue-list" data-testid="machine-traceability-issues">
              {issues.map((issue) => (
                <article key={`${issue.code}-${issue.objectId}`} className="honesty-card honesty-card--warn">
                  <strong>{title(issue.code)}</strong>
                  <p className="small muted">{issue.message}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="small">No unresolved requirement or interface gaps detected.</p>
          )}
          <p className="muted small">
            Architecture does not imply fabrication, power, firmware, or operational authorization.
          </p>
        </aside>
      </div>
    </section>
  );
}

export { projectIssues };
