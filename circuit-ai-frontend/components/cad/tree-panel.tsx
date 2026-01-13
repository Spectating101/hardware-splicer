"use client";

import { useMemo, useState } from "react";
import type { PcbGeometry } from "@/lib/cad-types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function TreePanel({
  geometry,
  selectedRef,
  onSelectRef,
}: {
  geometry: PcbGeometry | null;
  selectedRef?: string;
  onSelectRef: (ref: string) => void;
}) {
  const [q, setQ] = useState("");

  const refs = useMemo(() => {
    if (!geometry) return [];
    const query = q.trim().toUpperCase();
    return geometry.footprints
      .map((f) => f.ref)
      .filter((r) => (!query ? true : r.toUpperCase().includes(query)))
      .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  }, [geometry, q]);

  return (
    <Card className="h-full border-white/10 bg-[#0b1220] text-white">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold text-white/90">Project</CardTitle>
      </CardHeader>
      <CardContent className="h-[calc(100%-56px)] overflow-auto">
        <div className="mb-3">
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search ref (e.g. R1, U...)"
            className="border-white/10 bg-white/5 text-white placeholder:text-white/40"
          />
        </div>

        {!geometry ? (
          <div className="rounded-md border border-white/10 bg-white/5 p-3 text-sm text-white/70">
            No design loaded. Use `Project` → `Import KiCad`, or click `Demo Board`.
          </div>
        ) : (
          <div className="space-y-1">
            {refs.map((r) => {
              const active = selectedRef?.toUpperCase() === r.toUpperCase();
              return (
                <button
                  key={r}
                  type="button"
                  onClick={() => onSelectRef(r)}
                  className={`flex w-full items-center justify-between rounded px-2 py-1 text-left text-sm ${
                    active ? "bg-blue-500/20 text-blue-100" : "hover:bg-white/5 text-white/85"
                  }`}
                >
                  <span className="font-medium">{r}</span>
                  <span className="text-xs text-white/50">Footprint</span>
                </button>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
