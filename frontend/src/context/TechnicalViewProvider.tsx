import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  TECHNICAL_VIEW_STORAGE_KEY,
  TechnicalViewContext,
  readInitialTechnicalView,
} from "./technicalView";

export function TechnicalViewProvider({ children }: { children: ReactNode }) {
  const [technical, setTechnical] = useState<boolean>(readInitialTechnicalView);

  useEffect(() => {
    try {
      localStorage.setItem(TECHNICAL_VIEW_STORAGE_KEY, String(technical));
    } catch {
      // localStorage unavailable: keep state in memory only
    }
  }, [technical]);

  const toggle = useCallback(() => setTechnical((v) => !v), []);

  const value = useMemo(
    () => ({ technical, setTechnical, toggle }),
    [technical, toggle],
  );

  return (
    <TechnicalViewContext.Provider value={value}>
      {children}
    </TechnicalViewContext.Provider>
  );
}
