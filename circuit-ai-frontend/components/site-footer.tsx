import Link from "next/link";
import { ArrowUpRight, CircuitBoard, Workflow } from "lucide-react";

const footerGroups = [
  {
    title: "Navigate",
    items: [
      { href: "/", label: "Overview" },
      { href: "/docs", label: "Docs" },
      { href: "/playground", label: "Playground" },
      { href: "/status", label: "Status" },
    ],
  },
  {
    title: "Core Flows",
    items: [
      { href: "/dashboard/keys", label: "API Keys" },
      { href: "/playground", label: "Validate Requests" },
      { href: "/cad", label: "CAD Workspace" },
      { href: "/projects", label: "Project Templates" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-slate-200 bg-[#0f172a] text-slate-300">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.2fr_1fr_1fr] lg:px-8">
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#1e293b,#2563eb,#f97316)] text-white">
              <CircuitBoard className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-400">Circuit.AI</div>
              <div className="text-sm text-slate-300">Hardware intelligence that goes beyond screenshots and static BOMs.</div>
            </div>
          </div>
          <div className="max-w-md rounded-3xl border border-white/10 bg-white/5 p-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
              <Workflow className="h-4 w-4 text-cyan-300" />
              Product stance
            </div>
            <p className="text-sm leading-6 text-slate-300">
              One frontend, multiple backend depths: image analysis, KiCad validation, minting flows, and spatial engineering workspaces.
            </p>
          </div>
        </div>

        {footerGroups.map((group) => (
          <div key={group.title}>
            <div className="mb-4 text-sm font-semibold uppercase tracking-[0.24em] text-slate-500">{group.title}</div>
            <div className="space-y-3">
              {group.items.map((item) => (
                <Link key={item.href} href={item.href} className="flex items-center gap-2 text-sm text-slate-300 transition-colors hover:text-white">
                  <ArrowUpRight className="h-3.5 w-3.5 text-slate-500" />
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </footer>
  );
}
