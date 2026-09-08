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
      setError("Completá el nombre de cada producto (o quitá las filas vacías).");
      return;
    }
    if (!clientId) {
      setError("Seleccioná un cliente.");
      return;
    }
    if (status === "pending" && !dueDate) {
      setError("La fecha de vencimiento es obligatoria para ventas pendientes.");
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
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Nueva venta</h1>
        <a href="#/sales" className="text-sm text-slate-500 hover:underline">
          ← Volver a ventas
        </a>
      </div>

      {ok ? (
        <div className="rounded-2xl bg-emerald-50 border border-emerald-200 p-6">
          <p className="text-emerald-700 font-medium">
            Venta registrada correctamente.
          </p>
          <a
            href="#/sales"
            className="mt-4 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Ver ventas
          </a>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-6">
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Cliente</label>
              <select
                required
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm bg-white focus:border-sky-500 focus:outline-none"
              >
                <option value="">Seleccionar…</option>
                {clients.map((c) => (
                  <option key={c.id} value={String(c.id)}>
                    {c.full_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Fecha de venta</label>
              <input
                type="date"
                required
                value={saleDate}
                onChange={(e) => setSaleDate(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-sky-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Estado</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as SaleStatus)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm bg-white focus:border-sky-500 focus:outline-none"
              >
                <option value="pending">Pendiente (a cobrar)</option>
                <option value="paid">Pagada</option>
              </select>
            </div>
            {status === "pending" && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Vencimiento (obligatorio)
                </label>
                <input
                  type="date"
                  required
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-sky-500 focus:outline-none"
                />
              </div>
            )}
          </div>

          <div className="rounded-2xl bg-white border border-slate-200 shadow-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-400 uppercase border-b border-slate-200">
                  <th className="px-3 py-2.5">Producto</th>
                  <th className="px-3 py-2.5 w-24 text-right">Cant.</th>
                  <th className="px-3 py-2.5 w-32 text-right">P. unitario (R$)</th>
                  <th className="px-3 py-2.5 text-right">Subtotal</th>
                  <th className="px-3 py-2.5 w-16"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.key} className="border-t border-slate-100">
                    <td className="px-3 py-2">
                      <input
                        type="text"
                        value={it.product_name}
                        onChange={(e) => onUpdateItem(it.key, { product_name: e.target.value })}
                        placeholder="Nombre del producto"
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm focus:border-sky-500 focus:outline-none"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        min={1}
                        step={1}
                        value={it.quantity}
                        onChange={(e) => onUpdateItem(it.key, { quantity: e.target.value })}
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-right text-sm focus:border-sky-500 focus:outline-none"
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
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-right text-sm focus:border-sky-500 focus:outline-none"
                      />
                    </td>
                    <td className="px-3 py-2 text-right font-medium text-slate-700">
                      {fmtMoney(toNum(it.quantity) * toNum(it.unit_price))}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <button
                        type="button"
                        onClick={() => onRemoveItem(it.key)}
                        disabled={items.length === 1}
                        className="text-red-400 hover:text-red-600 text-lg leading-none"
                        aria-label="Quitar fila"
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
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200"
            >
              + Agregar producto
            </button>
            <div className="ml-auto text-right">
              <div className="text-xs text-slate-400 uppercase">Total</div>
              <div className="text-2xl font-bold text-slate-900">{fmtMoney(total)}</div>
            </div>
          </div>

          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3">
            <a
              href="#/sales"
              className="rounded-lg border border-slate-300 px-5 py-2.5 text-sm text-slate-600 hover:bg-slate-200"
            >
              Cancelar
            </a>
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
            >
              {busy ? "Guardando…" : "Registrar venta"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}