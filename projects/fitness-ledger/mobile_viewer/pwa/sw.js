const CACHE_NAME = "fitness-ledger-pwa-v30";
const APP_SHELL = [
  "./",
  "./index.html",
  "./styles.css?v=20260820-04",
  "./config.js?v=20260820-04",
  "./app.js?v=20260820-04",
  "./data-modules.js?v=20260820-04",
  "./api.js?v=20260820-04",
  "./share.html",
  "./share.css?v=20260820-04",
  "./share.js?v=20260820-04",
  "./manifest.webmanifest",
  "./icons/fitness-ledger.png"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  const requestUrl = new URL(event.request.url);
  if (requestUrl.pathname.includes("/api/")) return;
  if (event.request.method !== "GET" || requestUrl.origin !== self.location.origin) return;

  event.respondWith(
    fetch(event.request)
      .then(response => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request).then(response => response || caches.match("./index.html")))
  );
});
