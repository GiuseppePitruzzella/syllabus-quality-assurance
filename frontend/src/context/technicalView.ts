import { createContext, useContext } from "react";

export const TECHNICAL_VIEW_STORAGE_KEY = "sqa.technicalView";

export interface TechnicalViewValue {
  technical: boolean;
  setTechnical: (value: boolean) => void;
  toggle: () => void;
}

export const TechnicalViewContext = createContext<TechnicalViewValue | null>(
  null,
);

/** Read the persisted flag; defaults to false (guided view). */
export function readInitialTechnicalView(): boolean {
  try {
    return localStorage.getItem(TECHNICAL_VIEW_STORAGE_KEY) === "true";
  } catch {
    return false; // localStorage unavailable (e.g. private mode)
  }
}

export function useTechnicalView(): TechnicalViewValue {
  const ctx = useContext(TechnicalViewContext);
  if (!ctx) {
    throw new Error(
      "useTechnicalView must be used within TechnicalViewProvider",
    );
  }
  return ctx;
}
