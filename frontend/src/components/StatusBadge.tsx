import type { SaleStatus } from "../types.ts";

export function StatusBadge({ status }: { status: SaleStatus }) {
  return (
    <span
      className={`chip ring-1 ring-inset ${
        status === "paid"
          ? "bg-brand-50 text-brand-700 ring-brand-700/15 dark:bg-brand-400/15 dark:text-brand-200 dark:ring-brand-300/20"
          : "bg-amber-50 text-amber-700 ring-amber-700/15 dark:bg-amber-400/15 dark:text-amber-200 dark:ring-amber-300/20"
      }`}
    >
      {status === "paid" ? "Paga" : "Pendente"}
    </span>
  );
}
