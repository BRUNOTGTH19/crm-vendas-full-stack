import { useCallback, useEffect, useState } from "react";
import { api, ApiError, downloadSaleReceipt, getCollectionReminders } from "../lib/api.ts";
import { fmtDate, fmtMoney, todayISO } from "../lib/format.ts";
import { PDFButton } from "../components/PDFButton.tsx";
import { PaymentModal, paymentPayload } from "../components/PaymentModal.tsx";
import { CollectionModal } from "../components/CollectionModal.tsx";
import { PageHeader } from "../components/PageHeader.tsx";
import { IconAlert } from "../components/icons.tsx";
import type { Client, Sale } from "../types.ts";

type ChargeSituation = "vencida" | "hoje" | "a-vencer";

function situationOf(sale: Sale): ChargeSituation {
  if (!sale.due_date) return "a-vencer";
  if (sale.due_date < todayISO()) return "vencida";
  if (sale.due_date === todayISO()) return "hoje";
  return "a-vencer";
}

const SITUATION_STYLE: Record<ChargeSituation, string> = {
  vencida:
    "bg-rose-50 text-rose-700 ring-rose-700/15 dark:bg-rose-400/15 dark:text-rose-200 dark:ring-rose-300/20",
  hoje: "bg-amber-50 text-amber-700 ring-amber-700/15 dark:bg-amber-400/15 dark:text-amber-200 dark:ring-amber-300/20",
  "a-vencer":
    "bg-ink/5 text-ink/70 ring-ink/10 dark:bg-white/5 dark:text-ink/80 dark:ring-white/10",
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
  const [paying, setPaying] = useState<Sale | null>(null);
  const [collecting, setCollecting] = useState<Sale | null>(null);
  const [dueCount, setDueCount] = useState(0);

  const clientName = new Map(clients.map((c) => [c.id, c.full_name]));

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const [pending, allClients, reminders] = await Promise.all([
        api.get<Sale[]>("/sales?status=pending"),
        api.get<Client[]>("/clients"),
        getCollectionReminders(),
      ]);
      setSales(pending);
      setClients(allClients);
      setDueCount(reminders.length);
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
    setError("");
    setPaying(sale);
  }

  async function confirmPayment(saleId: number, amountPaid: string, newDueDate: string | null) {
    setBusy(true);
    setError("");
    try {
      await api.post("/payments", paymentPayload(saleId, amountPaid, newDueDate));
      setPaying(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  const total = sales.reduce((acc, s) => acc + parseFloat(s.remaining), 0);
  const ordered = [...sales].sort((a, b) => (a.due_date ?? "").localeCompare(b.due_date ?? ""));
  const overdue = sales.filter((s) => situationOf(s) === "vencida").length;

  return (
    <div className="animate-fade-up space-y-5">
      <PageHeader
        title="Cobranças"
        eyebrow="A receber"
        subtitle={`${sales.length} pendente(s) · ${overdue} vencida(s) · Total ${fmtMoney(total)}`}
        actions={
          <button onClick={load} disabled={busy} className="btn btn-primary btn-sm">
            {busy ? "Carregando…" : "Atualizar"}
          </button>
        }
      />

      {error && (
        <div
          role="alert"
          className="rounded-2xl border border-rose-700/20 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 dark:border-rose-300/20 dark:bg-rose-400/15 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      {dueCount > 0 && (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-700/20 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-300/20 dark:bg-amber-400/15 dark:text-amber-200">
          <IconAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            <span className="font-bold">{dueCount}</span> cobrança(s) vencida(s) ou vencendo
            hoje. Use <span className="font-bold">Cobrar</span> para enviar a mensagem
            personalizada no WhatsApp.
          </span>
        </div>
      )}

      {busy && sales.length === 0 ? (
        <p className="text-sm text-ink/70">Carregando…</p>
      ) : ordered.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="text-sm text-ink/70">Nenhuma cobrança pendente.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {ordered.map((s) => {
            const sit = situationOf(s);
            return (
              <div key={s.id} className="card flex flex-wrap items-center gap-3 p-4">
                <div className="min-w-40 flex-1">
                  <div className="font-bold text-ink">
                    {clientName.get(s.client_id) ?? `Cliente ${s.client_id}`}
                  </div>
                  <div className="text-xs text-ink/70">
                    Venda #{s.id} · {fmtDate(s.sale_date)}
                  </div>
                </div>
                <div className="text-right">
                  <div className="money text-lg font-extrabold text-ink">
                    {fmtMoney(s.remaining)}
                  </div>
                  <div className="text-xs text-ink/70">
                    Saldo de {fmtMoney(s.total)} · Vence {fmtDate(s.due_date)}
                  </div>
                </div>
                <span className={`chip ring-1 ring-inset ${SITUATION_STYLE[sit]}`}>
                  {SITUATION_LABEL[sit]}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setCollecting(s)}
                    disabled={busy}
                    className="btn btn-lime btn-sm"
                  >
                    Cobrar
                  </button>
                  <button
                    type="button"
                    onClick={() => receive(s)}
                    disabled={busy}
                    className="btn btn-primary btn-sm"
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

      {paying && (
        <PaymentModal
          sale={paying}
          busy={busy}
          onConfirm={confirmPayment}
          onClose={() => setPaying(null)}
        />
      )}

      {collecting && (
        <CollectionModal
          sale={collecting}
          clientName={clientName.get(collecting.client_id) ?? `Cliente ${collecting.client_id}`}
          onClose={() => setCollecting(null)}
        />
      )}
    </div>
  );
}
