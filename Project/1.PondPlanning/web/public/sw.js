// Offline-first service worker (P5 task 7; exercised by the P6 chaos test).
//
// Strategy:
//   * tiles, fonts, built assets  -> cache-first (they never change for a given URL)
//   * GET /api/...                -> network-first, fall back to the last cached copy
//     and mark it with the `X-From-Cache` header so the app can show a staleness badge
//   * everything else             -> network
const VERSION = "pond-sw-v3";
const TILE_HOSTS = ["server.arcgisonline.com", "demotiles.maplibre.org"];

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});
self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

async function cacheFirst(request) {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(request);
  if (hit) return hit;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

async function staleCopy(cache, request) {
  const hit = await cache.match(request);
  if (!hit) return null;
  const headers = new Headers(hit.headers);
  headers.set("X-From-Cache", "true");
  const body = await hit.blob();
  return new Response(body, { status: hit.status, statusText: hit.statusText, headers });
}

async function networkFirst(request) {
  const cache = await caches.open(VERSION);
  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
      return response;
    }
    // A 5xx from the reverse proxy (502 when the API container is down) is
    // "backend unavailable" just as much as a network error is.
    if (response.status >= 500) {
      const stale = await staleCopy(cache, request);
      if (stale) return stale;
    }
    return response;
  } catch (error) {
    const stale = await staleCopy(cache, request);
    if (!stale) throw error;
    return stale;
  }
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  const isTile = TILE_HOSTS.includes(url.host) || url.pathname.startsWith("/tiles/");
  const isAsset = url.origin === self.location.origin && url.pathname.startsWith("/assets/") || url.pathname.startsWith("/landing/");
  if (isTile || isAsset) {
    event.respondWith(cacheFirst(request));
  } else if (url.origin === self.location.origin && url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(request));
  } else if (url.origin === self.location.origin && (url.pathname === "/" || url.pathname === "/app" || url.pathname === "/index.html")) {
    event.respondWith(networkFirst(request));
  }
});
