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
        wrot_deg: p.wrot_deg,
        shape: p.shape,
        size_w_mm: p.size_w_mm,
        size_h_mm: p.size_h_mm,
        drill_mm: p.drill_mm,
        roundrect_ratio: p.roundrect_ratio,
        type: p.type,
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
    zones: info.zones.map((z) => ({
      layer: z.layer,
      net_id: z.net_id,
      net_name: z.net_name,
      polygons: z.polygons,
    })),
    silkLines: info.silkLines,
    silkArcs: info.silkArcs,
    silkText: info.silkText,
    edgeArcs: info.edgeArcs,
    edgeLines: info.edgeLines,
  };
}
import { BoardHeader } from "./board-header";
import { LayerPanel } from "./layer-panel";
import { JarvisPanel } from "./jarvis-panel";
import { DrcConsole } from "./drc-console";
import { EmptyState } from "./empty-state";
import { ShipPanel } from "./ship-panel";
import { SuggestionsTray } from "./suggestions-tray";
import { PcbViewport } from "@/components/cad/pcb-viewport";

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
        // Backend geometry is authoritative for nets/segments/zones, but the
        // Python side doesn't emit silkscreen or edge arcs yet. Re-attach
        // those from the local parse so the board doesn't go silent.
        const localGeom = boardInfoToGeometry(localInfo);
        store.setGeometry({
          ...json.pcb_geometry,
          silkLines: json.pcb_geometry.silkLines ?? localGeom.silkLines,
          silkArcs: json.pcb_geometry.silkArcs ?? localGeom.silkArcs,
          silkText: json.pcb_geometry.silkText ?? localGeom.silkText,
          edgeArcs: json.pcb_geometry.edgeArcs ?? localGeom.edgeArcs,
          edgeLines: json.pcb_geometry.edgeLines ?? localGeom.edgeLines,
          zones: json.pcb_geometry.zones ?? localGeom.zones,
        });
      }

      store.setValidationResult(issues, score, nextSteps, dfmNotes);
      store.setAnalysis({
        dcAnalysis: json.dc_analysis ?? null,
        thermal: json.thermal ?? null,
        bomRisk: json.bom_risk ?? null,
      });
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
      store.setAnalysis({
        dcAnalysis: json.dc_analysis ?? null,
        thermal: json.thermal ?? null,
        bomRisk: json.bom_risk ?? null,
      });
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

  // ── Ship-mode handlers: BOM pricing, DFM, PnP, full package ────────────────

  const handlePrice = useCallback(async () => {
    if (!store.geometry) return;
    store.addJarvisMessage({ role: "jarvis", text: "Pricing BOM via `/api/v2/manufacture/bom` + `/api/pricing/component`…" });
    try {
      const res = await fetch("/api/proxy/manufacture/bom", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ filename: store.filename, qty: 5 }),
      });
      const json = await res.json().catch(() => ({} as { unit_usd?: number; total_usd?: number; lead_days?: number; qty?: number; error?: string }));
      if (!res.ok || json.error) {
        store.addJarvisMessage({ role: "jarvis", text: `Pricing unavailable — backend returned ${json.error ?? res.status}. Ensure Circuit-AI server is running on :5000.` });
        return;
      }
      const unitUsd = Number(json.unit_usd) || 0;
      const qty = Number(json.qty) || 5;
      const totalUsd = Number(json.total_usd) || unitUsd * qty;
      const leadDays = Number(json.lead_days) || 9;
      store.setBomCost({ unitUsd, qty, totalUsd, leadDays });
      store.addJarvisMessage({ role: "jarvis", text: `BOM priced — **$${totalUsd.toFixed(2)}** for ${qty} boards, ${leadDays}-day lead.` });
    } catch {
      store.addJarvisMessage({ role: "jarvis", text: "Network error pricing BOM." });
    }
  }, [store]);

  const handleDfm = useCallback(async () => {
    if (!store.file) return;
    store.addJarvisMessage({ role: "jarvis", text: "Running DFM check via `/api/v2/report/dfm`…" });
    try {
      const fd = new FormData();
      fd.set("pcb_file", store.file, store.file.name);
      const res = await fetch("/api/proxy/report/dfm", { method: "POST", body: fd });
      const json = await res.json().catch(() => ({} as { score?: number; critical?: number; warnings?: number; fab?: string; error?: string }));
      if (!res.ok || json.error) {
        store.addJarvisMessage({ role: "jarvis", text: `DFM check unavailable — ${json.error ?? res.status}.` });
        return;
      }
      const score = Number(json.score) || 0;
      const critical = Number(json.critical) || 0;
      const warnings = Number(json.warnings) || 0;
      store.setDfmReport({ score, critical, warnings, fab: json.fab });
      store.addJarvisMessage({ role: "jarvis", text: `DFM: **${score}/100**${critical ? ` — ${critical} critical` : ""}${warnings ? `, ${warnings} warnings` : ""}.` });
    } catch {
      store.addJarvisMessage({ role: "jarvis", text: "Network error running DFM." });
    }
  }, [store]);

  const handlePnp = useCallback(async () => {
    if (!store.file) return;
    store.addJarvisMessage({ role: "jarvis", text: "Generating pick-and-place via `/api/v2/manufacture/pnp`…" });
    try {
      const fd = new FormData();
      fd.set("pcb_file", store.file, store.file.name);
      const res = await fetch("/api/proxy/manufacture/pnp", { method: "POST", body: fd });
      const json = await res.json().catch(() => ({} as { file?: string; error?: string }));
      if (!res.ok || json.error) {
        store.addJarvisMessage({ role: "jarvis", text: `PnP failed — ${json.error ?? res.status}.` });
        return;
      }
      store.addJarvisMessage({ role: "jarvis", text: `PnP file ready — ${json.file ?? "see backend reports dir"}.` });
    } catch {
      store.addJarvisMessage({ role: "jarvis", text: "Network error generating PnP." });
    }
  }, [store]);

  const handlePackage = useCallback(async () => {
    if (!store.file) return;
    store.setPipelineFlag("manufacturing", true);
    store.addJarvisMessage({ role: "jarvis", text: "Building full fab package via `/api/v2/manufacture/package`…" });
    try {
      const fd = new FormData();
      fd.set("pcb_file", store.file, store.file.name);
      const res = await fetch("/api/proxy/manufacture/package", { method: "POST", body: fd });
      const json = await res.json().catch(() => ({} as { zip_file?: string; error?: string }));
      if (!res.ok || json.error) {
        store.setPipelineFlag("manufacturing", false);
        store.addJarvisMessage({ role: "jarvis", text: `Package failed — ${json.error ?? res.status}.` });
        return;
      }
      store.setManufactured();
      const filename = json.zip_file ? String(json.zip_file).split("/").pop() : null;
      if (filename) {
        const a = document.createElement("a");
        a.href = `/api/proxy/manufacture/download-package/${encodeURIComponent(filename)}`;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
      }
      store.addJarvisMessage({ role: "jarvis", text: `Fab package ready — **${filename ?? "zip"}**.` });
    } catch {
      store.setPipelineFlag("manufacturing", false);
      store.addJarvisMessage({ role: "jarvis", text: "Network error building fab package." });
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
        componentCount={store.geometry?.footprints.length ?? 0}
        spiceResult={store.spiceResult}
        dfmReport={store.dfmReport}
        bomCost={store.bomCost}
        renderMode={store.renderMode}
        mode={store.mode}
        onSetRenderMode={store.setRenderMode}
        onSetMode={store.setMode}
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
          lenses={store.lenses}
          selectedRef={store.selectedRef}
          availability={{
            voltage: !!store.dcAnalysis?.node_voltages,
            current: !!store.dcAnalysis?.branch_currents,
            thermal: !!store.thermal,
            bom: !!store.bomRisk,
          }}
          onToggleLens={store.toggleLens}
          onSetLens={store.setLens}
          onSelectRef={store.setSelectedRef}
        />

        {/* Canvas — 3D board + onboarding doors when empty. */}
        <div className="flex-1 relative overflow-hidden cursor-default">
          <PcbViewport
            geometry={store.geometry}
            issues={store.issues}
            selection={{
              footprintRef: store.selectedRef,
              netId: store.selectedNet ? Number(store.selectedNet) || null : null,
            }}
            onSelectionChange={(s) => {
              store.setSelectedRef(s.footprintRef);
              if (s.netId !== undefined) {
                store.setSelectedNet(s.netId != null ? String(s.netId) : null);
              }
              // If the clicked component has issues, auto-open the DRC drawer so
              // the spatial halo and the issue list are linked in one glance.
              if (s.footprintRef && !store.drcOpen) {
                const hit = store.issues.some((issue) => {
                  const ref = (issue as unknown as { component_ref?: string; ref?: string }).component_ref ?? (issue as unknown as { ref?: string }).ref;
                  return ref === s.footprintRef;
                });
                if (hit) store.toggleDrc();
              }
            }}
            lenses={store.lenses}
            dcAnalysis={store.dcAnalysis}
            thermal={store.thermal}
            bomRisk={store.bomRisk}
            renderMode={store.renderMode}
          />
          {store.mode === "iterate" && store.geometry && (
            <SuggestionsTray
              ready={store.pipeline.validated}
              filename={store.filename}
              onMessage={(role, text) => store.addJarvisMessage({ role, text })}
              onHighlight={(ref) => store.setSelectedRef(ref)}
            />
          )}
          {!store.geometry && !store.pipeline.parsed && (
            <EmptyState
              onOpenFile={() => fileInputRef.current?.click()}
              onDescribe={() => {
                store.addJarvisMessage({
                  role: "jarvis",
                  text: "Describe what you want to build in the chat — e.g. *\"battery-powered temperature logger with BLE, USB-C charging, 3 AA-equivalent runtime\"* — and I'll compile it into a starter board via the intake pipeline.",
                });
              }}
              onCatalog={() => {
                store.addJarvisMessage({
                  role: "jarvis",
                  text: "Template catalog coming online — ESP32 sensor nodes, buck converters, motor drivers. For now, drop any reference `.kicad_pcb` and I'll parse it.",
                });
              }}
              onLearn={() => {
                store.addJarvisMessage({
                  role: "jarvis",
                  text: "Learning paths wired to `/api/learning-paths` — from resistor basics through your first fab order. Which track interests you: *digital logic*, *analog sensors*, *power electronics*, or *RF*?",
                });
              }}
            />
          )}
        </div>

        {store.mode === "ship" ? (
          <ShipPanel
            geometry={store.geometry}
            filename={store.filename}
            pipeline={store.pipeline}
            spiceResult={store.spiceResult}
            dfmReport={store.dfmReport}
            bomCost={store.bomCost}
            onPrice={handlePrice}
            onDfm={handleDfm}
            onPackage={handlePackage}
            onGerber={handleManufacture}
            onPnp={handlePnp}
          />
        ) : (
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
            onRefChip={(r) => store.setSelectedRef(r)}
            onNetChip={(n) => store.setSelectedNet(n)}
            onIssueChip={() => {
              // Open the DRC drawer when a user clicks an [issue:N] chip.
              if (!store.drcOpen) store.toggleDrc();
            }}
          />
        )}
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
