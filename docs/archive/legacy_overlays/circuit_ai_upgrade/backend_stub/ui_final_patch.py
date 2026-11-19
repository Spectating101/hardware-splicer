
import os

target_path = "../Circuit-AI/circuit-ai-frontend/app/cad/page.tsx"

with open(target_path, "r") as f:
    content = f.read()

old_block = """          {/* Left panel - Component tree */}
          {showPanels && (
            <div className="overflow-hidden">
              <GlassPanel className="h-full">
                <TreePanel
                  geometry={geometry}
                  selectedRef={selectedRef}
                  onSelectRef={setSelectedRef}
                />
              </GlassPanel>
            </div>
          )}"""

new_block = """          {/* Left panel - Component tree or Fabrication */}
          {showPanels && (
            <div className="overflow-hidden">
              <GlassPanel className="h-full">
                {activeView === "design" ? (
                  <TreePanel
                    geometry={geometry}
                    selectedRef={selectedRef}
                    onSelectRef={setSelectedRef}
                  />
                ) : (
                  <div className="flex-1 overflow-y-auto p-4">
                    <div className="text-xs font-bold text-[#d65d0e] uppercase mb-4 tracking-widest">Robot Control (Dum-E)</div>
                    <div className="space-y-4">
                      <div className="bg-white/5 border border-white/10 p-3 rounded-lg">
                        <div className="text-[10px] text-white/40 mb-1 uppercase">Machine Status</div>
                        <div className="text-sm font-mono text-emerald-400">READY / CONNECTED</div>
                      </div>
                      <button className="w-full bg-[#d65d0e] hover:bg-[#b34d0b] text-white py-2 rounded-lg text-xs font-bold transition-all">
                        Generate Repair Toolpath
                      </button>
                      <div className="bg-black/40 p-2 rounded border border-white/5 h-32 font-mono text-[10px] text-white/30 overflow-hidden">
                        &gt; G28 ; Home<br/>
                        &gt; G0 Z5.0<br/>
                        &gt; M114 ; Get Pos
                      </div>
                    </div>
                  </div>
                )}
              </GlassPanel>
            </div>
          )}"""

if old_block in content:
    new_content = content.replace(old_block, new_block)
    with open(target_path, "w") as f:
        f.write(new_content)
    print("SUCCESS: Unified UI with Fabrication Mode.")
else:
    print("FAILURE: Could not find the target block in the merged file.")
