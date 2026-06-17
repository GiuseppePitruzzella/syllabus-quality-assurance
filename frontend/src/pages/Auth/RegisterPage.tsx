import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/context/auth";
import { ApiError } from "@/lib/api";
import { REGISTERABLE_ROLE_OPTIONS } from "@/lib/roles";
import type { RegisterableUserRole } from "@/lib/types";
import { AuthShell } from "./AuthShell";

export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<RegisterableUserRole>("quality_reviewer");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const selectedRole = REGISTERABLE_ROLE_OPTIONS.find((option) => option.value === role);

  if (user) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("La password deve contenere almeno 8 caratteri.");
      return;
    }
    setSubmitting(true);
    try {
      await register({
        full_name: fullName,
        email,
        password,
        role,
      });
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("Esiste già un account associato a questa email.");
      } else {
        setError("Registrazione non riuscita. Controlla i dati e riprova.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell>
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
          Registrazione
        </p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight text-slate-950">
          Crea il tuo accesso.
        </h1>
        <p className="mt-4 text-sm leading-6 text-slate-600">
          Scegli il profilo operativo: guidato per la revisione dei risultati,
          tecnico per ispezionare agenti, RAG e tracciabilità.
        </p>
      </div>

      <form className="mt-10 space-y-6" onSubmit={handleSubmit}>
        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Nome completo
          </span>
          <Input
            className="mt-2 h-11 rounded-none border-x-0 border-t-0 border-slate-300 px-0 text-base focus-visible:ring-0"
            autoComplete="name"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            required
          />
        </label>

        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Email
          </span>
          <Input
            className="mt-2 h-11 rounded-none border-x-0 border-t-0 border-slate-300 px-0 text-base focus-visible:ring-0"
            autoComplete="email"
            inputMode="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>

        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Password
          </span>
          <Input
            className="mt-2 h-11 rounded-none border-x-0 border-t-0 border-slate-300 px-0 text-base focus-visible:ring-0"
            autoComplete="new-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
          <span className="mt-2 block text-xs text-slate-500">
            Almeno 8 caratteri.
          </span>
        </label>

        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Tipo account
          </span>
          <select
            className="mt-2 h-11 w-full rounded-none border-0 border-b border-slate-300 bg-transparent px-0 text-base text-slate-950 outline-none transition-colors focus:border-slate-950"
            value={role}
            onChange={(event) => setRole(event.target.value as RegisterableUserRole)}
          >
            {REGISTERABLE_ROLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <span className="mt-2 block text-xs leading-5 text-slate-500">
            {selectedRole?.description}
          </span>
        </label>

        {error ? (
          <p className="border-l-2 border-rose-400 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </p>
        ) : null}

        <Button
          type="submit"
          className="h-11 w-full rounded-none border border-cyan-300 bg-cyan-50 text-cyan-800 hover:bg-cyan-100"
          disabled={submitting}
        >
          <UserPlus className="h-4 w-4" aria-hidden />
          {submitting ? "Creazione account..." : "Crea account"}
        </Button>
      </form>

      <p className="mt-8 text-sm text-slate-600">
        Hai già un account?{" "}
        <Link className="font-medium text-slate-950 underline" to="/login">
          Accedi
        </Link>
      </p>
    </AuthShell>
  );
}
