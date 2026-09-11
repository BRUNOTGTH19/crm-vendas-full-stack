import { useState, type FormEvent } from "react";
import { api, ApiError, setSession } from "../lib/api.ts";
import type { TokenResponse } from "../types.ts";

export function Login() {
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

        <p className="mt-6 text-center text-sm text-zinc-400">
          Ainda não tem conta?{" "}
          <a href="#/register" className="font-medium text-[#FAC775] hover:underline">
            Cadastre-se
          </a>
        </p>
      </div>
    </div>
  );
}