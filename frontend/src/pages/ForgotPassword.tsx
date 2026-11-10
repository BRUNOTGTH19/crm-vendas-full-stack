import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  passwordResetConfig,
  requestPasswordReset,
} from "../lib/api.ts";
import { ThemeToggle } from "../components/ThemeToggle.tsx";
import { IconReports } from "../components/icons.tsx";

const footerLink = "font-bold text-brand-700 hover:underline dark:text-brand-300";

/**
 * "Esqueci minha senha".
 *
 * Com SMTP configurado no backend, o usuário informa o e-mail e recebe um link
 * de uso único. Sem SMTP, a tela orienta o caminho que já existe: pedir um
 * token ao administrador (ou, se for o próprio admin, redefinir pelo servidor).
 * A resposta é sempre a mesma, então a tela nunca revela se o e-mail existe.
 */
export function ForgotPassword() {
  const [selfService, setSelfService] = useState<boolean | null>(null);
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    passwordResetConfig()
      .then((config) => active && setSelfService(config.self_service))
      .catch(() => active && setSelfService(false));
    return () => {
      active = false;
    };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await requestPasswordReset(email.trim());
      setMessage(response.message);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "Não foi possível enviar o pedido. Tente novamente."
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
            Esqueci minha senha
          </h1>
          <p className="page-subtitle mt-1">
            Vamos devolver o acesso à sua conta
          </p>
        </div>

        <div className="card p-6 sm:p-8">
          {message ? (
            <div
              role="status"
              className="rounded-2xl border border-brand-700/20 bg-brand-50 px-4 py-3 text-sm font-semibold text-brand-800 dark:border-brand-300/20 dark:bg-brand-400/15 dark:text-brand-100"
            >
              {message}
              <p className="mt-3 font-normal leading-relaxed">
                Não recebeu? Confira a caixa de spam ou peça um token ao
                administrador e use{" "}
                <a href="#/reset-password" className={footerLink}>
                  Tenho um token
                </a>
                .
              </p>
            </div>
          ) : selfService === null ? (
            <p className="text-sm text-ink/70">Verificando como recuperar…</p>
          ) : selfService ? (
            <form onSubmit={submit} className="space-y-4">
              <p className="text-sm leading-relaxed text-ink/70">
                Informe o e-mail da sua conta. Se ele estiver cadastrado,
                enviaremos um link válido por 15 minutos para você escolher uma
                nova senha.
              </p>
              <div>
                <label className="label" htmlFor="forgot-email">
                  E-mail
                </label>
                <input
                  id="forgot-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="field"
                  placeholder="voce@crm.com"
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
                {busy ? "Enviando…" : "Enviar link de recuperação"}
              </button>
            </form>
          ) : (
            <div className="space-y-3 text-sm leading-relaxed text-ink/70">
              <p>
                A recuperação por e-mail ainda não está ativada neste servidor.
                Peça ao administrador um <strong>token de redefinição</strong> e
                use a tela{" "}
                <a href="#/reset-password" className={footerLink}>
                  Tenho um token
                </a>
                .
              </p>
              <p className="hint">
                Se você é o administrador, redefina a própria senha no servidor
                (Render → Shell):{" "}
                <code className="rounded bg-ink/5 px-1 py-0.5 font-mono text-[0.75rem] dark:bg-white/10">
                  python manage.py set-password --email seu@email
                </code>
              </p>
            </div>
          )}

          <p className="mt-6 text-center text-sm text-ink/70">
            <a href="#/login" className={footerLink}>
              Voltar para o login
            </a>
            <span aria-hidden className="mx-2 text-ink/40">
              •
            </span>
            <a href="#/reset-password" className={footerLink}>
              Tenho um token
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
