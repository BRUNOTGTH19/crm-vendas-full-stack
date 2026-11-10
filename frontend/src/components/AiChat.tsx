import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { aiChat, ApiError } from "../lib/api.ts";
import { parseRichText, type Block, type Inline } from "../lib/rich-text.ts";
import { IconClose, IconSparkles } from "./icons.tsx";

interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  text: string;
}

const SUGGESTIONS = [
  "Quanto vendi neste mês?",
  "Quais cobranças estão atrasadas?",
  "Quais são meus melhores clientes?",
  "Quais produtos mais vendem?",
  "Qual é a cotação do dólar hoje?",
];

const MAX_HISTORY = 12;

function friendlyError(err: unknown): string {
  if (err instanceof ApiError) {
    // 429 e 503 já chegam com mensagem amigável do backend.
    return err.detail || "Não foi possível falar com o assistente agora.";
  }
  if (err instanceof Error) return err.message;
  return "Não foi possível falar com o assistente agora.";
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

export function AiChat() {
  const [open, setOpen] = useState(false);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const nextId = useRef(1);
  const endRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    closeRef.current?.focus();
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, busy, open]);

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();
    const text = input.trim();
    if (!text || busy) return;

    const userMessage: ChatMessage = { id: nextId.current++, role: "user", text };
    const history = messages
      .slice(-MAX_HISTORY)
      .map((item) => ({ role: item.role, content: item.text }));
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setError("");
    setBusy(true);
    try {
      const response = await aiChat(text, history);
      setMessages((current) => [
        ...current,
        { id: nextId.current++, role: "assistant", text: response.reply },
      ]);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  function startNewConversation() {
    if (busy) return;
    setMessages([]);
    setInput("");
    setError("");
    nextId.current = 1;
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
        title="Abrir assistente de IA"
        className="fixed bottom-20 right-4 z-40 inline-flex min-h-11 items-center gap-2 rounded-full bg-brand-950 px-4 text-xs font-bold text-lime shadow-float transition hover:bg-brand-900 dark:bg-lime dark:text-brand-950 dark:hover:bg-lime-hover lg:bottom-6 lg:right-6"
      >
        <IconSparkles className="h-4 w-4" />
        <span className="hidden min-[380px]:inline">Assistente</span>
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-6">
          <button
            type="button"
            aria-label="Fechar assistente"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-brand-950/40 backdrop-blur-sm dark:bg-black/70"
          />
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="ai-chat-title"
            className="animate-fade-up relative flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-4xl border border-ink/[0.06] bg-paper shadow-float dark:border-white/10 sm:max-h-[85dvh] sm:max-w-lg sm:rounded-4xl"
          >
            <header className="flex items-start justify-between gap-3 border-b border-ink/[0.06] px-4 py-3 dark:border-white/10">
              <div className="min-w-0">
                <h2 id="ai-chat-title" className="text-base font-extrabold text-ink">
                  Assistente IA
                </h2>
                <p className="text-[11px] text-ink/70">
                  Dados do CRM + web · somente leitura
                </p>
                {messages.length > 0 && (
                  <button
                    type="button"
                    onClick={startNewConversation}
                    disabled={busy}
                    className="mt-1 text-[11px] font-bold text-brand-700 underline-offset-2 hover:underline disabled:opacity-60 dark:text-brand-300"
                  >
                    Nova conversa
                  </button>
                )}
              </div>
              <button
                ref={closeRef}
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Fechar"
                className="icon-btn"
              >
                <IconClose className="h-4 w-4" />
              </button>
            </header>

            <div aria-live="polite" className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
              {messages.length === 0 && !busy && (
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

              {messages.map((message) => (
                <div
                  key={message.id}
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

              {busy && (
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
            </div>

            <form onSubmit={sendMessage} className="border-t border-ink/[0.06] p-3 dark:border-white/10">
              <div className="flex items-end gap-2">
                <textarea
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
              </p>
            </form>
          </section>
        </div>
      )}
    </>
  );
}
