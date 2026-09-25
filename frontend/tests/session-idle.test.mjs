import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ACTIVITY_EVENTS,
  createIdleGuard,
  evaluateIdle,
  IDLE_LOGOUT_MESSAGE,
  IDLE_TIMEOUT_MS,
  IDLE_WARNING_MS,
  isExpired,
  secondsLeft,
} from "../src/lib/session-idle.ts";

const T0 = 1_700_000_000_000;

test("o timeout de inatividade é de 2 minutos", () => {
  assert.equal(IDLE_TIMEOUT_MS, 2 * 60 * 1000);
  assert.equal(IDLE_WARNING_MS, 30 * 1000);
});

test("qualquer evento de atividade émonitorado", () => {
  for (const evento of ["pointerdown", "pointermove", "keydown", "wheel", "touchstart", "focus"]) {
    assert.ok(ACTIVITY_EVENTS.includes(evento), `falta o evento ${evento}`);
  }
});

test("a sessão continua ativa enquanto houver interação", () => {
  const state = evaluateIdle(T0, T0 + 60_000);
  assert.equal(state.expired, false);
  assert.equal(state.warning, false);
  assert.equal(state.remainingMs, 60_000);
});

test("a sessão NÃO expira antes de 2 minutos (regra dos 2 minutos)", () => {
  assert.equal(isExpired(T0, T0 + IDLE_TIMEOUT_MS - 1), false);
  // Logo após o limite: ainda dentro da tolerância do tick de 1s.
  assert.equal(isExpired(T0, T0 + IDLE_TIMEOUT_MS), true);
});

test("expirada após 2 minutos sem nenhuma atividade", () => {
  const state = evaluateIdle(T0, T0 + 10 * 60 * 1000);
  assert.equal(state.expired, true);
  assert.equal(state.remainingMs, 0);
});

test("avisa nos últimos 30 segundos antes de encerrar", () => {
  const dentro = evaluateIdle(T0, T0 + IDLE_TIMEOUT_MS - 29_000);
  assert.equal(dentro.warning, true);
  assert.equal(dentro.expired, false);

  const antes = evaluateIdle(T0, T0 + IDLE_TIMEOUT_MS - 31_000);
  assert.equal(antes.warning, false);
  assert.equal(antes.expired, false);
});

test("a contagem regressiva arredonda para cima", () => {
  assert.equal(secondsLeft(evaluateIdle(T0, T0 + IDLE_TIMEOUT_MS - 29_500)), 30);
  assert.equal(secondsLeft(evaluateIdle(T0, T0 + IDLE_TIMEOUT_MS - 1_200)), 2);
  assert.equal(secondsLeft(evaluateIdle(T0, T0 + IDLE_TIMEOUT_MS + 5_000)), 0);
});

test("renovar a atividade devolve o prazo inteiro", () => {
  // Usuário mexe no mouse aos 100s: o prazo passa a contar do novo instante.
  const ultimoAto = T0 + 100_000;
  assert.equal(evaluateIdle(ultimoAto, ultimoAto + 10_000).remainingMs, IDLE_TIMEOUT_MS - 10_000);
});

test("relógio que anda para trás não gera estado negativo", () => {
  const state = evaluateIdle(T0, T0 - 5_000);
  assert.equal(state.remainingMs, IDLE_TIMEOUT_MS);
  assert.equal(state.expired, false);
});

test("a mensagem de inatividade é exibida na tela de login", () => {
  assert.match(IDLE_LOGOUT_MESSAGE, /falta de atividade/i);
  assert.match(IDLE_LOGOUT_MESSAGE, /login/i);
});

// ---------------------------------------------------------------------------
// Guarda de inatividade (comportamento do logout automático)
// ---------------------------------------------------------------------------

/** Guarda com relógio controlado + registro de expirações. */
function guardEm() {
  const expiracoes = [];
  const guard = createIdleGuard({ onExpire: () => expiracoes.push(true) });
  return { guard, expiracoes };
}

/** Simula o uso: um evento de atividade a cada `intervaloSeg` segundos. */
function usar(guard, de, ate, intervaloSeg = 5) {
  for (let s = de; s <= ate; s += intervaloSeg) {
    const instante = T0 + s * 1000;
    guard.notifyActivity(instante);
    guard.check(instante);
  }
}

