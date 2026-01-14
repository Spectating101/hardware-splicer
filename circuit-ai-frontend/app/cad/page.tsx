"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { PcbGeometry, ValidateKiCadResponse, ValidationIssue } from "@/lib/cad-types";
import { demoValidation } from "@/lib/cad-demo";
import { cadTemplates, type CadTemplate } from "@/lib/cad-templates";
import {
  createProject,
  getActiveProjectId,
  loadProjects,
  saveProjects,
  setActiveProjectId,
  touchProject,
  upsertProject,
  type CadProject,
} from "@/lib/cad-project";
import { PcbViewport } from "@/components/cad/pcb-viewport";
import { IssuesPanel } from "@/components/cad/issues-panel";
import { TreePanel } from "@/components/cad/tree-panel";
import { Button } from "@/components/ui/button";

function pickRefFromComponent(component: string, geometry: PcbGeometry | null): string | null {
  if (!geometry) return null;
  const m = (component || "").toUpperCase().match(/\b[A-Z]{1,3}\d{1,4}\b/);
  if (!m) return null;
  const ref = m[0];
  return geometry.footprints.some((f) => f.ref.toUpperCase() === ref) ? ref : null;
}

function pickNetFromComponent(component: string, geometry: PcbGeometry | null): string | null {
  if (!geometry) return null;
  const c = (component || "").toUpperCase();
  for (const n of geometry.nets) {
    const name = (n.name || "").toUpperCase();
    if (name && name.length >= 2 && c.includes(name)) return n.name;
  }
  return null;
}

