import { useState, type FormEvent } from "react";
import { api, ApiError, setSession } from "../lib/api.ts";
import type { TokenResponse } from "../types.ts";
import { ThemeToggle } from "../components/ThemeToggle.tsx";
import { IconReports } from "../components/icons.tsx";

export function Login({ notice = "" }: { notice?: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api.post<TokenResponse>("/auth/login", { email, password });
      setSession(res);
      window.location.hash = "#/";
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  const footerLink = "font-bold text-brand-700 hover:underline dark:text-brand-300";

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-10 sm:px-6">
      <div className="absolute right-4 top-[max(1rem,env(safe-area-inset-top))]">
        <ThemeToggle />
      </div>

      <div className="animate-fade-up w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-950 text-lime shadow-card dark:bg-lime dark:text-brand-950">
            <IconReports className="h-7 w-7" />
          </div>
          <h1 className="mt-4 text-2xl font-extrabold tracking-[-0.03em] text-ink sm:text-3xl">
            CRM PWA de Vendas
          </h1>
          <p className="page-subtitle mt-1">Acesse seu painel de vendas</p>
        </div>

        <div className="card p-6 sm:p-8">
          {notice && (
            <div
              role="alert"
              className="mb-4 rounded-2xl border border-amber-700/20 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800 dark:border-amber-300/20 dark:bg-amber-400/15 dark:text-amber-200"
            >
              {notice}
            </div>
          )}

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label" htmlFor="login-email">
                E-mail
              </label>
              <input
                id="login-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="field"
                placeholder="voce@crm.com"
              />
            </div>
            <div>
              <label className="label" htmlFor="login-password">
                Senha
              </label>
              <input
                id="login-password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="field"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-2xl border border-rose-700/20 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 dark:border-rose-300/20 dark:bg-rose-400/15 dark:text-rose-200"
              >
                {error}
              </div>
            )}

            <button type="submit" disabled={busy} className="btn btn-primary w-full">
              {busy ? "Entrando…" : "Entrar"}
            </button>
          </form>

          {/* A redefinição por e-mail foi removida: qualquer pessoa que soubesse
              o e-mail trocava a senha (A1). Agora o administrador gera um token
              de uso único e o usuário confirma na tela abaixo. */}
          <p className="mt-6 text-center text-sm leading-relaxed text-ink/70">
            <a href="#/reset-password" className={footerLink}>
              Tenho um token de redefinição
            </a>
            <span aria-hidden className="mx-2 text-ink/40">
              •
            </span>
            Ainda não tem conta?{" "}
            <a href="#/register" className={footerLink}>
              Cadastre-se
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
