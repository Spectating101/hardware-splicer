"use client";

import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Zap, X } from "lucide-react";
import { useWorkspaceStore } from "@/lib/store";

export function NotificationStrip() {
  const { jarvisStrip, dismissJarvisStrip, openDrawer } = useWorkspaceStore();

  useEffect(() => {
    if (!jarvisStrip) return;
    const timer = setTimeout(() => dismissJarvisStrip(), 8000);
    return () => clearTimeout(timer);
  }, [jarvisStrip, dismissJarvisStrip]);

  return (
    <AnimatePresence>
      {jarvisStrip && (
        <motion.div
          key={jarvisStrip.message}
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="overflow-hidden flex-shrink-0"
        >
          <div className="bg-cyan-950/60 border-b border-cyan-500/20 px-4 py-2 flex items-center gap-3">
            <Zap size={14} className="text-cyan-400 flex-shrink-0" />
            <p className="flex-1 text-sm text-cyan-100/80 truncate">
              {jarvisStrip.message
                .replace(/\*\*(.*?)\*\*/g, "$1")
                .replace(/`(.*?)`/g, "$1")}
            </p>
            {jarvisStrip.nodeId && (
              <button
                onClick={() => {
                  openDrawer(jarvisStrip.nodeId!);
                  dismissJarvisStrip();
                }}
                className="text-xs text-cyan-400 hover:text-cyan-200 transition-colors flex-shrink-0"
              >
                Show me →
              </button>
            )}
            <button
              onClick={dismissJarvisStrip}
              className="text-white/30 hover:text-white/60 transition-colors flex-shrink-0"
            >
              <X size={14} />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
