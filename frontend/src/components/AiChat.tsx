import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { aiChat, ApiError, getSessionUser } from "../lib/api.ts";
import {
  activeConversation,
  appendMessage,
  appendMessageTo,
  deleteConversation,
  loadChatState,
  saveChatState,
  startConversation,
  type ChatState,
} from "../lib/ai-chat-store.ts";
import { parseRichText, type Block, type Inline } from "../lib/rich-text.ts";
import { IconClose, IconPlus, IconSparkles, IconTrash } from "./icons.tsx";

const SUGGESTIONS = [
  "Quanto vendi neste mês?",
  "Quais cobranças estão atrasadas?",
  "Quais são meus melhores clientes?",
  "Quais produtos mais vendem?",
  "Qual é a cotação do dólar hoje?",
];

/** Quantas mensagens o backend aceita por requisição (ver `schemas/ai.py`). */
const MAX_HISTORY = 12;

function friendlyError(err: unknown): string {
  if (err instanceof ApiError) {
    // 429 e 503 já chegam com mensagem amigável do backend.
    return err.detail || "Não foi possível falar com o assistente agora.";
  }
  if (err instanceof Error) return err.message;
  return "Não foi possível falar com o assistente agora.";
}

/** Horário de hoje ou data curta para itens antigos da lista. */
function formatWhen(timestamp: number): string {
  const date = new Date(timestamp);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  return date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

const ERROR_BOX =
  "rounded-2xl border border-rose-700/20 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 dark:border-rose-300/20 dark:bg-rose-400/15 dark:text-rose-200";

/** Renderiza o Markdown básico devolvido pela IA sem usar HTML cru. */
function renderSpans(spans: Inline[]): ReactNode[] {
  return spans.map((span, index) => {
    switch (span.kind) {
      case "bold":
        return (
          <strong key={index} className="font-extrabold">
            {span.text}
          </strong>
        );
      case "italic":
        return <em key={index}>{span.text}</em>;
      case "code":
        return (
          <code
            key={index}
            className="rounded bg-ink/10 px-1 py-0.5 font-mono text-[0.95em] dark:bg-white/15"
          >
            {span.text}
          </code>
        );
      case "link":
        return (
          <a
            key={index}
            href={span.href}
            target="_blank"
            rel="noreferrer noopener"
            className="font-semibold underline underline-offset-2"
          >
            {span.text}
          </a>
        );
      default:
        return <span key={index}>{span.text}</span>;
    }
  });
}

function RichText({ text }: { text: string }) {
  const blocks: Block[] = parseRichText(text);
  return (
    <div className="space-y-1.5">
      {blocks.map((block, index) => {
        if (block.kind === "list") {
          const Tag = block.ordered ? "ol" : "ul";
          return (
            <Tag
              key={index}
              className={`space-y-0.5 pl-5 ${block.ordered ? "list-decimal" : "list-disc"}`}
            >
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderSpans(item)}</li>
              ))}
            </Tag>
          );
        }
        if (block.kind === "code") {
          return (
            <pre
              key={index}
              className="overflow-x-auto rounded-xl bg-ink/10 p-2 text-[11px] dark:bg-black/30"
            >
              <code>{block.text}</code>
            </pre>
          );
        }
        return (
          <p
            key={index}
            className={`whitespace-pre-wrap break-words ${
              block.kind === "heading" ? "font-extrabold" : ""
            }`}
          >
            {renderSpans(block.spans)}
          </p>
        );
      })}
    </div>
  );
}

/**
 * Assistente de IA em painel fixo.
 *
 * O painel não bloqueia a aplicação (não usa backdrop nem trava o scroll),
 * então dá para continuar usando o CRM com ele aberto. O histórico é salvo
 * no `localStorage` por usuário (`lib/ai-chat-store.ts`) e sobrevive a recarregar
 * a página; o backend continua stateless e recebe apenas as últimas 12
 * mensagens.
 */
