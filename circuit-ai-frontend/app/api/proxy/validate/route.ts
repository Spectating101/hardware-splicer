import { NextRequest } from "next/server";

export async function POST(request: NextRequest) {
  const backendUrl = process.env.CIRCUIT_AI_API_URL ?? "http://localhost:5000";
  const targetUrl = `${backendUrl}/api/v2/workflow/validate-kicad`;

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
