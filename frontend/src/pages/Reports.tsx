import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api.ts";
import { firstDayOfMonthISO, fmtDate, fmtMoney, todayISO } from "../lib/format.ts";
import type { ClientReportRow, ProductReportRow, SalesReport } from "../types.ts";

export function Reports() {
  const [start, setStart] = useState(firstDayOfMonthISO());
  const [end, setEnd] = useState(todayISO());
  const [report, setReport] = useState<SalesReport | null>(null);
  const [clientsReport, setClientsReport] = useState<ClientReportRow[]>([]);
  const [productsReport, setProductsReport] = useState<ProductReportRow[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadSalesReport() {
    setBusy(true);
    setError("");
    try {
      setReport(
        await api.get<SalesReport>(
          `/reports/sales?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
        )
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadOthers() {
    try {
      setClientsReport(await api.get<ClientReportRow[]>("/reports/clients"));
      setProductsReport(await api.get<ProductReportRow[]>("/reports/products"));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  useEffect(() => {
    loadSalesReport();
    loadOthers();
  }, []);

  return (
    <ReportPage
      busy={busy}
      error={error}
      start={start}
      setStart={setStart}
      end={end}
      setEnd={setEnd}
      onLoad={loadSalesReport}
      report={report}
      clientsReport={clientsReport}
      productsReport={productsReport}
    />
  );
}

function ReportPage(props: {
  busy: boolean;
  error: string;
  start: string;
  setStart: (v: string) => void;
  end: string;
  setEnd: (v: string) => void;
  onLoad: () => void;
  report: SalesReport | null;
  clientsReport: ClientReportRow[];
  productsReport: ProductReportRow[];
}) {
  const {
    busy, error, start, setStart, end, setEnd, onLoad,
    report, clientsReport, productsReport,
  } = props;

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-white">Relatórios</h1>

      {error && (
        <div className="mb-4 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <section className="rounded-3xl bg-[#26215C] p-5 shadow-lg shadow-black/30">
        <h2 className="mb-4 text-base font-semibold text-zinc-200">Vendas por período</h2>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-400">De</label>
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="rounded-xl border border-white/10 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#534AB7] focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-400">Até</label>
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="rounded-xl border border-white/10 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#534AB7] focus:outline-none"
            />
          </div>
          <button
            type="button"
            onClick={onLoad}
            disabled={busy}
            className="rounded-full bg-[#534AB7] px-4 py-2 text-sm font-medium text-white hover:bg-[#6a60d4] disabled:opacity-50"
          >
            {busy ? "Carregando…" : "Gerar"}
          </button>
        </div>

        {report && (
          <>
            <div className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-4">
              <div className="rounded-2xl bg-white/5 p-3">
                <div className="text-xs text-zinc-400 uppercase">Vendas</div>
                <div className="text-xl font-bold text-white">{report.sales_count}</div>
              </div>
              <div className="rounded-2xl bg-emerald-500/10 p-3">
                <div className="text-xs text-emerald-300 uppercase">Recebido</div>
                <div className="text-xl font-bold text-emerald-300">{fmtMoney(report.paid_total)}</div>
              </div>
              <div className="rounded-2xl bg-[#BA7517]/20 p-3">
                <div className="text-xs text-[#FAC775] uppercase">Pendente</div>
                <div className="text-xl font-bold text-[#FAC775]">{fmtMoney(report.pending_total)}</div>
              </div>
              <div className="rounded-2xl bg-white/5 p-3">
                <div className="text-xs text-zinc-400 uppercase">Total</div>
                <div className="text-xl font-bold text-white">{fmtMoney(report.total)}</div>
              </div>
            </div>

            {report.sales.length === 0 ? (
              <p className="mt-5 text-sm text-zinc-400">Nenhuma venda no período.</p>
            ) : (
              <div className="mt-5 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-zinc-400 uppercase border-b border-white/10">
                      <th className="px-3 py-2">#</th>
                      <th className="px-3 py-2">Cliente</th>
                      <th className="px-3 py-2">Data</th>
                      <th className="px-3 py-2 text-right">Total</th>
                      <th className="px-3 py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.sales.map((s) => (
                      <tr key={s.id} className="border-t border-white/5">
                        <td className="px-3 py-2 text-zinc-400">#{s.id}</td>
                        <td className="px-3 py-2 text-zinc-200">{s.client_name}</td>
                        <td className="px-3 py-2 text-zinc-400">{fmtDate(s.sale_date)}</td>
                        <td className="px-3 py-2 text-right font-medium text-white">{fmtMoney(s.total)}</td>
                        <td className="px-3 py-2">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                              s.status === "paid"
                                ? "bg-[#2E5E3A]/40 text-[#7FE0A0] ring-1 ring-[#2E5E3A]"
                                : "bg-[#BA7517]/30 text-[#FAC775] ring-1 ring-[#BA7517]/60"
                            }`}
                          >
                            {s.status === "paid" ? "Paga" : "Pendente"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>

      <section className="mt-6 rounded-3xl bg-[#26215C] p-5 shadow-lg shadow-black/30">
        <h2 className="mb-4 text-base font-semibold text-zinc-200">Ranking de clientes</h2>
        {clientsReport.length === 0 ? (
          <p className="text-sm text-zinc-400">Sem dados ainda.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-400 uppercase border-b border-white/10">
                <th className="px-3 py-2">Cliente</th>
                <th className="px-3 py-2 text-right">Vendas</th>
                <th className="px-3 py-2 text-right">Faturado</th>
              </tr>
            </thead>
            <tbody>
              {clientsReport.map((r) => (
                <tr key={r.client_id} className="border-t border-white/5">
                  <td className="px-3 py-2 text-zinc-200">{r.client_name}</td>
                  <td className="px-3 py-2 text-right text-zinc-400">{r.sales_count}</td>
                  <td className="px-3 py-2 text-right font-medium text-white">{fmtMoney(r.total_revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="mt-6 rounded-3xl bg-[#26215C] p-5 shadow-lg shadow-black/30">
        <h2 className="mb-4 text-base font-semibold text-zinc-200">Produtos mais vendidos</h2>
        {productsReport.length === 0 ? (
          <p className="text-sm text-zinc-400">Sem dados ainda.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-400 uppercase border-b border-white/10">
                <th className="px-3 py-2">Produto</th>
                <th className="px-3 py-2 text-right">Quantidade</th>
                <th className="px-3 py-2 text-right">Faturado</th>
              </tr>
            </thead>
            <tbody>
              {productsReport.map((r) => (
                <tr key={r.product_name} className="border-t border-white/5">
                  <td className="px-3 py-2 text-zinc-200">{r.product_name}</td>
                  <td className="px-3 py-2 text-right text-zinc-400">{r.total_quantity}</td>
                  <td className="px-3 py-2 text-right font-medium text-white">{fmtMoney(r.total_revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}