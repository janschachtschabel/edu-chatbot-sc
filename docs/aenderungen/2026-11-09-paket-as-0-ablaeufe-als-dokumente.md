# Paket AS-0 — ein Dokument je Ablauf, Studio-Seite „Abläufe“ (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), §5b,
Entscheid E1 („eine Datei je Ablauf“).

## Was sich ändert

- **Ein Dokument je Ablauf.**
  - Vorher lagen alle Abläufe als Liste in `06-ablaeufe/katalog`. Wer einen speicherte, speicherte
    alle, und Werks- und eigene Fassung galten für alle zusammen.
  - Jetzt ist `06-ablaeufe` ein Ordner wie die Muster: `06-ablaeufe/<id>`, die Kennung ist der
    Schlüssel.
  - Anlegen, Kopieren und Löschen laufen über die vorhandenen Ordner-Wege (`POST /api/config/documents`,
    `DELETE /api/config/file`).
- **Neue und kopierte Abläufe sind aus.** Eine Kopie bekommt Kennung und Titel neu; der Titel gilt für
  die Sprache des Studios. Die Kopie startet aus, sonst lösten zwei aktive Abläufe dieselbe Wendung und
  denselben Knopf aus.
- **Kennung:** in der Form, die der Treiber liest:
  - Kleinbuchstaben, Ziffern und `_`;
  - am Anfang ein Buchstabe;
  - höchstens 40 Zeichen;
  - `katalog` ist vergeben.

  Speichern mit einer Kennung, die nicht zum Schlüssel passt, weist der Server ab
  (`documents.ablaufKey`). Zum Umbenennen eine Kopie anlegen.
- **Laufzeit:** `ausloeser` liest alle Dokumente unter `06-ablaeufe/`, sortiert nach Schlüssel. So
  bleibt „der erste passende gewinnt“ bei Wendungen stabil. Ein kaputtes Dokument wird übersprungen.
- **Laufende Läufe** laufen weiter: Die Fassung eines Laufs hängt nur an den Schritten, und die bleiben
  gleich (Test).
- **„Prüfen“** (`POST /api/config/ablauf-pruefen`) meldet zusätzlich `warnungen`, die das Speichern nicht
  sperren. Neu ist: Dieselbe Wendung steht in einem anderen aktiven Ablauf.
- **Liste:** `GET /api/config/ablaeufe` liefert je Ablauf Kennung, Titel, an/aus, Arten der Auslöser,
  benutzte Module und die Zahl der Befunde. Ein Dokument, das das Modell nicht besteht, steht mit
  `lesbar: false` darin und bleibt so reparierbar.
- **Studio:**
  - Eigene Seite „Abläufe“ in der Gruppe „Gemeinsam“; vorher ein Abschnitt der Seite „UI-Module“.
  - Die Liste zeigt je Ablauf den Titel und als Text „Kennung · an/aus · Auslöser · Befunde“. Ein
    fehlerhafter Ablauf ist markiert, und der Text sagt es auch ohne Farbe.
  - Neu, Kopieren und Löschen mit Rückfrage wie bei den Mustern.
  - „Prüfen“ und die Schrittfolge stehen an der Wurzel des Formulars.
  - Warnungen erscheinen als „Hinweis“, nicht als Fehler.
- **Alte Sicherungen** (Schnappschuss, Werkszustand, Datei) mit `06-ablaeufe/katalog` werden beim
  Wiederherstellen in Dokumente geteilt (`domain/ablauf_altbestand.py`).
- **Migration `0021`:** teilt eine vorhandene Zeile `06-ablaeufe/katalog` auf, ohne Angepasstes zu
  überschreiben. Zwei Dinge übernimmt sie nicht (Querschnitts-Review AS-0…AS-2):
  - Kennungen, die es nur in der stillgelegten eigenen Fassung gab. Die Migration nennt sie in
    ihrer Ausgabe, sie bleiben in `config_history` des Katalogs.
  - Die Basis einer eigenen Fassung (`eigene_basis`). Wer danach auf die eigene Fassung
    zurückschaltet, sieht „neue Werksfassung verfügbar“.
  - **Unberührt** (Inhalt gleich der gemerkten Werksfassung): Jeder Ablauf merkt sich seine eigene
    Prüfsumme als Werksbasis.
  - **Angepasst:** ohne Basis, der Ablauf gilt als eigen.
  - **Stillgelegte eigene Fassung:** wird je Kennung mit aufgeteilt.
  - **Löschvermerk** des Katalogs: wird zu einem Vermerk für den Werks-Ablauf `sammlungsstruktur`.
  - Vorhandene Dokumente bleiben unberührt.
  - Der Rückweg setzt den Katalog wieder zusammen.
  - Offline (`--sql`) schreibt die Migration nur einen Hinweis.
