/**
 * Histórico do assistente de IA salvo no próprio navegador.
 *
 * O backend é stateless (cada `/ai/chat` recebe só as últimas 12 mensagens),
 * então a lista de conversas vive aqui: `localStorage` por usuário, sem custo,
 * sem migration e sem sincronizar entre dispositivos. Ao recarregar a página ou
 * fechar a aba, o chat volta como estava.
 *
 * Regras:
 *
 * - a chave inclui o `user_id`, então trocar de conta no mesmo navegador não
 *   mostra a conversa da conta anterior;
 * - o armazenamento é melhor esforço: JSON inválido, cota cheia ou
 *   `localStorage` indisponível não podem quebrar a tela;
 * - o histórico guardado é limitado (conversas e mensagens) para não crescer
 *   sem controle nem estourar a cota do navegador.
 */

export type ChatRole = "user" | "assistant";

export interface StoredMessage {
  role: ChatRole;
  text: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: StoredMessage[];
  updatedAt: number;
}

export interface ChatState {
  activeId: string | null;
  conversations: Conversation[];
}

/** Subconjunto de `Storage` usado aqui (facilita o teste com memória falsa). */
export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export const MAX_CONVERSATIONS = 20;
export const MAX_MESSAGES_PER_CONVERSATION = 60;
const TITLE_MAX_CHARS = 60;
const STORAGE_PREFIX = "ai_chat:v1:user:";

export function storageKey(userId: number): string {
  return `${STORAGE_PREFIX}${userId}`;
}

export function emptyChatState(): ChatState {
  return { activeId: null, conversations: [] };
}

function defaultStorage(): StorageLike | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    // Navegador com armazenamento bloqueado (modo privado/iframe).
    return null;
  }
}

function makeId(now: number): string {
  const suffix = Math.random().toString(36).slice(2, 8);
  return `${now.toString(36)}-${suffix}`;
}

function isRole(value: unknown): value is ChatRole {
  return value === "user" || value === "assistant";
}

function parseMessage(value: unknown): StoredMessage | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  if (!isRole(item.role) || typeof item.text !== "string" || item.text === "") {
    return null;
  }
  return { role: item.role, text: item.text };
}

function parseConversation(value: unknown): Conversation | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  if (typeof item.id !== "string" || item.id === "") return null;
  if (typeof item.title !== "string") return null;
  if (typeof item.updatedAt !== "number" || !Number.isFinite(item.updatedAt)) {
    return null;
  }
  if (!Array.isArray(item.messages)) return null;
  const messages = item.messages
    .map(parseMessage)
    .filter((message): message is StoredMessage => message !== null)
    .slice(-MAX_MESSAGES_PER_CONVERSATION);
  return {
    id: item.id,
    title: item.title,
    messages,
    updatedAt: item.updatedAt,
  };
}

/** Lê o histórico do usuário. Qualquer problema devolve estado vazio. */
export function loadChatState(
  userId: number,
  storage: StorageLike | null = defaultStorage(),
): ChatState {
  if (!storage || userId <= 0) return emptyChatState();

  let raw: string | null = null;
  try {
    raw = storage.getItem(storageKey(userId));
  } catch {
    return emptyChatState();
  }
  if (!raw) return emptyChatState();

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return emptyChatState();
    const item = parsed as Record<string, unknown>;
    const conversations = Array.isArray(item.conversations)
      ? item.conversations
          .map(parseConversation)
          .filter((conversation): conversation is Conversation => conversation !== null)
          .sort((a, b) => b.updatedAt - a.updatedAt)
          .slice(0, MAX_CONVERSATIONS)
      : [];
    const activeId =
      typeof item.activeId === "string" &&
      conversations.some((conversation) => conversation.id === item.activeId)
        ? item.activeId
        : (conversations[0]?.id ?? null);
    return { activeId, conversations };
  } catch {
    return emptyChatState();
  }
}

