"""Englische Schlagzeilen ins Deutsche übersetzen (Claude Messages API).

Wird für die Financial Times verwendet: jede FT-Schlagzeile bekommt eine
deutsche Übersetzung, das englische Original bleibt darunter stehen.

Die Übersetzungen werden in einer Cache-Datei abgelegt, damit ein zweiter Lauf
am selben Tag (oder eine Schlagzeile, die mehrere Tage im Feed steht) keine
erneuten API-Aufrufe kostet.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

# Struktur der Antwort festnageln: garantiert gültiges JSON zurück,
# statt Modelltext hinterher parsen zu müssen.
ANTWORT_SCHEMA = {
    "type": "object",
    "properties": {
        "uebersetzungen": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nr": {"type": "integer"},
                    "de": {"type": "string"},
                },
                "required": ["nr", "de"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["uebersetzungen"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """Du übersetzt Nachrichten-Schlagzeilen ins {zielsprache}.

Regeln:
- Übersetze jede Schlagzeile einzeln und vollständig.
- Behalte den knappen Schlagzeilen-Ton bei; keine ganzen Sätze erfinden, nichts ergänzen, nichts weglassen.
- Eigennamen, Firmen-, Produkt- und Ortsnamen bleiben unverändert (z. B. "Goldman Sachs", "Federal Reserve", "Downing Street").
- Etablierte deutsche Entsprechungen verwenden, wo es sie gibt (z. B. "US-Notenbank" für "Fed", "Weißes Haus" für "White House").
- Fachbegriffe aus Wirtschaft und Finanzen fachlich korrekt übertragen.
- Gib zu jeder Nummer genau eine Übersetzung zurück."""


@dataclass
class Uebersetzungsergebnis:
    anzahl_uebersetzt: int = 0
    anzahl_aus_cache: int = 0
    fehler: str = ""

    @property
    def ok(self) -> bool:
        return not self.fehler


def _schluessel(titel: str) -> str:
    return hashlib.sha256(titel.strip().encode("utf-8")).hexdigest()[:20]


def _lade_cache(pfad: Path) -> dict[str, str]:
    if not pfad.exists():
        return {}
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _speichere_cache(pfad: Path, cache: dict[str, str]) -> None:
    try:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(
            json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    except OSError:
        pass  # Ein nicht schreibbarer Cache darf das Briefing nicht kippen.


def _uebersetze_batch(
    client, titel: list[str], modell: str, zielsprache: str
) -> dict[int, str]:
    nummeriert = "\n".join(f"{nr}. {t}" for nr, t in enumerate(titel, start=1))
    antwort = client.messages.create(
        model=modell,
        max_tokens=16000,
        system=SYSTEM_PROMPT.format(zielsprache=zielsprache),
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": ANTWORT_SCHEMA},
        },
        messages=[
            {
                "role": "user",
                "content": (
                    "Übersetze diese Schlagzeilen. Gib zu jeder Nummer die "
                    f"Übersetzung zurück:\n\n{nummeriert}"
                ),
            }
        ],
    )

    text = next((b.text for b in antwort.content if b.type == "text"), "")
    if not text:
        return {}
    daten = json.loads(text)
    return {
        eintrag["nr"]: eintrag["de"].strip()
        for eintrag in daten.get("uebersetzungen", [])
        if eintrag.get("de", "").strip()
    }


def uebersetze_schlagzeilen(
    schlagzeilen: list,
    modell: str = "claude-opus-5",
    zielsprache: str = "Deutsch",
    batch_groesse: int = 25,
    cache_datei: str | Path = "cache/uebersetzungen.json",
) -> Uebersetzungsergebnis:
    """Setzt ``schlagzeile.uebersetzung`` für alle übergebenen Schlagzeilen.

    Schlägt der API-Aufruf fehl (kein API-Key, Netzwerkfehler …), bleibt das
    Briefing benutzbar: die Schlagzeilen erscheinen dann im Original, und der
    Grund steht in der Statuszeile.
    """
    ergebnis = Uebersetzungsergebnis()
    if not schlagzeilen:
        return ergebnis

    cache_pfad = Path(cache_datei)
    cache = _lade_cache(cache_pfad)

    offen: list = []
    for schlagzeile in schlagzeilen:
        zwischengespeichert = cache.get(_schluessel(schlagzeile.titel))
        if zwischengespeichert:
            schlagzeile.uebersetzung = zwischengespeichert
            ergebnis.anzahl_aus_cache += 1
        else:
            offen.append(schlagzeile)

    if not offen:
        return ergebnis

    try:
        import anthropic
    except ImportError:
        ergebnis.fehler = (
            "Paket 'anthropic' nicht installiert — Schlagzeilen bleiben im Original "
            "(pip install anthropic)"
        )
        return ergebnis

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        ergebnis.fehler = (
            "Kein ANTHROPIC_API_KEY gesetzt — Schlagzeilen bleiben im Original"
        )
        return ergebnis

    try:
        client = anthropic.Anthropic()
        for start in range(0, len(offen), batch_groesse):
            teil = offen[start : start + batch_groesse]
            uebersetzungen = _uebersetze_batch(
                client, [s.titel for s in teil], modell, zielsprache
            )
            for nr, schlagzeile in enumerate(teil, start=1):
                text = uebersetzungen.get(nr, "")
                if text:
                    schlagzeile.uebersetzung = text
                    cache[_schluessel(schlagzeile.titel)] = text
                    ergebnis.anzahl_uebersetzt += 1
    except Exception as fehler:  # API-, Netz- oder Parse-Fehler
        ergebnis.fehler = f"Übersetzung unvollständig: {fehler}"

    _speichere_cache(cache_pfad, cache)
    return ergebnis