- `06-ablaeufe/katalog` ist **gestrichen**: Kein Schreibweg legt den Bereich wieder an, auch nicht in
  der alten Form.

## Wo

- **Backend:**
  - Modell: `domain/config_models/ablauf.py` (`ORDNER`, `RESERVIERT`, ohne `AblaufKatalogArea`) und
    `domain/config_models/__init__.py` (Gruppe, gestrichen).
  - Speichern und Kennungen: `api/config_guards.py` (Gruppe, Prüfung je Dokument),
    `api/config_kennungen.py` (Kennung im Feld `id`, Regel `ablauf_kennung_gueltig`) und
    `api/config_documents.py` (leerer Ablauf, Kopie).
  - Endpunkte: `api/config_ablauf.py` (Liste, Warnungen).
  - Laufzeit: `services/ablauf/ausloeser.py` (`_roh_liste`) und `services/ablauf/pruefung.py`
    (`wendungs_warnungen`).
  - Texte: `i18n/messages_dokumente.py`.
  - Migration: `alembic/versions/0021_ablauf_dokumente.py`.
  - Seed: `seeds/06-ablaeufe/sammlungsstruktur.yaml` (statt `katalog.yaml`).
- **Studio:**
  - Seite und Navigation: `studio-views.ts`, `views/curated-pages-gemeinsam.ts`.
  - Liste und Anlegen: `views/group-documents.ts` (Liste, Kennungen), `views/group-section.component.ts`
    und `views/ablauf-notiz.ts`.
  - Prüfen: `schema-form/schema-form.component.ts` („Prüfen“ an der Wurzel),
    `schema-form/ablauf-pruefen.component.ts` (Warnungen) und `core/ablauf-api.service.ts`.
  - Texte: `i18n/catalogue/ablaeufe-seite.ts`.
- **API-Vertrag:** `docs/api/openapi-*.json` (neu erzeugt).

## Tests

- **Backend:**
  - `test_ablauf_dokumente.py` (Postgres): anlegen, Kennungen, Konflikt, Kopie, Kennung passt zum
    Schlüssel, Prüfung beim Speichern, ein Ablauf speichert nur sich, Schlüssel ohne Blatt, löschen,
    Liste.
  - `test_ablauf_dokumente_laufzeit.py`: Ordner und Modell, Reihenfolge, kaputtes Dokument, Fassung
    vor und nach dem Umzug gleich, Wendungs-Warnung.
  - `test_migration_ablauf_dokumente.py`: unberührt, angepasst mit stillgelegter Fassung, vorhandene
    Dokumente, Löschvermerk, Rückweg.
  - Angepasst: 21 Testattrappen lesen jetzt `ausloeser._roh_liste`; dazu `test_ablauf_zug`,
    `test_ablauf_pruefung`, `test_ablauf_studio_k2c1`/`k2c4`, `test_config_models` und `test_seed_waechter`
    (liest die Gruppen aus `config_guards`).
- **Studio:**
  - `views/ablaeufe-seite.spec.ts`: Seite, Liste in beiden Sprachen, Anlegen mit Treiber-Kennung,
    „Prüfen“ an der Wurzel, Kennungsregeln, Notiz, leere Liste, Ladefehler, Liste nach dem Speichern.
  - Aus dem Review, Backend: `test_ablauf_altbestand.py`; dazu in `test_ablauf_dokumente.py`
    `frontmatter`, gestrichener Katalog und alte Sicherung, in `test_migration_ablauf_dokumente.py`
    der entfernte Werks-Ablauf und der importierte Katalog, in `test_ablauf_dokumente_laufzeit.py`
    ineinander enthaltene Wendungen.
  - Angepasst: die Specs mit dem echten Ablaufschema, nun ohne `ablaeufe.0`, sowie die Registry-Wächter
    (31 Ansichten, Paket `AS-0`, drei Ordner).

