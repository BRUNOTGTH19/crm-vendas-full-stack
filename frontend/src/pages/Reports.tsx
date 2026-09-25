import { useCallback, useEffect, useState } from "react";
import { api, ApiError, downloadReportPdf } from "../lib/api.ts";
import {
  cashflowReportDownload,
  chargesReportDownload,
  paidReportDownload,
  pendingReportDownload,
  periodReportDownload,
  type ReportDownload,
} from "../lib/report-export.ts";
import {
  currentMonthISO,
  firstDayOfMonthISO,
  fmtDate,
  fmtMoney,
  todayISO,
} from "../lib/format.ts";
import type { ClientReportRow, ProductReportRow, SalesReport } from "../types.ts";

const CARD = "rounded-3xl bg-[#26215C] p-4 shadow-lg shadow-black/30 sm:p-5";
const LABEL = "mb-1 block text-xs font-medium text-zinc-400";
// `text-base` (16px) evita o zoom automático que o iOS aplica em inputs menores.
const INPUT =
  "w-full rounded-xl border border-white/10 bg-[#1A1A1A] px-3 py-2.5 text-base text-white focus:border-[#534AB7] focus:outline-none sm:text-sm";
// Alvo de toque de 44px no mobile (min-h-11) — o botão antigo tinha ~32px.
const PRIMARY_BUTTON =
  "min-h-11 w-full rounded-full bg-[#534AB7] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#6a60d4] disabled:opacity-50 sm:w-auto";

type ExportKind = "period" | "paid" | "pending" | "charges" | "cashflow";

const EXPORTS: { kind: ExportKind; label: string; hint: string; icon: string }[] = [
  { kind: "period", label: "Vendas do período", hint: "pagas e pendentes do período", icon: "🗓️" },
  { kind: "paid", label: "Vendas pagas", hint: "período das datas acima", icon: "💰" },
  { kind: "pending", label: "Vendas pendentes", hint: "todas em aberto", icon: "⏳" },
  { kind: "charges", label: "Cobranças", hint: "com situação de vencimento", icon: "🔔" },
  { kind: "cashflow", label: "Fechamento de caixa", hint: "mês selecionado acima", icon: "📦" },
];

function buildDownload(
  kind: ExportKind,
  start: string,
  end: string,
  month: string
): ReportDownload {
  switch (kind) {
    case "period":
      return periodReportDownload(start, end);
    case "paid":
      return paidReportDownload(start, end);
    case "pending":
      return pendingReportDownload();
    case "charges":
      return chargesReportDownload();
    case "cashflow":
      return cashflowReportDownload(month);
  }
}

function errorText(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof Error) return err.message;
  return String(err);
}

