import { useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api.ts";

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
    <div className="flex min-h-screen items-center justify-center bg-[#1A1A1A] p-6">
      <div className="w-full max-w-md rounded-3xl bg-[#26215C] p-8 shadow-2xl">
        <div className="mb-8 text-center">
          <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-[#534AB7] text-2xl font-bold text-[#FAC775]">
            C
          </div>
          <h1 className="mt-4 text-2xl font-bold text-white">Criar conta</h1>
          <p className="mt-1 text-sm text-zinc-400">CRM PWA de Vendas</p>
        </div>

        {ok ? (
          <div className="rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
            Conta criada com sucesso. Você já pode entrar.
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-zinc-200">Nome</label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
                placeholder="Seu nome completo"
              />
            </div>
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
                minLength={6}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
                placeholder="Mínimo de 6 caracteres"
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
              {busy ? "Criando…" : "Criar conta"}
            </button>
          </form>
        )}

        <p className="mt-6 text-center text-sm text-zinc-400">
          Já tem conta?{" "}
          <a href="#/login" className="font-medium text-[#FAC775] hover:underline">
            Entrar
          </a>
        </p>
      </div>
    </div>
  );
}