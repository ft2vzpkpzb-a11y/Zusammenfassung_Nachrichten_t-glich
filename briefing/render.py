"""HTML-Briefing rendern — eigenständige Datei ohne externe Ressourcen."""

from __future__ import annotations

from datetime import date, datetime
from html import escape

from . import pwa

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

CSS = """
*, *::before, *::after { box-sizing: border-box; }
:root {
  --bg: #f6f6f4;
  --bg-karte: #ffffff;
  --bg-gedaempft: #eeedea;
  --text: #16181d;
  --text-gedaempft: #5c6270;
  --text-schwach: #868d9b;
  --rand: #e0dfdb;
  --rand-stark: #cbcac5;
  --akzent: #1b3a6b;
  --ok: #197a4b;
  --warn: #a8570b;
  --fehler: #b3261e;
  --radius: 14px;
  --schatten: 0 1px 2px rgba(16,18,23,.05), 0 8px 24px -12px rgba(16,18,23,.16);
  --serif: ui-serif, Georgia, "Iowan Old Style", "Times New Roman", serif;
  --sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #101216;
    --bg-karte: #181b21;
    --bg-gedaempft: #21252d;
    --text: #eceef2;
    --text-gedaempft: #a4abb8;
    --text-schwach: #79808d;
    --rand: #282d36;
    --rand-stark: #39404b;
    --akzent: #8fb4e8;
    --ok: #5fcf95;
    --warn: #e0a458;
    --fehler: #f2857c;
    --schatten: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.6);
  }
}
:root[data-theme="dark"] {
  --bg: #101216; --bg-karte: #181b21; --bg-gedaempft: #21252d;
  --text: #eceef2; --text-gedaempft: #a4abb8; --text-schwach: #79808d;
  --rand: #282d36; --rand-stark: #39404b; --akzent: #8fb4e8;
  --ok: #5fcf95; --warn: #e0a458; --fehler: #f2857c;
  --schatten: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.6);
}
:root[data-theme="light"] {
  --bg: #f6f6f4; --bg-karte: #ffffff; --bg-gedaempft: #eeedea;
  --text: #16181d; --text-gedaempft: #5c6270; --text-schwach: #868d9b;
  --rand: #e0dfdb; --rand-stark: #cbcac5; --akzent: #1b3a6b;
  --ok: #197a4b; --warn: #a8570b; --fehler: #b3261e;
  --schatten: 0 1px 2px rgba(16,18,23,.05), 0 8px 24px -12px rgba(16,18,23,.16);
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
  font-size: 16px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.huelle { max-width: 1240px; margin: 0 auto; padding: 0 20px 72px; }
a { color: inherit; }
:focus-visible { outline: 2px solid var(--akzent); outline-offset: 2px; border-radius: 4px; }

/* ---------- Kopfbereich ---------- */
.kopf { padding: 40px 0 24px; border-bottom: 3px double var(--rand-stark); margin-bottom: 28px; }
.kopf__marke {
  font-family: var(--mono); font-size: .72rem; letter-spacing: .16em;
  text-transform: uppercase; color: var(--text-schwach); margin: 0 0 12px;
}
.kopf__titel {
  font-family: var(--serif); font-weight: 600; font-size: clamp(2rem, 5vw, 3.1rem);
  line-height: 1.08; letter-spacing: -.02em; margin: 0 0 10px;
}
.kopf__datum { font-size: 1.02rem; color: var(--text-gedaempft); margin: 0 0 22px; }
.kennzahlen { display: flex; flex-wrap: wrap; gap: 10px; }
.kennzahl {
  background: var(--bg-karte); border: 1px solid var(--rand); border-radius: 999px;
  padding: 7px 15px; display: flex; align-items: baseline; gap: 7px; box-shadow: var(--schatten);
}
.kennzahl__wert { font-variant-numeric: tabular-nums; font-weight: 650; font-size: 1.02rem; }
.kennzahl__label { font-size: .8rem; color: var(--text-gedaempft); }

/* ---------- Werkzeugleiste ---------- */
.werkzeuge {
  position: sticky; top: 0; z-index: 20; display: flex; flex-wrap: wrap; gap: 10px;
  align-items: center; padding: 12px 0; margin-bottom: 26px;
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: blur(8px); border-bottom: 1px solid var(--rand);
}
.suche {
  flex: 1 1 260px; min-width: 0; padding: 10px 14px; font: inherit; font-size: .92rem;
  color: var(--text); background: var(--bg-karte);
  border: 1px solid var(--rand-stark); border-radius: 10px;
}
.suche::placeholder { color: var(--text-schwach); }
.knopf {
  padding: 10px 14px; font: inherit; font-size: .88rem; font-weight: 550; cursor: pointer;
  color: var(--text); background: var(--bg-karte);
  border: 1px solid var(--rand-stark); border-radius: 10px; white-space: nowrap;
}
.knopf:hover { border-color: var(--akzent); color: var(--akzent); }
.treffer { font-size: .84rem; color: var(--text-gedaempft); font-variant-numeric: tabular-nums; }

/* ---------- Rubriken & Raster ---------- */
.rubrik { margin: 0 0 34px; }
.rubrik__titel {
  display: flex; align-items: center; gap: 12px; margin: 0 0 16px;
  font-family: var(--mono); font-size: .74rem; letter-spacing: .16em;
  text-transform: uppercase; color: var(--text-schwach); font-weight: 500;
}
.rubrik__titel::after { content: ""; flex: 1; height: 1px; background: var(--rand); }
.raster { display: grid; gap: 18px; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); }

/* ---------- Quellenkarte ---------- */
.karte {
  background: var(--bg-karte); border: 1px solid var(--rand); border-radius: var(--radius);
  box-shadow: var(--schatten); overflow: hidden; display: flex; flex-direction: column;
  border-top: 3px solid var(--quellfarbe, var(--akzent));
}
.karte--leer { opacity: .85; }
.karte__kopf {
  display: flex; align-items: center; gap: 10px; padding: 14px 18px 12px;
  border-bottom: 1px solid var(--rand);
}
.karte__name { font-family: var(--serif); font-size: 1.16rem; font-weight: 650; margin: 0; letter-spacing: -.01em; }
.karte__name a { text-decoration: none; }
.karte__name a:hover { color: var(--quellfarbe, var(--akzent)); }
.karte__anzahl {
  margin-left: auto; font-variant-numeric: tabular-nums; font-size: .76rem; font-weight: 600;
  color: var(--text-gedaempft); background: var(--bg-gedaempft);
  border-radius: 999px; padding: 3px 10px; white-space: nowrap;
}
.karte__punkt { width: 9px; height: 9px; border-radius: 50%; background: var(--quellfarbe, var(--akzent)); flex: none; }

.liste { list-style: none; margin: 0; padding: 4px 0; }
.zeile { border-bottom: 1px solid var(--rand); }
.zeile:last-child { border-bottom: 0; }

/* Rang 1–5 für die offen sichtbaren Schlagzeilen */
.liste--haupt { counter-reset: rang; }
.liste--haupt > .zeile { position: relative; counter-increment: rang; }
.liste--haupt > .zeile > a { padding-left: 44px; }
.liste--haupt > .zeile > a::before {
  content: counter(rang);
  position: absolute; left: 18px; top: 12px;
  font-family: var(--mono); font-size: .76rem; font-weight: 650;
  color: var(--quellfarbe, var(--akzent)); opacity: .65;
}
.zeile a {
  display: block; padding: 11px 18px; text-decoration: none; color: inherit;
  transition: background .12s ease;
}
.zeile a:hover { background: var(--bg-gedaempft); }
.zeile__titel { font-size: .945rem; line-height: 1.42; font-weight: 500; }
.zeile__original {
  display: block; margin-top: 4px; font-size: .82rem; line-height: 1.4;
  color: var(--text-schwach); font-style: italic;
}
.zeile__meta {
  display: flex; gap: 8px; align-items: center; margin-top: 5px;
  font-size: .74rem; color: var(--text-schwach); font-variant-numeric: tabular-nums;
}
.marke {
  font-family: var(--mono); font-size: .64rem; letter-spacing: .06em; text-transform: uppercase;
  border: 1px solid var(--rand-stark); border-radius: 4px; padding: 1px 5px; color: var(--text-schwach);
}

/* ---------- Aufklapper ---------- */
.mehr { border-top: 1px solid var(--rand); }
.mehr > summary {
  cursor: pointer; list-style: none; padding: 11px 18px;
  font-size: .84rem; font-weight: 600; color: var(--akzent);
  display: flex; align-items: center; gap: 8px; user-select: none;
}
.mehr > summary::-webkit-details-marker { display: none; }
.mehr > summary:hover { background: var(--bg-gedaempft); }
.mehr > summary::before {
  content: "▸"; font-size: .8em; transition: transform .15s ease; display: inline-block;
}
.mehr[open] > summary::before { transform: rotate(90deg); }
.mehr[open] > summary { border-bottom: 1px solid var(--rand); }
.mehr__zu { display: none; }
.mehr[open] > summary .mehr__auf { display: none; }
.mehr[open] > summary .mehr__zu { display: inline; }
.mehr .liste { max-height: 30rem; overflow-y: auto; overscroll-behavior: contain; }

/* ---------- Hervorgehobene Quelle (FT) ---------- */
.gross { grid-column: 1 / -1; }
.gross .karte__name { font-size: 1.5rem; }
.gross .liste { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.gross .mehr .liste { max-height: 34rem; }
.gross .liste > .zeile:nth-child(odd) { border-right: 1px solid var(--rand); }
@media (max-width: 720px) {
  .gross .liste { grid-template-columns: 1fr; }
  .gross .liste > .zeile:nth-child(odd) { border-right: 0; }
}
.hinweis {
  padding: 10px 18px; font-size: .82rem; color: var(--text-gedaempft);
  background: var(--bg-gedaempft); border-bottom: 1px solid var(--rand);
}

/* ---------- Fehler / Status ---------- */
.fehlerbox {
  margin: 0; padding: 14px 18px; font-size: .87rem; color: var(--fehler);
  background: color-mix(in srgb, var(--fehler) 8%, transparent);
  border-bottom: 1px solid var(--rand);
}
.fehlerbox code { font-family: var(--mono); font-size: .8em; word-break: break-all; }
.status { margin-top: 44px; }
.status__tabelle { width: 100%; border-collapse: collapse; font-size: .82rem; }
.status__tabelle th, .status__tabelle td {
  text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--rand); vertical-align: top;
}
.status__tabelle th { font-weight: 600; color: var(--text-gedaempft); font-size: .74rem;
  text-transform: uppercase; letter-spacing: .08em; }
.status__tabelle td.url { font-family: var(--mono); font-size: .76rem; word-break: break-all; color: var(--text-gedaempft); }
.pille { font-size: .72rem; font-weight: 650; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.pille--ok { color: var(--ok); background: color-mix(in srgb, var(--ok) 12%, transparent); }
.pille--fehler { color: var(--fehler); background: color-mix(in srgb, var(--fehler) 12%, transparent); }
.fuss { margin-top: 28px; padding-top: 18px; border-top: 1px solid var(--rand);
  font-size: .8rem; color: var(--text-schwach); }

.demo {
  margin: 18px 0 0; padding: 12px 16px; border-radius: 10px; font-size: .88rem;
  color: var(--warn); background: color-mix(in srgb, var(--warn) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--warn) 35%, transparent);
}
.versteckt { display: none !important; }

/* ---------- Archiv ---------- */
.archiv { margin-top: 40px; }
.archiv__liste { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px; }
.archiv__liste a {
  display: block; padding: 8px 14px; font-size: .86rem; text-decoration: none;
  background: var(--bg-karte); border: 1px solid var(--rand); border-radius: 999px;
}
.archiv__liste a:hover { border-color: var(--akzent); color: var(--akzent); }

/* ---------- Zurück nach oben (vor allem am Handy nützlich) ---------- */
.nach-oben {
  position: fixed; right: 16px; bottom: 16px; z-index: 30;
  width: 46px; height: 46px; border-radius: 50%; cursor: pointer;
  display: grid; place-items: center; font-size: 1.1rem;
  color: var(--text); background: var(--bg-karte);
  border: 1px solid var(--rand-stark); box-shadow: var(--schatten);
  opacity: 0; visibility: hidden; transition: opacity .18s ease;
}
.nach-oben.sichtbar { opacity: .96; visibility: visible; }

@media (max-width: 560px) {
  .huelle { padding: 0 14px 56px; }
  .gross .karte__name { font-size: 1.2rem; }
  .karte__kopf { flex-wrap: wrap; row-gap: 6px; }
  .kennzahl { padding: 6px 12px; }
  /* Am Handy nicht kleben: die Leiste würde sonst ein Viertel des Bildschirms
     belegen und den Inhalt überdecken. Nach oben führt der runde Knopf. */
  .werkzeuge { position: static; backdrop-filter: none; padding: 10px 0 14px; }
  .suche { flex: 1 1 100%; }
  .knopf { flex: 1 1 0; text-align: center; }
  .knopf--drucken { display: none; }
  .kopf { padding: 28px 0 20px; }
}

@media print {
  .werkzeuge, .status { display: none; }
  body { background: #fff; font-size: 11pt; }
  .karte { break-inside: avoid; box-shadow: none; }
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
    if (e.key === '/' && document.activeElement !== suche) { e.preventDefault(); suche.focus(); }
  });
})();
"""