export function AiChat() {
  const userId = getSessionUser()?.id ?? 0;

  const [open, setOpen] = useState(false);
  const [showList, setShowList] = useState(false);
  const [state, setState] = useState<ChatState>(() => loadChatState(userId));
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const endRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const active = activeConversation(state);
  const messages = active?.messages ?? [];
  // Spinner só na conversa que fez o pedido (o usuário pode ter trocado).
  const waiting = busy && pendingId === active?.id;

  // Persistência: qualquer mudança de conversa é gravada (best-effort).
  useEffect(() => {
    if (userId > 0) saveChatState(userId, state);
  }, [state, userId]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    inputRef.current?.focus();
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  useEffect(() => {
    if (!open || showList) return;
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages.length, waiting, open, showList]);

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();
    const text = input.trim();
    if (!text || busy) return;

    // O backend só conhece o que vai no corpo: mantém a janela de 12 mensagens.
    const history = messages
      .slice(-MAX_HISTORY)
      .map((item) => ({ role: item.role, content: item.text }));

    // Garante uma conversa e fixa o id: a resposta vai para ela mesmo se o
    // usuário trocar de conversa enquanto a requisição está em andamento.
    const base = activeConversation(state)
      ? state
      : startConversation(state, Date.now());
    const conversationId = activeConversation(base)?.id;
    if (!conversationId) return;

    setState(appendMessage(base, { role: "user", text }));
    setInput("");
    setError("");
    setBusy(true);
    setPendingId(conversationId);
    try {
      const response = await aiChat(text, history);
      setState((current) =>
        appendMessageTo(current, conversationId, {
          role: "assistant",
          text: response.reply,
        })
      );
    } catch (err) {
      // A pergunta fica registrada mesmo se a resposta falhar.
      setError(friendlyError(err));
    } finally {
      setBusy(false);
      setPendingId(null);
    }
  }

  function startNewConversation() {
    if (busy) return;
    setState((current) => startConversation(current));
    setInput("");
    setError("");
    setShowList(false);
  }

  function removeConversation(id: string) {
    if (busy) return;
    if (!window.confirm("Apagar esta conversa do histórico deste dispositivo?")) {
      return;
    }
    setState((current) => deleteConversation(current, id));
  }

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-controls="ai-chat-panel"
          title="Abrir assistente de IA"
          className="fixed bottom-20 right-4 z-40 inline-flex min-h-11 items-center gap-2 rounded-full bg-brand-950 px-4 text-xs font-bold text-lime shadow-float transition hover:bg-brand-900 dark:bg-lime dark:text-brand-950 dark:hover:bg-lime-hover lg:bottom-6 lg:right-6"
        >
          <IconSparkles className="h-4 w-4" />
          <span className="hidden min-[380px]:inline">Assistente</span>
        </button>
      )}

      {open && (
        <section
          id="ai-chat-panel"
          role="dialog"
          aria-modal="false"
          aria-labelledby="ai-chat-title"
          className="animate-fade-up fixed inset-x-0 bottom-0 z-50 flex max-h-[85dvh] flex-col overflow-hidden rounded-t-4xl border border-ink/[0.06] bg-paper pb-[env(safe-area-inset-bottom)] shadow-float dark:border-white/10 sm:inset-x-auto sm:bottom-4 sm:right-4 sm:max-h-[min(40rem,85dvh)] sm:w-[26rem] sm:rounded-4xl sm:pb-0 lg:bottom-6 lg:right-6"
        >
          <header className="flex items-start justify-between gap-2 border-b border-ink/[0.06] px-4 py-3 dark:border-white/10">
            <div className="min-w-0">
              <h2 id="ai-chat-title" className="text-base font-extrabold text-ink">
                Assistente IA
              </h2>
              <p className="text-[11px] text-ink/70">
                Dados do CRM + web · somente leitura
              </p>
              <p className="text-[11px] text-ink/60">
                Histórico salvo neste dispositivo
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <button
                type="button"
                onClick={() => setShowList((current) => !current)}
                aria-pressed={showList}
                className={`min-h-9 rounded-full px-2 text-[11px] font-bold transition ${
                  showList
                    ? "bg-brand-950 text-lime dark:bg-lime dark:text-brand-950"
                    : "text-ink/70 hover:bg-ink/5 dark:hover:bg-white/10"
                }`}
              >
                Conversas
              </button>
              <button
                type="button"
                onClick={startNewConversation}
                disabled={busy}
                aria-label="Nova conversa"
                title="Nova conversa"
                className="icon-btn disabled:opacity-60"
              >
                <IconPlus className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Fechar"
                title="Fechar"
                className="icon-btn"
              >
                <IconClose className="h-4 w-4" />
              </button>
            </div>
          </header>

          <div aria-live="polite" className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {showList ? (
              <div className="space-y-2">
                {state.conversations.length === 0 ? (
                  <p className="text-sm leading-relaxed text-ink/70">
                    Nenhuma conversa salva ainda. Faça uma pergunta para começar.
                  </p>
                ) : (
                  state.conversations.map((conversation) => (
                    <div key={conversation.id} className="flex items-stretch gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setState((current) => ({
                            ...current,
                            activeId: conversation.id,
                          }));
                          setShowList(false);
                        }}
                        aria-current={
                          conversation.id === state.activeId ? "true" : undefined
                        }
                        className={`min-w-0 flex-1 rounded-2xl border px-3 py-2 text-left transition ${
                          conversation.id === state.activeId
                            ? "border-brand-500 bg-brand-50 dark:border-brand-300/40 dark:bg-brand-400/10"
                            : "border-ink/10 bg-white/60 hover:border-brand-500 dark:border-white/10 dark:bg-white/5"
                        }`}
                      >
                        <span className="block truncate text-sm font-semibold text-ink">
                          {conversation.title || "Nova conversa"}
                        </span>
                        <span className="block text-[11px] text-ink/60">
                          {conversation.messages.length} mensagem
                          {conversation.messages.length === 1 ? "" : "s"} ·{" "}
                          {formatWhen(conversation.updatedAt)}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => removeConversation(conversation.id)}
                        disabled={busy}
                        aria-label={`Apagar conversa ${
                          conversation.title || "sem título"
                        }`}
                        title="Apagar conversa"
                        className="icon-btn shrink-0 disabled:opacity-60"
                      >
                        <IconTrash className="h-4 w-4" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            ) : (
              <>
                {messages.length === 0 && !waiting && (
                  <div className="space-y-3">
                    <p className="text-sm leading-relaxed text-ink/70">
                      Pergunte sobre clientes, vendas, cobranças, pagamentos,
                      produtos ou relatórios. Também pode pedir uma pesquisa na
                      web. A IA consulta os dados no seu escopo e não altera
                      nada.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {SUGGESTIONS.map((suggestion) => (
                        <button
                          key={suggestion}
                          type="button"
                          onClick={() => setInput(suggestion)}
                          className="min-h-11 rounded-full border border-ink/10 bg-white/60 px-3 text-left text-xs font-semibold text-ink/70 transition hover:border-brand-500 hover:bg-brand-50 dark:border-white/10 dark:bg-white/5 dark:hover:border-brand-300/40 dark:hover:bg-brand-400/10"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {messages.map((message, index) => (
                  <div
                    key={index}
                    className={`flex ${
                      message.role === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div
                      className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                        message.role === "user"
                          ? "bg-brand-950 text-white dark:bg-brand-100 dark:text-brand-950"
                          : "bg-ink/5 text-ink dark:bg-white/10"
                      }`}
                    >
                      <RichText text={message.text} />
                    </div>
                  </div>
                ))}

                {waiting && (
                  <div className="flex justify-start">
                    <p className="rounded-2xl bg-ink/5 px-3 py-2 text-sm text-ink/70 dark:bg-white/10">
                      Consultando dados e web…
                    </p>
                  </div>
                )}

                {error && (
                  <div role="alert" className={ERROR_BOX}>
                    {error}
                  </div>
                )}
                <div ref={endRef} />
              </>
            )}
          </div>

          {!showList && (
            <form
              onSubmit={sendMessage}
              className="border-t border-ink/[0.06] p-3 dark:border-white/10"
            >
              <div className="flex items-end gap-2">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void sendMessage();
                    }
                  }}
                  maxLength={1000}
                  rows={2}
                  disabled={busy}
                  aria-label="Mensagem para o assistente"
                  placeholder="Ex.: quanto vendi em outubro?"
                  className="field min-h-11 flex-1 resize-none disabled:opacity-60"
                />
                <button
                  type="submit"
                  disabled={busy || !input.trim()}
                  className="btn btn-primary btn-sm shrink-0"
                >
                  {busy ? "…" : "Enviar"}
                </button>
              </div>
              <p className="mt-1.5 text-[10px] leading-snug text-ink/70">
                A IA não altera dados. Confira valores e fontes antes de usar.
                Enter envia; Shift+Enter quebra a linha.
              </p>
            </form>
          )}
        </section>
      )}
    </>
  );
}
