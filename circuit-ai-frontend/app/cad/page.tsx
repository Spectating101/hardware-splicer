"use client";

import { useState } from "react";
import { PcbViewport } from "@/components/cad/pcb-viewport";
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
  Mic
} from "lucide-react";

// --- MOCK DATA ---
const COMPONENTS = [
  { ref: "U1", type: "STM32F405", package: "LQFP-64", x: 40, y: 30, rot: 0 },
  { ref: "U2", type: "AMS1117", package: "SOT-223", x: 20, y: 30, rot: 90 },
  { ref: "C1", type: "100nF", package: "0603", x: 35, y: 25, rot: 0 },
  { ref: "C2", type: "10uF", package: "0805", x: 45, y: 25, rot: 0 },
];

export default function SpatialIDE() {
  const [activeView, setActiveView] = useState<"design" | "fab">("design");
  const [fabMode, setFabMode] = useState<"robot" | "manual">("manual"); // Default to Manual for layman
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const [showExplorer, setShowExplorer] = useState(true);
  const [showInspector, setShowInspector] = useState(true);

  // ... (Rest of render)

          {/* Bottom Center: The Dock (Workflow Control) */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 flex flex-col gap-2 items-center">
        
        {/* FAB MODE TOGGLE (Only visible in Fab View) */}
        {activeView === "fab" && (
          <div className="flex bg-black/60 backdrop-blur-md rounded-full p-1 border border-white/10">
            <button 
              onClick={() => setFabMode("manual")}
              className={`px-3 py-1 rounded-full text-[10px] font-bold transition-all ${fabMode === "manual" ? "bg-white text-black" : "text-white/50 hover:text-white"}`}
            >
              MANUAL GUIDE
            </button>
            <button 
              onClick={() => setFabMode("robot")}
              className={`px-3 py-1 rounded-full text-[10px] font-bold transition-all ${fabMode === "robot" ? "bg-[#d65d0e] text-white" : "text-white/50 hover:text-white"}`}
            >
              ROBOT ARM
            </button>
          </div>
        )}

        <FloatingToolbar>
           {/* ... (Existing Toolbar Buttons) ... */}
           <button 
             onClick={() => setShowExplorer(!showExplorer)}
             className={`p-2 rounded-full transition-all ${showExplorer ? "bg-white text-black" : "text-white/60 hover:text-white hover:bg-white/10"}`}
           >
             <Files size={20} />
           </button>
           <button className="p-2 rounded-full text-white/60 hover:text-white hover:bg-white/10 transition-all">
             <Search size={20} />
           </button>
           
           <div className="w-px h-6 bg-white/10" />
           
           <button 
             onClick={() => setActiveView("design")}
             className={`p-2 rounded-full transition-all ${activeView === "design" ? "bg-[#007fd4] text-white shadow-lg shadow-blue-500/20" : "text-white/60 hover:text-white hover:bg-white/10"}`}
           >
             <Layers size={20} />
           </button>
           <button 
             onClick={() => setActiveView("fab")}
             className={`p-2 rounded-full transition-all ${activeView === "fab" ? "bg-[#d65d0e] text-white shadow-lg shadow-orange-500/20" : "text-white/60 hover:text-white hover:bg-white/10"}`}
           >
             <Printer size={20} />
           </button>

           <div className="w-px h-6 bg-white/10" />
           
           <button className="p-2 rounded-full text-white/60 hover:text-white hover:bg-white/10 transition-all">
             <Activity size={20} />
           </button>
        </FloatingToolbar>
      </div>

      {/* OVERLAY FOR MANUAL GUIDE (Replaces Bottom Panel logic effectively in this layout) */}
      {activeView === "fab" && fabMode === "manual" && (
        <div className="absolute bottom-24 right-6 w-80 bg-[#1e1e1e]/90 backdrop-blur-xl border border-[#d65d0e]/50 rounded-xl p-4 shadow-2xl animate-in slide-in-from-bottom-4">
           <div className="flex items-center justify-between mb-3 border-b border-white/10 pb-2">
             <span className="text-xs font-bold text-[#d65d0e] uppercase tracking-wider">Human Repair Sequence</span>
             <span className="text-[10px] text-white/40">Step 1 of 4</span>
           </div>
           <div className="space-y-3">
             <div className="flex gap-3">
               <div className="mt-1 h-5 w-5 rounded-full bg-[#d65d0e] text-black font-bold text-xs flex items-center justify-center shrink-0">1</div>
               <div>
                 <div className="text-sm font-medium text-white">Heat Component C2</div>
                 <div className="text-xs text-white/60 mt-1">Set iron to 350°C. Apply heat to both pads simultaneously if possible.</div>
               </div>
             </div>
             <div className="flex gap-3 opacity-50">
               <div className="mt-1 h-5 w-5 rounded-full bg-white/10 text-white font-bold text-xs flex items-center justify-center shrink-0">2</div>
               <div>
                 <div className="text-sm font-medium text-white">Remove & Clean</div>
                 <div className="text-xs text-white/60 mt-1">Use tweezers to lift C2. Clean pads with wick.</div>
               </div>
             </div>
           </div>
           <button className="mt-4 w-full bg-[#d65d0e] hover:bg-[#b34d0b] text-white py-2 rounded-lg text-xs font-bold transition-colors">
             Next Step →
           </button>
        </div>
      )}
      
      {/* ... (Keep Status Bar logic mostly, just tweak text) */}

