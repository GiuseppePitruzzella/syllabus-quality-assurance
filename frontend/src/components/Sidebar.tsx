import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Search,
  BarChart3,
  Clock,
  Settings,
  FlaskConical,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, to: "/", enabled: true },
  { label: "Search", icon: Search, to: "#", enabled: false },
  { label: "Results", icon: BarChart3, to: "#", enabled: false },
  { label: "History", icon: Clock, to: "#", enabled: false },
  { label: "Settings", icon: Settings, to: "#", enabled: false },
];

export function Navbar() {
  const location = useLocation();

  return (
    <header className="fixed left-0 top-0 z-40 flex h-12 w-full items-center justify-between bg-sidebar text-sidebar-foreground border-b border-white/10">
      <div className="flex items-center h-full">
        <Link
          to="/"
          className="flex items-center h-full px-5 text-xs font-semibold tracking-wide uppercase text-white/90 hover:text-white transition-colors"
        >
          Syllabus QA
        </Link>

        <div className="w-px h-5 bg-white/15" />

        <nav className="flex items-center h-full">
          {navItems.map((item) => {
            const isActive = item.enabled && location.pathname === item.to;
            if (!item.enabled) {
              return (
                <Tooltip key={item.label}>
                  <TooltipTrigger
                    render={
                      <div className="flex cursor-not-allowed items-center gap-2 h-full px-4 text-xs text-sidebar-muted/40" />
                    }
                  >
                    <item.icon className="h-3.5 w-3.5" />
                    {item.label}
                  </TooltipTrigger>
                  <TooltipContent side="bottom">Coming soon</TooltipContent>
                </Tooltip>
              );
            }
            return (
              <Link
                key={item.label}
                to={item.to}
                className={`flex items-center gap-2 h-full px-4 text-xs transition-colors border-b-2 ${
                  isActive
                    ? "border-white text-white font-medium"
                    : "border-transparent text-sidebar-muted hover:text-white"
                }`}
              >
                <item.icon className="h-3.5 w-3.5" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="flex items-center h-full px-5">
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                variant="ghost"
                size="sm"
                className="text-sidebar-muted/50 h-7 text-xs gap-1.5"
                disabled
              />
            }
          >
            <FlaskConical className="h-3.5 w-3.5" />
            Evaluate
          </TooltipTrigger>
          <TooltipContent side="bottom">Coming soon</TooltipContent>
        </Tooltip>
      </div>
    </header>
  );
}
