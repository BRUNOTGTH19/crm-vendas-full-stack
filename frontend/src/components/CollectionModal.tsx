import { useEffect, useState } from "react";
import { Modal } from "./Modal.tsx";
import { fmtMoney, fmtDate } from "../lib/format.ts";
import { IconAlert, IconCheck } from "./icons.tsx";
import {
  ApiError,
  copyToClipboard,
  downloadSaleReceipt,
  getCollectionMessage,
  openWhatsappLink,
} from "../lib/api.ts";
import type { Sale } from "../types.ts";

interface CollectionModalProps {
  sale: Sale;
  clientName: string;
  onClose: () => void;
}

/**
 * Central de cobrança de uma venda.
 *
 * Monta a mensagem personalizada (via backend), permite editá-la, copiar,
 * baixar o recibo em PDF e abrir o WhatsApp com tudo preenchido (wa.me, grátis).
 */
export function CollectionModal({ sale, clientName, onClose }: CollectionModalProps) {
  const [message, setMessage] = useState("");
  const [waBase, setWaBase] = useState<string | null>(null);
  const [hasPhone, setHasPhone] = useState(false);
  const [loading, setLoading] = useState(true);
  const [pdfState, setPdfState] = useState<"idle" | "working" | "done" | "error">("idle");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    getCollectionMessage(sale.id)
      .then((data) => {
        if (!alive) return;
        setMessage(data.message);
        setHasPhone(data.has_phone);
        // Guarda o link base para reconstruir com a mensagem editada.
        setWaBase(
          data.whatsapp_digits ? `https://wa.me/${data.whatsapp_digits}?text=` : null
        );
      })
      .catch((err) => {
        if (!alive) return;
        setError(err instanceof ApiError ? err.detail : String(err));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    // Baixa o PDF do recibo automaticamente ao abrir a cobrança, para o
    // usuário anexar na conversa do WhatsApp. O botão manual continua
    // disponível como alternativa/repetição.
    setPdfState("working");
    downloadSaleReceipt(sale.id).then(
      () => {
        if (alive) setPdfState("done");
      },
      (err) => {
        if (!alive) return;
        setPdfState("error");
        setError(err instanceof ApiError ? err.detail : String(err));
      }
    );

    return () => {
      alive = false;
    };
  }, [sale.id]);

  function openWhatsapp() {
    if (!waBase) return;
    openWhatsappLink(waBase + encodeURIComponent(message));
  }

  async function copy() {
    await copyToClipboard(message);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function downloadPdf() {
    if (pdfState === "working") return;
    setPdfState("working");
    setError("");
    try {
      await downloadSaleReceipt(sale.id);
      setPdfState("done");
    } catch (err) {
      setPdfState("error");
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  return (
    <Modal title={`Cobrar — Venda #${sale.id}`} onClose={onClose}>
      <div className="mb-3 grid grid-cols-3 gap-2 text-sm">
        <div className="rounded-2xl bg-ink/[0.04] p-3 dark:bg-white/5">
          <div className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-ink/70">
            Cliente
          </div>
          <div className="mt-0.5 truncate font-bold text-ink">{clientName}</div>
        </div>
        <div className="rounded-2xl bg-amber-50 p-3 dark:bg-amber-400/15">
          <div className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-amber-700 dark:text-amber-200">
            Saldo
          </div>
          <div className="money mt-0.5 font-bold text-amber-700 dark:text-amber-200">
            {fmtMoney(sale.remaining)}
          </div>
        </div>
        <div className="rounded-2xl bg-ink/[0.04] p-3 dark:bg-white/5">
          <div className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-ink/70">
            Vencimento
          </div>
          <div className="mt-0.5 font-bold text-ink">{fmtDate(sale.due_date)}</div>
        </div>
      </div>

      <label className="label" htmlFor="collection-message">
        Mensagem de cobrança
      </label>
      <textarea
        id="collection-message"
        rows={9}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        disabled={loading}
        className="field resize-y leading-relaxed"
      />

      {!hasPhone && !loading && (
        <p className="mt-2 flex items-start gap-2 rounded-xl border border-amber-700/20 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-300/20 dark:bg-amber-400/15 dark:text-amber-200">
          <IconAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Este cliente ainda não tem WhatsApp cadastrado. Edite o cliente em{" "}
            <span className="font-bold">Clientes</span> para habilitar o envio automático.
            Você ainda pode copiar a mensagem.
          </span>
        </p>
      )}

      <p className="hint mt-2">
        O WhatsApp não permite anexar arquivos por link. O PDF do recibo é baixado
        automaticamente — anexe-o na conversa após abrir o WhatsApp.
      </p>

      {pdfState === "working" && (
        <p className="mt-2 text-xs text-ink/70">Gerando o PDF do recibo…</p>
      )}
      {pdfState === "done" && (
        <p className="mt-2 flex items-center gap-1.5 text-xs font-semibold text-brand-700 dark:text-brand-300">
          <IconCheck className="h-3.5 w-3.5" />
          PDF baixado! Anexe-o na conversa do WhatsApp.
        </p>
      )}

      {error && (
        <p
          role="alert"
          className="mt-3 rounded-xl border border-rose-700/20 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 dark:border-rose-300/20 dark:bg-rose-400/15 dark:text-rose-200"
        >
          {error}
        </p>
      )}

      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <button type="button" onClick={copy} disabled={loading} className="btn btn-ghost">
          {copied ? "Copiado ✓" : "Copiar"}
        </button>
        <button
          type="button"
          onClick={downloadPdf}
          disabled={pdfState === "working"}
          className="btn btn-primary"
        >
          {pdfState === "working"
            ? "Gerando…"
            : pdfState === "done"
              ? "Baixar novamente"
              : "Baixar PDF"}
        </button>
        <button
          type="button"
          onClick={openWhatsapp}
          disabled={!hasPhone || loading}
          title={hasPhone ? "Abrir WhatsApp com a mensagem pronta" : "Cliente sem WhatsApp"}
          className="btn btn-lime"
        >
          Abrir WhatsApp
        </button>
      </div>
    </Modal>
  );
}
