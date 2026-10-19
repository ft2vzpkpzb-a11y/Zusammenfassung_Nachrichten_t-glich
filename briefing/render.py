"""HTML-Briefing rendern — eigenständige Datei ohne externe Ressourcen.

Gestaltung angelehnt an Apple (apple.com, Apple News, iOS): Systemschrift
(SF Pro auf iPhone und Mac), große, eng gesetzte Überschriften mit grauem
Nachsatz, weiße Karten auf hellgrauem Grund, eine durchscheinende
Navigationsleiste und echtes Schwarz im Dunkelmodus.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from html import escape

from . import pwa
from .gesetzgebung import zeitraum

WOCHENTAGE = [
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
]
MONATE = [
    "Jänner",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]
MONATE_KURZ = ["Jän", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

# Grauer Nachsatz hinter der Rubriküberschrift, wie auf apple.com.
NACHSAETZE = {
    "Österreich": "Politik und Wirtschaft im Inland.",
    "Deutschland": "Politik und Wirtschaft beim Nachbarn.",
    "International": "Politik und Wirtschaft weltweit.",
}

GESETZGEBUNG_KARTEN = {
    # id: (Symbol, Farbe, Mehrzahl, Einzahl)
    "nationalrat": ("NR", "#c8102e", "Gesetzesbeschlüsse", "Gesetzesbeschluss"),
    "kongress": ("US", "#0a3161", "Entscheidungen", "Entscheidung"),
}

FARBE = re.compile(r"^#[0-9A-Fa-f]{3,8}$")

SYMBOL_SUCHE = (
    '<svg class="suchfeld__symbol" viewBox="0 0 24 24" aria-hidden="true">'
    '<circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2.2"/>'
    '<path d="m15.5 15.5 5 5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>'
)
SYMBOL_HELLDUNKEL = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" fill="none" '
    'stroke="currentColor" stroke-width="2"/><path d="M12 3.5a8.5 8.5 0 0 1 0 17z" fill="currentColor"/></svg>'
)
SYMBOL_PFEIL = (
    '<svg class="pfeil" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" fill="none" '
    'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)
SYMBOL_NACH_OBEN = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 15 6-6 6 6" fill="none" '
    'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)
SYMBOL_KALENDER = (
    '<svg class="leer__symbol" viewBox="0 0 48 48" aria-hidden="true"><rect x="6" y="9" width="36" '
    'height="33" rx="7" fill="none" stroke="currentColor" stroke-width="2.5"/><path d="M6 18h36M16 5v8M32 '
    '5v8" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/><circle cx="24" cy="30" r="2.5" '
    'fill="currentColor"/></svg>'
)

CSS = """
*, *::before, *::after { box-sizing: border-box; }
:root {
  --bg: #f5f5f7;
  --flaeche: #ffffff;
  --flaeche-2: #fafafc;
  --fuellung: rgba(118,118,128,.12);
  --fuellung-2: rgba(118,118,128,.07);
  --text: #1d1d1f;
  --text-2: #6e6e73;
  --text-3: #86868b;
  --trenner: rgba(60,60,67,.13);
  --link: #0066cc;
  --blau: #0071e3;
  --gruen: #248a3d;
  --rot: #e30000;
  --orange: #b64400;
  --lila: #8944ab;
  --glas: rgba(250,250,252,.78);
  --schatten: 0 2px 6px rgba(0,0,0,.025), 0 12px 32px -8px rgba(0,0,0,.08);
  --schatten-hoch: 0 4px 10px rgba(0,0,0,.04), 0 24px 48px -12px rgba(0,0,0,.14);
  --radius: 22px;
  --sans: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", Helvetica, Arial, sans-serif;
  --rund: ui-rounded, "SF Pro Rounded", -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #000000; --flaeche: #1c1c1e; --flaeche-2: #232325;
    --fuellung: rgba(118,118,128,.24); --fuellung-2: rgba(118,118,128,.14);
    --text: #f5f5f7; --text-2: #a1a1a6; --text-3: #8e8e93; --trenner: rgba(84,84,88,.55);
    --link: #2997ff; --blau: #0a84ff; --gruen: #30d158; --rot: #ff453a; --orange: #ff9f0a; --lila: #bf5af2;
    --glas: rgba(22,22,23,.78); --schatten: none; --schatten-hoch: none;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #000000; --flaeche: #1c1c1e; --flaeche-2: #232325;
  --fuellung: rgba(118,118,128,.24); --fuellung-2: rgba(118,118,128,.14);
  --text: #f5f5f7; --text-2: #a1a1a6; --text-3: #8e8e93; --trenner: rgba(84,84,88,.55);
  --link: #2997ff; --blau: #0a84ff; --gruen: #30d158; --rot: #ff453a; --orange: #ff9f0a; --lila: #bf5af2;
  --glas: rgba(22,22,23,.78); --schatten: none; --schatten-hoch: none;
  color-scheme: dark;
}

html { scroll-padding-top: 64px; -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font-family: var(--sans); font-size: 17px; line-height: 1.47; letter-spacing: -.022em;
  -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
}
.huelle { max-width: 1180px; margin: 0 auto; padding: 0 22px 80px; }
a { color: var(--link); text-decoration: none; }
:focus-visible { outline: 3px solid color-mix(in srgb, var(--blau) 60%, transparent); outline-offset: 2px; border-radius: 8px; }
.nur-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

