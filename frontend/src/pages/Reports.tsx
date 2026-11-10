import { useCallback, useEffect, useState, type ComponentType } from "react";
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
import { PageHeader } from "../components/PageHeader.tsx";
import {
  IconAlert,
  IconBell,
  IconCalendar,
  IconDatabase,
  IconReceipt,
} from "../components/icons.tsx";
import type { ClientReportRow, ProductReportRow, SalesReport } from "../types.ts";

const ERROR_BOX =
  "rounded-2xl border border-rose-700/20 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 dark:border-rose-300/20 dark:bg-rose-400/15 dark:text-rose-200";

type ExportKind = "period" | "paid" | "pending" | "charges" | "cashflow";

const EXPORTS: {
  kind: ExportKind;
  label: string;
  hint: string;
  Icon: ComponentType<{ className?: string }>;
}[] = [
  { kind: "period", label: "Vendas do período", hint: "pagas e pendentes do período", Icon: IconCalendar },
  { kind: "paid", label: "Vendas pagas", hint: "período das datas acima", Icon: IconReceipt },
  { kind: "pending", label: "Vendas pendentes", hint: "todas em aberto", Icon: IconBell },
  { kind: "charges", label: "Cobranças", hint: "com situação de vencimento", Icon: IconAlert },
  { kind: "cashflow", label: "Fechamento de caixa", hint: "mês selecionado acima", Icon: IconDatabase },
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
      className={`chip ring-1 ring-inset ${
        paid
          ? "bg-brand-50 text-brand-700 ring-brand-700/15 dark:bg-brand-400/15 dark:text-brand-200 dark:ring-brand-300/20"
          : "bg-amber-50 text-amber-700 ring-amber-700/15 dark:bg-amber-400/15 dark:text-amber-200 dark:ring-amber-300/20"
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
    <section className="card mt-4 p-4 sm:mt-6 sm:p-6">
      <h2 className="section-title mb-4">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-ink/70">{emptyText}</p>
      ) : (
        <>
          <ul className="space-y-2 sm:hidden">
            {rows.map((row) => (
              <li
                key={row.key}
                className="flex items-center justify-between gap-3 rounded-2xl bg-ink/[0.04] px-3 py-2.5 dark:bg-white/5"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-ink">{row.name}</div>
                  <div className="text-xs text-ink/70">{row.meta}</div>
                </div>
                <div className="money shrink-0 text-sm font-bold text-ink">{row.value}</div>
              </li>
            ))}
          </ul>

          <div className="hidden overflow-x-auto sm:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ink/[0.06] text-left text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink/70 dark:border-white/10">
                  <th className="px-3 py-2">Nome</th>
                  <th className="px-3 py-2 text-right">{metaHeader}</th>
                  <th className="px-3 py-2 text-right">Faturado</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.key} className="border-t border-ink/[0.06] dark:border-white/10">
                    <td className="px-3 py-2 font-medium text-ink">{row.name}</td>
                    <td className="px-3 py-2 text-right text-ink/70">{row.meta}</td>
                    <td className="money px-3 py-2 text-right font-bold text-ink">{row.value}</td>
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
    <div className="animate-fade-up space-y-4 sm:space-y-6">
      <PageHeader
        title="Relatórios"
        eyebrow="Análise"
        subtitle="Acompanhe os números do período e emita os relatórios em PDF (A4) para imprimir ou enviar ao cliente."
      />

      {error && (
        <div role="alert" className={ERROR_BOX}>
          {error}
        </div>
      )}

      <section className="card card-pad">
        <h2 className="section-title mb-4">Vendas por período</h2>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:flex lg:items-end lg:gap-3">
          <div className="lg:w-44">
            <label className="label" htmlFor="reports-start">
              De
            </label>
            <input
              id="reports-start"
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="field"
            />
          </div>
          <div className="lg:w-44">
            <label className="label" htmlFor="reports-end">
              Até
            </label>
            <input
              id="reports-end"
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="field"
            />
          </div>
          <button
            type="button"
            onClick={onLoad}
            disabled={busy || exporting !== null || periodInvalid}
            className="btn btn-primary lg:w-auto"
          >
            {exporting === "period" ? "Gerando PDF…" : busy ? "Gerando…" : "Gerar e baixar PDF"}
          </button>
        </div>

        <p className="hint mt-2">
          O botão “Gerar” filtra o período e baixa o PDF com todas as vendas
          (pagas e pendentes) das datas selecionadas.
        </p>

        {periodInvalid && (
          <p className="mt-2 text-xs font-semibold text-amber-700 dark:text-amber-300">
            A data inicial não pode ser maior que a data final.
          </p>
        )}

        <p
          aria-live="polite"
          role="status"
          className={`mt-2 text-xs font-semibold ${
            pdfFeedback
              ? pdfFeedback.ok
                ? "text-brand-700 dark:text-brand-300"
                : "text-rose-600 dark:text-rose-300"
              : "text-transparent"
          }`}
        >
          {pdfFeedback?.text ?? "—"}
        </p>

        {loading && !report && <p className="mt-4 text-sm text-ink/70">Carregando…</p>}

        {report && (
          <>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
              <div className="rounded-2xl bg-ink/[0.04] p-3 dark:bg-white/5">
                <div className="text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink/70 sm:text-xs">
                  Vendas
                </div>
                <div className="money text-lg font-extrabold break-words text-ink sm:text-xl">
                  {report.sales_count}
                </div>
              </div>
              <div className="rounded-2xl bg-brand-50 p-3 dark:bg-brand-400/15">
                <div className="text-[11px] font-extrabold uppercase tracking-[0.12em] text-brand-700 sm:text-xs dark:text-brand-200">
                  Recebido
                </div>
                <div className="money text-lg font-extrabold break-words text-brand-700 sm:text-xl dark:text-brand-200">
                  {fmtMoney(report.paid_total)}
                </div>
              </div>
              <div className="rounded-2xl bg-amber-50 p-3 dark:bg-amber-400/15">
                <div className="text-[11px] font-extrabold uppercase tracking-[0.12em] text-amber-700 sm:text-xs dark:text-amber-200">
                  Pendente
                </div>
                <div className="money text-lg font-extrabold break-words text-amber-700 sm:text-xl dark:text-amber-200">
                  {fmtMoney(report.pending_total)}
                </div>
              </div>
              <div className="rounded-2xl bg-ink/[0.04] p-3 dark:bg-white/5">
                <div className="text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink/70 sm:text-xs">
                  Total
                </div>
                <div className="money text-lg font-extrabold break-words text-ink sm:text-xl">
                  {fmtMoney(report.total)}
                </div>
              </div>
            </div>
            {report.sales.length === 0 && (
              <p className="mt-4 text-sm text-ink/70">Nenhuma venda no período.</p>
            )}
          </>
        )}
      </section>

      <section className="card card-pad">
        <h2 className="section-title">Emitir relatório em PDF</h2>
        <p className="hint mt-1">
          Os arquivos são gerados na hora, em A4, com data de emissão, total e
          número de página no rodapé.
        </p>

        <div className="mt-4 sm:max-w-xs">
          <label className="label" htmlFor="reports-month">
            Mês do fechamento de caixa
          </label>
          <input
            id="reports-month"
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="field"
          />
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {EXPORTS.map(({ kind, label, hint, Icon }) => {
            const isExporting = exporting === kind;
            return (
              <button
                key={kind}
                type="button"
                onClick={() => onExport(kind)}
                disabled={exporting !== null}
                aria-label={`Baixar PDF: ${label}`}
                className="flex min-h-14 w-full items-start gap-3 rounded-2xl border border-ink/10 bg-white/60 px-4 py-3 text-left transition hover:border-brand-500 hover:bg-brand-50 disabled:opacity-50 dark:border-white/10 dark:bg-white/5 dark:hover:border-brand-300/40 dark:hover:bg-brand-400/10"
              >
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-100 text-brand-700 dark:bg-brand-400/15 dark:text-brand-200">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-bold text-ink">{label}</span>
                  <span className="block text-[11px] text-ink/70">
                    {isExporting ? "Gerando PDF…" : hint}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        <p
          aria-live="polite"
          role="status"
          className={`mt-3 text-xs font-semibold ${
            pdfFeedback
              ? pdfFeedback.ok
                ? "text-brand-700 dark:text-brand-300"
                : "text-rose-600 dark:text-rose-300"
              : "text-transparent"
          }`}
        >
          {pdfFeedback?.text ?? "—"}
        </p>
      </section>

      {report && report.sales.length > 0 && (
        <section className="card card-pad">
          <h2 className="section-title mb-4">Vendas do período</h2>

          {/* Mobile: cartões — a tabela de 5 colunas não cabe em 360px */}
          <ul className="space-y-2 sm:hidden">
            {report.sales.map((sale) => (
              <li
                key={sale.id}
                className="rounded-2xl bg-ink/[0.04] px-3 py-2.5 dark:bg-white/5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-bold text-ink">
                      {sale.client_name}
                    </div>
                    <div className="text-xs text-ink/70">
                      #{sale.id} · {fmtDate(sale.sale_date)}
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="money text-sm font-bold text-ink">{fmtMoney(sale.total)}</span>
                    <StatusPill status={sale.status} />
                  </div>
                </div>
              </li>
            ))}
          </ul>

          <div className="hidden overflow-x-auto sm:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ink/[0.06] text-left text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink/70 dark:border-white/10">
                  <th className="px-3 py-2">#</th>
                  <th className="px-3 py-2">Cliente</th>
                  <th className="px-3 py-2">Data</th>
                  <th className="px-3 py-2 text-right">Total</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {report.sales.map((sale) => (
                  <tr key={sale.id} className="border-t border-ink/[0.06] dark:border-white/10">
                    <td className="px-3 py-2 text-ink/70">#{sale.id}</td>
                    <td className="px-3 py-2 font-medium text-ink">{sale.client_name}</td>
                    <td className="px-3 py-2 text-ink/70">{fmtDate(sale.sale_date)}</td>
                    <td className="money px-3 py-2 text-right font-bold text-ink">
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
