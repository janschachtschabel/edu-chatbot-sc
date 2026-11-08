# Paket K2c-1 — Ablauf-Editor im Studio: was das Backend dafür liefert (2026-11-08)

Plan: [`plans/2026-11-08-kestra-ablaeufe-komfort.md`](../plans/2026-11-08-kestra-ablaeufe-komfort.md), §K2c,
Zuschnitt in K2c-1…4. Dieses Teilpaket legt die Grundlage; sichtbar wird es im Studio mit K2c-2 (Felder je
Schritttyp), K2c-3 (Argumente) und K2c-4 (Prüfen, Schrittfolge).

## Was sich ändert

- **Flow-Auswahl:** Das Feld `flow` eines Auftragsschritts zeigt im Studio die freigeschalteten Flows als
  Vorschlagsliste (Katalog `ablauf_flows` = `B_API_JOBS_FLOWS`, nur gültige Formen). Freitext bleibt möglich
  (offener Katalog wie überall); die Prüfung meldet einen nicht freigeschalteten Flow weiter.
- **Felder je Schritttyp:** Jedes Feld von `Schritt` sagt im Schema, bei welchem `typ` es gilt
  (`x-nur-bei: {feld: "typ", werte: […]}`). Das Studio nutzt das ab K2c-2.
- **Prüfen ohne Speichern:** `POST /api/config/ablauf-pruefen` (Studio-Schlüssel) nimmt einen Ablauf und gibt
  die Befunde je Schritt zurück: `{befunde: [{schritt, nr, text}]}` (`nr` = Stelle in `schritte`, eindeutig auch
  bei doppelten Kennungen), `schritt`/`nr: null` für den ganzen Ablauf. Es sind dieselben Befunde in derselben
  Reihenfolge wie die 400 beim Speichern.

## Geändert

- `domain/config_models/_shared.py`: Auszeichnung `NurBei(feld, *werte)`.
- `domain/config_models/ablauf.py`: `NurBei` an `text`, `modul`, `daten`, `werkzeug`, `flow`, `argumente`,
  `warten`, `schreibt`, `weiter`, `bei_fehler`, `agent`; `flow` mit `Catalog("ablauf_flows")`.
- `api/config_choices.py`: Katalog `ablauf_flows` (ohne Sprungziel — ein Flow wird in Kestra gepflegt);
  `services/auftraege/client.py`: `freigeschaltete_flows()`.
- `services/ablauf/pruefung.py`: `pruefe_gegliedert()` liefert `(schritt, text)`; `pruefe()` ist dessen flache
  Liste (unverändert für Speichern und Wächter); `_laeufe` nennt den Schritt.
- neu `api/config_ablauf.py` (Router mit Studio-Schlüssel), eingehängt in `main.py`.
- Studio: `schema-form/json-schema.ts` kennt `x-nur-bei` (nur der Typ); Schema-Fixture neu erzeugt.
- Vertrag neu erzeugt; Eintrag in `api/bewusste-vertragszusaetze.md`; Routen-Inventar in
  `test_openapi_contract.py`.

## Bewusst so

- **Flow-Liste ohne Abruf bei der B-API** (Abweichung vom Plan): `GET /api/config/choices` lädt alle Kataloge eines
  Formulars in einem Zug und ruft keinen Fremddienst. Die Eingaben eines Flows kommen erst mit einem eigenen Abruf,
  wenn die B-API sie nennt.
- **Die Auszeichnung ändert keine Fassung:** Sie steht nur im Schema; die Fassung eines Ablaufs hängt an den Daten
  (`treiber.fassung`, `exclude_none`). Ein Test hält das fest.

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 0 hoch. Die Zuordnung der Felder zu den Schritttypen, die unveränderte Fassung
(286 Eingaben verglichen) und die Gleichheit von `pruefe_gegliedert` mit dem alten `pruefe` hat er am Quelltext
bestätigt. Behoben:

| Befund | Behebung |
|---|---|
| Der Fassungs-Test verglich den neuen Stand mit sich selbst. | Die Fassung, die main für dieselben Daten rechnet, steht wörtlich im Test. |
| „flach = gegliedert“ war per Bau immer wahr. | Goldwerte: die Befunde, die `pruefe` auf main für zwei Abläufe mit vielen Befunden meldet (de/en), wörtlich. |
| Der Flow-Katalog ignorierte, ob Aufträge überhaupt eingerichtet sind. | Ohne Startpfad keine Vorschläge. |
| Bei doppelten Kennungen war ein Befund keinem Schritt eindeutig zuzuordnen. | `nr` (Index) neben `schritt`. |
| Vertragseintrag nannte drei statt sieben Schemas. | Korrigiert, mit dem Hinweis, dass Felder von `Schritt`/`AblaufArea` jetzt zum v1-Vertrag gehören. |
| Älter: Kommentar an `daten`; sehr tief geschachtelte Daten → `RecursionError` (500). | Kommentar korrigiert; Tiefengrenze 32 in `_verweise`. |

Älter und offen (eigener Punkt in `offene-befunde-und-todo.md`): `nachfolger` zählt `bei_fehler` auch bei
`nachricht` und `verzweigung`, die ihn nie nehmen. Ein Befund dafür änderte das Speichern bestehender Abläufe.

## Tests

- neu `tests/test_ablauf_studio_k2c1.py`:
  - jedes Schrittfeld nennt seine Typen (Tabelle aus `treiber`/`pruefung`);
  - Daten und Fassung bleiben gleich;
  - der Flow-Katalog ist die Freischaltliste;
  - `ablauf-pruefen`: 401 ohne Schlüssel, keine Befunde, Befunde am Schritt, Befunde des Ablaufs, Englisch über
    `Accept-Language`, 422;
  - `pruefe` ist die flache Liste von `pruefe_gegliedert`.
- Studio: die volle Suite (1978) mit der neuen Fixture.

## Betrieb

Keine Migration und keine neue Variable; das Studio-Bündel wird ohnehin mit dem Image gebaut.
