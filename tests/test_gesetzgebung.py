"""Tests für die Gesetzgebung: Nationalrat, US-Kongress und ihre Darstellung.

Alles ohne Netz: Abrufe werden durch Fixtures ersetzt, die wie die echten
Antworten aufgebaut sind (Filter-API des Parlaments, senate.gov, clerk.house.gov,
api.congress.gov).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import urllib.error
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from briefing import fetch, kongress, nationalrat  # noqa: E402
from briefing.feeds import Konfiguration, Quelle, lade_konfiguration  # noqa: E402
from briefing.gesetzgebung import Beschluss, Gesetzgebungsergebnis, Partei  # noqa: E402
from briefing.render import rendere_briefing  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def lies(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def lies_json(name: str) -> dict:
    return json.loads(lies(name))


def http_fehler(url: str, code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "Fehler", {}, None)


class Ersatzabruf:
    """Ersetzt ``hole_daten`` in einem Modul durch eine Zuordnung URL → Antwort."""

    def __init__(self, modul, antworten):
        self.modul, self.antworten, self.abgerufen = modul, antworten, []

    def __enter__(self):
        self.original = self.modul.hole_daten

        def ersatz(url, json_daten=None, timeout=20, versuche=3, kopfzeilen=None):
            self.abgerufen.append(url)
            antwort = self.antworten(url) if callable(self.antworten) else self.antworten.get(url)
            if isinstance(antwort, Exception):
                raise antwort
            if antwort is None:
                raise http_fehler(url, 404)
            return antwort

        self.modul.hole_daten = ersatz
        return self

    def __exit__(self, *_):
        self.modul.hole_daten = self.original


# ---------------------------------------------------------------- Nationalrat


class TestNationalrat(unittest.TestCase):
    def test_nur_gesetzesbeschluesse_neueste_zuerst(self):
        beschluesse = nationalrat.parse_liste(lies_json("nr_filter.json"))
        nummern = [b.nummer for b in beschluesse]
        self.assertNotIn("53/BS", nummern)  # „Sonstiger Beschluss“ ist kein Gesetz
        self.assertEqual(nummern[:4], ["226/BNR", "221/BNR", "214/BNR", "212/BNR"])
        self.assertEqual(beschluesse[0].datum, date(2026, 10, 15))

    def test_felder_werden_ueber_spaltennamen_gelesen(self):
        beschluss = nationalrat.parse_liste(lies_json("nr_filter.json"))[0]
        self.assertEqual(beschluss.titel, "GeoSphere Austria-Gesetz")
        self.assertEqual(beschluss.link, "https://www.parlament.gv.at/gegenstand/XXVIII/BNR/226")
        self.assertEqual(beschluss.themen, ["Innovation, Technologie und Forschung", "Klima, Umwelt und Energie"])
        self.assertEqual(beschluss.gremium, "Nationalrat")

    def test_staatsvertrag_wird_erkannt(self):
        beschluesse = {b.nummer: b for b in nationalrat.parse_liste(lies_json("nr_filter.json"))}
        self.assertEqual(beschluesse["221/BNR"].art, "Staatsvertrag")

    def test_detail_liefert_gegenstand_und_verweis(self):
        beschluss = Beschluss(datum=date(2026, 9, 23), titel="AVG", nummer="207/BNR")
        bezug = nationalrat.ergaenze_detail(beschluss, lies_json("nr_beschluss_207.json"))
        self.assertEqual(bezug, "https://www.parlament.gv.at/gegenstand/XXVIII/I/539?json=true")
        self.assertTrue(beschluss.erlaeuterung.startswith("Ein Bundesgesetz, mit dem das Allgemeine"))
        self.assertNotIn("Beschluss des Nationalrates vom", beschluss.erlaeuterung)
        self.assertEqual(beschluss.art, "Bundesgesetz")

    def test_vorlage_liefert_abstimmung(self):
        beschluss = Beschluss(datum=date(2026, 9, 23), titel="AVG", erlaeuterung="Gegenstand")
        nationalrat.ergaenze_bezug(beschluss, lies_json("nr_vorlage_539.json"))
        self.assertEqual([p.name for p in beschluss.dafuer], ["ÖVP", "SPÖ", "NEOS"])
        self.assertEqual([p.name for p in beschluss.dagegen], ["FPÖ", "GRÜNE"])
        self.assertEqual(beschluss.parteien[0].farbe, "#0052FB")
        self.assertFalse(beschluss.einstimmig)
        # Korrespondenz-Meldungen decken ganze Debattenblöcke ab und würden oft
        # ein anderes Gesetz beschreiben — der Gegenstand bleibt stehen.
        self.assertEqual(beschluss.erlaeuterung, "Gegenstand")

    def test_einstimmig(self):
        beschluss = Beschluss(
            datum=date(2026, 10, 14), titel="x", parteien=[Partei("A", dafuer=True), Partei("B", dafuer=True)]
        )
        self.assertTrue(beschluss.einstimmig)

    def test_abruf_grenzt_auf_sieben_tage_ein_und_reichert_an(self):
        def antworten(url):
            if url == nationalrat.FILTER_URL:
                return lies("nr_filter.json")
            if url.endswith("/BNR/214?json=true"):
                return lies("nr_beschluss_207.json")
            if url.endswith("/I/539?json=true"):
                return lies("nr_vorlage_539.json")
            return None  # übrige Detailseiten fehlen → Beschluss bleibt knapp

        with Ersatzabruf(nationalrat, antworten):
            ergebnis = nationalrat.hole_beschluesse(date(2026, 10, 19), tage=7)

        self.assertTrue(ergebnis.ok)
        self.assertEqual(
            [b.nummer for b in ergebnis.beschluesse], ["226/BNR", "221/BNR", "214/BNR", "212/BNR"]
        )
        self.assertEqual(ergebnis.zuletzt, date(2026, 10, 15))
        angereichert = next(b for b in ergebnis.beschluesse if b.nummer == "214/BNR")
        self.assertEqual(len(angereichert.parteien), 5)
        knapp = next(b for b in ergebnis.beschluesse if b.nummer == "212/BNR")
        self.assertEqual(knapp.erlaeuterung, "")
        self.assertEqual(ergebnis.status[0].anzahl, 4)

    def test_mehrere_perioden_werden_abgefragt(self):
        gesendet = {}
        original = nationalrat.hole_daten

        def ersatz(url, json_daten=None, **_):
            gesendet.update(json_daten or {})
            return lies("nr_filter.json") if url == nationalrat.FILTER_URL else b"{}"

        nationalrat.hole_daten = ersatz
        try:
            nationalrat.hole_beschluesse(date(2026, 10, 19), perioden=["XXVIII", "XXIX"])
        finally:
            nationalrat.hole_daten = original
        self.assertEqual(gesendet["GP_CODE"], ["XXVIII", "XXIX"])
        self.assertEqual(gesendet["VHG"], ["BNR"])

    def test_ausfall_der_schnittstelle_wird_gemeldet(self):
        with Ersatzabruf(nationalrat, lambda url: RuntimeError("HTTP Error 503")):
            ergebnis = nationalrat.hole_beschluesse(date(2026, 10, 19))
        self.assertFalse(ergebnis.ok)
        self.assertIn("503", ergebnis.fehlermeldungen[0])
        self.assertEqual(ergebnis.beschluesse, [])


# ------------------------------------------------------------------ Kongress

HOUSE_VORLAGE = """<?xml version="1.0" encoding="utf-8"?>
<rollcall-vote>
  <vote-metadata>
    <majority>R</majority>
    <congress>119</congress>
    <session>2nd</session>
    <chamber>U.S. House of Representatives</chamber>
    <rollcall-num>{nummer}</rollcall-num>
    <legis-num>{vorlage}</legis-num>
    <vote-question>{frage}</vote-question>
    <vote-type>2/3 YEA-AND-NAY</vote-type>
    <vote-result>{ergebnis}</vote-result>
    <action-date>{datum}</action-date>
    <action-time time-etz="19:05">7:05 PM</action-time>
    <vote-desc>{titel}</vote-desc>
    <vote-totals>
      <totals-by-party>
        <party>Republican</party>
        <yea-total>191</yea-total>
        <nay-total>14</nay-total>
      </totals-by-party>
      <totals-by-vote>
        <total-stub>Totals</total-stub>
        <yea-total>391</yea-total>
        <nay-total>24</nay-total>
        <present-total>0</present-total>
        <not-voting-total>16</not-voting-total>
      </totals-by-vote>
    </vote-totals>
  </vote-metadata>
  <vote-data>
    <recorded-vote><legislator name-id="X000001">Beispiel</legislator><vote>Yea</vote></recorded-vote>
