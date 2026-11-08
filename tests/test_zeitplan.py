"""Tests für die Zeitsteuerung: Wann baut der stündlich angestoßene Workflow?"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from briefing import zeitplan  # noqa: E402
from briefing.feeds import lade_konfiguration  # noqa: E402

WIEN = ZoneInfo("Europe/Vienna")
TERMINE = [time(5, 0), time(13, 0), time(21, 0)]


def wien(*teile) -> datetime:
    return datetime(*teile, tzinfo=WIEN)


class TestLetzterTermin(unittest.TestCase):
    def test_tagsueber(self):
        self.assertEqual(zeitplan.letzter_termin(wien(2026, 11, 8, 9, 30), TERMINE), wien(2026, 11, 8, 5, 0))
        self.assertEqual(zeitplan.letzter_termin(wien(2026, 11, 8, 13, 0), TERMINE), wien(2026, 11, 8, 13, 0))
        self.assertEqual(zeitplan.letzter_termin(wien(2026, 11, 8, 23, 59), TERMINE), wien(2026, 11, 8, 21, 0))

    def test_vor_dem_ersten_termin_gilt_der_vortag(self):
        self.assertEqual(zeitplan.letzter_termin(wien(2026, 11, 8, 4, 59), TERMINE), wien(2026, 11, 7, 21, 0))
        self.assertEqual(zeitplan.letzter_termin(wien(2027, 1, 1, 0, 30), TERMINE), wien(2026, 12, 31, 21, 0))

    def test_zeitumstellung(self):
        # Sommerzeitbeginn (29.03.2026) und -ende (25.10.2026): 05:00 bleibt 05:00 Wiener Zeit.
        for tag in ((2026, 3, 29), (2026, 10, 25)):
            termin = zeitplan.letzter_termin(wien(*tag, 6, 0), TERMINE)
            self.assertEqual((termin.hour, termin.minute), (5, 0))
        self.assertEqual(zeitplan.letzter_termin(wien(2026, 3, 29, 6, 0), TERMINE).utcoffset().seconds, 7200)
        self.assertEqual(zeitplan.letzter_termin(wien(2026, 10, 25, 6, 0), TERMINE).utcoffset().seconds, 3600)


class TestFaellig(unittest.TestCase):
    def test_ohne_stand_wird_gebaut(self):
        self.assertTrue(zeitplan.ist_faellig(wien(2026, 11, 8, 9, 0), None, TERMINE))

    def test_verspaeteter_lauf_baut_trotzdem(self):
        # Letzte Ausgabe gestern 21:05; der Anstoß für 05:00 kommt erst um 11:36.
        letzte = wien(2026, 11, 7, 21, 5)
        self.assertTrue(zeitplan.ist_faellig(wien(2026, 11, 8, 11, 36), letzte, TERMINE))

    def test_weitere_laeufe_bis_zum_naechsten_termin_bauen_nicht(self):
        letzte = wien(2026, 11, 8, 5, 23)
        for stunde in (6, 9, 12):
            self.assertFalse(zeitplan.ist_faellig(wien(2026, 11, 8, stunde, 23), letzte, TERMINE))
        self.assertTrue(zeitplan.ist_faellig(wien(2026, 11, 8, 13, 23), letzte, TERMINE))

    def test_stand_in_anderer_zeitzone_wird_richtig_verglichen(self):
        # 04:30 UTC = 05:30 Wiener Winterzeit → der 05:00-Termin ist erledigt.
        letzte = datetime(2026, 11, 8, 4, 30, tzinfo=ZoneInfo("UTC"))
        self.assertFalse(zeitplan.ist_faellig(wien(2026, 11, 8, 9, 0), letzte, TERMINE))


class TestEingaben(unittest.TestCase):
    def test_termine_lesen(self):
        self.assertEqual(zeitplan.lies_termine(["21:00", "05:00", " 13:00"]), TERMINE)
        for falsch in (["5 Uhr"], ["25:00"], []):
            with self.assertRaises(ValueError):
                zeitplan.lies_termine(falsch)

    def test_stand_lesen(self):
        self.assertEqual(zeitplan.lies_stand("2026-11-08T05:23:10+01:00\n"), wien(2026, 11, 8, 5, 23, 10))
        for unbrauchbar in ("", "kaputt", "2026-11-08T05:23:10"):  # ohne Zone nicht vergleichbar
            self.assertIsNone(zeitplan.lies_stand(unbrauchbar))

    def test_konfigurierte_termine_sind_gueltig(self):
        konfiguration = lade_konfiguration(WURZEL / "config" / "feeds.json")
        self.assertEqual(zeitplan.lies_termine(konfiguration.ausgaben), TERMINE)

    def test_aufruf_liefert_eine_zeile_fuer_github_output(self):
        ausgabe, protokoll = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(ausgabe), contextlib.redirect_stderr(protokoll):
            zeitplan.main(["2000-01-01T00:00:00+00:00"])
        self.assertEqual(ausgabe.getvalue(), "faellig=true\n")
        self.assertIn("wird gebaut", protokoll.getvalue())


class TestStandDatei(unittest.TestCase):
    def test_website_schreibt_den_stand(self):
        import generate_briefing

        jetzt = wien(2026, 11, 8, 5, 23, 10)
        with tempfile.TemporaryDirectory() as ordner:
            generate_briefing.baue_website(Path(ordner), lambda archiv: "<html></html>", jetzt, "Briefing", 30)
            inhalt = (Path(ordner) / "stand.txt").read_text(encoding="utf-8")
        self.assertEqual(zeitplan.lies_stand(inhalt), jetzt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
