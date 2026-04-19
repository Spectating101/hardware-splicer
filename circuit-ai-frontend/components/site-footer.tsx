import Link from "next/link";
import { ArrowUpRight, CircuitBoard } from "lucide-react";

const footerGroups = [
  {
    title: "Product",
    items: [
      { href: "/scan", label: "Scan" },
      { href: "/build", label: "Build" },
      { href: "/parts", label: "Parts" },
      { href: "/cad", label: "Advanced / KiCad" },
    ],
  },
  {
    title: "Developers",
    items: [
      { href: "/docs", label: "API Docs" },
      { href: "/playground", label: "Playground" },
      { href: "/dashboard/keys", label: "API Keys" },
      { href: "/status", label: "Status" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-white/5 bg-[#070b14] text-slate-400">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.4fr_1fr_1fr] lg:px-8">
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#1e293b,#2563eb,#f97316)] text-white">
              <CircuitBoard className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight text-white">Circuit.AI</div>
              <div className="text-xs text-slate-500">Build electronics from anything</div>
            </div>
          </div>
          <p className="max-w-md text-sm leading-6 text-slate-400">
            An AI copilot for makers, students, repair folks, and anyone who&apos;d rather build
            than buy new. Safe by default. Open at the advanced tier. KiCad-compatible all the way down.
          </p>
        </div>

        {footerGroups.map((group) => (
          <div key={group.title}>
            <div className="mb-4 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">{group.title}</div>
            <div className="space-y-2.5">
              {group.items.map((item) => (
                <Link key={item.href} href={item.href} className="flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white">
                  <ArrowUpRight className="h-3.5 w-3.5 text-slate-600" />
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="border-t border-white/5">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-5 sm:px-6 lg:px-8">
          <div className="text-[11px] uppercase tracking-[0.24em] text-slate-600">© Circuit.AI</div>
          <div className="text-[11px] text-slate-600">Safety first · KiCad-compatible · Open to graduate</div>
        </div>
      </div>
    </footer>
  );
}
