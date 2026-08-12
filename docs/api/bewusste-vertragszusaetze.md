# Bewusste Vertragszusätze

`docs/api/openapi-v1.json` ist der eingefrorene Vertrag; `scripts/export_openapi.py --check`
vergleicht ihn **byte-genau**. Jede Abweichung ist rot — auch eine neue
Beschreibung oder ein neuer Query-Parameter.

Rot heißt zuerst: **nachsehen, nicht neu erzeugen.** Der Regelfall ist ein
Versehen, und genau das soll das Gate fangen.

Wenn ein Zusatz **gewollt** ist, gehört er in die Tabelle unten und der Vertrag
wird einmal neu erzeugt:

```bash
cd backend && uv run python scripts/export_openapi.py
```

`tests/test_openapi_additions.py` bewacht diese Datei in **beide** Richtungen:
jeder Eintrag muss im Vertrag existieren, und der Vertrag darf keine Operation
enthalten, die weder zum eingefrorenen Stand gehört noch hier steht. Wer eine
Route hinzufügt und das Dokument arglos neu erzeugt, wird also trotzdem
gestoppt. Dieselbe Bauart wie `BEWUSST_EINSPRACHIG` (i18n), `OHNE_BUCHUNG`
(Token-Buchung) und `NEUE_BEREICHE` (Config-Bereiche).

**Eingefrorener Stand** (P0-4, gemessen 2026-08-11 am unveränderten Dokument):
**86 Pfade, 114 Operationen** — 61 GET, 26 POST, 13 PUT, 11 DELETE, 3 HEAD.
Diese Zahlen stehen als Konstanten im Wächter und dürfen **nicht** nachgezogen
werden.

## Warum ein Zusatz überhaupt erlaubt ist

Die Prüfung schützt zwei Dinge, und nur eines steht bei einem Zusatz zur
Debatte (Nutzer-Entscheid 2026-08-11, ausführlich in
`docs/plans/2026-08-11-kostenueberwachung.md` §5.5):

* Die **ALT-Treue** („NEU bietet genau das, was ALT bot") ist an den Umbau
  gebunden und läuft mit der Stilllegung von ALT ohnehin ab (P11-Schritt 6).
* Die **Drift-Erkennung** — dass eine *versehentliche* Änderung auffällt — ist
  davon unabhängig und bleibt nach dem Neu-Erzeugen vollständig erhalten. Sie
  ist der bleibende Wert des Gates.

Kompatibilität steht nicht auf dem Spiel: Aufrufer sind Widget und Studio,
beide in diesem Repo; einen externen Verbraucher gibt es nicht.

## Die Zusätze

| Methode | Pfad | Grund |
|---|---|---|
| GET | `/api/usage/session/{session_id}` | K4 Kostenüberwachung: Token, Aufrufe und Betrag einer Sitzung. Könnte formal auch als zusätzlicher Schlüssel an `GET /api/sessions/{session_id}` hängen (untypisierte Antwort, byte-gleich) — steht aber bewusst neben der Zeitraum-Route, damit beide Fragen dieselbe Antwortform haben. |
| GET | `/api/usage/period` | K4 Kostenüberwachung: derselbe Wert über einen Zeitraum. Erzwingt die Vertragsänderung: `from`/`to` sind neue Query-Parameter, und die gibt es nicht gratis. Der Umweg über `scope` von `/api/quality/stats` wäre byte-frei gewesen, hätte aber die Beschreibung dieses Parameters zur Lüge gemacht. **Beschreibung am 2026-08-12 einmal nachgezogen** (Review-Befund 3): die Route weist Zeiträume über `MAX_PERIOD_DAYS` ab, und eine Beschreibung, die das verschweigt, wäre wieder eine Lüge. Abweichung damals gemessen: **genau ein Blatt** (`paths./api/usage/period.get.description`), keine neue Operation. |
| POST | `/api/agent` | A3 Agent-Endpunkt: ein Auftrag auf dem WLO-Bestand fuer Gastgeber ohne Chat-Rahmen (Browser-Plugin, edu-sharing). Laesst sich **nicht** an `/api/chat` anhaengen: andere Zielgruppe (Maschine statt Mensch), andere Eingabe (Sammlungs-ID, nodeIds, `result_schema`), andere Ausgabe (freies JSON statt Chat-Blase), andere Anmeldung (Studio-Schluessel statt oeffentlich). In `ChatRequest` gequetscht waere jedes zweite Feld unwahr — dieselbe Sorte Luege, die bei `scope` von `/api/quality/stats` schon einmal vermieden wurde. |
| POST | `/api/agent/stream` | Derselbe Auftrag als Server-Sent-Events. Kein Zierrat, sondern Anforderung: ein Lauf steht gemessen bis 23 s an einem einzigen MCP-Aufruf, und der Gastgeber soll sehen, woran gerade gearbeitet wird (`connected` → `phase*` → `result`/`error`, gleicher Rahmenvertrag wie `/api/chat/stream`). Eine Kopfzeile am POST haette das nicht geleistet: SSE ist eine eigene Antwortform, keine Variante. |
