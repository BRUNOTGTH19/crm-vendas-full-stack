import { useEffect, useState } from "react";
import { api, ApiError, downloadSaleReceipt } from "../lib/api.ts";
import { Modal } from "../components/Modal.tsx";
import { StatusBadge } from "../components/StatusBadge.tsx";
import { fmtDate, fmtMoney } from "../lib/format.ts";
import type { Client, Sale, SaleStatus } from "../types.ts";

export function Sales() {
  const [sales, setSales] = useState<Sale[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [status, setStatus] = useState<"" | SaleStatus>("");
  const [clientId, setClientId] = useState("");
  const [viewing, setViewing] = useState<Sale | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const clientName = new Map(clients.map((c) => [c.id, c.full_name]));

  async function loadClients() {
    try {
      setClients(await api.get<Client[]>("/clients"));
    } catch {
      /* no bloqueante */
    }
  }

  async function loadSales() {
    setBusy(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (clientId) params.set("client_id", clientId);
      const qs = params.toString();
      setSales(await api.get<Sale[]>(`/sales${qs ? `?${qs}` : ""}`));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadClients();
    loadSales();
  }, []);

  // Recurso de recarga con los filtros actuales (no exponer en deps).
  const [reloadTick, setReloadTick] = useState(0);

  useEffect(() => {
    if (reloadTick > 0) void loadSales();
  }, [reloadTick, status, clientId]);

  async function pay(sale: Sale) {
    if (!window.confirm(`Marcar a venda #${sale.id} como paga?`)) return;
    setBusy(true);
    setError("");
    try {
      await api.patch(`/sales/${sale.id}/pay`);
      await loadSales();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function downloadPdf(saleId: number) {
    setError("");
    try {
      await downloadSaleReceipt(saleId);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  return (
    <SalesPage
      busy={busy}
      error={error}
      sales={sales}
      clientName={clientName}
      status={status}
      setStatus={setStatus}
      clientId={clientId}
      setClientId={setClientId}
      clients={clients}
      onReload={async () => {
        setReloadTick(reloadTick + 1);
        setStatus(status);
      }}
      onView={setViewing}
      onPay={pay}
      onPdf={downloadPdf}
      viewing={viewing}
      setViewing={setViewing}
    />
  );
}

function SalesPage(props: {
  busy: boolean;
  error: string;
  sales: Sale[];
  clientName: Map<number, string>;
  status: "" | SaleStatus;
  setStatus: (v: "" | SaleStatus) => void;
  clientId: string;
  setClientId: (v: string) => void;
  clients: Client[];
  onReload: () => void;
  onView: (s: Sale) => void;
  onPay: (s: Sale) => void;
  onPdf: (saleId: number) => void;
  viewing: Sale | null;
  setViewing: (s: Sale | null) => void;
}) {
  const {
    busy, error, sales, clientName, status, setStatus, clientId, setClientId,
    clients, onReload, onView, onPay, onPdf, viewing, setViewing,
  } = props;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Vendas</h1>
        <a
          href="#/sales/new"
          className="rounded-full bg-[#534AB7] px-4 py-2 text-sm font-medium text-white hover:bg-[#6a60d4]"
        >
          + Nova venda
        </a>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as "" | SaleStatus)}
          className="rounded-xl border border-white/10 bg-[#26215C] px-3 py-2 text-sm text-white focus:border-[#534AB7] focus:outline-none"
        >
          <option value="" className="bg-[#1A1A1A]">Todos os status</option>
          <option value="pending" className="bg-[#1A1A1A]">Pendentes</option>
          <option value="paid" className="bg-[#1A1A1A]">Pagas</option>
        </select>

        <select
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          className="rounded-xl border border-white/10 bg-[#26215C] px-3 py-2 text-sm text-white focus:border-[#534AB7] focus:outline-none"
        >
          <option value="" className="bg-[#1A1A1A]">Todos os clientes</option>
          {clients.map((c) => (
            <option key={c.id} value={String(c.id)} className="bg-[#1A1A1A]">
              {c.full_name}
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={onReload}
          disabled={busy}
          className="rounded-full border border-white/10 px-4 py-2 text-sm font-medium text-zinc-200 hover:bg-white/5 disabled:opacity-50"
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
      ) : sales.length === 0 ? (
        <p className="text-sm text-zinc-400">Nenhuma venda com esses filtros.</p>
      ) : (
        <div className="overflow-x-auto rounded-3xl bg-[#26215C] shadow-lg shadow-black/30">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-400 uppercase border-b border-white/10">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Cliente</th>
                <th className="px-4 py-3">Data</th>
                <th className="px-4 py-3">Total</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Vence</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              {sales.map((s) => (
                <tr key={s.id} className="border-t border-white/5 hover:bg-white/5">
                  <td className="px-4 py-2.5 font-medium text-zinc-300">#{s.id}</td>
                  <td className="px-4 py-2.5 text-white">
                    {clientName.get(s.client_id) ?? `Cliente ${s.client_id}`}
                  </td>
                  <td className="px-4 py-2.5 text-zinc-400">{fmtDate(s.sale_date)}</td>
                  <td className="px-4 py-2.5 font-medium text-white">{fmtMoney(s.total)}</td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={s.status} />
                  </td>
                  <td className="px-4 py-2.5 text-zinc-400">{fmtDate(s.due_date)}</td>
                  <td className="px-4 py-2.5 text-right whitespace-nowrap">
                    <button
                      type="button"
                      onClick={() => onView(s)}
                      className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-medium text-zinc-200 hover:bg-white/5"
                    >
                      Ver
                    </button>
                    {s.status === "pending" && (
                      <button
                        type="button"
                        onClick={() => onPay(s)}
                        disabled={busy}
                        className="ml-1.5 rounded-full border border-emerald-500/40 px-3 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-50"
                      >
                        Pagar
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => onPdf(s.id)}
                      disabled={busy}
                      className="ml-1.5 rounded-full border border-[#534AB7] px-3 py-1.5 text-xs font-medium text-[#B9B2F5] hover:bg-[#534AB7]/20 disabled:opacity-50"
                    >
                      PDF
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {viewing && (
        <Modal title={`Venda #${viewing.id}`} onClose={() => setViewing(null)}>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt className="text-zinc-400">Cliente</dt>
            <dd className="text-white">{clientName.get(viewing.client_id) ?? "—"}</dd>
            <dt className="text-zinc-400">Data</dt>
            <dd className="text-white">{fmtDate(viewing.sale_date)}</dd>
            <dt className="text-zinc-400">Status</dt>
            <dd className="text-white capitalize">{viewing.status}</dd>
            <dt className="text-zinc-400">Vencimento</dt>
            <dd className="text-white">{fmtDate(viewing.due_date)}</dd>
          </dl>
          <table className="mt-4 w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-400 uppercase border-b border-white/10">
                <th className="px-3 py-2">Produto</th>
                <th className="px-3 py-2 text-right">Qtd.</th>
                <th className="px-3 py-2 text-right">P. unit.</th>
                <th className="px-3 py-2 text-right">Subtotal</th>
              </tr>
            </thead>
            <tbody>
              {viewing.items.map((it) => (
                <tr key={it.id} className="border-t border-white/5">
                  <td className="px-3 py-2 text-zinc-200">{it.product_name}</td>
                  <td className="px-3 py-2 text-right text-zinc-400">{it.quantity}</td>
                  <td className="px-3 py-2 text-right text-zinc-400">{fmtMoney(it.unit_price)}</td>
                  <td className="px-3 py-2 text-right font-medium text-[#FAC775]">{fmtMoney(it.subtotal)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-white/10">
                <td colSpan={3} className="px-3 py-2.5 text-right font-semibold text-zinc-300">
                  Total
                </td>
                <td className="px-3 py-2.5 text-right text-base font-bold text-white">
                  {fmtMoney(viewing.total)}
                </td>
              </tr>
            </tfoot>
          </table>
        </Modal>
      )}
    </div>
  );
}