import { useEffect, useState } from "react";
import { Modal } from "./Modal.tsx";
import { fmtMoney, fmtDate } from "../lib/format.ts";
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
  const [busyPdf, setBusyPdf] = useState(false);
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
    setBusyPdf(true);
    setError("");
    try {
      await downloadSaleReceipt(sale.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusyPdf(false);
    }
  }

  return (
    <Modal title={`Cobrar — Venda #${sale.id}`} onClose={onClose}>
      <div className="mb-3 grid grid-cols-3 gap-3 text-sm">
        <div>
          <div className="text-xs uppercase text-zinc-400">Cliente</div>
          <div className="truncate font-semibold text-white">{clientName}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-zinc-400">Saldo</div>
          <div className="font-semibold text-[#FAC775]">{fmtMoney(sale.remaining)}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-zinc-400">Vencimento</div>
          <div className="font-semibold text-white">{fmtDate(sale.due_date)}</div>
        </div>
      </div>

      <label className="mb-1 block text-sm font-medium text-zinc-300">
        Mensagem de cobrança <span className="text-zinc-500">(editável)</span>
      </label>
      <textarea
        rows={9}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        disabled={loading}
        className="w-full resize-y rounded-xl border border-white/10 bg-[#1A1A1A] px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40 disabled:opacity-50"
      />

      {!hasPhone && !loading && (
        <p className="mt-2 rounded-xl border border-[#FAC775]/40 bg-[#FAC775]/10 px-3 py-2 text-xs text-[#FAC775]">
          Este cliente ainda não tem WhatsApp cadastrado. Edite o cliente em{" "}
          <span className="font-semibold">Clientes</span> para habilitar o envio
          automático. Você ainda pode copiar a mensagem.
        </p>
      )}

      <p className="mt-2 text-xs text-zinc-400">
        💡 O WhatsApp não permite anexar arquivos por link. Baixe o PDF e anexe-o
        na conversa após abrir o WhatsApp.
      </p>

      {error && (
        <p className="mt-3 rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}

      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <button
          type="button"
          onClick={copy}
          disabled={loading}
          className="rounded-full border border-white/10 px-4 py-2 text-sm text-zinc-200 hover:bg-white/5 disabled:opacity-50"
        >
          {copied ? "Copiado ✓" : "Copiar"}
        </button>
        <button
          type="button"
          onClick={downloadPdf}
          disabled={busyPdf}
          className="rounded-full bg-[#534AB7] px-4 py-2 text-sm font-semibold text-white hover:bg-[#6a60d4] disabled:opacity-50"
        >
          {busyPdf ? "Gerando…" : "Baixar PDF"}
        </button>
        <button
          type="button"
          onClick={openWhatsapp}
          disabled={!hasPhone || loading}
          title={hasPhone ? "Abrir WhatsApp com a mensagem pronta" : "Cliente sem WhatsApp"}
          className="rounded-full bg-emerald-500/90 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-40"
        >
          Abrir WhatsApp
        </button>
      </div>
    </Modal>
  );
}