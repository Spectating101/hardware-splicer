const API_BASE = import.meta.env.VITE_API_BASE !== undefined
  ? import.meta.env.VITE_API_BASE : import.meta.env.DEV ? "/api" : "";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const error = new Error(typeof detail === "string" ? detail : detail?.message || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return body;
}

export const fetchDigitalCases = (signal) => request("/v1/digital/cases", { signal });

export const createDigitalProject = (caseId) => request("/v1/digital/projects", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ case_id: caseId }),
});

export const fetchDigitalStudy = (projectId, signal) =>
  request(`/v1/projects/${encodeURIComponent(projectId)}/digital`, { signal });

export const submitDigitalRun = (projectId, payload) =>
  request(`/v1/projects/${encodeURIComponent(projectId)}/digital/runs`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });

export const fetchDigitalJob = (jobId, signal) => request(`/v1/jobs/${encodeURIComponent(jobId)}`, { signal });
export const cancelDigitalJob = (jobId) => request(`/v1/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
export const digitalArtifactUrl = (path) => path ? `${API_BASE}${path}` : undefined;

export const fetchProjectAssurance = (projectId, revision, signal) =>
  request(`/v1/projects/${encodeURIComponent(projectId)}/engineering/assurance?revision=${revision}`, { signal });
export const fetchProjectMaterials = (projectId, signal) =>
  request(`/v1/projects/${encodeURIComponent(projectId)}/materials`, { signal });
export const fetchMaterialAssessment = (projectId, assessmentId, signal) =>
  request(`/v1/projects/${encodeURIComponent(projectId)}/materials/${encodeURIComponent(assessmentId)}`, { signal });
export const fetchPartSubstitution = (projectId, assessmentId, signal) =>
  request(`/v1/projects/${encodeURIComponent(projectId)}/parts/substitutions/${encodeURIComponent(assessmentId)}`, { signal });
export const assessMachineRelease = (project, signal) => request("/v1/machine-projects/assess-release", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project }), signal,
});
export const fetchDigitalCompare = (projectId, before, after, signal) =>
  request(`/v1/projects/${encodeURIComponent(projectId)}/digital/compare?before_revision=${before}&after_revision=${after}`, { signal });
export const fetchEvidenceDelta = (projectId, base, candidate, signal) =>
  request(`/v1/projects/${encodeURIComponent(projectId)}/engineering/assurance/evidence-delta`, {
    method: "POST", headers: { "Content-Type": "application/json" }, signal,
    body: JSON.stringify({ base_revision: base, candidate_revision: candidate }),
  });
export const fetchEngineeringPackages = (projectId, signal) =>
  request(`/v1/projects/${encodeURIComponent(projectId)}/engineering-packages`, { signal });
export const engineeringPackageUrl = (projectId, packageId) =>
  `${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/engineering-packages/${encodeURIComponent(packageId)}/download`;
export const fetchEngineeringRevisionDiff = (projectId, base, candidate, signal) => request("/v1/engineering/revisions/diff", {
  method: "POST", headers: { "Content-Type": "application/json" }, signal,
  body: JSON.stringify({ project_id: projectId, base_revision: base, candidate_revision: candidate }),
});
