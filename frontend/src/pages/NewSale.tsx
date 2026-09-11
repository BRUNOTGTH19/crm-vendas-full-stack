import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api.ts";
import { fmtMoney, todayISO } from "../lib/format.ts";
import type { Client, SaleInput, SaleStatus } from "../types.ts";

type ItemRow = { key: number; product_name: string; quantity: string; unit_price: string };

let itemKey = 0;
const newItemRow = (): ItemRow => ({
  key: ++itemKey,
  product_name: "",
  quantity: "1",
  unit_price: "",
});

const toNum = (v: string): number => {
  const n = parseFloat(String(v).replace(",", "."));
  return Number.isFinite(n) ? n : 0;
};

export function NewSale() {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [saleDate, setSaleDate] = useState(todayISO());
  const [status, setStatus] = useState<SaleStatus>("pending");
  const [dueDate, setDueDate] = useState("");
  const [items, setItems] = useState<ItemRow[]>([newItemRow()]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);

  const total = items.reduce((acc, it) => acc + toNum(it.quantity) * toNum(it.unit_price), 0);

  useEffect(() => {
    (async () => {
      try {
        setClients(await api.get<Client[]>("/clients"));
      } catch {
        /* no bloqueante */
      }
    })();
  }, []);

  function addItem() {
    setItems([...items, newItemRow()]);
  }

  function removeItem(key: number) {
    if (items.length === 1) return;
    setItems(items.filter((it) => it.key !== key));
  }

  function updateItem(key: number, patch: Partial<ItemRow>) {
    setItems(items.map((it) => (it.key === key ? { ...it, ...patch } : it)));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");

    const emptyProduct = items.some((it) => !it.product_name.trim());
    if (emptyProduct) {
      setError("Preencha o nome de cada produto (ou remova as linhas vazias).");
      return;
    }
    if (!clientId) {
      setError("Selecione um cliente.");
      return;
    }
    if (status === "pending" && !dueDate) {
      setError("A data de vencimento é obrigatória para vendas pendentes.");
      return;
    }

    const payload: SaleInput = {
      client_id: parseInt(clientId, 10),
      sale_date: saleDate,
      status,
      due_date: status === "pending" ? dueDate : null,
      items: items.map((it) => ({
        product_name: it.product_name.trim(),
        quantity: Math.max(1, Math.floor(toNum(it.quantity))),
        unit_price: toNum(it.unit_price),
      })),
    };

    setBusy(true);
    try {
      await api.post("/sales", payload);
      setOk(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <NewSalePage
      busy={busy}
      ok={ok}
      error={error}
      clients={clients}
      clientId={clientId}
      setClientId={setClientId}
      saleDate={saleDate}
      setSaleDate={setSaleDate}
      status={status}
      setStatus={setStatus}
      dueDate={dueDate}
      setDueDate={setDueDate}
      items={items}
      total={total}
      onAddItem={addItem}
      onRemoveItem={removeItem}
      onUpdateItem={updateItem}
      onSubmit={submit}
    />
  );
}

function NewSalePage(props: {
  busy: boolean;
  ok: boolean;
  error: string;
  clients: Client[];
  clientId: string;
  setClientId: (v: string) => void;
  saleDate: string;
  setSaleDate: (v: string) => void;
  status: SaleStatus;
  setStatus: (v: SaleStatus) => void;
  dueDate: string;
  setDueDate: (v: string) => void;
  items: ItemRow[];
  total: number;
  onAddItem: () => void;
  onRemoveItem: (key: number) => void;
  onUpdateItem: (key: number, patch: Partial<ItemRow>) => void;
  onSubmit: (e: FormEvent) => void;
}) {
  const {
    busy, ok, error, clients, clientId, setClientId, saleDate, setSaleDate,
    status, setStatus, dueDate, setDueDate, items, total, onAddItem,
    onRemoveItem, onUpdateItem, onSubmit,
  } = props;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Nova venda</h1>
        <a href="#/sales" className="text-sm text-[#FAC775] hover:underline">
          ← Voltar para vendas
        </a>
      </div>

      {ok ? (
        <div className="rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-6">
          <p className="font-medium text-emerald-300">
            Venda registrada com sucesso.
          </p>
          <a
            href="#/sales"
            className="mt-4 inline-block rounded-full bg-[#534AB7] px-4 py-2 text-sm font-medium text-white hover:bg-[#6a60d4]"
          >
            Ver vendas
          </a>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-zinc-300">Cliente</label>
              <select
                required
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-[#26215C] px-3 py-2.5 text-sm text-white focus:border-[#534AB7] focus:outline-none"
              >
                <option value="" className="bg-[#1A1A1A]">Selecionar…</option>
                {clients.map((c) => (
                  <option key={c.id} value={String(c.id)} className="bg-[#1A1A1A]">
                    {c.full_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-zinc-300">Data da venda</label>
              <input
                type="date"
                required
                value={saleDate}
                onChange={(e) => setSaleDate(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-[#26215C] px-3 py-2.5 text-sm text-white focus:border-[#534AB7] focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-zinc-300">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as SaleStatus)}
                className="w-full rounded-xl border border-white/10 bg-[#26215C] px-3 py-2.5 text-sm text-white focus:border-[#534AB7] focus:outline-none"
              >
                <option value="pending" className="bg-[#1A1A1A]">Pendente (a cobrar)</option>
                <option value="paid" className="bg-[#1A1A1A]">Paga</option>
              </select>
            </div>
            {status === "pending" && (
              <div>
                <label className="mb-1 block text-sm font-medium text-zinc-300">
                  Vencimento (obrigatório)
                </label>
                <input
                  type="date"
                  required
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-[#26215C] px-3 py-2.5 text-sm text-white focus:border-[#534AB7] focus:outline-none"
                />
              </div>
            )}
          </div>

          <div className="overflow-x-auto rounded-3xl bg-[#26215C] shadow-lg shadow-black/30">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-zinc-400 uppercase border-b border-white/10">
                  <th className="px-3 py-2.5">Produto</th>
                  <th className="px-3 py-2.5 w-24 text-right">Qtd.</th>
                  <th className="px-3 py-2.5 w-32 text-right">P. unit. (R$)</th>
                  <th className="px-3 py-2.5 text-right">Subtotal</th>
                  <th className="px-3 py-2.5 w-16"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.key} className="border-t border-white/5">
                    <td className="px-3 py-2">
                      <input
                        type="text"
                        value={it.product_name}
                        onChange={(e) => onUpdateItem(it.key, { product_name: e.target.value })}
                        placeholder="Nome do produto"
                        className="w-full rounded-xl border border-white/10 bg-[#1A1A1A] px-2 py-1.5 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        min={1}
                        step={1}
                        value={it.quantity}
                        onChange={(e) => onUpdateItem(it.key, { quantity: e.target.value })}
                        className="w-full rounded-xl border border-white/10 bg-[#1A1A1A] px-2 py-1.5 text-right text-sm text-white focus:border-[#534AB7] focus:outline-none"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        min={0}
                        step="0.01"
                        value={it.unit_price}
                        onChange={(e) => onUpdateItem(it.key, { unit_price: e.target.value })}
                        placeholder="0.00"
                        className="w-full rounded-xl border border-white/10 bg-[#1A1A1A] px-2 py-1.5 text-right text-sm text-white focus:border-[#534AB7] focus:outline-none"
                      />
                    </td>
                    <td className="px-3 py-2 text-right font-medium text-[#FAC775]">
                      {fmtMoney(toNum(it.quantity) * toNum(it.unit_price))}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <button
                        type="button"
                        onClick={() => onRemoveItem(it.key)}
                        disabled={items.length === 1}
                        className="text-lg leading-none text-red-400 hover:text-red-300 disabled:opacity-40"
                        aria-label="Remover linha"
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <button
              type="button"
              onClick={onAddItem}
              className="rounded-full border border-white/10 px-4 py-2 text-sm font-medium text-zinc-300 hover:bg-white/5"
            >
              + Adicionar produto
            </button>
            <div className="ml-auto text-right">
              <div className="text-xs text-zinc-400 uppercase">Total</div>
              <div className="text-2xl font-bold text-[#FAC775]">{fmtMoney(total)}</div>
            </div>
          </div>

          {error && (
            <div className="rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3">
            <a
              href="#/sales"
              className="rounded-full border border-white/10 px-5 py-2.5 text-sm text-zinc-300 hover:bg-white/5"
            >
              Cancelar
            </a>
            <button
              type="submit"
              disabled={busy}
              className="rounded-full bg-[#534AB7] px-6 py-2.5 text-sm font-semibold text-white hover:bg-[#6a60d4] disabled:opacity-50"
            >
              {busy ? "Salvando…" : "Registrar venda"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}