def _datum_lang(zeitpunkt: datetime) -> str:
    return (
        f"{WOCHENTAGE[zeitpunkt.weekday()]}, {zeitpunkt.day}. "
        f"{MONATE[zeitpunkt.month - 1]} {zeitpunkt.year}"
    )


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


def _zeile(schlagzeile, quelle, jetzt: datetime) -> str:
    """Eine Schlagzeile — bei Übersetzung steht Deutsch oben, Original darunter."""
    hat_uebersetzung = bool(schlagzeile.uebersetzung)
    haupttext = schlagzeile.uebersetzung if hat_uebersetzung else schlagzeile.titel

    original = ""
    if hat_uebersetzung:
        original = f'<span class="zeile__original">{escape(schlagzeile.titel)}</span>'

    teile: list[str] = []
    if schlagzeile.veroeffentlicht:
        lokal = schlagzeile.veroeffentlicht.astimezone(jetzt.tzinfo)
        teile.append(
            f'<time datetime="{escape(lokal.isoformat())}">{lokal:%H:%M}</time>'
        )
        relativ = _relative_zeit(schlagzeile.veroeffentlicht, jetzt)
        if relativ:
            teile.append(f"<span>{escape(relativ)}</span>")
    if hat_uebersetzung:
        teile.append('<span class="marke">übersetzt</span>')
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
    teile = [
        f'<article class="karte{gross}{leer}" style="--quellfarbe: {escape(quelle.farbe, quote=True)}">',
        '<header class="karte__kopf">',
        '<span class="karte__punkt" aria-hidden="true"></span>',
        f'<h3 class="karte__name">{kopf_name}</h3>',
        f'<span class="karte__anzahl">{len(schlagzeilen)} Schlagzeilen</span>',
        "</header>",
    ]

    if quelle.uebersetzen and schlagzeilen:
        teile.append(
            '<p class="hinweis">Alle Schlagzeilen auf Deutsch übersetzt — '
            "das englische Original steht jeweils darunter.</p>"
        )

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
            teile.append(
                '<details class="mehr">'
                "<summary>"
                f'<span class="mehr__auf">{len(rest)} weitere Schlagzeilen anzeigen</span>'
                f'<span class="mehr__zu">{len(rest)} weitere Schlagzeilen ausblenden</span>'
                "</summary>"
                f'<ol class="liste">{weitere}</ol>'
                "</details>"
            )

    teile.append("</article>")
    return "".join(teile)


