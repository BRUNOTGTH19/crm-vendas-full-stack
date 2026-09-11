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
      <div className="text-xs text-zinc-400">
        {qTxt} × R$ {pTxt}
      </div>
      <div className="text-xl font-bold text-[#FAC775]">{fmtMoney(total)}</div>
    </div>
  );
}