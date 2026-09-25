/* Service Worker: somente arquivos públicos estáticos são armazenados offline. */
// v4: renomeado a cada mudança visível do app — o `activate` apaga os caches
// antigos, senão o celular continuaria servindo um bundle velho (cache-first)
// mesmo depois do deploy.
const CACHE = "crm-vendas-cache-v4";

self.addEventListener("install", () => {
  self.skipWaiting();
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
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      tag: "crm-alerta",
      renotify: true,
      data: { url: data.url || "/#/queue", run_id: data.data?.run_id },
    }).then(() => {
      console.info("push_displayed", { run_id: data.data?.run_id });
    }).catch((error) => {
      console.error("push_display_failed", { run_id: data.data?.run_id, error_type: error.name });
      throw error;
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
          return ("navigate" in client ? client.navigate(target) : Promise.resolve(client))
            .then((navigated) => (navigated || client).focus());
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