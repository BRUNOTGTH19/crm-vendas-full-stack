/**
 * URLs e nomes de arquivo dos relatórios PDF (doc 2.5).
 *
 * Fica fora do componente para poder ser testado com `node --test` (mesmo
 * padrão de `lib/user-label.ts`) e para centralizar as regras de validação:
 * o backend responde 400 para mês fora de faixa ou período invertido, então a
 * tela barra o envio antes de gastar uma requisição — em rede móvel isso é a
 * diferença entre um erro imediato e um "não consegui emitir o relatório".
 */

export interface ReportDownload {
  /** Caminho relativo da API (ex.: `/reports/paid?start=...`). */
  path: string;
  /** Nome sugerido do arquivo salvo pelo navegador. */
  filename: string;
}

const MONTH_PATTERN = /^(\d{4})-(\d{2})$/;
const MIN_YEAR = 1900;
const MAX_YEAR = 2999;

const MONTH_NAMES = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

/** Valida `AAAA-MM`; devolve o valor normalizado ou lança Error amigável. */
export function assertValidMonth(month: string): string {
  const value = month.trim();
  const match = MONTH_PATTERN.exec(value);
  if (!match) {
    throw new Error("Informe o mês no formato AAAA-MM.");
  }

  const year = Number(match[1]);
  const monthNumber = Number(match[2]);
  if (monthNumber < 1 || monthNumber > 12) {
    throw new Error("Mês inválido: use um valor entre 01 e 12.");
  }
  if (year < MIN_YEAR || year > MAX_YEAR) {
    throw new Error(`Ano inválido: use um valor entre ${MIN_YEAR} e ${MAX_YEAR}.`);
  }
  return value;
}

/** Valida o período (`AAAA-MM-DD`); data invertida é erro, não relatório vazio. */
export function assertValidPeriod(start: string, end: string): void {
  if (!start || !end) {
    throw new Error("Informe a data inicial e a data final.");
  }
  if (start > end) {
    throw new Error("A data inicial não pode ser maior que a data final.");
  }
}

/** Relatório de vendas pagas dentro do período exibido na tela. */
export function paidReportDownload(start: string, end: string): ReportDownload {
  assertValidPeriod(start, end);
  const params = new URLSearchParams({ start, end });
  return {
    path: `/reports/paid?${params.toString()}`,
    filename: `vendas_pagas_${start}_a_${end}.pdf`,
  };
}

/**
 * Relatório de **todas** as vendas do período (pagas e pendentes) — é o PDF do
 * botão "Gerar" do cartão "Vendas por período".
 */
export function periodReportDownload(start: string, end: string): ReportDownload {
  assertValidPeriod(start, end);
  const params = new URLSearchParams({ start, end });
  return {
    path: `/reports/period?${params.toString()}`,
    filename: `vendas_periodo_${start}_a_${end}.pdf`,
  };
}

/** Relatório de todas as vendas pendentes (sem filtro de período). */
export function pendingReportDownload(): ReportDownload {
  return { path: "/reports/pending", filename: "vendas_pendentes.pdf" };
}

/** Relatório de cobranças pendentes com a situação de cada vencimento. */
export function chargesReportDownload(): ReportDownload {
  return { path: "/reports/charges", filename: "cobrancas.pdf" };
}

/** Fechamento de caixa do mês informado (`AAAA-MM`). */
export function cashflowReportDownload(month: string): ReportDownload {
  const valid = assertValidMonth(month);
  const params = new URLSearchParams({ month: valid });
  return {
    path: `/reports/cashflow?${params.toString()}`,
    filename: `fechamento_caixa_${valid}.pdf`,
  };
}

/** Rótulo amigável de `AAAA-MM` (ex.: `2026-09` → `setembro de 2026`). */
export function monthLabel(month: string): string {
  const valid = assertValidMonth(month);
  const [year, monthNumber] = valid.split("-");
  return `${MONTH_NAMES[Number(monthNumber) - 1]} de ${year}`;
}

/**
 * Traduz falhas HTTP do download de PDF em algo acionável.
 *
 * O caso do **404** é o que mais engana: o FastAPI responde `{"detail":"Not
 * Found"}` quando a rota ainda não existe no backend publicado (deploy do
 * servidor atrasado, ou URL da API apontando para outro serviço). Sem esta
 * tradução o usuário lê só "Not Found" e acha que o relatório está quebrado.
 */
export function describeReportError(status: number, detail: string): string {
  if (status === 404) {
    return "Este relatório ainda não existe no servidor. O backend precisa ser atualizado (deploy) para emitir o PDF do período.";
  }
  if (status === 401 || status === 403) {
    return "Sessão expirada ou sem permissão. Faça login novamente e tente de novo.";
  }
  if (status === 429) {
    return "Muitas tentativas. Aguarde alguns instantes e tente novamente.";
  }
  if ([500, 502, 503, 504].includes(status)) {
    return "O servidor está temporariamente indisponível (pode estar iniciando). Tente novamente em alguns instantes.";
  }
  return detail;
}
