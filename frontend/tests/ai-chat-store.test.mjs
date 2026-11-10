import assert from "node:assert/strict";
import { test } from "node:test";

import {
  MAX_CONVERSATIONS,
  MAX_MESSAGES_PER_CONVERSATION,
  activeConversation,
  appendMessage,
  appendMessageTo,
  deleteConversation,
  emptyChatState,
  loadChatState,
  saveChatState,
  startConversation,
  storageKey,
} from "../src/lib/ai-chat-store.ts";

/** `localStorage` em memória, com a mesma interface usada pelo módulo. */
function memoryStorage() {
  const data = new Map();
  return {
    data,
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
  };
}

test("chave do histórico é separada por usuário", () => {
  assert.equal(storageKey(7), "ai_chat:v1:user:7");
  assert.notEqual(storageKey(7), storageKey(8));
});

test("sem nada salvo devolve estado vazio", () => {
  assert.deepEqual(loadChatState(1, memoryStorage()), emptyChatState());
});

test("salva e recarrega a conversa com a mensagem e o título", () => {
  const storage = memoryStorage();
  const now = 1_700_000_000_000;

  let state = appendMessage(emptyChatState(), { role: "user", text: "Quanto vendi?" }, now);
  state = appendMessage(state, { role: "assistant", text: "Você vendeu R$ 10." }, now + 1);

  assert.equal(saveChatState(1, state, storage), true);
  const loaded = loadChatState(1, storage);

  assert.equal(loaded.conversations.length, 1);
  assert.equal(loaded.conversations[0].title, "Quanto vendi?");
  assert.deepEqual(loaded.conversations[0].messages, [
    { role: "user", text: "Quanto vendi?" },
    { role: "assistant", text: "Você vendeu R$ 10." },
  ]);
  assert.equal(loaded.activeId, loaded.conversations[0].id);
  assert.deepEqual(loadChatState(2, storage), emptyChatState());
});

test("título vem da primeira pergunta e é truncado", () => {
  const text = "a".repeat(100);
  const state = appendMessage(emptyChatState(), { role: "user", text }, 1);

  const title = activeConversation(state).title;
  assert.equal(title.length, 60);
  assert.ok(title.endsWith("…"));
});

test("resposta da IA não sobrescreve o título", () => {
  let state = appendMessage(emptyChatState(), { role: "user", text: "Primeira" }, 1);
  state = appendMessage(state, { role: "assistant", text: "Resposta" }, 2);

  assert.equal(activeConversation(state).title, "Primeira");
});

test("guarda no máximo o limite de mensagens por conversa", () => {
  let state = emptyChatState();
  for (let index = 0; index < MAX_MESSAGES_PER_CONVERSATION + 10; index += 1) {
    state = appendMessage(state, { role: "user", text: `msg ${index}` }, index + 1);
  }

  const conversation = activeConversation(state);
  assert.equal(conversation.messages.length, MAX_MESSAGES_PER_CONVERSATION);
  assert.equal(
    conversation.messages.at(-1).text,
    `msg ${MAX_MESSAGES_PER_CONVERSATION + 9}`,
  );
});

test("nova conversa não empilha conversas vazias", () => {
  const first = startConversation(emptyChatState(), 1);
  const again = startConversation(first, 2);

  assert.equal(again.conversations.length, 1);
  assert.equal(again.activeId, first.activeId);
});

test("nova conversa cria outra depois de uma mensagem", () => {
  let state = appendMessage(emptyChatState(), { role: "user", text: "Oi" }, 1);
  state = startConversation(state, 2);

  assert.equal(state.conversations.length, 2);
  assert.equal(activeConversation(state).messages.length, 0);
  assert.equal(state.conversations[0].id, state.activeId);
});

test("a conversa ativa sobe para o topo ao receber mensagem", () => {
  let state = startConversation(emptyChatState(), 1);
  const firstId = state.activeId;
  state = appendMessage(state, { role: "user", text: "Primeira" }, 2);
  state = startConversation(state, 3);
  state = appendMessage(state, { role: "user", text: "Segunda" }, 4);

  assert.equal(state.conversations[0].title, "Segunda");
  assert.equal(state.conversations[1].id, firstId);

  // Volta para a primeira conversa e manda outra mensagem.
  const stored = { ...state, activeId: firstId };
  const updated = appendMessage(stored, { role: "user", text: "Mais" }, 5);

  assert.equal(updated.conversations[0].id, firstId);
});

