"""Tests für den Website-Modus (--site) und die App-Dateien."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from briefing import pwa  # noqa: E402
from briefing.feeds import Konfiguration, Quelle  # noqa: E402
from briefing.fetch import FeedStatus, QuellenErgebnis, Schlagzeile  # noqa: E402
from briefing.render import rendere_briefing  # noqa: E402
from generate_briefing import baue_website  # noqa: E402

JETZT = datetime(2026, 7, 30, 7, 0, tzinfo=ZoneInfo("Europe/Vienna"))


def beispiel_ergebnisse():
    quelle = Quelle(id="orf", name="ORF.at", feeds=["https://rss.orf.at/news.xml"])
    ergebnis = QuellenErgebnis(
        quelle_id="orf",
        schlagzeilen=[Schlagzeile(titel="Testmeldung", link="https://orf.at/1")],
        status=[FeedStatus(url="https://rss.orf.at/news.xml", quelle_id="orf", ok=True, anzahl=1)],
    )
    return Konfiguration(quellen=[quelle]), {"orf": ergebnis}


class TestWebsite(unittest.TestCase):
    def _bauen(self, ordner: Path, jetzt: datetime = JETZT, archiv_tage: int = 30):
        konfiguration, ergebnisse = beispiel_ergebnisse()

        def html_bauen(archiv):
            return rendere_briefing(
                konfiguration, ergebnisse, jetzt, web=True, archiv=archiv
            )

        return baue_website(ordner, html_bauen, jetzt, konfiguration.titel, archiv_tage)

    def test_erzeugt_index_archiv_und_app_dateien(self):
        with tempfile.TemporaryDirectory() as tmp:
            ordner = Path(tmp) / "docs"
            index = self._bauen(ordner)

            self.assertTrue(index.exists())
            self.assertTrue((ordner / "archiv" / "2026-07-30.html").exists())
            for datei in ("manifest.webmanifest", "sw.js", "icon-192.png",
                          "icon-512.png", "apple-touch-icon.png", ".nojekyll"):
                self.assertTrue((ordner / datei).exists(), f"{datei} fehlt")

    def test_alte_ausgaben_werden_entfernt_neuere_bleiben(self):
        with tempfile.TemporaryDirectory() as tmp:
            ordner = Path(tmp) / "docs"
            (ordner / "archiv").mkdir(parents=True)
            frisch = JETZT.date() - timedelta(days=3)
            alt = JETZT.date() - timedelta(days=40)
            for tag in (frisch, alt):
                (ordner / "archiv" / f"{tag}.html").write_text("alt", encoding="utf-8")
            (ordner / "archiv" / "kein-datum.html").write_text("x", encoding="utf-8")

            self._bauen(ordner, archiv_tage=30)

            self.assertTrue((ordner / "archiv" / f"{frisch}.html").exists())
            self.assertFalse((ordner / "archiv" / f"{alt}.html").exists())
            # Fremde Dateien werden nicht angefasst.
            self.assertTrue((ordner / "archiv" / "kein-datum.html").exists())

    def test_index_verlinkt_frühere_ausgaben(self):
        with tempfile.TemporaryDirectory() as tmp:
            ordner = Path(tmp) / "docs"
            (ordner / "archiv").mkdir(parents=True)
            gestern = JETZT.date() - timedelta(days=1)
            (ordner / "archiv" / f"{gestern}.html").write_text("alt", encoding="utf-8")

            index = self._bauen(ordner)
            html = index.read_text(encoding="utf-8")

            self.assertIn(f'href="archiv/{gestern}.html"', html)
            self.assertIn("Frühere Ausgaben", html)
            # Die heutige Ausgabe verlinkt sich nicht selbst.
            self.assertNotIn(f'href="archiv/{JETZT.date()}.html"', html)

    def test_zweiter_lauf_am_selben_tag_ueberschreibt(self):
        with tempfile.TemporaryDirectory() as tmp:
            ordner = Path(tmp) / "docs"
            self._bauen(ordner)
            self._bauen(ordner, jetzt=JETZT.replace(hour=19))

            ausgaben = list((ordner / "archiv").glob("*.html"))
            self.assertEqual(len(ausgaben), 1)
            self.assertIn("Stand 19:00", (ordner / "index.html").read_text(encoding="utf-8"))


class TestAppKopfzeilen(unittest.TestCase):
    def test_web_modus_bringt_manifest_und_service_worker(self):
        konfiguration, ergebnisse = beispiel_ergebnisse()
        html = rendere_briefing(konfiguration, ergebnisse, JETZT, web=True)

        self.assertIn('rel="manifest"', html)
        self.assertIn('rel="apple-touch-icon"', html)
        self.assertIn("apple-mobile-web-app-capable", html)
        self.assertIn("serviceWorker", html)
        self.assertIn('name="theme-color"', html)

    def test_ohne_web_modus_bleibt_die_datei_eigenstaendig(self):
        konfiguration, ergebnisse = beispiel_ergebnisse()
        html = rendere_briefing(konfiguration, ergebnisse, JETZT)

        # Lokal geöffnet (file://) gäbe es sonst tote Verweise.
        self.assertNotIn("manifest.webmanifest", html)
        self.assertNotIn("serviceWorker", html)

    def test_manifest_ist_gueltiges_json_mit_symbolen(self):
        daten = json.loads(pwa.manifest("Testbriefing"))
        self.assertEqual(daten["name"], "Testbriefing")
        self.assertEqual(daten["display"], "standalone")
        self.assertEqual(daten["start_url"], "./index.html")
        groessen = {symbol["sizes"] for symbol in daten["icons"]}
        self.assertEqual(groessen, {"192x192", "512x512"})
        self.assertTrue(any(s.get("purpose") == "maskable" for s in daten["icons"]))

    def test_service_worker_legt_vorrat_an(self):
        # Ohne Vorrat beim Installieren wäre die Seite beim ersten Offline-Start leer.
        self.assertIn("./index.html", pwa.SERVICE_WORKER)
        self.assertIn("install", pwa.SERVICE_WORKER)
        self.assertIn("caches.open(CACHE)", pwa.SERVICE_WORKER)

    def test_symbole_liegen_im_repo(self):
        for name in pwa.SYMBOLE:
            self.assertTrue((pwa.ASSETS / name).exists(), f"assets/{name} fehlt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
