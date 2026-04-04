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

export function Sidebar() {
  const location = useLocation();

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col bg-sidebar text-sidebar-foreground">
      <div className="border-b border-white/10 p-5">
        <h1 className="text-lg font-bold">Syllabus QA</h1>
        <p className="mt-1 text-xs text-sidebar-muted leading-relaxed">
          A Retrieval-Augmented Multi-Agent Framework for Automated Evaluation
        </p>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => {
          const isActive = item.enabled && location.pathname === item.to;
          if (!item.enabled) {
            return (
              <Tooltip key={item.label}>
                <TooltipTrigger asChild>
                  <div className="flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-sm text-sidebar-muted/50">
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </div>
                </TooltipTrigger>
                <TooltipContent side="right">Coming soon</TooltipContent>
              </Tooltip>
            );
          }
          return (
            <Link
              key={item.label}
              to={item.to}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                isActive
                  ? "bg-white/10 text-white font-medium"
                  : "text-sidebar-muted hover:bg-white/5 hover:text-white"
              }`}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-white/10 p-3">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              className="w-full border-white/20 text-sidebar-muted"
              disabled
            >
              <FlaskConical className="mr-2 h-4 w-4" />
              New Evaluation
            </Button>
          </TooltipTrigger>
          <TooltipContent>Coming soon</TooltipContent>
        </Tooltip>
      </div>
    </aside>
  );
}
