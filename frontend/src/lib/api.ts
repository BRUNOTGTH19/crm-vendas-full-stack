import type { CollectionMessage, CollectionReminder, TokenResponse, User } from "../types.ts";

/**
 * URL base de la API. En desarrollo, Vite hace proxy de `/api` hacia
 * `http://127.0.0.1:8000` (ver vite.config.ts). Para producción, definir
 * VITE_API_URL con la URL completa del backend.
 */
const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";

const TOKEN_KEY = "crm_token";
const USER_KEY = "crm_user";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getSessionUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function setSession(token: TokenResponse): void {
  localStorage.setItem(TOKEN_KEY, token.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(token.user));
  window.dispatchEvent(new Event("crm_auth_changed"));
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.dispatchEvent(new Event("crm_auth_changed"));
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

function detailFrom(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = data.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d
        .map((x) => (x && typeof x === "object" && "msg" in x ? String(x.msg) : String(x)))
        .join(" · ");
    }
  }
  return fallback;
}

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 
    "Content-Type": "application/json",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(API_BASE + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(
      0,
      "No se pudo conectar con el servidor. Verificá que el backend esté corriendo en el puerto 8000."
    );
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/auth/login") && !path.startsWith("/auth/register")) {
      clearSession();
      window.dispatchEvent(
        new CustomEvent("crm_session_revoked", {
          detail: detailFrom(data, "Sessão expirada ou revogada. Faça login novamente."),
        })
      );
    }
    throw new ApiError(res.status, detailFrom(data, `Error ${res.status}`));
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string) => request<T>("PATCH", path),
  del: (path: string) => request<void>("DELETE", path),
};

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/** Baixa qualquer endpoint de relatório PDF (doc 2.5) e dispara o download. */
export async function downloadReportPdf(path: string, filename: string): Promise<void> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(API_BASE + path, { headers });
  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try {
      const data = await res.json();
      detail = detailFrom(data, detail);
    } catch {
      /* mantém mensagem padrão */
    }
    throw new ApiError(res.status, detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * Genera el recibo PDF de una venta a través de la cola del backend
 * y dispara la descarga en el navegador.
 */
export async function downloadSaleReceipt(saleId: number): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res = await fetch(API_BASE + `/queue/pdf/${saleId}`, { method: "POST", headers });
  let body = await res.json();
  if (!res.ok) throw new ApiError(res.status, detailFrom(body, "No se pudo encolar el PDF"));
  const jobId = body.job_id as string;

  for (let i = 0; i < 24; i++) {
    await sleep(500);
    res = await fetch(API_BASE + `/queue/pdf/${jobId}`, { headers });
    body = await res.json();
    if (!res.ok) throw new ApiError(res.status, detailFrom(body, "Error consultando el job"));
    if (body.status === "error") throw new ApiError(500, body.error ?? "Error generando el PDF");
    if (body.status === "done") break;
  }

  res = await fetch(API_BASE + `/queue/pdf/${jobId}/download`, { headers });
  if (!res.ok) throw new ApiError(res.status, "No se pudo descargar el PDF");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `recibo_venda_${saleId}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Lembretes de cobrança (vencidas ou que vencem hoje), integrados ao alerta. */
export function getCollectionReminders(): Promise<CollectionReminder[]> {
  return api.get<CollectionReminder[]>("/collections/reminders");
}

/** Mensagem de cobrança personalizada + link wa.me de uma venda. */
export function getCollectionMessage(saleId: number): Promise<CollectionMessage> {
  return api.get<CollectionMessage>(`/collections/message/${saleId}`);
}

/**
 * Abre o WhatsApp (app ou Web) com a mensagem de cobrança já preenchida.
 * 100% grátis via deep-link oficial wa.me — o usuário confirma o envio.
 */
export function openWhatsappLink(waLink: string): void {
  window.open(waLink, "_blank", "noopener,noreferrer");
}

/** Copia o texto para a área de transferência (com fallback). */
export async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const el = document.createElement("textarea");
    el.value = text;
    document.body.appendChild(el);
    el.select();
    document.execCommand("copy");
    el.remove();
  }
}

// ---------------------------------------------------------------------------
// Admin — gestão de dados (reset/export/import)
// ---------------------------------------------------------------------------

export interface AdminResetResult {
  cleared: Record<string, number>;
  preserved: string[];
}

export interface AdminImportResult {
  mode: "skip" | "overwrite";
  inserted: Record<string, number>;
  skipped: Record<string, number>;
  updated: Record<string, number>;
}

/** Zera as tabelas de dados (exige confirm=true). Preserva os usuários. */
export function adminResetDatabase(): Promise<AdminResetResult> {
  return api.post<AdminResetResult>("/admin/database/reset", { confirm: true });
}

/** Baixa o JSON consolidado de todos os dados (download no navegador). */
export async function adminExportDatabase(): Promise<void> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(API_BASE + "/admin/database/export", { headers });
  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try {
      detail = detailFrom(await res.json(), detail);
    } catch {
      /* mantém mensagem padrão */
    }
    throw new ApiError(res.status, detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "crm_vendas_export.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Importa um arquivo JSON exportado. mode: "skip" (padrão) ou "overwrite". */
export async function adminImportDatabase(
  file: File,
  mode: "skip" | "overwrite" = "skip"
): Promise<AdminImportResult> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const form = new FormData();
  form.append("file", file);

  const res = await fetch(
    API_BASE + `/admin/database/import?mode=${encodeURIComponent(mode)}`,
    { method: "POST", headers, body: form }
  );
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (!res.ok) throw new ApiError(res.status, detailFrom(data, `Erro ${res.status}`));
  return data as AdminImportResult;
}
