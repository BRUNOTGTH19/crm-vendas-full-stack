import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api.ts";
import { fmtDate, fmtMoney } from "../lib/format.ts";
import { StatusBadge } from "../components/StatusBadge.tsx";
import type { Client, Sale } from "../types.ts";

export function History() {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [sales, setSales] = useState<Sale[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        setClients(await api.get<Client[]>("/clients"));
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
      }
    })();
  }, []);

  const load = useCallback(async (id: string) => {
    if (!id) return;
    setBusy(true);
    setError("");
    try {
      setSales(await api.get<Sale[]>(`/sales/client/${id}`));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  const selected = clients.find((c) => String(c.id) === clientId);
  // Soma o saldo devedor (remaining) — vendas com pagamento parcial não devem contar o valor já recebido.
  const total = sales.reduce((acc, s) => acc + parseFloat(s.remaining), 0);

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-white">Histórico</h1>
      <p className="mb-6 text-sm text-zinc-400">
        Consulte todas as vendas de um cliente (doc 3.2 — histórico/consulta por cliente).
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select
          value={clientId}
          onChange={(e) => {
            setClientId(e.target.value);
            load(e.target.value);
          }}
          className="min-w-56 rounded-full border border-white/10 bg-[#26215C] px-4 py-2.5 text-sm text-white focus:border-[#534AB7] focus:outline-none"
        >
          <option value="">Selecione um cliente…</option>
          {clients.map((c) => (
            <option key={c.id} value={String(c.id)}>
              {c.full_name}
            </option>
          ))}
        </select>
        {selected && (
          <span className="text-sm text-zinc-400">
            {sales.length} venda(s) · Saldo devedor{" "}
            <span className="font-semibold text-[#FAC775]">{fmtMoney(total)}</span>
          </span>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {busy ? (
        <p className="text-sm text-zinc-400">Carregando…</p>
      ) : !clientId ? (
        <p className="text-sm text-zinc-400">Escolha um cliente para ver o histórico.</p>
      ) : sales.length === 0 ? (
        <p className="text-sm text-zinc-400">Este cliente ainda não tem vendas.</p>
      ) : (
        <div className="overflow-x-auto rounded-3xl bg-[#26215C] shadow-lg shadow-black/30">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-zinc-400">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Data</th>
                <th className="px-4 py-3">Total</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Vencimento</th>
              </tr>
            </thead>
            <tbody>
              {sales.map((s) => (
                <tr key={s.id} className="border-t border-white/5">
                  <td className="px-4 py-2.5 font-medium text-zinc-300">#{s.id}</td>
                  <td className="px-4 py-2.5 text-zinc-100">{fmtDate(s.sale_date)}</td>
                  <td className="px-4 py-2.5 font-semibold text-white">{fmtMoney(s.total)}</td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={s.status} />
                  </td>
                  <td className="px-4 py-2.5 text-zinc-400">{fmtDate(s.due_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}