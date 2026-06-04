"use client";

import { AlertTriangle, ShieldAlert, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import type { SafetyLevel } from "@/lib/cad-types";
import { cn } from "@/lib/utils";

const VARIANTS: Record<SafetyLevel, {
  Icon: typeof ShieldCheck;
  label: string;
  border: string;
  bg: string;
  fg: string;
  iconFg: string;
}> = {
  safe: {
    Icon: ShieldCheck,
    label: "Safe",
    border: "border-emerald-400/30",
    bg: "bg-emerald-500/10",
    fg: "text-emerald-200",
    iconFg: "text-emerald-300",
  },
  caution: {
    Icon: AlertTriangle,
    label: "Caution",
    border: "border-amber-400/40",
    bg: "bg-amber-500/10",
    fg: "text-amber-100",
    iconFg: "text-amber-300",
  },
  hazard: {
    Icon: ShieldAlert,
    label: "Hazard",
    border: "border-rose-400/50",
    bg: "bg-rose-500/15",
    fg: "text-rose-100",
    iconFg: "text-rose-300",
  },
};

export interface SafetyBannerProps {
  level: SafetyLevel;
  title?: string;
  message: string;
  /** When true, the banner acts as a gate: the caller must render `requireAck`
   *  and wait for the user to click "I understand". */
  requireAck?: boolean;
  onAcknowledge?: () => void;
  onDismiss?: () => void;
  className?: string;
}

/** Universal safety surface used across /scan, /build, /parts, /cad.
 *  - safe:    subtle confirmation chip.
 *  - caution: yellow banner with an advisory message.
 *  - hazard:  red banner with optional ack gate + dismiss. */
export function SafetyBanner({
  level,
  title,
  message,
  requireAck,
  onAcknowledge,
  onDismiss,
  className,
}: SafetyBannerProps) {
  const v = VARIANTS[level];
  const Icon = v.Icon;
  const [acked, setAcked] = useState(false);

  const resolvedTitle = title ?? (
    level === "safe" ? "Looks safe"
    : level === "caution" ? "Heads up"
    : "Read this before you touch it"
  );

  return (
    <div className={cn(
      "relative rounded-2xl border p-4",
      v.border, v.bg, v.fg,
      className,
    )}>
      <div className="flex items-start gap-3">
        <div className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/5", v.iconFg)}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold">{resolvedTitle}</div>
          <p className="mt-1 text-sm leading-6 opacity-90">{message}</p>
          {requireAck && !acked && (
            <button
              type="button"
              onClick={() => { setAcked(true); onAcknowledge?.(); }}
              className={cn(
                "mt-3 inline-flex items-center rounded-full px-3 py-1.5 text-xs font-semibold uppercase tracking-wider",
                level === "hazard" ? "bg-rose-400/20 text-rose-100 hover:bg-rose-400/30"
                : "bg-amber-400/20 text-amber-100 hover:bg-amber-400/30",
              )}
            >
              I understand — show me anyway
            </button>
          )}
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-current/60 hover:bg-white/5 hover:text-current"
            aria-label="Dismiss"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
