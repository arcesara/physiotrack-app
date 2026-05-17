const CACHE = 'physiotrack-v3';
const ASSETS = [
  '/static/css/style.css',
  '/static/js/sesion.js',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  // Las páginas HTML siempre van a la red, nunca desde caché
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request));
    return;
  }
  // Los recursos estáticos sí se cachean
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
