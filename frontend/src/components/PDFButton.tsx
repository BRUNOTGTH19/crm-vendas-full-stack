import { useState } from "react";

interface PDFButtonProps {
  /** Função que dispara o download e lança ApiError em caso de falha. */
  onDownload: () => Promise<void>;
  label?: string;
  disabled?: boolean;
}

/** Botão pílula roxo para exportação em PDF (doc 3.1 e 3.4). */
export function PDFButton({ onDownload, label = "PDF", disabled }: PDFButtonProps) {
  const [busy, setBusy] = useState(false);

  return (
    <button
      type="button"
      disabled={busy || disabled}
      onClick={async () => {
        setBusy(true);
        try {
          await onDownload();
        } finally {
          setBusy(false);
        }
      }}
      className="rounded-full bg-[#534AB7] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#6a60d4] disabled:opacity-50"
    >
      {busy ? "Gerando…" : label}
    </button>
  );
}