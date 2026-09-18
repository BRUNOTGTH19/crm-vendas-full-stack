import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../public/sw.js", import.meta.url), "utf8");

function worker({ fail = false, windows = [] } = {}) {
  const handlers = {};
  const notifications = [];
  const logs = [];
  const opened = [];
  const self = {
    addEventListener: (name, callback) => { handlers[name] = callback; },
    registration: { showNotification: async (title, options) => {
      if (fail) throw new Error("simulated");
      notifications.push({ title, options });
    } },
    clients: {
      matchAll: async () => windows,
      openWindow: async (url) => { opened.push(url); },
    },
  };
  vm.runInNewContext(source, {
    self, console: {
      info: (...args) => logs.push(args),
      error: (...args) => logs.push(args),
    },
  });
  async function dispatch(name, event) {
    let pending;
    handlers[name]({ ...event, waitUntil: (promise) => { pending = promise; } });
    assert.ok(pending, "evento deve manter o worker vivo com waitUntil");
    await pending;
  }
  return { dispatch, notifications, logs, opened };
}

for (const state of ["sem janela aberta", "janela em background", "janela em primeiro plano"]) {
  test(`push chama showNotification: ${state} (simulado)`, async () => {
    const w = worker({ windows: state === "sem janela aberta" ? [] : [{}] });
    await w.dispatch("push", { data: { json: () => ({
      title: "🔔 Alerta de cobranças", body: "2 cobranças", url: "/#/queue",
      data: { run_id: "test-run" },
    }) } });
    assert.equal(w.notifications.length, 1);
    const { title, options } = w.notifications[0];
    assert.equal(title, "🔔 Alerta de cobranças");
    assert.equal(options.body, "2 cobranças");
    assert.equal(options.icon, "/icons/icon-192.png");
    assert.equal(options.data.run_id, "test-run");
    assert.equal(options.data.url, "/#/queue");
    assert.equal(w.logs[0][0], "push_displayed");
  });
}

test("payload ausente ou texto simples usa fallback", async () => {
  const w = worker();
  await w.dispatch("push", {});
  await w.dispatch("push", { data: {
    json: () => { throw new Error("not JSON"); }, text: () => "Alerta texto",
  } });
  assert.equal(w.notifications[0].options.data.url, "/#/queue");
  assert.equal(w.notifications[1].options.body, "Alerta texto");
});

test("falha na exibição é registrada", async () => {
  const w = worker({ fail: true });
  await assert.rejects(w.dispatch("push", {}), /simulated/);
  assert.equal(w.logs[0][0], "push_display_failed");
});

test("clique sem janela abre a central de cobranças", async () => {
  const w = worker();
  let closed = false;
  await w.dispatch("notificationclick", { notification: {
    close: () => { closed = true; }, data: { url: "/#/queue" },
  } });
  assert.ok(closed);
  assert.deepEqual(w.opened, ["/#/queue"]);
});

test("clique aguarda navegação e foco da janela existente", async () => {
  const actions = [];
  const window = {
    navigate: async (url) => { actions.push(url); return window; },
    focus: async () => { actions.push("focus"); },
  };
  const w = worker({ windows: [window] });
  await w.dispatch("notificationclick", { notification: { close: () => {}, data: {} } });
  assert.deepEqual(actions, ["/#/queue", "focus"]);
  assert.equal(w.opened.length, 0);
});
