import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/context/auth";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <div className="w-full max-w-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
            Syllabus Quality Assurance
          </p>
          <div className="mt-6 h-2 w-full overflow-hidden bg-slate-100">
            <div className="h-full w-1/2 animate-pulse bg-slate-300" />
          </div>
          <p className="mt-4 text-sm text-slate-500">
            Verifica della sessione in corso...
          </p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}