/* ---------- Navigationsleiste (Glas) ---------- */
.leiste {
  position: sticky; top: 0; z-index: 40;
  background: var(--glas);
  -webkit-backdrop-filter: saturate(180%) blur(20px); backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--trenner);
  padding-top: env(safe-area-inset-top);
}
.leiste__innen {
  max-width: 1180px; margin: 0 auto; padding: 0 22px; height: 52px;
  display: flex; align-items: center; gap: 22px;
}
.leiste__marke {
  display: flex; align-items: center; gap: 9px; flex: none;
  font-size: 19px; font-weight: 600; letter-spacing: -.02em; color: var(--text);
}
.leiste__symbol {
  width: 26px; height: 26px; border-radius: 7px; flex: none;
  background: linear-gradient(160deg, #ff5f6d 0%, #e3192d 100%);
  box-shadow: inset 0 0 0 .5px rgba(0,0,0,.08);
  position: relative;
}
.leiste__symbol::after {
  content: ""; position: absolute; left: 6px; right: 6px; top: 7px; height: 12px;
  background: linear-gradient(#fff 0 0) top/100% 3px no-repeat, linear-gradient(rgba(255,255,255,.75) 0 0) 0 6px/100% 2px no-repeat, linear-gradient(rgba(255,255,255,.75) 0 0) 0 10px/70% 2px no-repeat;
}
.leiste__links {
  display: flex; gap: 22px; flex: 1; min-width: 0; overflow-x: auto; scrollbar-width: none;
  -webkit-mask-image: linear-gradient(90deg, #000 85%, transparent); mask-image: linear-gradient(90deg, #000 85%, transparent);
  padding-right: 24px;
}
.leiste__links::-webkit-scrollbar { display: none; }
.leiste__links a { font-size: 13px; letter-spacing: -.01em; color: var(--text); opacity: .8; white-space: nowrap; }
.leiste__links a:hover { opacity: 1; color: var(--link); }
.symbolknopf {
  flex: none; width: 34px; height: 34px; border-radius: 50%; border: 0; cursor: pointer;
  display: grid; place-items: center; color: var(--text); background: transparent;
}
.symbolknopf:hover { background: var(--fuellung); }
.symbolknopf svg { width: 19px; height: 19px; }

/* ---------- Kopf ---------- */
.held { padding: 56px 0 30px; }
.held__datum { margin: 0 0 6px; font-size: 17px; font-weight: 600; color: var(--text-2); letter-spacing: -.01em; }
.held__wochentag { color: var(--rot); }
.held__titel {
  margin: 0; font-size: clamp(40px, 6.4vw, 64px); line-height: 1.05; font-weight: 700; letter-spacing: -.035em;
}
.held__intro { margin: 10px 0 0; font-size: clamp(19px, 2.4vw, 24px); line-height: 1.3; color: var(--text-2); letter-spacing: -.02em; }
.held__intro strong { color: var(--text); font-weight: 600; }
.kopf__filter {
  display: inline-flex; align-items: center; gap: 7px; margin: 18px 0 0; padding: 6px 13px;
  font-size: 13px; font-weight: 500; color: var(--text-2); background: var(--fuellung-2); border-radius: 999px; letter-spacing: -.01em;
}
.kopf__filter::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--gruen); }

.kennzahlen { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin-top: 30px; }
.kennzahl {
  background: var(--flaeche); border-radius: 18px; padding: 16px 18px 15px; box-shadow: var(--schatten);
  display: flex; flex-direction: column; gap: 2px;
}
.kennzahl__wert { font-family: var(--rund); font-size: 32px; line-height: 1.1; font-weight: 700; letter-spacing: -.02em; font-variant-numeric: tabular-nums; }
.kennzahl__label { font-size: 13px; color: var(--text-2); letter-spacing: -.005em; }
.kennzahl--akzent .kennzahl__wert { color: var(--rot); }

.demo {
  margin: 22px 0 0; padding: 13px 16px; border-radius: 14px; font-size: 15px;
  color: var(--orange); background: color-mix(in srgb, var(--orange) 10%, transparent);
}

/* ---------- Suche & Knöpfe ---------- */
.werkzeuge { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 4px 0 44px; }
.suchfeld {
  flex: 1 1 280px; min-width: 0; display: flex; align-items: center; gap: 8px;
  padding: 0 14px; height: 44px; border-radius: 12px; background: var(--fuellung); color: var(--text-3);
}
.suchfeld__symbol { width: 18px; height: 18px; flex: none; }
.suche {
  flex: 1; min-width: 0; height: 100%; border: 0; outline: 0; background: transparent;
  font: inherit; font-size: 17px; color: var(--text); letter-spacing: -.022em;
}
.suche::placeholder { color: var(--text-3); }
.suche::-webkit-search-cancel-button { filter: grayscale(1); }
.suchfeld:focus-within { box-shadow: 0 0 0 3px color-mix(in srgb, var(--blau) 45%, transparent); }
.knopf {
  height: 44px; padding: 0 20px; border: 0; border-radius: 999px; cursor: pointer;
  font: inherit; font-size: 15px; font-weight: 500; letter-spacing: -.01em; white-space: nowrap;
  color: var(--link); background: var(--fuellung-2);
}
.knopf:hover { background: var(--fuellung); }
.knopf--voll { color: #fff; background: var(--blau); }
.knopf--voll:hover { background: color-mix(in srgb, var(--blau) 88%, #000); }
.treffer { font-size: 15px; color: var(--text-2); font-variant-numeric: tabular-nums; }
.treffer:empty { display: none; }

/* ---------- Rubriken ---------- */
.rubrik { margin: 0 0 64px; }
.rubrik__titel {
  margin: 0 0 22px; font-size: clamp(28px, 3.6vw, 40px); line-height: 1.1; font-weight: 700; letter-spacing: -.03em;
}
.rubrik__titel span { color: var(--text-3); }
.raster { display: grid; gap: 20px; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); }

/* ---------- Karten ---------- */
.karte {
  --quellfarbe: var(--blau);
  background: var(--flaeche); border-radius: var(--radius); box-shadow: var(--schatten);
  overflow: hidden; display: flex; flex-direction: column;
  transition: box-shadow .3s ease, transform .3s ease;
}
@media (hover: hover) {
  .karte:hover { box-shadow: var(--schatten-hoch); }
}
.karte--leer { opacity: .9; }
.karte__kopf { display: flex; align-items: center; gap: 13px; padding: 18px 20px 14px; }
.karte__logo {
  flex: none; width: 42px; height: 42px; border-radius: 11px; display: grid; place-items: center;
  font-family: var(--rund); font-size: 17px; font-weight: 700; letter-spacing: -.02em; color: #fff;
  background: linear-gradient(160deg, color-mix(in srgb, var(--quellfarbe) 78%, #fff) 0%, var(--quellfarbe) 70%);
  box-shadow: inset 0 0 0 .5px rgba(0,0,0,.12);
}
.karte__logo--lang { font-size: 13px; letter-spacing: 0; }
.karte__kopftext { min-width: 0; }
.karte__name { margin: 0; font-size: 19px; line-height: 1.2; font-weight: 600; letter-spacing: -.02em; }
.karte__name a { color: var(--text); }
.karte__name a:hover { color: var(--link); }
.karte__unter { margin: 1px 0 0; font-size: 13px; color: var(--text-2); letter-spacing: -.005em; font-variant-numeric: tabular-nums; }

.hinweis { margin: 0 20px 10px; padding: 10px 13px; border-radius: 12px; font-size: 13px; line-height: 1.4; color: var(--text-2); background: var(--fuellung-2); }
.hinweis--warn { color: var(--orange); background: color-mix(in srgb, var(--orange) 10%, transparent); }

/* ---------- Listen ---------- */
.liste { list-style: none; margin: 0; padding: 0 0 6px; }
.zeile { position: relative; }
.zeile + .zeile::before {
  content: ""; position: absolute; top: 0; right: 0; left: 20px; height: 1px; background: var(--trenner);
}
.zeile > a { display: block; padding: 12px 20px; color: inherit; transition: background .15s ease; }
.zeile > a:hover { background: var(--fuellung-2); }
.zeile > a:active { background: var(--fuellung); }
.zeile__titel { display: block; font-size: 16px; line-height: 1.35; font-weight: 600; letter-spacing: -.016em; }
.zeile__original { display: block; margin-top: 3px; font-size: 14px; line-height: 1.35; color: var(--text-2); letter-spacing: -.01em; }
.zeile__meta {
  display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 4px;
  font-size: 13px; color: var(--text-3); letter-spacing: -.005em; font-variant-numeric: tabular-nums;
}
.zeile__meta > * + *::before { content: "·"; margin-right: 6px; }
.zeile__meta > .marke::before, .zeile__meta > .marke + *::before { content: none; margin: 0; }
.marke {
  font-size: 11px; font-weight: 600; letter-spacing: .01em; padding: 1px 7px; border-radius: 6px;
  color: var(--text-2); background: var(--fuellung-2);
}

/* Rang 1–5 */
.liste--haupt { counter-reset: rang; }
.liste--haupt > .zeile { counter-increment: rang; }
.liste--haupt > .zeile > a { padding-left: 52px; }
.liste--haupt > .zeile + .zeile::before { left: 52px; }
.liste--haupt > .zeile > a::before {
  content: counter(rang); position: absolute; left: 20px; top: 11px; width: 20px; text-align: center;
  font-family: var(--rund); font-size: 17px; font-weight: 700; color: var(--quellfarbe);
}

/* ---------- Aufklapper ---------- */
.mehr { border-top: 1px solid var(--trenner); margin-top: 2px; }
.mehr > summary {
  cursor: pointer; list-style: none; padding: 14px 20px; user-select: none;
  display: flex; align-items: center; gap: 6px;
  font-size: 15px; font-weight: 500; color: var(--link); letter-spacing: -.01em;
}
.mehr > summary::-webkit-details-marker { display: none; }
.mehr > summary:hover { background: var(--fuellung-2); }
.mehr .pfeil { width: 15px; height: 15px; transition: transform .25s ease; }
.mehr[open] > summary .pfeil { transform: rotate(180deg); }
.mehr[open] > summary { border-bottom: 1px solid var(--trenner); }
.mehr__zu { display: none; }
.mehr[open] > summary .mehr__auf { display: none; }
.mehr[open] > summary .mehr__zu { display: inline; }
.mehr .liste { max-height: 34rem; overflow-y: auto; overscroll-behavior: contain; }

/* ---------- Breite Karten (FT, Gesetzgebung) ---------- */
.gross { grid-column: 1 / -1; }
.gross .liste { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 0; }
.gross .liste > .zeile::before { left: 20px; }
.gross .liste--haupt > .zeile::before { left: 52px; }
.gross .liste > .zeile:nth-child(2)::before { display: none; }
.gross .liste > .zeile:nth-child(1)::before { display: none; }
@media (max-width: 760px) {
  .gross .liste { grid-template-columns: 1fr; }
  .gross .liste > .zeile:nth-child(2)::before { display: block; }
}

/* ---------- Gesetzgebung ---------- */
.raster--gesetze { grid-template-columns: 1fr; }
.beschluss > a { display: grid; grid-template-columns: 46px minmax(0, 1fr); gap: 14px; padding: 14px 20px; }
.liste--beschluesse > .zeile::before, .gross .liste--beschluesse > .zeile::before { left: 80px; }
.kalender {
  width: 46px; border-radius: 11px; overflow: hidden; text-align: center; align-self: start;
  background: var(--flaeche); box-shadow: 0 0 0 1px var(--trenner), 0 1px 3px rgba(0,0,0,.06);
}
.kalender__monat {
  display: block; padding: 2px 0 1px; font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;
  color: #fff; background: var(--rot);
}
.kalender__tag { display: block; padding: 2px 0 4px; font-family: var(--rund); font-size: 21px; line-height: 1.1; font-weight: 600; color: var(--text); }
.beschluss__text {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  margin-top: 3px; font-size: 14px; line-height: 1.38; color: var(--text-2); letter-spacing: -.01em;
}
.ergebnis { font-size: 11px; font-weight: 600; letter-spacing: .01em; padding: 1px 8px; border-radius: 999px; }
.ergebnis--ja { color: var(--gruen); background: color-mix(in srgb, var(--gruen) 13%, transparent); }
.ergebnis--nein { color: var(--rot); background: color-mix(in srgb, var(--rot) 12%, transparent); }
.ergebnis--person { color: var(--blau); background: color-mix(in srgb, var(--blau) 12%, transparent); }
.ergebnis--gesetz { color: var(--lila); background: color-mix(in srgb, var(--lila) 13%, transparent); }
.zeile__meta > .ergebnis::before, .zeile__meta > .ergebnis + *::before { content: none; margin: 0; }
.fraktionen { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 7px; font-size: 12px; color: var(--text-2); }
.fraktionen__gruppe { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
.fraktionen__label { font-weight: 600; color: var(--text-3); }
.fraktion { display: inline-flex; align-items: center; gap: 4px; font-weight: 500; letter-spacing: 0; }
.fraktion::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--f, var(--text-3)); }
.fraktionen__gruppe--dagegen .fraktion { color: var(--text-3); }

.leer { padding: 18px 24px 30px; text-align: center; color: var(--text-2); }
.leer__symbol { width: 44px; height: 44px; color: var(--text-3); opacity: .7; }
.leer__titel { margin: 8px 0 2px; font-size: 17px; font-weight: 600; color: var(--text); letter-spacing: -.02em; }
.leer__text { margin: 0; font-size: 15px; }

/* ---------- Fehler / Status ---------- */
.fehlerbox {
  margin: 0 20px 14px; padding: 12px 14px; border-radius: 12px; font-size: 14px; line-height: 1.4;
  color: var(--rot); background: color-mix(in srgb, var(--rot) 9%, transparent);
}
.fehlerbox code { font-family: var(--mono); font-size: 12px; word-break: break-all; }
.status__karte { background: var(--flaeche); border-radius: var(--radius); box-shadow: var(--schatten); overflow-x: auto; }
.status__tabelle { width: 100%; border-collapse: collapse; font-size: 13px; letter-spacing: -.005em; }
.status__tabelle th, .status__tabelle td { text-align: left; padding: 10px 14px; border-bottom: 1px solid var(--trenner); vertical-align: top; }
.status__tabelle tr:last-child td { border-bottom: 0; }
.status__tabelle th { font-weight: 600; color: var(--text-2); font-size: 12px; background: var(--flaeche-2); }
.status__tabelle td.url { font-family: var(--mono); font-size: 11.5px; word-break: break-all; color: var(--text-2); min-width: 220px; }
.pille { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.pille--ok { color: var(--gruen); background: color-mix(in srgb, var(--gruen) 13%, transparent); }
.pille--fehler { color: var(--rot); background: color-mix(in srgb, var(--rot) 12%, transparent); }
.fuss { margin: 40px 0 0; padding-top: 18px; border-top: 1px solid var(--trenner); font-size: 12px; line-height: 1.5; color: var(--text-3); letter-spacing: 0; }
.fuss + .fuss { margin-top: 8px; padding-top: 0; border-top: 0; }
.versteckt { display: none !important; }

/* ---------- Archiv ---------- */
.archiv__liste { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px; }
.archiv__liste a {
  display: block; padding: 8px 16px; font-size: 15px; color: var(--text); border-radius: 999px;
  background: var(--flaeche); box-shadow: var(--schatten);
}
.archiv__liste a:hover { color: var(--link); }

/* ---------- Nach oben ---------- */
.nach-oben {
  position: fixed; right: 18px; bottom: calc(18px + env(safe-area-inset-bottom)); z-index: 30;
  width: 44px; height: 44px; border-radius: 50%; border: 0; cursor: pointer;
  display: grid; place-items: center; color: var(--text);
  background: var(--glas); -webkit-backdrop-filter: saturate(180%) blur(20px); backdrop-filter: saturate(180%) blur(20px);
  box-shadow: 0 0 0 1px var(--trenner), 0 8px 24px rgba(0,0,0,.12);
  opacity: 0; visibility: hidden; transform: translateY(8px); transition: opacity .25s ease, transform .25s ease, visibility .25s;
}
.nach-oben svg { width: 20px; height: 20px; }
.nach-oben.sichtbar { opacity: 1; visibility: visible; transform: none; }

@media (max-width: 600px) {
  body { font-size: 16px; }
  .huelle, .leiste__innen { padding-left: 16px; padding-right: 16px; }
  .leiste__innen { gap: 14px; height: 48px; }
  .leiste__marke { font-size: 17px; }
  .held { padding: 30px 0 22px; }
  .held__titel { font-size: 36px; letter-spacing: -.03em; }
  .kennzahlen { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 22px; }
  .kennzahl { padding: 13px 15px 12px; border-radius: 16px; }
  .kennzahl__wert { font-size: 26px; }
  .werkzeuge { margin-bottom: 34px; }
  .suchfeld { flex: 1 1 100%; }
  .knopf { flex: 1 1 0; }
  .knopf--drucken { display: none; }
  .rubrik { margin-bottom: 46px; }
  .rubrik__titel { font-size: 28px; margin-bottom: 16px; }
  .raster { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .karte { border-radius: 18px; }
  .karte__kopf { padding: 16px 16px 12px; }
  .zeile > a { padding: 12px 16px; }
  .liste--haupt > .zeile > a { padding-left: 46px; }
  .liste--haupt > .zeile > a::before { left: 15px; }
  .liste--haupt > .zeile + .zeile::before, .gross .liste--haupt > .zeile::before { left: 46px; }
  .beschluss > a { grid-template-columns: 42px minmax(0, 1fr); gap: 12px; padding: 13px 16px; }
  .kalender { width: 42px; }
  .liste--beschluesse > .zeile::before, .gross .liste--beschluesse > .zeile::before { left: 70px; }
  .hinweis, .fehlerbox { margin-left: 16px; margin-right: 16px; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition: none !important; scroll-behavior: auto !important; }
}

@media print {
  .leiste, .werkzeuge, .status, .nach-oben, .archiv { display: none; }
  body { background: #fff; font-size: 11pt; }
  .karte { break-inside: avoid; box-shadow: none; border: 1px solid #ddd; }
  .mehr .liste { max-height: none; overflow: visible; }
  .mehr > summary { display: none; }
  .raster { grid-template-columns: repeat(2, 1fr); }
}
"""

JS = """
(function () {
  var suche = document.getElementById('suche');
  var treffer = document.getElementById('treffer');
  var knopfAlle = document.getElementById('alle');
  var knopfTheme = document.getElementById('theme');
  var zeilen = Array.prototype.slice.call(document.querySelectorAll('.zeile'));
  var aufklapper = Array.prototype.slice.call(document.querySelectorAll('.mehr'));
  var alleOffen = false;

  function filtern() {
    var q = suche.value.trim().toLowerCase();
    var sichtbar = 0;
    zeilen.forEach(function (zeile) {
      var passt = !q || zeile.dataset.text.indexOf(q) !== -1;
      zeile.classList.toggle('versteckt', !passt);
      if (passt) sichtbar++;
    });
    document.querySelectorAll('.karte').forEach(function (karte) {
      var hatTreffer = karte.querySelector('.zeile:not(.versteckt)') !== null;
      karte.classList.toggle('versteckt', Boolean(q) && !hatTreffer);
    });
    if (q) { aufklapper.forEach(function (d) { d.open = true; }); }
    treffer.textContent = q ? sichtbar + ' Treffer' : '';
  }

  function alleUmschalten() {
    alleOffen = !alleOffen;
    aufklapper.forEach(function (d) { d.open = alleOffen; });
    knopfAlle.textContent = alleOffen ? 'Alle zuklappen' : 'Alle aufklappen';
  }

  if (suche) {
    suche.addEventListener('input', filtern);
    suche.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { suche.value = ''; filtern(); }
    });
  }
  if (knopfAlle) knopfAlle.addEventListener('click', alleUmschalten);

  var nachOben = document.getElementById('nachOben');
  if (nachOben) {
    nachOben.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    window.addEventListener('scroll', function () {
      nachOben.classList.toggle('sichtbar', window.scrollY > 700);
    }, { passive: true });
  }

  if (knopfTheme) {
    knopfTheme.addEventListener('click', function () {
      var wurzel = document.documentElement;
      var dunkel = wurzel.getAttribute('data-theme') === 'dark'
        || (!wurzel.getAttribute('data-theme')
            && window.matchMedia('(prefers-color-scheme: dark)').matches);
      wurzel.setAttribute('data-theme', dunkel ? 'light' : 'dark');
    });
  }
  document.addEventListener('keydown', function (e) {
    if (e.key === '/' && suche && document.activeElement !== suche) { e.preventDefault(); suche.focus(); }
  });
})();
"""


def _datum_kurz(tag: date) -> str:
    return f"{tag.day}. {MONATE[tag.month - 1]} {tag.year}"


def _anker(text: str) -> str:
    ersetzt = text.lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        ersetzt = ersetzt.replace(alt, neu)
    return re.sub(r"[^a-z0-9]+", "-", ersetzt).strip("-") or "rubrik"


def _farbe(wert: str, ersatz: str = "") -> str:
    """Nur echte Farbwerte ins ``style``-Attribut lassen."""
    return wert if FARBE.match(wert or "") else ersatz


def _relative_zeit(zeitpunkt: datetime | None, jetzt: datetime) -> str:
    if zeitpunkt is None:
        return ""
    minuten = int((jetzt - zeitpunkt).total_seconds() // 60)
    if minuten < 0:
        return "gerade eben"
    if minuten < 60:
        return f"vor {minuten} Min." if minuten else "gerade eben"
    stunden = minuten // 60
    if stunden < 24:
        return f"vor {stunden} Std."
    tage = stunden // 24
    return "gestern" if tage == 1 else f"vor {tage} Tagen"


def _logo(kuerzel: str) -> str:
    lang = " karte__logo--lang" if len(kuerzel) >= 3 else ""
    return f'<span class="karte__logo{lang}" aria-hidden="true">{escape(kuerzel)}</span>'


def _aufklapper(anzahl: int, wort: str, inhalt: str, listenklasse: str = "liste") -> str:
    return (
        '<details class="mehr">'
        "<summary>"
        f'<span class="mehr__auf">{anzahl} weitere {wort} anzeigen</span>'
        f'<span class="mehr__zu">{anzahl} weitere {wort} ausblenden</span>{SYMBOL_PFEIL}'
        "</summary>"
        f'<ol class="{listenklasse}">{inhalt}</ol>'
        "</details>"
    )


# --------------------------------------------------------------- Schlagzeilen


def _zeile(schlagzeile, quelle, jetzt: datetime) -> str:
    """Eine Schlagzeile — bei Übersetzung steht Deutsch oben, Original darunter."""
    hat_uebersetzung = bool(schlagzeile.uebersetzung)
    haupttext = schlagzeile.uebersetzung if hat_uebersetzung else schlagzeile.titel

    original = ""
    if hat_uebersetzung:
        original = f'<span class="zeile__original">{escape(schlagzeile.titel)}</span>'

    teile: list[str] = []
    if hat_uebersetzung:
        teile.append('<span class="marke">übersetzt</span>')
    if schlagzeile.veroeffentlicht:
        lokal = schlagzeile.veroeffentlicht.astimezone(jetzt.tzinfo)
        teile.append(
            f'<time datetime="{escape(lokal.isoformat())}">{lokal:%H:%M}</time>'
        )
        relativ = _relative_zeit(schlagzeile.veroeffentlicht, jetzt)
        if relativ:
            teile.append(f"<span>{escape(relativ)}</span>")
    meta = f'<span class="zeile__meta">{"".join(teile)}</span>' if teile else ""

    suchtext = escape(f"{schlagzeile.titel} {schlagzeile.uebersetzung}".lower(), quote=True)
    ziel = escape(schlagzeile.link or quelle.webseite or "#", quote=True)
    return (
        f'<li class="zeile" data-text="{suchtext}">'
        f'<a href="{ziel}" target="_blank" rel="noopener noreferrer">'
        f'<span class="zeile__titel">{escape(haupttext)}</span>{original}{meta}'
        f"</a></li>"
    )


def _karte(ergebnis, quelle, jetzt: datetime, sichtbar: int) -> str:
    schlagzeilen = ergebnis.schlagzeilen
    gross = " gross" if quelle.hervorheben else ""
    # Immer nur die ersten n Schlagzeilen offen; der Rest kommt in den Aufklapper.
    anzahl_sichtbar = min(sichtbar, len(schlagzeilen))

    kopf_name = (
        f'<a href="{escape(quelle.webseite, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(quelle.name)}</a>'
        if quelle.webseite
        else escape(quelle.name)
    )
    leer = "" if schlagzeilen else " karte--leer"
    farbe = _farbe(quelle.farbe, "#6e6e73")
    teile = [
        f'<article class="karte{gross}{leer}" style="--quellfarbe: {farbe}">',
        '<header class="karte__kopf">',
        _logo(quelle.kuerzel or quelle.name[:2]),
        '<div class="karte__kopftext">',
        f'<h3 class="karte__name">{kopf_name}</h3>',
        f'<p class="karte__unter">{len(schlagzeilen)} Schlagzeilen</p>',
        "</div></header>",
    ]

    if quelle.uebersetzen and schlagzeilen:
        if any(s.uebersetzung for s in schlagzeilen):
            teile.append(
                '<p class="hinweis">Auf Deutsch übersetzt — das englische Original '
                "steht jeweils darunter.</p>"
            )
        else:
            # Nicht „übersetzt“ behaupten, wenn die Übersetzung gerade nicht läuft.
            teile.append(
                '<p class="hinweis hinweis--warn">Übersetzung derzeit nicht aktiv — '
                "die Schlagzeilen stehen im englischen Original.</p>"
            )
    elif quelle.hinweis:
        teile.append(f'<p class="hinweis">{escape(quelle.hinweis)}</p>')

    if not ergebnis.ok or not schlagzeilen:
        meldungen = ergebnis.fehlermeldungen or ["Keine Schlagzeilen empfangen."]
        eintraege = "".join(f"<div><code>{escape(m)}</code></div>" for m in meldungen)
        teile.append(
            f'<div class="fehlerbox"><strong>Feed konnte nicht gelesen werden</strong>{eintraege}</div>'
        )

    if schlagzeilen:
        haupt = "".join(_zeile(s, quelle, jetzt) for s in schlagzeilen[:anzahl_sichtbar])
        teile.append(f'<ol class="liste liste--haupt">{haupt}</ol>')

        rest = schlagzeilen[anzahl_sichtbar:]
        if rest:
            weitere = "".join(_zeile(s, quelle, jetzt) for s in rest)
            teile.append(_aufklapper(len(rest), "Schlagzeilen", weitere))

    teile.append("</article>")
    return "".join(teile)


# --------------------------------------------------------------- Gesetzgebung


def _ergebnisklasse(beschluss) -> str:
    if not beschluss.angenommen:
        return "ergebnis--nein"
    if beschluss.ergebnis == "bestätigt":
        return "ergebnis--person"
    if beschluss.ergebnis == "unterzeichnet":
        return "ergebnis--gesetz"
    return "ergebnis--ja"


def _fraktionen(beschluss) -> str:
    if not beschluss.parteien:
        return ""
    if beschluss.einstimmig:
        return '<span class="fraktionen"><span class="ergebnis ergebnis--ja">Einstimmig</span></span>'

    def gruppe(label: str, parteien, zusatz: str = "") -> str:
        if not parteien:
            return ""
        namen = "".join(
            f'<span class="fraktion" style="--f: {_farbe(p.farbe, "#8e8e93")}">{escape(p.name)}</span>'
            for p in parteien
        )
        return (
            f'<span class="fraktionen__gruppe{zusatz}">'
            f'<span class="fraktionen__label">{label}</span>{namen}</span>'
        )

    return (
        '<span class="fraktionen">'
        f"{gruppe('Dafür', beschluss.dafuer)}"
        f"{gruppe('Dagegen', beschluss.dagegen, ' fraktionen__gruppe--dagegen')}"
        "</span>"
    )


def _beschlusszeile(beschluss) -> str:
    haupttext = beschluss.uebersetzung or beschluss.titel
    original = (
        f'<span class="zeile__original">{escape(beschluss.titel)}</span>'
        if beschluss.uebersetzung
        else ""
    )
    erlaeuterung = (
        f'<span class="beschluss__text">{escape(beschluss.erlaeuterung)}</span>'
        if beschluss.erlaeuterung
        else ""
    )

    meta: list[str] = []
    if beschluss.gremium and beschluss.gremium != "Nationalrat":
        meta.append(f"<span>{escape(beschluss.gremium)}</span>")
    if beschluss.art:
        meta.append(f'<span class="marke">{escape(beschluss.art)}</span>')
    if beschluss.nummer:
        meta.append(f"<span>{escape(beschluss.nummer)}</span>")
    if beschluss.themen:
        # Nur das erste Thema — mehrere brechen die Zeile am Handy unschön um.
        meta.append(f"<span>{escape(beschluss.themen[0])}</span>")
    if beschluss.stimmen:
        meta.append(f'<span aria-label="Stimmen dafür zu dagegen">{escape(beschluss.stimmen)}</span>')
    if beschluss.ergebnis and beschluss.gremium != "Nationalrat":
        meta.append(
            f'<span class="ergebnis {_ergebnisklasse(beschluss)}">'
            f"{escape(beschluss.ergebnis.capitalize())}</span>"
        )

    tag = beschluss.datum
    suchtext = escape(
        " ".join(
            [beschluss.titel, beschluss.uebersetzung, beschluss.erlaeuterung, beschluss.nummer]
        ).lower(),
        quote=True,
    )
    return (
        f'<li class="zeile beschluss" data-text="{suchtext}">'
        f'<a href="{escape(beschluss.link or "#", quote=True)}" target="_blank" rel="noopener noreferrer">'
        '<span class="kalender" aria-hidden="true">'
        f'<span class="kalender__monat">{MONATE_KURZ[tag.month - 1]}</span>'
        f'<span class="kalender__tag">{tag.day}</span></span>'
        '<span class="beschluss__inhalt">'
        f'<time class="nur-sr" datetime="{tag.isoformat()}">{_datum_kurz(tag)}</time>'
        f'<span class="zeile__titel">{escape(haupttext)}</span>{original}{erlaeuterung}'
        f'<span class="zeile__meta">{"".join(meta)}</span>'
        f"{_fraktionen(beschluss)}"
        "</span></a></li>"
    )


def _gesetzkarte(ergebnis, heute: date, tage: int, sichtbar: int) -> str:
    kuerzel, farbe, mehrzahl, einzahl = GESETZGEBUNG_KARTEN.get(
        ergebnis.id, (ergebnis.name[:2], "#6e6e73", "Beschlüsse", "Beschluss")
    )
    von, bis = zeitraum(heute, tage)
    anzahl = len(ergebnis.beschluesse)
    zeitspanne = f"{von.day}.{von.month}.–{bis.day}.{bis.month}."
    name = (
        f'<a href="{escape(ergebnis.webseite, quote=True)}" target="_blank" rel="noopener noreferrer">'
        f"{escape(ergebnis.name)}</a>"
        if ergebnis.webseite
        else escape(ergebnis.name)
    )
    teile = [
        f'<article class="karte gross karte--gesetz" style="--quellfarbe: {farbe}">',
        '<header class="karte__kopf">',
        _logo(kuerzel),
        '<div class="karte__kopftext">',
        f'<h3 class="karte__name">{name}</h3>',
        f'<p class="karte__unter">{anzahl} {mehrzahl if anzahl != 1 else einzahl} · {zeitspanne}</p>',
        "</div></header>",
    ]
    for hinweis in ergebnis.hinweise:
        teile.append(f'<p class="hinweis hinweis--warn">{escape(hinweis)}</p>')

    if not ergebnis.ok:
        meldungen = "".join(f"<div><code>{escape(m)}</code></div>" for m in ergebnis.fehlermeldungen)
        teile.append(
            f'<div class="fehlerbox"><strong>Daten konnten nicht abgerufen werden</strong>{meldungen}</div>'
        )
    elif ergebnis.fehlermeldungen and not ergebnis.hinweise:
        fehlend = ", ".join(s.format for s in ergebnis.status if not s.ok)
        teile.append(f'<p class="hinweis hinweis--warn">Unvollständig — nicht erreichbar: {escape(fehlend)}</p>')

    if ergebnis.beschluesse:
        zeilen = [_beschlusszeile(b) for b in ergebnis.beschluesse]
        teile.append(f'<ol class="liste liste--beschluesse">{"".join(zeilen[:sichtbar])}</ol>')
        if zeilen[sichtbar:]:
            teile.append(
                _aufklapper(
                    len(zeilen) - sichtbar,
                    "Beschlüsse" if ergebnis.id == "nationalrat" else "Entscheidungen",
                    "".join(zeilen[sichtbar:]),
                    "liste liste--beschluesse",
                )
            )
    elif ergebnis.ok:
        zuletzt = (
            f"Zuletzt: {_datum_kurz(ergebnis.zuletzt)}." if ergebnis.zuletzt else ""
        )
        teile.append(
            f'<div class="leer">{SYMBOL_KALENDER}'
            f'<p class="leer__titel">Keine {mehrzahl} in den letzten {tage} Tagen</p>'
            f'<p class="leer__text">{escape(zuletzt)}</p></div>'
        )

    teile.append("</article>")
    return "".join(teile)


def _gesetzgebungsabschnitt(gesetzgebung: dict, heute: date, tage: int, sichtbar: int) -> str:
    karten = "".join(
        _gesetzkarte(gesetzgebung[schluessel], heute, tage, sichtbar)
        for schluessel in ("nationalrat", "kongress")
        if gesetzgebung.get(schluessel) is not None
    )
    if not karten:
        return ""
    return (
        '<section class="rubrik" id="gesetzgebung">'
        f'<h2 class="rubrik__titel">Gesetzgebung. <span>Was in den letzten {tage} Tagen beschlossen wurde.</span></h2>'
        f'<div class="raster raster--gesetze">{karten}</div></section>'
    )


# ------------------------------------------------------------ Status & Archiv


def _statuszeile(name: str, status) -> str:
    pille = (
        '<span class="pille pille--ok">OK</span>'
        if status.ok
        else '<span class="pille pille--fehler">Fehler</span>'
    )
    gefiltert = f"−{status.gefiltert}" if status.gefiltert else "—"
    return (
        "<tr>"
        f"<td>{escape(name)}</td>"
        f'<td class="url">{escape(status.url)}</td>'
        f"<td>{pille}</td>"
        f"<td>{escape(status.format)}</td>"
        f"<td>{status.anzahl}</td>"
        f"<td>{gefiltert}</td>"
        f"<td>{status.dauer_ms} ms</td>"
        f"<td>{escape(status.fehler)}</td>"
        "</tr>"
    )


def _statusabschnitt(
    ergebnisse: dict, quellen: list, uebersetzung_hinweis: str, gesetzgebung: dict | None = None
) -> str:
    zeilen = []
    for ergebnis in (gesetzgebung or {}).values():
        zeilen.extend(_statuszeile(ergebnis.name, status) for status in ergebnis.status)
    for quelle in quellen:
        ergebnis = ergebnisse.get(quelle.id)
        if ergebnis is None:
            continue
        zeilen.extend(_statuszeile(quelle.name, status) for status in ergebnis.status)
    hinweis = (
        f'<p class="fuss">{escape(uebersetzung_hinweis)}</p>' if uebersetzung_hinweis else ""
    )
    return (
        '<section class="rubrik status" id="status">'
        '<h2 class="rubrik__titel">Feed-Status. <span>Was beim letzten Abruf ankam.</span></h2>'
        '<div class="status__karte"><table class="status__tabelle">'
        "<thead><tr><th>Quelle</th><th>Feed</th><th>Status</th><th>Format</th>"
        "<th>Einträge</th><th>Gefiltert</th><th>Dauer</th><th>Hinweis</th></tr></thead>"
        f"<tbody>{''.join(zeilen)}</tbody></table></div>{hinweis}</section>"
    )


def _archivabschnitt(archiv: list[date]) -> str:
    """Liste vergangener Ausgaben — nur im Web-Modus vorhanden."""
    if not archiv:
        return ""
    eintraege = "".join(
        f'<li><a href="archiv/{tag:%Y-%m-%d}.html">'
        f"{WOCHENTAGE[tag.weekday()][:2]}, {tag.day}. {MONATE[tag.month - 1][:3]}</a></li>"
        for tag in archiv
    )
    return (
        '<section class="rubrik archiv" id="archiv"><h2 class="rubrik__titel">Frühere Ausgaben. '
        "<span>Die letzten Wochen zum Nachlesen.</span></h2>"
        f'<ul class="archiv__liste">{eintraege}</ul></section>'
    )


# ------------------------------------------------------------------ Gesamt


def rendere_briefing(
    konfiguration,
    ergebnisse: dict,
    jetzt: datetime,
    uebersetzung_hinweis: str = "",
    demo: bool = False,
    web: bool = False,
    archiv: list[date] | None = None,
    gesetzgebung: dict | None = None,
) -> str:
    """Baut die vollständige HTML-Seite.

    ``web=True`` ergänzt Manifest, Symbole und Service-Worker-Registrierung,
    damit die Seite am Handy als App auf den Startbildschirm gelegt werden kann.
    ``gesetzgebung`` (Nationalrat, US-Kongress) steht ganz oben.
    """
    quellen = konfiguration.quellen
    sichtbar = konfiguration.sichtbare_schlagzeilen
    tage = getattr(getattr(konfiguration, "gesetzgebung", None), "tage", 7)
    gesamt = sum(len(e.schlagzeilen) for e in ergebnisse.values())
    uebersetzt = sum(1 for e in ergebnisse.values() for s in e.schlagzeilen if s.uebersetzung)
    quellen_ok = sum(1 for q in quellen if ergebnisse.get(q.id) and ergebnisse[q.id].ok)
    beschluesse = sum(len(e.beschluesse) for e in (gesetzgebung or {}).values())

    navigation: list[tuple[str, str]] = []
    abschnitte: list[str] = []

    if gesetzgebung:
        abschnitt = _gesetzgebungsabschnitt(gesetzgebung, jetzt.date(), tage, sichtbar)
        if abschnitt:
            abschnitte.append(abschnitt)
            navigation.append(("gesetzgebung", "Gesetzgebung"))

    # Hervorgehobene Quellen (FT) danach, dann nach Rubrik gruppiert.
    hervorgehoben = [q for q in quellen if q.hervorheben and q.id in ergebnisse]
    if hervorgehoben:
        karten = "".join(_karte(ergebnisse[q.id], q, jetzt, sichtbar) for q in hervorgehoben)
        namen = ", ".join(q.name for q in hervorgehoben)
        abschnitte.append(
            '<section class="rubrik" id="fokus">'
            f'<h2 class="rubrik__titel">Im Fokus. <span>{escape(namen)} — vollständig.</span></h2>'
            f'<div class="raster">{karten}</div></section>'
        )
        navigation.append(("fokus", "Im Fokus"))

    rubriken: dict[str, list] = {}
    for quelle in quellen:
        if quelle.hervorheben:
            continue
        rubriken.setdefault(quelle.kategorie, []).append(quelle)

    for kategorie, quellen_der_rubrik in rubriken.items():
        karten = "".join(
            _karte(ergebnisse[q.id], q, jetzt, sichtbar)
            for q in quellen_der_rubrik
            if q.id in ergebnisse
        )
        if not karten:
            continue
        anker = _anker(kategorie)
        nachsatz = NACHSAETZE.get(kategorie, "")
        nachsatz_html = f" <span>{escape(nachsatz)}</span>" if nachsatz else ""
        abschnitte.append(
            f'<section class="rubrik" id="{anker}">'
            f'<h2 class="rubrik__titel">{escape(kategorie)}.{nachsatz_html}</h2>'
            f'<div class="raster">{karten}</div></section>'
        )
        navigation.append((anker, kategorie))

    if archiv:
        navigation.append(("archiv", "Archiv"))
    navigation.append(("status", "Status"))
    links = "".join(f'<a href="#{anker}">{escape(text)}</a>' for anker, text in navigation)

    demo_banner = (
        '<p class="demo"><strong>Vorschau mit Beispieldaten.</strong> '
        "Diese Seite wurde mit erfundenen Schlagzeilen und Beschlüssen erzeugt, um das "
        "Layout zu zeigen — sie enthält keine echten Nachrichten.</p>"
        if demo
        else ""
    )

    # Sichtbar machen, dass gefiltert wird — sonst wirken fehlende Themen wie ein Fehler.
    ohne_filter = [q.name for q in quellen if not q.rubriken_filtern and q.id in ergebnisse]
    filterhinweis = ""
    if getattr(konfiguration.rubrikfilter, "aktiv", False):
        ausnahme = f" · {escape(', '.join(ohne_filter))} vollständig" if ohne_filter else ""
        filterhinweis = f'<p class="kopf__filter">Nur Politik &amp; Wirtschaft{ausnahme}</p>'

    kennzahlen = [
        f'<div class="kennzahl"><span class="kennzahl__wert">{gesamt}</span><span class="kennzahl__label">Schlagzeilen</span></div>',
        f'<div class="kennzahl"><span class="kennzahl__wert">{quellen_ok}/{len(quellen)}</span><span class="kennzahl__label">Quellen abgerufen</span></div>',
    ]
    if gesetzgebung:
        kennzahlen.append(
            f'<div class="kennzahl kennzahl--akzent"><span class="kennzahl__wert">{beschluesse}</span>'
            f'<span class="kennzahl__label">Beschlüsse · {tage} Tage</span></div>'
        )
    kennzahlen.append(
        f'<div class="kennzahl"><span class="kennzahl__wert">{uebersetzt}</span><span class="kennzahl__label">übersetzt</span></div>'
    )

    untertitel = getattr(konfiguration, "untertitel", "") or "Politik und Wirtschaft auf einen Blick"
    datenhinweis = (
        '<p class="fuss">Gesetzgebung: Parlament Österreich (Open Data, CC BY 4.0), '
        "senate.gov, clerk.house.gov und api.congress.gov.</p>"
        if gesetzgebung
        else ""
    )
    titel = f"{konfiguration.titel} — {jetzt:%d.%m.%Y}"
    app_kopf = pwa.kopfzeilen() if web else ""
    app_skript = pwa.registrierung() if web else ""
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>{escape(titel)}</title>
{app_kopf}
<style>{CSS}</style>
</head>
<body>
<nav class="leiste" aria-label="Rubriken">
  <div class="leiste__innen">
    <a class="leiste__marke" href="#oben"><span class="leiste__symbol" aria-hidden="true"></span>Briefing</a>
    <div class="leiste__links">{links}</div>
    <button id="theme" class="symbolknopf" type="button" aria-label="Hell- oder Dunkelmodus" title="Hell / Dunkel">{SYMBOL_HELLDUNKEL}</button>
  </div>
</nav>
<div class="huelle" id="oben">
<header class="held">
  <p class="held__datum"><span class="held__wochentag">{WOCHENTAGE[jetzt.weekday()]}</span>, {jetzt.day}. {MONATE[jetzt.month - 1]} {jetzt.year}</p>
  <h1 class="held__titel">{escape(konfiguration.titel)}</h1>
  <p class="held__intro">{escape(untertitel)}. <strong>Stand {jetzt:%H:%M} Uhr.</strong></p>
  {filterhinweis}
  <div class="kennzahlen">{"".join(kennzahlen)}</div>
  {demo_banner}
</header>

<div class="werkzeuge">
  <label class="suchfeld">{SYMBOL_SUCHE}<input id="suche" class="suche" type="search" placeholder="Suchen" aria-label="Schlagzeilen und Beschlüsse durchsuchen"></label>
  <span id="treffer" class="treffer" role="status"></span>
  <button id="alle" class="knopf" type="button">Alle aufklappen</button>
  <button class="knopf knopf--drucken" type="button" onclick="window.print()">Drucken</button>
</div>

{"".join(abschnitte)}
{_archivabschnitt(archiv or [])}
{_statusabschnitt(ergebnisse, quellen, uebersetzung_hinweis, gesetzgebung)}
<p class="fuss">Erzeugt am {jetzt:%d.%m.%Y um %H:%M} Uhr ({escape(konfiguration.zeitzone)}). Je Quelle
sind die {sichtbar} aktuellsten Einträge sichtbar, alle weiteren stehen im Aufklapper.</p>
{datenhinweis}
</div>
<button id="nachOben" class="nach-oben" type="button" aria-label="Nach oben">{SYMBOL_NACH_OBEN}</button>
<script>{JS}
{app_skript}</script>
</body>
</html>
"""
