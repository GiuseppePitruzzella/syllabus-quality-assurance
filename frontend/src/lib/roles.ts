import type { RegisterableUserRole, UserRole } from "@/lib/types";

export const ROLE_META: Record<
  UserRole,
  {
    label: string;
    shortLabel: string;
    description: string;
    technicalView: boolean;
  }
> = {
  admin: {
    label: "Amministratore",
    shortLabel: "Admin",
    description: "Gestisce utenti e configurazione; usa sempre la vista tecnica.",
    technicalView: true,
  },
  quality_reviewer: {
    label: "Revisore qualità",
    shortLabel: "Revisione",
    description: "Consulta dashboard, syllabus e risultati in vista guidata.",
    technicalView: false,
  },
  technical_reviewer: {
    label: "Revisore tecnico",
    shortLabel: "Tecnico",
    description: "Analizza agenti, RAG, prompt e dettagli di esecuzione.",
    technicalView: true,
  },
};

export const REGISTERABLE_ROLE_OPTIONS: Array<{
  value: RegisterableUserRole;
  label: string;
  description: string;
}> = [
  {
    value: "quality_reviewer",
    label: ROLE_META.quality_reviewer.label,
    description: ROLE_META.quality_reviewer.description,
  },
  {
    value: "technical_reviewer",
    label: ROLE_META.technical_reviewer.label,
    description: ROLE_META.technical_reviewer.description,
  },
];

export const ROLE_OPTIONS: Array<{
  value: UserRole;
  label: string;
  description: string;
}> = (["admin", "quality_reviewer", "technical_reviewer"] as const).map(
  (value) => ({
    value,
    label: ROLE_META[value].label,
    description: ROLE_META[value].description,
  }),
);

export function roleLabel(role: string | undefined): string {
  if (role && role in ROLE_META) {
    return ROLE_META[role as UserRole].label;
  }
  return role ?? "Utente";
}

export function roleShortLabel(role: string | undefined): string {
  if (role && role in ROLE_META) {
    return ROLE_META[role as UserRole].shortLabel;
  }
  return "Utente";
}

export function hasAutomaticTechnicalView(role: string | undefined): boolean {
  return Boolean(
    role && role in ROLE_META && ROLE_META[role as UserRole].technicalView,
  );
}
