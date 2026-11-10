import { useState } from "react";
import { IconDownload } from "./icons.tsx";

interface PDFButtonProps {
  /** Função que dispara o download e lança ApiError em caso de falha. */
  onDownload: () => Promise<void>;
  label?: string;
  disabled?: boolean;
}

/** Botão de exportação em PDF (estado "Gerando…" preservado). */
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
      className="btn btn-ghost btn-sm"
    >
      <IconDownload className="h-4 w-4" />
      {busy ? "Gerando…" : label}
    </button>
  );
}
