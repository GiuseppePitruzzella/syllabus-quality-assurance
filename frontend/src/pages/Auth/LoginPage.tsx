import { FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/context/auth";
import { ApiError } from "@/lib/api";
import { AuthShell } from "./AuthShell";

function getRedirectPath(state: unknown): string {
  if (
    state &&
    typeof state === "object" &&
    "from" in state &&
    typeof (state as { from?: { pathname?: unknown } }).from?.pathname === "string"
  ) {
    return (state as { from: { pathname: string } }).from.pathname;
  }
  return "/";
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password });
      navigate(getRedirectPath(location.state), { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Email o password non corretti.");
      } else {
        setError("Accesso non riuscito. Riprova tra qualche istante.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell>
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
          Accesso
        </p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight text-slate-950">
          Entra nella piattaforma.
        </h1>
        <p className="mt-4 text-sm leading-6 text-slate-600">
          Usa il tuo account per consultare dashboard, syllabus, valutazioni e
          impostazioni di governance.
        </p>
      </div>

      <form className="mt-10 space-y-6" onSubmit={handleSubmit}>
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
            autoComplete="current-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>

        {error ? (
          <p className="border-l-2 border-rose-400 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </p>
        ) : null}

        <Button
          type="submit"
          className="h-11 w-full rounded-none bg-slate-950"
          disabled={submitting}
        >
          <LogIn className="h-4 w-4" aria-hidden />
          {submitting ? "Accesso in corso..." : "Accedi"}
        </Button>
      </form>

      <p className="mt-8 text-sm text-slate-600">
        Non hai ancora un account?{" "}
        <Link className="font-medium text-slate-950 underline" to="/register">
          Registrati
        </Link>
      </p>
    </AuthShell>
  );
}
