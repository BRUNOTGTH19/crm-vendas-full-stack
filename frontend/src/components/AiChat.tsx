import { useEffect, useRef, useState, type FormEvent } from "react";
import { aiChat, aiStatusMessage, ApiError, copyToClipboard } from "../lib/api.ts";

type Mode = "chat" | "status";

interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  text: string;
}

const SUGGESTIONS = [
  "Quanto vendi neste mês?",
  "Quais cobranças estão atrasadas?",
];

function friendlyError(err: unknown): string {
  if (err instanceof ApiError) {
    // 429 e 503 já chegam com mensagem amigável do backend.
    return err.detail || "Não foi possível falar com o assistente agora.";
  }
  if (err instanceof Error) return err.message;
  return "Não foi possível falar com o assistente agora.";
}

export function AiChat() {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("chat");

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [reason, setReason] = useState("");
  const [clientName, setClientName] = useState("");
  const [order, setOrder] = useState("");
  const [statusBusy, setStatusBusy] = useState(false);
  const [statusError, setStatusError] = useState("");
  const [generated, setGenerated] = useState("");
  const [copied, setCopied] = useState(false);

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
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setError("");
    setBusy(true);
    try {
      const response = await aiChat(text);
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

  async function generateStatus(event: FormEvent) {
    event.preventDefault();
    if (!reason.trim() || statusBusy) return;
    setStatusBusy(true);
    setStatusError("");
    setGenerated("");
    setCopied(false);
    try {
      const response = await aiStatusMessage({
        motivo: reason.trim(),
        cliente: clientName.trim() || null,
        pedido: order.trim() || null,
      });
      setGenerated(response.message);
    } catch (err) {
      setStatusError(friendlyError(err));
    } finally {
      setStatusBusy(false);
    }
  }

  async function copyGenerated() {
    if (!generated) return;
    await copyToClipboard(generated);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
        title="Abrir assistente de IA"
        className="fixed bottom-20 right-4 z-40 inline-flex min-h-11 items-center gap-1.5 rounded-full border border-[#534AB7]/60 bg-[#26215C] px-3 text-xs font-semibold text-[#FAC775] shadow-xl transition-colors hover:bg-[#534AB7] hover:text-white lg:bottom-6 lg:right-6"
      >
        <span aria-hidden>✨</span>
        <span className="hidden min-[380px]:inline">Assistente</span>
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-6">
          <button
            type="button"
            aria-label="Fechar assistente"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-black/70"
          />
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="ai-chat-title"
            className="relative flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-3xl border border-white/10 bg-[#26215C] shadow-2xl sm:max-h-[85dvh] sm:max-w-lg sm:rounded-3xl"
          >
            <header className="flex items-start justify-between gap-3 border-b border-white/10 px-4 py-3">
              <div className="min-w-0">
                <h2 id="ai-chat-title" className="text-base font-semibold text-white">
                  Assistente IA
                </h2>
                <p className="text-[11px] text-zinc-400">
                  Consultas somente leitura · nada é enviado sozinho
                </p>
              </div>
              <button
                ref={closeRef}
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Fechar"
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-lg text-zinc-300 hover:bg-white/10 hover:text-white"
              >
                ✕
              </button>
            </header>

            <div
              role="tablist"
              aria-label="Modo do assistente"
              className="flex gap-1 border-b border-white/10 px-3 py-2"
            >
              <button
                type="button"
                role="tab"
                aria-selected={mode === "chat"}
                onClick={() => {
                  setMode("chat");
                  setError("");
                }}
                className={`min-h-11 flex-1 rounded-full px-3 text-xs font-semibold transition-colors ${
                  mode === "chat"
                    ? "bg-[#534AB7] text-white"
                    : "text-zinc-300 hover:bg-white/5"
                }`}
              >
                Consultar dados
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === "status"}
                onClick={() => {
                  setMode("status");
                  setStatusError("");
                }}
                className={`min-h-11 flex-1 rounded-full px-3 text-xs font-semibold transition-colors ${
                  mode === "status"
                    ? "bg-[#534AB7] text-white"
                    : "text-zinc-300 hover:bg-white/5"
                }`}
              >
                Criar status
              </button>
            </div>

            {mode === "chat" ? (
              <>
                <div
                  aria-live="polite"
                  className="flex-1 space-y-3 overflow-y-auto px-4 py-4"
                >
                  {messages.length === 0 && !busy && (
                    <div className="space-y-3">
                      <p className="text-sm text-zinc-300">
                        Pergunte sobre vendas, atrasos ou status de um pedido. A IA
                        consulta apenas os seus dados.
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {SUGGESTIONS.map((suggestion) => (
                          <button
                            key={suggestion}
                            type="button"
                            onClick={() => setInput(suggestion)}
                            className="min-h-11 rounded-full border border-white/10 bg-white/5 px-3 text-left text-xs text-zinc-200 hover:border-[#534AB7] hover:bg-[#534AB7]/20"
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
                      <p
                        className={`max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3 py-2 text-sm ${
                          message.role === "user"
                            ? "bg-[#534AB7] text-white"
                            : "bg-white/10 text-zinc-100"
                        }`}
                      >
                        {message.text}
                      </p>
                    </div>
                  ))}

                  {busy && (
                    <div className="flex justify-start">
                      <p className="rounded-2xl bg-white/10 px-3 py-2 text-sm text-zinc-300">
                        Consultando…
                      </p>
                    </div>
                  )}

                  {error && (
                    <div
                      role="alert"
                      className="rounded-2xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300"
                    >
                      {error}
                    </div>
                  )}
                  <div ref={endRef} />
                </div>

                <form onSubmit={sendMessage} className="border-t border-white/10 p-3">
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
                      className="min-h-11 flex-1 resize-none rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40 disabled:opacity-60"
                    />
                    <button
                      type="submit"
                      disabled={busy || !input.trim()}
                      className="min-h-11 shrink-0 rounded-full bg-[#534AB7] px-4 text-sm font-semibold text-white hover:bg-[#6a60d4] disabled:opacity-50"
                    >
                      {busy ? "…" : "Enviar"}
                    </button>
                  </div>
                  <p className="mt-1.5 text-[10px] leading-snug text-zinc-500">
                    A IA não altera dados. Confira os valores antes de usar.
                  </p>
                </form>
              </>
            ) : (
              <form
                onSubmit={generateStatus}
                className="flex-1 space-y-3 overflow-y-auto p-4"
              >
                <div>
                  <label
                    htmlFor="ai-status-reason"
                    className="mb-1 block text-sm font-medium text-zinc-200"
                  >
                    Motivo do status *
                  </label>
                  <textarea
                    id="ai-status-reason"
                    required
                    maxLength={200}
                    rows={3}
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    placeholder="Ex.: o pedido 123 atrasou um dia"
                    className="w-full resize-none rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
                  />
                </div>

                <div className="grid grid-cols-1 gap-3 min-[380px]:grid-cols-2">
                  <div>
                    <label
                      htmlFor="ai-status-client"
                      className="mb-1 block text-sm font-medium text-zinc-200"
                    >
                      Cliente (opcional)
                    </label>
                    <input
                      id="ai-status-client"
                      type="text"
                      maxLength={100}
                      value={clientName}
                      onChange={(event) => setClientName(event.target.value)}
                      placeholder="Nome do cliente"
                      className="min-h-11 w-full rounded-full border border-white/10 bg-white/5 px-3 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="ai-status-order"
                      className="mb-1 block text-sm font-medium text-zinc-200"
                    >
                      Pedido (opcional)
                    </label>
                    <input
                      id="ai-status-order"
                      type="text"
                      maxLength={60}
                      value={order}
                      onChange={(event) => setOrder(event.target.value)}
                      placeholder="Ex.: 123"
                      className="min-h-11 w-full rounded-full border border-white/10 bg-white/5 px-3 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={statusBusy || !reason.trim()}
                  className="min-h-11 w-full rounded-full bg-[#534AB7] px-4 text-sm font-semibold text-white hover:bg-[#6a60d4] disabled:opacity-50"
                >
                  {statusBusy ? "Gerando…" : "Gerar frase"}
                </button>

                {statusError && (
                  <div
                    role="alert"
                    className="rounded-2xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300"
                  >
                    {statusError}
                  </div>
                )}

                {generated && (
                  <div className="rounded-2xl border border-[#BA7517]/50 bg-[#BA7517]/15 p-3">
                    <p className="whitespace-pre-wrap break-words text-sm text-[#FAC775]">
                      {generated}
                    </p>
                    <button
                      type="button"
                      onClick={() => void copyGenerated()}
                      className="mt-3 min-h-11 rounded-full border border-[#FAC775]/40 px-3 text-xs font-semibold text-[#FAC775] hover:bg-[#BA7517]/20"
                    >
                      {copied ? "Copiado!" : "Copiar texto"}
                    </button>
                  </div>
                )}

                <p className="text-[10px] leading-snug text-zinc-500">
                  Revise antes de copiar. Nenhuma mensagem é enviada ou gravada
                  automaticamente.
                </p>
              </form>
            )}
          </section>
        </div>
      )}
    </>
  );
}
