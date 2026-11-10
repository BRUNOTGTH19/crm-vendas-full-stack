import { useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api.ts";
import { ThemeToggle } from "../components/ThemeToggle.tsx";
import { IconReports } from "../components/icons.tsx";

export function Register() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setOk(false);
    try {
      await api.post("/auth/register", { name, email, password });
      setOk(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

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
            Criar conta
          </h1>
          <p className="page-subtitle mt-1">CRM PWA de Vendas</p>
        </div>

        <div className="card p-6 sm:p-8">
          {ok ? (
            <div
              role="status"
              className="rounded-2xl border border-brand-700/20 bg-brand-50 px-4 py-3 text-sm font-semibold text-brand-700 dark:border-brand-300/20 dark:bg-brand-400/15 dark:text-brand-200"
            >
              Conta criada com sucesso. Você já pode entrar.
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="label" htmlFor="register-name">
                  Nome
                </label>
                <input
                  id="register-name"
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="field"
                  placeholder="Seu nome completo"
                />
              </div>
              <div>
                <label className="label" htmlFor="register-email">
                  E-mail
                </label>
                <input
                  id="register-email"
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
                <label className="label" htmlFor="register-password">
                  Senha
                </label>
                <input
                  id="register-password"
                  type="password"
                  required
                  minLength={6}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="field"
                  placeholder="Mínimo de 6 caracteres"
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
                {busy ? "Criando…" : "Criar conta"}
              </button>
            </form>
          )}

          <p className="mt-6 text-center text-sm text-ink/70">
            Já tem conta?{" "}
            <a
              href="#/login"
              className="font-bold text-brand-700 hover:underline dark:text-brand-300"
            >
              Entrar
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
