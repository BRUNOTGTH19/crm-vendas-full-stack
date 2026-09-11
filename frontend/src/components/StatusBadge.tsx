import type { SaleStatus } from "../types.ts";

export function StatusBadge({ status }: { status: SaleStatus }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
        status === "paid"
          ? "bg-[#2E5E3A]/40 text-[#7FE0A0] ring-1 ring-[#2E5E3A]"
          : "bg-[#BA7517]/30 text-[#FAC775] ring-1 ring-[#BA7517]/60"
      }`}
    >
      {status === "paid" ? "Paga" : "Pendente"}
    </span>
  );
}