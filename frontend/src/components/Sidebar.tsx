import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Search,
  BarChart3,
  Clock,
  Settings,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, to: "/", enabled: true },
  { label: "Cerca", icon: Search, to: "#", enabled: false },
  { label: "Risultati", icon: BarChart3, to: "#", enabled: false },
  { label: "Storico", icon: Clock, to: "#", enabled: false },
  { label: "Impostazioni", icon: Settings, to: "#", enabled: false },
];

/**
 * Phase 5.9.D — navbar polish.
 *
 * The four sibling sections (Cerca / Risultati / Storico / Impostazioni)
 * are still planned, not implemented. Until they are, the items render
 * as visibly inert: greyed text, no hover, no underline, a small
 * "soon" pill on the right and a tooltip that says "Disponibile a
 * breve". This is the "non fuorvianti" half of the charter rule —
 * the items advertise the product surface without pretending to be
 * functional links.
 *
 * The previous "Evaluate" disabled CTA on the right side is dropped:
 * evaluations now have a real entry point on the SyllabusViewer
 * ("Valuta syllabus"), so the navbar shortcut would have been
 * redundant and confusing.
 */
export function Navbar() {
  const location = useLocation();

  return (
    <header className="fixed left-0 top-0 z-40 flex h-12 w-full items-center bg-sidebar text-sidebar-foreground border-b border-white/10">
      <Link
        to="/"
        className="flex h-full items-center px-5 text-xs font-semibold uppercase tracking-wide text-white/90 transition-colors hover:text-white"
      >
        Syllabus QA
      </Link>

      <div className="h-5 w-px bg-white/15" />

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
                  ? "border-white text-white font-medium"
                  : "border-transparent text-sidebar-muted hover:text-white")
              }
            >
              <item.icon className="h-3.5 w-3.5" aria-hidden />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </header>
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
            className="flex h-full cursor-not-allowed items-center gap-2 px-4 text-xs text-sidebar-muted/50 select-none"
          />
        }
      >
        <item.icon className="h-3.5 w-3.5" aria-hidden />
        {item.label}
        <span className="ml-1 rounded-sm bg-white/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-white/40">
          soon
        </span>
      </TooltipTrigger>
      <TooltipContent side="bottom">Disponibile a breve</TooltipContent>
    </Tooltip>
  );
}
