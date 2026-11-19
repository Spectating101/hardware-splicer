"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { PcbGeometry, ValidateKiCadResponse, ValidationIssue } from "@/lib/cad-types";
import { demoValidation } from "@/lib/cad-demo";
import { 
  createProject, 
  getActiveProjectId, 
  loadProjects, 
  saveProjects, 
  setActiveProjectId, 
  touchProject, 
  upsertProject, 
  type CadProject 
} from "@/lib/cad-project";
import { PcbViewport } from "@/components/cad/pcb-viewport";
import { IssuesPanel } from "@/components/cad/issues-panel";
import { TreePanel } from "@/components/cad/tree-panel";
import { GlassPanel, FloatingToolbar } from "@/components/cad/spatial-ui";
import { 
  Files, 
  Search, 
  Cpu, 
  Settings, 
  Terminal, 
  Zap,
  Printer,
  Maximize2,
  Box,
  ChevronRight,
  ChevronDown,
  Layers,
  Activity,
  Command,
  Mic,
  X,
  Download
} from "lucide-react";

export default function CircuitAIWorkspace() {
  // --- STATE: LOGIC (ChatGPT) ---
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [geometry, setGeometry] = useState<PcbGeometry | null>(null);
  const [issues, setIssues] = useState<ValidationIssue[]>([]);
  const [status, setStatus] = useState<string>("idle");
  const [busy, setBusy] = useState(false);
  const [projects, setProjects] = useState<CadProject[]>([]);
  const [activeProject, setActiveProject] = useState<CadProject | null>(null);
  const [showStart, setShowStart] = useState(true);

  // --- STATE: UI (Gemini) ---
  const [activeView, setActiveView] = useState<"design" | "fab">("design");
  const [fabMode, setFabMode] = useState<"robot" | "manual">("manual");
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const [showPanels, setShowPanels] = useState(true);
  const [explodeFactor, setExplodeFactor] = useState(0);

  // --- EFFECT: Load Projects ---
  useEffect(() => {
    const ps = loadProjects();
    setProjects(ps);
    const activeId = getActiveProjectId();
    const p = (activeId && ps.find((x) => x.id === activeId)) || ps[0] || null;
    if (p) {
      setActiveProject(touchProject(p));
      setShowStart(false);
    }
  }, []);

  // --- HANDLERS: Logic ---
  const handleValidate = async () => {
    if (!file) return;
    setBusy(true);
    setStatus("validating");
    try {
      const fd = new FormData();
      fd.set("kicad_file", file, file.name);
      // Calls the PROXY route (secure)
      const res = await fetch("/api/proxy/validate-kicad", { method: "POST", body: fd });
      const json = await res.json();
      setGeometry(json.pcb_geometry);
      setIssues(json.validation?.issues || []);
      setStatus("done");
    } catch (e) {
      setStatus("error");
    } finally {
      setBusy(false);
    }
  };

  const handleLoadDemo = () => {
    const res = demoValidation();
    setGeometry(res.pcb_geometry);
    setIssues(res.validation.issues);
    setShowStart(false);
  };

  const startNewProject = (name: string) => {
    const p = createProject(name);
    const next = upsertProject(projects, p);
    saveProjects(next);
    setProjects(next);
    setActiveProject(p);
    setActiveProjectId(p.id);
    setShowStart(false);
  };

  // --- RENDER: Startup ---
  if (showStart) {
    return (
      <div className="h-screen w-screen bg-[#070b14] text-white flex items-center justify-center p-6 bg-[url('/grid.svg')]">
        <GlassPanel title="Circuit-AI / Welcome" className="w-full max-w-md p-6">
           <h1 className="text-2xl font-bold mb-2">New Mission</h1>
           <p className="text-sm text-white/40 mb-6">Autonomous Hardware Engineering Platform</p>
           <div className="space-y-3">
              <button onClick={() => startNewProject("New Design")} className="w-full py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-left px-4 flex items-center justify-between group">
                 <span>Create Blank Project</span>
                 <ChevronRight size={16} className="opacity-0 group-hover:opacity-100 transition-all" />
              </button>
              <button onClick={handleLoadDemo} className="w-full py-3 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 rounded-xl text-left px-4 flex items-center justify-between group">
                 <span className="text-blue-200">Load Intelligence Demo</span>
                 <Zap size={16} className="text-blue-400" />
              </button>
           </div>
        </GlassPanel>
      </div>
    );
  }

  return (
    <div className="relative h-screen w-screen bg-black overflow-hidden font-sans text-white/80 select-none">
      
      {/* 1. VIEWPORT (The World) */}
      <div className="absolute inset-0 z-0">
        <PcbViewport 
          geometry={geometry} 
          issues={issues}
          selection={{ footprintRef: selectedRef }}
          onSelectionChange={(s: any) => setSelectedRef(s.footprintRef)}
          explodeFactor={explodeFactor}
        />
      </div>

      {/* 2. COMMAND BAR */}
      <div className="absolute top-6 left-1/2 -translate-x-1/2 z-20 w-[600px] max-w-full px-4">
        <div className="backdrop-blur-xl bg-black/60 border border-white/10 rounded-xl shadow-2xl flex items-center px-4 py-3 gap-3">
          <Command size={18} className="text-white/40" />
          <input 
            type="text" 
            placeholder="Ask AI to analyze, route, or repair..." 
            className="bg-transparent border-none outline-none text-sm text-white w-full placeholder-white/30"
          />
          <input 
             type="file" 
             className="hidden" 
             ref={fileInputRef} 
             onChange={(e) => setFile(e.target.files?.[0] || null)} 
          />
          <button onClick={handleValidate} disabled={busy} className="bg-blue-600 text-white px-3 py-1 rounded-lg text-xs font-bold hover:bg-blue-500 disabled:opacity-50">
            {busy ? "Thinking..." : "Validate"}
          </button>
        </div>
      </div>

      {/* 3. SIDE PANELS */}
      {showPanels && (
        <>
          {/* Left: Explorer */}
          <GlassPanel title="Project Explorer" className="absolute top-24 left-6 bottom-32 w-72 z-10">
             {activeView === "design" ? (
               <TreePanel geometry={geometry} selectedRef={selectedRef} onSelectRef={setSelectedRef} />
             ) : (
               <div className="p-4 space-y-4">
                  <div className="text-xs font-bold text-orange-400 uppercase tracking-widest">Robot Control</div>
                  <div className="bg-white/5 p-3 rounded-lg border border-white/10">
                     <div className="text-[10px] text-white/40 uppercase">Arm Status</div>
                     <div className="text-sm font-mono text-emerald-400 font-bold">READY</div>
                  </div>
                  {/* Fab Mode Logic */}
                  {fabMode === "manual" ? (
                     <div className="text-xs text-white/60">
                        <p className="mb-2">Manual Guide Active:</p>
                        <ol className="list-decimal pl-4 space-y-1">
                           <li>Heat pad to 350C</li>
                           <li>Apply Flux</li>
                           <li>Remove Component</li>
                        </ol>
                     </div>
                  ) : (
                     <button className="w-full bg-orange-600 py-2 rounded-lg text-xs font-bold">Run Repair G-Code</button>
                  )}
               </div>
             )}
          </GlassPanel>

          {/* Right: Inspector / Issues */}
          <GlassPanel title={selectedRef ? "Inspector" : "Validation Issues"} className="absolute top-24 right-6 bottom-32 w-80 z-10">
             {selectedRef ? (
               <div className="p-4">
                  <div className="flex items-center gap-4 mb-6">
                     <div className="h-12 w-12 rounded bg-white/5 flex items-center justify-center"><Box className="text-blue-400" /></div>
                     <div><div className="text-lg font-bold">{selectedRef}</div><div className="text-xs text-white/40">Verified Component</div></div>
                  </div>
                  <button className="w-full py-2 bg-white/5 border border-white/10 rounded text-xs">Download Datasheet</button>
               </div>
             ) : (
               <IssuesPanel issues={issues} onFocusComponent={(c: any) => setSelectedRef(c)} />
             )}
          </GlassPanel>
        </>
      )}

      {/* 4. DOCK */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 flex flex-col gap-2 items-center">
        {activeView === "fab" && (
          <div className="flex bg-black/60 backdrop-blur-md rounded-full p-1 border border-white/10">
            <button onClick={() => setFabMode("manual")} className={`px-3 py-1 rounded-full text-[10px] font-bold ${fabMode === "manual" ? "bg-white text-black" : "text-white/50"}`}>MANUAL</button>
            <button onClick={() => setFabMode("robot")} className={`px-3 py-1 rounded-full text-[10px] font-bold ${fabMode === "robot" ? "bg-orange-600 text-white" : "text-white/50"}`}>ROBOT</button>
          </div>
        )}
        <FloatingToolbar>
           <button onClick={() => setShowPanels(!showPanels)} className={`p-2 rounded-full ${showPanels ? "bg-white text-black" : "text-white/40"}`}><Files size={20}/></button>
           <div className="w-px h-6 bg-white/10" />
           <button onClick={() => setActiveView("design")} className={`p-2 rounded-full ${activeView === "design" ? "bg-blue-600 text-white" : "text-white/40"}`}><Layers size={20}/></button>
           <button onClick={() => setActiveView("fab")} className={`p-2 rounded-full ${activeView === "fab" ? "bg-orange-600 text-white" : "text-white/40"}`}><Printer size={20}/></button>
           <div className="w-px h-6 bg-white/10" />
           <button className="p-2 rounded-full text-white/40"><Activity size={20}/></button>
        </FloatingToolbar>
      </div>

      {/* Status Bar */}
      <div className="absolute bottom-0 w-full h-6 bg-[#007fd4] flex items-center px-3 text-[10px] text-white font-mono justify-between">
         <div className="flex gap-4">
            <span>Project: {activeProject?.name || "None"}</span>
            <span>Status: {status.toUpperCase()}</span>
         </div>
         <div className="flex gap-4">
            <span>AI: Llama-3.3 (Cerebras)</span>
            <span>Hardware: Dum-E Disconnected</span>
         </div>
      </div>
    </div>
  );
}