export default function CadWorkspacePage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [pcbFile, setPcbFile] = useState<File | null>(null);
  const [netFile, setNetFile] = useState<File | null>(null);
  const [activeFileKind, setActiveFileKind] = useState<"pcb" | "net">("pcb");
  const [geometry, setGeometry] = useState<PcbGeometry | null>(null);
  const [issues, setIssues] = useState<ValidationIssue[]>([]);
  const [nextSteps, setNextSteps] = useState<string[]>([]);
  const [status, setStatus] = useState<string>("idle");
  const [manufacturingReady, setManufacturingReady] = useState<boolean>(false);
  const [selectedRef, setSelectedRef] = useState<string | undefined>(undefined);
  const [rawResponse, setRawResponse] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [selectedNet, setSelectedNet] = useState<string | undefined>(undefined);
  const [projects, setProjects] = useState<CadProject[]>([]);
  const [activeProject, setActiveProject] = useState<CadProject | null>(null);
  const [showStart, setShowStart] = useState(true);
  const [starterChecklist, setStarterChecklist] = useState<string[]>([]);
  const [defaultHints, setDefaultHints] = useState<Record<string, unknown> | null>(null);
  const [activeTemplateId, setActiveTemplateId] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState<string>("");
  const [lastGerberFilename, setLastGerberFilename] = useState<string | null>(null);

  const activeFile = useMemo(() => (activeFileKind === "pcb" ? pcbFile : netFile), [activeFileKind, pcbFile, netFile]);

  const headerStatus = useMemo(() => {
    if (busy) return "Validating…";
    if (status === "idle") return "Ready";
    return status;
  }, [busy, status]);

  useEffect(() => {
    const ps = loadProjects();
    setProjects(ps);
    const activeId = getActiveProjectId();
    const p = (activeId && ps.find((x) => x.id === activeId)) || ps[0] || null;
    if (p) {
      const t = touchProject(p);
      const next = upsertProject(ps, t);
      saveProjects(next);
      setProjects(next);
      setActiveProject(t);
      setShowStart(false);
    } else {
      setShowStart(true);
    }
  }, []);

  function resetWorkspace() {
    setPcbFile(null);
    setNetFile(null);
    setActiveFileKind("pcb");
    setGeometry(null);
    setIssues([]);
    setNextSteps([]);
    setSelectedRef(undefined);
    setSelectedNet(undefined);
    setRawResponse(null);
    setStatus("idle");
    setManufacturingReady(false);
    setStarterChecklist([]);
    setDefaultHints(null);
    setActiveTemplateId(null);
    setExportStatus("");
    setLastGerberFilename(null);
  }

  async function loadPublicFile(path: string, filename: string): Promise<File> {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`Failed to load ${path}`);
    const blob = await res.blob();
    return new File([blob], filename, { type: "text/plain" });
  }

  function createAndActivateProject(name: string, source: CadProject["source"]) {
    const p = createProject(name.trim(), source);
    const next = upsertProject(projects, p);
    saveProjects(next);
    setProjects(next);
    setActiveProject(p);
    setActiveProjectId(p.id);
    resetWorkspace();
    setShowStart(false);
  }

  function startNewProject(source: CadProject["source"]) {
    const name = window.prompt("Project name?", source.type === "demo" ? "Demo Board" : source.type === "template" ? "Template Project" : "New Project");
    if (!name) return;
    const p = createProject(name.trim(), source);
    const next = upsertProject(projects, p);
    saveProjects(next);
    setProjects(next);
    setActiveProject(p);
    setActiveProjectId(p.id);
    resetWorkspace();
    setShowStart(false);
  }

  async function validate(fileOverride?: File): Promise<ValidateKiCadResponse | null> {
    const file = fileOverride ?? activeFile;
    if (!file) return null;
    setBusy(true);
    setStatus("running");
    try {
      if (backendOk === null) {
        try {
          const health = await fetch("/api/proxy/health", { method: "GET" });
          setBackendOk(health.ok);
        } catch {
          setBackendOk(false);
        }
      }
      const fd = new FormData();
      fd.set("kicad_file", file, file.name);
      if (defaultHints) fd.set("hints", JSON.stringify(defaultHints));
      const res = await fetch("/api/proxy/validate-kicad", { method: "POST", body: fd });
      const json = (await res.json()) as ValidateKiCadResponse;
      setRawResponse(json);
      setStatus(json.status || "done");
      setManufacturingReady(Boolean(json.manufacturing_ready));
      setNextSteps(json.next_steps || []);
      setIssues(json.validation?.issues || []);
      setGeometry(json.pcb_geometry ?? null);
      if (json.pcb_geometry?.footprints?.length) setSelectedRef(json.pcb_geometry.footprints[0].ref);
      setSelectedNet(undefined);

      if (activeProject) {
        const updated: CadProject = {
          ...activeProject,
          lastOpenedAt: new Date().toISOString(),
          source: { type: "kicad", filename: file.name },
        };
        const next = upsertProject(projects, updated);
        saveProjects(next);
        setProjects(next);
        setActiveProject(updated);
        setActiveProjectId(updated.id);
      }
      return json;
    } catch (e: any) {
      setStatus("error");
      setRawResponse({ error: String(e?.message || e) });
      return null;
    } finally {
      setBusy(false);
    }
  }

  function focusComponent(component: string, g: PcbGeometry | null) {
    const ref = pickRefFromComponent(component, g);
    if (ref) {
      setSelectedRef(ref);
      setSelectedNet(undefined);
      return;
    }
    const net = pickNetFromComponent(component, g);
    if (net) setSelectedNet(net);
  }

  async function loadTemplateSample(t: CadTemplate, mode: "load" | "guided") {
    if (!t.sampleFiles) return;

    setExportStatus("");
    setLastGerberFilename(null);

    createAndActivateProject(t.productName ?? t.name, t.source);
    setStarterChecklist(t.starterChecklist);
    setDefaultHints(t.defaultHints ?? null);
    setActiveTemplateId(t.id);

    try {
      const pcb = await loadPublicFile(t.sampleFiles.pcbPath, t.sampleFiles.pcbFilename);
      const net = await loadPublicFile(t.sampleFiles.netPath, t.sampleFiles.netFilename);
      setPcbFile(pcb);
      setNetFile(net);
      setActiveFileKind("pcb");
      setExportStatus(mode === "guided" ? "Sample loaded. Running Validate…" : "Sample loaded. Run Validate, then export Gerbers/BOM.");
      setShowStart(false);

      if (mode === "guided") {
        const res = await validate(pcb);
        if (!res) {
          setExportStatus("Validate failed — start the backend at http://localhost:5000 and try again.");
          return;
        }
        const g = res?.pcb_geometry ?? null;
        const firstIssue = res?.validation?.issues?.[0];
        if (firstIssue) focusComponent(firstIssue.component, g);
        setExportStatus(firstIssue ? "Validated. Focused first issue — click more issues, then export Gerbers/BOM." : "Validated — no issues returned. Try exporting Gerbers/BOM.");
      }
    } catch (e: any) {
      setExportStatus(`Failed to load sample: ${String(e?.message || e)}`);
    }
  }

  async function exportGerbers() {
    if (!pcbFile) return;
    if (!pcbFile.name.toLowerCase().endsWith(".kicad_pcb")) {
      setExportStatus("Gerber export requires a .kicad_pcb file.");
      return;
    }
    setExportStatus("Generating Gerbers…");
    setLastGerberFilename(null);
    try {
      const fd = new FormData();
      fd.set("pcb_file", pcbFile, pcbFile.name);
      fd.set("quantity", "5");
      const res = await fetch("/api/proxy/manufacture/gerber", { method: "POST", body: fd });
      const json = await res.json();
      if (!res.ok) {
        setExportStatus(json?.error ? `Gerber export failed: ${json.error}` : "Gerber export failed.");
        return;
      }
      const zipFile: string | undefined = json?.zip_file;
      const filename = zipFile ? String(zipFile).split("/").pop() : null;
      if (filename) {
        setLastGerberFilename(filename);
        setExportStatus(`Gerbers ready: ${filename}`);
      } else {
        setExportStatus("Gerbers generated (no ZIP filename returned).");
      }
      setRawResponse(json);
    } catch (e: any) {
      setExportStatus(`Gerber export error: ${String(e?.message || e)}`);
    }
  }

  async function exportBom(format: "json" | "csv") {
    if (!netFile) return;
    if (!netFile.name.toLowerCase().endsWith(".net")) {
      setExportStatus("BOM export requires a .net file for now.");
      return;
    }
    setExportStatus(`Generating BOM (${format.toUpperCase()})…`);
    try {
      const fd = new FormData();
      fd.set("netlist_file", netFile, netFile.name);
      fd.set("include_pricing", "false");
      fd.set("format", format);
      const res = await fetch("/api/proxy/manufacture/bom", { method: "POST", body: fd });
      if (!res.ok) {
        const text = await res.text();
        setExportStatus(`BOM export failed: ${text.slice(0, 200)}`);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = format === "csv" ? "bom.csv" : "bom.json";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setExportStatus(`BOM downloaded (${format.toUpperCase()}).`);
    } catch (e: any) {
      setExportStatus(`BOM export error: ${String(e?.message || e)}`);
    }
  }

  function loadDemo() {
    if (!activeProject) {
      startNewProject({ type: "demo" });
      return;
    }
    setRawResponse(demoValidation);
    setStatus(demoValidation.status);
    setManufacturingReady(demoValidation.manufacturing_ready);
    setNextSteps(demoValidation.next_steps);
    setIssues(demoValidation.validation.issues);
    setGeometry(demoValidation.pcb_geometry ?? null);
    setSelectedRef(demoValidation.pcb_geometry?.footprints?.[0]?.ref);
    setSelectedNet(undefined);
    setStarterChecklist([
      "Click issues to focus on-board",
      "Toggle layers/labels in the viewport",
      "Validate a real KiCad board when ready",
    ]);
    setDefaultHints(null);
    setActiveTemplateId(null);
    setExportStatus("");
    setLastGerberFilename(null);
    const updated: CadProject = {
      ...activeProject,
      lastOpenedAt: new Date().toISOString(),
      source: { type: "demo" },
    };
    const next = upsertProject(projects, updated);
    saveProjects(next);
    setProjects(next);
    setActiveProject(updated);
    setActiveProjectId(updated.id);
    setShowStart(false);
  }

  return (
    <div className="h-screen w-screen bg-[#070b14] text-white">
      <div className="flex h-12 items-center justify-between border-b border-white/10 bg-[#0b1220] px-3">
        <div className="flex items-center gap-2">
          <div className="text-sm font-semibold tracking-wide">Circuit-AI / Splicer</div>
          {activeProject ? (
            <div className="rounded border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-white/70">
              {activeProject.name}
            </div>
          ) : null}
          <div className="rounded border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-white/70">{headerStatus}</div>
          {backendOk !== null ? (
            <div
              className={`rounded border px-2 py-0.5 text-xs ${
                backendOk ? "border-emerald-400/20 bg-emerald-500/10 text-emerald-200" : "border-red-400/20 bg-red-500/10 text-red-200"
              }`}
            >
              API {backendOk ? "Connected" : "Offline"}
            </div>
          ) : null}
          {manufacturingReady ? (
            <div className="rounded border border-emerald-400/20 bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-200">
              Manufacturing Ready
            </div>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".kicad_pcb,.net"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              resetWorkspace();
              if (!f) return;
              if (f.name.toLowerCase().endsWith(".kicad_pcb")) {
                setPcbFile(f);
                setActiveFileKind("pcb");
              } else {
                setNetFile(f);
                setActiveFileKind("net");
              }
              if (!activeProject) startNewProject({ type: "kicad", filename: f.name });
            }}
          />
          <Button variant="outline" onClick={() => setShowStart(true)}>
            Project
          </Button>
          <Button variant="outline" onClick={() => fileInputRef.current?.click()}>
            Import KiCad
          </Button>
          <Button variant="secondary" disabled={!activeFile || busy} onClick={() => void validate()}>
            Validate
          </Button>
          <Button variant="outline" onClick={loadDemo}>
            Demo Board
          </Button>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => {
              const drone = cadTemplates.find((t) => t.id === "hero-drone-fc-power");
              if (!drone) return;
              void loadTemplateSample(drone, "guided");
            }}
          >
            Guided Drone
          </Button>
          <Button variant="outline" disabled={!pcbFile || busy} onClick={exportGerbers}>
            Export Gerbers
          </Button>
          <Button variant="outline" disabled={!netFile || busy} onClick={() => exportBom("json")}>
            Export BOM (JSON)
          </Button>
          <Button variant="outline" disabled={!netFile || busy} onClick={() => exportBom("csv")}>
            Export BOM (CSV)
          </Button>
        </div>
      </div>

      <div className="grid h-[calc(100vh-48px)] grid-cols-[280px_1fr_360px] grid-rows-[1fr_180px] gap-2 p-2">
        <div className="row-span-2">
          <TreePanel geometry={geometry} selectedRef={selectedRef} onSelectRef={(r) => setSelectedRef(r)} />
        </div>

        <div className="row-span-1">
          <PcbViewport
            geometry={geometry}
            issues={issues}
            selection={{ footprintRef: selectedRef, netName: selectedNet }}
            onSelectionChange={(s) => {
              setSelectedRef(s.footprintRef);
              setSelectedNet(undefined);
            }}
          />
        </div>

        <div className="row-span-2">
          <IssuesPanel
            issues={issues}
            onFocusComponent={(component) => {
              focusComponent(component, geometry);
            }}
          />
        </div>

        <div className="rounded-lg border border-white/10 bg-[#0b1220] p-3">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-white/90">Next steps</div>
            <div className="text-xs text-white/50">
              {activeFile ? `Active: ${activeFile.name}` : activeProject ? "No design imported" : "No project"}
            </div>
          </div>
          <div className="mt-2 flex h-[120px] gap-3">
            <div className="w-1/2 overflow-auto rounded border border-white/10 bg-white/5 p-2 text-xs text-white/70">
              {nextSteps.length === 0 && starterChecklist.length === 0 ? (
                <div className="text-white/50">Start a project to see the checklist.</div>
              ) : (
                <ol className="list-decimal pl-4">
                  {starterChecklist.map((s, i) => (
                    <li key={`c_${i}`} className="mb-1">
                      {s}
                    </li>
                  ))}
                  {nextSteps.map((s, i) => (
                    <li key={i} className="mb-1">
                      {s}
                    </li>
                  ))}
                </ol>
              )}
            </div>
            <div className="w-1/2 overflow-auto rounded border border-white/10 bg-white/5 p-2 text-[11px] text-white/70">
              <div className="mb-1 text-white/50">Context</div>
              {activeTemplateId ? (() => {
                const t = cadTemplates.find((x) => x.id === activeTemplateId);
                if (!t) return null;
                return (
                  <div className="mb-2 rounded border border-white/10 bg-black/20 p-2">
                    <div className="text-xs font-semibold text-white/85">{t.productName ?? t.name}</div>
                    <div className="mt-1 text-[11px] text-white/70">{t.productPitch ?? t.description}</div>
                    {t.demoNarration?.length ? (
                      <ul className="mt-2 list-disc pl-4 text-[11px] text-white/70">
                        {t.demoNarration.map((n, idx) => (
                          <li key={idx}>{n}</li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                );
              })() : null}
              <pre className="whitespace-pre-wrap break-words">
                {defaultHints ? JSON.stringify({ default_hints: defaultHints }, null, 2) : rawResponse ? JSON.stringify(rawResponse, null, 2) : "{}"}
              </pre>
            </div>
          </div>
          <div className="mt-2 flex items-center justify-between rounded border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/70">
            <div className="truncate">{exportStatus || "Exports: Gerbers (.kicad_pcb) or BOM (.net)"}</div>
            {lastGerberFilename ? (
              <button
                type="button"
                className="shrink-0 rounded border border-white/10 bg-black/30 px-2 py-1 text-xs text-white/80 hover:bg-black/45"
                onClick={() => {
                  window.location.href = `/api/proxy/manufacture/download-gerber/${encodeURIComponent(lastGerberFilename)}`;
                }}
              >
                Download ZIP
              </button>
            ) : null}
          </div>

          {(pcbFile && netFile) ? (
            <div className="mt-2 flex gap-2 text-xs">
              <button
                type="button"
                className={`rounded border px-2 py-1 ${activeFileKind === "pcb" ? "border-blue-400/30 bg-blue-500/10 text-blue-200" : "border-white/10 bg-white/5 text-white/70 hover:bg-white/10"}`}
                onClick={() => setActiveFileKind("pcb")}
              >
                Use PCB
              </button>
              <button
                type="button"
                className={`rounded border px-2 py-1 ${activeFileKind === "net" ? "border-blue-400/30 bg-blue-500/10 text-blue-200" : "border-white/10 bg-white/5 text-white/70 hover:bg-white/10"}`}
                onClick={() => setActiveFileKind("net")}
              >
                Use Netlist
              </button>
            </div>
          ) : null}
        </div>
      </div>

      {showStart ? (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/60 p-6">
          <div className="w-full max-w-2xl rounded-xl border border-white/10 bg-[#0b1220] p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-lg font-semibold">Start a project</div>
                <div className="mt-1 text-sm text-white/60">
                  The workspace is project-first. Create a project, then import KiCad or load the demo board.
                </div>
              </div>
              <button
                type="button"
                className="rounded-md border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/70 hover:bg-white/10"
                onClick={() => setShowStart(false)}
              >
                Close
              </button>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
              <button
                type="button"
                className="rounded-lg border border-white/10 bg-white/5 p-3 text-left hover:bg-white/10"
                onClick={() => startNewProject({ type: "blank" })}
              >
                <div className="text-sm font-semibold">New Project</div>
                <div className="mt-1 text-xs text-white/60">Start with an empty workspace.</div>
              </button>
              <button
                type="button"
                className="rounded-lg border border-white/10 bg-white/5 p-3 text-left hover:bg-white/10"
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="text-sm font-semibold">Import KiCad</div>
                <div className="mt-1 text-xs text-white/60">Bring in a `.kicad_pcb` and render it.</div>
              </button>
              <button
                type="button"
                className="rounded-lg border border-white/10 bg-white/5 p-3 text-left hover:bg-white/10"
                onClick={loadDemo}
              >
                <div className="text-sm font-semibold">Demo Project</div>
                <div className="mt-1 text-xs text-white/60">Instant board + issues for pitching.</div>
              </button>
            </div>

            <div className="mt-5">
              <div className="text-xs font-semibold text-white/60">Templates</div>
              <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                {cadTemplates.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className="rounded-lg border border-white/10 bg-white/5 p-3 text-left hover:bg-white/10"
                    onClick={() => {
                      startNewProject(t.source);
                      setStarterChecklist(t.starterChecklist);
                      setDefaultHints(t.defaultHints ?? null);
                      setActiveTemplateId(t.id);
                      setExportStatus("");
                      setLastGerberFilename(null);
                    }}
                  >
                    <div className="text-sm font-semibold">{t.name}</div>
                    <div className="mt-1 text-xs text-white/60">{t.description}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-5">
              <div className="text-xs font-semibold text-white/60">One-Click Products</div>
              <div className="mt-2 space-y-2">
                {cadTemplates
                  .filter((t) => Boolean(t.sampleFiles))
                  .slice()
                  .sort((a, b) => {
                    const rank = (t: CadTemplate) => (t.id === "hero-drone-fc-power" ? 0 : t.id.startsWith("hero-") ? 1 : 2);
                    return rank(a) - rank(b);
                  })
                  .map((t) => (
                    <div key={t.id} className="rounded-lg border border-white/10 bg-white/5 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold">{t.productName ?? t.name}</div>
                          <div className="mt-1 text-xs text-white/60">{t.description}</div>
                        </div>
                        <div className="flex shrink-0 gap-2">
                          <button
                            type="button"
                            className="rounded-md border border-white/10 bg-black/30 px-2 py-1 text-xs text-white/80 hover:bg-black/45"
                            onClick={() => void loadTemplateSample(t, "load")}
                          >
                            Load
                          </button>
                          <button
                            type="button"
                            className="rounded-md border border-emerald-400/20 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-200 hover:bg-emerald-500/15"
                            onClick={() => void loadTemplateSample(t, "guided")}
                          >
                            Guided
                          </button>
                        </div>
                      </div>
                      <div className="mt-2 text-[11px] text-white/55">
                        Loads `.kicad_pcb` + `.net` so Validate + Export work immediately.
                      </div>
                    </div>
                  ))}
              </div>
            </div>

            <div className="mt-5">
              <div className="text-xs font-semibold text-white/60">Recent projects</div>
              <div className="mt-2 max-h-36 overflow-auto rounded-lg border border-white/10">
                {projects.length === 0 ? (
                  <div className="p-3 text-sm text-white/60">No projects yet.</div>
                ) : (
                  projects.slice(0, 8).map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className="flex w-full items-center justify-between border-b border-white/10 bg-transparent px-3 py-2 text-left hover:bg-white/5 last:border-b-0"
                      onClick={() => {
                        const t = touchProject(p);
                        const next = upsertProject(projects, t);
                        saveProjects(next);
                        setProjects(next);
                        setActiveProject(t);
                        setActiveProjectId(t.id);
                        resetWorkspace();
                        setShowStart(false);
                      }}
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-white/85">{p.name}</div>
                        <div className="truncate text-xs text-white/50">
                          {p.source.type === "kicad"
                            ? `KiCad: ${p.source.filename}`
                            : p.source.type === "demo"
                              ? "Demo"
                              : p.source.type === "template"
                                ? `Template: ${p.source.templateId}`
                                : "Blank"}
                        </div>
                      </div>
                      <div className="text-xs text-white/40">{new Date(p.lastOpenedAt).toLocaleString()}</div>
                    </button>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