test("resposta em andamento chega na conversa certa, sem trocar a ativa", () => {
  let state = appendMessage(emptyChatState(), { role: "user", text: "A" }, 1);
  const firstId = state.activeId;
  state = startConversation(state, 2);
  state = appendMessage(state, { role: "user", text: "B" }, 3);
  const secondId = state.activeId;

  const updated = appendMessageTo(
    state,
    firstId,
    { role: "assistant", text: "resposta da A" },
    4,
  );

  assert.equal(updated.activeId, secondId);
  const first = updated.conversations.find((item) => item.id === firstId);
  assert.equal(first.messages.at(-1).text, "resposta da A");
});

test("resposta para conversa apagada é descartada", () => {
  const state = appendMessage(emptyChatState(), { role: "user", text: "A" }, 1);

  const updated = appendMessageTo(
    state,
    "conversa-que-nao-existe",
    { role: "assistant", text: "oi" },
    2,
  );

  assert.equal(updated, state);
});

test("apagar a conversa ativa ativa a mais recente restante", () => {
  let state = appendMessage(emptyChatState(), { role: "user", text: "A" }, 1);
  const firstId = state.activeId;
  state = startConversation(state, 2);
  state = appendMessage(state, { role: "user", text: "B" }, 3);
  const secondId = state.activeId;

  const afterDelete = deleteConversation(state, secondId);
  assert.equal(afterDelete.conversations.length, 1);
  assert.equal(afterDelete.activeId, firstId);

  const empty = deleteConversation(afterDelete, firstId);
  assert.deepEqual(empty, { activeId: null, conversations: [] });
});

test("apagar id inexistente devolve o mesmo estado", () => {
  const state = appendMessage(emptyChatState(), { role: "user", text: "A" }, 1);
  assert.equal(deleteConversation(state, "nao-existe"), state);
});

test("limita o número de conversas guardadas", () => {
  let state = emptyChatState();
  for (let index = 0; index < MAX_CONVERSATIONS + 5; index += 1) {
    state = startConversation(state, index + 1);
    state = appendMessage(state, { role: "user", text: `conversa ${index}` }, index + 1);
  }

  assert.equal(state.conversations.length, MAX_CONVERSATIONS);

  const storage = memoryStorage();
  saveChatState(1, state, storage);
  assert.equal(loadChatState(1, storage).conversations.length, MAX_CONVERSATIONS);
});

test("JSON inválido ou formato estranho não quebra a leitura", () => {
  const storage = memoryStorage();
  storage.setItem(storageKey(1), "{nao e json");
  assert.deepEqual(loadChatState(1, storage), emptyChatState());

  storage.setItem(storageKey(1), JSON.stringify({ conversations: "x" }));
  assert.deepEqual(loadChatState(1, storage), emptyChatState());

  storage.setItem(
    storageKey(1),
    JSON.stringify({ conversations: [{ id: 1, title: null, messages: [] }] }),
  );
  assert.deepEqual(loadChatState(1, storage), emptyChatState());
});

test("armazenamento que quebra (cota cheia) não derruba o chat", () => {
  const broken = {
    getItem: () => {
      throw new Error("bloqueado");
    },
    setItem: () => {
      throw new Error("cota cheia");
    },
  };

  assert.deepEqual(loadChatState(1, broken), emptyChatState());
  assert.equal(saveChatState(1, emptyChatState(), broken), false);
});

test("sem armazenamento disponível o chat funciona em memória", () => {
  const state = appendMessage(emptyChatState(), { role: "user", text: "Oi" }, 1);
  assert.equal(activeConversation(state).title, "Oi");
  assert.deepEqual(loadChatState(1, null), emptyChatState());
  assert.equal(saveChatState(1, state, null), false);
});