export function Reports() {
  const [start, setStart] = useState(firstDayOfMonthISO());
  const [end, setEnd] = useState(todayISO());
  const [month, setMonth] = useState(currentMonthISO());
  const [report, setReport] = useState<SalesReport | null>(null);
  const [clientsReport, setClientsReport] = useState<ClientReportRow[]>([]);
  const [productsReport, setProductsReport] = useState<ProductReportRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState<ExportKind | null>(null);
  const [pdfFeedback, setPdfFeedback] = useState<{ ok: boolean; text: string } | null>(null);

  const loadSalesReport = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      setReport(
        await api.get<SalesReport>(
          `/reports/sales?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
        )
      );
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }, [start, end]);

  const loadOthers = useCallback(async () => {
    try {
      const [clients, products] = await Promise.all([
        api.get<ClientReportRow[]>("/reports/clients"),
        api.get<ProductReportRow[]>("/reports/products"),
      ]);
      setClientsReport(clients);
      setProductsReport(products);
    } catch (err) {
      setError(errorText(err));
    }
  }, []);

  useEffect(() => {
    void Promise.all([loadSalesReport(), loadOthers()]).finally(() => setLoading(false));
  }, [loadSalesReport, loadOthers]);

  /**
   * Ação do botão "Gerar": filtra a tabela E baixa o PDF do período escolhido.
   *
   * Antes o botão só recarregava os totais na tela — o usuário selecionava as
   * datas, clicava em "Gerar" e nenhum arquivo era gerado, parecendo que a
   * emissão por período estava quebrada. Os dois passos acontecem juntos, e a
   * tabela é atualizada mesmo se o download falhar (com o erro à parte).
   */
  async function generatePeriod() {
    setPdfFeedback(null);
    setExporting("period");
    try {
      const { path, filename } = periodReportDownload(start, end);
      await downloadReportPdf(path, filename);
      setPdfFeedback({ ok: true, text: `Relatório baixado: ${filename}` });
    } catch (err) {
      setPdfFeedback({ ok: false, text: errorText(err) });
    } finally {
      setExporting(null);
      // Atualiza os números da tela mesmo se o PDF não saiu.
      await loadSalesReport();
    }
  }

  /** Emite o PDF do relatório escolhido e informa o resultado na tela. */
  async function exportPdf(kind: ExportKind) {
    setPdfFeedback(null);
    setExporting(kind);
    try {
      const { path, filename } = buildDownload(kind, start, end, month);
      await downloadReportPdf(path, filename);
      setPdfFeedback({ ok: true, text: `Relatório baixado: ${filename}` });
    } catch (err) {
      setPdfFeedback({ ok: false, text: errorText(err) });
    } finally {
      setExporting(null);
    }
  }

  return (
    <ReportsPage
      start={start}
      setStart={setStart}
      end={end}
      setEnd={setEnd}
      month={month}
      setMonth={setMonth}
      report={report}
      clientsReport={clientsReport}
      productsReport={productsReport}
      loading={loading}
      busy={busy}
      error={error}
      exporting={exporting}
      pdfFeedback={pdfFeedback}
      onLoad={() => void generatePeriod()}
      onExport={exportPdf}
    />
  );
}

// ---------------------------------------------------------------------------
// Subcomponentes de apresentação
// ---------------------------------------------------------------------------
function StatusPill({ status }: { status: string }) {
  const paid = status === "paid";
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${
        paid
          ? "bg-[#2E5E3A]/40 text-[#7FE0A0] ring-1 ring-[#2E5E3A]"
          : "bg-[#BA7517]/30 text-[#FAC775] ring-1 ring-[#BA7517]/60"
      }`}
    >
      {paid ? "Paga" : "Pendente"}
    </span>
  );
}

interface RankingRow {
  key: string | number;
  name: string;
  meta: string;
  value: string;
}

/**
 * Ranking com duas apresentações: lista de cartões no mobile (nomes longos não
 * são cortados por uma tabela de 3 colunas) e tabela a partir de `sm`.
 */
