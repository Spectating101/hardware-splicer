import { cn } from "@/lib/utils";

type BadgeVariant =
  | "critical"
  | "error"
  | "warning"
  | "success"
  | "info"
  | "processing"
  | "default";

const variantClasses: Record<BadgeVariant, string> = {
  critical: "bg-red-950 text-red-400 border-red-800",
  error: "bg-red-900/40 text-red-300 border-red-700/50",
  warning: "bg-amber-900/40 text-amber-300 border-amber-700/50",
  success: "bg-emerald-900/40 text-emerald-300 border-emerald-700/50",
  info: "bg-cyan-900/40 text-cyan-300 border-cyan-700/50",
  processing: "bg-blue-900/40 text-blue-300 border-blue-700/50 animate-pulse",
  default: "bg-white/5 text-white/60 border-white/10",
};

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

export function Badge({ children, variant = "default", className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border",
        variantClasses[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
