"""Gesetzgebung der letzten Tage: Nationalrat (Österreich) und US-Kongress.

Beide Abschnitte stehen ganz oben im Briefing. Gemeinsam ist ihnen nur das
Grundgerüst — ein ``Beschluss`` mit Datum, Titel, Link und Ergebnis — die
Herkunft ist völlig verschieden:

* Nationalrat: Open-Data-Schnittstelle des Parlaments (``nationalrat.py``)
* US-Kongress: Abstimmungslisten von Senat und Repräsentantenhaus sowie neue
  Gesetze über api.congress.gov (``kongress.py``)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .fetch import FeedStatus


@dataclass
class Partei:
    name: str
    farbe: str = ""
    dafuer: bool = True


@dataclass
class Beschluss:
    """Eine Entscheidung — ein Gesetzesbeschluss, eine Abstimmung, ein neues Gesetz."""

    datum: date
    titel: str
    link: str = ""
    nummer: str = ""  # 214/BNR, H.R. 7831, PN1129 …
    gremium: str = ""  # Nationalrat, Senat, Repräsentantenhaus, Präsident
    art: str = ""  # Bundesgesetz, Staatsvertrag, Gesetz, Personalie …
    ergebnis: str = ""  # angenommen, abgelehnt, bestätigt, unterzeichnet
    angenommen: bool = True
    stimmen: str = ""  # „52 : 48“
    erlaeuterung: str = ""  # Parlamentskorrespondenz-Schlagzeile oder Gegenstand
    themen: list[str] = field(default_factory=list)
    parteien: list[Partei] = field(default_factory=list)
    # Gleiche Feldnamen wie bei Schlagzeilen, damit dieselbe Übersetzung greift.
    uebersetzung: str = ""

    @property
    def dafuer(self) -> list[Partei]:
        return [p for p in self.parteien if p.dafuer]

    @property
    def dagegen(self) -> list[Partei]:
        return [p for p in self.parteien if not p.dafuer]

    @property
    def einstimmig(self) -> bool:
        return bool(self.parteien) and not self.dagegen


@dataclass
class Gesetzgebungsergebnis:
    id: str
    name: str
    webseite: str = ""
    beschluesse: list[Beschluss] = field(default_factory=list)
    status: list[FeedStatus] = field(default_factory=list)
    zuletzt: date | None = None  # jüngste Entscheidung überhaupt — für den Leerhinweis
    hinweise: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return any(s.ok for s in self.status)

    @property
    def fehlermeldungen(self) -> list[str]:
        return [f"{s.url}: {s.fehler}" for s in self.status if not s.ok]


@dataclass
class Gesetzgebungsoptionen:
    aktiv: bool = True
    tage: int = 7
    nationalrat: bool = True
    # Mehrere Perioden gleichzeitig abfragen: nach einer Wahl liegt die neue
    # schon mit drin, ohne dass jemand die Konfiguration anfassen muss.
    gesetzgebungsperioden: list[str] = field(default_factory=lambda: ["XXVIII", "XXIX"])
    kongress: bool = True
    kongress_uebersetzen: bool = True


def zeitraum(heute: date, tage: int) -> tuple[date, date]:
    """``tage`` Tage zurück bis einschließlich heute."""
    return heute - timedelta(days=tage), heute


def sortiere(beschluesse: list[Beschluss]) -> list[Beschluss]:
    """Neueste zuerst; am selben Tag die höhere Nummer (= später beschlossen) zuerst."""

    def schluessel(b: Beschluss):
        ziffern = "".join(c for c in b.nummer if c.isdigit())
        return (b.datum, int(ziffern) if ziffern else 0)

    return sorted(beschluesse, key=schluessel, reverse=True)
