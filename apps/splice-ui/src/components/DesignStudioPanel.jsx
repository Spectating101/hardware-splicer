import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { composeAgentLoop, fetchDesignQuality, fetchModuleCatalog } from "../api.js";
import ModuleLibrary from "../studio/ModuleLibrary.jsx";
import ModuleNode from "../studio/ModuleNode.jsx";
import StudioDrcPanel from "../studio/StudioDrcPanel.jsx";
import { buildComposePayload, createModuleNode, nextNodeId } from "../studio/studioCanvas.js";
import { extractStudioDrc } from "../studio/studioDrc.js";

const nodeTypes = { module: ModuleNode };

function StudioCanvas({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  setNodes,
  setEdges,
  onSelectionChange,
  disabled,
}) {
  const { screenToFlowPosition } = useReactFlow();

  const onConnect = useCallback(
    (connection) => {
      if (disabled) return;
      setEdges((eds) => addEdge({ ...connection, animated: true, className: "studio-wire" }, eds));
    },
    [disabled, setEdges],
  );

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      if (disabled) return;
      const raw = event.dataTransfer.getData("application/hs-module");
      if (!raw) return;
      let spec;
      try {
        spec = JSON.parse(raw);
      } catch {
        return;
      }
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
      setNodes((nds) => {
        const id = nextNodeId(nds);
        return [...nds, createModuleNode(spec.id, { id, position, spec })];
      });
    },
    [disabled, setNodes, screenToFlowPosition],
  );

  return (
    <div className="studio-canvas-wrap">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onSelectionChange={onSelectionChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        deleteKeyCode={disabled ? null : ["Backspace", "Delete"]}
        className="studio-canvas"
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="rgba(148,163,184,0.25)" />
        <Controls showInteractive={!disabled} />
        <MiniMap nodeColor={() => "#0f766e"} maskColor="rgba(2,6,23,0.75)" className="studio-minimap" />
      </ReactFlow>
      {!nodes.length && (
        <div className="studio-canvas-empty">
          <p>
            <strong>Drop modules here</strong> or click a library entry to start wiring.
          </p>
          <p className="muted small">Compile runs KiCad DRC with an auto-fix loop — feedback stays in the studio.</p>
        </div>
      )}
    </div>
  );
}

function buildAgentSteps(composeResult, drc) {
  const agentRounds = drc?.agentRounds || [];
  if (agentRounds.length) {
    return agentRounds.flatMap((round, idx) => [
      {
        id: `compose-${idx}`,
        status: "done",
        detail: `round ${round.round} · ${round.mode || "compose"} · ${round.kicad_drc_errors} DRC errors`,
      },
      ...(round.engine_drc_fix_loop?.attempts?.length
        ? [
            {
              id: `fix-${idx}`,
              status: round.kicad_drc_errors === 0 ? "done" : "warn",
              detail: `${round.engine_drc_fix_loop.attempts.length} engine fix attempt(s)`,
            },
          ]
        : []),
    ]).concat([
      {
        id: "done",
        status: drc?.resolved ? "done" : "warn",
        detail: drc?.resolved ? "DRC errors cleared" : "review remaining violations",
      },
    ]);
  }

  const attempts = drc?.attempts || [];
  const errors = drc?.truth?.kicad_drc_errors ?? 0;
  return [
    {
      id: "compose",
      status: composeResult ? "done" : "pending",
      detail: composeResult?.mode ? `${composeResult.mode} graph` : null,
    },
    {
      id: "compile",
      status: composeResult ? "done" : "pending",
      detail: composeResult?.build_id || null,
    },
    {
      id: "drc",
      status: composeResult ? (errors === 0 ? "done" : "warn") : "pending",
      detail: composeResult ? `${errors} errors, ${drc?.truth?.kicad_drc_warnings ?? 0} warnings` : null,
    },
    {
      id: "fix",
      status: attempts.length ? (drc?.resolved ? "done" : "warn") : composeResult ? "done" : "pending",
      detail: attempts.length ? `${attempts.length} attempt(s)` : "no fixups needed",
    },
    {
      id: "done",
      status: composeResult?.ok ? "done" : composeResult ? "warn" : "pending",
      detail: composeResult?.ok ? "build ready" : composeResult ? "review DRC" : null,
    },
  ];
}

