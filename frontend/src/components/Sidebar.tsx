import { Link, useLocation } from "react-router-dom";
import { BarChart3, LayoutDashboard, LogOut, Settings } from "lucide-react";

import { TechnicalViewToggle } from "@/components/TechnicalViewToggle";
import { useAuth } from "@/context/auth";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, to: "/", enabled: true },
  { label: "Risultati", icon: BarChart3, to: "#", enabled: false },
  { label: "Impostazioni", icon: Settings, to: "/settings", enabled: true },
];

/**
 * Phase 6.1.F — premium navbar with centred nav.
 *
 * Three slots, edge to edge:
 *   - brand          : left, anchored
 *   - nav            : absolutely centred to the navbar, independent
 *                      of brand and profile widths so the items stay
 *                      visually balanced regardless of who's wider
 *   - profile mock   : right, anchored
 *
 * Disabled items (`Risultati`, `Impostazioni`) are simple disabled
 * spans — no `SOON` pill, no tooltip. Their dim colour is the only
 * affordance, matching standard form-disabled semantics.
 */
export function Navbar() {
  const location = useLocation();

  return (
    <div className="relative flex h-14 w-full items-center justify-between text-slate-100">
      <Link
        to="/"
        className="flex h-full items-center gap-2 px-4 text-sm font-semibold tracking-wide text-white transition-colors hover:text-white/90 sm:px-5"
      >
        <span
          className="inline-block h-2 w-2 rounded-sm bg-emerald-400"
          aria-hidden
        />
        Syllabus Quality Assurance
      </Link>

      <nav
        className="pointer-events-none absolute left-1/2 top-0 hidden h-full -translate-x-1/2 items-center md:flex"
        aria-label="Sezioni"
      >
        {navItems.map((item) => {
          if (!item.enabled) {
            return (
              <span
                key={item.label}
                aria-disabled="true"
                className="pointer-events-auto flex h-full cursor-not-allowed select-none items-center gap-2 px-4 text-xs text-slate-500"
              >
                <item.icon className="h-3.5 w-3.5" aria-hidden />
                {item.label}
              </span>
            );
          }
          const isActive = location.pathname === item.to;
          return (
            <Link
              key={item.label}
              to={item.to}
              className={
                "pointer-events-auto flex h-full items-center gap-2 border-b-2 px-4 text-xs transition-colors " +
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

      <div className="flex h-full items-center gap-1 pr-1">
        <TechnicalViewToggle />
        <MockProfile />
      </div>
    </div>
  );
}

function MockProfile() {
  const { user, logout } = useAuth();

  const initials = getInitials(user?.full_name ?? user?.email ?? "Utente");
  const primary = user?.full_name ?? "Utente";
  const secondary = user?.role === "quality_reviewer" ? "Presidio qualità" : user?.email;

  return (
    <div className="flex h-full items-center gap-2 px-3 sm:px-5">
      <div className="hidden text-right sm:block">
        <p className="text-xs font-medium leading-none text-white">
          {primary}
        </p>
        <p className="mt-0.5 text-[10px] leading-none text-slate-400">
          {secondary}
        </p>
      </div>
      <span
        aria-hidden
        className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-emerald-500/30 bg-emerald-500/15 text-xs font-medium text-emerald-200"
      >
        {initials}
      </span>
      <button
        type="button"
        onClick={() => void logout()}
        className="inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
        aria-label="Esci"
        title="Esci"
      >
        <LogOut className="h-3.5 w-3.5" aria-hidden />
      </button>
    </div>
  );
}

function getInitials(value: string): string {
  const parts = value
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return value.slice(0, 2).toUpperCase();
}
