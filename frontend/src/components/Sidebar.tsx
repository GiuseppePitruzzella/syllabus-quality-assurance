import { Link, useLocation } from "react-router-dom";
import { BarChart3, LayoutDashboard, Settings } from "lucide-react";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, to: "/", enabled: true },
  { label: "Risultati", icon: BarChart3, to: "#", enabled: false },
  { label: "Impostazioni", icon: Settings, to: "#", enabled: false },
];

/**
 * Phase 6.1.B — premium navbar.
 *
 * Three pieces, left to right:
 *   - brand `Syllabus QA`
 *   - horizontal nav (Dashboard active, Risultati / Impostazioni
 *     disabled with `soon` pill + tooltip)
 *   - mock profile cluster (label + role + avatar with initials)
 *
 * No login. The profile cluster is a static demo affordance so the
 * dashboard reads as a SaaS shell rather than a bare React app.
 */
export function Navbar() {
  const location = useLocation();

  return (
    <div className="flex h-14 w-full items-center justify-between bg-slate-950 text-slate-100">
      <div className="flex h-full items-center">
        <Link
          to="/"
          className="flex h-full items-center gap-2 px-5 text-sm font-semibold tracking-wide text-white transition-colors hover:text-white/90"
        >
          <span
            className="inline-block h-2 w-2 rounded-sm bg-emerald-400"
            aria-hidden
          />
          Syllabus QA
        </Link>

        <div className="h-6 w-px bg-white/10" />

        <nav className="flex h-full items-center">
          {navItems.map((item) => {
            if (!item.enabled) {
              return <DisabledNavItem key={item.label} item={item} />;
            }
            const isActive = location.pathname === item.to;
            return (
              <Link
                key={item.label}
                to={item.to}
                className={
                  "flex h-full items-center gap-2 border-b-2 px-4 text-xs transition-colors " +
                  (isActive
                    ? "border-emerald-400 text-white font-medium"
                    : "border-transparent text-slate-400 hover:text-white")
                }
              >
                <item.icon className="h-3.5 w-3.5" aria-hidden />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <MockProfile />
    </div>
  );
}

function DisabledNavItem({
  item,
}: {
  item: { label: string; icon: typeof LayoutDashboard };
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            aria-disabled="true"
            className="flex h-full cursor-not-allowed select-none items-center gap-2 px-4 text-xs text-slate-500"
          />
        }
      >
        <item.icon className="h-3.5 w-3.5" aria-hidden />
        {item.label}
        <span className="ml-1 rounded-sm bg-white/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
          soon
        </span>
      </TooltipTrigger>
      <TooltipContent side="bottom">Disponibile a breve</TooltipContent>
    </Tooltip>
  );
}

function MockProfile() {
  return (
    <div className="flex h-full items-center gap-3 px-5">
      <div className="hidden text-right sm:block">
        <p className="text-xs font-medium leading-none text-white">
          Docente demo
        </p>
        <p className="mt-0.5 text-[10px] leading-none text-slate-400">
          Presidio qualità
        </p>
      </div>
      <span
        aria-hidden
        className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-emerald-500/30 bg-emerald-500/15 text-xs font-medium text-emerald-200"
      >
        DD
      </span>
    </div>
  );
}
