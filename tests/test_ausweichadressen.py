"""Tests für Ausweichadressen: eine falsche Schreibweise darf keine Quelle leeren."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from briefing import fetch  # noqa: E402
from briefing.feeds import Feedadresse, Quelle, lade_konfiguration  # noqa: E402
from briefing.rubriken import Rubrikfilter  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
INHALT = (FIXTURES / "presse_politik.xml").read_bytes()
LEERE_HUELLE = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'

AUS = Rubrikfilter(aktiv=False)


def mit_antworten(antworten: dict, quelle):
    """Ruft hole_quelle mit einer festen URL→Antwort-Zuordnung auf."""
    abgerufen: list[str] = []

    def ersatz(url, timeout=20, versuche=3):
        abgerufen.append(url)
        antwort = antworten.get(url)
        if antwort is None:
            raise RuntimeError("HTTP Error 404: Not Found")
        return antwort

    original = fetch.hole_feed
    fetch.hole_feed = ersatz
    try:
        return fetch.hole_quelle(quelle, rubrikfilter=AUS), abgerufen
    finally:
        fetch.hole_feed = original


class TestAusweichadressen(unittest.TestCase):
    def _quelle(self):
        return Quelle(
            id="presse",
            name="Die Presse",
            feeds=[
                Feedadresse(
                    url="https://www.diepresse.com/rss/Politik",
                    alternativen=["https://www.diepresse.com/rss/politik"],
                )
            ],
        )

    def test_haupadresse_wird_zuerst_genommen(self):
        ergebnis, abgerufen = mit_antworten(
            {"https://www.diepresse.com/rss/Politik": INHALT}, self._quelle()
        )
        self.assertEqual(len(ergebnis.schlagzeilen), 4)
        self.assertEqual(abgerufen, ["https://www.diepresse.com/rss/Politik"])
        self.assertEqual(ergebnis.status[0].fehler, "")

    def test_bei_404_greift_die_alternative(self):
        ergebnis, abgerufen = mit_antworten(
            {"https://www.diepresse.com/rss/politik": INHALT}, self._quelle()
        )
        self.assertEqual(len(ergebnis.schlagzeilen), 4)
        self.assertEqual(len(abgerufen), 2)  # erst die Haupt-, dann die Ausweichadresse
        self.assertEqual(ergebnis.status[0].url, "https://www.diepresse.com/rss/politik")
        self.assertIn("Ausweichadresse", ergebnis.status[0].fehler)

    def test_leere_aber_gueltige_antwort_zaehlt_nicht_als_treffer(self):
        # Manche Server antworten auf unbekannte Pfade mit einer leeren Hülle.
        ergebnis, _ = mit_antworten(
            {
                "https://www.diepresse.com/rss/Politik": LEERE_HUELLE,
                "https://www.diepresse.com/rss/politik": INHALT,
            },
            self._quelle(),
        )
        self.assertEqual(len(ergebnis.schlagzeilen), 4)
        self.assertEqual(ergebnis.status[0].url, "https://www.diepresse.com/rss/politik")

    def test_alle_adressen_kaputt_meldet_fehler(self):
        ergebnis, abgerufen = mit_antworten({}, self._quelle())
        self.assertFalse(ergebnis.ok)
        self.assertEqual(len(abgerufen), 2)
        self.assertIn("404", ergebnis.status[0].fehler)

    def test_reine_zeichenketten_bleiben_gueltig(self):
        quelle = Quelle(id="x", name="X", feeds=["https://x.at/feed"])
        self.assertIsInstance(quelle.feeds[0], Feedadresse)
        ergebnis, _ = mit_antworten({"https://x.at/feed": INHALT}, quelle)
        self.assertEqual(len(ergebnis.schlagzeilen), 4)

    def test_status_traegt_die_url_als_text(self):
        """Im Status muss die Adresse als Zeichenkette stehen — sie wird gerendert."""
        from datetime import datetime

        from briefing.demo import demo_ergebnis

        quelle = self._quelle()
        for status in demo_ergebnis(quelle, datetime(2026, 7, 30, 8, 0)).status:
            self.assertIsInstance(status.url, str)


class TestKonfigurierteAdressen(unittest.TestCase):
    def setUp(self):
        self.konfiguration = lade_konfiguration(WURZEL / "config" / "feeds.json")

    def _quelle(self, quelle_id):
        return next(q for q in self.konfiguration.quellen if q.id == quelle_id)

    def test_apa_nutzt_die_themenkanaele(self):
        adressen = [a.url for a in self._quelle("apa").feeds]
        self.assertIn("https://www.ots.at/rss/politik", adressen)
        self.assertIn("https://www.ots.at/rss/wirtschaft", adressen)

    def test_presse_hat_politik_und_wirtschaft(self):
        adressen = [a.url for a in self._quelle("presse").feeds]
        self.assertIn("https://www.diepresse.com/rss/Politik", adressen)
        self.assertIn("https://www.diepresse.com/rss/Wirtschaft", adressen)

    def test_heikle_adressen_haben_ausweichvarianten(self):
        for quelle_id in ("presse", "apa"):
            for adresse in self._quelle(quelle_id).feeds:
                self.assertTrue(
                    adresse.alternativen, f"{quelle_id}: {adresse.url} ohne Alternative"
                )

    def test_jeder_feedpfad_traegt_sein_ressort(self):
        """Feeds ohne Kategorie-Angaben brauchen das Ressort im Pfad."""
        from briefing.rubriken import pfadsignale

        # Nicht dabei: ORF (kein Ressort-Feed, filtert über <dc:subject>) und
        # die FT (ohne Rubrikfilter).
        for quelle_id in (
            "presse", "apa", "standard", "tagesschau", "spiegel", "zeit", "bbc", "guardian",
        ):
            for adresse in self._quelle(quelle_id).feeds:
                signale = pfadsignale(adresse.url)
                self.assertTrue(
                    self.konfiguration.rubrikfilter.passt(signale),
                    f"{quelle_id}: {adresse.url} liefert kein Ressort-Signal",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