/** Grava o histórico. Falha de cota/armazenamento é silenciosa. */
export function saveChatState(
  userId: number,
  state: ChatState,
  storage: StorageLike | null = defaultStorage(),
): boolean {
  if (!storage || userId <= 0) return false;

  const conversations = [...state.conversations]
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, MAX_CONVERSATIONS)
    .map((conversation) => ({
      ...conversation,
      messages: conversation.messages.slice(-MAX_MESSAGES_PER_CONVERSATION),
    }));
  const activeId = conversations.some((item) => item.id === state.activeId)
    ? state.activeId
    : (conversations[0]?.id ?? null);

  try {
    storage.setItem(
      storageKey(userId),
      JSON.stringify({ activeId, conversations } satisfies ChatState),
    );
    return true;
  } catch {
    return false;
  }
}

export function activeConversation(state: ChatState): Conversation | null {
  if (!state.activeId) return null;
  return (
    state.conversations.find((conversation) => conversation.id === state.activeId) ??
    null
  );
}

function titleFrom(text: string): string {
  const single = text.replace(/\s+/g, " ").trim();
  if (single.length <= TITLE_MAX_CHARS) return single;
  return `${single.slice(0, TITLE_MAX_CHARS - 1).trimEnd()}…`;
}

/** Cria uma conversa vazia, deixando-a como ativa. */
export function startConversation(state: ChatState, now = Date.now()): ChatState {
  const current = activeConversation(state);
  // Evita pilha de conversas vazias ao clicar em "Nova conversa" repetido.
  if (current && current.messages.length === 0) return state;

  const conversation: Conversation = {
    id: makeId(now),
    title: "",
    messages: [],
    updatedAt: now,
  };
  return {
    activeId: conversation.id,
    conversations: [conversation, ...state.conversations].slice(0, MAX_CONVERSATIONS),
  };
}

/**
 * Acrescenta uma mensagem à conversa ativa (criando uma se necessário).
 * A conversa sobe para o topo da lista e ganha título na primeira pergunta.
 */
export function appendMessage(
  state: ChatState,
  message: StoredMessage,
  now = Date.now(),
): ChatState {
  const active = activeConversation(state) ?? {
    id: makeId(now),
    title: "",
    messages: [],
    updatedAt: now,
  };

  const messages = [...active.messages, message].slice(
    -MAX_MESSAGES_PER_CONVERSATION,
  );
  const shouldTitle = active.title === "" && message.role === "user";
  const conversation: Conversation = {
    ...active,
    title: shouldTitle ? titleFrom(message.text) : active.title,
    messages,
    updatedAt: now,
  };

  return {
    activeId: conversation.id,
    conversations: [
      conversation,
      ...state.conversations.filter((item) => item.id !== conversation.id),
    ].slice(0, MAX_CONVERSATIONS),
  };
}

/**
 * Acrescenta uma mensagem a uma conversa específica.
 *
 * Usado pela resposta da IA: se o usuário trocou de conversa (ou apagou a
 * original) enquanto a requisição estava em andamento, a resposta vai para a
 * conversa certa — ou é descartada, sem reaparecer em outro histórico.
 */
export function appendMessageTo(
  state: ChatState,
  conversationId: string,
  message: StoredMessage,
  now = Date.now(),
): ChatState {
  const target = state.conversations.find((item) => item.id === conversationId);
  if (!target) return state;

  const messages = [...target.messages, message].slice(
    -MAX_MESSAGES_PER_CONVERSATION,
  );
  const conversation: Conversation = { ...target, messages, updatedAt: now };

  return {
    ...state,
    conversations: [
      conversation,
      ...state.conversations.filter((item) => item.id !== conversationId),
    ].slice(0, MAX_CONVERSATIONS),
  };
}

/** Remove a conversa e ativa a mais recente restante. */
export function deleteConversation(state: ChatState, id: string): ChatState {
  const conversations = state.conversations.filter((item) => item.id !== id);
  if (conversations.length === state.conversations.length) return state;

  const activeId =
    state.activeId === id ? (conversations[0]?.id ?? null) : state.activeId;
  return { activeId, conversations };
}
