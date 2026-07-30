"""Schlagzeilen auf bestimmte Ressorts eingrenzen (Standard: Politik & Wirtschaft).

Feeds kennzeichnen ihr Ressort auf drei verschiedene Arten, je nach Format und
Redaktion:

1. ``<category>Wirtschaft</category>`` (RSS 2.0, z. B. Die Presse, APA-OTS)
2. ``<dc:subject>Inland</dc:subject>`` (RSS 1.0/RDF, z. B. ORF)
3. gar nicht — dann verrät nur der Pfad des Artikels das Ressort
   (``/politik/``, ``/wirtschaft/``, ``/news/business/`` …)

Deshalb sammelt der Filter alle drei Signale ein und entscheidet darauf. Kommt
ein Eintrag aus einem Feed, der ohnehin nur ein Ressort führt
(``…/rss/wirtschaft``), zählt schon das als Treffer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit

# Ressorts, die zu „Politik" und „Wirtschaft" zählen — deutsch und englisch,
# weil BBC und Guardian ihre Pfade englisch benennen.
ERLAUBT = [
    "politik", "politics", "inland", "ausland", "international", "europa", "eu",
    "aussenpolitik", "innenpolitik", "weltpolitik", "world", "uk-news",
    "wirtschaft", "economy", "business", "konjunktur", "unternehmen", "companies",
    "finanzen", "finance", "boerse", "markt", "maerkte", "markets", "geld",
    "budget", "steuern", "arbeitsmarkt", "industrie", "handel", "immobilien",
]

# Gewinnt gegen die Erlaubt-Liste: „Kulturpolitik" bleibt damit draußen.
GESPERRT = [
    "sport", "fussball", "fussball-em", "olympia", "kultur", "kunst", "musik",
    "film", "buehne", "literatur", "panorama", "chronik", "leute", "promi",
    "lifestyle", "reise", "motor", "auto", "gesundheit", "wissenschaft",
    "wissen", "science", "religion", "etat", "karriere", "essen", "familie",
    "spiele", "games", "tv", "fernsehen", "wetter", "horoskop", "kolumne",
    "entertainment", "culture", "travel", "lifeandstyle", "football",
]

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


@dataclass
class Rubrikfilter:
    aktiv: bool = True
    erlaubt: list[str] = field(default_factory=lambda: list(ERLAUBT))
    gesperrt: list[str] = field(default_factory=lambda: list(GESPERRT))

    def passt(self, signale: list[str]) -> bool:
        """True, wenn mindestens ein Signal erlaubt und keines gesperrt ist."""
        normalisiert = [normalisiere(s) for s in signale if s]
        normalisiert = [s for s in normalisiert if s]
        if not normalisiert:
            return False
        if any(_trifft(s, self.gesperrt) for s in normalisiert):
            return False
        return any(_trifft(s, self.erlaubt) for s in normalisiert)


def normalisiere(wert: str) -> str:
    return wert.strip().lower().translate(_UMLAUTE)


def _trifft(signal: str, begriffe: list[str]) -> bool:
    # Teiltreffer, damit „innenpolitik" über „politik" und
    # „wirtschaftsministerium" über „wirtschaft" gefunden wird.
    return any(begriff in signal for begriff in begriffe)


def pfadsignale(url: str) -> list[str]:
    """Ressort-Hinweise aus einer Feed-Adresse ziehen: /rss/wirtschaft, /news/business/…"""
    if not url:
        return []
    teile = [t for t in urlsplit(url).path.split("/") if t and not t.isdigit()]
    return [t.rsplit(".", 1)[0] for t in teile]


def artikelsignale(url: str) -> list[str]:
    """Wie ``pfadsignale``, aber ohne den letzten Pfadteil.

    Der letzte Teil einer Artikel-Adresse ist die Überschrift oder eine ID.
    Würde man ihn mitlesen, landete „…-streit-ueber-sportbudget“ wegen des
    Wortes „sport“ auf der Sperrliste — das Ressort steht immer davor.
    """
    teile = pfadsignale(url)
    return teile[:-1] if len(teile) > 1 else []


def signale(schlagzeile, feed_url: str = "") -> list[str]:
    """Alle Ressort-Hinweise zu einer Schlagzeile einsammeln."""
    gesammelt = list(schlagzeile.kategorien)
    gesammelt += artikelsignale(schlagzeile.link)
    gesammelt += pfadsignale(feed_url)
    return gesammelt
