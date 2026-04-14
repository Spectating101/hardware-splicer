"use client";

import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Zap, X } from "lucide-react";
import { useWorkspaceStore } from "@/lib/store";

/** Renders **bold** and `code` markdown inline */
function InlineMarkdown({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**"))
          return <strong key={i} className="font-semibold text-cyan-100">{part.slice(2, -2)}</strong>;
        if (part.startsWith("`") && part.endsWith("`"))
          return <code key={i} className="font-mono text-cyan-300 bg-cyan-950/40 px-0.5 rounded">{part.slice(1, -1)}</code>;
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

export function NotificationStrip() {
  const { jarvisStrip, dismissJarvisStrip, openDrawer } = useWorkspaceStore();

  // Auto-dismiss: longer when there's an action (give user time to react)
  useEffect(() => {
    if (!jarvisStrip) return;
    const delay = jarvisStrip.action ? 14000 : 9000;
    const timer = setTimeout(() => dismissJarvisStrip(), delay);
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
            <p className="flex-1 text-sm text-cyan-100/80 min-w-0">
              <InlineMarkdown text={jarvisStrip.message.split("\n")[0]} />
            </p>
            {jarvisStrip.nodeId && !jarvisStrip.action && (
              <button
                onClick={() => {
                  openDrawer(jarvisStrip.nodeId!);
                  dismissJarvisStrip();
                }}
                className="text-xs text-cyan-400 hover:text-cyan-200 transition-colors flex-shrink-0 whitespace-nowrap"
              >
                Show me →
              </button>
            )}
            {jarvisStrip.action && (
              <button
                onClick={() => {
                  jarvisStrip.action!.onAction();
                  dismissJarvisStrip();
                }}
                className="text-xs bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 border border-cyan-500/30 rounded-md px-2.5 py-1 transition-colors flex-shrink-0 whitespace-nowrap"
              >
                {jarvisStrip.action.label}
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
