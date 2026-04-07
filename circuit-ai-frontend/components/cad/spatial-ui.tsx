"use client";

import type { MouseEventHandler, PropsWithChildren, ReactNode } from "react";
import { X, Minus } from "lucide-react";

type GlassPanelProps = PropsWithChildren<{
  title: ReactNode;
  className?: string;
  onClose?: MouseEventHandler<SVGSVGElement>;
}>;

type FloatingToolbarProps = PropsWithChildren;

export function GlassPanel({ title, children, className = "", onClose }: GlassPanelProps) {
  return (
    <div className={`backdrop-blur-md bg-[#1e1e1e]/80 border border-white/10 rounded-lg shadow-2xl overflow-hidden flex flex-col ${className}`}>
      {/* Header */}
      <div className="h-8 px-3 flex items-center justify-between bg-white/5 border-b border-white/5 cursor-move select-none">
        <span className="text-[11px] font-bold uppercase tracking-wider text-white/70">{title}</span>
        <div className="flex items-center gap-2">
           <Minus size={12} className="text-white/40 hover:text-white cursor-pointer" />
           {onClose && <X size={12} className="text-white/40 hover:text-red-400 cursor-pointer" onClick={onClose} />}
        </div>
      </div>
      
      {/* Content */}
      <div className="flex-1 overflow-auto p-2 scrollbar-thin scrollbar-thumb-white/20">
        {children}
      </div>
    </div>
  );
}

export function FloatingToolbar({ children }: FloatingToolbarProps) {
  return (
    <div className="backdrop-blur-xl bg-black/60 border border-white/10 rounded-full px-4 py-2 flex items-center gap-4 shadow-xl">
      {children}
    </div>
  );
}
