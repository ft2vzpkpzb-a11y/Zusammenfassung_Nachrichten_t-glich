#!/usr/bin/env python3
"""Tägliche Nachrichten-Zusammenfassung erzeugen.

Beispiele
---------
    python3 generate_briefing.py                     # Briefing für heute bauen
    python3 generate_briefing.py --demo              # Layout-Vorschau ohne Netz
    python3 generate_briefing.py --ohne-uebersetzung # FT im Original lassen
    python3 generate_briefing.py --out briefing.html
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from briefing import pwa
from briefing.demo import demo_ergebnis
from briefing.feeds import Quelle, lade_konfiguration
from briefing.fetch import hole_quelle
from briefing.render import rendere_briefing
from briefing.translate import uebersetze_schlagzeilen

WURZEL = Path(__file__).resolve().parent
OHNE_LIMIT = 10_000


def argumente() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tägliche Nachrichten-Zusammenfassung")
    parser.add_argument(
        "--config", default=str(WURZEL / "config" / "feeds.json"), help="Pfad zur Feed-Konfiguration"
    )
    parser.add_argument("--out", default="", help="Zieldatei (Standard: out/briefing-JJJJ-MM-TT.html)")
    parser.add_argument("--sichtbar", type=int, default=0, help="Sichtbare Schlagzeilen je Quelle")
    parser.add_argument("--timeout", type=int, default=20, help="Timeout je Feed in Sekunden")
    parser.add_argument("--ohne-uebersetzung", action="store_true", help="Keine Übersetzung anfordern")
    parser.add_argument("--demo", action="store_true", help="Beispieldaten statt echter Feeds")
    parser.add_argument("--quelle", action="append", default=[], help="Nur diese Quellen-ID(s) verwenden")
    parser.add_argument(
        "--site",
        default="",
        help="Website-Verzeichnis bauen (index.html, archiv/, App-Dateien) — z. B. --site docs",
    )
    parser.add_argument(
        "--archiv-tage", type=int, default=30, help="Wie viele frühere Ausgaben behalten (Standard 30)"
    )
    parser.add_argument(
        "--ohne-rubrikfilter",
        action="store_true",
        help="Alle Ressorts übernehmen statt nur Politik und Wirtschaft",
    )
    parser.add_argument(
        "--pruefe",
        action="store_true",
        help="Nur prüfen: jeden Feed abrufen und melden, was ankommt (kein Briefing bauen)",
    )
    return parser.parse_args()


def pruefe_feeds(konfiguration, timeout: int) -> int:
    """Jeden Feed einzeln abrufen und zeigen, was ankommt.

    Gedacht zum Nachschärfen der Konfiguration: welche Adressen antworten,
    welches Format sie liefern, welche Ressorts darin vorkommen und wie viel
    davon der Rubrikfilter übrig lässt.
    """
    probleme = 0
    for quelle in konfiguration.quellen:
        filter_an = konfiguration.rubrikfilter.aktiv and quelle.rubriken_filtern
        print(f"\n{quelle.name}  ({'Rubrikfilter an' if filter_an else 'ohne Rubrikfilter'})")
        if quelle.hinweis:
            print(f"  Hinweis: {quelle.hinweis}")

        for adresse in quelle.feeds:
            einzeln = Quelle(
                id=quelle.id,
                name=quelle.name,
                feeds=[adresse],
                rubriken_filtern=quelle.rubriken_filtern,
            )
            ergebnis = hole_quelle(
                einzeln,
                max_schlagzeilen=OHNE_LIMIT,
                timeout=timeout,
                rubrikfilter=konfiguration.rubrikfilter,
            )
            status = ergebnis.status[0]
            marke = "ok  " if status.ok else "FEHL"
            if not status.ok:
                probleme += 1
                print(f"  [{marke}] {adresse.url}")
                print(f"         {status.fehler}")
                if adresse.alternativen:
                    print(f"         auch ohne Erfolg: {', '.join(adresse.alternativen)}")
                continue

            print(f"  [{marke}] {status.url}")
            if status.url != adresse.url:
                print(f"         (Ausweichadresse — {adresse.url} ging nicht)")

            gesamt = status.anzahl + status.gefiltert
            print(
                f"         {status.format} · {gesamt} Einträge · "
                f"{status.anzahl} nach Filter · {status.dauer_ms} ms"
            )
            if status.rubriken:
                print(f"         Ressorts im Feed: {', '.join(status.rubriken)}")
            elif filter_an:
                print("         Ressorts im Feed: keine Angabe — es zählt der Link-Pfad")
            if ergebnis.schlagzeilen:
                print(f"         Beispiel: „{ergebnis.schlagzeilen[0].titel[:70]}“")
            elif filter_an:
                probleme += 1
                print("         Nichts aus Politik/Wirtschaft — Erlaubt-Liste prüfen")

    print(
        "\nAlles in Ordnung." if not probleme else f"\n{probleme} Feed(s) mit Auffälligkeiten."
    )
    return 0 if not probleme else 1


def baue_website(
    verzeichnis: Path, html_bauen, jetzt: datetime, titel: str, archiv_tage: int
) -> Path:
    """Schreibt index.html, die Tagesausgabe ins Archiv und die App-Dateien."""
    archiv_ordner = verzeichnis / "archiv"
    archiv_ordner.mkdir(parents=True, exist_ok=True)

    # Vorhandene Ausgaben einsammeln (ohne die von heute) und alte wegräumen.
    vorhanden: list[date] = []
    for datei in archiv_ordner.glob("*.html"):
        try:
            tag = date.fromisoformat(datei.stem)
        except ValueError:
            continue
        if tag == jetzt.date():
            continue
        if (jetzt.date() - tag).days > archiv_tage:
            datei.unlink()
            continue
        vorhanden.append(tag)
    vorhanden.sort(reverse=True)

    html = html_bauen(vorhanden)
    (verzeichnis / "index.html").write_text(html, encoding="utf-8")
    (archiv_ordner / f"{jetzt:%Y-%m-%d}.html").write_text(html, encoding="utf-8")
    (verzeichnis / ".nojekyll").write_text("", encoding="utf-8")
    pwa.schreibe_dateien(verzeichnis, titel)
    return verzeichnis / "index.html"


def main() -> int:
    args = argumente()
    konfiguration = lade_konfiguration(args.config)
    if args.sichtbar:
        konfiguration.sichtbare_schlagzeilen = args.sichtbar
    if args.quelle:
        gewuenscht = set(args.quelle)
        konfiguration.quellen = [q for q in konfiguration.quellen if q.id in gewuenscht]
        if not konfiguration.quellen:
            print(f"Keine Quelle passt zu {sorted(gewuenscht)}", file=sys.stderr)
            return 2

    if args.ohne_rubrikfilter:
        konfiguration.rubrikfilter.aktiv = False

    if args.pruefe:
        return pruefe_feeds(konfiguration, args.timeout)

    jetzt = datetime.now(ZoneInfo(konfiguration.zeitzone))

    # --- Feeds holen (parallel: ein langsamer Feed bremst die anderen nicht) ---
    ergebnisse: dict = {}
    if args.demo:
        for quelle in konfiguration.quellen:
            ergebnisse[quelle.id] = demo_ergebnis(quelle, jetzt)
    else:
        def abrufen(quelle):
            grenze = (
                OHNE_LIMIT if quelle.alle_anzeigen else konfiguration.max_schlagzeilen_pro_quelle
            )
            return quelle.id, hole_quelle(
                quelle,
                max_schlagzeilen=grenze,
                timeout=args.timeout,
                rubrikfilter=konfiguration.rubrikfilter,
            )

        with ThreadPoolExecutor(max_workers=min(8, len(konfiguration.quellen))) as pool:
            for quelle_id, ergebnis in pool.map(abrufen, konfiguration.quellen):
                ergebnisse[quelle_id] = ergebnis

    # --- Übersetzen (Standard: Financial Times) ---
    hinweis = ""
    if args.demo:
        hinweis = "Beispieldaten — die „Übersetzungen“ sind Platzhalter."
    elif konfiguration.uebersetzung.aktiv and not args.ohne_uebersetzung:
        zu_uebersetzen = []
        for quelle in konfiguration.quellen:
            quellenergebnis = ergebnisse.get(quelle.id)
            if quelle.uebersetzen and quellenergebnis:
                zu_uebersetzen.extend(quellenergebnis.schlagzeilen)

        if zu_uebersetzen:
            uebersetzung = uebersetze_schlagzeilen(
                zu_uebersetzen,
                modell=konfiguration.uebersetzung.modell,
                zielsprache=konfiguration.uebersetzung.zielsprache,
                batch_groesse=konfiguration.uebersetzung.batch_groesse,
                cache_datei=WURZEL / konfiguration.uebersetzung.cache_datei,
            )
            hinweis = (
                f"Übersetzung: {uebersetzung.anzahl_uebersetzt} neu via "
                f"{konfiguration.uebersetzung.modell}, "
                f"{uebersetzung.anzahl_aus_cache} aus dem Cache."
            )
            if uebersetzung.fehler:
                hinweis += f" {uebersetzung.fehler}"
                print(f"Warnung: {uebersetzung.fehler}", file=sys.stderr)
    elif args.ohne_uebersetzung:
        hinweis = "Übersetzung per --ohne-uebersetzung deaktiviert."

    # --- Rendern ---
    if args.site:
        def html_bauen(archiv: list[date]) -> str:
            return rendere_briefing(
                konfiguration, ergebnisse, jetzt, hinweis, demo=args.demo, web=True, archiv=archiv
            )

        ziel = baue_website(
            Path(args.site), html_bauen, jetzt, konfiguration.titel, args.archiv_tage
        )
    else:
        html = rendere_briefing(konfiguration, ergebnisse, jetzt, hinweis, demo=args.demo)
        ziel = Path(args.out) if args.out else WURZEL / "out" / f"briefing-{jetzt:%Y-%m-%d}.html"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(html, encoding="utf-8")

    # --- Kurzbericht fürs Log (macht stille Ausfälle im Cron sichtbar) ---
    gesamt = 0
    probleme: list[str] = []
    for quelle in konfiguration.quellen:
        ergebnis = ergebnisse.get(quelle.id)
        if ergebnis is None:
            continue
        anzahl = len(ergebnis.schlagzeilen)
        gesamt += anzahl
        markierung = "ok  " if ergebnis.ok and anzahl else "FEHL"
        aussortiert = sum(s.gefiltert for s in ergebnis.status)
        zusatz = f"  ({aussortiert} andere Ressorts aussortiert)" if aussortiert else ""
        print(f"[{markierung}] {quelle.name:<24} {anzahl:>4} Schlagzeilen{zusatz}")
        if not (ergebnis.ok and anzahl):
            probleme.extend(f"    {quelle.name}: {m}" for m in ergebnis.fehlermeldungen)

    for zeile in probleme:
        print(zeile, file=sys.stderr)
    print(f"\n{gesamt} Schlagzeilen → {ziel}")

    if gesamt == 0:
        print("Keine einzige Schlagzeile abgerufen.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
