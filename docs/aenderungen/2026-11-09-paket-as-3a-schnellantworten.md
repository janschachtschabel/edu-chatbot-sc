# Paket AS-3a: Schnellantworten mit Ziel und Freitext (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), D2 und §5d.

## Was sich ändert

- **Schnellantworten an `nachricht` und `modul`:**
  - **Optionen:** Ein Schritt kann `optionen` tragen, je Option eine Kennung, ein Label je Sprache und ein Ziel.
  - **Freitext:** Ein Schritt kann `freitext` tragen, mit Ziel und dem Namen des Teils, den er schreibt.
  - **Warten:** Mit einem von beiden wartet der Schritt (`wartet_wahl`). Die Wahl verzweigt direkt, ein
    eigener `verzweigung`-Schritt ist nicht nötig. Die gewählte Kennung steht danach in `gewaehlt`;
    eine folgende Verzweigung kann sie mit „gewählt ist“ prüfen.
- **Im Chat:**
  - **Chips:** Die Optionen erscheinen als Chips unter der Antwort. Technisch sind es Direktaktionen
    `ablauf_wahl` mit Ablauf, Schritt und Wahl, so wie „Weiter im Ablauf“. Eine Wahl wirkt nur, wenn
    der Lauf dieser Person genau dort und in unveränderter Fassung wartet; sonst kommt „unbekannt“, und
    der Lauf bleibt stehen.
  - **Getippter Text gleich einem Label:** Er ist diese Wahl. Verglichen wird wie bei einer Wendung,
    also ohne Rücksicht auf Groß- und Kleinschreibung und Leerraum.
  - **Getippter Text mit Freitext:** An einem Schritt mit Freitext ist getippter Text die Antwort. Er
    wird ein Teil (Text, höchstens 2000 Zeichen) und gilt schon für die Schritte desselben Zugs. Er
    durchläuft dieselbe Sicherheitsprüfung wie jede Nachricht; bei hohem Risiko setzt er den Lauf
    nicht fort.
  - **Getippter Text ohne Freitext:** Er geht wie bisher an die KI. Solange der Lauf wartet, stehen die
    Chips auch unter jeder Antwort der KI; das ist der Weg zurück zum Ablauf.
  - **Nicht verwertbar:** Kann der Text nicht verwertet werden, weil der Lauf inzwischen anders steht,
    läuft der Zug den gewöhnlichen Weg.
- **Prüfung:**
  - höchstens 8 Optionen;
  - Kennungen eindeutig;
  - Label mindestens auf Deutsch;
  - jedes Ziel ist ein Schritt;
  - der Name des Freitext-Teils hat die übliche Form;
  - kein `weiter` daneben;
  - kein abfragendes Modul daneben, denn das wartet selbst;
  - nur an `nachricht` und `modul`.

  Erreichbarkeit und Schleifenprüfung sehen die neuen Ziele. Ein Schritt mit Wahl gilt als Halt.
- **Fassung:** Neue Felder haben die Vorgabe `None`, eine leere Liste aus dem Studio zählt wie nicht
  gesetzt. Die Fassung bestehender Abläufe bleibt also gleich, und kein wartender Lauf bricht beim
  Deploy ab.
- **Simulation:**
  - Testfälle nehmen an einem wartenden Schritt `option` (Kennung) oder `text`.
  - Eine Wahl, die der Schritt nicht anbietet, ist eine Abweichung.
  - In der Erwartung gibt es den Status `wartet_wahl`.
- **Studio:**
  - **Zielauswahl:** Die Ziele von Optionen und Freitext sind eine Auswahl der Schritte
    (`x-widget: schritt-ziel`). Der eigene Schritt steht als „dieser Schritt“ da; ein unbekanntes
    Ziel bleibt sichtbar und ist markiert.
  - **Schrittfolge und Ablaufbild:** Sie zeigen je Option einen Pfeil mit dem Label und einen Pfeil
    „getippter Text“.
  - **Regel-Editor:** An einem Schritt mit Wahl zeigt er statt der Arten den Hinweis „hier
    entscheidet die Schnellantwort“. Ein gesetztes `weiter` sperrt das Speichern und lässt sich mit
    „Weiter leeren“ entfernen.
  - **Feldtexte:** auf Deutsch und Englisch.

## Wo

- **Backend:**
  - `domain/config_models/ablauf.py`: `Schnellantwort`, `Freitext`, Felder an `Schritt`, `TestEingabe.option` und `text`, Status;
  - `domain/config_models/_shared.py`: `SchrittZiel()`;
  - `services/ablauf/pruefung.py`: `mit_wahl`, `wahl_ziele`, `_wahl`, `_normal`, `_wartet`;
  - `services/ablauf/pruefung_texte.py`;
  - `services/ablauf/treiber.py`: `WARTET_WAHL`, `wahl_angebot`, `weiter_wahl`, `Ausgabe.wahl`.
- **Zug:**
  - `services/ablauf/wahl_zug.py` (neu): Chips, Direktaktion, Freitext, Chips ohne Datenbank;
  - `services/ablauf/zug_basis.py`: Status, Chips der Antwort;
  - `services/ablauf/zug.py`: `lauf_wartet`;
  - `services/arbeitsstand_verweis.py`;
  - `graph/nodes/preflight.py`: Direktaktion hinter der Sicherheitsprüfung;
  - `graph/nodes/preflight_ablauf.py`: Freitext;
  - `services/turn_assembly.py`: Chips unter Antworten der KI;
  - `services/ablauf/simulation.py`.
