# Änderungsnotiz — Paket 18C/D, Phase 1: Trace-ID und Zugakte je Zug

Stand 2026-10-29 · Basis `main` `2debba7` · Plan [`docs/plans/2026-10-29-paket-18cd-volle-umsetzung.md`](../plans/2026-10-29-paket-18cd-volle-umsetzung.md)
(Entscheidungsgrundlage: [`…-paket-18cd-datenbedarf.md`](../plans/2026-10-29-paket-18cd-datenbedarf.md))

**Warum:** Das Störtest-Audit (18C) fand Inhalte in den Logs: Suchbegriffe, Werkzeug-Argumente,
Antwortentwürfe. Gebraucht werden sie trotzdem — für die Diagnose eines gescheiterten Zuges. Phase 1
schafft dafür den Ort, bevor Phase 2 die Inhalte aus den Logs nimmt: Jeder Zug trägt seine
Trace-ID in die Datenbank, und die **Zugakte** im Diagnoseteil der Antwort hält fest, welche
Werkzeuge mit welchen Argumenten liefen, was der Wächter umschrieb und welcher Schnellweg griff. Die
Trace-ID führt aus dem Log zum Zug; das Studio findet ihn über die neue Suche. Am Verhalten des
Chats ändert sich nichts.

| # | Commit | Was |
|---|---|---|
| 1 | Migration 0016 | `trace_id` (nullable) an `messages`, `quality_logs`, `safety_logs`; Teilindex `ix_messages_trace_id` (`text_pattern_ops`) |
| 2 | Trace-ID beim Speichern | Nachricht, Qualitäts- und Sicherheitsprotokoll lesen sie aus dem Kontext; ohne Anfrage `NULL` |
| 3 | Zugakte: Sammler und Bindung | `services/zugakte.py` mit Deckeln (1 000 Zeichen je Wert, 20 Einträge je Liste, 50 Aufrufe je Zug) und Schwärzung (`confirmToken` nie, `fileBase64`/`content` nur als Länge); gebunden in `begin_turn` vor dem Graphen |
| 4 | MCP-Aufrufe in die Akte | an der Engstelle `call_mcp_tool_status`: Argumente beim Eingang und wie gesendet, Status, Cache, Dauer, Länge bzw. Fehlertext; aufgefächerte Listen je Teilaufruf; fremde MCP-Server ebenso |
| 5 | Umschreibungen und Schnellwege | Typ-Fokus und Wächter (Text vorher/nachher, Grund), Canvas und Lernpfad (Thema) |
| 6 | Zugakte speichern | `save_message` (Antworten) und `finalize_message` legen sie unter `debug._zugakte` ab — Normalweg, früh endende Züge, Fehlerblase, Strom; Nachtrag auch, wenn nur die Akte wuchs. `get_messages` gibt sie nur auf Wunsch heraus: der öffentliche Verlauf zeigt sie nur über den Studio-Proxy bzw. mit Studio-Schlüssel. Bei offenem Studio-Tor mit gesetztem Schlüssel zählt der Proxy nicht mehr als Freigabe |
| 7 | Suche nach Fehlernummer | `GET /api/sessions/zug/{nummer}` (Studio): Präfix der Trace-ID, 8–128 Zeichen aus `[A-Za-z0-9._:-]`, ein Treffer je Zug, höchstens 20, neueste zuerst; OpenAPI-Vertrag um genau diesen Pfad neu erzeugt, eingetragen in `docs/api/bewusste-vertragszusaetze.md` |
| 8 | Doku | diese Notiz, Plan-Log, Deploy-README, Übergabe, Steckbrief |

## Was sich im Betrieb ändert

| Was | Muss | Kann |
|---|---|---|
| Migration 0016 | mit dem Release laufen lassen (`migrate`-Job: `alembic upgrade head`). Nur neue, nullable Spalten und ein Index; alte Zeilen bleiben leer. Der Index entsteht in einem kurzen Schreibstopp auf `messages` | Rücknahme: `alembic downgrade 0015` |
| Image | Backend neu bauen und ausrollen (das Widget-Bundle ist unverändert) | |
| Speicher | | je Antwort typisch etwa 6 KB mehr im Verlauf, ein schwerer Zug etwa 30 KB, höchstens rund 250 KB (Deckel oben); gelöscht mit dem Verlauf nach 30 Tagen |
| Datenschutz | | die Zugakte enthält Suchbegriffe und Werkzeug-Argumente des Zuges — innerhalb der bestehenden 30 Tage Verlauf und nur im Studio sichtbar (Risiko R17 im Plan) |
| Studio | | die Suche ist zunächst nur per API da; Oberfläche folgt in Phase 4 |

**Abweichungen vom Plan:** im Plan-Log (Feldnamen der Akte, Schnellwege, Verlaufsfilter schon in
PR 1, ein Treffer je Zug).

## Prüfung

- Backend: volle Suite gegen Postgres und Valkey; neu `test_migration_trace_id.py`,
  `test_trace_id_speichern_pg.py`, `test_zugakte.py`, `test_zugakte_mcp.py`,
  `test_zugakte_speichern_pg.py`, `test_zugakte_verlauf.py`, `test_zug_suche_pg.py`; Ergänzungen in
  Graph, Typ-Fokus/Wächter, Schnellwegen, Nachtrag, `/api/chat`, Strom und Sitzungs-Router; Ruff
  sauber.
- OpenAPI: `openapi-v1.json` weicht nur um den neuen Pfad ab, `openapi-public.json` gar nicht;
  Vertrags-Gates grün.
- Unabhängiges Review (nur lesend): sechs Befunde, behoben bzw. begründet gelassen — im Plan-Log.
- `EXPLAIN` der Präfixsuche (mit `ESCAPE`) nutzt `ix_messages_trace_id`.
