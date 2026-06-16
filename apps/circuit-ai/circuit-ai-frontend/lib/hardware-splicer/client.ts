import type { BuildGraph } from "@/lib/rules/safety-rules";

const PROXY_COMPOSE = "/api/proxy/hardware-splicer/compose";
const PROXY_COMPILE = "/api/proxy/hardware-splicer/compile-build";

/** Strict opt-in (legacy). */
export function hardwareSplicerEngineEnabled(): boolean {
  return process.env.NEXT_PUBLIC_HARDWARE_SPLICER_ENGINE === "1";
}

/** Python engine is tried first unless explicitly disabled with `=0`. */
export function preferPythonEngine(): boolean {
  return process.env.NEXT_PUBLIC_HARDWARE_SPLICER_ENGINE !== "0";
}

type ComposeCanvasPayload = {
  canvas_nodes: Array<{ id: string; moduleId: string }>;
  canvas_wires?: Array<{ from: { nodeId: string; pinId: string }; to: { nodeId: string; pinId: string } }>;
  export_gerber?: boolean;
  wire_only?: boolean;
};

type ComposePhrasePayload = {
  phrase: string;
  export_gerber?: boolean;
  wire_only?: boolean;
};

type CompilePayload = {
  build_id: string;
  export_gerber?: boolean;
};

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const payload = (await response.json()) as T & { error?: string; ok?: boolean; detail?: { message?: string } };
  if (!response.ok || payload.ok === false) {
    const detailMessage =
      typeof payload.detail === "object" && payload.detail?.message
        ? payload.detail.message
        : undefined;
    throw new Error(
      typeof payload.error === "string" && payload.error.trim()
        ? payload.error
        : detailMessage ?? `Hardware-Splicer request failed (${response.status})`,
    );
  }
  return payload;
}

export async function compileCatalogBuildRemote(
  buildId: string,
): Promise<{ graph: BuildGraph; warnings?: string[]; notes?: string[] }> {
  const payload = await postJson<{
    graph?: BuildGraph;
    design_quality?: { warnings?: string[]; notes?: string[] };
  }>(PROXY_COMPILE, { build_id: buildId, export_gerber: false } satisfies CompilePayload);

  if (!payload.graph?.nodes?.length) {
    throw new Error(`Python engine returned no graph for "${buildId}".`);
  }
  return {
    graph: payload.graph,
    warnings: payload.design_quality?.warnings,
    notes: payload.design_quality?.notes,
  };
}

export async function composeCanvasRemote(
  nodes: ComposeCanvasPayload["canvas_nodes"],
  wires?: ComposeCanvasPayload["canvas_wires"],
): Promise<BuildGraph> {
  const payload = await postJson<{ graph?: BuildGraph; wire_only?: boolean }>(PROXY_COMPOSE, {
    canvas_nodes: nodes,
    canvas_wires: wires,
    export_gerber: false,
    wire_only: true,
  } satisfies ComposeCanvasPayload);

  if (!payload.graph?.nodes?.length) {
    throw new Error("Python engine returned no canvas graph.");
  }
  return payload.graph;
}

export async function composePhraseRemote(phrase: string): Promise<{
  graph: BuildGraph;
  moduleIds: string[];
  warnings?: string[];
}> {
  const payload = await postJson<{
    graph?: BuildGraph;
    module_ids?: string[];
    warnings?: string[];
  }>(PROXY_COMPOSE, {
    phrase,
    export_gerber: false,
    wire_only: true,
  } satisfies ComposePhrasePayload);

  if (!payload.graph?.nodes?.length) {
    throw new Error("Python engine returned no composed graph.");
  }
  return {
    graph: payload.graph,
    moduleIds: payload.module_ids ?? payload.graph.nodes.map((n) => n.moduleId),
    warnings: payload.warnings,
  };
}

type ComposeBuildPayload = {
  canvas_nodes: Array<{ id: string; moduleId: string }>;
  canvas_wires?: Array<{ from: { nodeId: string; pinId: string }; to: { nodeId: string; pinId: string } }>;
  export_gerber?: boolean;
  wire_only?: boolean;
};

export async function composeCanvasBuildRemote(
  graph: BuildGraph,
  options?: { exportGerber?: boolean },
): Promise<{
  ok?: boolean;
  design_quality?: Record<string, unknown>;
  design_quality_gate?: Record<string, unknown>;
  error?: string;
}> {
  return postJson(PROXY_COMPOSE, {
    canvas_nodes: graph.nodes.map((n) => ({ id: n.id, moduleId: n.moduleId })),
    canvas_wires: graph.wires.map((w) => ({
      from: w.from,
      to: w.to,
    })),
    export_gerber: options?.exportGerber ?? false,
    wire_only: false,
  } satisfies ComposeBuildPayload);
}
