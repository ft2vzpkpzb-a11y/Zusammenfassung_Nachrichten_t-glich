"""Dateien, die aus dem Briefing eine Handy-App auf dem Startbildschirm machen.

Manifest + Service Worker sorgen dafür, dass die Seite nach „Zum Startbildschirm
hinzufügen“ wie eine App startet (ohne Browserleiste) und auch offline noch das
zuletzt geladene Briefing zeigt — praktisch in der U-Bahn.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SYMBOLE = ["icon-192.png", "icon-512.png", "apple-touch-icon.png", "icon.svg"]

# Netz zuerst: online immer das frische Briefing, offline das zuletzt geladene.
SERVICE_WORKER = """
const CACHE = 'briefing-v1';
const VORRAT = [
  './index.html', './manifest.webmanifest',
  './icon-192.png', './icon-512.png', './apple-touch-icon.png'
];

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
""".strip()


def manifest(titel: str) -> str:
    return json.dumps(
        {
            "name": titel,
            "short_name": "Briefing",
            "description": "Tägliche Nachrichten-Zusammenfassung",
            "start_url": "./index.html",
            "scope": "./",
            "display": "standalone",
            "orientation": "portrait-primary",
            "lang": "de",
            "background_color": "#f6f6f4",
            "theme_color": "#16181d",
            "icons": [
                {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
                {
                    "src": "icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def kopfzeilen() -> str:
    """Meta-Tags, damit iOS und Android die Seite als App behandeln."""
    return """
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" media="(prefers-color-scheme: light)" content="#f6f6f4">
<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#101216">
<link rel="icon" href="icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Briefing">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
""".strip()


def registrierung() -> str:
    """Service Worker registrieren — scheitert still, wenn er fehlt (z. B. lokal)."""
    return (
        "if ('serviceWorker' in navigator) { window.addEventListener('load', function () "
        "{ navigator.serviceWorker.register('sw.js').catch(function () {}); }); }"
    )


def schreibe_dateien(ziel: Path, titel: str) -> list[str]:
    """Manifest, Service Worker und Symbole ins Zielverzeichnis legen."""
    ziel.mkdir(parents=True, exist_ok=True)
    geschrieben = []

    (ziel / "manifest.webmanifest").write_text(manifest(titel), encoding="utf-8")
    geschrieben.append("manifest.webmanifest")

    (ziel / "sw.js").write_text(SERVICE_WORKER + "\n", encoding="utf-8")
    geschrieben.append("sw.js")

    for name in SYMBOLE:
        quelle = ASSETS / name
        if quelle.exists():
            shutil.copyfile(quelle, ziel / name)
            geschrieben.append(name)

    return geschrieben
