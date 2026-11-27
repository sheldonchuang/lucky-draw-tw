const CACHE_NAME = 'luckygo-pwa-v1';
const CORE_ASSETS = [
  './',
  './index.html',
  './bogo-monthly.html',
  './coupons.html',
  './guide.html',
  './contact.html',
  './community.html',
  './manifest.json',
  './assets/icon-192.png',
  './assets/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(CORE_ASSETS).catch(() => {});
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Skip Supabase API, Google Analytics, OAuth, and external non-GET/API traffic
  if (
    url.origin !== self.location.origin ||
    url.pathname.includes('/rest/v1/') ||
    url.pathname.includes('/auth/v1/')
  ) {
    return;
  }

  const isDynamicData =
    req.mode === 'navigate' ||
    url.pathname.endsWith('.html') ||
    url.pathname.endsWith('data.js') ||
    url.pathname.endsWith('events.json');

  if (isDynamicData) {
    // Network-first: always get freshest events & pages when online, fallback to cache offline
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req).then((cached) => cached || caches.match('./index.html')))
    );
    return;
  }

  // Stale-while-revalidate for static local assets
  event.respondWith(
    caches.match(req).then((cached) => {
      const fetchPromise = fetch(req)
        .then((res) => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          }
          return res;
        })
        .catch(() => cached);
      return cached || fetchPromise;
    })
  );
});
