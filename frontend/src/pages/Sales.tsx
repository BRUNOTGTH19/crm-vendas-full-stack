import { useEffect, useState } from "react";
import { api, ApiError, downloadSaleReceipt } from "../lib/api.ts";
import { Modal } from "../components/Modal.tsx";
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
    if (!window.confirm(`¿Marcar la venta #${sale.id} como pagada?`)) return;
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
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Ventas</h1>
        <a
          href="#/sales/new"
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          + Nueva venta
        </a>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as "" | SaleStatus)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white focus:border-sky-500 focus:outline-none"
        >
          <option value="">Todos los estados</option>
          <option value="pending">Pendientes</option>
          <option value="paid">Pagadas</option>
        </select>

        <select
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white focus:border-sky-500 focus:outline-none"
        >
          <option value="">Todos los clientes</option>
          {clients.map((c) => (
            <option key={c.id} value={String(c.id)}>
              {c.full_name}
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={onReload}
          disabled={busy}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200 disabled:opacity-50"
        >
          {busy ? "Cargando…" : "Actualizar"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {busy && sales.length === 0 ? (
        <p className="text-slate-500 text-sm">Cargando…</p>
      ) : sales.length === 0 ? (
        <p className="text-slate-500 text-sm">No hay ventas con esos filtros.</p>
      ) : (
        <div className="overflow-x-auto bg-white rounded-2xl border border-slate-200 shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-400 uppercase border-b border-slate-200">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Cliente</th>
                <th className="px-4 py-3">Fecha</th>
                <th className="px-4 py-3">Total</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Vence</th>
                <th className="px-4 py-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {sales.map((s) => (
                <tr key={s.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-medium text-slate-700">#{s.id}</td>
                  <td className="px-4 py-2.5 text-slate-800">
                    {clientName.get(s.client_id) ?? `Cliente ${s.client_id}`}
                  </td>
                  <td className="px-4 py-2.5 text-slate-500">{fmtDate(s.sale_date)}</td>
                  <td className="px-4 py-2.5 font-medium text-slate-800">{fmtMoney(s.total)}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                        s.status === "paid"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-amber-100 text-amber-700"
                      }`}
                    >
                      {s.status === "paid" ? "Paga" : "Pendiente"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-500">{fmtDate(s.due_date)}</td>
                  <td className="px-4 py-2.5 text-right whitespace-nowrap">
                    <button
                      type="button"
                      onClick={() => onView(s)}
                      className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-200"
                    >
                      Ver
                    </button>
                    {s.status === "pending" && (
                      <button
                        type="button"
                        onClick={() => onPay(s)}
                        disabled={busy}
                        className="ml-1.5 rounded-lg border border-emerald-200 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                      >
                        Pagar
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => onPdf(s.id)}
                      disabled={busy}
                      className="ml-1.5 rounded-lg border border-sky-200 px-3 py-1.5 text-xs font-medium text-sky-700 hover:bg-sky-50 disabled:opacity-50"
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
        <Modal title={`Venta #${viewing.id}`} onClose={() => setViewing(null)}>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt className="text-slate-400">Cliente</dt>
            <dd className="text-slate-800">{clientName.get(viewing.client_id) ?? "—"}</dd>
            <dt className="text-slate-400">Fecha</dt>
            <dd className="text-slate-800">{fmtDate(viewing.sale_date)}</dd>
            <dt className="text-slate-400">Estado</dt>
            <dd className="text-slate-800 capitalize">{viewing.status}</dd>
            <dt className="text-slate-400">Vencimiento</dt>
            <dd className="text-slate-800">{fmtDate(viewing.due_date)}</dd>
          </dl>
          <table className="mt-4 w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-400 uppercase border-b border-slate-200">
                <th className="px-3 py-2">Producto</th>
                <th className="px-3 py-2 text-right">Cant.</th>
                <th className="px-3 py-2 text-right">P. unit.</th>
                <th className="px-3 py-2 text-right">Subtotal</th>
              </tr>
            </thead>
            <tbody>
              {viewing.items.map((it) => (
                <tr key={it.id} className="border-t border-slate-100">
                  <td className="px-3 py-2 text-slate-700">{it.product_name}</td>
                  <td className="px-3 py-2 text-right text-slate-500">{it.quantity}</td>
                  <td className="px-3 py-2 text-right text-slate-500">{fmtMoney(it.unit_price)}</td>
                  <td className="px-3 py-2 text-right font-medium text-slate-800">{fmtMoney(it.subtotal)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-slate-200">
                <td colSpan={3} className="px-3 py-2.5 text-right font-semibold text-slate-700">
                  Total
                </td>
                <td className="px-3 py-2.5 text-right text-base font-bold text-slate-900">
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