const API_BASE =
  import.meta.env.VITE_API_BASE !== undefined
    ? import.meta.env.VITE_API_BASE
    : import.meta.env.DEV
      ? "/api"
      : "";

async function parseJson(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body?.detail;
    const error = new Error(
      typeof detail === "string"
        ? detail
        : detail?.message || detail?.error?.message || res.statusText || `Request failed (${res.status})`,
    );
    error.status = res.status;
    error.type = detail?.type || "request_failed";
    throw error;
  }
  return body;
}

export async function projectElectricalDesign(project) {
  return parseJson(
    await fetch(`${API_BASE}/v1/electrical-designs/from-machine-project`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project }),
    }),
  );
}

export async function editElectricalDesign(design, operations) {
  return parseJson(
    await fetch(`${API_BASE}/v1/electrical-designs/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ design, operations }),
    }),
  );
}

export async function checkElectricalDesign(design) {
  return parseJson(
    await fetch(`${API_BASE}/v1/electrical-designs/erc`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ design }),
    }),
  );
}