## Review (2026-11-09)

Ein frischer Reviewer: 2 hoch, 6 klein, 4 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| Hoch: Ein Feld `frontmatter` im Ablauf umging die Regel „Kennung = Schlüssel“, und `06-ablaeufe/katalog` ließ sich wieder anlegen (danach nicht mehr löschbar). | `kennung_von` liest bei Abläufen nur `id` (die Gruppe entscheidet, nicht die Form). Ein Ablauf ohne Kennung wird abgewiesen. Gestrichene Bereiche sind auch in einem Ordner nicht adressierbar (404). |
| Hoch: Eine Sicherung, ein Schnappschuss oder der Werkszustand von vor AS-0 verlor beim Wiederherstellen alle Abläufe; der Modus „exakt“ löschte die vorhandenen. | `domain/ablauf_altbestand.katalog_aufteilen` teilt einen alten Katalog beim Lesen jeder Sicherung in Dokumente, wie Migration 0021. |
| 0021 legte einen Werks-Ablauf wieder an, den die Redaktion aus dem Katalog entfernt hatte. | Fehlt er im Katalog, bekommt er einen Löschvermerk. |
| 0021: Ein aus dem Werk importierter Katalog ohne Basis (`updated_by: import`) galt danach als eigen. Der Rückweg setzte bei vorhandenen Abläufen auch einen Löschvermerk. | `updated_by` wird übernommen, der Ablauf bleibt anhebbar. Der Vermerk wird nur gesetzt, wenn kein Ablauf mehr da ist. Dass der Rückweg Basis und stillgelegte Fassungen verwirft, steht jetzt im Docstring (Notweg). |
| Die Wendungs-Warnung prüfte nur Gleichheit, die Laufzeit sucht aber Teilzeichenketten. | Gewarnt wird auch, wenn eine Wendung in einer anderen enthalten ist („überschneidet sich mit“). |
| Bei Hinweisen ohne Befund sagte die Live-Region „Keine Befunde.“ | „Keine Befunde, 1 Hinweis.“ |
| Die Liste zeigte nach dem Speichern den alten Stand und folgte keinem Sprachwechsel. | Bei Abläufen wird die Liste nach dem Speichern und beim Sprachwechsel neu geladen. |
| Abweichungen vom Plan: keine Module in der Liste, allgemeiner Leertext, Tests für leer/Fehler fehlten. | Module stehen im Zusatz („Module: …“). Eigener Leertext. Tests für leere Liste, Ladefehler und Liste nach dem Speichern ergänzt. |
| Kleinigkeiten: `_kopie_100` hatte 41 Zeichen; `katalog` fiel erst am Server auf. | Der Stamm wird je Endung gekürzt. `katalog` gilt im Studio als vergeben. |

**Browser-Abnahme** (Wegwerf-DB `boerdi_as0_browser`, Backend und Studio aus dem Staging): Die Seite
zeigt die Liste mit Stand. Anlegen bildet `sammlung_pruefen`. „Prüfen“ meldet „Keine Befunde.“ Nach
„aktiv“ und Speichern zeigt die Liste „an“. Konsole und Server-Log sind ohne Fehler.

Ein Fund dabei: „Prüfen und Schrittfolge“ stand achtmal da, einmal je Abschnitt des Formulars und
einmal am Ende. Behoben: Das Wurzelfeld trägt das Widget nicht mehr, das Formular setzt es genau einmal
ans Ende. Ein Test prüft „genau einmal“.

**Bewusst anders als im Plan §5b:**
- Den Schalter „aktiv“ gibt es im Formular des Ablaufs, nicht als eigenen Schalter in der Liste. Die
  Liste zeigt den Stand als Text. Ein zweiter Schreibweg neben dem offenen Formular hätte eigene
  Konfliktfälle gebraucht.
- Die Seite „UI-Module“ verweist im Einleitungstext auf „Abläufe“, ohne Link.
- Eine Kopie behält die Titel der anderen Sprachen aus der Vorlage.

## Betrieb

- Migration `0021`, dann `boerdi import-config --werksabgleich`. Studio- und Backend-Bild neu bauen.
- Eine alte Sicherung mit `06-ablaeufe/katalog` wird beim Wiederherstellen in Dokumente geteilt.
