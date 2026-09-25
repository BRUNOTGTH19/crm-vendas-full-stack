import assert from "node:assert/strict";
import { test } from "node:test";

import {
  assertValidMonth,
  assertValidPeriod,
  cashflowReportDownload,
  chargesReportDownload,
  describeReportError,
  monthLabel,
  paidReportDownload,
  pendingReportDownload,
  periodReportDownload,
} from "../src/lib/report-export.ts";
import { currentMonthISO } from "../src/lib/format.ts";

test("paidReportDownload monta o período na query string", () => {
  const download = paidReportDownload("2026-09-01", "2026-09-30");
  assert.equal(download.path, "/reports/paid?start=2026-09-01&end=2026-09-30");
  assert.equal(download.filename, "vendas_pagas_2026-09-01_a_2026-09-30.pdf");
});

test("paidReportDownload rejeita período invertido antes de chamar a API", () => {
  assert.throws(() => paidReportDownload("2026-09-30", "2026-09-01"), /data inicial/);
});

test("paidReportDownload rejeita datas vazias", () => {
  assert.throws(() => paidReportDownload("", "2026-09-01"), /data inicial e a data final/);
});

test("relatórios sem parâmetro usam os caminhos fixos da API", () => {
  assert.deepEqual(pendingReportDownload(), {
    path: "/reports/pending",
    filename: "vendas_pendentes.pdf",
  });
  assert.deepEqual(chargesReportDownload(), {
    path: "/reports/charges",
    filename: "cobrancas.pdf",
  });
});

test("cashflowReportDownload usa o mês e nomeia o arquivo com ele", () => {
  assert.deepEqual(cashflowReportDownload("2026-09"), {
    path: "/reports/cashflow?month=2026-09",
    filename: "fechamento_caixa_2026-09.pdf",
  });
});

test("periodReportDownload monta o endpoint do PDF do período", () => {
  const download = periodReportDownload("2026-09-01", "2026-09-30");
  assert.equal(download.path, "/reports/period?start=2026-09-01&end=2026-09-30");
  assert.equal(download.filename, "vendas_periodo_2026-09-01_a_2026-09-30.pdf");
});

test("periodReportDownload valida o período antes de chamar a API", () => {
  assert.throws(() => periodReportDownload("2026-09-30", "2026-09-01"), /data inicial/);
  assert.throws(() => periodReportDownload("", "2026-09-30"), /data inicial e a data final/);
});

test("assertValidMonth aceita AAAA-MM e rejeita mês/ano fora de faixa", () => {
  assert.equal(assertValidMonth(" 2026-09 "), "2026-09");
  assert.throws(() => assertValidMonth("2026-13"), /entre 01 e 12/);
  assert.throws(() => assertValidMonth("2026-00"), /entre 01 e 12/);
  assert.throws(() => assertValidMonth("0000-01"), /entre 1900 e 2999/);
  assert.throws(() => assertValidMonth("3000-01"), /entre 1900 e 2999/);
  assert.throws(() => assertValidMonth("2026"), /AAAA-MM/);
  assert.throws(() => assertValidMonth("2026-9-1"), /AAAA-MM/);
});

test("assertValidPeriod exige as duas datas", () => {
  assert.doesNotThrow(() => assertValidPeriod("2026-09-01", "2026-09-01"));
  assert.throws(() => assertValidPeriod("2026-09-01", ""), /data inicial e a data final/);
});

test("monthLabel traduz o mês por extenso em pt-BR", () => {
  assert.equal(monthLabel("2026-09"), "setembro de 2026");
  assert.equal(monthLabel("2026-01"), "janeiro de 2026");
  assert.equal(monthLabel("2026-12"), "dezembro de 2026");
});

test("currentMonthISO devolve AAAA-MM do mês corrente", () => {
  assert.match(currentMonthISO(), /^\d{4}-\d{2}$/);
  assert.equal(currentMonthISO(), new Date().toISOString().slice(0, 7));
});

test("404 vira mensagem de backend desatualizado, não 'Not Found'", () => {
  // Regressão do que o usuário viu no celular: o FastAPI respondia
  // {"detail":"Not Found"} e a tela mostrava só isso.
  const mensagem = describeReportError(404, "Not Found");
  assert.doesNotMatch(mensagem, /Not Found/);
  assert.match(mensagem, /backend/i);
  assert.match(mensagem, /deploy/i);
});

test("401/403, 429 e 5xx têm mensagens próprias", () => {
  assert.match(describeReportError(401, "Token expirado"), /login/i);
  assert.match(describeReportError(403, "Acesso restrito"), /permissão/i);
  assert.match(describeReportError(429, "Muitas tentativas"), /instantes/i);
  assert.match(describeReportError(500, "Erro interno"), /indisponível|iniciando/i);
  assert.match(describeReportError(503, "Service Unavailable"), /indisponível|i/);
});

test("qualquer outro status preserva o detalhe do servidor", () => {
  assert.equal(describeReportError(400, "Período inválido"), "Período inválido");
});
