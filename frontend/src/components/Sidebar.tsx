import { Link, useLocation } from "react-router-dom";
import {
  BarChart3,
  LayoutDashboard,
  LogOut,
  Settings,
} from "lucide-react";

import { useAuth } from "@/context/auth";
import { roleShortLabel } from "@/lib/roles";

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
    <div className="relative flex h-14 w-full items-center justify-between text-slate-900">
      <Link
        to="/"
        className="flex h-full items-center gap-2 px-4 text-sm font-semibold tracking-wide text-slate-950 transition-colors hover:text-sky-700 sm:px-5"
      >
        <span
          className="inline-block h-2 w-2 rounded-sm bg-sky-500"
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
                className="pointer-events-auto flex h-full cursor-not-allowed select-none items-center gap-2 px-4 text-xs text-slate-400"
              >
                <item.icon className="h-3.5 w-3.5" aria-hidden />
                {item.label}
              </span>
            );
          }
          const isActive =
            item.to === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(item.to);
          return (
            <Link
              key={item.label}
              to={item.to}
              className={
                "pointer-events-auto flex h-full items-center gap-2 border-b-2 px-4 text-xs transition-colors " +
                (isActive
                  ? "border-sky-500 text-slate-950 font-medium"
                  : "border-transparent text-slate-600 hover:text-sky-700")
              }
            >
              <item.icon className="h-3.5 w-3.5" aria-hidden />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="flex h-full items-center gap-1 pr-1">
        <MockProfile />
      </div>
    </div>
  );
}

function MockProfile() {
  const { user, logout } = useAuth();

  const initials = getInitials(user?.full_name ?? user?.email ?? "Utente");
  const primary = user?.full_name ?? "Utente";
  const secondary = user ? roleShortLabel(user.role) : "Utente";

  return (
    <div className="flex h-full items-center gap-2 px-3 sm:px-5">
      <Link to="/profile" className="hidden text-right sm:block">
        <p className="text-xs font-medium leading-none text-slate-950">
          {primary}
        </p>
        <p className="mt-0.5 text-[10px] leading-none text-slate-500">
          {secondary}
        </p>
      </Link>
      <Link
        to="/profile"
        className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-sky-200 bg-sky-50 text-xs font-medium text-sky-700"
        aria-label="Apri profilo"
        title="Apri profilo"
      >
        {initials}
      </Link>
      <button
        type="button"
        onClick={() => void logout()}
        className="inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-950"
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
