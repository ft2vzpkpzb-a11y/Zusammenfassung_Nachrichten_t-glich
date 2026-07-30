"""Feeds abrufen und robust parsen.

Hier lag der ORF-Fehler: ``https://rss.orf.at/news.xml`` ist **RSS 1.0 (RDF)**,
kein RSS 2.0. Die ``<item>``-Elemente hängen dort direkt unter ``<rdf:RDF>``
statt unter ``<channel>``, und alles liegt im Namensraum
``http://purl.org/rss/1.0/``. Ein Parser, der ``channel/item`` sucht oder
Namensräume ignoriert, findet für den ORF schlicht null Einträge — die Spalte
bleibt leer, ohne dass ein Fehler auftaucht.

Der Parser hier arbeitet deshalb formatunabhängig: er sucht im gesamten Baum
nach Elementen, deren *lokaler* Name ``item`` (RSS 1.0/2.0) oder ``entry``
(Atom) ist. Zusätzlich meldet jeder Feed seinen Status zurück, damit eine leere
Spalte nie wieder stillschweigend passiert.
"""

from __future__ import annotations

import gzip
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from xml.etree import ElementTree as ET

from . import rubriken

BENUTZER_AGENT = (
    "Mozilla/5.0 (compatible; NachrichtenBriefing/2.0; "
    "+https://github.com/ft2vzpkpzb-a11y/Zusammenfassung_Nachrichten_t-glich)"
)

# Elementnamen (ohne Namensraum), die einen Nachrichteneintrag markieren.
EINTRAG_TAGS = {"item", "entry"}


@dataclass
class Schlagzeile:
    titel: str
    link: str = ""
    veroeffentlicht: datetime | None = None
    zusammenfassung: str = ""
    quelle_id: str = ""
    uebersetzung: str = ""
    kategorien: list[str] = field(default_factory=list)

    @property
    def sortierschluessel(self) -> datetime:
        """Einträge ohne Datum ans Ende sortieren, statt sie zu verlieren."""
        return self.veroeffentlicht or datetime.min.replace(tzinfo=timezone.utc)


@dataclass
class FeedStatus:
    """Ergebnis eines einzelnen Feed-Abrufs — Grundlage der Statusanzeige."""

    url: str
    quelle_id: str
    ok: bool
    anzahl: int = 0
    format: str = "unbekannt"
    fehler: str = ""
    dauer_ms: int = 0
    gefiltert: int = 0  # vom Rubrikfilter aussortierte Einträge
    rubriken: list[str] = field(default_factory=list)  # gefundene Ressorts


@dataclass
class QuellenErgebnis:
    quelle_id: str
    schlagzeilen: list[Schlagzeile] = field(default_factory=list)
    status: list[FeedStatus] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return any(s.ok for s in self.status)

    @property
    def fehlermeldungen(self) -> list[str]:
        return [f"{s.url}: {s.fehler}" for s in self.status if not s.ok]


def _lokaler_name(tag: str) -> str:
    """``{http://purl.org/rss/1.0/}item`` -> ``item``."""
    return tag.rsplit("}", 1)[-1].lower()


def _text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return unescape(element.text).strip()


def _kind(eintrag: ET.Element, *namen: str) -> ET.Element | None:
    """Erstes Kind mit passendem lokalem Namen — namensraumunabhängig."""
    gesucht = {n.lower() for n in namen}
    for kind in eintrag:
        if _lokaler_name(kind.tag) in gesucht:
            return kind
    return None


def _extrahiere_kategorien(eintrag: ET.Element) -> list[str]:
    """Ressorts einsammeln: <category> (RSS/Atom) und <dc:subject> (RSS 1.0)."""
    gefunden: list[str] = []
    for kind in eintrag:
        name = _lokaler_name(kind.tag)
        if name not in {"category", "subject"}:
            continue
        # Atom schreibt das Ressort ins Attribut, RSS in den Text.
        wert = kind.attrib.get("term") or (kind.text or "")
        wert = unescape(wert).strip()
        if wert and wert not in gefunden:
            gefunden.append(wert)
    return gefunden


def _extrahiere_link(eintrag: ET.Element) -> str:
    """Link aus RSS 2.0, RSS 1.0 (rdf:about) oder Atom (<link href>) holen."""
    for kind in eintrag:
        if _lokaler_name(kind.tag) != "link":
            continue
        # Atom: <link rel="alternate" href="..."/>
        href = kind.attrib.get("href")
        if href:
            if kind.attrib.get("rel", "alternate") == "alternate":
                return href.strip()
            continue
        if kind.text and kind.text.strip():
            return kind.text.strip()

    # RSS 1.0: <item rdf:about="https://...">
    for schluessel, wert in eintrag.attrib.items():
        if _lokaler_name(schluessel) == "about" and wert:
            return wert.strip()

    # Notnagel: <guid isPermaLink="true">
    guid = _kind(eintrag, "guid")
    if guid is not None and guid.attrib.get("isPermaLink", "true") != "false":
        return _text(guid)
    return ""


