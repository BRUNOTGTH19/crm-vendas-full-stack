import assert from "node:assert/strict";
import { test } from "node:test";

import {
  assertValidMonth,
  assertValidPeriod,
  cashflowReportDownload,
  chargesReportDownload,
  monthLabel,
  paidReportDownload,
  pendingReportDownload,
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
