import { useState, type FormEvent } from "react";
import { api, ApiError, resetPassword, setSession } from "../lib/api.ts";
import type { TokenResponse } from "../types.ts";
import { ThemeToggle } from "../components/ThemeToggle.tsx";
import { IconReports } from "../components/icons.tsx";

export function Login({ notice = "" }: { notice?: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Redefinição de senha: simples, direto na tela de login (sem link/código).
  const [mode, setMode] = useState<"login" | "reset">("login");
  const [resetEmail, setResetEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [ok, setOk] = useState("");

  function openReset() {
    setMode("reset");
    setError("");
    setOk("");
    setResetEmail(email);
    setNewPassword("");
    setConfirmPassword("");
  }

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

  async function submitReset(e: FormEvent) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("As senhas não coincidem.");
      return;
    }
    if (newPassword.length < 6) {
      setError("A nova senha precisa ter pelo menos 6 caracteres.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await resetPassword(resetEmail, newPassword);
      setMode("login");
      setEmail(resetEmail);
      setPassword("");
      setOk("Senha redefinida! Faça login com a nova senha.");
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

          {ok && (
            <div
              role="status"
              className="mb-4 rounded-2xl border border-brand-700/20 bg-brand-50 px-4 py-3 text-sm font-semibold text-brand-700 dark:border-brand-300/20 dark:bg-brand-400/15 dark:text-brand-200"
            >
              {ok}
            </div>
          )}

          {mode === "login" ? (
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
          ) : (
            <form onSubmit={submitReset} className="space-y-4">
              <div>
                <label className="label" htmlFor="reset-email">
                  E-mail cadastrado
                </label>
                <input
                  id="reset-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={resetEmail}
                  onChange={(e) => setResetEmail(e.target.value)}
                  className="field"
                  placeholder="voce@crm.com"
                />
              </div>
              <div>
                <label className="label" htmlFor="reset-password">
                  Nova senha
                </label>
                <input
                  id="reset-password"
                  type="password"
                  required
                  minLength={6}
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="field"
                  placeholder="mínimo 6 caracteres"
                />
              </div>
              <div>
                <label className="label" htmlFor="reset-confirm">
                  Confirmar nova senha
                </label>
                <input
                  id="reset-confirm"
                  type="password"
                  required
                  minLength={6}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="field"
                  placeholder="repita a nova senha"
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
                {busy ? "Redefinindo…" : "Redefinir senha"}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  setMode("login");
                  setError("");
                }}
                className="btn btn-ghost w-full"
              >
                Voltar para o login
              </button>
            </form>
          )}

          <p className="mt-6 text-center text-sm leading-relaxed text-ink/70">
            {mode === "login" ? (
              <>
                <button type="button" onClick={openReset} className={footerLink}>
                  Esqueci minha senha
                </button>
                <span aria-hidden className="mx-2 text-ink/40">
                  •
                </span>
                <a href="#/reset-password" className={footerLink}>
                  Tenho um token
                </a>
                <span aria-hidden className="mx-2 text-ink/40">
                  •
                </span>
                Ainda não tem conta?{" "}
                <a href="#/register" className={footerLink}>
                  Cadastre-se
                </a>
              </>
            ) : (
              <>Sem link ou e-mail: informe o e-mail cadastrado e escolha a nova senha.</>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
