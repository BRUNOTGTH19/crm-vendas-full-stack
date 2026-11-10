/**
 * Preferencia de tema do CRM (claro / escuro / sistema).
 *
 * A chave `crm:theme` e lida tambem pelo script anti-flash em `index.html`
 * antes do React montar. Nao usa APIs de autenticacao nem de negocio.
 */

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "crm:theme";

const LIGHT_THEME_COLOR = "#F5F2EA";
const DARK_THEME_COLOR = "#08100C";

function isPreference(value: string | null): value is ThemePreference {
  return value === "light" || value === "dark" || value === "system";
}

/** Le a preferencia salva; o padrao do CRM e o tema claro. */
export function getThemePreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (isPreference(stored)) return stored;
  } catch {
    // Storage bloqueado (modo privado / politica do navegador).
  }
  return "light";
}

export function systemPrefersDark(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference === "system") return systemPrefersDark() ? "dark" : "light";
  return preference;
}

/**
 * Aplica a preferencia no <html>: classe `.dark`, `color-scheme` e a meta
 * `theme-color` (barra do navegador / PWA). Retorna o tema efetivo.
 */
export function applyTheme(preference: ThemePreference): ResolvedTheme {
  const resolved = resolveTheme(preference);
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  root.style.colorScheme = resolved;

  const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (meta) {
    meta.content = resolved === "dark" ? DARK_THEME_COLOR : LIGHT_THEME_COLOR;
  }

  return resolved;
}

export function setThemePreference(preference: ThemePreference): ResolvedTheme {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Sem persistencia: ainda aplica no documento atual.
  }
  return applyTheme(preference);
}
