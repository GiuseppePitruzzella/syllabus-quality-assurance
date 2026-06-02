import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "sonner";
import { Navbar } from "@/components/Sidebar";
import { Dashboard } from "@/pages/Dashboard/Dashboard";
import { EvaluationPage } from "@/pages/Evaluation/EvaluationPage";
import { SyllabusViewer } from "@/pages/SyllabusViewer/SyllabusViewer";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <TooltipProvider delay={300}>
          <div className="flex min-h-screen flex-col bg-background">
            <Navbar />
            <main className="mt-12 flex-1 px-10 py-8">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/syllabus/:seuid" element={<SyllabusViewer />} />
                <Route
                  path="/evaluation/:evaluation_uuid"
                  element={<EvaluationPage />}
                />
              </Routes>
            </main>
          </div>
          <Toaster position="bottom-right" />
        </TooltipProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
