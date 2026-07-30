"""Tests für Parser, Statusmeldungen und Rendering."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from briefing import fetch  # noqa: E402
from briefing.feeds import Konfiguration, Quelle, lade_konfiguration  # noqa: E402
from briefing.render import rendere_briefing  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def lies(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class TestOrfParser(unittest.TestCase):
    """Der ORF-Feed ist RSS 1.0/RDF — genau daran scheiterte die alte Spalte."""

    def test_rdf_eintraege_werden_gefunden(self):
        schlagzeilen, format_name = fetch.parse_feed(lies("orf_news.xml"), "orf")
        self.assertEqual(len(schlagzeilen), 3)
        self.assertEqual(format_name, "RSS 1.0 (RDF)")
        self.assertEqual(schlagzeilen[0].titel, "Testmeldung eins aus dem Inland")

    def test_alter_pfad_channel_item_findet_nichts(self):
        """Dokumentiert die Ursache: 'channel/item' liefert beim ORF null Treffer."""
        wurzel = ET.fromstring(lies("orf_news.xml"))
        self.assertEqual(wurzel.findall("channel/item"), [])
        self.assertEqual(wurzel.findall("./channel/item"), [])
        # Und ohne Namensraum-Präfix findet auch ein direktes 'item' nichts:
        self.assertEqual(wurzel.findall("item"), [])

    def test_datum_aus_dc_date(self):
        schlagzeilen, _ = fetch.parse_feed(lies("orf_news.xml"), "orf")
        erwartet = datetime(2026, 7, 30, 7, 12, tzinfo=ZoneInfo("Europe/Vienna"))
        self.assertEqual(schlagzeilen[0].veroeffentlicht, erwartet)

    def test_link_faellt_auf_rdf_about_zurueck(self):
        schlagzeilen, _ = fetch.parse_feed(lies("orf_news.xml"), "orf")
        ohne_link_element = schlagzeilen[2]
        self.assertEqual(ohne_link_element.link, "https://orf.at/stories/3300003/")

    def test_sortierung_neueste_zuerst(self):
        quelle = Quelle(id="orf", name="ORF.at", feeds=["https://rss.orf.at/news.xml"])
        ergebnis = self._hole_mit_fixture(quelle, "orf_news.xml")
        zeiten = [s.veroeffentlicht for s in ergebnis.schlagzeilen]
        self.assertEqual(zeiten, sorted(zeiten, reverse=True))

    def _hole_mit_fixture(self, quelle, dateiname):
        original = fetch.hole_feed
        fetch.hole_feed = lambda url, timeout=20, versuche=3: lies(dateiname)
        try:
            return fetch.hole_quelle(quelle)
        finally:
            fetch.hole_feed = original


class TestWeitereFormate(unittest.TestCase):
    def test_rss2(self):
        schlagzeilen, format_name = fetch.parse_feed(lies("ft_home.xml"), "ft")
        self.assertEqual(len(schlagzeilen), 3)
        self.assertTrue(format_name.startswith("RSS 2"))
        self.assertEqual(
            schlagzeilen[0].link,
            "https://www.ft.com/content/00000000-0000-0000-0000-000000000001",
        )
        self.assertIsNotNone(schlagzeilen[0].veroeffentlicht)

    def test_atom(self):
        schlagzeilen, format_name = fetch.parse_feed(lies("atom_beispiel.xml"), "demo")
        self.assertEqual(format_name, "Atom")
        self.assertEqual(len(schlagzeilen), 2)
        # rel="alternate" gewinnt gegen rel="self"
        self.assertEqual(schlagzeilen[0].link, "https://example.org/atom/1")

    def test_kaputtes_xml_wirft_parse_error(self):
        with self.assertRaises(ET.ParseError):
            fetch.parse_feed(b"<rss><channel><item></rss>", "kaputt")


class TestFeedStatus(unittest.TestCase):
    """Eine leere Spalte muss als Fehler sichtbar werden, nicht stillschweigend."""

    def _quelle(self):
        return Quelle(id="test", name="Test", feeds=["https://example.org/feed.xml"])

    def _mit_fetch(self, quelle, ersatz):
        original = fetch.hole_feed
        fetch.hole_feed = ersatz
        try:
            return fetch.hole_quelle(quelle)
        finally:
            fetch.hole_feed = original

    def test_netzwerkfehler_wird_gemeldet(self):
        def kaputt(url, timeout=20, versuche=3):
            raise RuntimeError("HTTP Error 403: Forbidden")

        ergebnis = self._mit_fetch(self._quelle(), kaputt)
        self.assertFalse(ergebnis.ok)
        self.assertIn("403", ergebnis.fehlermeldungen[0])

    def test_leerer_feed_gilt_als_fehler(self):
        leer = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'
        ergebnis = self._mit_fetch(self._quelle(), lambda url, timeout=20, versuche=3: leer)
        self.assertFalse(ergebnis.ok)
        self.assertIn("ohne Einträge", ergebnis.status[0].fehler)

    def test_doppelte_eintraege_werden_entfernt(self):
        quelle = Quelle(
            id="ft",
            name="FT",
            feeds=["https://www.ft.com/rss/home", "https://www.ft.com/rss/world"],
        )
        ergebnis = self._mit_fetch(quelle, lambda url, timeout=20, versuche=3: lies("ft_home.xml"))
        self.assertEqual(len(ergebnis.schlagzeilen), 3)  # nicht 6
        self.assertEqual(ergebnis.status[1].anzahl, 0)


class TestRendering(unittest.TestCase):
    def _briefing(self, anzahl=12, sichtbar=5, **quellenoptionen):
        quelle = Quelle(
            id="ft", name="Financial Times", feeds=["https://www.ft.com/rss/home"], **quellenoptionen
        )
        jetzt = datetime(2026, 7, 30, 8, 0, tzinfo=ZoneInfo("Europe/Vienna"))
        ergebnis = fetch.QuellenErgebnis(
            quelle_id="ft",
            schlagzeilen=[
                fetch.Schlagzeile(titel=f"Schlagzeile {n}", link=f"https://example.org/{n}")
                for n in range(anzahl)
            ],
            status=[fetch.FeedStatus(url="https://www.ft.com/rss/home", quelle_id="ft", ok=True, anzahl=anzahl)],
        )
        konfiguration = Konfiguration(sichtbare_schlagzeilen=sichtbar, quellen=[quelle])
        return rendere_briefing(konfiguration, {"ft": ergebnis}, jetzt)

    def test_nur_fuenf_sichtbar_rest_im_aufklapper(self):
        html = self._briefing(anzahl=57, sichtbar=5)
        haupt = html.split('<details class="mehr">')[0]
        self.assertEqual(haupt.count('class="zeile"'), 5)
        self.assertIn("52 weitere Schlagzeilen anzeigen", html)

    def test_kein_aufklapper_bei_wenigen_schlagzeilen(self):
        html = self._briefing(anzahl=3, sichtbar=5)
        self.assertNotIn('<details class="mehr">', html)

    def test_uebersetzung_steht_ueber_dem_original(self):
        jetzt = datetime(2026, 7, 30, 8, 0, tzinfo=ZoneInfo("Europe/Vienna"))
        schlagzeile = fetch.Schlagzeile(titel="Sample English headline", link="https://ft.com/1")
        schlagzeile.uebersetzung = "Deutsche Beispiel-Schlagzeile"
        quelle = Quelle(id="ft", name="FT", feeds=["x"], uebersetzen=True, sprache="en")
        ergebnis = fetch.QuellenErgebnis(
            quelle_id="ft",
            schlagzeilen=[schlagzeile],
            status=[fetch.FeedStatus(url="x", quelle_id="ft", ok=True, anzahl=1)],
        )
        html = rendere_briefing(Konfiguration(quellen=[quelle]), {"ft": ergebnis}, jetzt)
        position_deutsch = html.index("Deutsche Beispiel-Schlagzeile")
        position_original = html.index("Sample English headline")
        self.assertLess(position_deutsch, position_original)
        self.assertIn("übersetzt", html)

    def test_html_wird_maskiert(self):
        jetzt = datetime(2026, 7, 30, 8, 0, tzinfo=ZoneInfo("Europe/Vienna"))
        quelle = Quelle(id="x", name="X", feeds=["f"])
        ergebnis = fetch.QuellenErgebnis(
            quelle_id="x",
            schlagzeilen=[fetch.Schlagzeile(titel="<script>alert(1)</script>", link="https://a")],
            status=[fetch.FeedStatus(url="f", quelle_id="x", ok=True, anzahl=1)],
        )
        html = rendere_briefing(Konfiguration(quellen=[quelle]), {"x": ergebnis}, jetzt)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_fehler_erscheint_in_der_karte_und_im_status(self):
        jetzt = datetime(2026, 7, 30, 8, 0, tzinfo=ZoneInfo("Europe/Vienna"))
        quelle = Quelle(id="orf", name="ORF.at", feeds=["https://rss.orf.at/news.xml"])
        ergebnis = fetch.QuellenErgebnis(
            quelle_id="orf",
            status=[
                fetch.FeedStatus(
                    url="https://rss.orf.at/news.xml",
                    quelle_id="orf",
                    ok=False,
                    fehler="HTTP Error 403: Forbidden",
                )
            ],
        )
        html = rendere_briefing(Konfiguration(quellen=[quelle]), {"orf": ergebnis}, jetzt)
        self.assertIn("Feed konnte nicht gelesen werden", html)
        self.assertIn("HTTP Error 403", html)
        self.assertIn("pille--fehler", html)


class TestKonfiguration(unittest.TestCase):
    def test_beispielkonfiguration_ist_gueltig(self):
        konfiguration = lade_konfiguration(WURZEL / "config" / "feeds.json")
        self.assertGreaterEqual(len(konfiguration.quellen), 5)
        ids = [q.id for q in konfiguration.quellen]
        self.assertIn("orf", ids)
        ft = next(q for q in konfiguration.quellen if q.id == "ft")
        self.assertTrue(ft.uebersetzen)
        self.assertTrue(ft.hervorheben)
        self.assertEqual(konfiguration.sichtbare_schlagzeilen, 5)

    def test_doppelte_id_wird_abgelehnt(self):
        import json
        import tempfile

        daten = {"quellen": [{"id": "a", "feeds": ["u"]}, {"id": "a", "feeds": ["v"]}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as datei:
            json.dump(daten, datei)
            pfad = datei.name
        with self.assertRaises(ValueError):
            lade_konfiguration(pfad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