function DesignStudioInner({ onOpenProject, llmReady, apiOk }) {
  const [modules, setModules] = useState([]);
  const [catalogError, setCatalogError] = useState(null);
  const [phrase, setPhrase] = useState("");
  const [composeMode, setComposeMode] = useState("canvas");
  const [selectedIds, setSelectedIds] = useState([]);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [compiling, setCompiling] = useState(false);
  const [composeError, setComposeError] = useState("");
  const [composeResult, setComposeResult] = useState(null);
  const [drcState, setDrcState] = useState(null);
  const [drcFixup, setDrcFixup] = useState(null);
  const [manualRetries, setManualRetries] = useState(0);

  useEffect(() => {
    if (!apiOk) return;
    fetchModuleCatalog()
      .then((body) => {
        setModules(body.modules || []);
        setCatalogError(null);
      })
      .catch((err) => setCatalogError(err.message));
  }, [apiOk]);

  const moduleIndex = useMemo(() => {
    const map = new Map();
    for (const row of modules) map.set(row.id, row);
    return map;
  }, [modules]);

  const addModule = useCallback(
    (spec) => {
      if (compiling) return;
      const resolved = moduleIndex.get(spec.id) || spec;
      setNodes((nds) => {
        const id = nextNodeId(nds);
        const offset = nds.length * 32;
        return [
          ...nds,
          createModuleNode(resolved.id, {
            id,
            position: { x: 120 + offset, y: 80 + offset },
            spec: resolved,
          }),
        ];
      });
    },
    [compiling, moduleIndex, setNodes],
  );

  const handleLibraryDragStart = (event, spec) => {
    event.dataTransfer.setData("application/hs-module", JSON.stringify(spec));
    event.dataTransfer.effectAllowed = "move";
  };

  const removeSelected = () => {
    if (!selectedIds.length || compiling) return;
    const drop = new Set(selectedIds);
    setNodes((nds) => nds.filter((n) => !drop.has(n.id)));
    setEdges((eds) => eds.filter((e) => !drop.has(e.source) && !drop.has(e.target)));
    setSelectedIds([]);
  };

  const clearCanvas = () => {
    if (compiling) return;
    setNodes([]);
    setEdges([]);
    setSelectedIds([]);
    setComposeResult(null);
    setDrcState(null);
    setDrcFixup(null);
    setManualRetries(0);
    setComposeError("");
  };

  const runCompose = async ({ fixup = drcFixup, isRetry = false, maxRounds = 2 } = {}) => {
    const allowLlm = composeMode === "ai" && llmReady;
    const payload = buildComposePayload(nodes, edges, {
      phrase,
      allowLlmFirst: allowLlm,
      drcFixup: fixup,
    });
    if (!payload) return;

    setCompiling(true);
    setComposeError("");
    if (!isRetry) {
      setComposeResult(null);
      setDrcState(null);
    }

    try {
      const result = await composeAgentLoop(payload, { maxManualRetries: maxRounds });
      setComposeResult(result);

      let drc = extractStudioDrc(result);
      if (result.out_dir) {
        try {
          const quality = await fetchDesignQuality(result.out_dir);
          drc = extractStudioDrc({
            ...result,
            design_quality: {
              ...(result.design_quality || {}),
              drc_fix_loop: quality.drc_fix_loop || result.design_quality?.drc_fix_loop,
              copper_tier: quality.copper_tier || result.design_quality?.copper_tier,
              fab_recommendation: quality.fab_recommendation || result.design_quality?.fab_recommendation,
            },
            violations: quality.violations,
          });
        } catch {
          // keep compose payload truth
        }
      }

      setDrcState(drc);
      if (fixup) setDrcFixup(fixup);
      if (isRetry) setManualRetries((n) => n + 1);
      else setManualRetries(result.agent_loop?.manual_retries_used || 0);
    } catch (err) {
      setComposeError(err.message);
    } finally {
      setCompiling(false);
    }
  };

  const handleCompile = () => runCompose({ fixup: null, isRetry: false, maxRounds: 2 });

  const handleAutoFix = (nextFixup) => runCompose({ fixup: nextFixup, isRetry: true, maxRounds: 2 });

  const canCompile =
    composeMode === "ai"
      ? phrase.trim().length > 0
      : nodes.filter((n) => n.data?.moduleId).length >= 2;

  const disabled = compiling || !apiOk;
  const agentSteps = buildAgentSteps(composeResult, drcState);

  return (
    <div className="design-studio">
      <header className="design-studio__toolbar card">
        <div className="design-studio__toolbar-main">
          <div>
            <p className="eyebrow">Design studio</p>
            <h1>Pin-level canvas → KiCad compile + DRC agent</h1>
          </div>
          <div className="design-studio__mode">
            <button
              type="button"
              className={`chip ${composeMode === "canvas" ? "active" : ""}`}
              onClick={() => setComposeMode("canvas")}
              disabled={disabled}
            >
              Canvas compile
            </button>
            <button
              type="button"
              className={`chip ${composeMode === "ai" ? "active" : ""}`}
              onClick={() => setComposeMode("ai")}
              disabled={disabled}
            >
              AI phrase compose
            </button>
          </div>
        </div>

        <label className="design-studio__phrase">
          <span className="small muted">Project goal (names the build + steers AI)</span>
          <input
            type="text"
            value={phrase}
            onChange={(e) => setPhrase(e.target.value)}
            placeholder="e.g. ESP32 soil moisture logger with OLED and 18650 power"
            disabled={disabled}
          />
        </label>

        <div className="design-studio__actions">
          <button type="button" className="ghost" onClick={removeSelected} disabled={disabled || !selectedIds.length}>
            Remove selected
          </button>
          <button type="button" className="ghost" onClick={clearCanvas} disabled={disabled || !nodes.length}>
            Clear canvas
          </button>
          <button type="button" className="primary" onClick={handleCompile} disabled={disabled || !canCompile}>
            {compiling ? "Compiling…" : composeMode === "ai" ? "AI compose → KiCad" : "Compile to KiCad"}
          </button>
        </div>

        {composeMode === "ai" && (
          <p className="hint small">
            {llmReady
              ? "AI-first compose uses Qwen when configured — DRC fix loop runs on every compile."
              : "LLM keys not configured — phrase compose falls back to heuristic module picker."}
          </p>
        )}
        {composeMode === "canvas" && edges.length === 0 && nodes.length >= 2 && (
          <p className="hint small">No manual wires — engine auto-wires modules on compile.</p>
        )}
        {manualRetries > 0 && (
          <p className="hint small">Manual DRC retries this session: {manualRetries}</p>
        )}
        {composeError && <p className="error small">{composeError}</p>}
        {catalogError && <p className="error small">{catalogError}</p>}
      </header>

      <div className="design-studio__workspace design-studio__workspace--with-drc">
        <div className="studio-library-host">
          <ModuleLibrary modules={modules} onAdd={addModule} disabled={disabled} />
          <div className="studio-drag-hint muted small">
            Tip: drag library rows onto the canvas
            <div className="studio-drag-list">
              {modules.slice(0, 6).map((row) => (
                <button
                  key={row.id}
                  type="button"
                  className="studio-drag-chip"
                  draggable={!disabled}
                  onDragStart={(e) => handleLibraryDragStart(e, row)}
                  onClick={() => addModule(row)}
                  disabled={disabled}
                >
                  {row.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <StudioCanvas
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          setNodes={setNodes}
          setEdges={setEdges}
          onSelectionChange={({ nodes: picked }) => setSelectedIds(picked.map((n) => n.id))}
          disabled={disabled}
        />

        <StudioDrcPanel
          drc={drcState}
          agentSteps={agentSteps}
          compiling={compiling}
          onAutoFix={handleAutoFix}
          onOpenProject={(drc) => onOpenProject?.({ composeResult, drc })}
          onDismiss={() => {
            setDrcState(null);
            setComposeResult(null);
          }}
        />
      </div>
    </div>
  );
}

export default function DesignStudioPanel(props) {
  return (
    <ReactFlowProvider>
      <DesignStudioInner {...props} />
    </ReactFlowProvider>
  );
}
