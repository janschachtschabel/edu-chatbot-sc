# Bildungsstufen im Themenbaum, getippte Führung (Rückmeldung 20.11. nachmittags)

## Warum

Rückmeldung vom 20.11. nach dem Deploy von PR #92:

- Bei „Für wen ist er – welche Stufe?“ fehlten Stufen wie die Elementarbildung.
- „Führung“ getippt startete weder die eingebaute Tour noch den Ablauf „Führung durch WLO“. In den
  Auslöse-Phrasen der Tour stand nur „fuehre mich“ (ohne Umlaut, ein getipptes „führe mich“ traf
  nie) und Varianten mit „Tour“. Selbst der Text des Tour-Chips („Führe mich systematisch durch die
  Webseite.“) traf nicht. Die Führung als Ablauf übernimmt die Phrasen 1:1 (Erzeuger), hatte also
  dieselbe Lücke.

## Was

| Datei | Änderung |
|---|---|
| `backend/seeds/06-ablaeufe/themenbaum.yaml` | Schritt `stufe`: dazu Elementarbereich, Erwachsenenbildung, Fortbildung (Labels des WLO-Vokabulars `educationalContext`) |
| `backend/src/boerdi/services/ablauf/vorbelegung.py` | `STUFEN`: `elementarbereich`, `fortbildung` (Erwachsenenbildung gab es schon) — die Wahl wird Bildungsstufe des Entwurfs |
| `backend/seeds/01-base/website-tour.yaml` | `trigger_phrases`: „führe mich durch die“, „führ mich durch die“, „führe mich systematisch“, „webseitenführung“, „führung starten“, „starte die führung“, „starte eine führung“, „führung durch die“ — bewusst mit „durch die …“: „Führe mich zu Material über …“ bleibt eine Suche |
| `backend/seeds/06-ablaeufe/fuehrung.yaml` | neu erzeugt (`scripts/fuehrung_aus_tour.py`), Wendungen wie die Tour |

## Tests (zuerst rot, dann grün)

- `test_tg5_vorbelegung.py`: Elementarbereich, Erwachsenenbildung, Fortbildung werden Bildungsstufe;
  neu `test_jede_stufe_des_themenbaums_ist_ein_wlo_label` (jede Wahl am Schritt `stufe` ist ein
  WLO-Label oder bewusst keins) — rot: 3 Fälle.
- `test_fuehrung_wie_tour.py`: sechs getippte Sätze starten Tour und Ablauf (rot: 6), zwei Sätze
  lösen nichts aus („Führe mich zu Material über Bruchrechnung“, „Wer hat die Führung im Projekt?“);
  `test_der_seed_ist_der_frisch_erzeugte_stand` grün nach dem Erzeugen.
- Volle Backend-Suite mit der Stufen-Änderung: 12204 grün.

## Betrieb und Deploy

- Keine Migration, keine Variable. Nach dem Deploy `import-config --werksabgleich` (Seeds geändert).
  Hat die Redaktion die Tour oder die Führung im Studio angepasst, bleibt deren Fassung — dann die
  Phrasen dort nachtragen oder auf die Werksfassung umschalten.
- Welche Führung läuft: Der Tour-Chip geht an die eingebaute Tour, solange sie an ist (Studio „Tour &
  Lotse“). Die Führung als Ablauf startet nur, wenn die eingebaute Tour aus ist — dann steht unten die
  Leiste „Führung durch WLO“.
