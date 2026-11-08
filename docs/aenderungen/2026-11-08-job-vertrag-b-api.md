# Aufträge gegen den echten Job-Vertrag der B-API (2026-11-08)

Anlass: das B-API-Handbuch „Kestra-Flows über die B-API bereitstellen“ (07.11.2026) und eine Messung am Staging mit
dem Demo-Flow `edusharing.support/test-mit-jan`. Entscheid des Nutzers: Der **Chatbot** steuert die Flows (nicht
der MCP).

## Befund

Der Client (Paket K1a) war vor dem Vertrag gegen eine Attrappe gebaut. Als fertig galten dort `SUCCESS` und
`WARNING`. Die B-API meldet aber `SUCCEEDED`, gemessen am Staging. Ein fertiger Auftrag galt deshalb als
„unbekannter Stand“, und „Stand prüfen“ kam endlos wieder.

## Geändert

- **`services/auftraege/client.py`**
  - Statuswerte der B-API: `QUEUED`/`RUNNING` → läuft, `SUCCEEDED` → fertig, `FAILED`/`CANCELLED` → Fehler.
    Die Kestra-Namen bleiben als Rückfall.
  - `Stand` trägt `warnungen` (`warnings`) und `fehlercode` (`error.code`; dokumentiert ist nur `TIMEOUT`,
    unbekannte Codes bleiben Fehler).
  - Dateien tragen `verfuegbar`/`grund` (`available`/`reason`, Dateien verfallen nach 7 Tagen), nie die Adresse.
  - Start: 400 → Grund `eingaben`; 429 → `voll` mit `warte_s` aus `Retry-After`.
  - Neu `abbrechen()` (`DELETE /api/v1/jobs/{jobId}`; 200/202 = abgebrochen, 409 = schon fertig, 404 = fremd).
  - Neu `abbrechen_im_hintergrund()`: wirft nie und hält keine DB-Verbindung.
- **`services/ablauf/auftrag_zug.py`**: Ein Teilerfolg (`warnungen`) reist im Teil des Ergebnisses mit.
- **`services/ablauf/zug_basis.py`, `zug.py`**: Ein abgebrochener oder ersetzter wartender Lauf beendet seinen
  Auftrag auch bei der B-API. Das gilt nur mit dem Schlüssel der Person; mit `B_API_KEY` wäre der Job fremd.
- **`deploy/.env.example`**: Start-Pfad `/api/v1/jobs/flows/{flow}` als bekannter Wert. Freigeben nur Flows ohne
  Repository-Scopes.
- **`docs/offene-befunde-und-todo.md`**: K16, K21 und K22 sind geklärt, K18 (`X-Edu-User-Id`) bleibt offen.

## Nach dem Review

| Befund | Behebung |
|---|---|
| 1 (hoch): Der Abbruch ging vor dem Festschreiben raus. Ein Konflikt-Rollback ließ den Lauf auf einen schon beendeten Auftrag warten. | `_alten_auftrag_schliessen` und `schliessen` geben die Job-ID zurück. `bei_der_b_api_abbrechen` läuft erst nach `commit()`, genauso in `abbrechen()`. |
| 2: „Neues Vorhaben“, der Start eines anderen Ablaufs und „Arbeitsstand löschen“ ließen Jobs weiterlaufen. | Diese Wege beenden den Auftrag jetzt auch bei der B-API. Beim Löschen liest `ablage.offene_job_ids` die IDs vor der Kaskade. |
| 3: Ein gestarteter, wegen eines Konflikts nicht festgehaltener Auftrag lief weiter. | `nicht_festgehalten` bricht ihn ab (K21 ist geklärt). |
| 4: Der Hintergrund-Abbruch fing nur `AuftragFehler`. | Fängt jetzt jeden Fehler und loggt nur dessen Art. |
| 5: Nach einem abgewiesenen Schlüssel ging trotzdem ein DELETE raus. | Kein DELETE mehr mit dem gerade abgewiesenen Schlüssel. |
| Kleinere Punkte | DELETE mit 204 gilt als abgebrochen. `eingaben` steht im Docstring. Die Notiz in `.env.example` sagt, dass DELETE die Status-Adresse nutzt. |

Die zweite Prüfung fand nichts Blockierendes. Daraufhin:

- der Docstring von `vorgang_aktion` ist korrigiert, weil der Abbruch bei der B-API jetzt geht;
- zwei Tests sind dazugekommen: der Start eines anderen Ablaufs bricht ab, und ein Konflikt in `abbrechen()`
  sendet kein DELETE;
- drei Fälle ohne Abbruch bei der B-API stehen in `offene-befunde-und-todo.md` (K-Abschnitt): Verdrängen
  ab 3 Vorgängen, ein kleines Rennen beim Löschen, Aufbewahrung ohne Schlüssel.

## Gemessen am Staging (2026-11-07)

| Prüfung | Ergebnis |
|---|---|
| `GET /api/v1/jobs/flows` mit `X-API-KEY` bzw. `Bearer` | beide 200 |
| Start `test-mit-jan` nur mit `Bearer` | 202, `jobId`, `deadlineAt` = Start + 24 h |
| Status | `SUCCEEDED`, `outputs.status_code` = `"200"` (Text) |
| Lesen über die B-API mit `X-Edu-User-Id` = Benutzername, an einem eigenen Testknoten (danach gelöscht) | 200; ohne Kopf 400; erfundene Kennung 403 |

## Betrieb

Keine Migration, keine neue Variable. Aufträge bleiben aus, bis `B_API_JOBS_START_PATH` und `B_API_JOBS_FLOWS`
gesetzt sind. Der Schlüssel braucht unter JOBS das Privileg des Flows.

## Tests

- Neu: `tests/test_auftraege_vertrag.py` (17).
- Ergänzt: `tests/test_ablauf_auftrag.py`
  - Teilerfolg
  - Abbruch bei der B-API mit und ohne Schlüssel der Person
  - ersetzter Lauf
  - Konflikt beim Ersetzen
  - neues Vorhaben
  - Arbeitsstand löschen
  - abgewiesener Schlüssel
- `tests/test_auftraege_ablage.py`: `offene_job_ids` gegen Postgres.
