# Paket S — schreibende Ablaufschritte mit Freigabe (2026-11-08)

Plan: [`plans/2026-11-08-paket-s-schreibende-schritte.md`](../plans/2026-11-08-paket-s-schreibende-schritte.md)
(Entscheide FS-1…FS-9 nach Empfehlung, Nutzer-Go „weiter mit dem nächsten Paket“).

## Was sich ändert

Ein Ablauf kann jetzt in WLO schreiben: einen Volltext anhängen (W1), Metadaten ändern, einsortieren. Er tut
das nur mit der **Freigabe der Person**, auf demselben Weg wie im Chat.

- **Schritt:** `typ: werkzeug` mit einem bestätigbaren WLO-Werkzeug (kein Plan, kein Löschen) und dem neuen
  Feld `freigabe`. Das Feld
  trägt den Satz über der Vorschau je Sprache, mindestens `de`.
  ```yaml
  - id: anhaengen
    typ: werkzeug
    werkzeug: wlo_attach_fulltext
    freigabe: {de: "Diesen Volltext an den Datensatz hängen?"}
    argumente: {nodeId: {$teil: ziel, pfad: nodeId}, markdown: {$teil: volltext, pfad: texte.report},
                source: binary}
    schreibt: angehaengt
    bei_fehler: nicht_angehaengt
  ```
- **Ablauf eines Laufs:**
  1. Der Schritt ruft das Werkzeug **ohne** Schlüssel. Der Server liefert die Vorschau.
  2. Der Chatbot merkt die Abnahme wie im Chat: mit Aufrufer, 10 Minuten gültig, mit einer Marke für den Lauf.
     Er zeigt Satz, Vorschau-Box und den Chip „Ja, so ausführen“. Der Lauf wartet (`wartet_freigabe`).
  3. „Ja“ (Chip oder getippt) löst der Vorlauf ein, nach derselben Zustimmungsprüfung (Liste → Veto → LLM).
     Danach geht der Lauf weiter:
     - Erfolg: Der strukturierte Teil der Antwort wird Teil `schreibt`, es folgt der nächste Schritt.
     - Abgelehnt: `bei_fehler`.
     - Keine Antwort: Der Lauf **endet** mit Fehler und „bitte in WLO nachsehen“. Es kann geschrieben sein,
       ein Folgeschritt auf falscher Annahme wäre schlimmer.
     - Ausgelastet: Der Lauf wartet, die Abnahme liegt bereit.
     - Schlüssel abgelaufen: Es kommt eine neue Vorschau, die Marke reist mit.
  4. Ein Nein verwirft die Abnahme wie im Chat. Der Lauf wartet; unter den Antworten steht
     „Vorschau erneut zeigen“, die Antwort auf die Vorlage bietet dazu „Ablauf abbrechen“.
  - „Nichts zu ändern“ (kein Schlüssel) gilt als Erfolg (`{"unveraendert": true}`).
  - Ohne Schreibrecht, mit Fehler oder ohne Vorschau: `bei_fehler`. Geschrieben wurde dann nichts.
- **Prüfung beim Speichern:**
  - Ein schreibendes Werkzeug ist nur erlaubt, wenn es bestätigbar ist und weder Plan noch Löschen ist, und
    der Schritt `freigabe.de` trägt.
  - Der Ablauf braucht die Voraussetzung `anmeldung`.
  - Ein fest eingetragener Schlüssel in `argumente` (`confirmToken`, `continuationToken`, `batchToken`) ist
    ein Befund.
  - `freigabe` an einem lesenden Werkzeug oder an einem anderen Schritttyp ist ein Befund.
  - Der Schritt wartet: Schleifen- und Längenprüfung halten dort an.
- **Studio:** Feld „Freigabe (Satz über der Vorschau)“ nur bei `werkzeug`. Leere Sätze gelten als nicht
  gesetzt.

## Geändert

- `domain/config_models/ablauf.py`: `Schritt.freigabe` (Vorgabe `None`, die Fassung bestehender Abläufe bleibt).
- `services/ablauf/werkzeuge.py`: `freigebbar()`.
- `services/ablauf/pruefung.py` und `pruefung_texte.py`: Befunde `schreibend` (neu formuliert),
  `freigabe_fehlt`, `freigabe_lesend`, `freigabe_typ`, `freigabe_anmeldung`, `schluessel_fest`;
  `schreibt_mit_freigabe`, `_wartet`.
- `services/ablauf/treiber.py`: `WARTET_FREIGABE`, `Vorlage`, `Umgebung.vorlegen`, `Ausgabe.freigabe`,
  `erneut_vorlegen`, `weiter_freigabe`.
