import type { ReactNode } from "react";
import { IconClose } from "./icons.tsx";

interface ModalProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export function Modal({ title, onClose, children }: ModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-brand-950/40 backdrop-blur-sm dark:bg-black/60 sm:items-center sm:p-6"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="animate-fade-up flex max-h-[92vh] w-full flex-col rounded-t-4xl border border-ink/[0.06] bg-paper shadow-float dark:border-white/10 sm:max-w-lg sm:rounded-4xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-ink/[0.06] px-5 py-4 dark:border-white/10 sm:px-6">
          <h2 className="text-xl font-extrabold tracking-tight text-ink">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="icon-btn -mr-2"
            aria-label="Fechar"
          >
            <IconClose className="h-5 w-5" />
          </button>
        </div>
        <div className="max-h-[70vh] overflow-auto p-5 sm:p-6">{children}</div>
      </div>
    </div>
  );
}