- **Studio:**
  - `schema-form/schritt-ziel.component.ts` (neu), `schema-to-fields.ts`, `field-control.component.*`;
  - `ablauf-folge.ts`, `ablauf-bild*.ts`, `ablauf-schrittfolge.component.ts`;
  - `weiter-regeln.ts`, `weiter-editor.component.ts`;
  - Texte in `i18n/catalogue/fields-ablaeufe.ts` und `ablaeufe-seite.ts`.
- **Verträge:** `docs/api/openapi-v1.json`, `area-schemas.fixture.ts` neu erzeugt; Zeile in `docs/api/bewusste-vertragszusaetze.md`.

## Tests

- **Backend:**
  - `tests/test_ablauf_wahl.py`: Modell, Prüfung, Treiber, Simulation, Fassung;
  - `tests/test_ablauf_wahl_pg.py`: Zug gegen Postgres mit Chips, Wahl, falschem Schritt, Freitext und Chips ohne Datenbank;
  - `tests/test_preflight_node.py`: Direktaktion hinter der Prüfung, Freitext, hohes Risiko, Rückfall auf den gewöhnlichen Weg.
- **Studio:**
  - `schritt-ziel.component.spec.ts`;
  - neue Blöcke in `ablauf-folge.spec.ts`, `weiter-regeln.spec.ts` und `weiter-editor.component.spec.ts`.
- **Ergebnis:** Backend 881 gezielte Tests grün (Ablauf, Preflight, Chat, Verträge), Studio 170/170 grün; eslint, Tokens und a11y sauber.

## Betrieb

Keine Migration, keine neue Variable. Bestehende Abläufe behalten ihre Fassung. Das Image neu bauen
(Widget, Studio, Backend).

**Datenschutz:** Getippter Freitext an einem Ablaufschritt wird ein Teil des Vorgangs und liegt dort
bis zu dessen Frist (`vorgang_tage`). Das gilt unabhängig von `privacy-config.logging.messages`: Der
Text ist Arbeitsstand des Ablaufs, gehört der Person und geht mit dem Vorgang. Wer das nicht will,
nimmt keinen Freitext in den Ablauf.

## Review (2026-11-09)

Ein frischer Reviewer fand 2 hoch, 8 klein und einige Kleinigkeiten. Jeder Befund wurde am Quelltext nachgeprüft und behoben:

| Befund | Behebung |
|---|---|
| Hoch: Ein Freitext mit hohem Risiko bekam die Abweisung einer Direktaktion statt der Krisenantwort. | Ein Freitext geht bei hohem Risiko wie eine Wendung den gewöhnlichen Weg mit Krisenantwort (`preflight.py`). Der Test prüft das jetzt streng. |
| Hoch: Unter Antworten der KI standen höchstens 4 Chips (bzw. die Grenze des Gastgebers). Optionen 5 bis 8 waren dann nicht mehr erreichbar. | Die Chips einer Wahl werden nie gekürzt, nur andere Vorschläge fallen weg (`vorschlag.anhaengen(alle=True)`, Test). |
| Ein Lauf, dessen Ablauf sich änderte, wartete still weiter und sperrte Wendungen und Modul-Auslöser. | `wahl_zug.aufraeumen` bricht ihn vor der Sicherheitsprüfung ab, wie `zug.wartet_auf` (Test gegen Postgres). |
| Ein Fehler beim Rechnen und ein alter Chip sahen aus wie „Ablauf gibt es nicht“. | Ein Fehler ergibt „Fehler im Ablauf“. Ein alter Chip ergibt „Diese Wahl gilt nicht mehr“ und dazu die Chips, die jetzt gelten (Tests, auch für einen fremden Ablauf). |
| Die Vorschläge des Regel-Editors kannten weder die Schnellantworten noch den Freitext-Teil. | `wahlenAus` und `teileAus` lesen beide mit (Test). |
| Freitext ließ eine frühere Wahl in `gewaehlt` stehen. | Freitext leert `gewaehlt` (Test). |
| D2: Getippter Text gleich einem Label wurde nicht als Wahl erkannt. | Er ist jetzt diese Wahl (`wahl_aus_text`, Test). |
| Nach „Weiter leeren“ fiel der Fokus auf `body`. | Der Fokus geht an die Gruppe des Felds. |
| Die Zielauswahl kannte weder den Fehlerzustand des Formulars noch „Pflicht“. | `aria-invalid` gilt für unbekanntes Ziel oder abgelehnten Wert, dazu `aria-required`. |
| Testlücken | Neue Tests: Krisentest streng; alte Fassung im Zug; fremder Ablauf; Beschriftungen im Ablaufbild. |
| Kleinigkeiten | Die Kennzeile des Freitext-Teils lautet „Text“ statt eines Typnamens. Ein Label nur aus Leerraum zählt nicht. `weiter: ""` gilt als leer. Die Klasse heißt `Schnellantwort` statt `Option`. Plan und JSDoc sind nachgezogen. |

Prüfung: Backend 944 gezielte Tests grün (Ablauf, Preflight, Chat, Verträge, Texte); Studio 170/170 grün; eslint und a11y sauber.