- neu `services/ablauf/freigabe_zug.py`:
  - Vorlegen (`call_mcp_tool_antwort` ohne Schlüssel; Schlüssel aus `structuredContent.confirm`, sonst aus
    dem Text);
  - Merken, Knöpfe, Direktaktionen `ablauf_freigabe_erneut` und `ablauf_freigabe_abbrechen`;
  - Nachlauf `nach_einloesen`.
- `services/ablauf/zug_basis.py`, `zug.py`: der neue Wartezustand; die Antwort merkt die Abnahme und zeigt die Box.
- `services/write_approval.py`: Im Erfolgsweg bleibt der strukturierte Teil für den Nachlauf (eine Zeile).
- `graph/nodes/preflight.py`, `preflight_ablauf.py`: Nachlauf nach dem Einlösen, Direktaktionen.
- `services/turn_assembly.py`: „Vorschau erneut zeigen“ unter gewöhnlichen Antworten.
- `i18n/bot_text.py`: vier neue Texte (de/en).
- Studio: `fields-ablaeufe.ts` (de/en), `area-schemas.fixture.ts` neu exportiert; `docs/api/openapi-*.json`.

## Bewusst so

- **Kein eigenes Modul `ui_freigabe`** (FS-1). Box und Chip des Chats genügen, die Zustimmung läuft über
  einen einzigen Weg.
- **Keine Pläne und kein Löschen aus einem Ablauf.** Pläne laufen über mehrere Züge mit „Plan fortsetzen“
  (späteres Paket). Ob ein Ablauf löschen darf, entscheidet der Nutzer (offene Frage).
- **`freigabe` an `auftrag` später** (FS-4). Die B-API kennt heute nur lesende Flows.
- **Teile an das schreibende Werkzeug höchstens 64 KB** (`teil_verweise.MAX_BYTES`). Ein längerer Volltext
  fehlt beim Einsetzen, der Schritt geht zu `bei_fehler`.
- **Angaben über 256 KB werden nicht vorgelegt**, sonst wäre die Abnahme nicht einlösbar (`bei_fehler`).

## Review S1 (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 1 hoch, 5 klein, 3 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| Ein fest eingetragener Schlüssel in `argumente` (auch über `$teil`, etwa aus einem agent-Schritt) hätte beim Vorlegen geschrieben. | Befund `schluessel_fest`; der Treiber streicht die Schlüsselfelder vor dem Vorlegen zusätzlich. |
| `freigabe` an einem unbekannten Werkzeug meldete „schreibt nicht“ statt „unbekannt“. | Erst „unbekannt“. |
| `freigabe` an einem anderen Schritttyp blieb still. | Befund `freigabe_typ`. |
| `{"de": ""}` aus dem Studio galt als gesetzt. | Leere Sätze fallen weg. |
| Der `NurBei`-Wächter kannte das Feld nicht. | `ERWARTET` ergänzt. |
| Ein Ablauf hätte löschen dürfen. | Löschen ist ausgeschlossen, bis der Nutzer entscheidet. |
| Veraltete Docstrings, Testlücken | Nachgezogen; Tests für alle Fälle oben, Agent-Schritt, Anmeldung ohne Freigabe, Halt bei der Länge, Englisch. |

## Review S2/S3 (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 2 hoch, 8 klein, 4 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| Die Antwort des Ablaufs legte `entities` samt offener Abnahme (mit Schlüssel) in Debug und Verlauf. | Ohne `_`-Schlüssel, wie im Hauptweg (`turn_persist`). |
| Vorgelegt wurde auch in einer lesenden Einbettung oder mit einem im Studio verborgenen Werkzeug; das „ja“ verwarf still, der Lauf hing. | Vorgelegt wird nur, was eingelöst werden dürfte (`write_approval.nicht_einloesbar`), sonst `bei_fehler`. |
| Ein „ja“ nach der Frist tat nichts, der Knopf blieb aus. | Der Vorlauf fängt die abgelaufene Abnahme eines Laufs ab: Hinweis und „Vorschau erneut zeigen“. |
| Ein Konflikt nach dem Schreiben ließ den Lauf am Schritt stehen; ein zweites Vorlegen hätte doppelt geschrieben. | Der Lauf endet (`fehler`), die Antwort sagt „gespeichert, Ablauf nicht fortgeschrieben“. |
| Im Nachlauf speicherte eine verworfene Meldung, ein Abbruch blieb ungesagt. | Ohne Speichern; ein Abbruch wird angehängt. |
| Ein „ja“ zu einer alten Vorschau setzte einen neu gestarteten Lauf fort. | Jede Vorlage hat eine Kennung (`lauf.freigabe_id`, Marke `id`). |
| Erfolg galt als „kein Grund gesetzt“. | `reason: eingeloest` ausdrücklich. |
| Ausgelastet, keine Antwort oder Anmeldung abgewiesen beim Vorlegen beendete den Lauf; eine abgelehnte Vorschau nannte keinen Grund. | Der Lauf wartet mit „Vorschau erneut zeigen“; die Ablehnung nennt den Grund des Servers. |
| Das Ergebnis trug womöglich Schlüsselfelder. | Ohne `confirmToken`, `continuationToken`, `batchToken`, `confirm`. |
| Die Kennzeile der KI kannte `wartet_freigabe` nicht. | Ergänzt. |
| Testlücken | Tests für alle Punkte oben, echtes Vorlegen (Sperren, Größe, Text-Schlüssel, Ausfälle), Ergebnis ohne Schlüssel. |

