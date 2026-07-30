"""Konfiguration der Nachrichtenquellen laden und validieren."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Quelle:
    """Eine Nachrichtenquelle (eine Spalte im Briefing)."""

    id: str
    name: str
    feeds: list[str]
    kategorie: str = "Sonstige"
    sprache: str = "de"
    farbe: str = "#4b5563"
    webseite: str = ""
    uebersetzen: bool = False
    hervorheben: bool = False
    alle_anzeigen: bool = False


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
            )
        )

    if not quellen:
        raise ValueError("Die Konfiguration enthält keine Quellen.")

    u = rohdaten.get("uebersetzung", {})
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
        quellen=quellen,
    )
