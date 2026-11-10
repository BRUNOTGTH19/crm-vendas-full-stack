import { fmtMoney } from "../lib/format.ts";

interface TotalDisplayProps {
  quantity: string | number;
  unitPrice: string | number;
  total: number;
}

/** Exibe quantidade × valor unitário = total em tempo real (doc 3.1). */
export function TotalDisplay({ quantity, unitPrice, total }: TotalDisplayProps) {
  const q = typeof quantity === "string" ? parseFloat(quantity.replace(",", ".")) : quantity;
  const p = typeof unitPrice === "string" ? parseFloat(unitPrice.replace(",", ".")) : unitPrice;
  const qTxt = Number.isFinite(q) ? String(q) : "0";
  const pTxt = Number.isFinite(p) ? p.toFixed(2).replace(".", ",") : "0,00";

  return (
    <div className="text-right">
      <div className="text-xs text-ink/70">
        {qTxt} × R$ {pTxt}
      </div>
      <div className="money text-xl font-extrabold text-brand-700 dark:text-brand-300">
        {fmtMoney(total)}
      </div>
    </div>
  );
}
