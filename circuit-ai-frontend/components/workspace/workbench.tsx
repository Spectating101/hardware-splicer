"use client";

import { useEffect, useCallback, useRef, useState } from "react";
import { useWorkbenchStore } from "@/lib/workbench-store";
import { isProxyFailure } from "@/lib/proxy-client";
import type { PcbGeometry, ValidateKiCadResponse } from "@/lib/cad-types";
import { scoreFromIssues } from "@/lib/jarvis";
import { parseKicadPcb, generateAirwires, type KicadBoardInfo } from "@/lib/kicad-parser";

/** Convert lightweight frontend parse result to the PcbGeometry shape. */
function boardInfoToGeometry(info: KicadBoardInfo): PcbGeometry {
  const xs = info.components.map((c) => c.x);
  const ys = info.components.map((c) => c.y);
  const minX = xs.length ? Math.min(...xs) - 10 : 0;
  const minY = ys.length ? Math.min(...ys) - 10 : 0;
  const maxX = xs.length ? Math.max(...xs) + 10 : 100;
  const maxY = ys.length ? Math.max(...ys) + 10 : 100;

  // Keep any nets that have actually-routed segments so the LayerPanel net badge
  // reflects reality, but also include the full net table the parser found.
  const routedNetIds = new Set(info.segments.map((s) => s.net_id));

  // Airwires for nets without (enough) routed coverage. Even partially-routed
  // nets get airwires between all their pads — at worst a few overlap, which is
  // still less confusing than a board that looks like disconnected squares.
  const airwires = generateAirwires(info.components);

  const segments = [
    ...info.segments.map((s) => ({
      start: s.start,
      end: s.end,
      width_mm: s.width_mm,
      layer: s.layer,
      net: { id: s.net_id, name: s.net_name },
    })),
    ...airwires
      .filter((a) => !routedNetIds.has(a.net_id)) // only show airwires for UNrouted nets
      .map((a) => ({
        start: a.start,
        end: a.end,
        width_mm: a.width_mm,
        layer: a.layer,
        net: { id: a.net_id, name: a.net_name },
      })),
  ];

  return {
    board: {
      bbox_mm: {
        min_x: minX, min_y: minY,
        max_x: maxX, max_y: maxY,
        width: maxX - minX, height: maxY - minY,
      },
    },
    nets: info.nets,
    footprints: info.components.map((c) => ({
      ref: c.ref,
      value: c.value,
      footprint: c.footprint,
      layer: c.layer,
      at: { x: c.x, y: c.y, rot_deg: c.rot_deg },
      pads: c.pads.map((p) => ({
        num: p.num,
        wx: p.wx,
        wy: p.wy,
        net: { id: p.netId, name: p.netName },
      })),
    })),
    segments,
    vias: info.vias.map((v) => ({
      x: v.x,
      y: v.y,
      size_mm: v.size_mm,
      drill_mm: v.drill_mm,
      net: { id: v.net_id, name: info.nets.find((n) => n.id === v.net_id)?.name ?? "" },
    })),
  };
}
import { BoardHeader } from "./board-header";
import { LayerPanel } from "./layer-panel";
import { BoardCanvas } from "./board-canvas";
import { JarvisPanel } from "./jarvis-panel";
import { DrcConsole } from "./drc-console";

const DFM_KEYWORDS = /(tolerance|clearance|assembly|thermal|mechanical|stress|via|drill|fab|solder|annular|keepout|courtyard|silk|mask)/i;

function extractDfmNotes(nextSteps: string[]): string[] {
  return nextSteps.filter((s) => DFM_KEYWORDS.test(s));
}

