"""Tests für den Rubrikfilter (Politik & Wirtschaft)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from briefing import fetch, rubriken  # noqa: E402
from briefing.feeds import Quelle, lade_konfiguration  # noqa: E402
from briefing.rubriken import Rubrikfilter  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def lies(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def hole_mit_fixture(quelle, dateiname, filter_=None):
    original = fetch.hole_feed
    fetch.hole_feed = lambda url, timeout=20, versuche=3: lies(dateiname)
    try:
        return fetch.hole_quelle(quelle, rubrikfilter=filter_ or Rubrikfilter())
    finally:
        fetch.hole_feed = original


class TestSignale(unittest.TestCase):
    def test_kategorien_werden_geparst(self):
        schlagzeilen, _ = fetch.parse_feed(lies("presse_politik.xml"), "presse")
        self.assertEqual(schlagzeilen[0].kategorien, ["Innenpolitik"])
        self.assertEqual(schlagzeilen[3].kategorien, [])

    def test_dc_subject_wird_als_kategorie_gelesen(self):
        schlagzeilen, _ = fetch.parse_feed(lies("orf_gemischt.xml"), "orf")
        self.assertEqual(schlagzeilen[0].kategorien, ["Inland"])
        self.assertEqual(schlagzeilen[2].kategorien, ["Sport"])

    def test_atom_kategorie_steht_im_attribut(self):
        atom = b"""<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry><title>Test</title><category term="Wirtschaft"/></entry>
        </feed>"""
        schlagzeilen, _ = fetch.parse_feed(atom, "x")
        self.assertEqual(schlagzeilen[0].kategorien, ["Wirtschaft"])

    def test_feedpfad_zaehlt_als_signal(self):
        self.assertIn("wirtschaft", rubriken.pfadsignale("https://www.derstandard.at/rss/wirtschaft"))
        self.assertIn("politics", rubriken.pfadsignale("https://feeds.bbci.co.uk/news/politics/rss.xml"))

    def test_artikelpfad_ohne_letzten_teil(self):
        # Die Überschrift am Ende darf nicht mitgelesen werden.
        signale = rubriken.artikelsignale(
            "https://www.diepresse.com/19000001/streit-ueber-sportbudget"
        )
        self.assertNotIn("streit-ueber-sportbudget", signale)
        signale = rubriken.artikelsignale(
            "https://www.spiegel.de/wirtschaft/unternehmen/musterfirma-a-123"
        )
        self.assertEqual(signale, ["wirtschaft", "unternehmen"])


class TestFilterlogik(unittest.TestCase):
    def setUp(self):
        self.filter = Rubrikfilter()

    def test_erlaubte_ressorts(self):
        for wert in ("Politik", "Wirtschaft", "Inland", "Ausland", "business", "politics"):
            self.assertTrue(self.filter.passt([wert]), wert)

    def test_gesperrte_ressorts(self):
        for wert in ("Sport", "Kultur", "Panorama", "Reise", "Wissenschaft"):
            self.assertFalse(self.filter.passt([wert]), wert)

    def test_teiltreffer_bei_zusammensetzungen(self):
        self.assertTrue(self.filter.passt(["Innenpolitik"]))
        self.assertTrue(self.filter.passt(["Außenpolitik"]))  # Umlaut wird normalisiert
        self.assertTrue(self.filter.passt(["Wirtschaftspolitik"]))

    def test_sperre_gewinnt_gegen_erlaubnis(self):
        self.assertFalse(self.filter.passt(["Kulturpolitik"]))
        self.assertFalse(self.filter.passt(["Sport", "Wirtschaft"]))

    def test_ohne_signal_kein_treffer(self):
        self.assertFalse(self.filter.passt([]))
        self.assertFalse(self.filter.passt(["", "  "]))

    def test_eigene_listen_aus_der_konfiguration(self):
        eigener = Rubrikfilter(erlaubt=["sport"], gesperrt=[])
        self.assertTrue(eigener.passt(["Sport"]))
        self.assertFalse(eigener.passt(["Wirtschaft"]))


class TestFilterImAbruf(unittest.TestCase):
    def test_orf_behaelt_nur_politik_und_wirtschaft(self):
        quelle = Quelle(id="orf", name="ORF.at", feeds=["https://rss.orf.at/news.xml"])
        ergebnis = hole_mit_fixture(quelle, "orf_gemischt.xml")

        titel = [s.titel for s in ergebnis.schlagzeilen]
        self.assertEqual(len(titel), 4)  # Inland, Wirtschaft, Ausland, Inland
        self.assertNotIn("Testteam gewinnt Beispielspiel", titel)
        self.assertNotIn("Musterfestspiele eröffnen Saison", titel)
        # Politik-Meldung mit „Sport" im Titel bleibt drin.
        self.assertIn("Streit über Sportbudget im Testausschuss", titel)
        self.assertEqual(ergebnis.status[0].gefiltert, 2)

    def test_gefundene_ressorts_werden_gemeldet(self):
        quelle = Quelle(id="orf", name="ORF.at", feeds=["https://rss.orf.at/news.xml"])
        ergebnis = hole_mit_fixture(quelle, "orf_gemischt.xml")
        self.assertIn("Sport", ergebnis.status[0].rubriken)
        self.assertIn("Inland", ergebnis.status[0].rubriken)

    def test_ressortfeed_wird_vollstaendig_uebernommen(self):
        """…/rss/Politik ist bereits das Ressort — die Redaktion hat sortiert.

        Deshalb bleiben auch Einträge ohne Ressortangabe und solche mit einem
        Schlagwort wie „Kultur" drin: „Kulturpolitischer Beirat" ist Politik.
        """
        quelle = Quelle(id="presse", name="Die Presse", feeds=["https://www.diepresse.com/rss/Politik"])
        ergebnis = hole_mit_fixture(quelle, "presse_politik.xml")

        titel = [s.titel for s in ergebnis.schlagzeilen]
        self.assertEqual(len(titel), 4)
        self.assertIn("Regierung einigt sich auf Muster-Paket", titel)
        self.assertIn("Eintrag ganz ohne Ressortangabe", titel)
        self.assertEqual(ergebnis.status[0].gefiltert, 0)

    def test_sammelfeed_derselben_quelle_wird_gefiltert(self):
        """Aus einem Sammelfeld (…/rss/home) entscheidet dagegen der Eintrag."""
        quelle = Quelle(id="presse", name="Die Presse", feeds=["https://www.diepresse.com/rss/home"])
        ergebnis = hole_mit_fixture(quelle, "presse_politik.xml")

        titel = [s.titel for s in ergebnis.schlagzeilen]
        self.assertIn("Regierung einigt sich auf Muster-Paket", titel)
        self.assertNotIn("Kulturpolitischer Beirat tagt zum ersten Mal", titel)
        self.assertNotIn("Eintrag ganz ohne Ressortangabe", titel)

    def test_quelle_ohne_filter_behaelt_alles(self):
        ft = Quelle(id="ft", name="FT", feeds=["https://www.ft.com/rss/home"], rubriken_filtern=False)
        ergebnis = hole_mit_fixture(ft, "orf_gemischt.xml")
        self.assertEqual(len(ergebnis.schlagzeilen), 6)
        self.assertEqual(ergebnis.status[0].gefiltert, 0)

    def test_abgeschalteter_filter_behaelt_alles(self):
        quelle = Quelle(id="orf", name="ORF.at", feeds=["https://rss.orf.at/news.xml"])
        ergebnis = hole_mit_fixture(quelle, "orf_gemischt.xml", Rubrikfilter(aktiv=False))
        self.assertEqual(len(ergebnis.schlagzeilen), 6)

    def test_leeres_ergebnis_wird_erklaert_statt_als_fehler(self):
        nur_sport = b"""<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>Spielbericht</title><link>https://x.at/a/b</link>
        <category>Sport</category></item></channel></rss>"""
        quelle = Quelle(id="x", name="X", feeds=["https://x.at/feed"])
        original = fetch.hole_feed
        fetch.hole_feed = lambda url, timeout=20, versuche=3: nur_sport
        try:
            ergebnis = fetch.hole_quelle(quelle, rubrikfilter=Rubrikfilter())
        finally:
            fetch.hole_feed = original

        self.assertEqual(ergebnis.schlagzeilen, [])
        self.assertTrue(ergebnis.status[0].ok)  # Der Feed war in Ordnung …
        self.assertIn("Politik/Wirtschaft", ergebnis.status[0].fehler)  # … nur unpassend.


class TestRessortfeeds(unittest.TestCase):
    """Ein Feed, dessen Adresse das Ressort nennt, wird komplett übernommen."""

    def test_ressortfeed_wird_erkannt(self):
        f = Rubrikfilter()
        self.assertTrue(rubriken.ist_ressortfeed("https://www.ots.at/rss/wirtschaft", f))
        self.assertTrue(rubriken.ist_ressortfeed("https://feeds.bbci.co.uk/news/politics/rss.xml", f))
        self.assertFalse(rubriken.ist_ressortfeed("https://rss.orf.at/news.xml", f))
        self.assertFalse(rubriken.ist_ressortfeed("https://www.ots.at/rss/kultur", f))

    def test_schlagwoerter_kippen_keine_ressortfeed_meldung(self):
        """Guardian verschlagwortet Wirtschaftsartikel u. a. mit „Television industry“."""
        feed = b"""<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>Sender streicht Sendung nach Streit</title>
        <link>https://www.theguardian.com/business/2026/jul/30/slug</link>
        <category>Television industry</category><category>Media</category></item>
        </channel></rss>"""
        quelle = Quelle(id="guardian", name="Guardian",
                        feeds=["https://www.theguardian.com/business/rss"])
        original = fetch.hole_feed
        fetch.hole_feed = lambda url, timeout=20, versuche=3: feed
        try:
            ergebnis = fetch.hole_quelle(quelle, rubrikfilter=Rubrikfilter())
        finally:
            fetch.hole_feed = original

        self.assertEqual(len(ergebnis.schlagzeilen), 1)
        self.assertEqual(ergebnis.status[0].gefiltert, 0)

    def test_sammelfeed_wird_weiterhin_je_eintrag_geprueft(self):
        quelle = Quelle(id="orf", name="ORF.at", feeds=["https://rss.orf.at/news.xml"])
        ergebnis = hole_mit_fixture(quelle, "orf_gemischt.xml")
        self.assertEqual(ergebnis.status[0].gefiltert, 2)  # Sport und Kultur raus


class TestKonfiguration(unittest.TestCase):
    def test_presse_und_apa_sind_konfiguriert(self):
        konfiguration = lade_konfiguration(WURZEL / "config" / "feeds.json")
        ids = [q.id for q in konfiguration.quellen]
        self.assertIn("presse", ids)
        self.assertIn("apa", ids)

    def test_nur_die_ft_ist_vom_filter_ausgenommen(self):
        konfiguration = lade_konfiguration(WURZEL / "config" / "feeds.json")
        self.assertTrue(konfiguration.rubrikfilter.aktiv)
        ohne_filter = [q.id for q in konfiguration.quellen if not q.rubriken_filtern]
        self.assertEqual(ohne_filter, ["ft"])

    def test_standardlisten_greifen_bei_leerer_angabe(self):
        konfiguration = lade_konfiguration(WURZEL / "config" / "feeds.json")
        self.assertIn("wirtschaft", konfiguration.rubrikfilter.erlaubt)
        self.assertIn("sport", konfiguration.rubrikfilter.gesperrt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
