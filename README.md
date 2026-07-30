# Tägliche Nachrichten-Zusammenfassung

Erzeugt aus RSS-/Atom-Feeds ein einzelnes, in sich geschlossenes HTML-Briefing:
je Quelle die fünf aktuellsten Schlagzeilen offen, alle weiteren im Aufklapper,
die Financial Times zusätzlich vollständig und ins Deutsche übersetzt.

```bash
python3 generate_briefing.py            # Briefing für heute → out/briefing-JJJJ-MM-TT.html
python3 generate_briefing.py --demo     # Layout-Vorschau mit Beispieldaten, ohne Netz
```

## Was das Briefing kann

| | |
|---|---|
| **Erste fünf offen** | Je Quelle sind die fünf aktuellsten Schlagzeilen sichtbar; der Rest (auch 50+) steckt in einem Aufklapper und ist einen Klick entfernt. Über `sichtbare_schlagzeilen` einstellbar. |
| **Financial Times komplett** | Die FT wird aus drei Feeds (Home, World, Companies) zusammengeführt, dedupliziert und als hervorgehobene Karte oben angezeigt — deutsche Übersetzung als Haupttitel, englisches Original klein darunter. |
| **Übersetzung** | Über die Claude Messages API (`claude-opus-5`, Structured Outputs). Ergebnisse landen im Cache, ein zweiter Lauf am selben Tag kostet nichts. Ohne API-Key erscheinen die Schlagzeilen im Original — das Briefing bricht nicht ab. |
| **Feed-Status** | Unten steht je Feed: Status, erkanntes Format, Anzahl Einträge, Dauer. Eine leere Quelle wird als Fehler angezeigt statt still zu verschwinden. |
| **Bedienung** | Volltextsuche (Taste `/`), „Alle aufklappen“, Hell/Dunkel, Druckansicht. Keine externen Ressourcen, keine Tracker — eine Datei, die überall funktioniert. |

## Der ORF-Fehler (behoben)

Die ORF-Spalte war immer leer, weil `https://rss.orf.at/news.xml` **RSS 1.0 (RDF)**
ausliefert und nicht RSS 2.0:

```xml
<rdf:RDF xmlns="http://purl.org/rss/1.0/" …>
  <channel rdf:about="…"> … </channel>
  <item rdf:about="https://orf.at/stories/3300001/">   <!-- neben, nicht in <channel> -->
```

Damit läuft jeder Parser ins Leere, der `channel/item` sucht oder Namensräume
ignoriert — ohne Fehlermeldung, weil der Abruf technisch erfolgreich war.
`tests/test_briefing.py::test_alter_pfad_channel_item_findet_nichts` hält genau
das fest.

Behoben in `briefing/fetch.py`:

- Einträge werden über ihren *lokalen* Elementnamen (`item`/`entry`) im gesamten
  Baum gesucht — das deckt RSS 2.0, RSS 1.0/RDF und Atom mit einem Codepfad ab.
- Link-Ermittlung mit Rückfall auf `rdf:about` bzw. `<guid>`, weil ORF-Einträge
  nicht immer ein `<link>`-Element haben.
- Datum aus `pubDate`, `dc:date`, `published` oder `updated` (RFC 822 und ISO 8601).
- Eigener User-Agent: ORF und FT antworten auf den urllib-Standard-Header teils mit `403`.
- Ein Feed, der zwar lädt, aber keine Einträge liefert, gilt als **Fehler** und
  erscheint rot in der Karte und in der Statustabelle.

## Einrichtung

```bash
git clone <repo> && cd Zusammenfassung_Nachrichten_t-glich
pip install -r requirements.txt        # nur für die Übersetzung nötig
export ANTHROPIC_API_KEY=sk-ant-…      # ohne Key: FT bleibt englisch
python3 generate_briefing.py
```

Ohne Übersetzung läuft alles mit der Python-Standardbibliothek (ab 3.11).

### Täglich laufen lassen

```cron
30 6 * * * cd /pfad/zum/repo && ANTHROPIC_API_KEY=sk-ant-… /usr/bin/python3 generate_briefing.py >> log/briefing.log 2>&1
```

Der Aufruf schreibt je Quelle eine Zeile ins Log und beendet sich mit Code `1`,
wenn keine einzige Schlagzeile ankam — das lässt sich überwachen.

## Optionen

| Option | Wirkung |
|---|---|
| `--demo` | Beispieldaten statt echter Feeds (kein Netz, kein API-Key) |
| `--out DATEI` | Zielpfad (Standard: `out/briefing-JJJJ-MM-TT.html`) |
| `--sichtbar N` | Sichtbare Schlagzeilen je Quelle (Standard 5) |
| `--ohne-uebersetzung` | FT-Schlagzeilen im Original lassen |
| `--quelle ID` | Nur bestimmte Quellen (mehrfach angebbar), z. B. `--quelle orf --quelle ft` |
| `--timeout N` | Timeout je Feed in Sekunden (Standard 20) |
| `--config PFAD` | Andere Feed-Konfiguration verwenden |

## Quellen anpassen

Alles steckt in `config/feeds.json` — kein Code-Eingriff nötig:

```json
{
  "id": "ft",
  "name": "Financial Times",
  "kategorie": "International",
  "sprache": "en",
  "farbe": "#0f5499",
  "uebersetzen": true,
  "hervorheben": true,
  "alle_anzeigen": true,
  "feeds": ["https://www.ft.com/rss/home", "https://www.ft.com/rss/world"]
}
```

| Feld | Bedeutung |
|---|---|
| `feeds` | Beliebig viele Feed-URLs; die Einträge werden zusammengeführt und über Link/Titel dedupliziert |
| `kategorie` | Überschrift, unter der die Karte einsortiert wird |
| `farbe` | Akzentfarbe der Karte (oberer Rand, Punkt, Rangnummern) |
| `uebersetzen` | Schlagzeilen dieser Quelle übersetzen lassen |
| `hervorheben` | Karte über volle Breite ganz oben unter „Im Fokus“ |
| `alle_anzeigen` | Keine Obergrenze durch `max_schlagzeilen_pro_quelle` |

Weitere ORF-Feeds folgen dem gleichen Muster, z. B. `https://rss.orf.at/help.xml`
oder für Bundesländer `https://<land>.orf.at/stories/rss`. Ob ein Feed
funktioniert, steht nach dem nächsten Lauf in der Statustabelle.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

26 Tests, keine Netzwerkzugriffe: Parser für RDF/RSS 2.0/Atom, Datums- und
Link-Ermittlung, Deduplizierung, Fehlerstatus, Rendering (5 sichtbar +
Aufklapper, Übersetzungsreihenfolge, HTML-Maskierung), Konfigurationsprüfung
sowie Übersetzung mit Stub-Client (Structured Outputs, Cache, Verhalten ohne
API-Key).

## Aufbau

```
generate_briefing.py     CLI: holen → übersetzen → rendern
briefing/feeds.py        Konfiguration laden und prüfen
briefing/fetch.py        HTTP-Abruf + formatunabhängiger Parser (ORF-Fix)
briefing/translate.py    Übersetzung via Claude Messages API, mit Cache
briefing/render.py       HTML, CSS und JavaScript des Briefings
briefing/demo.py         Beispieldaten für --demo
config/feeds.json        Quellen und Einstellungen
```
