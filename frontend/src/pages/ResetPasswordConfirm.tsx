import { useState, type FormEvent } from "react";
import { ApiError, confirmPasswordReset } from "../lib/api.ts";

/**
 * Tela pública para confirmar a redefinição com o token entregue pelo admin.
 * O token fica apenas no estado do componente — nunca no localStorage.
 */
export function ResetPasswordConfirm() {
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (password.length < 6) {
      setError("A nova senha precisa ter pelo menos 6 caracteres.");
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
    <div className="flex min-h-screen items-center justify-center bg-[#1A1A1A] p-6 pt-[max(1.5rem,env(safe-area-inset-top))] pb-[max(1.5rem,env(safe-area-inset-bottom))]">
      <div className="w-full max-w-md rounded-3xl bg-[#26215C] p-6 shadow-2xl sm:p-8">
        <div className="mb-6 text-center">
          <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-[#534AB7] text-2xl font-bold text-[#FAC775]">
            C
          </div>
          <h1 className="mt-4 text-2xl font-bold text-white">Redefinir senha</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Use o token entregue pelo administrador. Ele expira em 15 minutos e
            só pode ser usado uma vez.
          </p>
        </div>

        {ok ? (
          <div className="space-y-4">
            <div
              role="status"
              className="rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300"
            >
              Senha redefinida. Todas as sessões antigas foram encerradas.
            </div>
            <a
              href="#/login"
              className="flex min-h-11 w-full items-center justify-center rounded-full bg-[#534AB7] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#6a60d4]"
            >
              Ir para o login
            </a>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label
                htmlFor="reset-token"
                className="mb-1 block text-sm font-medium text-zinc-200"
              >
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
                className="min-h-11 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-2.5 font-mono text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
                placeholder="cole o token recebido"
              />
            </div>
            <div>
              <label
                htmlFor="reset-password"
                className="mb-1 block text-sm font-medium text-zinc-200"
              >
                Nova senha
              </label>
              <input
                id="reset-password"
                type="password"
                required
                minLength={6}
                maxLength={128}
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="min-h-11 w-full rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
                placeholder="mínimo 6 caracteres"
              />
            </div>
            <div>
              <label
                htmlFor="reset-confirmation"
                className="mb-1 block text-sm font-medium text-zinc-200"
              >
                Confirmar nova senha
              </label>
              <input
                id="reset-confirmation"
                type="password"
                required
                minLength={6}
                maxLength={128}
                autoComplete="new-password"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                className="min-h-11 w-full rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
                placeholder="repita a nova senha"
              />
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-2.5 text-sm text-red-300"
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={busy || !token.trim()}
              className="min-h-11 w-full rounded-full bg-[#534AB7] py-2.5 text-sm font-semibold text-white hover:bg-[#6a60d4] disabled:opacity-50"
            >
              {busy ? "Redefinindo…" : "Redefinir senha"}
            </button>
          </form>
        )}

        {!ok && (
          <p className="mt-6 text-center text-sm">
            <a href="#/login" className="font-medium text-[#FAC775] hover:underline">
              Voltar para o login
            </a>
          </p>
        )}
      </div>
    </div>
  );
}
