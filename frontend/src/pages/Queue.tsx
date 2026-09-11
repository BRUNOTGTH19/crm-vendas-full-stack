import { useCallback, useEffect, useState } from "react";
import { api, ApiError, downloadSaleReceipt } from "../lib/api.ts";
import { fmtDate, fmtMoney, todayISO } from "../lib/format.ts";
import { PDFButton } from "../components/PDFButton.tsx";
import type { Client, Sale } from "../types.ts";

type ChargeSituation = "vencida" | "hoje" | "a-vencer";

function situationOf(sale: Sale): ChargeSituation {
  if (!sale.due_date) return "a-vencer";
  if (sale.due_date < todayISO()) return "vencida";
  if (sale.due_date === todayISO()) return "hoje";
  return "a-vencer";
}

const SITUATION_STYLE: Record<ChargeSituation, string> = {
  vencida: "bg-red-500/15 text-red-300 ring-1 ring-red-500/40",
  hoje: "bg-[#FAC775]/15 text-[#FAC775] ring-1 ring-[#BA7517]/60",
  "a-vencer": "bg-white/5 text-zinc-300 ring-1 ring-white/10",
};

const SITUATION_LABEL: Record<ChargeSituation, string> = {
  vencida: "Vencida",
  hoje: "Vence hoje",
  "a-vencer": "A vencer",
};

export function Queue() {
  const [sales, setSales] = useState<Sale[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const clientName = new Map(clients.map((c) => [c.id, c.full_name]));

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const [pending, allClients] = await Promise.all([
        api.get<Sale[]>("/sales?status=pending"),
        api.get<Client[]>("/clients"),
      ]);
      setSales(pending);
      setClients(allClients);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function receive(sale: Sale) {
    if (!window.confirm(`Dar baixa na cobrança da venda #${sale.id}?`)) return;
    setBusy(true);
    setError("");
    try {
      await api.patch(`/sales/${sale.id}/pay`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  const total = sales.reduce((acc, s) => acc + parseFloat(s.total), 0);
  const ordered = [...sales].sort((a, b) => (a.due_date ?? "").localeCompare(b.due_date ?? ""));
  const overdue = sales.filter((s) => situationOf(s) === "vencida").length;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Cobranças</h1>
          <p className="text-sm text-zinc-400">
            {sales.length} pendente(s) ·{" "}
            <span className={overdue > 0 ? "font-semibold text-red-300" : ""}>
              {overdue} vencida(s)
            </span>{" "}
            · Total {fmtMoney(total)}
          </p>
        </div>
        <button
          onClick={load}
          disabled={busy}
          className="rounded-full bg-[#534AB7] px-4 py-2 text-sm font-semibold text-white hover:bg-[#6a60d4] disabled:opacity-50"
        >
          {busy ? "Carregando…" : "Atualizar"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {busy && sales.length === 0 ? (
        <p className="text-sm text-zinc-400">Carregando…</p>
      ) : ordered.length === 0 ? (
        <p className="text-sm text-zinc-400">Nenhuma cobrança pendente. 🎉</p>
      ) : (
        <div className="space-y-3">
          {ordered.map((s) => {
            const sit = situationOf(s);
            return (
              <div
                key={s.id}
                className="flex flex-wrap items-center gap-3 rounded-3xl bg-[#26215C] p-4 shadow-lg shadow-black/30"
              >
                <div className="min-w-40 flex-1">
                  <div className="font-semibold text-white">
                    {clientName.get(s.client_id) ?? `Cliente ${s.client_id}`}
                  </div>
                  <div className="text-xs text-zinc-400">
                    Venda #{s.id} · {fmtDate(s.sale_date)}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold text-[#FAC775]">{fmtMoney(s.total)}</div>
                  <div className="text-xs text-zinc-400">Vence {fmtDate(s.due_date)}</div>
                </div>
                <span
                  className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${SITUATION_STYLE[sit]}`}
                >
                  {SITUATION_LABEL[sit]}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => receive(s)}
                    disabled={busy}
                    className="rounded-full bg-emerald-500/80 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
                  >
                    Receber
                  </button>
                  <PDFButton onDownload={() => downloadSaleReceipt(s.id)} disabled={busy} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}