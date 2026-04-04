import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "sonner";
import { Sidebar } from "@/components/Sidebar";
import { Dashboard } from "@/pages/Dashboard/Dashboard";
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
          <div className="flex min-h-screen bg-background">
            <Sidebar />
            <main className="ml-60 flex-1 p-8">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/syllabus/:seuid" element={<SyllabusViewer />} />
              </Routes>
            </main>
          </div>
          <Toaster position="bottom-right" />
        </TooltipProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
