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
      <h1 className="text-2xl font-bold text-slate-800 mb-6">Reportes</h1>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <section className="rounded-2xl bg-white border border-slate-200 shadow-sm p-5">
        <h2 className="text-base font-semibold text-slate-700 mb-4">Ventas por período</h2>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Desde</label>
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Hasta</label>
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none"
            />
          </div>
          <button
            type="button"
            onClick={onLoad}
            disabled={busy}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {busy ? "Cargando…" : "Generar"}
          </button>
        </div>

        {report && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5">
              <div className="rounded-xl bg-slate-50 p-3">
                <div className="text-xs text-slate-400 uppercase">Ventas</div>
                <div className="text-xl font-bold text-slate-800">{report.sales_count}</div>
              </div>
              <div className="rounded-xl bg-emerald-50 p-3">
                <div className="text-xs text-emerald-600 uppercase">Cobrado</div>
                <div className="text-xl font-bold text-emerald-700">{fmtMoney(report.paid_total)}</div>
              </div>
              <div className="rounded-xl bg-amber-50 p-3">
                <div className="text-xs text-amber-600 uppercase">Pendiente</div>
                <div className="text-xl font-bold text-amber-700">{fmtMoney(report.pending_total)}</div>
              </div>
              <div className="rounded-xl bg-slate-100 p-3">
                <div className="text-xs text-slate-400 uppercase">Total</div>
                <div className="text-xl font-bold text-slate-800">{fmtMoney(report.total)}</div>
              </div>
            </div>

            {report.sales.length === 0 ? (
              <p className="mt-5 text-sm text-slate-400">Sin ventas en el período.</p>
            ) : (
              <div className="mt-5 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-400 uppercase border-b border-slate-200">
                      <th className="px-3 py-2">#</th>
                      <th className="px-3 py-2">Cliente</th>
                      <th className="px-3 py-2">Fecha</th>
                      <th className="px-3 py-2 text-right">Total</th>
                      <th className="px-3 py-2">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.sales.map((s) => (
                      <tr key={s.id} className="border-t border-slate-100">
                        <td className="px-3 py-2 text-slate-500">#{s.id}</td>
                        <td className="px-3 py-2 text-slate-700">{s.client_name}</td>
                        <td className="px-3 py-2 text-slate-500">{fmtDate(s.sale_date)}</td>
                        <td className="px-3 py-2 text-right font-medium text-slate-800">{fmtMoney(s.total)}</td>
                        <td className="px-3 py-2">
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
              </div>
            )}
          </>
        )}
      </section>

      <section className="mt-6 rounded-2xl bg-white border border-slate-200 shadow-sm p-5">
        <h2 className="text-base font-semibold text-slate-700 mb-4">Ranking de clientes</h2>
        {clientsReport.length === 0 ? (
          <p className="text-sm text-slate-400">Sin datos todavía.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-400 uppercase border-b border-slate-200">
                <th className="px-3 py-2">Cliente</th>
                <th className="px-3 py-2 text-right">Ventas</th>
                <th className="px-3 py-2 text-right">Facturado</th>
              </tr>
            </thead>
            <tbody>
              {clientsReport.map((r) => (
                <tr key={r.client_id} className="border-t border-slate-100">
                  <td className="px-3 py-2 text-slate-700">{r.client_name}</td>
                  <td className="px-3 py-2 text-right text-slate-500">{r.sales_count}</td>
                  <td className="px-3 py-2 text-right font-medium text-slate-800">{fmtMoney(r.total_revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="mt-6 rounded-2xl bg-white border border-slate-200 shadow-sm p-5">
        <h2 className="text-base font-semibold text-slate-700 mb-4">Productos más vendidos</h2>
        {productsReport.length === 0 ? (
          <p className="text-sm text-slate-400">Sin datos todavía.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-400 uppercase border-b border-slate-200">
                <th className="px-3 py-2">Producto</th>
                <th className="px-3 py-2 text-right">Cantidad</th>
                <th className="px-3 py-2 text-right">Facturado</th>
              </tr>
            </thead>
            <tbody>
              {productsReport.map((r) => (
                <tr key={r.product_name} className="border-t border-slate-100">
                  <td className="px-3 py-2 text-slate-700">{r.product_name}</td>
                  <td className="px-3 py-2 text-right text-slate-500">{r.total_quantity}</td>
                  <td className="px-3 py-2 text-right font-medium text-slate-800">{fmtMoney(r.total_revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}