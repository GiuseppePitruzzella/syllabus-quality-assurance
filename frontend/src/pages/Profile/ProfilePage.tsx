import { FormEvent, useState, type ReactNode } from "react";
import { CheckCircle2, KeyRound, ShieldCheck, UserRound } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/context/auth";
import { ApiError } from "@/lib/api";

export function ProfilePage() {
  const { user, changePassword } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (newPassword.length < 8) {
      setError("La nuova password deve contenere almeno 8 caratteri.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("La conferma non coincide con la nuova password.");
      return;
    }

    setSubmitting(true);
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setSuccess(
        "Password aggiornata. Le altre sessioni aperte sono state disconnesse.",
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("La password attuale non è corretta.");
      } else if (err instanceof ApiError && err.status === 422) {
        setError("La nuova password deve essere diversa e rispettare i requisiti.");
      } else {
        setError("Cambio password non riuscito. Riprova tra qualche istante.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-[1720px] space-y-10">
      <PageHeader
        badge="Profilo"
        badgeTone="neutral"
        title="Account personale"
        subtitle="Gestisci l’identità usata per accedere alla piattaforma e proteggi la sessione di lavoro."
      />

      <section className="grid gap-10 xl:grid-cols-[minmax(0,0.9fr)_minmax(420px,0.6fr)]">
        <div className="space-y-8">
          <div className="border-t border-slate-200 pt-6">
            <div className="flex items-start gap-4">
              <span className="flex h-12 w-12 items-center justify-center rounded-none bg-slate-950 text-sm font-semibold text-white">
                {getInitials(user?.full_name ?? user?.email ?? "Utente")}
              </span>
              <div className="min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Utente autenticato
                </p>
                <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                  {user?.full_name}
                </h2>
                <p className="mt-1 text-sm text-slate-600">{user?.email}</p>
              </div>
            </div>
          </div>

          <dl className="grid gap-px overflow-hidden border-y border-slate-200 bg-slate-200 sm:grid-cols-3">
            <ProfileMetric
              icon={<UserRound className="h-4 w-4" aria-hidden />}
              label="Identità"
              value={user?.full_name ?? "Utente"}
            />
            <ProfileMetric
              icon={<ShieldCheck className="h-4 w-4" aria-hidden />}
              label="Ruolo"
              value={roleLabel(user?.role)}
            />
            <ProfileMetric
              icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}
              label="Creato il"
              value={formatDate(user?.created_at)}
            />
          </dl>

          <div className="border-l-2 border-sky-400 bg-sky-50/70 px-4 py-3 text-sm leading-6 text-slate-700">
            Questo profilo controlla l’accesso alla dashboard, alle valutazioni,
            ai documenti locali e agli stream tecnici. La gestione dei ruoli
            avanzati resta fuori da questa fase.
          </div>
        </div>

        <form className="border-t border-slate-200 pt-6" onSubmit={handleSubmit}>
          <div className="flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-slate-500" aria-hidden />
            <h2 className="text-lg font-semibold text-slate-950">
              Cambia password
            </h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Dopo il cambio, la sessione corrente resta attiva. Le altre sessioni
            aperte vengono revocate per sicurezza.
          </p>

          <div className="mt-8 space-y-6">
            <PasswordField
              label="Password attuale"
              autoComplete="current-password"
              value={currentPassword}
              onChange={setCurrentPassword}
            />
            <PasswordField
              label="Nuova password"
              autoComplete="new-password"
              value={newPassword}
              onChange={setNewPassword}
              hint="Almeno 8 caratteri."
            />
            <PasswordField
              label="Conferma nuova password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={setConfirmPassword}
            />
          </div>

          {error ? (
            <p className="mt-6 border-l-2 border-rose-400 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="mt-6 border-l-2 border-emerald-400 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              {success}
            </p>
          ) : null}

          <Button
            type="submit"
            className="mt-8 h-11 w-full rounded-none bg-slate-950"
            disabled={submitting}
          >
            <KeyRound className="h-4 w-4" aria-hidden />
            {submitting ? "Aggiornamento..." : "Aggiorna password"}
          </Button>
        </form>
      </section>
    </div>
  );
}

function ProfileMetric({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="bg-slate-50 p-4">
      <dt className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
        {icon}
        {label}
      </dt>
      <dd className="mt-3 truncate text-sm font-medium text-slate-950">{value}</dd>
    </div>
  );
}

function PasswordField({
  label,
  autoComplete,
  value,
  onChange,
  hint,
}: {
  label: string;
  autoComplete: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
        {label}
      </span>
      <Input
        className="mt-2 h-11 rounded-none border-x-0 border-t-0 border-slate-300 px-0 text-base focus-visible:ring-0"
        autoComplete={autoComplete}
        type="password"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required
      />
      {hint ? <span className="mt-2 block text-xs text-slate-500">{hint}</span> : null}
    </label>
  );
}

function roleLabel(role: string | undefined): string {
  if (role === "quality_reviewer") return "Presidio qualità";
  return role ?? "Utente";
}

function formatDate(value: string | undefined): string {
  if (!value) return "Non disponibile";
  return new Intl.DateTimeFormat("it-IT", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(new Date(value));
}

function getInitials(value: string): string {
  const parts = value
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return value.slice(0, 2).toUpperCase();
}
