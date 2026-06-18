import type { ReactNode } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "sonner";
import { Navbar } from "@/components/Sidebar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AuthProvider } from "@/context/AuthProvider";
import { Dashboard } from "@/pages/Dashboard/Dashboard";
import { LoginPage } from "@/pages/Auth/LoginPage";
import { RegisterPage } from "@/pages/Auth/RegisterPage";
import { EvaluationPage } from "@/pages/Evaluation/EvaluationPage";
import { ProfilePage } from "@/pages/Profile/ProfilePage";
import { ResultsPage } from "@/pages/Results/ResultsPage";
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
 * No global fixed navbar anymore. Each protected page uses the
 * lightweight `Chromed` wrapper, which renders the shared light
 * navbar above the page content.
 */
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TechnicalViewProvider>
          <BrowserRouter>
            <TooltipProvider delay={300}>
              <main className="relative isolate min-h-screen bg-slate-50">
                <Routes>
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/register" element={<RegisterPage />} />
                  <Route
                    path="/"
                    element={
                      <ProtectedRoute>
                        <Chromed>
                          <Dashboard />
                        </Chromed>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/syllabus/:seuid"
                    element={
                      <ProtectedRoute>
                        <Chromed>
                          <SyllabusViewer />
                        </Chromed>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/evaluation/:evaluation_uuid"
                    element={
                      <ProtectedRoute>
                        <Chromed>
                          <EvaluationPage />
                        </Chromed>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/results"
                    element={
                      <ProtectedRoute>
                        <Chromed>
                          <ResultsPage />
                        </Chromed>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/settings"
                    element={
                      <ProtectedRoute>
                        <Chromed>
                          <SettingsPage />
                        </Chromed>
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/profile"
                    element={
                      <ProtectedRoute>
                        <Chromed>
                          <ProfilePage />
                        </Chromed>
                      </ProtectedRoute>
                    }
                  />
                </Routes>
              </main>
              <Toaster position="bottom-right" />
            </TooltipProvider>
          </BrowserRouter>
        </TechnicalViewProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

function Chromed({ children }: { children: ReactNode }) {
  return (
    <div>
      <header className="border-b border-slate-200 bg-white/95 shadow-sm shadow-slate-200/40">
        <Navbar />
      </header>
      <div className="px-4 py-8 sm:px-6 lg:px-10 lg:py-10">{children}</div>
    </div>
  );
}
