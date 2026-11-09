# Paket K2c-4 — Studio: „Ablauf prüfen“ und die Schrittfolge (2026-11-08)

Plan: [`plans/2026-11-08-kestra-ablaeufe-komfort.md`](../plans/2026-11-08-kestra-ablaeufe-komfort.md), §K2c,
Teil K2c-4. Damit ist K2c fertig.

## Was die Redaktion sieht

Unter jedem Ablauf (Seite „UI-Module“ › Abläufe) steht ein Block **„Prüfen und Schrittfolge“**:

- **„Ablauf prüfen“** schickt den Entwurf an `POST /api/config/ablauf-pruefen` (K2c-1). Das ist dieselbe Prüfung
  wie beim Speichern, nur ohne zu speichern.
  - Die Befunde eines Schritts stehen **am Schritt**: als Meldung im Editor des Schritts, mit ⚠ in der Liste der
    Schritte (damit auch am Ablauf in der Liste der Abläufe) und in der Schrittfolge unter der Zeile des Schritts.
    Befunde des ganzen Ablaufs markieren die Liste nicht — sie stehen oben im Block.
  - Befunde des ganzen Ablaufs (zum Beispiel „Ein Auftrag braucht die Anmeldung“) stehen oben im Block.
  - Ein Entwurf, der das Modell noch nicht besteht (422, etwa eine Kennung mit Leerzeichen), zeigt dessen Meldungen
    im Block mit ihrer Stelle und am Feld — gibt es an der Stelle kein Feld (ein Zweig von `str | list[Weiter]`),
    am nächsten darüber.
  - Die Statuszeile (`role="status"`) nennt das Ergebnis: „Keine Befunde.“, „3 Befunde — an den Schritten
    markiert.“, „Prüfen ging nicht: …“.
- **Ein Stand, keine Sperre:** Die Befunde sperren das Speichern nicht. Ändert sich der Ablauf, verschwinden sie aus
  dem Formular, und der Knopf heißt „Erneut prüfen“ („Geändert seit der Prüfung — bitte erneut prüfen.“). Ein
  anderer Ablauf und „Verwerfen“ setzen den Block zurück.
- **Schrittfolge** (nur lesend, live aus dem Entwurf), je Schritt:
  - Kennung und Art, dann die Pfeile: `→ nächster`, `bei Fehler → …`;
  - bei einer Verzweigung je Regel `wenn Teil „draft“ da → …`, `wenn „ja“ gewählt → …`, `sonst → …`;
  - `Endet hier.` am `ende`-Schritt, `(Ende ohne „ende“-Schritt)` nach dem letzten oder ohne Pfeil;
  - eine Verzweigung ohne `sonst` zeigt zuletzt `greift keine Regel → (Ende ohne „ende“-Schritt)` — so läuft der
    Treiber aus;
  - ein Ziel, das es nicht gibt, ist fett und benannt („— diesen Schritt gibt es nicht“).

## Geändert

- **Backend**
  - `domain/config_models/ablauf.py`: `AblaufArea` trägt `x-widget: ablauf` (`model_config`). Nur Schema: Daten und
    Fassung bleiben.
  - Schema-Fixture und Vertrag neu erzeugt. Nur das Schema von `AblaufArea` ändert sich, keine neue Operation.
- **Studio** (`schema-form/`, `core/`)
  - neu `ablauf-folge.ts`: die Schrittfolge als reine Funktion, nach dem Treiber (`_rechne`, `_waehle`).
  - neu `ablauf-pruefen.component.ts`: der Block.
  - neu `form-befunde.ts`: `FORM_BEFUNDE` gibt Befunde einer Prüfung ohne Speichern an das Formular, je Quelle.
  - neu `core/ablauf-api.service.ts`: `AblaufApi.pruefen`.
  - `schema-form.component.ts`: stellt `FORM_BEFUNDE` bereit und mischt die Befunde in die Meldungen am Feld,
    hinter eine Meldung des Servers, nicht statt ihrer. „Verwerfen“ räumt sie.
  - `schema-to-fields.ts`: `widget: 'ablauf'` an einer Gruppe. `schema-field.component.{ts,html}` setzt den Block
    unter die Felder der Gruppe.
  - `_sf-meldungen.scss`: der Block. Ein Schritt mit Befund trägt einen Strich am Rand, nicht nur Farbe.
  - `i18n/catalogue/area-editor.ts`: `ablaufPruefen.*` (de/en); `en.spec.ts`: „→ {ziel}“ ist in beiden Sprachen
    gleich.

