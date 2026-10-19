"""Gesetzesbeschlüsse des Nationalrates über die Open-Data-Schnittstelle.

Jeder Gesetzesbeschluss des Nationalrates wird als eigener Gegenstand
„Beschluss des Nationalrates“ (``BNR``) geführt und an den Bundesrat
weitergeleitet. Die Filter-API des Parlaments liefert alle davon in einer
einzigen Antwort (Spalten im ``header``, Werte in ``rows``); das Datum ist der
Tag des Beschlusses im Plenum.

Für jeden Beschluss im Zeitraum gibt es zwei Ergänzungen, beide optional:

* die Detailseite des Beschlusses (``?json=true``) — Volltext des Gegenstands
  und der Verweis auf die ursprüngliche Vorlage,
* die Detailseite dieser Vorlage — Abstimmungsverhalten der Fraktionen und die
  Schlagzeile der Parlamentskorrespondenz zur Plenarsitzung.

Fehlt eine Ergänzung, erscheint der Beschluss trotzdem — nur knapper.
Daten: Parlament Österreich, Lizenz CC BY 4.0.
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

from .fetch import FeedStatus, hole_daten
from .gesetzgebung import Beschluss, Gesetzgebungsergebnis, Partei, sortiere, zeitraum

BASIS = "https://www.parlament.gv.at"
FILTER_URL = f"{BASIS}/Filter/api/filter/data/101?js=eval&showAll=true"
WEBSEITE = f"{BASIS}/recherchieren/gegenstaende/?NRBR=NR&VHG=BNR&DOKTYP=BNR"

STAATSVERTRAG = re.compile(r"\b(Abkommen|Protokoll|Übereinkommen|Vertrag|Konvention)\b")
BETREFFEND = re.compile(r"^Beschluss des Nationalrates vom .*? betreffend\s+", re.S)


def _datum(text) -> date | None:
    try:
        return datetime.strptime(str(text).strip(), "%d.%m.%Y").date()
    except (TypeError, ValueError):
        return None


def _liste(wert) -> list[str]:
    """Spalten wie THEMEN kommen als JSON-Text: ``'["Bildung"]'``."""
    if isinstance(wert, list):
        return [str(w) for w in wert if w]
    try:
        daten = json.loads(wert) if wert else []
    except (TypeError, ValueError):
        return []
    return [str(w) for w in daten if w] if isinstance(daten, list) else []


def zeilen(antwort: dict) -> list[dict]:
    """Zeilen der Filter-API als Dicts — über die Spaltennamen, nicht die Position."""
    namen = [spalte.get("label") for spalte in antwort.get("header", [])]
    return [dict(zip(namen, zeile)) for zeile in antwort.get("rows", [])]


def parse_liste(antwort: dict) -> list[Beschluss]:
    """Alle Gesetzesbeschlüsse (``BNR``) der Antwort, neueste zuerst.

    „Sonstige Beschlüsse“ (``BS``, etwa zur Kenntnis genommene Berichte)
    kommen in derselben Liste mit, sind aber keine Gesetze und fallen weg.
    """
    beschluesse = []
    for zeile in zeilen(antwort):
        if zeile.get("ITYP") != "BNR":
            continue
        datum = _datum(zeile.get("Datum"))
        titel = " ".join(str(zeile.get("Betreff") or "").split())
        if datum is None or not titel:
            continue
        pfad = zeile.get("HIS_URL") or ""
        beschluesse.append(
            Beschluss(
                datum=datum,
                titel=titel,
                link=f"{BASIS}{pfad}" if pfad.startswith("/") else pfad,
                nummer=str(zeile.get("Nummer") or ""),
                gremium="Nationalrat",
                ergebnis="beschlossen",
                art="Staatsvertrag" if STAATSVERTRAG.search(titel) else "",
                themen=_liste(zeile.get("THEMEN")),
            )
        )
    return sortiere(beschluesse)


def ergaenze_detail(beschluss: Beschluss, detail: dict) -> str:
    """Gegenstandstext übernehmen; gibt die Adresse der Ursprungsvorlage zurück."""
    inhalt = detail.get("content") or {}
    beschreibung = " ".join(str(inhalt.get("description") or "").split())
    if beschreibung:
        gegenstand = BETREFFEND.sub("", beschreibung)
        beschluss.erlaeuterung = gegenstand[:1].upper() + gegenstand[1:]
        if "Bundesverfassungsgesetz" in beschreibung:
            beschluss.art = "Verfassungsgesetz"
        elif "Bundesgesetz" in beschreibung:
            beschluss.art = "Bundesgesetz"

    for verweis in inhalt.get("reference") or []:
        pfad = str(verweis.get("url") or "")
        if pfad.startswith("/gegenstand/"):
            return f"{BASIS}{pfad}?json=true"
    return ""


def _korrespondenz_zur_plenarsitzung(inhalt: dict) -> str:
    """Schlagzeile der Parlamentskorrespondenz zum Beschluss im Plenum."""
    for phase in inhalt.get("phase") or []:
        if not str(phase.get("name", "")).startswith("Plenarberatungen NR"):
            continue
        meldungen = [m for m in phase.get("correspondence") or [] if m.get("title")]
        if meldungen:
            neueste = max(meldungen, key=lambda m: _datum(m.get("date")) or date.min)
            return " ".join(str(neueste["title"]).split())
    return ""


def ergaenze_bezug(beschluss: Beschluss, bezug: dict) -> None:
    """Abstimmungsverhalten und Korrespondenz-Schlagzeile aus der Vorlage."""
    inhalt = bezug.get("content") or {}
    abstimmung = inhalt.get("vote") or {}
    beschluss.parteien = [
        Partei(
            name=str(fraktion.get("text") or fraktion.get("code") or "?"),
            farbe=str(fraktion.get("color") or ""),
            dafuer=bool(fraktion.get("infavor")),
        )
        for fraktion in abstimmung.get("result") or []
    ]
    schlagzeile = _korrespondenz_zur_plenarsitzung(inhalt)
    if schlagzeile:
        beschluss.erlaeuterung = schlagzeile


def _anreichern(beschluss: Beschluss, timeout: int) -> None:
    try:
        detail = json.loads(hole_daten(f"{beschluss.link}?json=true", timeout=timeout, versuche=2))
        bezug_url = ergaenze_detail(beschluss, detail)
        if bezug_url:
            ergaenze_bezug(
                beschluss, json.loads(hole_daten(bezug_url, timeout=timeout, versuche=2))
            )
    except Exception:
        pass  # Ohne Details bleibt der Beschluss mit Titel, Datum und Link stehen.


def hole_beschluesse(
    heute: date, tage: int = 7, perioden: list[str] | None = None, timeout: int = 20
) -> Gesetzgebungsergebnis:
    ergebnis = Gesetzgebungsergebnis(id="nationalrat", name="Nationalrat", webseite=WEBSEITE)
    perioden = perioden or ["XXVIII", "XXIX"]
    start = time.monotonic()
    try:
        antwort = json.loads(
            hole_daten(
                FILTER_URL,
                {"NRBR": ["NR"], "GP_CODE": perioden, "VHG": ["BNR"]},
                timeout=timeout,
            )
        )
        alle = parse_liste(antwort)
    except Exception as fehler:
        ergebnis.status.append(
            FeedStatus(
                url=FILTER_URL, quelle_id="nationalrat", ok=False, format="Open Data (JSON)",
                fehler=str(fehler), dauer_ms=int((time.monotonic() - start) * 1000),
            )
        )
        return ergebnis

    von, bis = zeitraum(heute, tage)
    ergebnis.zuletzt = alle[0].datum if alle else None
    ergebnis.beschluesse = [b for b in alle if von <= b.datum <= bis]
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda b: _anreichern(b, timeout), ergebnis.beschluesse))

    ergebnis.status.append(
        FeedStatus(
            url=FILTER_URL,
            quelle_id="nationalrat",
            ok=bool(alle),
            anzahl=len(ergebnis.beschluesse),
            format="Open Data (JSON)",
            fehler="" if alle else "Antwort ohne Gesetzesbeschlüsse",
            dauer_ms=int((time.monotonic() - start) * 1000),
        )
    )
    return ergebnis
