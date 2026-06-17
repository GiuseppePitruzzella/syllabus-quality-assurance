import { useCallback, useMemo, type ReactNode } from "react";

import { useAuth } from "@/context/auth";
import { hasAutomaticTechnicalView } from "@/lib/roles";

import { TechnicalViewContext } from "./technicalView";

export function TechnicalViewProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const technical = hasAutomaticTechnicalView(user?.role);
  const setTechnical = useCallback(() => undefined, []);
  const toggle = useCallback(() => undefined, []);

  const value = useMemo(
    () => ({ technical, setTechnical, toggle }),
    [setTechnical, technical, toggle],
  );

  return (
    <TechnicalViewContext.Provider value={value}>
      {children}
    </TechnicalViewContext.Provider>
  );
}