def _statusabschnitt(ergebnisse: dict, quellen: list, uebersetzung_hinweis: str) -> str:
    zeilen = []
    for quelle in quellen:
        ergebnis = ergebnisse.get(quelle.id)
        if ergebnis is None:
            continue
        for status in ergebnis.status:
            pille = (
                '<span class="pille pille--ok">OK</span>'
                if status.ok
                else '<span class="pille pille--fehler">Fehler</span>'
            )
            zeilen.append(
                "<tr>"
                f"<td>{escape(quelle.name)}</td>"
                f'<td class="url">{escape(status.url)}</td>'
                f"<td>{pille}</td>"
                f"<td>{escape(status.format)}</td>"
                f"<td>{status.anzahl}</td>"
                f"<td>{status.dauer_ms} ms</td>"
                f"<td>{escape(status.fehler)}</td>"
                "</tr>"
            )
    hinweis = (
        f'<p class="fuss">{escape(uebersetzung_hinweis)}</p>' if uebersetzung_hinweis else ""
    )
    return (
        '<section class="status">'
        '<h2 class="rubrik__titel">Feed-Status</h2>'
        '<table class="status__tabelle">'
        "<thead><tr><th>Quelle</th><th>Feed</th><th>Status</th><th>Format</th>"
        "<th>Einträge</th><th>Dauer</th><th>Hinweis</th></tr></thead>"
        f"<tbody>{''.join(zeilen)}</tbody></table>{hinweis}</section>"
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
        '<section class="archiv"><h2 class="rubrik__titel">Frühere Ausgaben</h2>'
        f'<ul class="archiv__liste">{eintraege}</ul></section>'
    )


