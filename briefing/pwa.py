"""Dateien, die aus dem Briefing eine Handy-App auf dem Startbildschirm machen.

Manifest + Service Worker sorgen dafür, dass die Seite nach „Zum Startbildschirm
hinzufügen“ wie eine App startet (ohne Browserleiste) und auch offline noch das
zuletzt geladene Briefing zeigt — praktisch in der U-Bahn.
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
from functools import lru_cache
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
# Das Symbol stammt aus einer 1024-px-Vorlage (mit Higgsfield erzeugt); alle
# Größen sind daraus verkleinert. „maskable“ hat Rand für Androids Kreismaske.
SYMBOLE = [
    "icon-192.png",
    "icon-512.png",
    "icon-maskable-512.png",
    "apple-touch-icon.png",
    "favicon-32.png",
]


@lru_cache(maxsize=None)
def adresse(name: str) -> str:
    """Dateiname mit Prüfsumme des Inhalts, etwa ``favicon-32.png?v=1a2b3c4d``.

    Safari merkt sich Symbole unter ihrer Adresse und fragt dort nicht neu an —
    ein neues Bild unter altem Namen bliebe in den Tabs unsichtbar. Mit der
    Prüfsumme bekommt jedes neue Bild eine neue Adresse; GitHub Pages übergeht
    den Zusatz und liefert einfach die Datei.
    """
    datei = ASSETS / name
    if not datei.exists():
        return name
    return f"{name}?v={hashlib.sha256(datei.read_bytes()).hexdigest()[:8]}"


# Netz zuerst: online immer das frische Briefing, offline das zuletzt geladene.
# __VORRAT__ füllt service_worker() mit den Adressen, unter denen die Seiten anfragen.
_SW_VORLAGE = """
const CACHE = 'briefing-v4';
const VORRAT = __VORRAT__;

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


def service_worker() -> str:
    """Der Vorrat nennt die Symbole mit Prüfsumme — genau so fragen die Seiten
    sie an; unter dem bloßen Dateinamen fände der Service Worker sie offline nicht."""
    symbole = ["icon-192.png", "icon-512.png", "apple-touch-icon.png", "favicon-32.png"]
    vorrat = ["./index.html", "./manifest.webmanifest"] + [f"./{adresse(n)}" for n in symbole]
    return _SW_VORLAGE.replace("__VORRAT__", json.dumps(vorrat))


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
            "background_color": "#f5f5f7",
            "theme_color": "#f5f5f7",
            "icons": [
                {"src": adresse("icon-192.png"), "sizes": "192x192", "type": "image/png"},
                {"src": adresse("icon-512.png"), "sizes": "512x512", "type": "image/png"},
                {
                    "src": adresse("icon-maskable-512.png"),
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def kopfzeilen(wurzel: str = "") -> str:
    """Meta-Tags, damit iOS und Android die Seite als App behandeln.

    ``wurzel`` ist der Weg zur Website-Wurzel: leer für index.html, "../" für
    die Ausgaben im Ordner archiv/.
    """
    return f"""
<link rel="manifest" href="{wurzel}manifest.webmanifest">
<meta name="theme-color" media="(prefers-color-scheme: light)" content="#f5f5f7">
<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#000000">
<link rel="icon" href="{wurzel}{adresse('favicon-32.png')}" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{wurzel}{adresse('apple-touch-icon.png')}">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Briefing">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
""".strip()


@lru_cache(maxsize=1)
def leisten_symbol() -> str:
    """Das Symbol für die Navigationsleiste als data:-URI — so bleibt jede Seite
    eigenständig, auch die Einzeldatei und die Archivseiten. Leer, wenn es fehlt."""
    datei = ASSETS / "leiste-symbol.jpg"
    if not datei.exists():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(datei.read_bytes()).decode("ascii")


def registrierung(wurzel: str = "") -> str:
    """Service Worker registrieren — scheitert still, wenn er fehlt (z. B. lokal)."""
    return (
        "if ('serviceWorker' in navigator) { window.addEventListener('load', function () "
        "{ navigator.serviceWorker.register('" + wurzel + "sw.js').catch(function () {}); }); }"
    )


def schreibe_dateien(ziel: Path, titel: str) -> list[str]:
    """Manifest, Service Worker und Symbole ins Zielverzeichnis legen."""
    ziel.mkdir(parents=True, exist_ok=True)
    geschrieben = []

    (ziel / "manifest.webmanifest").write_text(manifest(titel), encoding="utf-8")
    geschrieben.append("manifest.webmanifest")

    (ziel / "sw.js").write_text(service_worker() + "\n", encoding="utf-8")
    geschrieben.append("sw.js")

    for name in SYMBOLE:
        quelle = ASSETS / name
        if quelle.exists():
            shutil.copyfile(quelle, ziel / name)
            geschrieben.append(name)

    return geschrieben
