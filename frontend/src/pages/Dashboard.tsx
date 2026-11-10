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
import {
  CHART_AXIS,
  CHART_PAID,
  CHART_PENDING,
  CHART_SERIES,
  CHART_TOOLTIP_STYLE,
} from "../lib/chart-colors.ts";
import { StatusBadge } from "../components/StatusBadge.tsx";
import { PageHeader } from "../components/PageHeader.tsx";
import type { Dashboard as DashboardData } from "../types.ts";

function KpiCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="card p-4 sm:p-5">
      <div className={`text-[11px] font-extrabold uppercase tracking-[0.16em] ${tone}`}>
        {label}
      </div>
      <div className="money mt-2 text-2xl font-extrabold tracking-tight text-ink sm:text-3xl">
        {value}
      </div>
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
    <div className="animate-fade-up space-y-6">
      <PageHeader
        title="Painel"
        eyebrow="Visão geral"
        subtitle="Acompanhe clientes, vendas e o que está pendente de cobrança."
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

      {!data && busy && <div className="skeleton h-28 w-full" />}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <KpiCard
              label="Clientes"
              value={String(data.total_clients)}
              tone="text-brand-700 dark:text-brand-300"
            />
            <KpiCard
              label="Vendas"
              value={String(data.total_sales)}
              tone="text-brand-700 dark:text-brand-300"
            />
            <KpiCard
              label="Recebido"
              value={fmtMoney(data.revenue_paid)}
              tone="text-brand-700 dark:text-brand-300"
            />
            <KpiCard
              label="Pendente"
              value={fmtMoney(data.revenue_pending)}
              tone="text-amber-700 dark:text-amber-300"
            />
            <KpiCard
              label="Vencidas"
              value={String(data.overdue_count)}
              tone="text-rose-700 dark:text-rose-300"
            />
            <KpiCard
              label="Mês atual"
              value={fmtMoney(data.revenue_month)}
              tone="text-sky-700 dark:text-sky-300"
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {/*DASH_STEP2*/}
            <div className="card min-w-0 p-5 sm:p-6">
              <h2 className="section-title">
                Últimas vendas{" "}
                <span className="text-sm font-bold text-ink/70">
                  ({data.pending_count} pendentes)
                </span>
              </h2>
              {data.recent_sales.length === 0 ? (
                <p className="mt-3 text-sm text-ink/70">Nenhuma venda registrada ainda.</p>
              ) : (
                // Tabela com rolagem horizontal: em telas estreitas as 4 colunas
                // não cabem e a página inteira não deve rolar de lado.
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink/70">
                        <th className="pb-2 pr-4">Cliente</th>
                        <th className="pb-2 pr-4">Data</th>
                        <th className="pb-2 pr-4">Total</th>
                        <th className="pb-2">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_sales.map((s) => (
                        <tr
                          key={s.id}
                          className="border-t border-ink/[0.06] dark:border-white/10"
                        >
                          <td className="py-2.5 pr-4 font-semibold text-ink">{s.client_name}</td>
                          <td className="py-2.5 pr-4 text-ink/70">{fmtDate(s.sale_date)}</td>
                          <td className="money py-2.5 pr-4 font-bold text-ink">
                            {fmtMoney(s.total)}
                          </td>
                          <td className="py-2.5">
                            <StatusBadge status={s.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="grid min-w-0 gap-6 sm:grid-cols-2">
              <div className="card min-w-0 p-5 sm:p-6">
                <h2 className="section-title">Recebido vs. pendente</h2>
                {pieData.length === 0 ? (
                  <p className="mt-3 text-sm text-ink/70">Sem dados ainda.</p>
                ) : (
                  <div className="mt-2 h-48">
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
                            <Cell key={entry.name} fill={i === 0 ? CHART_PAID : CHART_PENDING} />
                          ))}
                        </Pie>
                        <Tooltip
                          formatter={(v) => fmtMoney(Number(v))}
                          contentStyle={CHART_TOOLTIP_STYLE}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>

              <div className="card min-w-0 p-5 sm:p-6">
                <h2 className="section-title">Produtos mais vendidos</h2>
                {barData.length === 0 ? (
                  <p className="mt-3 text-sm text-ink/70">Sem dados ainda.</p>
                ) : (
                  <div className="mt-2 h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={barData} layout="vertical" margin={{ left: 8 }}>
                        <XAxis type="number" hide />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={80}
                          tick={{ fill: CHART_AXIS, fontSize: 10 }}
                        />
                        <Tooltip
                          formatter={(v) => fmtMoney(Number(v))}
                          contentStyle={CHART_TOOLTIP_STYLE}
                        />
                        <Bar dataKey="total" radius={[0, 8, 8, 0]}>
                          {barData.map((_, i) => (
                            <Cell key={i} fill={CHART_SERIES[i % CHART_SERIES.length]} />
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