def _parse_datum(rohwert: str) -> datetime | None:
    """RFC-822 (pubDate) und ISO-8601 (dc:date, Atom) verstehen."""
    rohwert = rohwert.strip()
    if not rohwert:
        return None
    try:
        datum = parsedate_to_datetime(rohwert)
        if datum is not None:
            return datum if datum.tzinfo else datum.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        datum = datetime.fromisoformat(rohwert.replace("Z", "+00:00"))
        return datum if datum.tzinfo else datum.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _extrahiere_datum(eintrag: ET.Element) -> datetime | None:
    for feldname in ("pubdate", "date", "published", "updated", "created"):
        element = _kind(eintrag, feldname)
        if element is not None:
            datum = _parse_datum(_text(element))
            if datum is not None:
                return datum
    return None


def _erkenne_format(wurzel: ET.Element) -> str:
    name = _lokaler_name(wurzel.tag)
    if name == "rdf":
        return "RSS 1.0 (RDF)"
    if name == "rss":
        return f"RSS {wurzel.attrib.get('version', '2.0')}"
    if name == "feed":
        return "Atom"
    return name or "unbekannt"


def parse_feed(rohdaten: bytes, quelle_id: str = "") -> tuple[list[Schlagzeile], str]:
    """XML-Bytes in Schlagzeilen umwandeln.

    Versteht RSS 2.0, RSS 1.0/RDF (ORF) und Atom, weil Einträge über ihren
    lokalen Elementnamen im ganzen Baum gesucht werden — nicht über einen
    festen Pfad wie ``channel/item``.
    """
    # Manche Feeds liefern BOM oder führende Leerzeichen vor der XML-Deklaration.
    rohdaten = rohdaten.lstrip(b"\xef\xbb\xbf").lstrip()
    wurzel = ET.fromstring(rohdaten)
    format_name = _erkenne_format(wurzel)

    schlagzeilen: list[Schlagzeile] = []
    for element in wurzel.iter():
        if _lokaler_name(element.tag) not in EINTRAG_TAGS:
            continue
        titel = _text(_kind(element, "title"))
        if not titel:
            continue
        schlagzeilen.append(
            Schlagzeile(
                titel=" ".join(titel.split()),
                link=_extrahiere_link(element),
                veroeffentlicht=_extrahiere_datum(element),
                zusammenfassung=" ".join(
                    _text(_kind(element, "description", "summary")).split()
                )[:400],
                quelle_id=quelle_id,
                kategorien=_extrahiere_kategorien(element),
            )
        )
    return schlagzeilen, format_name


def hole_feed(url: str, timeout: int = 20, versuche: int = 3) -> bytes:
    """Feed herunterladen — mit User-Agent, gzip und Wiederholversuchen.

    Ohne eigenen User-Agent antworten mehrere Redaktionen (u. a. ORF und FT)
    mit 403 auf den urllib-Standard-Header.
    """
    letzter_fehler: Exception | None = None
    for versuch in range(versuche):
        anfrage = urllib.request.Request(
            url,
            headers={
                "User-Agent": BENUTZER_AGENT,
                "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
                "Accept-Encoding": "gzip",
                "Accept-Language": "de,en;q=0.8",
            },
        )
        try:
            with urllib.request.urlopen(anfrage, timeout=timeout) as antwort:
                nutzdaten = antwort.read()
                if antwort.headers.get("Content-Encoding", "") == "gzip":
                    nutzdaten = gzip.decompress(nutzdaten)
                return nutzdaten
        except (urllib.error.URLError, OSError, gzip.BadGzipFile) as fehler:
            letzter_fehler = fehler
            if versuch < versuche - 1:
                time.sleep(2**versuch)
    raise RuntimeError(str(letzter_fehler))


