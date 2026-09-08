/* Service Worker de la PWA "CRM Vendas" — cache-first para estáticos, network-first para API. */
const CACHE = "crm-vendas-cache-v1";

self.addEventListener("install", () => {
  self.skipWaiting = true;
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients && self.clients.claim ? self.clients.claim() : Promise.resolve());
});

async function openCache() {
  return await caches.open(CACHE);
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" && event.request.method !== "HEAD") return;

  // Llamadas a la API: primero red, respaldo a cache si está offline.
  if (url.origin === self.location.origin && url.pathname.startsWith("/api/")) {
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
        if (cached) return cached;
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