## Bewusst so

- Die Schrittfolge rechnet das Studio selbst. So ist sie live, auch ohne Knopfdruck. Die Prüfung beim Speichern
  bleibt die Instanz.
- Kein Grafik-Editor und kein Sprung aus der Schrittfolge in den Schritt; den Schritt wählt man in der Liste, wo
  er mit ⚠ markiert ist.

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 0 hoch, 2 mittel, 7 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| 422-Meldungen ohne passendes Feld (Zweig einer Union) verschwanden — nur ⚠, keine Meldung, obwohl die Statuszeile „am Feld markiert“ sagte. | Der Block nennt jede Meldung mit ihrer Stelle; im Formular steht sie am nächsten Feld darüber (`FormBefund` mit Pfad). |
| Eine Verzweigung ohne Regelliste zeigte „→ nächster“; der Treiber läuft dort aus. | Nach dem Treiber: ohne greifende Regel „greift keine Regel → (Ende …)“. |
| „Endet hier.“ an einem Nicht-`ende`-Schritt ohne Pfeil (`weiter: []`). | Nur am `ende`-Schritt; sonst „(Ende ohne „ende“-Schritt)“. |
| Kopfkommentar „dieselben Regeln wie `pruefung._normal`“ stimmte bei `sonst`+`dann` nicht. | Kommentar nennt die bewusste Abweichung. |
| Wechsel des Ablaufs während einer Prüfung: „Wird geprüft …“ und gesperrter Knopf bis zur (verworfenen) Antwort. | Je Anfrage eine Nummer; ein Wechsel gibt sofort frei. |
| Nach dem Löschen eines Ablaufs erbte der nächste an derselben Stelle den Stand. | Der Ablauf wird an Pfad **und** Kennung erkannt. |
| Dieselbe Meldung (Server und Prüfung) stand zweimal am Feld. | Nur einmal. |
| Nach Ablauf des Stands serialisierte jede Änderung den Ablauf erneut. | „alt“ wird fest gemerkt. |
| Notiz: Befunde des ganzen Ablaufs markieren die Liste nicht. | Notiz präzisiert. |

Offen und notiert: Der Treiber nimmt bei einem Nicht-Verzweigungsschritt mit `weiter: []` und `bei_fehler` auch im
Erfolgsfall `bei_fehler` (`nachfolger()[0]`) — eine Eigenheit des Treibers, die Prüfung meldet `weiter: []` nicht;
in `offene-befunde-und-todo.md`.

## Tests

- neu `schema-form/ablauf-folge.spec.ts` (5):
  - nächster Schritt und Auslaufen;
  - `ende` ohne Nachfolger;
  - Regeln wie der Treiber;
  - unbekannte Ziele;
  - falsche Form.
- neu `schema-form/ablauf-pruefen.component.spec.ts` (10):
  - Schrittfolge live;
  - Befunde am Schritt und im Formular, die des Ablaufs oben;
  - keine Befunde;
  - eine Änderung macht den Stand alt;
  - eine verspätete Antwort gilt nicht;
  - 422 am Feld ohne `body`;
  - ein anderer Fehler als Text;
  - anderer Ablauf und „Verwerfen“;
  - Abbau;
  - im echten Ablaufschema: Befund am Schritt, ⚠ an der Liste, **keine** Sperre des Speicherns, eine Änderung nimmt
    ihn weg.
    - Dieser Test fand einen Fehler: Das Formular reicht bei jedem Neuzeichnen ein neues Pfad-Feld herein, und das
      setzte den Block zurück. Verglichen wird jetzt der Pfad als Text.
- Backend: neu `tests/test_ablauf_studio_k2c4.py` (Auszeichnung nur am Ablauf, Daten unverändert); K2c-1/K2c-3
  und die Vertragsprüfungen grün.
- dazu (Review): 422 im Block mit Stelle, Wechsel während der Prüfung, anderer Ablauf an derselben Stelle,
  Verzweigung ohne greifende Regel, Schritt ohne Pfeil, Befund ohne Feld am nächsten darüber und keine doppelte
  Meldung.
- Studio-Suite 2033 grün (vor dem Integrationstest), eslint sauber.

## Betrieb

Nichts außer dem gewohnten Bau des Studio-Bündels.
