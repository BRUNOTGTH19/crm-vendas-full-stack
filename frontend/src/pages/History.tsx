import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api.ts";
import { fmtDate, fmtMoney } from "../lib/format.ts";
import { StatusBadge } from "../components/StatusBadge.tsx";
import { PageHeader } from "../components/PageHeader.tsx";
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
    <div className="animate-fade-up space-y-5">
      <PageHeader
        title="Histórico"
        eyebrow="Consulta"
        subtitle="Consulte todas as vendas de um cliente e o saldo devedor."
      />

      <div className="flex flex-wrap items-center gap-3">
        <select
          value={clientId}
          onChange={(e) => {
            setClientId(e.target.value);
            load(e.target.value);
          }}
          className="field w-auto min-w-56 max-w-full"
          aria-label="Selecionar cliente"
        >
          <option value="">Selecione um cliente…</option>
          {clients.map((c) => (
            <option key={c.id} value={String(c.id)}>
              {c.full_name}
            </option>
          ))}
        </select>
        {selected && (
          <span className="text-sm text-ink/70">
            {sales.length} venda(s) · Saldo devedor{" "}
            <span className="money font-bold text-ink">{fmtMoney(total)}</span>
          </span>
        )}
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-2xl border border-rose-700/20 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 dark:border-rose-300/20 dark:bg-rose-400/15 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      {busy ? (
        <p className="text-sm text-ink/70">Carregando…</p>
      ) : !clientId ? (
        <div className="card p-8 text-center">
          <p className="text-sm text-ink/70">Escolha um cliente para ver o histórico.</p>
        </div>
      ) : sales.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="text-sm text-ink/70">Este cliente ainda não tem vendas.</p>
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ink/[0.06] text-left text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink/70 dark:border-white/10">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Data</th>
                <th className="px-4 py-3">Total</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Vencimento</th>
              </tr>
            </thead>
            <tbody>
              {sales.map((s) => (
                <tr
                  key={s.id}
                  className="border-t border-ink/[0.06] transition hover:bg-ink/[0.03] dark:border-white/10 dark:hover:bg-white/5"
                >
                  <td className="px-4 py-3 font-semibold text-ink/70">#{s.id}</td>
                  <td className="px-4 py-3 text-ink">{fmtDate(s.sale_date)}</td>
                  <td className="money px-4 py-3 font-bold text-ink">{fmtMoney(s.total)}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={s.status} />
                  </td>
                  <td className="px-4 py-3 text-ink/70">{fmtDate(s.due_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
