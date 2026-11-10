import { useEffect, useState, type FormEvent } from "react";
import { Modal } from "./Modal.tsx";
import { fmtMoney, todayISO } from "../lib/format.ts";
import type { Sale } from "../types.ts";

interface PaymentModalProps {
  sale: Sale;
  busy: boolean;
  onConfirm: (saleId: number, amountPaid: string, newDueDate: string | null) => Promise<void>;
  onClose: () => void;
}

/**
 * Modal de pagamento (parcial ou total). Pré-preenche o valor com o saldo
 * restante; o campo de nova data de cobrança só aparece para pagamento parcial.
 */
export function PaymentModal({ sale, busy, onConfirm, onClose }: PaymentModalProps) {
  const remaining = parseFloat(sale.remaining);
  const [amount, setAmount] = useState(
    Number.isFinite(remaining) && remaining > 0 ? remaining.toFixed(2) : ""
  );
  const [newDueDate, setNewDueDate] = useState("");
  const [error, setError] = useState("");

  // Quantiza o restante após um pagamento parcial (evita float quebrado).
  const remainingAfter =
    Number.isFinite(parseFloat(amount)) && Number.isFinite(remaining)
      ? Math.round((remaining - parseFloat(amount)) * 100) / 100
      : NaN;
  const partial = Number.isFinite(remainingAfter) && remainingAfter > 0.004;

  useEffect(() => {
    if (!partial) setNewDueDate("");
  }, [partial]);

  function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    const value = parseFloat(amount);
    if (!Number.isFinite(value) || value <= 0) {
      setError("Informe um valor de pagamento maior que zero.");
      return;
    }
    if (Number.isFinite(remaining) && value > remaining + 0.004) {
      setError(`O valor não pode ser maior que o saldo devedor (${fmtMoney(remaining)}).`);
      return;
    }
    void onConfirm(sale.id, value.toFixed(2), partial && newDueDate ? newDueDate : null);
  }

  return (
    <Modal title={`Pagamento — Venda #${sale.id}`} onClose={onClose}>
      <form onSubmit={submit} noValidate>
        <div className="mb-4 grid grid-cols-3 gap-2 text-sm">
          <div className="rounded-2xl bg-ink/[0.04] p-3 dark:bg-white/5">
            <div className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-ink/70">
              Total
            </div>
            <div className="money mt-0.5 font-bold text-ink">{fmtMoney(sale.total)}</div>
          </div>
          <div className="rounded-2xl bg-brand-50 p-3 dark:bg-brand-400/15">
            <div className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-brand-700 dark:text-brand-200">
              Já pago
            </div>
            <div className="money mt-0.5 font-bold text-brand-700 dark:text-brand-200">
              {fmtMoney(sale.amount_paid)}
            </div>
          </div>
          <div className="rounded-2xl bg-amber-50 p-3 dark:bg-amber-400/15">
            <div className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-amber-700 dark:text-amber-200">
              Saldo
            </div>
            <div className="money mt-0.5 font-bold text-amber-700 dark:text-amber-200">
              {fmtMoney(sale.remaining)}
            </div>
          </div>
        </div>

        <label className="label" htmlFor="payment-amount">
          Valor pago <span className="text-rose-600 dark:text-rose-300">*</span>
        </label>
        <input
          id="payment-amount"
          type="number"
          required
          min="0.01"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="field"
        />

        {partial && (
          <>
            <label className="label mt-4" htmlFor="payment-due-date">
              Nova data de cobrança
            </label>
            <input
              id="payment-due-date"
              type="date"
              value={newDueDate}
              onChange={(e) => setNewDueDate(e.target.value)}
              className="field"
            />
            <p className="hint mt-2">
              Pagamento parcial: restará {fmtMoney(remainingAfter)} pendente.
            </p>
          </>
        )}

        {error && (
          <p
            role="alert"
            className="mt-3 rounded-xl border border-rose-700/20 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 dark:border-rose-300/20 dark:bg-rose-400/15 dark:text-rose-200"
          >
            {error}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} disabled={busy} className="btn btn-ghost">
            Cancelar
          </button>
          <button type="submit" disabled={busy} className="btn btn-primary">
            {busy ? "Processando…" : "Confirmar pagamento"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

/** Corpo exato do POST /payments aceito pelo backend (PaymentCreate). */
export function paymentPayload(
  saleId: number,
  amountPaid: string,
  newDueDate: string | null
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    sale_id: saleId,
    amount_paid: amountPaid,
    payment_date: todayISO(),
  };
  if (newDueDate) body.new_due_date = newDueDate;
  return body;
}
