# Review MCP-Änderungen und UI-Module (2026-11-07)

Auftrag des Nutzers nach M1–M7: die MCP-bezogenen Änderungen und die UI-Module noch einmal prüfen und die Befunde
beheben. Vier unabhängige Reviews (MCP-Client und Schreibwege · Werkzeugkatalog, Prompt-Sicht, Seeds ·
UI-Module Frontend · UI-Module Backend), je am Quelltext und am MCP-Server geprüft. **Kein CRITICAL; 1 MAJOR,
14 MINOR, 9 NIT.** Alles behoben bis auf die unten genannten bewusst gelassenen Punkte.

## MCP-Client und Schreibwege (4 MINOR, 1 NIT)

- **Kein Schlüssel in Zugakte oder Protokoll:** geschwärzt werden jetzt `confirmToken`, `continuationToken` und
  `batchToken` (`SCHLUESSEL_FELDER` in `domain/write_confirm`; `services/zugakte`, `obs/log_inhalt`,
  `services/mcp/client`). Der Fortsetzungs-Schlüssel kann der eingelöste Bestätigungsschlüssel selbst sein.
- **`timeout` mit `outcomeOpen: false`** ist keine Ablehnung mehr: eigener Text `write.timeoutNothingDone`
  („nichts geändert, bitte einfach noch einmal“) statt „WLO hat abgelehnt … was soll ich anders machen?“.
- **Ein Platz für den offenen Plan:** solange ein eigener, anderer Plan offen ist, wird ein neuer nicht eingelöst
  (`write.planStillOpen` mit Knopf „Weiter anlegen“) — sonst verlöre der erste Schlüssel und Knopf und zählte bis zur
  Frist gegen die fünf Pläne je Anmeldung.
- **Strukturierter Teil ohne Schlüssel** (`unchanged`): kein Rückfall mehr auf den Vorschautext, in dem fremde
  Titel stehen (`nimm_bestaetigung` dreiwertig: `""` = strukturiert ohne Schlüssel, `None` = kein strukturierter Teil).
- **„Weiter anlegen“** beachtet die Sperren der Sicherheitsprüfung wie jede Direktaktion.

## Werkzeugkatalog, Prompt-Sicht, Seeds (6 MINOR, 2 NIT)

- `get_collection_overview`: die Beschreibung verspricht nur, was der Text trägt (Zahl der Inhalte/Untersammlungen;
  Aufschlüsselung über `get_collection_stats`; alle Skills mit Titel und nodeId; Karten nur über
  `browse_collection_tree`). Muster M08 sagt dasselbe.
- `count_wlo_content_matches`: Filter mit `additionalProperties: false`, die Beschreibung nennt die vier Filter
  (keine Lizenz) und dass der Chat Anfragen mit anderem Filter oder über 500 Zeichen nicht zählt — das Modell nennt
  sie als nicht gezählt.
- **Pläne:** eigene Fassung `_ZWEISTUFIG_PLAN` ohne „rufe … erneut auf“; Muster M18 (Kernregel, Schritt 5) mit der
  Ausnahme für Pläne.
- **Sammlungsbaum:** Schema bis Tiefe 4 mit `additionalProperties: false`; das Argument-Modell behält je Knoten nur
  `title`/`description`/`children`, die Paare nur `nodeId`/`collectionId` (der Server prüft jede Ebene streng).
- `browse_collection_tree`: `truncatedAt` richtig beschrieben; Master-Skill: der Katalog wird ohne `task` geholt.
- **Bewusst:** die Zählung behält ihre Beispiel-Titel auch im Gruppiermodus (Beleg für M19), die Übersicht hält
  ihre Inhaltsliste zurück.

## UI-Module Frontend (1 MAJOR, 2 MINOR, 2 NIT)

- **Fokus und Rollposition beim Übertragen (MAJOR):** die Ergebnisliste und ihre Links tragen Fokus-Schlüssel, die
  Rollposition übersteht das Neuzeichnen — vorher fiel der Fokus bei jeder fertigen Datei auf `body` und die Liste
  sprang nach oben.
- Das Upload-Element zeichnet nur bei echter Änderung neu (`daten`, `kontext` flach verglichen, `beschaeftigt`).
- Studio-Vorschau: der Link-Fang sieht über `composedPath()` auch in Shadow Roots nachgeladener Module.
- Linkbox und Themenbaum zeichnen ohne http(s)-Adresse keinen leeren Link.
- „Letzte Ablagen“: ohne Einträge keine leere Liste, Überschrift ohne „(0)“.

## UI-Module Backend (2 MINOR, 4 NIT)

- **Frisch gelesen vor dem Zurückschreiben:** `sitzung_entities_frisch` (`populate_existing`, `FOR UPDATE` bis zum
  Commit) in `api/ui_ablage._verweis_zurueckschreiben` — vorher hing die Frische am Zufall der Identity-Map.
- Rumpf-Grenze 16 KiB auch für `POST /api/ui/auftrag/stand`.
- Die Liste der letzten Ablagen wird auch beim Abbruch der Anfrage selbst abgebrochen.
- Eine Vorschau des MCP mit kaputtem Index → `abgewiesen` statt 500; ein unlesbarer Zähler macht nur seine Ablage
  unlesbar; ein zwischenzeitlich offener anderer Stapel meldet `stapel_offen` statt `nicht_gespeichert`.

## Älteres, nur eingetragen

In `offene-befunde-und-todo.md` §6 („Aus dem Review vom 2026-11-07“): Länge der Seitenadresse in
`page_duplicate`, fehlende Argument-Modelle einiger Lesewerkzeuge, ungerahmte Redaktions-Anweisung im Agent-Weg,
`get_wikipedia_summary` in der Personen-Sperre, Log-Level fachlicher Ablehnungen, ein Randfall im Tool-Loop.

## Beim Deploy

- Seeds geändert: `03-patterns/m08`, `m18` → `import-config --werksabgleich`. Master-Skill (`vorgehen.md`) geändert →
  neu in den WLO-Knoten.
- Image neu bauen (Widget, Module, Studio); `ui-upload` 17,9 kB gzip (Grenze 20 kB).

## Tests

- `backend/tests/test_review_2026_11_07.py` (neu, 9); `test_body_limit.py` (+1 Zeile), `test_ui_ablage_api.py`
  (Attrappe für das frische Lesen).
- Frontend: `ui-upload-uebertragen.element.spec.ts` (+2: Fokus bleibt in der Liste, gleiche Werte zeichnen nicht neu).
