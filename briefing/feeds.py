"""Konfiguration der Nachrichtenquellen laden und validieren."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .rubriken import ERLAUBT, GESPERRT, Rubrikfilter


@dataclass
class Feedadresse:
    """Eine Feed-Adresse samt Ausweichadressen.

    Redaktionen schreiben ihre Ressorts unterschiedlich (``/rss/Politik`` vs.
    ``/rss/politik``) und ziehen Feeds gelegentlich um. Schlägt die erste
    Adresse fehl oder liefert nichts, werden der Reihe nach die Alternativen
    probiert — so bleibt eine Quelle nicht wegen eines Großbuchstabens leer.
    """

    url: str
    alternativen: list[str] = field(default_factory=list)

    @property
    def kandidaten(self) -> list[str]:
        return [self.url, *self.alternativen]


def _als_feedadresse(wert) -> Feedadresse:
    if isinstance(wert, Feedadresse):
        return wert
    if isinstance(wert, str):
        return Feedadresse(url=wert)
    if isinstance(wert, dict) and wert.get("url"):
        return Feedadresse(
            url=wert["url"], alternativen=list(wert.get("alternativen") or [])
        )
    raise ValueError(f"Feed-Eintrag nicht lesbar: {wert!r}")


@dataclass
class Quelle:
    """Eine Nachrichtenquelle (eine Spalte im Briefing)."""

    id: str
    name: str
    feeds: list
    kategorie: str = "Sonstige"
    sprache: str = "de"
    farbe: str = "#4b5563"
    webseite: str = ""
    uebersetzen: bool = False
    hervorheben: bool = False
    alle_anzeigen: bool = False
    rubriken_filtern: bool = True
    hinweis: str = ""

    def __post_init__(self) -> None:
        # Erlaubt sowohl "https://…" als auch {"url": …, "alternativen": [...]}
        self.feeds = [_als_feedadresse(f) for f in self.feeds]


@dataclass
class Uebersetzungsoptionen:
    aktiv: bool = True
    modell: str = "claude-opus-5"
    zielsprache: str = "Deutsch"
    batch_groesse: int = 25
    cache_datei: str = "cache/uebersetzungen.json"


@dataclass
class Konfiguration:
    titel: str = "Tägliche Nachrichten-Zusammenfassung"
    untertitel: str = ""
    zeitzone: str = "Europe/Vienna"
    sichtbare_schlagzeilen: int = 5
    max_schlagzeilen_pro_quelle: int = 80
    uebersetzung: Uebersetzungsoptionen = field(default_factory=Uebersetzungsoptionen)
    rubrikfilter: Rubrikfilter = field(default_factory=Rubrikfilter)
    quellen: list[Quelle] = field(default_factory=list)


def lade_konfiguration(pfad: str | Path) -> Konfiguration:
    """Liest die JSON-Konfiguration und prüft sie auf offensichtliche Fehler."""
    pfad = Path(pfad)
    rohdaten = json.loads(pfad.read_text(encoding="utf-8"))

    quellen: list[Quelle] = []
    gesehene_ids: set[str] = set()
    for eintrag in rohdaten.get("quellen", []):
        if not eintrag.get("id") or not eintrag.get("feeds"):
            raise ValueError(f"Quelle ohne 'id' oder 'feeds': {eintrag!r}")
        if eintrag["id"] in gesehene_ids:
            raise ValueError(f"Doppelte Quellen-ID: {eintrag['id']}")
        gesehene_ids.add(eintrag["id"])
        quellen.append(
            Quelle(
                id=eintrag["id"],
                name=eintrag.get("name", eintrag["id"]),
                feeds=list(eintrag["feeds"]),
                kategorie=eintrag.get("kategorie", "Sonstige"),
                sprache=eintrag.get("sprache", "de"),
                farbe=eintrag.get("farbe", "#4b5563"),
                webseite=eintrag.get("webseite", ""),
                uebersetzen=bool(eintrag.get("uebersetzen", False)),
                hervorheben=bool(eintrag.get("hervorheben", False)),
                alle_anzeigen=bool(eintrag.get("alle_anzeigen", False)),
                rubriken_filtern=bool(eintrag.get("rubriken_filtern", True)),
                hinweis=eintrag.get("hinweis", ""),
            )
        )

    if not quellen:
        raise ValueError("Die Konfiguration enthält keine Quellen.")

    u = rohdaten.get("uebersetzung", {})
    r = rohdaten.get("rubrikfilter", {})
    return Konfiguration(
        titel=rohdaten.get("titel", "Tägliche Nachrichten-Zusammenfassung"),
        untertitel=rohdaten.get("untertitel", ""),
        zeitzone=rohdaten.get("zeitzone", "Europe/Vienna"),
        sichtbare_schlagzeilen=int(rohdaten.get("sichtbare_schlagzeilen", 5)),
        max_schlagzeilen_pro_quelle=int(rohdaten.get("max_schlagzeilen_pro_quelle", 80)),
        uebersetzung=Uebersetzungsoptionen(
            aktiv=bool(u.get("aktiv", True)),
            modell=u.get("modell", "claude-opus-5"),
            zielsprache=u.get("zielsprache", "Deutsch"),
            batch_groesse=int(u.get("batch_groesse", 25)),
            cache_datei=u.get("cache_datei", "cache/uebersetzungen.json"),
        ),
        rubrikfilter=Rubrikfilter(
            aktiv=bool(r.get("aktiv", True)),
            # Ohne eigene Listen gelten die Vorgaben aus briefing/rubriken.py.
            erlaubt=list(r.get("erlaubt") or ERLAUBT),
            gesperrt=list(r.get("gesperrt") or GESPERRT),
        ),
        quellen=quellen,
    )
