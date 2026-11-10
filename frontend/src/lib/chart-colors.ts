/**
 * Cores usadas pelo Recharts. Sao referencias a variaveis CSS definidas em
 * `index.css`, portanto acompanham o tema claro/escuro sem duplicar hex no JS.
 */

export const CHART_SERIES = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
] as const;

export const CHART_PAID = "var(--chart-1)";
export const CHART_PENDING = "var(--chart-2)";
export const CHART_AXIS = "var(--chart-axis)";

export const CHART_TOOLTIP_STYLE = {
  background: "var(--chart-tooltip-bg)",
  border: "1px solid var(--chart-tooltip-border)",
  borderRadius: 16,
  color: "var(--chart-tooltip-text)",
  fontSize: 12,
  boxShadow: "0 12px 32px -20px rgba(0, 0, 0, 0.35)",
} as const;
