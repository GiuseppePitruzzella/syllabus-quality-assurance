import type { ReactNode } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "sonner";
import { Navbar } from "@/components/Sidebar";
import { Dashboard } from "@/pages/Dashboard/Dashboard";
import { EvaluationPage } from "@/pages/Evaluation/EvaluationPage";
import { SettingsPage } from "@/pages/Settings/SettingsPage";
import { SyllabusViewer } from "@/pages/SyllabusViewer/SyllabusViewer";
import { TechnicalViewProvider } from "@/context/TechnicalViewProvider";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

/**
 * Phase 6.1.B (rev) — SaaS shell.
 *
 * No global fixed navbar anymore. Each page owns its own dark
 * "rounded shell" at the top: Dashboard combines navbar + hero in
 * one shell; the other pages (SyllabusViewer, EvaluationPage) use
 * the lightweight `Chromed` wrapper which renders only the navbar
 * in a rounded slate-950 shell above the page content.
 */
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TechnicalViewProvider>
        <BrowserRouter>
          <TooltipProvider delay={300}>
            <main className="relative isolate min-h-screen bg-slate-50">
              <Routes>
                <Route
                  path="/"
                  element={
                    <Chromed>
                      <Dashboard />
                    </Chromed>
                  }
                />
                <Route
                  path="/syllabus/:seuid"
                  element={
                    <Chromed>
                      <SyllabusViewer />
                    </Chromed>
                  }
                />
                <Route
                  path="/evaluation/:evaluation_uuid"
                  element={
                    <Chromed>
                      <EvaluationPage />
                    </Chromed>
                  }
                />
                <Route
                  path="/settings"
                  element={
                    <Chromed>
                      <SettingsPage />
                    </Chromed>
                  }
                />
              </Routes>
            </main>
            <Toaster position="bottom-right" />
          </TooltipProvider>
        </BrowserRouter>
      </TechnicalViewProvider>
    </QueryClientProvider>
  );
}

function Chromed({ children }: { children: ReactNode }) {
  return (
    <div>
      <header className="bg-slate-950">
        <Navbar />
      </header>
      <div className="px-4 py-8 sm:px-6 lg:px-10 lg:py-10">{children}</div>
    </div>
  );
}
