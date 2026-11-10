import { useEffect, useState } from "react";
import { api, ApiError, downloadSaleReceipt } from "../lib/api.ts";
import { Modal } from "../components/Modal.tsx";
import { PaymentModal, paymentPayload } from "../components/PaymentModal.tsx";
import { StatusBadge } from "../components/StatusBadge.tsx";
import { PageHeader } from "../components/PageHeader.tsx";
import { IconPlus } from "../components/icons.tsx";
import { fmtDate, fmtMoney } from "../lib/format.ts";
import type { Client, Sale, SaleStatus } from "../types.ts";

const ERROR_BOX =
  "rounded-2xl border border-rose-700/20 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 dark:border-rose-300/20 dark:bg-rose-400/15 dark:text-rose-200";

export function Sales() {
  const [sales, setSales] = useState<Sale[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [status, setStatus] = useState<"" | SaleStatus>("");
  const [clientId, setClientId] = useState("");
  const [viewing, setViewing] = useState<Sale | null>(null);
  const [paying, setPaying] = useState<Sale | null>(null);
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
    setError("");
    setPaying(sale);
  }

  async function confirmPayment(saleId: number, amountPaid: string, newDueDate: string | null) {
    setBusy(true);
    setError("");
    try {
      await api.post("/payments", paymentPayload(saleId, amountPaid, newDueDate));
      setPaying(null);
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
    <>
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

      {paying && (
        <PaymentModal
          sale={paying}
          busy={busy}
          onConfirm={confirmPayment}
          onClose={() => setPaying(null)}
        />
      )}
    </>
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
    <div className="animate-fade-up space-y-5">
      <PageHeader
        title="Vendas"
        eyebrow="Movimento"
        subtitle="Filtre por status ou cliente e acompanhe cada venda."
        actions={
          <a href="#/sales/new" className="btn btn-primary btn-sm">
            <IconPlus className="h-4 w-4" />
            Nova venda
          </a>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as "" | SaleStatus)}
          className="field w-auto"
          aria-label="Filtrar por status"
        >
          <option value="">Todos os status</option>
          <option value="pending">Pendentes</option>
          <option value="paid">Pagas</option>
        </select>

        <select
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          className="field w-auto max-w-[16rem]"
          aria-label="Filtrar por cliente"
        >
          <option value="">Todos os clientes</option>
          {clients.map((c) => (
            <option key={c.id} value={String(c.id)}>
              {c.full_name}
            </option>
          ))}
        </select>

        <button type="button" onClick={onReload} disabled={busy} className="btn btn-ghost btn-sm">
          {busy ? "Carregando…" : "Atualizar"}
        </button>
      </div>

      {error && (
        <div role="alert" className={ERROR_BOX}>
          {error}
        </div>
      )}

      {busy && sales.length === 0 ? (
        <p className="text-sm text-ink/70">Carregando…</p>
      ) : sales.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="text-sm text-ink/70">Nenhuma venda com esses filtros.</p>
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ink/[0.06] text-left text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink/70 dark:border-white/10">
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
                <tr
                  key={s.id}
                  className="border-t border-ink/[0.06] transition hover:bg-ink/[0.03] dark:border-white/10 dark:hover:bg-white/5"
                >
                  <td className="px-4 py-3 font-semibold text-ink/70">#{s.id}</td>
                  <td className="px-4 py-3 font-bold text-ink">
                    {clientName.get(s.client_id) ?? `Cliente ${s.client_id}`}
                  </td>
                  <td className="px-4 py-3 text-ink/70">{fmtDate(s.sale_date)}</td>
                  <td className="money px-4 py-3 font-bold text-ink">{fmtMoney(s.total)}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={s.status} />
                  </td>
                  <td className="px-4 py-3 text-ink/70">{fmtDate(s.due_date)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    <button type="button" onClick={() => onView(s)} className="btn btn-ghost btn-sm">
                      Ver
                    </button>
                    {s.status === "pending" && (
                      <button
                        type="button"
                        onClick={() => onPay(s)}
                        disabled={busy}
                        className="btn btn-lime btn-sm ml-1.5"
                      >
                        Pagar
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => onPdf(s.id)}
                      disabled={busy}
                      className="btn btn-ghost btn-sm ml-1.5"
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
            <dt className="text-ink/70">Cliente</dt>
            <dd className="font-semibold text-ink">{clientName.get(viewing.client_id) ?? "—"}</dd>
            <dt className="text-ink/70">Data</dt>
            <dd className="font-semibold text-ink">{fmtDate(viewing.sale_date)}</dd>
            <dt className="text-ink/70">Status</dt>
            <dd className="text-ink capitalize">{viewing.status}</dd>
            <dt className="text-ink/70">Vencimento</dt>
            <dd className="font-semibold text-ink">{fmtDate(viewing.due_date)}</dd>
          </dl>
          {/* Tabela de itens com rolagem horizontal própria dentro do modal. */}
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ink/[0.06] text-left text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink/70 dark:border-white/10">
                  <th className="px-3 py-2">Produto</th>
                  <th className="px-3 py-2 text-right">Qtd.</th>
                  <th className="px-3 py-2 text-right">P. unit.</th>
                  <th className="px-3 py-2 text-right">Subtotal</th>
                </tr>
              </thead>
              <tbody>
                {viewing.items.map((it) => (
                  <tr key={it.id} className="border-t border-ink/[0.06] dark:border-white/10">
                    <td className="px-3 py-2 font-medium text-ink">{it.product_name}</td>
                    <td className="px-3 py-2 text-right text-ink/70">{it.quantity}</td>
                    <td className="money px-3 py-2 text-right text-ink/70">{fmtMoney(it.unit_price)}</td>
                    <td className="money px-3 py-2 text-right font-bold text-brand-700 dark:text-brand-300">
                      {fmtMoney(it.subtotal)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-ink/10 dark:border-white/15">
                  <td colSpan={3} className="px-3 py-2.5 text-right font-bold text-ink/70">
                    Total
                  </td>
                  <td className="money px-3 py-2.5 text-right text-base font-extrabold text-ink">
                    {fmtMoney(viewing.total)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Modal>
      )}
    </div>
  );
}
