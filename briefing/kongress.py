"""Entscheidungen des US-Kongresses: Abstimmungen und neue Gesetze.

Drei Quellen, je nach Art der Entscheidung:

* **Senat** — eine XML-Liste aller namentlichen Abstimmungen der laufenden
  Sitzungsperiode (senate.gov, ohne Schlüssel).
* **Repräsentantenhaus** — je Abstimmung eine XML-Datei beim Clerk
  (clerk.house.gov, ohne Schlüssel). Eine Übersicht gibt es dort nicht; die
  jüngste Nummer wird gesucht und im Cache gemerkt.
* **Neue Gesetze** — api.congress.gov. Ohne eigenen Schlüssel (Secret
  ``CONGRESS_API_KEY``) wird der öffentliche ``DEMO_KEY`` verwendet, der nur
  wenige Abrufe pro Stunde erlaubt.

Übernommen werden nur Entscheidungen in der Sache — Verabschiedung von
Gesetzen und Resolutionen, Bestätigung von Nominierungen, Veto-Abstimmungen.
Verfahrensschritte (Cloture, Geschäftsordnungsanträge, Änderungsanträge)
fallen weg; sie machen in Sitzungswochen den Großteil der Abstimmungen aus.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
from datetime import date, datetime
from html import unescape
from pathlib import Path
from xml.etree import ElementTree as ET

from .fetch import FeedStatus, hole_daten
from .gesetzgebung import Beschluss, Gesetzgebungsergebnis, sortiere, zeitraum

SENAT_LISTE = "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_{kongress}_{sitzung}.xml"
SENAT_ABSTIMMUNG = (
    "https://www.senate.gov/legislative/LIS/roll_call_votes/"
    "vote{kongress}{sitzung}/vote_{kongress}_{sitzung}_{nummer:05d}.htm"
)
HOUSE_ABSTIMMUNG = "https://clerk.house.gov/evs/{jahr}/roll{nummer:03d}.xml"
HOUSE_SEITE = "https://clerk.house.gov/Votes/{jahr}{nummer}"
GESETZE_API = "https://api.congress.gov/v3/law/{kongress}?format=json&limit=100&api_key={schluessel}"
WEBSEITE = "https://www.congress.gov"

# Typ der Vorlage → (Schreibweise, Pfad auf congress.gov)
VORLAGEN = {
    "HR": ("H.R.", "house-bill"),
    "S": ("S.", "senate-bill"),
    "HRES": ("H.Res.", "house-resolution"),
    "SRES": ("S.Res.", "senate-resolution"),
    "HJRES": ("H.J.Res.", "house-joint-resolution"),
    "SJRES": ("S.J.Res.", "senate-joint-resolution"),
    "HCONRES": ("H.Con.Res.", "house-concurrent-resolution"),
    "SCONRES": ("S.Con.Res.", "senate-concurrent-resolution"),
}

SENAT_IN_DER_SACHE = re.compile(
    r"^On (Passage|the (Joint |Concurrent )?Resolution|the Conference Report|the Nomination"
    r"|the Resolution of Ratification|Overriding the Veto|the Motion to Concur|the Bill)",
    re.I,
)
HOUSE_IN_DER_SACHE = re.compile(
    r"^On (Passage|Motion to Suspend the Rules and (Pass|Agree|Concur)|Agreeing to the "
    r"(Resolution|Conference Report)|Motion to Concur|Concurring|Overriding the Veto)",
    re.I,
)
# Die Mehrheit beschließt vor jeder großen Debatte eine „Rule“ — reines Verfahren.
GESCHAEFTSORDNUNG = re.compile(r"^Providing for (the )?consideration", re.I)
ABGELEHNT = re.compile(r"reject|fail|not agreed|sustained|not confirmed", re.I)


def kongress_und_sitzung(jahr: int) -> tuple[int, int]:
    """2025 → (119, 1), 2026 → (119, 2). Ein Kongress dauert zwei Jahre."""
    return (jahr - 1789) // 2 + 1, 1 if jahr % 2 else 2


def _ordinal(zahl: int) -> str:
    """119 → „119th“ (so stehen Kongresse in den Adressen von congress.gov)."""
    endung = "th" if 10 <= zahl % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(zahl % 10, "th")
    return f"{zahl}{endung}"


def vorlage(text: str, kongress: int) -> tuple[str, str]:
    """„H R 1234“, „H.R. 1234“, „PN1129“ → (Schreibweise, Link auf congress.gov)."""
    treffer = re.match(r"^\s*([A-Za-z.\s]+?)\s*(\d+)\s*$", text or "")
    if not treffer:
        return (text or "").strip(), ""
    typ = re.sub(r"[^A-Za-z]", "", treffer.group(1)).upper()
    nummer = treffer.group(2)
    if typ == "PN":
        return f"PN {nummer}", f"{WEBSEITE}/nomination/{_ordinal(kongress)}-congress/{nummer}"
    if typ not in VORLAGEN:
        return (text or "").strip(), ""
    schreibweise, pfad = VORLAGEN[typ]
    return f"{schreibweise} {nummer}", f"{WEBSEITE}/bill/{_ordinal(kongress)}-congress/{pfad}/{nummer}"


def _ergebnis(roh: str, frage: str) -> tuple[str, bool]:
    if ABGELEHNT.search(roh):
        return "abgelehnt", False
    if "Nomination" in frage or "confirm" in roh.lower():
        return "bestätigt", True
    return "angenommen", True


def _art(frage: str, nummer: str) -> str:
    if "Nomination" in frage:
        return "Personalie"
    if "Veto" in frage:
        return "Veto"
    if "Ratification" in frage:
        return "Staatsvertrag"
    if "Res." in nummer:
        return "Resolution"
    return "Gesetz"


# --------------------------------------------------------------------- Senat


def parse_senat(rohdaten: bytes, von: date, bis: date) -> tuple[list[Beschluss], date | None]:
    """Abstimmungen im Zeitraum + Datum der jüngsten Abstimmung überhaupt."""
    wurzel = ET.fromstring(rohdaten.lstrip(b"\xef\xbb\xbf").lstrip())
    jahr = int((wurzel.findtext("congress_year") or "0").strip())
    kongress = int((wurzel.findtext("congress") or "0").strip())
    sitzung = int((wurzel.findtext("session") or "0").strip())

    beschluesse: list[Beschluss] = []
    juengste: date | None = None
    for abstimmung in wurzel.iter("vote"):
        try:
            datum = datetime.strptime(
                f"{(abstimmung.findtext('vote_date') or '').strip()}-{jahr}", "%d-%b-%Y"
            ).date()
        except ValueError:
            continue
        juengste = max(juengste or datum, datum)
        frage = " ".join((abstimmung.findtext("question") or "").split())
        if not (von <= datum <= bis) or not SENAT_IN_DER_SACHE.search(frage):
            continue

        nummer, link = vorlage(abstimmung.findtext("issue") or "", kongress)
        titel = " ".join((abstimmung.findtext("title") or "").split())
        # „H.R. 9340 as Amended; A bill to …“ → nur der Gegenstand
        vorspann, _, rest = titel.partition(";")
        if rest.strip() and len(vorspann) < 60 and re.search(r"\d", vorspann):
            titel = rest.strip()
        titel = titel or nummer
        ergebnis, angenommen = _ergebnis(abstimmung.findtext("result") or "", frage)
        ja = (abstimmung.findtext("vote_tally/yeas") or "").strip()
        nein = (abstimmung.findtext("vote_tally/nays") or "").strip()
        laufnummer = int((abstimmung.findtext("vote_number") or "0").strip() or 0)
        beschluesse.append(
            Beschluss(
                datum=datum,
                titel=titel,
                link=link
                or SENAT_ABSTIMMUNG.format(kongress=kongress, sitzung=sitzung, nummer=laufnummer),
                nummer=nummer,
                gremium="Senat",
                art=_art(frage, nummer),
                ergebnis=ergebnis,
                angenommen=angenommen,
                stimmen=f"{ja} : {nein}" if ja and nein else "",
            )
        )
    return beschluesse, juengste


# ------------------------------------------------------- Repräsentantenhaus


def _feld(text: str, name: str) -> str:
    treffer = re.search(rf"<{name}\b[^>]*>(.*?)</{name}>", text, re.S)
    return " ".join(unescape(treffer.group(1)).split()) if treffer else ""


def parse_house(text: str) -> dict:
    """Kopfdaten einer Abstimmung — die Datei darf nach den Summen abgeschnitten sein."""
    summen = re.search(r"<totals-by-vote>(.*?)</totals-by-vote>", text, re.S)
    try:
        datum = datetime.strptime(_feld(text, "action-date"), "%d-%b-%Y").date()
    except ValueError:
        datum = None
    return {
        "datum": datum,
        "kongress": int(_feld(text, "congress") or 0),
        "vorlage": _feld(text, "legis-num"),
        "frage": _feld(text, "vote-question"),
        "ergebnis": _feld(text, "vote-result"),
        "titel": _feld(text, "vote-desc"),
        "ja": _feld(summen.group(1), "yea-total") if summen else "",
        "nein": _feld(summen.group(1), "nay-total") if summen else "",
    }


def house_beschluss(kopf: dict, jahr: int, nummer: int) -> Beschluss | None:
    """Nur Entscheidungen in der Sache — sonst ``None``."""
    if not HOUSE_IN_DER_SACHE.search(kopf["frage"]) or GESCHAEFTSORDNUNG.search(kopf["titel"]):
        return None
    kurz, link = vorlage(kopf["vorlage"], kopf["kongress"] or kongress_und_sitzung(jahr)[0])
    ergebnis, angenommen = _ergebnis(kopf["ergebnis"], kopf["frage"])
    return Beschluss(
        datum=kopf["datum"],
        titel=kopf["titel"] or kurz,
        link=link or HOUSE_SEITE.format(jahr=jahr, nummer=nummer),
        nummer=kurz,
        gremium="Repräsentantenhaus",
        art=_art(kopf["frage"], kurz),
        ergebnis=ergebnis,
        angenommen=angenommen,
        stimmen=f"{kopf['ja']} : {kopf['nein']}" if kopf["ja"] and kopf["nein"] else "",
    )


def letzte_nummer(existiert, bekannt: int = 0, obergrenze: int = 3000) -> int:
    """Jüngste vorhandene Abstimmungsnummer finden: erst galoppieren, dann halbieren.

    ``bekannt`` ist die Nummer vom letzten Lauf — damit reichen meist ein oder
    zwei Abrufe. Ohne Anhaltspunkt sind es rund zwanzig.
    """
    unten = bekannt if bekannt and existiert(bekannt) else 0
    if not unten:
        if not existiert(1):
            return 0
        unten = 1
    schritt, oben = 1, unten + 1
    while oben <= obergrenze and existiert(oben):
        unten, schritt = oben, schritt * 2
        oben = unten + schritt
    oben = min(oben, obergrenze + 1)
    while oben - unten > 1:
        mitte = (unten + oben) // 2
        if existiert(mitte):
            unten = mitte
        else:
            oben = mitte
    return unten


def _house_kopf(jahr: int, nummer: int, timeout: int) -> str | None:
    """Anfang der Abstimmungsdatei (die Namensliste dahinter braucht es nicht)."""
    try:
        roh = hole_daten(
            HOUSE_ABSTIMMUNG.format(jahr=jahr, nummer=nummer),
            timeout=timeout,
            versuche=2,
            kopfzeilen={"Range": "bytes=0-8191"},
        )
    except urllib.error.HTTPError as fehler:
        if fehler.code == 404:
            return None
        raise
    return roh.decode("utf-8", "replace")


def _lade_merker(pfad: Path | None) -> dict:
    try:
        return json.loads(pfad.read_text(encoding="utf-8")) if pfad and pfad.exists() else {}
    except (OSError, ValueError):
        return {}


def _speichere_merker(pfad: Path | None, merker: dict) -> None:
    if not pfad:
        return
    try:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps(merker, indent=1), encoding="utf-8")
    except OSError:
        pass


def hole_house(von: date, bis: date, timeout: int, merker_datei: Path | None, hoechstens: int = 250):
    beschluesse: list[Beschluss] = []
    juengste: date | None = None
    merker = _lade_merker(merker_datei)
    for jahr in sorted({von.year, bis.year}, reverse=True):
        koepfe: dict[int, str | None] = {}

        def existiert(nummer: int, jahr=jahr, koepfe=koepfe) -> bool:
            if nummer not in koepfe:
                koepfe[nummer] = _house_kopf(jahr, nummer, timeout)
            return koepfe[nummer] is not None

        nummer = letzte_nummer(existiert, int(merker.get(str(jahr), 0)))
        if nummer:
            merker[str(jahr)] = nummer
        # Rückwärts lesen, bis der Zeitraum verlassen ist.
        ende = max(nummer - hoechstens, 0)
        while nummer > ende:
            text = koepfe[nummer] if nummer in koepfe else _house_kopf(jahr, nummer, timeout)
            nummer -= 1
            if not text:
                continue
            kopf = parse_house(text)
            if kopf["datum"] is None:
                continue
            juengste = max(juengste or kopf["datum"], kopf["datum"])
            if kopf["datum"] < von:
                break
            if kopf["datum"] <= bis:
                beschluss = house_beschluss(kopf, jahr, nummer + 1)
                if beschluss:
                    beschluesse.append(beschluss)
    _speichere_merker(merker_datei, merker)
    return beschluesse, juengste


# ------------------------------------------------------------- Neue Gesetze


def parse_gesetze(antwort: dict, von: date, bis: date) -> tuple[list[Beschluss], date | None]:
    beschluesse: list[Beschluss] = []
    juengste: date | None = None
    for eintrag in antwort.get("bills") or []:
        letzte = eintrag.get("latestAction") or {}
        text = str(letzte.get("text") or "")
        try:
            datum = date.fromisoformat(str(letzte.get("actionDate") or ""))
        except ValueError:
            continue
        if "Became" not in text:
            continue
        juengste = max(juengste or datum, datum)
        if not (von <= datum <= bis):
            continue
        kongress = int(eintrag.get("congress") or 0)
        kurz, link = vorlage(f"{eintrag.get('type', '')} {eintrag.get('number', '')}", kongress)
        gesetze = [
            f"{g.get('type', 'Public Law')} {g.get('number', '')}".strip()
            for g in eintrag.get("laws") or []
        ]
        beschluesse.append(
            Beschluss(
                datum=datum,
                titel=" ".join(str(eintrag.get("title") or kurz).split()),
                link=link,
                nummer=kurz,
                gremium="Präsident",
                art=", ".join(gesetze) or "Gesetz",
                ergebnis="unterzeichnet",
            )
        )
    return beschluesse, juengste


# ------------------------------------------------------------------ Gesamt


def hole_entscheidungen(
    heute: date, tage: int = 7, timeout: int = 20, merker_datei: Path | None = None
) -> Gesetzgebungsergebnis:
    ergebnis = Gesetzgebungsergebnis(id="kongress", name="US-Kongress", webseite=WEBSEITE)
    von, bis = zeitraum(heute, tage)
    juengste: list[date] = []

    def schritt(url: str, format_name: str, abruf) -> None:
        start = time.monotonic()
        try:
            gefunden, zuletzt = abruf()
        except Exception as fehler:
            ergebnis.status.append(
                FeedStatus(url=url, quelle_id="kongress", ok=False, format=format_name,
                           fehler=str(fehler), dauer_ms=int((time.monotonic() - start) * 1000))
            )
            return
        ergebnis.beschluesse.extend(gefunden)
        if zuletzt:
            juengste.append(zuletzt)
        ergebnis.status.append(
            FeedStatus(url=url, quelle_id="kongress", ok=True, anzahl=len(gefunden),
                       format=format_name, dauer_ms=int((time.monotonic() - start) * 1000))
        )

    for jahr in sorted({von.year, bis.year}, reverse=True):
        kongress, sitzung = kongress_und_sitzung(jahr)
        url = SENAT_LISTE.format(kongress=kongress, sitzung=sitzung)
        schritt(url, "Senat (XML)", lambda url=url: parse_senat(hole_daten(url, timeout=timeout), von, bis))

    schritt(
        f"https://clerk.house.gov/evs/{bis.year}/",
        "Repräsentantenhaus (XML)",
        lambda: hole_house(von, bis, timeout, merker_datei),
    )

    schluessel = os.environ.get("CONGRESS_API_KEY", "").strip()
    kongress = kongress_und_sitzung(bis.year)[0]
    api_url = GESETZE_API.format(kongress=kongress, schluessel=schluessel or "DEMO_KEY")
    sichtbar = api_url.rsplit("&api_key=", 1)[0]  # Schlüssel nicht in die Seite schreiben
    vorher = len(ergebnis.status)
    schritt(sichtbar, "api.congress.gov (JSON)",
            lambda: parse_gesetze(json.loads(hole_daten(api_url, timeout=timeout)), von, bis))
    if not schluessel and len(ergebnis.status) > vorher and not ergebnis.status[-1].ok:
        ergebnis.status[-1].fehler = _ohne_schluessel(ergebnis.status[-1].fehler)
        ergebnis.hinweise.append(
            "Neue US-Gesetze fehlen gerade: der öffentliche Demo-Zugang von api.congress.gov "
            "ist ausgeschöpft. Abhilfe: kostenlosen Schlüssel als Secret CONGRESS_API_KEY hinterlegen."
        )

    ergebnis.zuletzt = max(juengste) if juengste else None
    ergebnis.beschluesse = sortiere(ergebnis.beschluesse)
    return ergebnis


def _ohne_schluessel(fehler: str) -> str:
    return f"{fehler} (DEMO_KEY — eigener Schlüssel: Secret CONGRESS_API_KEY)"
