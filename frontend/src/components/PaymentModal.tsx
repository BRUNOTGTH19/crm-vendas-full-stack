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
        <div className="mb-4 grid grid-cols-3 gap-3 text-sm">
          <div>
            <div className="text-xs uppercase text-zinc-400">Total</div>
            <div className="font-semibold text-white">{fmtMoney(sale.total)}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-zinc-400">Já pago</div>
            <div className="font-semibold text-zinc-200">{fmtMoney(sale.amount_paid)}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-zinc-400">Saldo</div>
            <div className="font-semibold text-[#FAC775]">{fmtMoney(sale.remaining)}</div>
          </div>
        </div>

        <label className="mb-1 block text-sm font-medium text-zinc-300">
          Valor pago <span className="text-red-400">*</span>
        </label>
        <input
          type="number"
          required
          min="0.01"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="w-full rounded-xl border border-white/10 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
        />

        {partial && (
          <>
            <label className="mb-1 mt-4 block text-sm font-medium text-zinc-300">
              Nova data de cobrança <span className="text-zinc-500">(opcional)</span>
            </label>
            <input
              type="date"
              value={newDueDate}
              onChange={(e) => setNewDueDate(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
            />
            <p className="mt-2 text-xs text-zinc-400">
              Pagamento parcial: restará {fmtMoney(remainingAfter)} pendente.
            </p>
          </>
        )}

        {error && (
          <p className="mt-3 rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-full border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5 disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={busy}
            className="rounded-full bg-emerald-500/80 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
          >
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