"""  # bewusst abgeschnitten — so kommt die Datei mit dem Range-Abruf an


def house_datei(nummer, datum, frage="On Motion to Suspend the Rules and Pass", titel="Example Test Act",
                vorlage="H R 1234", ergebnis="Passed") -> bytes:
    return HOUSE_VORLAGE.format(
        nummer=nummer, datum=datum, frage=frage, titel=titel, vorlage=vorlage, ergebnis=ergebnis
    ).encode()


class TestKongressGrundlagen(unittest.TestCase):
    def test_kongress_und_sitzung(self):
        self.assertEqual(kongress.kongress_und_sitzung(2025), (119, 1))
        self.assertEqual(kongress.kongress_und_sitzung(2026), (119, 2))
        self.assertEqual(kongress.kongress_und_sitzung(2027), (120, 1))

    def test_vorlagen_und_links(self):
        self.assertEqual(
            kongress.vorlage("H R 1234", 119),
            ("H.R. 1234", "https://www.congress.gov/bill/119th-congress/house-bill/1234"),
        )
        self.assertEqual(kongress.vorlage("S.J.Res. 9", 119)[0], "S.J.Res. 9")
        self.assertEqual(
            kongress.vorlage("H CON RES 5", 121)[1],
            "https://www.congress.gov/bill/121st-congress/house-concurrent-resolution/5",
        )
        self.assertEqual(
            kongress.vorlage("PN1129", 119)[1], "https://www.congress.gov/nomination/119th-congress/1129"
        )
        self.assertEqual(kongress.vorlage("QUORUM", 119), ("QUORUM", ""))


class TestSenat(unittest.TestCase):
    def setUp(self):
        self.beschluesse, self.juengste = kongress.parse_senat(
            lies("senat_abstimmungen.xml"), date(2026, 9, 25), date(2026, 10, 2)
        )

    def test_nur_entscheidungen_in_der_sache(self):
        nummern = [b.nummer for b in self.beschluesse]
        self.assertEqual(nummern, ["PN 1129", "S.J.Res. 9", "H.R. 1234"])  # Cloture & Co. fallen weg

    def test_ergebnisse_und_stimmen(self):
        nominierung, resolution, gesetz = self.beschluesse
        self.assertEqual((nominierung.ergebnis, nominierung.art), ("bestätigt", "Personalie"))
        self.assertFalse(resolution.angenommen)
        self.assertEqual(resolution.ergebnis, "abgelehnt")
        self.assertEqual(gesetz.stimmen, "60 : 38")
        self.assertEqual(gesetz.titel, "Example Test Act")  # Vorspann „H.R. 1234 as Amended;“ weg
        self.assertEqual(gesetz.gremium, "Senat")
        self.assertEqual(gesetz.datum, date(2026, 9, 25))

    def test_juengste_abstimmung_fuer_den_leerhinweis(self):
        self.assertEqual(self.juengste, date(2026, 9, 30))
        leer, juengste = kongress.parse_senat(lies("senat_abstimmungen.xml"), date(2026, 10, 12), date(2026, 10, 19))
        self.assertEqual(leer, [])
        self.assertEqual(juengste, date(2026, 9, 30))


class TestRepraesentantenhaus(unittest.TestCase):
    def test_kopf_aus_abgeschnittener_datei(self):
        kopf = kongress.parse_house(house_datei(314, "16-Sep-2026").decode())
        self.assertEqual(kopf["datum"], date(2026, 9, 16))
        self.assertEqual((kopf["ja"], kopf["nein"]), ("391", "24"))  # Summe, nicht eine Partei
        beschluss = kongress.house_beschluss(kopf, 2026, 314)
        self.assertEqual(beschluss.nummer, "H.R. 1234")
        self.assertEqual(beschluss.stimmen, "391 : 24")
        self.assertEqual(beschluss.gremium, "Repräsentantenhaus")

    def test_verfahrensabstimmungen_fallen_weg(self):
        for frage, titel in (
            ("On Ordering the Previous Question", "Providing for consideration of the bill (H.R. 1234)"),
            ("On Agreeing to the Resolution", "Providing for consideration of the bill (H.R. 1234)"),
            ("On Agreeing to the Amendment", "Amendment to H.R. 1234"),
            ("On Motion to Recommit", "Example Test Act"),
            ("Call of the House", ""),
        ):
            kopf = kongress.parse_house(house_datei(5, "16-Sep-2026", frage=frage, titel=titel).decode())
            self.assertIsNone(kongress.house_beschluss(kopf, 2026, 5), frage)

    def test_letzte_nummer_ohne_und_mit_merker(self):
        abfragen = []

        def existiert(n):
            abfragen.append(n)
            return n <= 314

        self.assertEqual(kongress.letzte_nummer(existiert), 314)
        ohne_merker = len(abfragen)
        abfragen.clear()
        self.assertEqual(kongress.letzte_nummer(existiert, bekannt=313), 314)
        self.assertLessEqual(len(abfragen), 10)  # eine Runde knapp über dem Merker
        self.assertLess(len(abfragen), ohne_merker)
        self.assertEqual(kongress.letzte_nummer(lambda n: False), 0)

    def test_letzte_nummer_trifft_auch_die_raender(self):
        for jungste in (1, 2, 9, 128, 129, 700, 2999, 3000):
            self.assertEqual(kongress.letzte_nummer(lambda n, j=jungste: n <= j), jungste)
            self.assertEqual(kongress.letzte_nummer(lambda n, j=jungste: n <= j, bekannt=1), jungste)

    def test_abruf_liest_rueckwaerts_bis_zum_zeitraum(self):
        daten = {
            318: house_datei(318, "15-Oct-2026"),
            317: house_datei(317, "14-Oct-2026", frage="On Ordering the Previous Question",
                             titel="Providing for consideration of the bill (H.R. 1234)"),
            316: house_datei(316, "14-Oct-2026", vorlage="S 2403", titel="Retire through Ownership Act"),
            315: house_datei(315, "02-Oct-2026"),
        }

        def antworten(url):
            nummer = int(url.rsplit("roll", 1)[1].split(".")[0])
            return daten.get(nummer, house_datei(nummer, "01-Sep-2026") if nummer < 315 else None)

        with tempfile.TemporaryDirectory() as ordner:
            merker = Path(ordner) / "kongress.json"
            with Ersatzabruf(kongress, antworten):
                beschluesse, juengste = kongress.hole_house(date(2026, 10, 12), date(2026, 10, 19), 5, merker)
            self.assertEqual([b.nummer for b in beschluesse], ["H.R. 1234", "S. 2403"])
            self.assertEqual(juengste, date(2026, 10, 15))
            self.assertEqual(json.loads(merker.read_text())["2026"], 318)

            # Zweiter Lauf mit Merker: nur knapp darüber suchen, und rückwärts
            # nichts vor dem Zeitraum nachladen (315 ist schon zu alt).
            with Ersatzabruf(kongress, antworten) as abruf:
                zweiter, _ = kongress.hole_house(date(2026, 10, 12), date(2026, 10, 19), 5, merker)
            self.assertEqual(len(zweiter), 2)
            nummern = [int(url.rsplit("roll", 1)[1].split(".")[0]) for url in abruf.abgerufen]
            self.assertGreaterEqual(min(nummern), 315)
            self.assertLessEqual(len(nummern), 15)


class TestNeueGesetze(unittest.TestCase):
    def test_nur_gesetze_im_zeitraum(self):
        beschluesse, juengste = kongress.parse_gesetze(
            lies_json("kongress_gesetze.json"), date(2026, 10, 12), date(2026, 10, 19)
        )
        self.assertEqual([b.nummer for b in beschluesse], ["S. 2403", "S. 283"])
        self.assertEqual(beschluesse[0].art, "Public Law 119-124")
        self.assertEqual(beschluesse[0].ergebnis, "unterzeichnet")
        self.assertEqual(juengste, date(2026, 10, 15))

    def test_gesamtabruf_und_demo_schluessel(self):
        senat = kongress.SENAT_LISTE.format(kongress=119, sitzung=2)

        def antworten(url):
            if url == senat:
                return lies("senat_abstimmungen.xml")
            if "api.congress.gov" in url:
                return http_fehler(url, 429)
            return None  # Repräsentantenhaus: noch keine Abstimmung

        alt = os.environ.pop("CONGRESS_API_KEY", None)
        try:
            with Ersatzabruf(kongress, antworten) as abruf:
                ergebnis = kongress.hole_entscheidungen(date(2026, 10, 19), 7)
        finally:
            if alt is not None:
                os.environ["CONGRESS_API_KEY"] = alt
        self.assertTrue(ergebnis.ok)  # Senat und Haus gingen
        self.assertEqual(ergebnis.zuletzt, date(2026, 9, 30))
        self.assertTrue(any("CONGRESS_API_KEY" in h for h in ergebnis.hinweise))
        self.assertTrue(any("DEMO_KEY" in url for url in abruf.abgerufen))
        for status in ergebnis.status:
            self.assertNotIn("api_key", status.url)  # Schlüssel nie in die Seite

    def test_eigener_schluessel_wird_verwendet(self):
        os.environ["CONGRESS_API_KEY"] = "geheim123"
        try:
            with Ersatzabruf(kongress, lambda url: lies("kongress_gesetze.json") if "api.congress" in url else None) as abruf:
                ergebnis = kongress.hole_entscheidungen(date(2026, 10, 19), 7)
        finally:
            del os.environ["CONGRESS_API_KEY"]
        self.assertTrue(any("api_key=geheim123" in url for url in abruf.abgerufen))
        self.assertEqual(ergebnis.hinweise, [])
        self.assertEqual([b.nummer for b in ergebnis.beschluesse], ["S. 2403", "S. 283"])
        for status in ergebnis.status:
            self.assertNotIn("geheim123", status.url)


# ------------------------------------------------------------------ Rendering

JETZT = datetime(2026, 10, 19, 13, 0, tzinfo=ZoneInfo("Europe/Vienna"))


def _seite(gesetzgebung, **optionen):
    quelle = Quelle(id="orf", name="ORF.at", feeds=["https://rss.orf.at/news.xml"])
    ergebnis = fetch.QuellenErgebnis(
        quelle_id="orf",
        schlagzeilen=[fetch.Schlagzeile(titel="Eine Schlagzeile", link="https://orf.at/1")],
        status=[fetch.FeedStatus(url="https://rss.orf.at/news.xml", quelle_id="orf", ok=True, anzahl=1)],
    )
    return rendere_briefing(Konfiguration(quellen=[quelle]), {"orf": ergebnis}, JETZT,
                            gesetzgebung=gesetzgebung, **optionen)


def _nr(beschluesse, ok=True, zuletzt=None):
    ergebnis = Gesetzgebungsergebnis(id="nationalrat", name="Nationalrat", beschluesse=beschluesse,
                                     zuletzt=zuletzt)
    ergebnis.status.append(fetch.FeedStatus(url=nationalrat.FILTER_URL, quelle_id="nationalrat", ok=ok,
                                            fehler="" if ok else "HTTP Error 503"))
    return ergebnis


class TestDarstellung(unittest.TestCase):
    def test_gesetzgebung_steht_ganz_oben(self):
        beschluss = Beschluss(datum=date(2026, 10, 14), titel="Strafrechtsänderungsgesetz 2026", nummer="214/BNR")
        html = _seite({"nationalrat": _nr([beschluss])})
        self.assertLess(html.index('id="gesetzgebung"'), html.index('<h3 class="karte__name">ORF.at'))
        self.assertIn("Strafrechtsänderungsgesetz 2026", html)
        self.assertIn('class="kalender__monat">Okt<', html)

    def test_fuenf_sichtbar_rest_im_aufklapper(self):
        beschluesse = [Beschluss(datum=date(2026, 10, 14), titel=f"Gesetz {n}", nummer=f"{n}/BNR") for n in range(12)]
        html = _seite({"nationalrat": _nr(beschluesse)})
        self.assertIn("7 weitere Beschlüsse anzeigen", html)
        oben = html.split('id="gesetzgebung"')[1].split('<details class="mehr">')[0]
        self.assertEqual(oben.count('class="zeile beschluss"'), 5)

    def test_fraktionen_und_einstimmig(self):
        geteilt = Beschluss(datum=date(2026, 10, 14), titel="A", parteien=[
            Partei("ÖVP", "#62C3D0", True), Partei("FPÖ", "#0052FB", False)])
        einig = Beschluss(datum=date(2026, 10, 14), titel="B", parteien=[Partei("ÖVP", "#62C3D0", True)])
        html = _seite({"nationalrat": _nr([geteilt, einig])})
        self.assertIn("Dafür", html)
        self.assertIn("Dagegen", html)
        self.assertIn("Einstimmig", html)

    def test_unsichere_farbe_kommt_nicht_ins_stilattribut(self):
        boese = Beschluss(datum=date(2026, 10, 14), titel="A", parteien=[
            Partei("X", "red;background:url(https://evil)", True), Partei("Y", "#000", False)])
        html = _seite({"nationalrat": _nr([boese])})
        self.assertNotIn("evil", html)

    def test_leerer_zeitraum_nennt_den_letzten_beschluss(self):
        html = _seite({"nationalrat": _nr([], zuletzt=date(2026, 9, 28))})
        self.assertIn("Keine Gesetzesbeschlüsse in den letzten 7 Tagen", html)
        self.assertIn("Zuletzt: 28. September 2026", html)

    def test_ausfall_wird_angezeigt(self):
        html = _seite({"nationalrat": _nr([], ok=False)})
        self.assertIn("Daten konnten nicht abgerufen werden", html)
        self.assertIn("HTTP Error 503", html)

    def test_kongress_mit_uebersetzung_und_ergebnis(self):
        beschluss = Beschluss(datum=date(2026, 10, 15), titel="Retire through Ownership Act", nummer="S. 2403",
                              gremium="Präsident", art="Public Law 119-124", ergebnis="unterzeichnet",
                              uebersetzung="Gesetz zur Altersvorsorge durch Beteiligung")
        us = Gesetzgebungsergebnis(id="kongress", name="US-Kongress", beschluesse=[beschluss],
                                   hinweise=["Schlüssel fehlt"])
        us.status.append(fetch.FeedStatus(url="x", quelle_id="kongress", ok=True))
        html = _seite({"kongress": us})
        self.assertLess(html.index("Gesetz zur Altersvorsorge"), html.index("Retire through Ownership Act"))
        self.assertIn("ergebnis--gesetz", html)
        self.assertIn("Unterzeichnet", html)
        self.assertIn("Schlüssel fehlt", html)

    def test_titel_werden_maskiert(self):
        beschluss = Beschluss(datum=date(2026, 10, 14), titel="<img src=x onerror=alert(1)>")
        html = _seite({"nationalrat": _nr([beschluss])})
        self.assertNotIn("<img src=x", html)

    def test_ohne_gesetzgebung_kein_abschnitt(self):
        html = _seite(None)
        self.assertNotIn('id="gesetzgebung"', html)


class TestKonfiguration(unittest.TestCase):
    def test_gesetzgebung_ist_konfiguriert(self):
        konfiguration = lade_konfiguration(WURZEL / "config" / "feeds.json")
        self.assertTrue(konfiguration.gesetzgebung.aktiv)
        self.assertEqual(konfiguration.gesetzgebung.tage, 7)
        self.assertIn("XXVIII", konfiguration.gesetzgebung.gesetzgebungsperioden)

    def test_jede_quelle_hat_ein_kuerzel(self):
        konfiguration = lade_konfiguration(WURZEL / "config" / "feeds.json")
        for quelle in konfiguration.quellen:
            self.assertTrue(1 <= len(quelle.kuerzel) <= 3, quelle.id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
