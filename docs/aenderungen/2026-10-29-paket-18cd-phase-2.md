# Änderungsnotiz — Paket 18C/D, Phase 2: Logs ohne Inhalte

Stand 2026-10-29 · setzt Phase 1 voraus (PR #29: Trace-ID und Zugakte) · Plan
[`docs/plans/2026-10-29-paket-18cd-volle-umsetzung.md`](../plans/2026-10-29-paket-18cd-volle-umsetzung.md)

**Warum:** Das Störtest-Audit (18C) fand Inhalte in den Logs: Ausschnitte von Nachrichten und
Antworten, Themen, Suchbegriffe, Sitzungs-IDs, IPs; auf DEBUG dazu ganze Prompts aus LiteLLM und
JSON-RPC-Nachrichten aus dem MCP-Client. Seit Phase 1 steht, was ein Zug tat, im Studio (Zugakte,
Trace-ID je Nachricht). Das Log sagt jetzt nur noch, **dass** etwas geschah und wie lange — die
Trace-ID führt zum Inhalt. Am Verhalten des Chats ändert sich nichts.

| Was | Wie |
|---|---|
| `LOG_CONTENT` (neu, Vorgabe aus) | öffnet für eine akute Analyse die Inhalts-Logger (LiteLLM, OpenAI-SDK, MCP-Client, instructor) und die Werte der Werkzeugargumente auf DEBUG; der Start warnt |
| Fremd-Logger | `obs/drittlogger.py`: LiteLLM, OpenAI, MCP, instructor auf WARNING (mit Schalter: wie die Wurzel); `httpx`, `httpcore`, `h11`, `uvicorn.access`, SQLAlchemy immer WARNING, `slowapi` ERROR; LiteLLMs eigener stderr-Handler entfernt (jede Zeile kam doppelt, am JSON vorbei) |
| Zugriffszeile | Uvicorns Zeile (IP, roher Pfad samt Sitzungs-ID) aus; eigene Zeile `zugriff` mit Methode, Pfad-Vorlage, Status, Dauer — Dateien und `/health` auf DEBUG |
| Eigene Logzeilen | rund 40 Stellen: Text nur als Länge (`inhalt`), Sitzung als Kurzkennung (`kennung`), Werkzeugargumente nur mit Filterwerten (`filterwerte`); MCP-Aufrufe als Ereignis `mcp_aufruf`; im JSON-Format Ereigniszeilen mit `event` und `fields` |
| Fehlermeldungen | Datenbankfehler ohne Parameterwerte (`hide_parameters`); die Formatierer schwärzen Postgres-`DETAIL:` (Schlüssel und Zeilenwerte) und Pydantic-`input_value=` in Meldung und Traceback; Prüffehler nur mit Ort und Art (`fehlerorte`), der Klassifikator nur mit Zahl der Versuche; Fehlertexte des MCP-Servers und fremder Server nur als Länge (der Text steht in der Zugakte) |
| OpenTelemetry | Pfade mit Sitzungs-ID (`/api/sessions/…`, `/studio/api/sessions/…`, `/api/usage/session/…`) werden nicht gemessen |
| Wächter | Kanarienvogel (`test_kanarienvogel_logs.py`: ein echter Zug je Weg, ein Markierwort in Nachricht, Sitzungs-ID, Modell- und Werkzeugantworten, kein Logeintrag darf es enthalten) und AST-Wächter (`test_log_ohne_inhalt.py`: jedes Argument eines Logaufrufs, auch DEBUG ohne `LOG_CONTENT`, nach Namensteilen und Schlüsseln) |

## Was sich im Betrieb ändert

| Was | Muss | Kann |
|---|---|---|
| Image | Backend neu bauen und ausrollen (Widget unverändert, keine Migration) | |
| Logs auswerten | Abfragen, die auf Uvicorns Zugriffszeile (`"GET /api/… HTTP/1.1" 200`) oder auf Textausschnitte in Meldungen bauen, anpassen: die Zugriffszeile heißt jetzt `zugriff methode=… route=… status=… dauer_ms=…` (im JSON `event: "zugriff"`) | Ereigniszeilen über `event`/`fields` filtern |
| `LOG_CONTENT` | | nur für eine akute Analyse setzen (mit `LOG_LEVEL=DEBUG`), danach wieder aus |
| Fehlersuche | Trace-ID aus dem Log → Studio (Suche nach Fehlernummer, `GET /api/sessions/zug/{nummer}`) → Gespräch samt Zugakte | |

## Prüfung

- Backend: volle Suite gegen Postgres und Valkey; neu `test_kanarienvogel_logs.py`,
  `test_log_ohne_inhalt.py`, `test_drittlogger.py`, `test_log_inhalt.py`, `test_zugriffslog.py`,
  `test_db_fehler_ohne_parameter_pg.py`; Ergänzungen in `test_otel.py`, `test_classify.py`,
  `test_sitzungssperre.py` (Kurzkennung) und `test_mcp_client.py` (zwei Erwartungen bewusst
  geändert: Suchtext und Titel stehen auf INFO nur als Länge).
- Deploy-Wächter (`.env.example`, Compose, Helm) für `LOG_CONTENT`.
- Unabhängiges Review (nur lesend): Befunde behoben bzw. begründet gelassen — im Plan-Log.
