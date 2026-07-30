"""Tests für die Übersetzung — ohne echte API-Aufrufe."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from briefing.fetch import Schlagzeile  # noqa: E402
from briefing.translate import (  # noqa: E402
    ANTWORT_SCHEMA,
    _uebersetze_batch,
    uebersetze_schlagzeilen,
)


class Textblock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class Antwort:
    def __init__(self, nutzlast: dict):
        self.content = [Textblock(json.dumps(nutzlast))]


class StubClient:
    """Minimaler Ersatz für ``anthropic.Anthropic`` — merkt sich die Aufrufe."""

    def __init__(self, nutzlast: dict):
        self.nutzlast = nutzlast
        self.aufrufe: list[dict] = []
        self.messages = self

    def create(self, **kwargs):
        self.aufrufe.append(kwargs)
        return Antwort(self.nutzlast)


class TestBatch(unittest.TestCase):
    def test_antwort_wird_auf_nummern_abgebildet(self):
        client = StubClient(
            {"uebersetzungen": [{"nr": 1, "de": "Erste"}, {"nr": 2, "de": "Zweite"}]}
        )
        ergebnis = _uebersetze_batch(client, ["First", "Second"], "claude-opus-5", "Deutsch")
        self.assertEqual(ergebnis, {1: "Erste", 2: "Zweite"})

    def test_anfrage_nutzt_structured_outputs(self):
        client = StubClient({"uebersetzungen": []})
        _uebersetze_batch(client, ["First"], "claude-opus-5", "Deutsch")
        anfrage = client.aufrufe[0]
        self.assertEqual(anfrage["model"], "claude-opus-5")
        self.assertEqual(anfrage["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(anfrage["output_config"]["format"]["schema"], ANTWORT_SCHEMA)
        self.assertEqual(anfrage["output_config"]["effort"], "low")
        # Keine auf Opus 5 entfernten Parameter mitschicken.
        for veraltet in ("temperature", "top_p", "top_k"):
            self.assertNotIn(veraltet, anfrage)
        self.assertIn("1. First", anfrage["messages"][0]["content"])

    def test_leere_uebersetzungen_werden_verworfen(self):
        client = StubClient({"uebersetzungen": [{"nr": 1, "de": "   "}]})
        self.assertEqual(_uebersetze_batch(client, ["First"], "claude-opus-5", "Deutsch"), {})

    def test_schema_erfuellt_die_regeln_fuer_structured_outputs(self):
        self.assertFalse(ANTWORT_SCHEMA["additionalProperties"])
        eintrag = ANTWORT_SCHEMA["properties"]["uebersetzungen"]["items"]
        self.assertFalse(eintrag["additionalProperties"])
        self.assertEqual(sorted(eintrag["required"]), ["de", "nr"])


class TestCacheUndFehlerpfade(unittest.TestCase):
    def test_cache_verhindert_erneuten_aufruf(self):
        schlagzeile = Schlagzeile(titel="Sample headline")
        with tempfile.TemporaryDirectory() as ordner:
            cache = Path(ordner) / "u.json"
            from briefing.translate import _schluessel

            cache.write_text(
                json.dumps({_schluessel("Sample headline"): "Beispiel-Schlagzeile"}),
                encoding="utf-8",
            )
            ergebnis = uebersetze_schlagzeilen([schlagzeile], cache_datei=cache)

        self.assertEqual(schlagzeile.uebersetzung, "Beispiel-Schlagzeile")
        self.assertEqual(ergebnis.anzahl_aus_cache, 1)
        self.assertEqual(ergebnis.anzahl_uebersetzt, 0)
        self.assertTrue(ergebnis.ok)

    def test_ohne_api_key_bleibt_das_original_stehen(self):
        import os

        schlagzeile = Schlagzeile(titel="Sample headline")
        alt = {k: os.environ.pop(k, None) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        try:
            with tempfile.TemporaryDirectory() as ordner:
                ergebnis = uebersetze_schlagzeilen(
                    [schlagzeile], cache_datei=Path(ordner) / "u.json"
                )
        finally:
            for schluessel, wert in alt.items():
                if wert is not None:
                    os.environ[schluessel] = wert

        self.assertFalse(ergebnis.ok)
        # Ohne installiertes SDK meldet die Funktion das fehlende Paket, sonst
        # den fehlenden Schlüssel — beides ist ein sauberer Rückfall.
        self.assertRegex(ergebnis.fehler, r"ANTHROPIC_API_KEY|anthropic' nicht installiert")
        self.assertEqual(schlagzeile.uebersetzung, "")  # Original bleibt nutzbar

    def test_leere_liste_ist_kein_fehler(self):
        ergebnis = uebersetze_schlagzeilen([])
        self.assertTrue(ergebnis.ok)


class TestSdkVertrag(unittest.TestCase):
    """Sichert ab, dass die verwendeten Parameter im SDK wirklich existieren."""

    def test_messages_create_kennt_die_verwendeten_parameter(self):
        try:
            import inspect

            from anthropic.resources.messages import Messages
        except ImportError:
            self.skipTest("Paket 'anthropic' nicht installiert")

        parameter = inspect.signature(Messages.create).parameters
        for name in ("model", "max_tokens", "system", "messages", "output_config"):
            self.assertIn(name, parameter, f"'{name}' fehlt in messages.create()")


if __name__ == "__main__":
    unittest.main(verbosity=2)
