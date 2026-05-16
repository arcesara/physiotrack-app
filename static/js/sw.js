const CACHE = 'physiotrack-v1';
const ASSETS = ['/', '/static/css/style.css', '/static/js/sesion.js'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
});

self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
