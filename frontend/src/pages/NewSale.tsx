import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api.ts";
import { fmtMoney, todayISO } from "../lib/format.ts";
import { PageHeader } from "../components/PageHeader.tsx";
import { IconClose, IconPlus } from "../components/icons.tsx";
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
    <div className="animate-fade-up space-y-5">
      <PageHeader
        title="Nova venda"
        eyebrow="Vendas"
        subtitle="Registre o cliente, as datas e os itens. O total é calculado em tempo real."
        actions={
          <a href="#/sales" className="btn btn-ghost btn-sm">
            Voltar para vendas
          </a>
        }
      />

      {ok ? (
        <div className="card card-pad border-brand-700/20 bg-brand-50 dark:border-brand-300/20 dark:bg-brand-400/10">
          <p className="font-bold text-brand-700 dark:text-brand-200">
            Venda registrada com sucesso.
          </p>
          <a href="#/sales" className="btn btn-primary mt-4">
            Ver vendas
          </a>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-5">
          <div className="card card-pad grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="sale-client">
                Cliente
              </label>
              <select
                id="sale-client"
                required
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                className="field"
              >
                <option value="">Selecionar…</option>
                {clients.map((c) => (
                  <option key={c.id} value={String(c.id)}>
                    {c.full_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="sale-date">
                Data da venda
              </label>
              <input
                id="sale-date"
                type="date"
                required
                value={saleDate}
                onChange={(e) => setSaleDate(e.target.value)}
                className="field"
              />
            </div>
            <div>
              <label className="label" htmlFor="sale-status">
                Status
              </label>
              <select
                id="sale-status"
                value={status}
                onChange={(e) => setStatus(e.target.value as SaleStatus)}
                className="field"
              >
                <option value="pending">Pendente (a cobrar)</option>
                <option value="paid">Paga</option>
              </select>
            </div>
            {status === "pending" && (
              <div>
                <label className="label" htmlFor="sale-due-date">
                  Vencimento (obrigatório)
                </label>
                <input
                  id="sale-due-date"
                  type="date"
                  required
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  className="field"
                />
              </div>
            )}
          </div>

          {/* Mobile: cards empilhados — o input do produto usa toda a largura
              disponível e text-base (evita zoom automático no iOS). */}
          <div className="space-y-3 sm:hidden">
            {items.map((it) => (
              <div key={it.key} className="card p-4">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink/70">
                    Produto
                  </span>
                  <button
                    type="button"
                    onClick={() => onRemoveItem(it.key)}
                    disabled={items.length === 1}
                    className="icon-btn text-rose-600 hover:border-rose-300 hover:text-rose-700 dark:text-rose-300"
                    aria-label="Remover linha"
                  >
                    <IconClose className="h-4 w-4" />
                  </button>
                </div>
                <input
                  type="text"
                  value={it.product_name}
                  onChange={(e) => onUpdateItem(it.key, { product_name: e.target.value })}
                  placeholder="Nome do produto"
                  className="field"
                />
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <div>
                    <label className="label">Qtd.</label>
                    <input
                      type="number"
                      min={1}
                      step={1}
                      value={it.quantity}
                      onChange={(e) => onUpdateItem(it.key, { quantity: e.target.value })}
                      className="field text-right"
                    />
                  </div>
                  <div>
                    <label className="label">P. unit. (R$)</label>
                    <input
                      type="number"
                      min={0}
                      step="0.01"
                      value={it.unit_price}
                      onChange={(e) => onUpdateItem(it.key, { unit_price: e.target.value })}
                      placeholder="0.00"
                      className="field text-right"
                    />
                  </div>
                </div>
                <div className="mt-3 text-right text-sm">
                  <span className="text-ink/70">Subtotal: </span>
                  <span className="money font-bold text-brand-700 dark:text-brand-300">
                    {fmtMoney(toNum(it.quantity) * toNum(it.unit_price))}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop/tablet: tabela com overflow horizontal seguro. */}
          <div className="card hidden overflow-x-auto sm:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ink/[0.06] text-left text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink/70 dark:border-white/10">
                  <th className="px-3 py-2.5">Produto</th>
                  <th className="w-24 px-3 py-2.5 text-right">Qtd.</th>
                  <th className="w-32 px-3 py-2.5 text-right">P. unit. (R$)</th>
                  <th className="px-3 py-2.5 text-right">Subtotal</th>
                  <th className="w-16 px-3 py-2.5"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.key} className="border-t border-ink/[0.06] dark:border-white/10">
                    <td className="px-3 py-2">
                      <input
                        type="text"
                        value={it.product_name}
                        onChange={(e) => onUpdateItem(it.key, { product_name: e.target.value })}
                        placeholder="Nome do produto"
                        className="field px-2 py-1.5"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        min={1}
                        step={1}
                        value={it.quantity}
                        onChange={(e) => onUpdateItem(it.key, { quantity: e.target.value })}
                        className="field px-2 py-1.5 text-right"
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
                        className="field px-2 py-1.5 text-right"
                      />
                    </td>
                    <td className="money px-3 py-2 text-right font-bold text-brand-700 dark:text-brand-300">
                      {fmtMoney(toNum(it.quantity) * toNum(it.unit_price))}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <button
                        type="button"
                        onClick={() => onRemoveItem(it.key)}
                        disabled={items.length === 1}
                        className="icon-btn mx-auto text-rose-600 hover:border-rose-300 hover:text-rose-700 dark:text-rose-300"
                        aria-label="Remover linha"
                      >
                        <IconClose className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <button type="button" onClick={onAddItem} className="btn btn-ghost btn-sm">
              <IconPlus className="h-4 w-4" />
              Adicionar produto
            </button>
            <div className="ml-auto rounded-2xl bg-brand-950 px-4 py-3 text-right text-white shadow-card dark:bg-lime dark:text-brand-950">
              <div className="text-[10px] font-extrabold uppercase tracking-[0.16em] opacity-70">
                Total
              </div>
              <div className="money text-2xl font-extrabold">{fmtMoney(total)}</div>
            </div>
          </div>

          {error && (
            <div
              role="alert"
              className="rounded-2xl border border-rose-700/20 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 dark:border-rose-300/20 dark:bg-rose-400/15 dark:text-rose-200"
            >
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3">
            <a href="#/sales" className="btn btn-ghost">
              Cancelar
            </a>
            <button type="submit" disabled={busy} className="btn btn-primary">
              {busy ? "Salvando…" : "Registrar venda"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
