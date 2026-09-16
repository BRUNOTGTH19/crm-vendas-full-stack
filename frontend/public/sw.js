/* Service Worker de la PWA "CRM Vendas" — cache-first para estáticos, network-first para API. */
const CACHE = "crm-vendas-cache-v2";

self.addEventListener("install", () => {
  self.skipWaiting = true;
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients && self.clients.claim ? self.clients.claim() : Promise.resolve())
  );
});

// --- Web Push: alerta de prazo de vendas ---
// O backend envia { title, body, url } assinado com VAPID; aqui exibimos a notificação.
self.addEventListener("push", (event) => {
  let data = { title: "🔔 CRM Vendas", body: "Você tem cobranças para conferir.", url: "/#/queue" };
  try {
    if (event.data) {
      const parsed = event.data.json();
      data = { ...data, ...parsed };
    }
  } catch (e) {
    if (event.data) data.body = event.data.text();
  }

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/icon.svg",
      badge: "/icon.svg",
      tag: "crm-alerta",
      renotify: true,
      data: { url: data.url || "/#/queue" },
    })
  );
});

// Clique na notificação: abre/foca o app na tela indicada (ex.: Cobranças).
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/#/queue";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) {
          client.focus();
          if ("navigate" in client) client.navigate(target);
          return;
        }
      }
      return self.clients.openWindow(target);
    })
  );
});

async function openCache() {
  return await caches.open(CACHE);
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" && event.request.method !== "HEAD") return;

  // Identificar llamadas a la API (tanto relativas como al dominio del backend en Render)
  const isApi = url.pathname.startsWith("/api/") || url.origin.includes("onrender.com") || url.origin.includes("localhost:8000");

  if (isApi) {
    // API: Network First (priorizar datos frescos, respaldo a cache si offline)
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          openCache()
            .then((c) => c.put(event.request, copy))
            .catch(() => {});
          return res;
        })
        .catch(() =>
          openCache()
            .then((c) => c.match(event.request))
            .then((cached) => cached || Response.error())
        )
    );
    return;
  }

  // Estáticos: cache-first, con actualización en segundo plano.
  event.respondWith(
    openCache()
      .then((c) => c.match(event.request))
      .then((cached) => {
        if (cached) {
          // Actualiza el cache en segundo plano
          fetch(event.request).then((net) => {
            const copy = net.clone();
            openCache().then((c) => c.put(event.request, copy)).catch(() => {});
          }).catch(() => {});
          return cached;
        }
        return fetch(event.request).then((net) => {
          const copy = net.clone();
          openCache()
            .then((c) => c.put(event.request, copy))
            .catch(() => {});
          return net;
        });
      })
      .catch(() => fetch(event.request))
  );
});