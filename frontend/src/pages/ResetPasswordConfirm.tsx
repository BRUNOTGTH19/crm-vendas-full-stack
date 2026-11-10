import { useState, type FormEvent } from "react";
import { ApiError, confirmPasswordReset } from "../lib/api.ts";
import { ThemeToggle } from "../components/ThemeToggle.tsx";
import { PasswordInput } from "../components/PasswordInput.tsx";
import { IconReports } from "../components/icons.tsx";

/** Token vindo do link do e-mail (`#/reset-password?token=...`). */
function tokenFromUrl(): string {
  const query = window.location.hash.split("?")[1] ?? "";
  return new URLSearchParams(query).get("token")?.trim() ?? "";
}

/**
 * Tela pública para confirmar a redefinição com o token entregue pelo admin
 * ou pelo link do e-mail. O token fica apenas no estado do componente — nunca
 * no localStorage.
 */
export function ResetPasswordConfirm() {
  const [token, setToken] = useState(tokenFromUrl);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (password.length < 8) {
      setError("A nova senha precisa ter pelo menos 8 caracteres.");
      return;
    }
    if (password !== confirmation) {
      setError("As senhas não coincidem.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await confirmPasswordReset(token.trim(), password);
      setOk(true);
      setToken("");
      setPassword("");
      setConfirmation("");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "Não foi possível redefinir a senha. Tente novamente."
      );
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
            Redefinir senha
          </h1>
          <p className="page-subtitle mt-1">
            Use o token entregue pelo administrador. Ele expira em 15 minutos e
            só pode ser usado uma vez.
          </p>
        </div>

        <div className="card p-6 sm:p-8">
          {ok ? (
            <div className="space-y-4">
              <div
                role="status"
                className="rounded-2xl border border-brand-700/20 bg-brand-50 px-4 py-3 text-sm font-semibold text-brand-700 dark:border-brand-300/20 dark:bg-brand-400/15 dark:text-brand-200"
              >
                Senha redefinida. Todas as sessões antigas foram encerradas.
              </div>
              <a href="#/login" className="btn btn-primary w-full">
                Ir para o login
              </a>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <div>
                <label htmlFor="reset-token" className="label">
                  Token de redefinição
                </label>
                <input
                  id="reset-token"
                  type="text"
                  required
                  autoComplete="off"
                  spellCheck={false}
                  value={token}
                  onChange={(event) => setToken(event.target.value)}
                  className="field font-mono"
                  placeholder="cole o token recebido"
                />
              </div>
              <div>
                <label htmlFor="reset-password" className="label">
                  Nova senha
                </label>
                <PasswordInput
                  id="reset-password"
                  required
                  minLength={8}
                  maxLength={72}
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="field"
                  placeholder="mínimo 8 caracteres"
                />
              </div>
              <div>
                <label htmlFor="reset-confirmation" className="label">
                  Confirmar nova senha
                </label>
                <PasswordInput
                  id="reset-confirmation"
                  required
                  minLength={8}
                  maxLength={72}
                  autoComplete="new-password"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
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

              <button
                type="submit"
                disabled={busy || !token.trim()}
                className="btn btn-primary w-full"
              >
                {busy ? "Redefinindo…" : "Redefinir senha"}
              </button>
            </form>
          )}

          {!ok && (
            <p className="mt-6 text-center text-sm">
              <a
                href="#/login"
                className="font-bold text-brand-700 hover:underline dark:text-brand-300"
              >
                Voltar para o login
              </a>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
