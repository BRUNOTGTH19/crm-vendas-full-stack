import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api.ts";
import { fmtDate, fmtMoney } from "../lib/format.ts";
import type { Dashboard as DashboardData } from "../types.ts";

function Card({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm border border-slate-200">
      <div className={`text-xs font-medium uppercase tracking-wide ${accent}`}>{label}</div>
      <div className="mt-2 text-2xl font-bold text-slate-800">{value}</div>
    </div>
  );
}

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const res = await api.get<DashboardData>("/dashboard");
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
        <button
          onClick={load}
          disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {busy ? "Cargando…" : "Actualizar"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {!data && busy && (
        <div className="text-slate-500 text-sm">Cargando métricas…</div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
            <Card label="Clientes" value={String(data.total_clients)} accent="text-sky-600" />
            <Card label="Ventas" value={String(data.total_sales)} accent="text-sky-600" />
            <Card label="Facturado" value={fmtMoney(data.revenue_paid)} accent="text-emerald-600" />
            <Card label="Pendiente" value={fmtMoney(data.revenue_pending)} accent="text-amber-600" />
            <Card label="Vencidas" value={String(data.overdue_count)} accent="text-red-600" />
            <Card label="Mes actual" value={fmtMoney(data.revenue_month)} accent="text-sky-600" />
          </div>

          <div className="mt-6 grid lg:grid-cols-2 gap-6">
            <div className="rounded-2xl bg-white p-5 shadow-sm border border-slate-200">
              <h2 className="text-sm font-semibold text-slate-700 mb-3">
                Últimas ventas ({data.pending_count} pendientes)
              </h2>
              {data.recent_sales.length === 0 ? (
                <p className="text-sm text-slate-400">Aún no hay ventas registradas.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-400 uppercase">
                      <th className="pb-2">Cliente</th>
                      <th className="pb-2">Fecha</th>
                      <th className="pb-2">Total</th>
                      <th className="pb-2">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_sales.map((s) => (
                      <tr key={s.id} className="border-t border-slate-100">
                        <td className="py-2.5 text-slate-700">{s.client_name}</td>
                        <td className="py-2.5 text-slate-500">{fmtDate(s.sale_date)}</td>
                        <td className="py-2.5 font-medium text-slate-800">{fmtMoney(s.total)}</td>
                        <td className="py-2.5">
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
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="rounded-2xl bg-white p-5 shadow-sm border border-slate-200">
              <h2 className="text-sm font-semibold text-slate-700 mb-3">Productos más vendidos</h2>
              {data.top_products.length === 0 ? (
                <p className="text-sm text-slate-400">Sin datos todavía.</p>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {data.top_products.map((p) => (
                    <li key={p.product_name} className="flex items-center justify-between py-2.5">
                      <span className="text-sm text-slate-700">{p.product_name}</span>
                      <span className="text-sm text-slate-500">
                        {p.total_quantity} uds ·{" "}
                        <span className="font-medium text-slate-800">{fmtMoney(p.total_revenue)}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}