test("encerra a sessão ao completar 2 minutos sem interação", () => {
  const { guard, expiracoes } = guardEm();
  guard.reset(T0);

  // 1 minuto de uso normal: nada acontece.
  usar(guard, 0, 55);
  assert.equal(expiracoes.length, 0);

  // Sai do sistema sem clicar em "Sair" e volta mais de 2 minutos depois.
  const volta = T0 + 55_000 + IDLE_TIMEOUT_MS;
  guard.check(volta);

  assert.equal(expiracoes.length, 1, "a sessão deveria ter sido encerrada");
  assert.equal(guard.peek(volta).expired, true);
});

test("qualquer atividade renova o prazo de 2 minutos", () => {
  const { guard, expiracoes } = guardEm();
  guard.reset(T0);

  // Mexe no mouse aos 100s, 190s e 280s: mais de 5 min de uso contínuo.
  usar(guard, 100, 280, 10);
  assert.equal(expiracoes.length, 0);
  assert.equal(guard.peek(T0 + 280_000).expired, false);
});

test("não expira enquanto o usuário continua mexendo no mouse", () => {
  const { guard, expiracoes } = guardEm();
  guard.reset(T0);

  // 5 minutos simulados com atividade a cada 10 segundos.
  usar(guard, 0, 300, 10);
  assert.equal(expiracoes.length, 0);
});

test("o aviso abre 30s antes e a atividade não o cancela sozinha", () => {
  const { guard, expiracoes } = guardEm();
  guard.reset(T0);

  const abrindo = guard.check(T0 + IDLE_TIMEOUT_MS - IDLE_WARNING_MS + 1000);
  assert.equal(abrindo.warning, true);
  assert.equal(abrindo.expired, false);
  assert.equal(secondsLeft(abrindo), IDLE_WARNING_MS / 1000 - 1);

  // Mexer no mouse com o aviso aberto NÃO renova (senão nunca expiraria).
  const mexendo = T0 + IDLE_TIMEOUT_MS - IDLE_WARNING_MS + 2000;
  guard.notifyActivity(mexendo);
  const depois = guard.check(mexendo);
  assert.equal(depois.warning, true);
  assert.equal(depois.remainingMs, 28_000);

  guard.check(T0 + IDLE_TIMEOUT_MS + 2000);
  assert.equal(expiracoes.length, 1);
});

test("'Continuar logado' (reset) devolve o prazo inteiro", () => {
  const { guard, expiracoes } = guardEm();
  guard.reset(T0);

  const antes = T0 + IDLE_TIMEOUT_MS - 10_000;
  guard.check(antes);
  assert.equal(guard.peek(antes).warning, true);

  // Clique em "Continuar logado".
  guard.reset(antes);
  assert.equal(guard.peek(antes).expired, false);
  assert.equal(guard.peek(antes).warning, false);
  assert.equal(guard.peek(antes).remainingMs, IDLE_TIMEOUT_MS);

  // Passados mais 2 minutos, volta a expirar normalmente.
  guard.check(antes + IDLE_TIMEOUT_MS);
  assert.equal(expiracoes.length, 1);
});

test("o logout por inatividade dispara uma única vez", () => {
  const { guard, expiracoes } = guardEm();
  guard.reset(T0);

  const depois = T0 + IDLE_TIMEOUT_MS + 1000;
  for (let i = 0; i < 10; i++) guard.check(depois);

  assert.equal(expiracoes.length, 1, "não pode disparar o logout repetidamente");
});

test("um novo login (reset) não herda a contagem antiga", () => {
  // 1 hora depois: o token do navegador continuaria válido sem o timeout.
  const { guard, expiracoes } = guardEm();
  const novoLogin = T0 + 60 * 60 * 1000;
  guard.reset(novoLogin);

  assert.equal(guard.peek(novoLogin).expired, false);
  assert.equal(guard.peek(novoLogin).remainingMs, IDLE_TIMEOUT_MS);

  guard.check(novoLogin + 1000);
  assert.equal(expiracoes.length, 0);
});