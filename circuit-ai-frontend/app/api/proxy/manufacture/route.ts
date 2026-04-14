import { NextRequest } from "next/server";

export async function POST(request: NextRequest) {
  const mechaUrl = process.env.MECHA_API_URL ?? "http://localhost:8085";
  const targetUrl = `${mechaUrl}/api/v1/bundle`;

  try {
    const body = await request.json();

    const response = await fetch(targetUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const text = await response.text();
      return Response.json(
        { error: `Mecha-Splicer returned ${response.status}: ${text}` },
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
