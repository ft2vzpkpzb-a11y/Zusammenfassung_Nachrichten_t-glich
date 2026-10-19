"""Erfundene Beispieldaten für die Layout-Vorschau (``--demo``).

Ausdrücklich **keine** echten Nachrichten: die Sätze sind frei erfunden und
dienen nur dazu, das Layout ohne Netzwerkzugriff zu prüfen. Die erzeugte Seite
trägt oben einen entsprechenden Hinweis.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from .fetch import FeedStatus, QuellenErgebnis, Schlagzeile

_BAUSTEINE_DE = [
    "Beispielressort einigt sich auf Muster-Kompromiss",
    "Testgemeinde beschließt neuen Platzhalter-Haushalt",
    "Blindtext-Kommission legt Zwischenbericht vor",
    "Musterbehörde kündigt Demo-Reform für Herbst an",
    "Beispielstadt eröffnet fiktive Verkehrsverbindung",
    "Platzhalter-Studie sieht Beispielbranche im Wandel",
    "Testverband fordert klarere Muster-Regeln",
    "Demo-Institut korrigiert Beispielprognose nach oben",
    "Musterregion meldet Rekord bei Blindtext-Anträgen",
    "Beispielgericht vertagt Verfahren auf Muster-Termin",
    "Platzhalter-Gipfel endet ohne konkrete Demo-Zusagen",
    "Testverwaltung startet Pilotprojekt mit Beispieldaten",
]

_BAUSTEINE_EN = [
    "Sample regulator opens placeholder inquiry into demo lender",
    "Fictional index closes higher on mock earnings data",
    "Example central bank holds rate in placeholder decision",
    "Demo conglomerate reshuffles board in sample restructuring",
    "Placeholder fund raises test capital for fictional venture",
    "Mock survey points to shifting demand in example sector",
    "Sample exchange delays launch of fictional trading venue",
    "Test ministry outlines placeholder budget for demo year",
    "Fictional carrier reports mock rise in quarterly volumes",
    "Example insurer sets aside demo provision after test claim",
    "Placeholder chipmaker guides to sample revenue range",
    "Demo retailer trims forecast in fictional trading update",
]


def _titel(sprache: str, nummer: int, rng: random.Random) -> str:
    bausteine = _BAUSTEINE_EN if sprache == "en" else _BAUSTEINE_DE
    return f"{rng.choice(bausteine)} (Beispiel {nummer})"


def demo_ergebnis(quelle, jetzt: datetime, anzahl: int = 0) -> QuellenErgebnis:
    """Erzeugt ein ``QuellenErgebnis`` mit erfundenen Schlagzeilen."""
    rng = random.Random(f"{quelle.id}-{jetzt:%Y-%m-%d}")
    if not anzahl:
        anzahl = rng.randint(52, 68) if quelle.hervorheben else rng.randint(11, 28)

    schlagzeilen = []
    for nummer in range(1, anzahl + 1):
        schlagzeile = Schlagzeile(
            titel=_titel(quelle.sprache, nummer, rng),
            link=quelle.webseite or "https://example.org",
            veroeffentlicht=jetzt - timedelta(minutes=7 * nummer + rng.randint(0, 6)),
            quelle_id=quelle.id,
        )
        if quelle.uebersetzen and quelle.sprache != "de":
            # Platzhalter-"Übersetzung", damit die zweizeilige Darstellung
            # (Deutsch oben, Original darunter) in der Vorschau sichtbar ist.
            schlagzeile.uebersetzung = f"{rng.choice(_BAUSTEINE_DE)} (Beispiel {nummer})"
        schlagzeilen.append(schlagzeile)

    ergebnis = QuellenErgebnis(quelle_id=quelle.id, schlagzeilen=schlagzeilen)
    for adresse in quelle.feeds:
        anteil = len(schlagzeilen) // max(len(quelle.feeds), 1)
        ergebnis.status.append(
            FeedStatus(
                url=getattr(adresse, "url", str(adresse)),
                quelle_id=quelle.id,
                ok=True,
                anzahl=anteil,
                format="Beispieldaten",
                dauer_ms=rng.randint(90, 420),
            )
        )
    return ergebnis


_GESETZE_DE = [
    "Beispielgesetz 2026",
    "Muster-Novelle zum Platzhaltergesetz",
    "Demo-Reformgesetz",
    "Blindtext-Anpassungsgesetz",
    "Abkommen zwischen Beispielland und Musterstaat",
    "Testverfahrensgesetz",
    "Platzhalter-Förderungsgesetz",
]
_GESETZE_EN = [
    "Sample Infrastructure Act",
    "Confirmation: Jane Example, to be Placeholder Secretary",
    "Demo Appropriations Resolution",
    "Mock Consumer Protection Act",
]
# Bewusst keine echten Parteien: erfundene Abstimmungen sollen niemandem zugeschrieben werden.
_FRAKTIONEN = [("Klub A", "#5ac8fa"), ("Klub B", "#ff3b30"), ("Klub C", "#ff2d55"), ("Klub D", "#007aff"), ("Klub E", "#34c759")]


def demo_gesetzgebung(jetzt: datetime, tage: int = 7) -> dict:
    """Erfundene Beschlüsse für die Layout-Vorschau — klar als Beispiel erkennbar."""
    from .gesetzgebung import Beschluss, Gesetzgebungsergebnis, Partei, sortiere

    rng = random.Random(f"gesetzgebung-{jetzt:%Y-%m-%d}")
    heute = jetzt.date()

    nr = Gesetzgebungsergebnis(id="nationalrat", name="Nationalrat", webseite="https://www.parlament.gv.at")
    for nummer, titel in enumerate(_GESETZE_DE, start=1):
        dafuer = rng.randint(2, 5)
        nr.beschluesse.append(
            Beschluss(
                datum=heute - timedelta(days=1 + nummer // 4),
                titel=f"{titel} (Beispiel {nummer})",
                link="https://www.parlament.gv.at",
                nummer=f"{900 + nummer}/BNR",
                gremium="Nationalrat",
                art="Staatsvertrag" if "Abkommen" in titel else "Bundesgesetz",
                ergebnis="beschlossen",
                erlaeuterung="Nationalrat beschließt Platzhalter-Regelung — erfundener Beispieltext.",
                themen=["Beispielthema"],
                parteien=[Partei(n, f, i < dafuer) for i, (n, f) in enumerate(_FRAKTIONEN)],
            )
        )
    nr.beschluesse = sortiere(nr.beschluesse)
    nr.zuletzt = nr.beschluesse[0].datum
    nr.status.append(FeedStatus(url="https://www.parlament.gv.at", quelle_id="nationalrat", ok=True,
                                anzahl=len(nr.beschluesse), format="Beispieldaten"))

    us = Gesetzgebungsergebnis(id="kongress", name="US-Kongress", webseite="https://www.congress.gov")
    for nummer, titel in enumerate(_GESETZE_EN, start=1):
        ja = rng.randint(40, 70)
        us.beschluesse.append(
            Beschluss(
                datum=heute - timedelta(days=nummer),
                titel=f"{titel} (Example {nummer})",
                link="https://www.congress.gov",
                nummer=f"H.R. {9000 + nummer}",
                gremium=["Senat", "Repräsentantenhaus", "Präsident"][nummer % 3],
                art="Personalie" if "Confirmation" in titel else "Gesetz",
                ergebnis="abgelehnt" if nummer == 3 else "angenommen",
                angenommen=nummer != 3,
                stimmen=f"{ja} : {100 - ja}",
                uebersetzung=f"{rng.choice(_BAUSTEINE_DE)} (Beispiel {nummer})",
            )
        )
    us.zuletzt = us.beschluesse[0].datum
    us.status.append(FeedStatus(url="https://www.congress.gov", quelle_id="kongress", ok=True,
                                anzahl=len(us.beschluesse), format="Beispieldaten"))
    return {"nationalrat": nr, "kongress": us}