function Ranking({
  title,
  metaHeader,
  rows,
  emptyText,
}: {
  title: string;
  metaHeader: string;
  rows: RankingRow[];
  emptyText: string;
}) {
  return (
    <section className={`mt-4 sm:mt-6 ${CARD}`}>
      <h2 className="mb-4 text-base font-semibold text-zinc-200">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-zinc-400">{emptyText}</p>
      ) : (
        <>
          <ul className="space-y-2 sm:hidden">
            {rows.map((row) => (
              <li
                key={row.key}
                className="flex items-center justify-between gap-3 rounded-2xl bg-white/5 px-3 py-2.5"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm text-zinc-100">{row.name}</div>
                  <div className="text-xs text-zinc-400">{row.meta}</div>
                </div>
                <div className="shrink-0 text-sm font-semibold text-white">{row.value}</div>
              </li>
            ))}
          </ul>

          <div className="hidden overflow-x-auto sm:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10 text-left text-xs uppercase text-zinc-400">
                  <th className="px-3 py-2">Nome</th>
                  <th className="px-3 py-2 text-right">{metaHeader}</th>
                  <th className="px-3 py-2 text-right">Faturado</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.key} className="border-t border-white/5">
                    <td className="px-3 py-2 text-zinc-200">{row.name}</td>
                    <td className="px-3 py-2 text-right text-zinc-400">{row.meta}</td>
                    <td className="px-3 py-2 text-right font-medium text-white">{row.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

interface ReportsPageProps {
  start: string;
  setStart: (value: string) => void;
  end: string;
  setEnd: (value: string) => void;
  month: string;
  setMonth: (value: string) => void;
  report: SalesReport | null;
  clientsReport: ClientReportRow[];
  productsReport: ProductReportRow[];
  loading: boolean;
  busy: boolean;
  error: string;
  exporting: ExportKind | null;
  pdfFeedback: { ok: boolean; text: string } | null;
  onLoad: () => void;
  onExport: (kind: ExportKind) => void;
}

function ReportsPage({
  start,
  setStart,
  end,
  setEnd,
  month,
  setMonth,
  report,
  clientsReport,
  productsReport,
  loading,
  busy,
  error,
  exporting,
  pdfFeedback,
  onLoad,
  onExport,
}: ReportsPageProps) {
  const periodInvalid = Boolean(start && end && start > end);

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">Relatórios</h1>
      <p className="mb-4 mt-1 text-sm text-zinc-400">
        Acompanhe os números do período e emita os relatórios em PDF (A4) para
        imprimir ou enviar ao cliente.
      </p>

      {error && (
        <div
          role="alert"
          className="mb-4 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300"
        >
          {error}
        </div>
      )}

      <section className={CARD}>
        <h2 className="mb-4 text-base font-semibold text-zinc-200">Vendas por período</h2>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:flex lg:items-end lg:gap-3">
          <div className="lg:w-44">
            <label className={LABEL} htmlFor="reports-start">
              De
            </label>
            <input
              id="reports-start"
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className={INPUT}
            />
          </div>
          <div className="lg:w-44">
            <label className={LABEL} htmlFor="reports-end">
              Até
            </label>
            <input
              id="reports-end"
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className={INPUT}
            />
          </div>
          <button
            type="button"
            onClick={onLoad}
            disabled={busy || exporting !== null || periodInvalid}
            className={PRIMARY_BUTTON}
          >
            {exporting === "period" ? "Gerando PDF…" : busy ? "Gerando…" : "Gerar e baixar PDF"}
          </button>
        </div>

        <p className="mt-2 text-xs text-zinc-400">
          O botão “Gerar” filtra o período e baixa o PDF com todas as vendas
          (pagas e pendentes) das datas selecionadas.
        </p>

        {periodInvalid && (
          <p className="mt-2 text-xs text-[#FAC775]">
            A data inicial não pode ser maior que a data final.
          </p>
        )}

        <p
          aria-live="polite"
          role="status"
          className={`mt-2 text-xs ${pdfFeedback ? (pdfFeedback.ok ? "text-emerald-300" : "text-red-300") : "text-transparent"}`}
        >
          {pdfFeedback?.text ?? "—"}
        </p>

        {loading && !report && <p className="mt-4 text-sm text-zinc-400">Carregando…</p>}

        {report && (
          <>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
              <div className="rounded-2xl bg-white/5 p-3">
                <div className="text-[11px] uppercase text-zinc-400 sm:text-xs">Vendas</div>
                <div className="text-lg font-bold break-words text-white sm:text-xl">
                  {report.sales_count}
                </div>
              </div>
              <div className="rounded-2xl bg-emerald-500/10 p-3">
                <div className="text-[11px] uppercase text-emerald-300 sm:text-xs">Recebido</div>
                <div className="text-lg font-bold break-words text-emerald-300 sm:text-xl">
                  {fmtMoney(report.paid_total)}
                </div>
              </div>
              <div className="rounded-2xl bg-[#BA7517]/20 p-3">
                <div className="text-[11px] uppercase text-[#FAC775] sm:text-xs">Pendente</div>
                <div className="text-lg font-bold break-words text-[#FAC775] sm:text-xl">
                  {fmtMoney(report.pending_total)}
                </div>
              </div>
              <div className="rounded-2xl bg-white/5 p-3">
                <div className="text-[11px] uppercase text-zinc-400 sm:text-xs">Total</div>
                <div className="text-lg font-bold break-words text-white sm:text-xl">
                  {fmtMoney(report.total)}
                </div>
              </div>
            </div>
            {report.sales.length === 0 && (
              <p className="mt-4 text-sm text-zinc-400">Nenhuma venda no período.</p>
            )}
          </>
        )}
      </section>

      <section className={`mt-4 sm:mt-6 ${CARD}`}>
        <h2 className="text-base font-semibold text-zinc-200">Emitir relatório em PDF</h2>
        <p className="mt-1 text-xs text-zinc-400">
          Os arquivos são gerados na hora, em A4, com data de emissão, total e
          número de página no rodapé.
        </p>

        <div className="mt-4 sm:max-w-xs">
          <label className={LABEL} htmlFor="reports-month">
            Mês do fechamento de caixa
          </label>
          <input
            id="reports-month"
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className={INPUT}
          />
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {EXPORTS.map((item) => {
            const isExporting = exporting === item.kind;
            return (
              <button
                key={item.kind}
                type="button"
                onClick={() => onExport(item.kind)}
                disabled={exporting !== null}
                aria-label={`Baixar PDF: ${item.label}`}
                className="flex min-h-14 w-full flex-col items-start justify-center gap-0.5 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-left transition-colors hover:border-[#534AB7] hover:bg-[#534AB7]/20 disabled:opacity-50"
              >
                <span className="text-sm font-semibold text-white">
                  <span aria-hidden className="mr-1.5">
                    {item.icon}
                  </span>
                  {item.label}
                </span>
                <span className="text-[11px] text-zinc-400">
                  {isExporting ? "Gerando PDF…" : item.hint}
                </span>
              </button>
            );
          })}
        </div>

        <p
          aria-live="polite"
          role="status"
          className={`mt-3 text-xs ${pdfFeedback ? (pdfFeedback.ok ? "text-emerald-300" : "text-red-300") : "text-transparent"}`}
        >
          {pdfFeedback?.text ?? "—"}
        </p>
      </section>

      {report && report.sales.length > 0 && (
        <section className={`mt-4 sm:mt-6 ${CARD}`}>
          <h2 className="mb-4 text-base font-semibold text-zinc-200">Vendas do período</h2>

          {/* Mobile: cartões — a tabela de 5 colunas não cabe em 360px */}
          <ul className="space-y-2 sm:hidden">
            {report.sales.map((sale) => (
              <li key={sale.id} className="rounded-2xl bg-white/5 px-3 py-2.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-white">
                      {sale.client_name}
                    </div>
                    <div className="text-xs text-zinc-400">
                      #{sale.id} · {fmtDate(sale.sale_date)}
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="text-sm font-bold text-white">{fmtMoney(sale.total)}</span>
                    <StatusPill status={sale.status} />
                  </div>
                </div>
              </li>
            ))}
          </ul>

          <div className="hidden overflow-x-auto sm:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10 text-left text-xs uppercase text-zinc-400">
                  <th className="px-3 py-2">#</th>
                  <th className="px-3 py-2">Cliente</th>
                  <th className="px-3 py-2">Data</th>
                  <th className="px-3 py-2 text-right">Total</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {report.sales.map((sale) => (
                  <tr key={sale.id} className="border-t border-white/5">
                    <td className="px-3 py-2 text-zinc-400">#{sale.id}</td>
                    <td className="px-3 py-2 text-zinc-200">{sale.client_name}</td>
                    <td className="px-3 py-2 text-zinc-400">{fmtDate(sale.sale_date)}</td>
                    <td className="px-3 py-2 text-right font-medium text-white">
                      {fmtMoney(sale.total)}
                    </td>
                    <td className="px-3 py-2">
                      <StatusPill status={sale.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <Ranking
        title="Ranking de clientes"
        metaHeader="Vendas"
        emptyText="Sem dados ainda."
        rows={clientsReport.map((row) => ({
          key: row.client_id,
          name: row.client_name,
          meta: `${row.sales_count} venda(s)`,
          value: fmtMoney(row.total_revenue),
        }))}
      />

      <Ranking
        title="Produtos mais vendidos"
        metaHeader="Quantidade"
        emptyText="Sem dados ainda."
        rows={productsReport.map((row) => ({
          key: row.product_name,
          name: row.product_name,
          meta: `${row.total_quantity} un.`,
          value: fmtMoney(row.total_revenue),
        }))}
      />
    </div>
  );
}
