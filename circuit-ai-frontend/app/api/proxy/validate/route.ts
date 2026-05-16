import { NextRequest } from "next/server";
import { getCircuitApiBaseUrl } from "../_backend";

export async function POST(request: NextRequest) {
  // /api/v2/* is the canonical Flask surface — use the shared resolver,
  // not a standalone hardcode that can drift from _backend.ts.
  const targetUrl = `${getCircuitApiBaseUrl()}/api/v2/workflow/validate-kicad`;

  try {
    const formData = await request.formData();

    const response = await fetch(targetUrl, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const text = await response.text();
      return Response.json(
        { error: `Backend returned ${response.status}: ${text}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return Response.json(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return Response.json(
      { error: `Proxy error: ${message}` },
      { status: 502 }
    );
  }
}
