# MCP-Stand vom 14.11.: Client ohne Werkzeugliste je Aufruf, Texte zum strengeren Schreiben (2026-11-14)

Anlass: Rückmeldung des MCP-Entwicklers zum Stand `8cbc051` (noch nicht bereitgestellt). Unsere
Antwort mit den kritischen Punkten: [`mcp-antwort-2026-11-14.md`](../mcp-antwort-2026-11-14.md).
Plan für die Folgeschritte: [`2026-11-14-mcp-stand-8cbc051.md`](../plans/2026-11-14-mcp-stand-8cbc051.md).

Beide Änderungen laufen mit dem alten und dem neuen MCP.

## N0 Kein `tools/list` mehr je Werkzeugaufruf

- **Fund:** Das MCP-Python-SDK (1.30.0) prüft eine erfolgreiche Werkzeugantwort gegen das
  Ausgabeschema, wenn das Werkzeug eines veröffentlicht. Um das zu wissen, holt es `tools/list`,
  sobald die Sitzung das Werkzeug nicht kennt. Der Chatbot öffnet je Aufruf eine frische Sitzung.
  Die ganze Werkzeugliste kam also bei jedem Aufruf mit, auch bei Werkzeugen ohne Schema.
- **Gemessen** (Staging-MCP, nur lesend, ohne Cache, je fünf Aufrufe):

| Werkzeug | vorher (Median) | nachher (Median) |
|---|---|---|
| `lookup_wlo_vocabulary` | 1,05 s | 0,70 s |
| `search_wlo_collections` | 1,31 s | 0,98 s |
| `get_subject_portals` | 1,49 s | 1,47 s (kleinster Wert 1,08 s) |

  Im direkten Wechsel mit und ohne Prüfung lag der Unterschied bei 0,25–0,33 s je Aufruf; die
  Liste war 171 KiB groß. Vorher 18 `tools/list` bei 18 Aufrufen, nachher 0.
- **Änderung:** `services/mcp/transport.py` öffnet die Sitzung als `_Sitzung`, eine Unterklasse
  ohne die Schema-Prüfung. Die Antworten lesen ohnehin eigene Parser. `list_tools` selbst bleibt
  („Server prüfen“ im Studio).
- **Nebenwirkung, gewollt:** Eine Antwort, die ein nachhinkendes Ausgabeschema knapp verfehlt,
  wird nicht mehr zum Transportfehler.
- **Grenze:** Die überschriebene Methode ist privat im SDK. Ein Test hält fest, dass `call_tool`
  sie noch ruft; ändert das SDK das, schlägt er an.

## N1 Texte: der Server rät beim Schreiben nicht mehr

- Der neue MCP nimmt für Fach, Stufe und Zielgruppe nur Name, Alias oder Adresse. Eine unbekannte
  Bezeichnung lehnt er ab und nennt Kandidaten („Meintest du: …?“).
- Die Texte von gestern sagten der KI, der Server gleiche über Teilwörter ab. Jetzt steht dort:
  Kandidaten aus der Ablehnung nehmen oder die Person wählen lassen, erst sonst nachschlagen. Der
  Satz „weicht ein Wert der Vorschau ab, sag das“ bleibt (Alias-Fall, und solange der alte Server
  läuft).
- Geändert: Werkzeugbeschreibungen (`tool_defs.py`, `tool_defs_curation.py`), Muster M18, die drei
  Fassungen des Master-Skills.
- `not_found` steht jetzt in der Liste der Codes, die die Abdeckungsprüfung aus `missing` liest
  (`services/abdeckung.py`). Der MCP meldet einen 404 so statt als `upstream_error`.

## Was ohne Änderung passt

- Die Vorschau-Zeile des Clients („Geändert wird …“) fällt von selbst weg, sobald der Server das
  Ziel als „Titel“ (Kennung) nennt. Das tut der neue Stand bei `wlo_update_content`. Bei sehr
  langen Titeln kürzt der Server; dann stehen beide Zeilen da.
- `is_a_collection` und `is_a_folder` beim Einreichen haben seit dem 13.11. eigene Sätze.
- Das Themenseiten-Muster wertet einen 404 (`not_found`) nicht als Ausfall.
- `textContentUnreadable` wertet der Chatbot nicht aus.

## Geprüft

- Neue Tests: `tests/test_mcp_keine_werkzeugliste_je_aufruf.py` (das SDK listet je Aufruf, unsere
  Sitzung nicht, `_open_session` öffnet unsere Sitzung, die Liste bleibt auf Wunsch erreichbar).
- Angepasst: `tests/test_werkzeug_ketten_kurz.py`.
- Nachmessung am Staging-MCP mit dem echten Client: 0 `tools/list`.

## Deploy

- Keine Migration, keine neue Variable.
- Image neu bauen, danach `boerdi import-config --werksabgleich` (M18 geändert).
- Master-Skill-Knoten in WLO mit `docs/skills/vorgehen-knapp.md` ersetzen (Abschnitt M18).
- Reihenfolge egal: Dieser Stand läuft mit dem alten und dem neuen MCP.