Offen (in `offene-befunde-und-todo.md`):

- Der Nachlauf nach dem „ja“ läuft vor der Sicherheitsprüfung mit leeren Sperren. Das ist vertretbar, weil die
  Nachricht ein kurzes, geprüftes Ja ist.
- Ein „ja“ speichert zwei Nachrichten im Verlauf. Live ist es eine Blase.
- Unter gewöhnlichen Antworten steht nur „Vorschau erneut zeigen“, ohne „Ablauf abbrechen“ (Deckel der
  Schnellantworten).

## Gesamt-Review (2026-11-08)

Ein frischer Reviewer über das ganze Paket: 0 kritisch, 0 hoch, 4 klein, 2 Kleinigkeiten. Er fand keinen Weg,
ohne Zustimmung oder doppelt zu schreiben, und keinen, auf dem das Modell einen Schlüssel sieht. Behoben:

| Befund | Behebung |
|---|---|
| Ein Konflikt nach einer **Ablehnung** sagte „die Änderung ist gespeichert“ und beendete den Lauf. | Satz nach Grund. Bei einer Ablehnung wartet der Lauf weiter; bei offenem Ausgang endet er ohne „gespeichert“. |
| Eingebettet (E3, der Server beschreibt nur, die Seite schreibt) liefen die Folgeschritte sofort weiter. | **Eigener Entscheid:** Der Lauf endet mit „vorbereitet, die Seite führt es aus“, kein Folgeschritt auf einer Änderung, die noch fehlt. |
| Ein vom Modell erkanntes Ja nach der Frist verwarf still. | Es zählt das Urteil dieses Zugs (`zustimmung_pruefen.zugestimmt`). |
| Ein „ja“ in Gespräch A schrieb noch, nachdem die Person den Lauf in B abgebrochen hatte („nichts geändert“). | **Eigener Entscheid:** Vor dem Einlösen prüft der Vorlauf, ob der Lauf noch auf genau diese Vorlage wartet (`freigabe_id`); sonst schreibt er nicht und sagt es. Der Abbruch soll verbindlich sein. |
| Der stumm aufgefrischte Verweis wurde nicht festgeschrieben. | `update_session`. |
| Doppelter `_`-Filter ohne Hinweis. | Kommentar nennt den Validator. |

Dazu: Vor dem Einlösen wird die Verbindung nach dem Lesen des Laufs freigegeben (M7).

## Tests

- neu:
  - `backend/tests/test_paket_s.py` (S1, mit Review);
  - `backend/tests/test_paket_s_zug.py` (22; S2/S3: Vorlegen, Ja, abgelehnt, offen, ausgelastet, Nein → erneut,
    abbrechen, nichts zu ändern, ohne Vorschau, neu vorgelegt, ohne Marke, dazu die Review-Fälle).
- angepasst: `test_ablauf_studio_k2c1.py` (`freigabe` nur bei `werkzeug`).
- Volle Suiten: Backend 9033 grün, 5 übersprungen, 1 rot (Log-Wächter: zwei Logzeilen nannten `antwort`) — behoben, Wächter und Paket-Tests danach grün; Studio 2041 grün, eslint und ruff sauber.

## Betrieb

- Keine Migration, kein Seed geändert.
- Backend und Studio neu bauen.
- Ein Ablauf mit Freigabe-Schritt wirkt erst, wenn die Redaktion ihn anlegt und einschaltet. Der Werksbestand
  enthält keinen.
