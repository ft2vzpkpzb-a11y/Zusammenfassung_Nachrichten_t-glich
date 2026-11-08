"""Ist ein neues Briefing fällig? — Entscheidung für den Workflow.

GitHub startet geplante Läufe nicht pünktlich. Die Läufe für 05:00 UTC kamen im
Oktober und November 2026 zwischen 09:20 und 13:20 UTC an, also vier bis acht
Stunden zu spät. Ein Workflow, der nur zur Zielstunde selbst baut, käme damit
praktisch nie zum Zug.

Deshalb wird der Workflow stündlich angestoßen, und hier fällt die
Entscheidung: gebaut wird, sobald ein Ausgabetermin (``ausgaben`` in
``config/feeds.json``, Wiener Zeit) erreicht ist und seit diesem Termin noch
kein Briefing veröffentlicht wurde. Ein verspäteter Lauf baut also trotzdem,
und weitere Läufe bis zum nächsten Termin bauen nicht noch einmal.

Aufruf im Workflow::

    python3 -m briefing.zeitplan "$(cat docs/stand.txt)"   # → faellig=true|false
"""

from __future__ import annotations

import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

WURZEL = Path(__file__).resolve().parent.parent


def lies_termine(texte: list[str]) -> list[time]:
    """``["05:00", "13:00"]`` → Uhrzeiten, sortiert. Unlesbares ist ein Konfigurationsfehler."""
    termine = []
    for text in texte:
        try:
            stunde, minute = (int(teil) for teil in str(text).strip().split(":"))
            termine.append(time(stunde, minute))
        except ValueError as fehler:
            raise ValueError(f"Ausgabetermin nicht lesbar: {text!r} (erwartet HH:MM)") from fehler
    if not termine:
        raise ValueError("Keine Ausgabetermine konfiguriert.")
    return sorted(termine)


def letzter_termin(jetzt: datetime, termine: list[time]) -> datetime:
    """Der jüngste Ausgabetermin, der nicht in der Zukunft liegt (in der Zone von ``jetzt``)."""
    for tage_zurueck in (0, 1):
        tag = (jetzt - timedelta(days=tage_zurueck)).date()
        vergangen = [
            termin
            for termin in (datetime.combine(tag, t, tzinfo=jetzt.tzinfo) for t in termine)
            if termin <= jetzt
        ]
        if vergangen:
            return max(vergangen)
    raise ValueError("Keine Ausgabetermine konfiguriert.")


def lies_stand(text: str) -> datetime | None:
    """Zeitpunkt der zuletzt veröffentlichten Ausgabe (Inhalt von ``stand.txt``)."""
    try:
        stand = datetime.fromisoformat(text.strip())
    except (AttributeError, ValueError):
        return None
    return stand if stand.tzinfo else None  # ohne Zeitzone nicht vergleichbar


def ist_faellig(jetzt: datetime, letzter_lauf: datetime | None, termine: list[time]) -> bool:
    return letzter_lauf is None or letzter_lauf < letzter_termin(jetzt, termine)


def main(argumente: list[str] | None = None) -> int:
    from .feeds import lade_konfiguration

    argumente = sys.argv[1:] if argumente is None else argumente
    konfiguration = lade_konfiguration(WURZEL / "config" / "feeds.json")
    termine = lies_termine(konfiguration.ausgaben)
    jetzt = datetime.now(ZoneInfo(konfiguration.zeitzone))
    letzter = lies_stand(argumente[0] if argumente else "")
    termin = letzter_termin(jetzt, termine)
    faellig = ist_faellig(jetzt, letzter, termine)

    print(f"faellig={'true' if faellig else 'false'}")
    zuletzt = f"{letzter.astimezone(jetzt.tzinfo):%d.%m. %H:%M}" if letzter else "unbekannt"
    print(
        f"Jetzt {jetzt:%d.%m. %H:%M}, letzter Termin {termin:%d.%m. %H:%M}, "
        f"zuletzt veröffentlicht {zuletzt} → {'wird gebaut' if faellig else 'nichts zu tun'}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