def rendere_briefing(
    konfiguration,
    ergebnisse: dict,
    jetzt: datetime,
    uebersetzung_hinweis: str = "",
    demo: bool = False,
    web: bool = False,
    archiv: list[date] | None = None,
) -> str:
    """Baut die vollständige HTML-Seite.

    ``web=True`` ergänzt Manifest, Symbole und Service-Worker-Registrierung,
    damit die Seite am Handy als App auf den Startbildschirm gelegt werden kann.
    """
    quellen = konfiguration.quellen
    gesamt = sum(len(e.schlagzeilen) for e in ergebnisse.values())
    uebersetzt = sum(
        1
        for e in ergebnisse.values()
        for s in e.schlagzeilen
        if s.uebersetzung
    )
    quellen_ok = sum(1 for q in quellen if ergebnisse.get(q.id) and ergebnisse[q.id].ok)

    # Hervorgehobene Quellen (FT) zuerst, danach nach Rubrik gruppiert.
    abschnitte: list[str] = []
    hervorgehoben = [q for q in quellen if q.hervorheben and q.id in ergebnisse]
    if hervorgehoben:
        karten = "".join(
            _karte(ergebnisse[q.id], q, jetzt, konfiguration.sichtbare_schlagzeilen)
            for q in hervorgehoben
        )
        abschnitte.append(
            '<section class="rubrik"><h2 class="rubrik__titel">Im Fokus</h2>'
            f'<div class="raster">{karten}</div></section>'
        )

    rubriken: dict[str, list] = {}
    for quelle in quellen:
        if quelle.hervorheben:
            continue
        rubriken.setdefault(quelle.kategorie, []).append(quelle)

    for kategorie, quellen_der_rubrik in rubriken.items():
        karten = "".join(
            _karte(ergebnisse[q.id], q, jetzt, konfiguration.sichtbare_schlagzeilen)
            for q in quellen_der_rubrik
            if q.id in ergebnisse
        )
        if not karten:
            continue
        abschnitte.append(
            f'<section class="rubrik"><h2 class="rubrik__titel">{escape(kategorie)}</h2>'
            f'<div class="raster">{karten}</div></section>'
        )

    demo_banner = (
        '<p class="demo"><strong>Vorschau mit Beispieldaten.</strong> '
        "Diese Seite wurde mit erfundenen Schlagzeilen erzeugt, um das Layout zu "
        "zeigen — sie enthält keine echten Nachrichten.</p>"
        if demo
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
<div class="huelle">
<header class="kopf">
  <p class="kopf__marke">Nachrichten-Briefing</p>
  <h1 class="kopf__titel">{escape(konfiguration.titel)}</h1>
  <p class="kopf__datum">{escape(_datum_lang(jetzt))} · Stand {jetzt:%H:%M} Uhr
     {escape(f"({konfiguration.zeitzone})")}</p>
  <div class="kennzahlen">
    <span class="kennzahl"><span class="kennzahl__wert">{gesamt}</span><span class="kennzahl__label">Schlagzeilen</span></span>
    <span class="kennzahl"><span class="kennzahl__wert">{quellen_ok}/{len(quellen)}</span><span class="kennzahl__label">Quellen abgerufen</span></span>
    <span class="kennzahl"><span class="kennzahl__wert">{uebersetzt}</span><span class="kennzahl__label">übersetzt</span></span>
    <span class="kennzahl"><span class="kennzahl__wert">{konfiguration.sichtbare_schlagzeilen}</span><span class="kennzahl__label">je Quelle sichtbar</span></span>
  </div>
  {demo_banner}
</header>

<div class="werkzeuge">
  <input id="suche" class="suche" type="search" placeholder="Schlagzeilen durchsuchen … (Taste /)" aria-label="Schlagzeilen durchsuchen">
  <span id="treffer" class="treffer" role="status"></span>
  <button id="alle" class="knopf" type="button">Alle aufklappen</button>
  <button id="theme" class="knopf" type="button">Hell / Dunkel</button>
  <button class="knopf knopf--drucken" type="button" onclick="window.print()">Drucken</button>
</div>

{"".join(abschnitte)}
{_archivabschnitt(archiv or [])}
{_statusabschnitt(ergebnisse, quellen, uebersetzung_hinweis)}
<p class="fuss">Erzeugt am {jetzt:%d.%m.%Y um %H:%M} Uhr · Es werden je Quelle die
{konfiguration.sichtbare_schlagzeilen} aktuellsten Schlagzeilen angezeigt, alle weiteren
stehen im Aufklapper.</p>
</div>
<button id="nachOben" class="nach-oben" type="button" aria-label="Nach oben">↑</button>
<script>{JS}
{app_skript}</script>
</body>
</html>
"""
