import { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, ApiError } from "../lib/api.ts";
import { fmtDate, fmtMoney } from "../lib/format.ts";
import { StatusBadge } from "../components/StatusBadge.tsx";
import type { Dashboard as DashboardData } from "../types.ts";

const CARD_COLORS = ["#534AB7", "#BA7517", "#7A6FD0", "#FAC775", "#4A4370"];

const TOOLTIP_STYLE = {
  background: "#1A1A1A",
  border: "1px solid #534AB7",
  borderRadius: 12,
  color: "#fff",
};

function Card({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="rounded-3xl bg-[#26215C] p-5 shadow-lg shadow-black/30">
      <div className={`text-xs font-semibold uppercase tracking-wide ${accent}`}>{label}</div>
      <div className="mt-2 text-3xl font-bold text-white">{value}</div>
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

  const pieData = data
    ? [
        { name: "Recebido", value: data.revenue_paid },
        { name: "Pendente", value: data.revenue_pending },
      ].filter((d) => d.value > 0)
    : [];
  const barData =
    data?.top_products.map((p) => ({ name: p.product_name, total: p.total_revenue })) ?? [];

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Painel</h1>
        <button
          onClick={load}
          disabled={busy}
          className="rounded-full bg-[#534AB7] px-4 py-2 text-sm font-semibold text-white hover:bg-[#6a60d4] disabled:opacity-50"
        >
          {busy ? "Carregando…" : "Atualizar"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {!data && busy && <div className="text-sm text-zinc-400">Carregando métricas…</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
            <Card label="Clientes" value={String(data.total_clients)} accent="text-[#7A6FD0]" />
            <Card label="Vendas" value={String(data.total_sales)} accent="text-[#7A6FD0]" />
            <Card label="Recebido" value={fmtMoney(data.revenue_paid)} accent="text-emerald-300" />
            <Card label="Pendente" value={fmtMoney(data.revenue_pending)} accent="text-[#FAC775]" />
            <Card label="Vencidas" value={String(data.overdue_count)} accent="text-red-400" />
            <Card label="Mês atual" value={fmtMoney(data.revenue_month)} accent="text-[#7A6FD0]" />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            {/*DASH_STEP2*/}
            <div className="rounded-3xl bg-[#26215C] p-5 shadow-lg shadow-black/30">
              <h2 className="mb-3 text-sm font-semibold text-zinc-200">
                Últimas vendas ({data.pending_count} pendentes)
              </h2>
              {data.recent_sales.length === 0 ? (
                <p className="text-sm text-zinc-400">Nenhuma venda registrada ainda.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase text-zinc-400">
                      <th className="pb-2">Cliente</th>
                      <th className="pb-2">Data</th>
                      <th className="pb-2">Total</th>
                      <th className="pb-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_sales.map((s) => (
                      <tr key={s.id} className="border-t border-white/5">
                        <td className="py-2.5 text-zinc-100">{s.client_name}</td>
                        <td className="py-2.5 text-zinc-400">{fmtDate(s.sale_date)}</td>
                        <td className="py-2.5 font-semibold text-white">{fmtMoney(s.total)}</td>
                        <td className="py-2.5">
                          <StatusBadge status={s.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="grid gap-6 sm:grid-cols-2">
              <div className="rounded-3xl bg-[#26215C] p-5 shadow-lg shadow-black/30">
                <h2 className="mb-3 text-sm font-semibold text-zinc-200">Recebido vs. pendente</h2>
                {pieData.length === 0 ? (
                  <p className="text-sm text-zinc-400">Sem dados ainda.</p>
                ) : (
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={pieData}
                          dataKey="value"
                          nameKey="name"
                          innerRadius="55%"
                          outerRadius="85%"
                          paddingAngle={3}
                        >
                          {pieData.map((entry, i) => (
                            <Cell key={entry.name} fill={i === 0 ? "#7A6FD0" : "#FAC775"} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(v) => fmtMoney(Number(v))} contentStyle={TOOLTIP_STYLE} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>

              <div className="rounded-3xl bg-[#26215C] p-5 shadow-lg shadow-black/30">
                <h2 className="mb-3 text-sm font-semibold text-zinc-200">Produtos mais vendidos</h2>
                {barData.length === 0 ? (
                  <p className="text-sm text-zinc-400">Sem dados ainda.</p>
                ) : (
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={barData} layout="vertical" margin={{ left: 8 }}>
                        <XAxis type="number" hide />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={80}
                          tick={{ fill: "#d4d2e0", fontSize: 10 }}
                        />
                        <Tooltip formatter={(v) => fmtMoney(Number(v))} contentStyle={TOOLTIP_STYLE} />
                        <Bar dataKey="total" radius={[0, 8, 8, 0]}>
                          {barData.map((_, i) => (
                            <Cell key={i} fill={CARD_COLORS[i % CARD_COLORS.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}