export function Workbench() {
  const store = useWorkbenchStore();
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // JARVIS greeting on first load
  useEffect(() => {
    if (store.jarvisMessages.length === 0) {
      store.addJarvisMessage({
        role: "jarvis",
        text: "Drop your `.kicad_pcb` file on the canvas or click to browse. I'll parse the board, run validation, and walk you through every issue — mechanical and electrical.",
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── File handling ──────────────────────────────────────────────────────────

  const processFile = useCallback(async (file: File) => {
    store.loadFile(file, file.name);
    store.addJarvisMessage({
      role: "jarvis",
      text: `Parsing **${file.name}**… sending to validation pipeline.`,
    });

    // ── Step 1: Local parse for instant board rendering ─────────────────────
    const text = await file.text();
    const localInfo = parseKicadPcb(text);
    if (localInfo.components.length > 0) {
      store.setGeometry(boardInfoToGeometry(localInfo));
    }

    store.setJarvisThinking(true);
    store.setPipelineFlag("validating", true);

    try {
      const fd = new FormData();
      fd.set("kicad_file", file, file.name);
      const res = await fetch("/api/proxy/validate-kicad", { method: "POST", body: fd });
      const json: ValidateKiCadResponse & { error?: string } = await res.json();

      if (!res.ok || isProxyFailure(json)) {
        store.setJarvisThinking(false);
        store.setPipelineFlag("validating", false);
        store.addJarvisMessage({
          role: "jarvis",
          text: `**${localInfo.componentCount} components** parsed from ${file.name}. Backend unavailable — validation requires the Circuit-AI server on port 5000. The board is rendered from local parse.`,
        });
        return;
      }

      const issues = json.validation?.issues ?? [];
      const score = scoreFromIssues(issues);
      const nextSteps = json.next_steps ?? [];
      const dfmNotes = extractDfmNotes(nextSteps);
      const critCount = issues.filter((i) => {
        const s = String(i.severity).toLowerCase();
        return s === "critical" || s === "error";
      }).length;

      if (json.pcb_geometry) {
        store.setGeometry(json.pcb_geometry);
      }

      store.setValidationResult(issues, score, nextSteps, dfmNotes);
      store.setJarvisThinking(false);

      const statusLine =
        issues.length === 0
          ? `Board parsed and validated — **${score}/100**, no issues found. Ready to manufacture.`
          : critCount > 0
          ? `Validation complete: **${score}/100** — **${critCount} critical issue${critCount > 1 ? "s" : ""}** need attention before ordering.`
          : `Validation complete: **${score}/100** — ${issues.length} issue${issues.length > 1 ? "s" : ""} found, no blockers.`;

      store.addJarvisMessage({ role: "jarvis", text: statusLine });
    } catch {
      store.setJarvisThinking(false);
      store.setPipelineFlag("validating", false);
      store.addJarvisMessage({
        role: "jarvis",
        text: "Network error reaching the backend. Check that the Circuit-AI server is running.",
      });
    }
  }, [store]);

  // ── Drag-and-drop ──────────────────────────────────────────────────────────

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => setDragOver(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = Array.from(e.dataTransfer.files).find(
      (f) => f.name.endsWith(".kicad_pcb") || f.name.endsWith(".kicad_sch")
    );
    if (file) processFile(file);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
    e.target.value = "";
  };

  // ── Validate action ────────────────────────────────────────────────────────

  const handleValidate = useCallback(async () => {
    if (!store.file) {
      store.addJarvisMessage({ role: "jarvis", text: "No file loaded. Drop a `.kicad_pcb` file first." });
      return;
    }
    store.setPipelineFlag("validating", true);
    store.setJarvisThinking(true);
    store.addJarvisMessage({ role: "jarvis", text: "Re-running validation…" });

    try {
      const fd = new FormData();
      fd.set("kicad_file", store.file, store.file.name);
      const res = await fetch("/api/proxy/validate-kicad", { method: "POST", body: fd });
      const json: ValidateKiCadResponse & { error?: string } = await res.json();

      if (!res.ok || isProxyFailure(json)) {
        store.setPipelineFlag("validating", false);
        store.setJarvisThinking(false);
        store.addJarvisMessage({ role: "jarvis", text: "Validation failed — backend error." });
        return;
      }

      const issues = json.validation?.issues ?? [];
      const score = scoreFromIssues(issues);
      const nextSteps = json.next_steps ?? [];
      const dfmNotes = extractDfmNotes(nextSteps);
      const critCount = issues.filter((i) => {
        const s = String(i.severity).toLowerCase();
        return s === "critical" || s === "error";
      }).length;

      if (json.pcb_geometry) store.setGeometry(json.pcb_geometry);
      store.setValidationResult(issues, score, nextSteps, dfmNotes);
      store.setJarvisThinking(false);

      store.addJarvisMessage({
        role: "jarvis",
        text:
          critCount > 0
            ? `Score **${score}/100** — ${critCount} critical issue${critCount > 1 ? "s" : ""} blocking manufacture.`
            : issues.length === 0
            ? `Score **${score}/100** — clean. Ready to package for manufacturing.`
            : `Score **${score}/100** — ${issues.length} warning${issues.length > 1 ? "s" : ""}, no blockers.`,
      });
    } catch {
      store.setPipelineFlag("validating", false);
      store.setJarvisThinking(false);
      store.addJarvisMessage({ role: "jarvis", text: "Network error during validation." });
    }
  }, [store]);

  // ── Manufacture action ─────────────────────────────────────────────────────

  const handleManufacture = useCallback(async () => {
    if (!store.file) return;
    store.setPipelineFlag("manufacturing", true);
    store.setJarvisThinking(true);
    store.addJarvisMessage({ role: "jarvis", text: "Generating Gerbers via Circuit-AI fab pipeline…" });

    try {
      const fd = new FormData();
      fd.set("pcb_file", store.file, store.file.name);
      fd.set("quantity", "5");
      const res = await fetch("/api/proxy/manufacture/gerber", { method: "POST", body: fd });
      const payload = await res.json();

      if (!res.ok || payload?.error) {
        store.setPipelineFlag("manufacturing", false);
        store.setJarvisThinking(false);
        store.addJarvisMessage({
          role: "jarvis",
          text: payload?.error
            ? `Gerber export failed: ${payload.error}`
            : "Gerber export failed — is the Circuit-AI backend running on port 5000?",
        });
        return;
      }

      const zipFile: string | undefined = payload?.zip_file;
      const filename = zipFile ? String(zipFile).split("/").pop() : null;

      if (filename) {
        // Trigger download via the existing download-gerber route
        const a = document.createElement("a");
        a.href = `/api/proxy/manufacture/download-gerber/${encodeURIComponent(filename)}`;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
      }

      store.setManufactured();
      store.setJarvisThinking(false);
      store.addJarvisMessage({
        role: "jarvis",
        text: filename
          ? `Gerbers ready — **${filename}**. Upload the zip to JLCPCB, PCBWay, or OSH Park. Quantity defaulted to 5; I can re-run with any qty you like.`
          : "Gerbers generated on the backend. Check the reports directory on the Circuit-AI server.",
      });
    } catch (err) {
      store.setPipelineFlag("manufacturing", false);
      store.setJarvisThinking(false);
      const msg = err instanceof Error ? err.message : String(err);
      store.addJarvisMessage({ role: "jarvis", text: `Network error generating Gerbers: ${msg}` });
    }
  }, [store]);

  // ── Focus component ────────────────────────────────────────────────────────

  const handleFocusComponent = useCallback((ref: string) => {
    // Extract ref designator pattern from string (e.g. "U1" from "U1 (ESP32)")
    const match = ref.match(/\b[A-Z]{1,3}\d+\b/);
    if (match) store.setSelectedRef(match[0]);
  }, [store]);

  // ── Critical count ─────────────────────────────────────────────────────────
  const criticalCount = store.issues.filter((i) => {
    const s = String(i.severity).toLowerCase();
    return s === "critical" || s === "error";
  }).length;

  return (
    <div
      className="h-screen flex flex-col bg-[#080e1a] overflow-hidden"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".kicad_pcb,.kicad_sch"
        className="hidden"
        onChange={handleFileInput}
      />

      {/* Drag overlay */}
      {dragOver && (
        <div className="absolute inset-0 z-50 bg-cyan-500/10 border-2 border-dashed border-cyan-500/50 flex items-center justify-center pointer-events-none">
          <div className="text-center">
            <p className="text-cyan-300 text-lg font-semibold">Drop .kicad_pcb here</p>
            <p className="text-cyan-400/60 text-sm mt-1">I&apos;ll parse and validate it immediately</p>
          </div>
        </div>
      )}

      {/* Header */}
      <BoardHeader
        filename={store.filename}
        pipeline={store.pipeline}
        healthScore={store.healthScore}
        issueCount={store.issues.length}
        criticalCount={criticalCount}
        onValidate={handleValidate}
        onManufacture={handleManufacture}
        onNew={() => {
          store.reset();
          fileInputRef.current?.click();
        }}
      />

      {/* Main body */}
      <div className="flex-1 flex overflow-hidden">
        <LayerPanel
          geometry={store.geometry}
          layers={store.layers}
          selectedRef={store.selectedRef}
          onToggleLayer={store.toggleLayer}
          onSelectRef={store.setSelectedRef}
        />

        {/* Canvas — also acts as file drop target with click-to-browse */}
        <div
          className="flex-1 relative overflow-hidden cursor-default"
          onClick={() => {
            if (!store.geometry && !store.pipeline.parsed) {
              fileInputRef.current?.click();
            }
          }}
        >
          <BoardCanvas
            geometry={store.geometry}
            layers={store.layers}
            selectedRef={store.selectedRef}
            onSelectRef={store.setSelectedRef}
            filename={store.filename}
          />
        </div>

        <JarvisPanel
          geometry={store.geometry}
          filename={store.filename}
          issues={store.issues}
          healthScore={store.healthScore}
          dfmNotes={store.dfmNotes}
          nextSteps={store.nextSteps}
          messages={store.jarvisMessages}
          thinking={store.jarvisThinking}
          pipeline={store.pipeline}
          selectedRef={store.selectedRef}
          onAddMessage={store.addJarvisMessage}
          onSetThinking={store.setJarvisThinking}
          onValidate={handleValidate}
          onManufacture={handleManufacture}
        />
      </div>

      {/* DRC console bottom rail */}
      <DrcConsole
        issues={store.issues}
        validating={store.pipeline.validating}
        validated={store.pipeline.validated}
        onValidate={handleValidate}
        onFocusComponent={handleFocusComponent}
      />
    </div>
  );
}
