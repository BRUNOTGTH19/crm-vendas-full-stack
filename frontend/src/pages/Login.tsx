import { useState, type FormEvent } from "react";
import { api, ApiError, resetPassword, setSession } from "../lib/api.ts";
import type { TokenResponse } from "../types.ts";

export function Login() {
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

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#1A1A1A] p-6">
      <div className="w-full max-w-md rounded-3xl bg-[#26215C] p-8 shadow-2xl">
        <div className="mb-8 text-center">
          <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-[#534AB7] text-2xl font-bold text-[#FAC775]">
            C
          </div>
          <h1 className="mt-4 text-2xl font-bold text-white">CRM PWA de Vendas</h1>
          <p className="mt-1 text-sm text-zinc-400">Acesse seu painel de vendas</p>
        </div>

        {ok && (
          <div className="mb-4 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2.5 text-sm text-emerald-300">
            {ok}
          </div>
        )}

        {mode === "login" ? (
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-zinc-200">E-mail</label>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
              placeholder="voce@crm.com"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-zinc-200">Senha</label>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-2.5 text-sm text-red-300">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-full bg-[#534AB7] py-2.5 text-sm font-semibold text-white hover:bg-[#6a60d4] disabled:opacity-50"
          >
            {busy ? "Entrando…" : "Entrar"}
          </button>
        </form>
        ) : (
        <form onSubmit={submitReset} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-zinc-200">E-mail cadastrado</label>
            <input
              type="email"
              required
              autoComplete="email"
              value={resetEmail}
              onChange={(e) => setResetEmail(e.target.value)}
              className="w-full rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
              placeholder="voce@crm.com"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-zinc-200">Nova senha</label>
            <input
              type="password"
              required
              minLength={6}
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
              placeholder="mínimo 6 caracteres"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-zinc-200">Confirmar nova senha</label>
            <input
              type="password"
              required
              minLength={6}
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
              placeholder="repita a nova senha"
            />
          </div>

          {error && (
            <div className="rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-2.5 text-sm text-red-300">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-full bg-[#534AB7] py-2.5 text-sm font-semibold text-white hover:bg-[#6a60d4] disabled:opacity-50"
          >
            {busy ? "Redefinindo…" : "Redefinir senha"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setMode("login");
              setError("");
            }}
            className="w-full rounded-full border border-white/10 py-2.5 text-sm text-zinc-300 hover:bg-white/5 disabled:opacity-50"
          >
            Voltar para o login
          </button>
        </form>
        )}

        <p className="mt-6 text-center text-sm text-zinc-400">
          {mode === "login" ? (
            <>
              <button
                type="button"
                onClick={openReset}
                className="font-medium text-[#FAC775] hover:underline"
              >
                Esqueci minha senha
              </button>
              <span className="mx-2 text-zinc-600">•</span>
              Ainda não tem conta?{" "}
              <a href="#/register" className="font-medium text-[#FAC775] hover:underline">
                Cadastre-se
              </a>
            </>
          ) : (
            <>Sem link ou e-mail: informe o e-mail cadastrado e escolha a nova senha.</>
          )}
        </p>
      </div>
    </div>
  );
}