def _hole_ersten_treffer(adresse, quelle_id: str, timeout: int):
    """Adresse und Ausweichadressen der Reihe nach probieren.

    Rückgabe: (verwendete URL, Schlagzeilen oder None, Format, Fehlertext).
    Gewonnen hat die erste Adresse, die überhaupt Einträge liefert — eine
    Seite, die auf einen unbekannten Pfad mit einer leeren, aber gültigen
    XML-Hülle antwortet, zählt also nicht.
    """
    kandidaten = getattr(adresse, "kandidaten", None) or [str(adresse)]
    letzte_url = kandidaten[0]
    letzter_fehler = "unbekannter Fehler"
    leerer_treffer = None

    for nummer, url in enumerate(kandidaten):
        letzte_url = url
        # Nur die Hauptadresse bekommt Wiederholversuche; die Ausweichadressen
        # werden einmal probiert, sonst dauert ein toter Feed ewig.
        versuche = 3 if nummer == 0 else 1
        try:
            rohdaten = hole_feed(url, timeout=timeout, versuche=versuche)
            schlagzeilen, format_name = parse_feed(rohdaten, quelle_id)
        except ET.ParseError as fehler:
            letzter_fehler = f"XML nicht lesbar ({fehler})"
            continue
        except Exception as fehler:  # Netzwerk, HTTP-Status, gzip …
            letzter_fehler = str(fehler)
            continue

        if schlagzeilen:
            return url, schlagzeilen, format_name, ""
        # Leer, aber lesbar: merken und erst nutzen, wenn nichts Besseres kommt.
        leerer_treffer = leerer_treffer or (url, [], format_name, "")
        letzter_fehler = "Feed gelesen, aber ohne Einträge"

    if leerer_treffer:
        return leerer_treffer
    return letzte_url, None, "unbekannt", letzter_fehler


def hole_quelle(
    quelle,
    max_schlagzeilen: int = 80,
    timeout: int = 20,
    rubrikfilter=None,
) -> QuellenErgebnis:
    """Alle Feeds einer Quelle abrufen, zusammenführen und deduplizieren.

    ``rubrikfilter`` grenzt auf bestimmte Ressorts ein (Standard: Politik und
    Wirtschaft). Quellen mit ``rubriken_filtern: false`` — etwa die Financial
    Times — bleiben davon unberührt.
    """
    ergebnis = QuellenErgebnis(quelle_id=quelle.id)
    gesehen: set[str] = set()
    filtern = rubrikfilter is not None and rubrikfilter.aktiv and quelle.rubriken_filtern

    for adresse in quelle.feeds:
        start = time.monotonic()
        url, schlagzeilen, format_name, fehlermeldung = _hole_ersten_treffer(
            adresse, quelle.id, timeout
        )
        if schlagzeilen is None:
            ergebnis.status.append(
                FeedStatus(
                    url=url,
                    quelle_id=quelle.id,
                    ok=False,
                    fehler=fehlermeldung,
                    dauer_ms=int((time.monotonic() - start) * 1000),
                )
            )
            continue

        # Ein Feed, dessen Adresse schon das Ressort nennt, wird komplett
        # übernommen — sonst würden Artikel-Schlagwörter (Guardian: „Media",
        # „Television industry") Meldungen aus dem richtigen Ressort kippen.
        eintraege_pruefen = filtern and not rubriken.ist_ressortfeed(url, rubrikfilter)

        neue = 0
        aussortiert = 0
        gefundene_rubriken: list[str] = []
        for schlagzeile in schlagzeilen:
            for rubrik in schlagzeile.kategorien:
                if rubrik not in gefundene_rubriken:
                    gefundene_rubriken.append(rubrik)

            if eintraege_pruefen and not rubrikfilter.passt(
                rubriken.signale(schlagzeile, url)
            ):
                aussortiert += 1
                continue

            schluessel = schlagzeile.link or schlagzeile.titel.lower()
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            ergebnis.schlagzeilen.append(schlagzeile)
            neue += 1

        if not schlagzeilen:
            hinweis = "Feed gelesen, aber ohne Einträge"
        elif filtern and neue == 0:
            # Nicht als Netzwerkfehler ausgeben: der Feed war in Ordnung,
            # nur passte nichts zu Politik/Wirtschaft.
            hinweis = f"{aussortiert} Einträge, keiner in Politik/Wirtschaft"
        else:
            hinweis = ""

        haupt_url = getattr(adresse, "url", url)
        if url != haupt_url:
            ausweich = f"Ausweichadresse verwendet statt {haupt_url}"
            hinweis = f"{ausweich} · {hinweis}" if hinweis else ausweich

        ergebnis.status.append(
            FeedStatus(
                url=url,
                quelle_id=quelle.id,
                # Ein technisch erfolgreicher Abruf ohne Einträge gilt als
                # Fehler — genau dieser Fall ist früher als leere Spalte
                # durchgerutscht, statt sichtbar zu werden.
                ok=bool(schlagzeilen),
                anzahl=neue,
                format=format_name,
                fehler=hinweis,
                dauer_ms=int((time.monotonic() - start) * 1000),
                gefiltert=aussortiert,
                rubriken=gefundene_rubriken[:12],
            )
        )

    ergebnis.schlagzeilen.sort(key=lambda s: s.sortierschluessel, reverse=True)
    del ergebnis.schlagzeilen[max_schlagzeilen:]
    return ergebnis
