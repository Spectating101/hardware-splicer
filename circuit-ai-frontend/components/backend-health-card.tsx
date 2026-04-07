"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, LoaderCircle, Server } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type HealthState = {
  status?: string;
  ok?: boolean;
  error?: string;
  timestamp?: string;
  [key: string]: unknown;
};

function statusTone(status: string) {
  if (status === "healthy" || status === "ok") {
    return {
      border: "border-emerald-200",
      bg: "bg-emerald-50",
      text: "text-emerald-800",
      icon: CheckCircle2,
      label: "Healthy",
    };
  }

  if (status === "loading") {
    return {
      border: "border-slate-200",
      bg: "bg-slate-50",
      text: "text-slate-700",
      icon: LoaderCircle,
      label: "Checking",
    };
  }

  return {
    border: "border-amber-200",
    bg: "bg-amber-50",
    text: "text-amber-800",
    icon: AlertTriangle,
    label: "Backend attention needed",
  };
}

export function BackendHealthCard({ className = "" }: { className?: string }) {
  const [health, setHealth] = useState<HealthState | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const response = await fetch("/api/proxy/health", { cache: "no-store" });
        const data = await response.json();
        if (!mounted) return;
        setHealth(data);
      } catch (error) {
        if (!mounted) return;
        setHealth({ status: "unhealthy", error: String(error) });
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();
    const timer = window.setInterval(load, 15000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  const rawStatus = loading ? "loading" : String(health?.status || (health?.ok ? "healthy" : "unhealthy")).toLowerCase();
  const tone = statusTone(rawStatus);
  const Icon = tone.icon;

  return (
    <Card className={`${tone.border} ${tone.bg} ${className}`.trim()}>
      <CardHeader>
        <CardTitle className={`flex items-center gap-2 text-lg ${tone.text}`}>
          <Icon className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Backend health
        </CardTitle>
        <CardDescription className={tone.text}>{tone.label}</CardDescription>
      </CardHeader>
      <CardContent className={`space-y-2 text-sm ${tone.text}`} aria-live="polite">
        {health?.error ? <p>{health.error}</p> : null}
        {health?.timestamp ? <p>Last check: {new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(health.timestamp))}</p> : null}
        {!health?.error ? (
          <p className="flex items-center gap-2">
            <Server className="h-4 w-4" />
            Health is read through the frontend proxy route.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
