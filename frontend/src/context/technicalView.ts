import { createContext, useContext } from "react";

export interface TechnicalViewValue {
  technical: boolean;
  setTechnical: (value: boolean) => void;
  toggle: () => void;
}

export const TechnicalViewContext = createContext<TechnicalViewValue | null>(
  null,
);

export function useTechnicalView(): TechnicalViewValue {
  const ctx = useContext(TechnicalViewContext);
  if (!ctx) {
    throw new Error(
      "useTechnicalView must be used within TechnicalViewProvider",
    );
  }
  return ctx;
}
