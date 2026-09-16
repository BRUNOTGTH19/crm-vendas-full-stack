/**
 * Web Push — ativação de notificações de alerta de prazo de vendas.
 *
 * Fluxo:
 * 1. Busca a chave pública VAPID no backend (GET /push/vapid-key).
 * 2. Pede permissão ao usuário e cria a subscrição via PushManager.
 * 3. Envia a subscrição ao backend (POST /push/subscribe), que a persiste.
 *
 * O service worker (/sw.js) exibe a notificação quando o backend envia o push.
 */
import { api, ApiError } from "./api.ts";

const PUSH_ENABLED_KEY = "crm_push_enabled";

export function isPushLocallyEnabled(): boolean {
  return localStorage.getItem(PUSH_ENABLED_KEY) === "1";
}

function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const buffer = new ArrayBuffer(raw.length);
  const output = new Uint8Array(buffer);
  for (let i = 0; i < raw.length; i++) output[i] = raw.charCodeAt(i);
  return output;
}

/** Indica se o navegador/dispositivo suporta Web Push. */
export function pushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

/** Estado atual da permissão/subscrição para exibir o botão correto na UI. */
export async function getPushState(): Promise<
  "unsupported" | "denied" | "subscribed" | "unsubscribed"
> {
  if (!pushSupported()) return "unsupported";
  if (Notification.permission === "denied") return "denied";
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  return sub ? "subscribed" : "unsubscribed";
}

/** Pede permissão, cria a subscrição e registra no backend. */
export async function enablePush(): Promise<void> {
  if (!pushSupported()) {
    throw new Error("Este navegador não suporta notificações push.");
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Permissão de notificação não concedida.");
  }

  const { public_key: vapidKey } = await api.get<{ public_key: string }>("/push/vapid-key");

  const reg = await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidKey),
    });
  }

  const json = sub.toJSON();
  const keys = (json.keys ?? {}) as { p256dh?: string; auth?: string };
  if (!keys.p256dh || !keys.auth) {
    throw new Error("Subscrição inválida (chaves ausentes).");
  }

  await api.post("/push/subscribe", {
    endpoint: json.endpoint,
    p256dh: keys.p256dh,
    auth: keys.auth,
  });
  localStorage.setItem(PUSH_ENABLED_KEY, "1");
}

/** Remove a subscrição do navegador e do backend. */
export async function disablePush(): Promise<void> {
  if (!pushSupported()) return;
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  if (sub) {
    const json = sub.toJSON();
    try {
      await api.post("/push/unsubscribe", { endpoint: json.endpoint });
    } catch (err) {
      // Se a sessão expirou etc., ainda removemos localmente.
      if (!(err instanceof ApiError)) throw err;
    }
    await sub.unsubscribe();
  }
  localStorage.removeItem(PUSH_ENABLED_KEY);
}