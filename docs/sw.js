const CACHE = 'briefing-v4';
const VORRAT = ["./index.html", "./manifest.webmanifest", "./icon-192.png?v=3bb2c137", "./icon-512.png?v=a5e17f67", "./apple-touch-icon.png?v=b8a400f6", "./favicon-32.png?v=87ee20b2"];

self.addEventListener('install', (e) => {
  // Beim ersten Besuch gleich ablegen — sonst steht offline nichts bereit.
  e.waitUntil(
    caches.open(CACHE).then((cache) =>
      Promise.all(VORRAT.map((pfad) => cache.add(pfad).catch(() => {})))
    )
  );
  self.skipWaiting();
});
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((namen) => Promise.all(namen.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== self.location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then((antwort) => {
        const kopie = antwort.clone();
        caches.open(CACHE).then((cache) => cache.put(e.request, kopie));
        return antwort;
      })
      .catch(() =>
        caches.match(e.request).then(
          (treffer) =>
            treffer ||
            (e.request.mode === 'navigate' ? caches.match('./index.html') : undefined)
        )
      )
  );
});
