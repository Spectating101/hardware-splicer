// Streaming chat endpoint. Posts { messages, context? } → SSE stream of text
// deltas. Frontend consumes with EventSource / fetch ReadableStream.

import { streamJarvis, type JarvisMessage } from "@/lib/jarvis/client";

export const runtime = "nodejs";

interface ChatRequest {
  messages: JarvisMessage[];
  /** Extra context to prepend as a system-level user preamble (e.g. current
   *  board geometry summary, selected component). */
  context?: string;
}

export async function POST(req: Request) {
  let body: ChatRequest;
  try {
    body = await req.json() as ChatRequest;
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
  }

  if (!Array.isArray(body.messages) || body.messages.length === 0) {
    return new Response(JSON.stringify({ error: "messages[] required" }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
  }

  const messages: JarvisMessage[] = body.context
    ? [
        { role: "user", content: `CONTEXT:\n${body.context}\n\n(proceed with the user's next message)` },
        { role: "assistant", content: "Understood — ready for the question." },
        ...body.messages,
      ]
    : body.messages;

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      try {
        for await (const delta of streamJarvis({ flow: "chat", messages })) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ delta })}\n\n`));
        }
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ done: true })}\n\n`));
        controller.close();
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ error: msg })}\n\n`));
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
    },
  });
}
