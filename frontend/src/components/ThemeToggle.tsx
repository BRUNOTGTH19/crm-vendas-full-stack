import { useEffect, useState } from "react";
import {
  applyTheme,
  getThemePreference,
  resolveTheme,
  setThemePreference,
  type ResolvedTheme,
  type ThemePreference,
} from "../lib/theme.ts";
import { IconMonitor, IconMoon, IconSun } from "./icons.tsx";

const OPTIONS: { value: ThemePreference; label: string; Icon: typeof IconSun }[] = [
  { value: "light", label: "Claro", Icon: IconSun },
  { value: "dark", label: "Escuro", Icon: IconMoon },
  { value: "system", label: "Sistema", Icon: IconMonitor },
];

const NEXT: Record<ThemePreference, ThemePreference> = {
  light: "dark",
  dark: "system",
  system: "light",
};

interface ThemeToggleProps {
  /** `icon` (cicla com um toque) ou `full` (tres opcoes). */
  variant?: "icon" | "full";
  className?: string;
}

/** Alterna o tema claro/escuro/sistema e persiste em `crm:theme`. */
export function ThemeToggle({ variant = "icon", className = "" }: ThemeToggleProps) {
  const [preference, setPreference] = useState<ThemePreference>(() => getThemePreference());
  const [, setResolved] = useState<ResolvedTheme>(() => resolveTheme(getThemePreference()));

  // Aplica sempre que a preferencia muda (inclusive quando o valor veio do
  // storage), mantendo `<html class="dark">`, color-scheme e theme-color.
  useEffect(() => {
    setResolved(applyTheme(preference));
  }, [preference]);

  // Em "sistema", acompanha mudancas do SO em tempo real.
  useEffect(() => {
    if (preference !== "system" || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setResolved(applyTheme("system"));
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [preference]);

  function choose(next: ThemePreference) {
    setPreference(next);
    setThemePreference(next);
  }

  if (variant === "full") {
    return (
      <div
        role="group"
        aria-label="Tema da interface"
        className={`flex w-full items-center gap-1 rounded-full border border-ink/10 bg-white/60 p-1 dark:border-white/10 dark:bg-white/5 ${className}`}
      >
        {OPTIONS.map(({ value, label, Icon }) => {
          const active = preference === value;
          return (
            <button
              key={value}
              type="button"
              aria-pressed={active}
              onClick={() => choose(value)}
              className={`inline-flex min-h-9 min-w-0 flex-1 items-center justify-center gap-1 rounded-full px-1.5 py-1.5 text-[11px] font-bold transition ${
                active
                  ? "bg-brand-950 text-white shadow-sm dark:bg-lime dark:text-brand-950"
                  : "text-ink/70 hover:text-ink"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{label}</span>
            </button>
          );
        })}
      </div>
    );
  }

  const current = OPTIONS.find((option) => option.value === preference) ?? OPTIONS[0];
  const CurrentIcon = current.Icon;

  return (
    <button
      type="button"
      onClick={() => choose(NEXT[preference])}
      className={`icon-btn ${className}`}
      aria-label={`Tema atual: ${current.label}. Trocar tema`}
      title={`Tema: ${current.label}`}
    >
      <CurrentIcon className="h-4 w-4" />
    </button>
  );
}
