# Paket 4: externes Audit 2026-10-03 und eigene Restliste

Stand 2026-10-03. **Status: freigegeben und umgesetzt (2026-10-03).** Mit der Freigabe gelten die
Empfehlungen in §3.1. Was je Aufgabe geschah, samt Abweichungen, steht im Log am Ende.

Auftrag des Nutzers: Das externe Review lief auf einem älteren Stand. Seine Befunde sind deshalb
am heutigen Code gegenzuprüfen und zusammen mit den eigenen Vermerken in einen Plan zur Behebung
aufzunehmen. Bei Entscheidungen folgt der Nutzer den Empfehlungen.

Quellen:
- **Externes Audit:** [`audits/2026-10-03-audit-extern.md`](../audits/2026-10-03-audit-extern.md), unverändert übernommen.
  - Geprüft wurde main `610abec` vom 2026-10-01.
  - Es enthält 22 Befunde (F01–F22) und 17 Reproduktionen.
- **Eigene Restliste:**
  - die Befundliste [`offene-befunde-und-todo.md`](../offene-befunde-und-todo.md), §1, §2 und §5;
  - der Vorschlag „Paket 4“ vom 2026-10-03.
- **Audit 2026-09-29**, Abschnitte 6 und 7: [`audits/2026-09-29-audit.md`](../audits/2026-09-29-audit.md).

**Gegenprüfung am heutigen Stand** main `e38006d`, gleich Staging:
- Seit `610abec` kamen vier PRs dazu: #7 (Paket 1), #8 (Paket 2), #9 (Token-Streaming) und #10 (Paket 3).
- Fünf Prüfer lasen den Code getrennt nach Bereichen und stellten 14 Befunde mit Attrappen nach, ohne Netz und ohne `.env`.
- Die Proben liegen im Scratchpad der Sitzung, nicht im Repo.
- Zeilenangaben gelten für `e38006d`.

## 1 Abgleich mit dem heutigen Stand

**Ergebnis:**
- 12 Befunde gelten weiter.
- 7 sind teilweise behoben.
- F05 ist behoben bis auf eine Restlücke.
- F18 ist behoben.
- Bei F13 stimmt die Mechanik, die behauptete Wirkung tritt aber nicht ein.

| Nr. | Befund | Heute | Wohin |
|---|---|---|---|
| F01 | Sitzungssperre nur je Prozess | bestätigt | L4, P5-1 |
| F02 | SSE-Zug überlebt Abbruch, Rückfall wiederholt ihn | teilweise | P5-2 |
| F03 | Angebot ist keine Ausführungsfreigabe | teilweise | A2 |
| F04 | Frist und Budget greifen nicht in laufende Aufrufe | bestätigt | B1–B3 |
| F05 | Agent-Schreibvorschlag im Folgezug | behoben, Restlücke | A1 |
| F06 | RAG-Import verliert Text | bestätigt | C2 |
| F07 | Wiederherstellen ohne Modellprüfung, nicht atomar | teilweise | D3, D4, P5-5 |
| F08 | Konfig-Cache fällt auf älteren Stand | teilweise | D1, D2, D6 |
| F09 | `/api/agent` ohne Kostenbuchung | bestätigt | C1, P5-3 |
| F10 | Klassifikator-Salvage nimmt ungültige Werte | bestätigt | C1 |
| F11 | Ergebnis-Schema nicht durchgesetzt | bestätigt | A3 |
| F12 | MCP-Cache ohne Server | bestätigt | C3 |
| F13 | always-RAG greift im Muster-Modus nicht | Mechanik ja, Wirkung nein | C6 |
| F14 | Studio-Speichern überschreibt Fremdes | bestätigt | D5 |
| F15 | Einstellungen ohne Wirkung | teilweise | D7, D8, P5-4 |
| F16 | Import belegt Live-Kapazität | bestätigt | C4 |
| F17 | Konvertierung und URL-Import | bestätigt | C5, P5-8 |
| F18 | Schnellantworten verlieren die Sprache | behoben | §6 (Rest) |
| F19 | Seitentext auf Systemebene, Cache | teilweise | P5-6 |
| F20 | npm-Meldungen ohne CI-Gate | teilweise | L1, L2 |
| F21 | Studio-Identität und Betrieb | bestätigt | L3, P5-7 |
| F22 | Eval-Liste schwer, Start nicht atomar | bestätigt | E1, E2 |

### Vermerke je Befund

- **F01:**
  - `BACKEND_REPLICAS` hat weiter die Vorgabe 3 (`deploy/compose.prod.yml:131`).
  - Die Doku widerspricht sich:
    - `INSTALL.md` empfiehlt drei Repliken.
    - `deploy/README.md` nennt das Backend zustandslos und ohne Bedarf an Sticky-Sessions.
    - `README.md` nennt es clusterfähig.
  - Doppeltes Schreiben schließt der MCP-Server aus, weil sein Schlüssel nur einmal gilt. Verloren gehen können aber `turn_count`, Verlauf und „Zuletzt gezeigt“.
  - Das ist C-H1, eine Entscheidung seit 2026-09-29.
- **F02:**
  - Behoben:
    - Fehlerrahmen generisch (Paket 1, A-M4);
    - kein Freitext im Muster-Weg (Paket 3, T7).
  - Offen:
    - **Der Zug rechnet nach dem Auflegen weiter.** Das läuft auf der schon geschlossenen Request-Sitzung, die Sitzungssperre bleibt gehalten (Probe mit echter App). Starlette bricht den Generator selbst ab, der Abbruch-Zweig in `api/sse.py` wird deshalb nie erreicht.
    - **Doppelte Anfrage aus dem Widget.** Es stellt auch nach `connected` und nach einem `error`-Rahmen eine zweite Anfrage per POST (`shell/send-message.ts:126-164`).
    - Es gibt keine `turn_id`.
  - Faktisch wird also heute schon zu Ende gerechnet, nur ungewollt.
- **F03:**
  - Behoben (Paket 3, T2):
    - MCP-Werkzeuge sind in beiden Schleifen gesperrt;
    - `tool_mode` wirkt im Agent-Weg.
  - Offen:
    - Drei virtuelle Werkzeuge des Agenten laufen vor der Sperre (Probe: `tools=[]` und `submit_result` ergeben `stop=submit`).
    - Im Muster-Weg laufen lokale Werkzeuge ohne Angebot, darunter `query_knowledge` mit RAG-Abfrage.
    - `tool_mode` fehlt im Muster-Weg.
- **F04:** Alle Teile sind per Probe bestätigt.
  - Zur Frist:
    - Frist 5 s, Ende bei 6 s mit `text`.
    - Drei Werkzeuge à 4 s laufen alle, erst danach greift `deadline`.
  - Zum Budget: Budget 1000, Verbrauch 1500, Ende mit `text`.
  - Dazu kommen zwei Punkte aus 09-29:
    - **Keine Frist je MCP-Aufruf** (B-M6). Es gelten 30 s Verbindung, 300 s Lesen je Lesevorgang und ein Retry.
    - **Doppelte LiteLLM-Wiederholungen.** Chat-Completions macht 5 Versuche, also bis etwa 375 s; die Responses-Brücke 3 bis 6.
- **F05:**
  - Behoben in Paket 2 (die xfails sind weg).
  - **Restlücke:** Eingelöst wird ohne Identitätsprüfung.
    - Probe: Die Vorschau wird mit Anmeldung gemerkt. Im Folgezug kommt „ja“ ohne Anmeldung, und der Aufruf läuft mit Dienst-Block und Schlüssel.
    - Das verletzt die Invariante „Schreiben nur mit Anmeldung einlösbar“ (Nutzer-Entscheid 2026-08-12).
- **F06:**
  - Probe: 2 Abschnitte gemeldet, 1 gespeichert.
  - Das Studio ruft den Nachhol-Weg `POST /api/rag/embed` nie auf.
  - Die Spalte erlaubt NULL, die Suche filtert NULL schon heraus.
- **F07:**
  - Behoben (Paket 3, T4): Schlüssel und `export_tree`.
  - Offen:
    - **Kein Modell-Check.** Probe: `mode: bad-mode` wird geschrieben, danach fällt `load_engine()` still auf die Muster-Maschine zurück.
    - **Je Bereich ein Commit.**
    - **Unsaubere Schlüssel:** `.`-Segmente und verschachtelte Gruppen-Schlüssel gehen durch.
  - Dieselbe Modell-Lücke hat der Rohtext-PUT. Seed-Anwenden committet ebenfalls je Bereich.
  - Wiederherstellen ist ergänzend: Neue Bereiche bleiben stehen.
- **F08:**
  - Behoben:
    - Wiederverbindung (Paket 3, T5);
    - Guide-Regeln wirken ohne Neustart (Paket 1).
  - Offen:
    - **Abrufe überholen sich**, auch mit einer Replik (Probe). Ein laufender Abruf überschreibt sogar das Durchschreiben aus `put`.
    - **Neu:** Snapshot und Backup entstehen aus dem Prozess-Cache.
    - **Veraltete Texte:** „wirkt erst nach Neustart“ steht noch im Code und im Studio.
    - **Regex ungeprüft:** Ein ungültiger Regex in den Guide-Regeln wird gespeichert und schaltet danach alle Nachrichten-Regeln ab.
- **F09:**
  - `/api/agent` bucht nichts. Hindernis: `usage_events.session_id` ist NOT NULL mit Fremdschlüssel.
  - Der Salvage-Zweig des Klassifikators kehrt vor der Buchung zurück. instructor liefert den Verbrauch an der Ausnahme mit.
  - Embeddings sind per Entscheid M5 bewusst ausgenommen.
- **F10:**
  - Probe: `signals='abc'`, `entities=[1,2]`, `intent_confidence=99` gehen durch.
  - `entities` als Liste endet in `graph/nodes/merge.py` in einer Ausnahme und der Fehlerblase.
  - Der Fehler ist wörtlich aus ALT übernommen.
- **F11:**
  - Probe: `score` als Integer 0..5 nimmt `"bad"` an, `liefere_ergebnis` nimmt 99 an.
  - `strict` ist nicht gesetzt.
  - Drei Docstrings behaupten, der Anbieter erzwinge die Form.
- **F12:**
  - Betrifft Registry-Server, deren URL das Studio live ändert (Probe).
  - Der primäre Server kommt nur aus der Umgebung. Ein Wechsel braucht einen Neustart und leert dabei den Cache.
- **F13:**
  - Die Mechanik stimmt: Der Zweig „alle `always`-Bereiche“ ist tot.
  - Wirkung hat das keine, weil das Tor `sources` RAG für fast alle Muster schon abschaltet.
  - Probe über alle 20 Seed-Muster: M04 bekommt 8 Bereiche, M15 bekommt 3, alle anderen 0. Mit der dokumentierten Semantik ist das Ergebnis identisch.
  - Das beantwortet die Frage aus Befundliste §2 („nur M04/M15 – so gewollt?“) mit Ja: siehe Befund F1 vom 2026-08-10.
- **F14:** Bestätigt (F-M3/F-M4 aus 09-29), dazu drei Funde:
  - „Neues Dokument“ leitet die Kennung aus dem ersten Wort ab. „Neue Zielgruppe“ und „Neue Lehrkraft“ ergeben beide `neue`.
  - Die MCP-Registry ersetzt die ganze Liste.
  - „Duplizieren“ in Listenformularen kopiert die Kennung.
- **F15:**
  - Behoben: AGENT (T10) und die EscalationBlock-Vorgaben (T9).
  - Der Rest steht in der Befundliste §5, das Studio kennzeichnet diese Felder schon mit „Wird derzeit nicht ausgewertet“.
  - `extra_crisis_terms` und `extra_pii_terms` hatte auch ALT nie verdrahtet.
  - `inline_result_grouping` wirkt im Muster-Prompt nie, weil `cards_enabled` in `Environment` fehlt.
  - `langgraph-checkpoint-postgres` wird nicht genutzt, zieht aber psycopg samt LGPL-Ausnahme in die CI.
- **F16:** Probe: Fünf Importe belegen alle Live-Plätze.
- **F17:**
  - (a) DOCX, PDF, PPTX und XLSX scheitern, das Studio verspricht sie aber. Ohne Extras gehen HTML, Markdown, Text, CSV und JSON (Probe).
  - (b) Der URL-Import hat weder Frist noch Bytedeckel.
  - (c) Die DNS-Prüfung blockiert den Event-Loop.
  - (d) `expected_dim` hat keinen Leser.
- **F18:**
  - Behoben mit `83ec65c` (Paket 1).
  - Rest, ungemessen: Spekulative Muster tragen unter „Bot-Antwort“ einen deutschen Platzhalter.
- **F19:**
  - Behoben (Paket 1, B-M4): Die Endmarken im Fremdtext sind entschärft.
  - Der Rest ist der Responses-Plan, unverändert „wartet auf Freigabe“.
- **F20:**
  - DOMPurify steht auf 3.4.16 und ist damit gepatcht.
  - Die Router-Meldung betrifft nur SSR, das hier nicht genutzt wird.
  - **piscina 5.2.0 ist noch betroffen** (GHSA-67c8-pqhq-4rmx, critical).
    - Es ist nur ein Build-Werkzeug, festgepinnt von `@angular/build` 22.1.3.
    - `@angular/build` 22.2.1 bringt 5.3.2 (geprüft auf unpkg).
  - Die Befundliste §5 sagt fälschlich, alle übrigen Funde seien behoben.
- **F21:**
  - Alle Teile sind bestätigt:
    - Token aus dem Passwort, kein Widerruf, keine Rollen;
    - kein CSP/HSTS;
    - Docker-Socket mit `:ro`;
    - Sicherungen auf demselben Host;
    - `image.yml` ohne CI-Gate;
    - CORS als Vorgabe offen.
  - Das meiste davon sind Entscheidungen seit 09-29.
- **F22:**
  - Die Liste lädt `conversations` mit; das Studio fragt alle 3 s.
  - Der Start ist nicht atomar.
  - Das Aufräumen nach `created_at` > 2 h trifft auch legitime lange Läufe.
- **Audit §9, „Widget ignoriert `text_delta`“:** überholt durch PR #9. Das Token-Streaming läuft hinter `CHAT_TOKEN_STREAMING`.
- **Audit §5–§9 (Tempo, Qualität, Kosten, Studio, Widget):** Das sind Ausbau-Vorschläge, keine Befunde. Sie stehen in §6.

## 2 Auswahl

Paket 4 nimmt auf, was drei Bedingungen erfüllt:
- am heutigen Code nachgeprüft;
- eine klare Behebung;
- ohne Golden-Lauf.

Braucht eine Aufgabe eine Entscheidung, steht die Empfehlung in §3.1. Sie gilt mit der Freigabe des Plans.

Größere Weichen zu Architektur, Betrieb und neuen Abhängigkeiten stehen in §5 als Paket 5.

Reihenfolge:
1. Zuerst der stabile Testlauf, damit Kipper die Nachweise nicht stören.
2. Dann Sicherheit, Korrektheit und Konfiguration.
3. Am Ende Lieferkette und Studio.

## 3 Entscheidungen

### 3.1 Für Paket 4 (gelten mit der Freigabe)

- **P4-1 · `tool_mode` im Muster-Weg (A2): ja.** Ein Gastgeber mit `read-only` bekommt dann auch im Muster-Weg keine schreibenden Werkzeuge.
- **P4-2 · Grenzen im Agent-Lauf (B1, B2):**
  - **Frist hart:** Laufende LLM- und Werkzeugaufrufe enden zur Frist. Die Uhr startet mit dem Zug, Gate und Vorabruf zählen mit.
  - **Budget:** nach jedem LLM-Aufruf geprüft.
    - Kein Ausgabe-Deckel per `max_completion_tokens`, wegen des Abschneide-Risikos.
    - Ist die fertige Antwort schon da, wird sie ausgeliefert und die Überschreitung protokolliert.
  - **MCP-Frist:** 60 s je Aufruf (`MCP_CALL_TIMEOUT_S`), nach einer Zeitüberschreitung kein Retry.
- **P4-3 · Ergebnis-Schema (A3):**
  - Ein ungültiges Ergebnis geht als Werkzeugfehler an das Modell zurück.
  - Kommt bis zu einem Deckel keins, bleibt `result` leer, und `stop_reason` nennt den Deckel.
  - Kein `strict`: Es verlangt `additionalProperties: false` und alle Felder als Pflicht, das bräche freie Gastgeber-Schemata.
  - `jsonschema` wird direkte Abhängigkeit. Es steht schon im Lockfile (4.26.0, MIT).
- **P4-4 · RAG im Muster-Weg (C6):**
  - Die Bindung der Wissensbereiche an M04 und M15 ist gewollt.
  - Die Engine hält künftig „keine Liste“ und „leere Liste“ auseinander, wie Modell und Doku es beschreiben.
  - Für alle Seed-Muster ändert sich nichts.
- **P4-5 · Wiederherstellen (D3):**
  - Verletzt ein Bereich das heutige Modell, wird der ganze Vorgang mit Liste abgewiesen (422), und nichts wird geschrieben.
  - Der Rohtext-Editor prüft ebenfalls gegen das Modell.
- **P4-6 · Konflikt beim Speichern (D5):**
  - Der Server antwortet mit 409 und nennt, wer wann geändert hat.
  - Das Studio bietet „Neu laden“ und „Trotzdem speichern“, der Entwurf bleibt erhalten.
  - Die Version bleibt auf dem Server optional; das Studio sendet sie immer.
- **P4-7 · Zusätzliche Krisen- und PII-Begriffe wirken (D8):**
  - als Begriff ab Wortanfang;
  - normalisiert wie die eingebauten Muster;
  - geprüft nach den eingebauten Mustern.
- **P4-8 · npm-Gate (L2):**
  - Schwelle `high`, Produktion und Entwicklung.
  - Ausnahmen nur mit GHSA, Grund und Ablaufdatum.
- **P4-9 · `latest` erst nach grüner CI (L3):**
  - Auf main und bei Tags startet `image` erst nach erfolgreichem `ci`. Das kostet 5–8 min.
  - PR-Bau und Smokes bleiben parallel.
- **P4-10 · Eine Replik als Vorgabe, bis C-H1 gelöst ist (L4):** Wer sich beim Deploy auf die Vorgabe 3 verlässt, läuft danach mit einer Replik.

### 3.2 Für Paket 5

Die Punkte stehen mit Empfehlung in §5. Weitere Entscheidungen ohne Bezug zum externen Audit stehen unverändert in der Befundliste §2.

## 4 Aufgaben Paket 4

Format je Aufgabe:
- **Befund:** am Stand `e38006d`.
- **Behebung**
- **Test zuerst:** Der Test ist vor dem Fix rot.
- **Abnahme**

### Phase V · Voraussetzung: stabiler Testlauf

Schritt 0: `/better-coding-workflow` laden.

#### V1 · Vitest: Frist und Zeitzone
- **Befund:**
  - In `frontend/angular.json` steht für ui, widget und studio kein `runnerConfig`. Damit gilt die Vitest-Vorgabe von 5 s je Test.
  - Die Zeitzone ist die des Prozesses: in der CI UTC, lokal die Windows-Zeit.
  - Am 2026-10-03 liefen 9 Studio-Dateien unter Last in „Test timed out in 5000ms“, einzeln waren sie grün.
- **Behebung:**
  - Neue Datei `frontend/vitest-base.config.ts` mit `testTimeout: 30000`, `hookTimeout: 30000` und `unstubGlobals: true`.
  - `process.env.TZ = 'UTC'` steht in der Datei, also vor dem Start der Worker.
  - In den drei Test-Targets kommt `"runnerConfig": "vitest-base.config.ts"` dazu.
  - Bricht ein Spec, das Globals in `beforeAll` stubbt, wird es auf `beforeEach` umgestellt.
- **Test zuerst:** Ein Spec prüft `new Date(0).getTimezoneOffset() === 0`. Lokal unter Windows-Zeit ist es rot.
- **Abnahme:** `npm test` (ui, widget, studio) zweimal voll grün.

### Phase A · Schreiben und Werkzeuge

Schritt 0: `/better-coding-workflow` neu laden.

#### A1 · Schreib-Abnahme an die Identität binden (F05-Rest)
- **Befund:**
  - Der Agent-Weg merkt die Abnahme nur mit persönlicher Anmeldung (`graph/nodes/respond_agent.py`, dann `services/write_approval.py::merke_abnahme`).
  - `redeem_write_approval` prüft beim Einlösen aber keine Identität (`write_approval.py:38-42`, bewusst für den Muster-Weg).
  - Der Schlüssel des MCP-Servers ist an keine Identität gebunden (`wlo-mcp-server-sc/src/services/write/confirm.ts:77-98`).
  - Probe:
    1. Zug 1 mit Anmeldung: Die Vorschau wird gemerkt.
    2. Zug 2 ohne Block, Eingabe „ja“: Der Aufruf läuft mit Dienst-Block und Schlüssel.
- **Behebung:**
  - Beide Ablagen speichern `caller_fingerprint()` (`services/mcp/auth.py:155`) im Merkposten. Gemeint sind `merke_abnahme` und der Muster-Weg in `services/tool_loop.py:822`.
  - `redeem_write_approval` löst nur ein, wenn der Fingerabdruck im aktuellen Zug gleich ist. Sonst wird der Merkposten verworfen und gespeichert, und der Zug läuft normal weiter.
  - Ein Merkposten ohne Fingerabdruck stammt von vor dem Deploy und gilt als fremd.
  - Im Muster-Weg gilt Dienst = Dienst, B-H3 bleibt unverändert.
- **Test zuerst:**
  - `tests/test_agent_schreib_abnahme.py`: Zug 1 angemeldet, Zug 2 anonym. Erwartet: kein MCP-Aufruf, Merkposten weg.
  - `tests/test_write_approval.py`: gleicher Abdruck → eingelöst; anderer → verworfen; fehlender → verworfen.
- **Abnahme:** grün, die bisherigen Abnahme-Tests unverändert grün.

#### A2 · Werkzeug-Sperre vervollständigen (F03-Rest, P4-1)
- **Befund:**
  - **Agent:** `respond_to_user`, `submit_result` und `liefere_ergebnis` werden in `services/agent_loop.py` vor der Sperre abgezweigt (Z. 364–409; die Sperre steht in Z. 416–424).
  - **Muster:** `zeige_dokument`, `select_top_cards`, `respond_to_user` und `query_knowledge` laufen ohne Angebot (`services/tool_loop.py`).
    - `query_knowledge` fragt RAG auch dann ab, wenn das Muster kein RAG hat.
    - `tool_mode` wird nicht beachtet.
- **Behebung:**
  - **Agent:** Die Sperre rückt vor die virtuellen Werkzeuge. Bei legitimer Nutzung stehen sie im Angebot (`services/agent_tools.py`), Fehlabweisungen gibt es also keine.
  - **Muster, RAG:** `query_knowledge` läuft nur, wenn es angeboten ist.
  - **Muster, Darstellungswerkzeuge:** Für die drei Werkzeuge wird vorab geprüft, ob Muster-Texte sie außerhalb des Angebots verlangen (wie Paket 3 bei den MCP-Werkzeugen).
    - Falls ja, bleiben sie als begründete Ausnahme frei. Die Ausnahme steht im Log.
    - Sonst gilt die Sperre auch für sie.
  - **Muster, `tool_mode` (P4-1):**
    - Angebot (`services/response_tool_selection.py::_select_active_tools`) und Sperre (`tool_loop._angeboten`) filtern mit `domain/host_capabilities.py`, wie im Agent-Weg.
    - Der Prompt wird nicht umgebaut.
- **Test zuerst:**
  - `tests/test_agent_loop.py`: Bei leerem Angebot werden die drei virtuellen Werkzeuge abgewiesen, und es gibt kein Ende über `submit`.
  - `tests/test_tool_loop.py`:
    - `query_knowledge` ohne Angebot löst keine RAG-Abfrage aus;
    - bei `read-only` ist kein Schreibwerkzeug im Angebot, und ein Aufruf wird abgewiesen.
- **Abnahme:** grün; `tests/test_werkzeug_angebot.py` und die Muster-Paritätstests grün.

#### A3 · Ergebnis-Schema durchsetzen (F11, P4-3)
- **Befund:**
  - `submit_result` übernimmt `args["result"]` ungeprüft (`services/agent_loop.py:375-378`).
  - `liefere_ergebnis` prüft nur, ob es ein Dict ist (`domain/result_delivery.py:123-126`).
  - `AgentRequest.result_schema` ist frei und ohne Größendeckel (`api/schemas_agent.py:39`).
- **Behebung:**
  - **Prüfen nach dem Aufruf:**
    - Der Validator kommt aus dem angebotenen Werkzeug, aus `parameters.properties.result` von `submit_result` bzw. `liefere_ergebnis`.
    - Geprüft wird mit `jsonschema.Draft202012Validator`.
    - Fehler gehen als Werkzeugfehler mit Pfad zurück. `submit_result` beendet dann nicht.
  - **Kein gültiges Ergebnis bis zu einem Deckel:** `result=None`, `stop_reason` des Deckels.
  - **Eingangsgrenze:**
    - `check_schema` auf `result_schema`, am Agent-Endpunkt und im Chat; Fehler ergibt 422.
    - Für `/api/agent` gilt derselbe Größendeckel wie im Chat (`api/schemas.py:199-212`).
    - Entfernte `$ref` werden nicht geladen (Vorgabe von `jsonschema` ohne Registry).
  - **Aufräumen:**
    - `jsonschema` kommt in `backend/pyproject.toml`.
    - Die drei Docstrings werden berichtigt: `agent_tools.py:15-19`, `result_delivery.py:88-90`, `schemas_agent.py:9-12`.
- **Test zuerst:**
  - `tests/test_agent_loop.py`, Fall Integer 0..5:
    - `"bad"` ergibt einen Werkzeugfehler, ein anschließend gültiges Ergebnis endet mit `submit`;
    - bleibt es ungültig, ist `result=None`.
  - `tests/test_result_delivery.py`.
  - Ein Endpunkt-Test: ungültiges Schema ergibt 422.
- **Abnahme:** grün. Kommt 422 in den OpenAPI-Vertrag, wird er bewusst erweitert und im Log vermerkt.

### Phase B · Fristen und Wiederholungen (F04, P4-2)

Schritt 0: `/better-coding-workflow` neu laden.

#### B1 · Gesamtfrist und Budget im Agent-Lauf
- **Befund:**
  - `run_agent_loop` prüft Frist und Budget nur am Rundenanfang (`services/agent_loop.py:265-275`).
  - Der LLM-Aufruf und die Werkzeuge einer Runde laufen ohne Restfrist.
  - Ein Ende über `text` oder `submit` wird nicht nachgeprüft.
  - Die Uhr startet erst in der Schleife. Gate und Vorabruf (`services/agent_run.py`, `graph/nodes/respond_agent.py`) laufen davor.
- **Behebung:**
  - **Start:** `run_agent_loop(..., start=None)`; die Aufrufer reichen ihre Startzeit herein.
  - **Frist:**
    - Jeder LLM- und Werkzeugaufruf läuft in `asyncio.timeout(rest)`. Läuft die Frist ab, endet der Lauf mit `deadline`.
    - Werkzeugaufrufe der Runde, die nicht mehr laufen, bekommen die Antwort „nicht ausgeführt (Frist)“. So bleibt der Verlauf gültig.
  - **Budget:**
    - Es wird nach jedem LLM-Aufruf geprüft. Ist es überschritten, endet der Lauf mit `token_budget`, bevor die nächste Runde beginnt.
    - Kam mit diesem Aufruf schon die fertige Antwort, wird sie ausgeliefert. Die Überschreitung steht dann als Warnung und als Trace-Zeile im Protokoll.
  - **Abschluss im Chat:** `_abschluss_nachholen` (`respond_agent.py:215-245`) läuft weiter nur, wenn noch keine Antwort da ist.
- **Test zuerst:** in `tests/test_agent_loop.py`, mit kleinen Zeiten:
  - Frist 0,2 s und LLM-Fake mit 0,5 s: Ende mit `deadline` nach unter 0,3 s.
  - Drei Werkzeuge à 0,15 s bei Rest 0,2 s: höchstens zwei laufen, der Rest wird „nicht ausgeführt“.
  - Budget 1000, Aufruf mit 1500 und Endtext: Der Text ist da, die Warnung steht im Protokoll.
  - Die Startzeit des Aufrufers zählt mit.
- **Abnahme:** grün; die vier Szenarien der Probe enden wie beschrieben.

#### B2 · Frist je MCP-Aufruf
- **Befund:**
  - `services/mcp/transport.py` übergibt keine Frist. Es gelten die SDK-Vorgaben: 30 s Verbindung, 300 s je Lesevorgang, keine Gesamtgrenze.
  - Dazu kommt ein Retry (`services/mcp/client.py:358-372`).
  - Der Status `timeout` (`services/outcome_service.py:88`) wird nie gesetzt.
- **Behebung:**
  - `session.call_tool(..., read_timeout_seconds=timedelta(seconds=settings.mcp_call_timeout_s))`. Die SDK-Signatur ist geprüft (mcp 1.28.1).
  - Neue Einstellung `MCP_CALL_TIMEOUT_S`, Vorgabe 60, in `settings.py`, `deploy/.env.example` und der Doku.
  - Eine Zeitüberschreitung ergibt das Ergebnis `timeout`, ohne Retry. Bestätigte Schreibaufrufe bleiben wie bisher ohne Retry.
- **Test zuerst:** `tests/test_mcp_transport.py`:
  - die Frist wird übergeben;
  - eine Fake-Session mit Zeitüberschreitung ergibt `timeout` mit genau einem Versuch.
- **Abnahme:** grün.

#### B3 · Eine Wiederholungsschicht für LLM-Aufrufe
- **Befund:** `num_retries=2` (`services/llm.py:185`) ergibt in LiteLLM 1.91.5 zwei Schichten.
  - Die zwei Schichten:
    - SDK-`max_retries`;
    - `acompletion_with_retries`.
  - Probe mit gefälschtem `httpx.send`:
    - Chat-Completions macht 5 Versuche, bis etwa 375 s.
    - Die Responses-Brücke macht 3 bzw. 6.
  - Gewollt waren 3 Versuche (ALT-Parität). Streaming, Embedding und Klassifikator tragen denselben Stempel.
- **Behebung:**
  - Je Pfad gibt es eine Schicht mit höchstens 3 Versuchen.
  - Die Einstellung wird mit dem Zähltest gewählt. Rechnerisch ergibt `num_retries=1` bei Chat 3, bei Responses 2.
  - Ein Kommentar hält die Zählung fest.
- **Test zuerst:** `tests/test_llm.py`, Zähltest je Pfad (Chat, Responses, Stream, Embedding) mit gefälschtem Transport. Erwartet: höchstens 3 Versuche; heute rot.
- **Abnahme:** grün.

### Phase C · Wissen, Klassifikation, Caches

Schritt 0: `/better-coding-workflow` neu laden; vor C2 und C5 zusätzlich `/better-coding-frontend`.

#### C1 · Klassifikator-Salvage prüft Felder und bucht Verbrauch (F10, F09-Teil)
- **Befund:**
  - `_salvage` (`services/classify.py:109-138`) übernimmt per `model_construct` auch ungültige Werte. Folge: Ausnahme in `graph/nodes/merge.py:80-81`, danach die Fehlerblase.
  - Der Fehlerzweig kehrt vor der Verbrauchsbuchung zurück (Z. 100–105).
- **Behebung:**
  - Jedes Feld wird einzeln gegen `ClassificationResult` geprüft, ungültige werden verworfen. Danach folgt `model_validate` mit den gültigen Feldern.
  - Im Fehlerzweig wird `exc.total_usage` als `classify` gebucht, dann gerettet.
- **Test zuerst:** `tests/test_classify.py`:
  - die drei Fälle der Probe ergeben ein gültiges Ergebnis mit Vorgaben;
  - der Verbrauch ist gebucht.
- **Abnahme:** grün.

#### C2 · RAG-Import verlustfrei (F06)
- **Befund:**
  - `ingest_document` (`services/rag/ingest.py:122-129`) überspringt Abschnitte ohne Vektor und meldet trotzdem alle.
  - Der Nachhol-Weg findet nur vorhandene Zeilen.
- **Behebung:**
  - **Speichern:** Abschnitte ohne Vektor werden mit `embedding=NULL` gespeichert. Die Rückgabe enthält die Zahl der Abschnitte gesamt und der eingebetteten.
  - **API:** Die drei Import-Antworten in `api/rag.py` melden zusätzlich `embedded` und `missing`. Der Vertrag wird additiv erweitert.
  - **Studio, Ansicht Wissens-Import (`views/rag-ingest.component.*`):**
    - Nach dem Import steht „N Abschnitte, davon M ohne Einbettung“.
    - Der Knopf „Fehlende Einbettungen nachholen“ ruft `POST /api/rag/embed`.
    - Alle Zustände sind gestaltet: alles eingebettet, Lücken, läuft, Fehler.
  - **Docstrings berichtigen:**
    - in `ingest.py` Kopf und Nachhol-Funktion;
    - in `api/rag.py`;
    - in `embed.py`: Die Angabe „ALT-Verhalten“ stimmt nicht, ALT brach ab.
- **Test zuerst:**
  - `tests/test_rag_ingest.py`: Wenn ein, mehrere oder alle Vektoren fehlen, sind trotzdem alle Texte gespeichert, und die Zahlen stimmen.
  - `tests/test_rag_router_ingest.py`: die neuen Felder.
  - `tests/test_rag_embed_pg.py`: Nachholen füllt genau die fehlenden Vektoren.
  - Ein Studio-Spec für die Ansicht.
- **Abnahme:** grün; die Ansicht ist im Browser geprüft, auch per Tastatur.

#### C3 · MCP-Cache je Server (F12)
- **Befund:**
  - Der Schlüssel in `services/mcp/tool_cache.py:102-126` besteht aus Werkzeug, Aufrufer und Argumenten.
  - `client.py:266` kennt die Ziel-URL, gibt sie aber nicht weiter (Z. 315).
- **Behebung:** Die Ziel-URL kommt in den Schlüssel. Das wirkt auch über Repliken hinweg.
- **Test zuerst:**
  - `tests/test_mcp_tool_cache.py`: gleiche Argumente bei anderer URL ergeben getrennte Einträge.
  - `tests/test_mcp_client.py`.
- **Abnahme:** grün.

#### C4 · Eigener Kanal für Import-Embeddings (F16)
- **Befund:**
  - `embed_many` legt je Aufruf einen eigenen Semaphor an (`services/rag/embed.py:104`).
  - `llm.embedding` nimmt zusätzlich einen Live-Platz (`services/llm.py:296`).
  - `settings.py:261-266` verspricht dagegen einen eigenen Deckel.
- **Behebung:**
  - `llm.embedding(..., kanal="live")` bekommt einen neuen, prozessweiten Kanal `ingest`. Seine Größe ist `EMBED_INGEST_PARALLEL`, die Einstellung gibt es schon (Vorgabe 4).
  - Import und Nachholen nutzen `ingest`, das Query-Embedding bleibt auf `live`.
  - Nicht der Kanal `bg`, den teilen sich Eval und Judge.
- **Test zuerst:**
  - `tests/test_rag_embed.py`: Parallele Importe lassen die Live-Plätze frei, im Kanal `ingest` laufen höchstens N.
  - `tests/test_llm.py`.
- **Abnahme:** grün.

#### C5 · URL-Import begrenzt, Formatangebot ehrlich (F17)
- **Befund:**
  - (a) Formate:
    - DOCX, PDF, PPTX und XLSX scheitern mit `MissingDependencyException`, der Router macht daraus 400.
    - Das Studio verspricht sie (`i18n/catalogue/knowledge.ts:83-85`), und der Datei-Input hat kein `accept`.
  - (b) Der URL-Import hat weder Frist noch Bytedeckel. markitdown liest den ganzen Rumpf ohne Timeout.
  - (c) DNS: `assert_public_url` löst DNS synchron im Event-Loop auf (`ingest.py:81`, ebenso `api/config.py:143`).
  - (d) `expected_dim` hat keinen Leser.
- **Behebung:**
  - (a) Bis zum Entscheid über die markitdown-Extras (P5-8):
    - Hilfetext und `accept` auf `.html,.htm,.md,.markdown,.txt,.csv,.json` beschränken.
    - `MissingDependencyException` ergibt 415 mit klarer, lokalisierter Meldung.
  - (b) Selbst holen über die SSRF-Sitzung (`services/url_safety.py`):
    - mit `stream=True` und `timeout=(5, 30)`;
    - `Content-Length` vorab prüfen;
    - `iter_content` mit Bytezähler gegen denselben Deckel wie beim Datei-Upload, dazu eine Gesamtfrist;
    - dann `convert_stream` mit `StreamInfo(url, mimetype)`;
    - die Sitzung wird immer geschlossen.
  - (c) `await asyncio.to_thread(assert_public_url, url)` an beiden Stellen.
  - (d) Ein Vektor falscher Länge gilt im Import als Fehlschlag und wird `NULL` (siehe C2). Der falsche Docstring („beim Start“) wird berichtigt.
- **Test zuerst:**
  - `tests/test_rag_ingest.py`:
    - ein langsamer Server läuft in die Frist;
    - zu groß per Header und per Rumpf bricht ab;
    - DOCX ergibt 415.
  - `tests/test_url_safety.py`.
  - Ein Studio-Spec für `accept`.
- **Abnahme:** grün.

#### C6 · RAG-Semantik im Muster-Weg wie dokumentiert (F13, P4-4)
- **Befund:**
  - `phase3_modulate` schreibt `rag_areas` immer als Liste (`domain/pattern_engine.py:61/263`). Deshalb ist der Zweig für `always`-Bereiche in `domain/route_head.py:37-44` tot.
  - Das Studio-Modell unterscheidet `None` und `[]` (`domain/config_models/patterns.py:53`), die Engine verliert diesen Unterschied.
  - Der Kommentar in `services/response_tool_selection.py:308` stimmt nicht.
- **Behebung:**
  - `rag_areas: list[str] | None` wird durchgereicht:
    - `None` heißt Vorgabe der Wissensbereiche;
    - `[]` heißt kein RAG;
    - eine Liste heißt genau diese Bereiche.
  - Der Leser in `services/turn_persist.py:185` bekommt `or []`.
  - Kommentare und der Seed-Kommentar in `backend/seeds/05-knowledge/rag-config.yaml` werden berichtigt.
- **Test zuerst:**
  - `tests/test_route_node.py`:
    - ein neues Muster mit `sources: [rag]` ohne Liste bekommt die `always`-Bereiche;
    - `[]` bekommt keine.
  - Ein Gleichheits-Test über alle Seed-Muster: Die Bereiche sind dieselben wie heute.
- **Abnahme:** grün, auch `tests/test_rag_korpus_erreichbar.py`.

### Phase D · Konfiguration verlässlich

Schritt 0: `/better-coding-workflow` neu laden; vor D5 und D8 zusätzlich `/better-coding-frontend`.

#### D1 · Ein Abruf je Bereich, Version im Cache (F08)
- **Befund:**
  - Jede NOTIFY startet einen eigenen `_refresh` (`services/config_store.py:99-120`), und `_fetch` lädt nur `data`.
  - Folge (Probe): Ein älterer, langsamer Abruf überschreibt einen neueren, auch mit einer Replik. Ebenso überschreibt ein laufender Abruf das Durchschreiben aus `put`.
- **Behebung:**
  - **Ein Abruf je Bereich:** Je Bereich läuft nur ein Abruf gleichzeitig. Kommt währenddessen eine NOTIFY, wird danach noch einmal geholt.
  - **Version im Cache:**
    - Der Cache lädt `SELECT data, version`, hält die Version und verwirft ältere Ergebnisse.
    - `put` setzt die zurückgegebene Version.
    - Löschen entfernt Eintrag und Version. Nach Löschen und Neuanlage beginnt die Version wieder bei 1.
- **Test zuerst:** ein DB-freier Test nach der Probe:
  - zwei NOTIFYs, v1 langsam, v2 schnell: v2 bleibt;
  - `put` v3 während des Abrufs v2: v3 bleibt.
- **Abnahme:** grün, `tests/test_notify_reconnect.py` grün.

#### D2 · Snapshot und Backup aus der Datenbank (F08, Folgebefund)
- **Befund:** Snapshot, Backup, Werksstand-Vergleich und Seed-Vergleich entstehen aus dem Prozess-Cache (`services/config_loader/_store.py:79-81`, `api/config_snapshots.py`).
- **Behebung:** aus der Datenbank lesen, mit einem `SELECT area, data` über alle Bereiche.
- **Test zuerst:** pg-Test: Ist der Cache veraltet und die DB neuer, enthält der Snapshot den DB-Stand.
- **Abnahme:** grün.

#### D3 · Wiederherstellen prüft Modelle und Schlüssel (F07, P4-5)
- **Befund:**
  - `_apply_config` ruft kein `model_validate` (`api/config_snapshots.py:44-69`). Dieselbe Lücke hat `PUT /api/config/file`.
  - `.`-Segmente und verschachtelte Gruppen-Schlüssel wie `03-patterns/a/b/c` gehen durch.
- **Behebung:**
  - **Modellprüfung:**
    - Vor dem Schreiben gilt `model_validate` für jeden Bereich mit Modell, nach der Logik in `api/config.py:328-341`.
    - Alle Fehler werden gesammelt. Dann kommt 422 mit Liste, und nichts wird geschrieben.
    - Bereiche ohne Modell passieren.
  - **Rohtext-PUT:** bekommt dasselbe Tor.
  - **Schlüssel:** `is_restorable_area_key` lehnt `.`-Segmente ab. Unter `03-patterns/` und `04-personas/` verlangt es genau ein Blatt, nach der Regel von `_is_file_key`.
- **Test zuerst:**
  - `tests/test_snapshots_endpoints.py`, nach Vorlage `test_restore_weist_interne_mcp_adressen_ab_und_schreibt_nichts`: `bad-mode` ergibt 422, und nichts ist geschrieben.
  - Ein Test für den Rohtext-PUT.
- **Abnahme:** grün.

#### D4 · Wiederherstellen und Seed-Anwenden in einer Transaktion (F07)
- **Befund:**
  - `ConfigStore.put` öffnet je Aufruf eine eigene Transaktion (`config_store.py:156-173`).
  - Scheitert der zweite Bereich, ist der erste schon neu (Probe). Das Seed-Anwenden arbeitet ebenso.
- **Behebung:**
  - `ConfigStore.put_many(items, updated_by, delete=())` schreibt alle UPSERTs, History-Zeilen und Löschungen in einem `begin()`.
  - Der Cache wird erst nach dem Commit gesetzt.
  - NOTIFY geht je Bereich; Postgres stellt sie beim Commit zu.
  - `_apply_config` und das Seed-Anwenden nutzen `put_many`.
- **Test zuerst:**
  - `tests/test_config_store.py`: Fehler im dritten Bereich, dann ist keiner geschrieben und der Cache unverändert.
  - `tests/test_seed_sync.py`.
- **Abnahme:** grün.

#### D5 · Speichern mit Konfliktschutz (F14, P4-6)
- **Befund:**
  - Keine Schreib-API nimmt eine erwartete Version, `GET /api/config/data` liefert keine, und `_UPSERT` überschreibt bedingungslos.
  - „Neues Dokument“ (`views/group-section.component.ts:186-235`) prüft Dubletten nur im Browser, speichert per Upsert und nimmt das erste Wort als Kennung.
  - Die MCP-Registry ersetzt die ganze Liste.
  - „Duplizieren“ kopiert die Kennung (`schema-form/object-list.component.ts:151-155`).
- **Behebung im Backend:**
  - **Prüfung:** `ConfigStore.put(..., expected_version=None, create_only=False)`.
    - Mit Version gilt `UPDATE … WHERE version = :v`.
    - Beim Anlegen gilt `INSERT … ON CONFLICT DO NOTHING`.
    - Ohne Treffer kommt 409 mit aktueller Version, `updated_by` und Zeitpunkt. Der Meldungsschlüssel steht in `i18n/messages.py`.
  - **Version in den Antworten:** Die Version steht in den GET- und PUT-Antworten von `/config/data`, `/config/file` und `/mcp-servers`.
  - **Neue Felder:** `expected_version` und `create` sind optional.
- **Behebung im Studio:**
  - **Speichern:** `schema-form/area-doc-editor.ts` und `core/config-api.service.ts` senden die Version mit.
  - **Konflikt (409):** Ein Hinweis bietet „Neu laden“ und „Trotzdem speichern“. Der Entwurf bleibt erhalten, und der Fokus landet auf dem Hinweis.
  - **„Neues Dokument“:**
    - `group-section` sendet `create: true` und leitet die Kennung aus dem ganzen Titel ab.
    - Bei 409 steht „Kennung gibt es schon“.
  - **MCP-Registry:** sendet die Version mit.
  - **„Duplizieren“:** vergibt eine neue Kennung.
- **Test zuerst:**
  - pg-Tests in `tests/test_config_data_endpoint.py`, `tests/test_config_store.py` und `tests/test_config_mcp_servers.py`:
    - eine alte Version ergibt 409, und nichts ist geschrieben;
    - Anlegen über Bestehendes ergibt 409.
  - Studio-Specs `area-doc-editor.spec.ts`, `group-section.component.spec.ts` und `mcp-registry.component.spec.ts`, dazu Duplizieren in `object-list`.
- **Abnahme:**
  - Tests grün.
  - Im Browser mit zwei Tabs auf demselben Bereich: Wer als zweites speichert, sieht den Konflikt und behält den Entwurf.
  - Der OpenAPI-Vertrag ist bewusst erweitert.

#### D6 · Guide-Regeln: Texte und Regex-Prüfung (F08-Reste)
- **Befund:**
  - Seit Paket 1 wirken Guide-Regeln ohne Neustart. `domain/area_effects.py:82` und die Studio-Hinweise in `i18n/catalogue/fields-lotse.ts` sagen aber noch „nach Neustart“.
  - Ein ungültiger Regex wird gespeichert und schaltet danach alle Nachrichten-Regeln ab (`guide_markers.py:96-98`).
- **Behebung:**
  - Die Texte werden berichtigt.
  - Beim Schreiben prüft `_assert_area_document_safe` im Bereich Guide-Regeln jedes `pattern` mit `re.compile`. Ein Fehler ergibt 400 mit Angabe der Regel.
  - Das Laden bleibt nachsichtig, damit ein alter Stand nicht alles abschaltet.
- **Test zuerst:**
  - Ein Schreibtest mit `pattern: "("` ergibt 400.
  - `tests/test_area_effects.py` erwartet den neuen Text.
- **Abnahme:** grün.

#### D7 · Ungenutzte Abhängigkeit entfernen (F15)
- **Befund:** `langgraph-checkpoint-postgres` steht in `backend/pyproject.toml:14`, wird aber nirgends importiert. Der Graph läuft bewusst ohne Checkpointer.
- **Behebung:**
  - **Abhängigkeit:** streichen und `uv lock` laufen lassen.
  - **CI:** Die LGPL-Ausnahme in `.github/workflows/ci.yml:80-87` fällt weg, sofern psycopg danach nicht mehr im Baum ist.
  - **Test:** `tests/test_alembic_logging.py:37` nutzt offline eine `postgresql+psycopg`-URL und wird bei Bedarf angepasst.
  - **Plan:** Die Zeile im Neubau-Plan wird nachgezogen.
- **Test zuerst:** entfällt, es ist eine reine Abhängigkeitsänderung.
- **Abnahme:**
  - volle Backend-Suite;
  - Lizenz-Gate und `pip-audit` lokal;
  - in der CI zusätzlich der Image-Smoke.

#### D8 · Zusätzliche Krisen- und PII-Begriffe (F15, P4-7)
- **Befund:** `extra_crisis_terms` und `extra_pii_terms` (`domain/config_models/base_governance.py:95-96`) haben keinen Leser, auch nicht im ALT.
- **Behebung:**
  - **Prüfung:** `regex_gate` (`services/safety/regex_gate.py:221`) prüft nach den eingebauten Krisen- bzw. PII-Mustern zusätzlich die Begriffe aus `01-base/safety-config`.
    - Normalisierung wie die Nachricht (`normalize_for_matching`), dazu `re.escape`.
    - Treffer ab Wortanfang.
  - **Wirkung:**
    - Ein Krisenbegriff führt zu M01, wie die eingebauten Muster.
    - Ein PII-Begriff ergibt die mittlere Stufe.
  - **Grenzen:**
    - Leere Begriffe zählen nicht.
    - Länge und Anzahl sind im Modell gedeckelt.
  - **Zwischenspeicher:** Die kompilierten Muster bleiben zwischengespeichert und werden bei geänderter Liste neu gebaut, wie bei den Guide-Regeln.
  - **Aufräumen:** Studio-Kennzeichnung und `area_effects` werden nachgezogen.
- **Test zuerst:** `tests/test_safety_regex_gate.py`:
  - ein zusätzlicher Krisenbegriff ergibt M01, auch mit Nullbreite-Zeichen und NFD;
  - ein PII-Begriff ergibt `medium`;
  - bei leerer Liste bleibt das Verhalten wie heute.
- **Abnahme:**
  - grün, die bisherigen Regex-Tests unverändert grün;
  - die Studio-Fixture ist neu erzeugt, falls sich das Schema ändert.

### Phase E · Eval-Verwaltung (F22)

Schritt 0: `/better-coding-workflow` neu laden.

#### E1 · Eval-Liste ohne Transkripte
- **Befund:**
  - `list_runs` und `get_trends` (`services/eval/queries.py:34-37/101-109`) laden ganze Zeilen samt `conversations`.
  - Das Studio fragt alle 3 s, solange ein Lauf läuft.
- **Behebung:** Nur die Listenspalten laden (`load_only` bzw. `defer(EvalRun.conversations)`). Was die Liste sonst braucht, kommt aus `summary`.
- **Test zuerst:** `tests/test_eval_queries.py`: Das Ergebnis enthält keine geladenen `conversations`.
- **Abnahme:** grün.

#### E2 · Eval-Start atomar
- **Befund:** `_ensure_no_running_run` (`services/eval/run_store.py:75-101`) prüft, angelegt wird später. Es gibt weder Index noch Sperre.
- **Behebung:**
  - Neue Migration `0006`: `CREATE UNIQUE INDEX … ON eval_runs ((true)) WHERE status = 'running'`.
  - Ein `IntegrityError` beim Anlegen ergibt dieselbe 409 wie heute.
  - Das Aufräumen nach `created_at` bleibt.
  - Bekannte Grenze: Ein Lauf über 2 h wird beim nächsten Startversuch beendet. Ein Lebenszeichen steht im Backlog.
- **Test zuerst:** `tests/test_eval_pg.py`: Zwei parallele Starts ergeben genau einen Lauf und eine 409.
- **Abnahme:** grün; `alembic upgrade head` und `downgrade -1` laufen durch.

### Phase L · Lieferkette und Betrieb

Schritt 0: `/better-coding-workflow` neu laden.

#### L1 · Angular 22.2 (F20)
- **Befund:**
  - `@angular/*` steht auf 22.1.1, `@angular/build` auf 22.1.3 mit piscina 5.2.0. Betroffen ist piscina vor 5.3.2.
  - `@angular/build` 22.2.1 bringt piscina 5.3.2 mit.
- **Behebung:** alle `@angular/*` gemeinsam per `ng update` auf 22.2 heben. Eine Überschreibung ist nicht nötig.
- **Abnahme:**
  - grün sind lint, `check:*`, Unit ui/widget/studio, Budget, Studio-Build, Widget-Build und E2E;
  - `npm audit` meldet nichts ab `high`.

#### L2 · npm-Audit als CI-Gate (F20, P4-8)
- **Befund:** Die CI hat `pip-audit` und zwei Lizenz-Gates, aber kein npm-Audit.
- **Behebung:**
  - **Skript:** `frontend/scripts/check-audit.mjs` wertet `npm audit --json` aus.
    - Schwelle ist `high`.
    - Ausnahmen stehen in `frontend/audit-ausnahmen.json` mit GHSA, Grund und Ablaufdatum.
    - Abgelaufene Ausnahmen schlagen fehl.
  - **CI:** ein neuer Schritt im Frontend-Job von `ci.yml`.
  - **Datenschutz:** `npm audit` schickt nur die Liste öffentlicher Pakete an die Registry, wie sie `npm ci` ohnehin lädt.
- **Test zuerst:** `node --test frontend/scripts/check-audit.test.mjs`, ohne neue Abhängigkeit. Er prüft die Bewertung:
  - ein Fund ab `high` ohne Ausnahme ist rot;
  - mit gültiger Ausnahme grün;
  - mit abgelaufener Ausnahme rot.
- **Abnahme:** Der Test ist grün; der CI-Schritt ist nach L1 grün.

#### L3 · `latest` erst nach grüner CI (F21-Teil, P4-9)
- **Befund:** `image.yml` veröffentlicht `latest` auf main unabhängig von `ci.yml`. Das ist bewusst so (Kommentar Z. 18–23).
- **Behebung:**
  - **Auslöser:** Push auf main und Tags lösen `image` nicht mehr direkt aus. Stattdessen startet es per `workflow_run` auf `ci` mit `conclusion == 'success'`.
  - **Checkout und Marken:** kommen aus `head_sha` und `head_branch`.
  - **Unverändert:** PR-Bau und Smokes bleiben wie heute; `workflow_dispatch` bleibt für das Veröffentlichen von Hand.
  - **Kommentar:** Der Kopfkommentar wird neu gefasst.
- **Test zuerst:** lokal nicht ausführbar.
  - Nach dem Merge zeigt `gh run list`, dass `image` erst nach grünem `ci` für denselben Commit läuft.
  - Falls vorhanden, läuft vorher `actionlint`.

#### L4 · Eine Replik als Vorgabe (F01-Zwischenmaßnahme, P4-10)
- **Befund:**
  - In `deploy/compose.prod.yml:131` steht `${BACKEND_REPLICAS:-3}`.
  - `.env.example` sagt „6 Kerne ⇒ 3 (= Default)“.
  - INSTALL.md, deploy/README.md und README.md versprechen den Mehr-Repliken-Betrieb.
- **Behebung:**
  - Die Vorgabe wird 1, mit Kommentar und Verweis auf C-H1.
  - Die Doku wird angeglichen: INSTALL, `deploy/README.md`, README, `docs/cluster-checkliste.md`.
  - Die Befundliste §4 („Beim nächsten Deploy“) bekommt einen Hinweis auf die geänderte Vorgabe.
- **Test zuerst:** `tests/test_deploy_compose.py` erwartet die Vorgabe 1.
- **Abnahme:** grün.

#### L5 · Doku und Befundlisten nachziehen
- **Audit 2026-09-29 §6:**
  - Die in Paket 1 und 3 behobenen Punkte bekommen ✅, mit Verweis auf die Nachträge in §7.
  - `architektur.md` bekommt aktuelle Zählstände.
  - In `INSTALL.md` steht TLS-ALPN statt HTTP-01, und der Auto-Import durch `migrate` ist erwähnt (Audit 09-29, 6.11).
- **Befundliste:**
  - Der Satz zu `npm audit fix` in §5 wird berichtigt.
  - Plan und externes Audit kommen unter „Die zugehörigen Pläne“.
  - Erledigtes wird gestrichen.

### Phase S · Studio-Barrierefreiheit

Schritt 0: `/better-coding-workflow` und `/better-coding-frontend` neu laden.

#### S1 · Live-Regionen leer anlegen (Audit 09-29, F-M6)
- **Befund:** Sechs Live-Regionen im Studio entstehen samt Inhalt. Screenreader sagen sie dann oft nicht an. `aria-live` steht heute in 12 Dateien; die sechs betroffenen werden beim Bau bestimmt.
- **Behebung:** Die Region steht leer im DOM, bevor der Text kommt. Der Text wird danach gesetzt, nach einem gemeinsamen Muster.
- **Test zuerst:** je Stelle ein Spec: Die Region existiert vor der Meldung, der Text kommt danach.
- **Abnahme:** grün. Die NVDA-Prüfung macht der Nutzer (Befundliste §3).

#### S2 · `color-scheme` im Studio
- **Befund:** Dem Studio fehlt `color-scheme: light dark`. Ungestylte Steuerelemente bleiben im Dunkelmodus hell.
- **Behebung:** `color-scheme` am Wurzelelement des Studios setzen.
- **Abnahme:**
  - `check:contrast` grün;
  - Dunkelmodus in der Browser-Vorschau geprüft, mit Bildschirmfoto im Log.

## 5 Paket 5: nach Entscheidung

| Nr. | Thema | Empfehlung | Aufwand |
|---|---|---|---|
| P5-1 | C-H1 Sitzungssperre (F01) | `pg_try_advisory_lock` auf eigener Verbindung für den ganzen Zug, auch den SSE-Task. Mit Wartefrist, danach 409 „Sitzung beschäftigt“; Freigabe im `finally`. Danach ist `BACKEND_REPLICAS` wieder frei. Nachweis mit zwei Prozessen. | mittel |
| P5-2 | SSE-Abbruch (F02) | Zu Ende rechnen, wie heute faktisch, aber mit eigener DB-Sitzung je Zug; die Sperre hält bis zum Ende. Das Widget stellt nach `connected` keine zweite Anfrage, sondern holt die Antwort aus dem Verlauf nach; der POST-Rückfall greift nur vor `connected`. `turn_id` folgt als eigener Schritt, weil sie den Vertrag ändert. | mittel |
| P5-3 | Kosten für `/api/agent` (F09) | Migration: `usage_events.session_id` wird nullbar, dazu eine Spalte `quelle` (`chat`, `agent_api`). Auswertung und Studio-Kostenansicht zeigen die Quelle. | mittel |
| P5-4 | Einstellungen ohne Wirkung (F15-Rest) | `retention_days`: täglichen Lösch-Job bauen, idempotent, mit Vorschau im Studio. `agent.safety`, guide-mode `default_enabled` und `confidence_adjustments`: streichen. `01-base/rag-retrieval`: mit leerem Seed registrieren (ST-5 Befund 2). `inline_result_grouping` im Muster-Prompt: von `cards_enabled` lösen, danach Golden-Lauf. | klein–mittel |
| P5-5 | Wiederherstellen „exakt“ (F07) | als Option; Vorgabe bleibt ergänzend | klein |
| P5-6 | Responses-Plan (F19) | Entscheide E-A bis E-AC laut Plan, danach Golden-Lauf | mittel |
| P5-7 | Studio und Betrieb (F21) | HSTS über Traefik, CSP für `/studio`; widerrufbare Studio-Sitzungen mit Ablauf; Socket-Proxy; Sicherung auf zweitem Host mit Restore-Probe und Alarm; CORS-Vorgabe zu. Rollen später. | mittel–groß |
| P5-8 | markitdown-Extras (F17a) | Lizenzen laut Prüfer, vor dem Einbau mit dem Lizenz-Gate zu bestätigen: pdfminer.six MIT, mammoth BSD, python-pptx MIT plus Pillow HPND, openpyxl MIT. Offen ist die MPL-Frage im Lizenz-Gate. | klein |
| P5-9 | B-H3 Dienst-Token-Schreiben | unverändert, siehe Befundliste §2 | — |

## 6 Backlog: Ausbau-Vorschläge aus Audit §5–§9

- **Tempo:**
  - Bestehende Pläne:
    - Agent-Inline-Schnellantworten (Kette-Plan; den Master-Skill-Text überträgt der Nutzer);
    - RAG parallel zur Klassifikation (Kette-Plan).
  - Neue Ideen:
    - unabhängige Lese-Werkzeuge im Agent parallel ausführen;
    - MCP-Verbindungen wiederverwenden;
    - Singleflight für gleiche Cache-Fehlschläge;
    - Wiederholungsfenster A-B-A-B im Stillstands-Wächter;
    - Laufhistorie budgetieren.
  - Klassifikationsprompt verkleinern (mit Golden-Lauf).
- **Messung:**
  - Zeit bis zum ersten Text;
  - p95 je Maschine und Zugart;
  - Warteschlangenzeit getrennt messen.
- **Qualität:**
  - Quellenbezug hart prüfen;
  - lexikalische Suche neben den Vektoren;
  - harte Regeln in der Golden-Suite.
- **Studio:**
  - wirksame Konfiguration anzeigen: Seed, DB, Env und effektiver Wert;
  - Retrieval-Prüftisch;
  - Agent-Prüftisch mit Abbruch;
  - Job-Verwaltung mit Lebenszeichen, auch für E2;
  - Rollen und Auditspur.
- **Widget:**
  - Stopp-Knopf (nach P5-2);
  - Fehleraktion je Status, etwa 429 oder offline;
  - Feedback je Antwort;
  - Quellenbox;
  - Verlauf und Export;
  - Live-Region im Shadow DOM.
- **Rest F18:** Spekulative Schnellantworten tragen einen deutschen Platzhalter, ungemessen.
- **Dateien über 300 Zeilen:** eigene Refactor-Runde, die Schnitte stehen im Betriebsmodi-Plan §9.3.

## 7 Ablauf

- **Je Aufgabe:**
  1. zuerst ein roter Test;
  2. dann der Fix;
  3. dann ist der Test grün.
- **Schritt 0 jeder Phase:** `/better-coding-workflow` neu laden, bei Studio und Widget zusätzlich `/better-coding-frontend`.
- **Nach jeder Phase:**
  - Backend:
    - `cd backend && uv run pytest -q`;
    - `ruff`;
    - OpenAPI-Vertrag.
  - Frontend, falls berührt: lint, `check:*`, Unit ui/widget/studio.
  - Am Ende E2E zweimal.
- **Vertrag:**
  - Er wird nur bewusst erweitert, in C2, D5 und gegebenenfalls A3.
  - Jedes Feld kommt ins Log; der Vertrag wird nicht pauschal neu erzeugt.
- **Prüfung:** Danach prüft ein frischer Prüfer den Diff. Seine Befunde werden behoben und ins Log eingetragen.
- **Upload:**
  - ein Branch `paket-4-audit-extern` von main;
  - ein Commit je Aufgabe;
  - ein PR.
  - Den Merge macht der Nutzer.
- **Deploy:**
  - Migration `0006`;
  - Vorgabe `BACKEND_REPLICAS=1`;
  - neue Einstellung `MCP_CALL_TIMEOUT_S`.

## 8 Abnahme des Pakets

Grundlage sind die Prüfbereiche aus Audit §11.

| Bereich | Erfolg | Aufgaben |
|---|---|---|
| Werkzeugpolitik | Nicht angebotene und virtuelle Werkzeuge führen zu keinem Aufruf. | A2 |
| Schreiben | Einlösen geht nur unter derselben Identität. | A1 |
| Laufbudget | Langsames Werkzeug, langsames Modell, teure letzte Runde: Der Vertrag wird eingehalten oder ist sichtbar überschritten. | B1–B3 |
| Konfiguration | Zwei Editoren, verspäteter Abruf, ungültiger Restore: Konflikt statt Überschreiben, und der letzte Stand bleibt. | D1–D5 |
| RAG | Fehlende Vektoren: Texte bleiben erhalten, die Zähler stimmen, der Zustand ist reparierbar. | C2, C4, C5 |
| Struktur | Ungültige Klassifikation, ungültiges Ergebnis oder Schema: gültiger Rückfall oder klarer Fehler. | A3, C1 |

**Nicht in Paket 4:** zwei Repliken (P5-1) und der Stream-Lebenszyklus (P5-2).

## Log

Freigabe durch den Nutzer am 2026-10-03 („Plan zur Behebung der Funde umsetzen“). Damit gelten P4-1 bis P4-10.

Vorab hat der Nutzer gebeten, alte Images dieser App zu löschen:
- **Gelöscht:** `edu-chatbot-sc:{0.3,aktuell,befunde,kette,paket1}-lokal` und ein namenloses Image mit `boerdi.main` als Startbefehl.
- **Freigegeben:** etwa 2,9 GB.
- **Stehen gelassen:**
  - das Image des laufenden Testcontainers;
  - die Dev-Datenbank;
  - die namenlosen Images von `compendious-text-fastapi`;
  - fremde Basis-Images;
  - den gemeinsamen Build-Cache.

### V1 · erledigt (2026-10-03)
- **Rot:** Je Projekt ein Spec `testlauf.spec.ts` verlangt `new Date(0).getTimezoneOffset() === 0`. Unter Windows-Zeit war es rot (ui).
- **Fix:**
  - `frontend/vitest-base.config.ts` mit `testTimeout`/`hookTimeout` 30 000 und `unstubGlobals`; `TZ=UTC` wird vor dem Worker-Start gesetzt.
  - In den drei Test-Targets steht `runnerConfig`.
  - Der Builder meldet „Using Vitest configuration file“ und führt den `test`-Block mit seinen Vorgaben zusammen (`@angular/build`, `plugins.js`).
- **Probe:** Ein Spec mit 6 s Wartezeit lief grün; mit der alten Vorgabe von 5 s wäre es gekippt. Danach gelöscht.
- **Voller Lauf:** ui 867, widget 71, studio 1328 passed, Exit 0.

### A1 · erledigt (2026-10-03)
- **Rot:** sieben Tests.
  - `test_write_approval.py::TestFremderAufrufer` (5): fremder Aufrufer, gleicher Aufrufer, Merkposten ohne Kennzeichen, Einlösen fremd, Einlösen gleich.
  - Ende zu Ende `test_agent_schreib_abnahme.py::test_ein_ja_ohne_die_anmeldung_des_vorzugs_fuehrt_nichts_aus`.
  - Pin im Muster-Weg `test_write_confirm.py::…traegt_das_kennzeichen_des_aufrufers`.
- **Fix:**
  - `remember_pending(…, caller=)` speichert `caller_fingerprint()`. Beide Ablagen reichen es herein: `tool_loop`, `agent_write`.
  - `write_approval._gehoert_dem_aufrufer` prüft an zwei Stellen:
    - `discard_stale_approval` verwirft fremde Vorgänge zu Zugbeginn; damit sieht auch der Fingerabdruck-Weg im Tool-Loop sie nie.
    - `redeem_write_approval` hat eine zweite Wache, denn der Abnahme-Test fährt den Vorlauf ohne `setup`.
  - Ein Merkposten ohne Kennzeichen (vor dem Deploy) gilt als fremd.
- **Gegenprobe:** Mit abgeschalteter Prüfung wurden 4 der neuen Tests rot, auch der Ende-zu-Ende-Test. Der Mechanismus ist also echt nachgestellt.
- **Grün:** 135 passed (Abnahme-, Confirm-, Setup-, Preflight-Tests).

### A2 · erledigt (2026-10-03), mit einer Abweichung vom Plan
- **Agent:** Die Sperre steht jetzt vor den virtuellen Werkzeugen.
  - Rot: `test_virtuelle_werkzeuge_laufen_nur_angeboten` (3 Fälle).
  - Ein vorhandener Streaming-Test rief `respond_to_user` mit leerem Angebot. Er bietet es jetzt an, wie der Betrieb.
- **Muster:** `select_top_cards`, `respond_to_user` und `zeige_dokument` laufen nur noch mit Angebot. Die Auswahl hält sie bewusst zurück (Rückfrage-Muster, abgeschaltete Karten-Auswahl, Degradation); die Sperre setzt das durch.
- **Abweichung `query_knowledge`:** Es bleibt ohne Angebot rufbar. Die Vorprüfung fand:
  - Die globalen Domänen-Regeln verlangen es musterübergreifend (`02-domain/domain-rules.md:59`).
  - M10 verlangt es als Pflicht für Berichte, hat aber `sources: [llm]` und bekommt es deshalb nie angeboten.
  - Eine Sperre änderte diese Antworten und braucht erst einen Golden-Lauf. Ein Test pinnt die Ausnahme.
  - **Neuer Befund für die Befundliste:** Der Seed von M10 widerspricht sich (`sources` gegen Pflicht-Aufruf).
- **`tool_mode` (P4-1):**
  - `_select_active_tools(…, tool_mode=)` filtert das Angebot.
  - `_run_tool_loop(…, tool_mode=)` filtert die Katalog-Sperre, auch das Werkzeug eines offenen Vorgangs.
  - `generate.py` reicht `environment["tool_mode"]` an beide durch. Der Verdrahtungstest prüft das.
- **Grün:** Agent-Suiten 162 passed; Muster, Auswahl und `generate` 150 passed.

### A3 · erledigt (2026-10-03), mit einer Abweichung vom Plan
- **Neues Modul `domain/ergebnis_schema.py`:**
  - `schema_fehler` prüft das Schema und lehnt `$ref` nach draußen ab.
  - `argument_fehler` prüft gegen die angebotenen Parameter, höchstens 5 Meldungen mit Pfad.
  - `ergebnis_ungueltig` formuliert die Werkzeug-Antwort.
  - `jsonschema` ist direkte Abhängigkeit geworden. Im `uv.lock` kamen nur die zwei Einträge der Wurzel dazu, keine Version änderte sich.
- **Agent-Schleife:**
  - `submit_result` und `liefere_ergebnis` prüfen gegen `werkzeug_angebot.angebotene_parameter`.
  - Ein ungültiges Ergebnis geht an das Modell zurück.
  - Bei `submit_result` ist dasselbe Ungültige zweimal Stillstand. Bei `liefere_ergebnis` gilt das bewusst nicht, wie bisher.
- **Eingang:** `api/schemas_result.pruefe_ergebnis_schema` prüft für Chat (`Environment`) und Agent-Endpunkt, Fehler ergibt 422.
- **Abweichung Größendeckel:** `/api/agent` bekommt keinen. Er ist bewusst offen (Kommentar an `MAX_RESULT_SCHEMA_CHARS`: hinter `require_agent_caller`, angemeldete Maschinen).
- **Docstrings berichtigt:** `agent_tools`, `result_delivery`, `schemas_agent`.
- **Rot vorher:**
  - 10 Modul-Tests (Modul fehlte);
  - 4 Schleifen-Tests;
  - 2 Eingangstests.
- **Grün:** 204 passed; `ruff` sauber, nach Import-Sortierung in drei Dateien.

**Volle Backend-Suite nach Phase A:** 5023 passed, 1 failed (`test_tool_loop_zwei_choices`).
- Der Test rief den Tool-Loop mit leerem Angebot. Im Betrieb steht `zeige_dokument` aber immer im Angebot, außer im Rückfrage-Muster.
- Die Vorbedingung ist auf `active_tools=[dokument_werkzeug()]` berichtigt, die Erwartung blieb unverändert. Danach grün.

### B1 · erledigt (2026-10-03)
- **Neues Modul `services/agent_frist.py`:**
  - `innerhalb(ende, aufruf)` mit `asyncio.timeout_at`. Nur das eigene Fristende wird zu `FristAbgelaufen`; Zeitüberschreitungen des Transports bleiben, was sie sind.
  - Das Ende steht als Zeitpunkt der Ereignisschleife fest, nicht als Wert der eingereichten `clock`. Sonst verschöbe jede zusätzliche Abfrage die gefälschten Uhren der bestehenden Tests.
- **Schleife:**
  - Modellaufruf, Wissenssuche und MCP-Aufruf laufen innerhalb der Frist.
  - Bei Fristende bekommt der laufende Aufruf „Abgebrochen … ob der Aufruf den Server erreicht hat, ist offen“, die übrigen der Runde „Nicht ausgeführt“. Ende mit `deadline`.
  - Mitgenommen aus Audit 09-29 (6.3, gleiche Ursache): Ein Stillstand (`no_progress`) quittiert jetzt ebenfalls die übrigen Aufrufe der Runde. Sonst scheiterte der Abschluss-Aufruf in `respond_agent` an der Kette.
- **Budget:** Eine fertige Antwort über dem Budget wird geliefert und als Warnung samt `progress`-Eintrag gemeldet (P4-2). Das gilt für Text, `respond_to_user` und `submit_result`.
- **Startzeit:** `run_agent_loop(start=)`. `agent_run.run_agent` und `respond_agent` reichen ihre Startzeit herein, damit Gate und Vorabruf mitzählen.
- **Rot vorher:** 5 Schleifen-Tests und 2 Verdrahtungstests.
  - Ein Test riet das Wort „Frist“ im Text. Er prüft jetzt genau gegen die beiden Konstanten.
  - Die Attrappe in `test_respond_agent` hat die echte Signatur und bekam deshalb `start`.
- **Grün:** 169 passed.
- **Dateigröße:** `agent_loop.py` hat jetzt 623 Zeilen (vor Paket 4: 507). Das kommt in die Befundliste §5; die Teilung bleibt eine eigene Runde.

### B2 · erledigt (2026-10-03), mit einer Abweichung vom Plan
- **Einstellung:** `MCP_CALL_TIMEOUT_S`, Vorgabe 60, mindestens 5. Gesetzt in `settings.py`, `compose.prod.yml` und `.env.example`.
- **Transport:** `call_tool` legt `asyncio.timeout` um Verbindung, Handshake und Aufruf zusammen. Statt `read_timeout_seconds` des SDK, das nur das Lesen begrenzte.
  - Nur die eigene Frist wird zur Art `timeout`.
  - Ein `TimeoutError` aus dem SDK bleibt `transport`; das pinnt ein vorhandener Test.
- **Client:** Keine Wiederholung bei `timeout`. `call_mcp_tool_status` reicht `timeout` als Art weiter. Für die Schreib-Abnahme ist das dasselbe wie `transport` („bitte nachsehen“).
- **Abweichung:** Der Ergebnis-Status bleibt `error`, nicht `timeout`.
  - `call_with_outcome` liest nur den Text, und seine Tests patchen genau diese Naht.
  - Der Status bräuchte die Art bis dorthin, ändert an der Frist aber nichts.
- **Grün:** 111 passed (Transport, Client, Abnahme, Auth, Settings).

### B3 · erledigt (2026-10-03)
- **Gemessen** (offline, gefälschter Draht; Skripte im Scratchpad):

| Variante | Chat Verbindung | Responses Verbindung | Chat Zeitüberschreitung | Responses Zeitüberschreitung |
|---|---|---|---|---|
| heute `num_retries=2` | 5 | 6 | 5 | 3 |
| `num_retries=1` | 3 | 4 | 3 | 2 |
| ohne `num_retries` (SDK-Vorgabe) | **3** | **2** | **3** | **1** |

- **Erkenntnis:** Ist `num_retries` gesetzt, überdeckt es `max_retries`. Jede Variante damit ergibt auf der Responses-Brücke mehr als 3 Versuche.
- **Fix:** `num_retries` fällt in `wire_transport` und in `embedding` weg. Es gilt wieder die SDK-Vorgabe `max_retries=2` wie in ALT; der Modulkopf von `llm.py` sagte das schon.
- **Klassifikator:**
  - Er nimmt den Transport-Stempel mit und hat jetzt 3 bzw. 1 Versuch statt 5 bzw. 3.
  - Ein `max_retries` im Stempel hätte mit dem gleichnamigen Parameter von instructor kollidiert; deshalb kein expliziter Wert.
- **Folge:** Auf der Responses-Brücke wird eine Zeitüberschreitung nicht mehr wiederholt. Höchstens 75 s statt 225 s.
- **Rot vorher:** `test_llm_wiederholungen.py`, 4 von 6 rot.
- **Vier Tests umgestellt:** `test_llm` (2), `test_llm_streaming`, `test_classify`. Sie prüften `num_retries == 2`, also genau den Fehler; jetzt prüfen sie, dass es fehlt.
- **Grün:** 75 passed.

**Volle Backend-Suite nach Phase B:** 5038 passed, 2 failed (`test_agent_prompt_preview`).
- Zwei Attrappen von `run_agent_loop` hatten die alte Signatur ohne `start`.
- Sie bekamen `start=None`, die Erwartungen blieben unverändert. Danach grün.

### C1 · erledigt (2026-10-03)
- **Salvage:** `_salvage` prüft jedes Feld einzeln mit dem Modell und nimmt nur gültige Felder; das Ergebnis entsteht über `ClassificationResult.model_validate`, nicht mehr `model_construct`.
- **Buchung:** `_buche_fehlversuche` bucht `InstructorRetryException.total_usage` als `classify`, bevor der Rettungsweg zurückkehrt.
- **Rot vorher:** `test_fallback_verwirft_ungueltige_typen_und_werte`, `test_fallback_bucht_den_verbrauch_der_fehlversuche`.

### C2 · erledigt (2026-10-03)
- **Import:** `ingest_document` gibt `ImportZahlen(chunks, embedded)` zurück und speichert jeden Abschnitt, auch ohne Vektor.
  - Ein Vektor falscher Länge (`expected_dim`) wird `None` und als „EMBED_DIM“-Warnung gemeldet.
  - Fehlen Vektoren, steht eine Warnung im Log.
- **API:** Die Import-Antwort trägt `embedded` und `missing`.
- **Studio:** `studio-rag-embed-missing` zeigt nach einem Import mit Lücken, wie viele Abschnitte die Suche noch nicht findet, und holt sie per `POST /rag/embed` nach.
  - Die Statuszeile (`aria-live`) steht vor ihrem Inhalt im DOM; der Fehler hat `role="alert"`.
  - Texte de/en mit Pluralformen.
- **Rot vorher:** drei Import-Tests, der Router-Test für `missing`, `test_ein_import_mit_ausfall_wird_vom_nachholen_vervollstaendigt` (Postgres) und die sechs Specs der neuen Komponente.
- **Berichtigt:** Der pg-Test setzt vor dem Import die Sequenzen (`setval`), sonst kollidierte der Primärschlüssel mit den Seed-Zeilen.

### C3 · erledigt (2026-10-03)
- Der Schlüssel des MCP-Caches enthält die Server-URL: `[Aufrufer, URL, Argumente]`.
- **Rot vorher:** `test_cache_key_unterscheidet_den_server`, Ende zu Ende `test_der_cache_trennt_die_server`.
- Zwei vorhandene Tests bauten den Schlüssel ohne URL nach; sie übergeben jetzt `url=FAKE_URL`.

### C4 · erledigt (2026-10-03)
- Eigener Kanal `ingest` im LLM-Semaphor, so groß wie `EMBED_INGEST_PARALLEL`. `embed_many` nutzt ihn; der lokale Semaphor in `rag/embed.py` ist weg.
- Live-Anfragen behalten ihren Kanal; ein Test hält einen Live-Platz frei, während der Import läuft.

### C5 · erledigt (2026-10-03)
- **Abruf:** `url_safety.hole_begrenzt` holt über die SSRF-Sitzung mit `timeout=(5, 30)`, einer Obergrenze in Bytes (Kopf und Körper) und einer Gesamtfrist von 60 s. markitdown liest danach aus dem Speicher (`convert_stream` mit `StreamInfo`).
- **Format:** Ein Format, das das Image nicht liest, wird 415 mit einem eigenen Satz (`ingest.formatUnsupported`, de/en), statt 400 mit der Meldung von markitdown.
- **DNS:** `assert_public_url` läuft im Thread, beim URL-Import und bei `discover` in `api/config.py`.
- **Studio:** Die Dateiauswahl bietet nur lesbare Formate an (`accept`), der Hilfetext nennt sie, und 415 hat einen eigenen Satz (`rag.error.format`).
  - Ein Spec las den falschen Hilfetext: `.ri-help` traf bei leerer Bereichsliste zuerst den Hinweis zum neuen Bereich. Es liest jetzt `#ri-file-help`.
- **Rot vorher:** 5 Tests für `hole_begrenzt`, `test_ein_abgebrochener_abruf_wird_benannt`, `test_die_dns_pruefung_laeuft_nicht_im_event_loop`, der Format-Test (2 Fälle), der 415-Router-Test, der DNS-Test für `discover` und zwei Studio-Specs.

### C6 · erledigt (2026-10-03), mit einer Ergänzung zum Plan
- **Engine:** `PatternDef.rag_areas` ist `list[str] | None`, Vorgabe `None`. `phase3_modulate` reicht `None` durch, der Zweig für die Vorgabe der Bereiche in `route_head` ist damit erreichbar. `turn_persist` schreibt weiter eine Liste (`or []`), Debug-Ansicht und Gastgeber-Ereignis lesen sie als solche.
- **Rot vorher:** `test_ein_rag_muster_ohne_liste_erbt_die_vorgabe_der_bereiche` (`[] == ['a', 'b']`).
- **Pins, schon vorher grün:**
  - `test_eine_leere_liste_bleibt_kein_rag`;
  - `test_jedes_seed_muster_behaelt_seine_bereiche` über alle 20 Seed-Muster;
  - `test_bereiche_ohne_angabe_stehen_als_leere_liste_im_debug`. Gegenprobe: mit dem alten Leser rot.
- Die neuen Tests laufen über `phase3_modulate`. Die alten reichten die Muster-Ausgabe von Hand herein und konnten den toten Zweig deshalb nicht sehen.
- **Kommentare berichtigt:** `route_head`, `response_tool_selection` (ein Muster ohne `sources` hat `["mcp"]`, also kein RAG, nicht „alles“) und der Kopf von `rag-config.yaml`.
- **Ergänzung, Studio-Texte:** Sie wurden mit dieser Änderung falsch bzw. waren es schon.
  - Hinweis zu den Wissensbereichen eines Musters: „Nie gesetzt heißt alle Bereiche, eine geleerte Liste heißt keine“.
  - Abrufart der Bereiche, und „always legt einen Bereich in jeden Prompt“ auf der Wissen-Seite (stimmte nie).
- **Nicht übernommen aus der Abnahme des Audits** („ungültiger Bereich wird sichtbar abgewiesen“):
  - Der Katalog ist bewusst offen. Ein neuer Bereich darf getippt werden, bevor er eingelesen ist.
  - Für den Seed wacht `test_bereiche_stehen_wirklich_in_der_konfiguration`.
- **Folgepunkt für die Befundliste:** Das Formular zeigt „nie gesetzt“ und „leere Liste“ gleich an. Wer den letzten Bereich entfernt, schaltet das Erben ab, ohne es zu sehen. Die Anzeige der wirksamen Bereiche je Muster (Audit F13, Verbesserung) bleibt offen.

**Volle Backend-Suite nach Phase C:** 5084 passed, 4 skipped, 1 failed (`test_openapi_contract`).
- Abweichend war nur die Beschreibung von `POST /api/rag/embed`. Ihr Docstring ist in C2 bewusst berichtigt worden.
- `docs/api/openapi-v1.json` ist mit `scripts/export_openapi.py` neu erzeugt. Ein Vergleich vorher/nachher zeigt nur diese eine Zeile. Danach grün.
- `ruff` sauber. Studio: RAG-, i18n- und Schema-Form-Specs 362 passed.

### D1 · erledigt (2026-10-03)
- **Cache:** `ConfigStore` hält je Bereich die Version neben den Daten (`SELECT data, version`).
  - Ein Abruf mit älterer Version als der gehaltenen wird verworfen.
  - `put` setzt die zurückgegebene Version; eine neuere, die eine andere Replik inzwischen geschrieben hat, bleibt.
  - Löschen und Leeren (`clear_cache`) vergessen Daten und Version zusammen. Eine neu angelegte Zeile beginnt in Postgres wieder bei 1.
- **Ein Abruf je Bereich:** Meldungen während eines Abrufs lösen genau einen weiteren danach aus (`_refresh_until_quiet`).
- **Rot vorher** (`tests/test_config_store_frische.py`, ohne Datenbank, mit Attrappe der Engine): langsamer alter Abruf gegen neuen, laufender Abruf gegen `put`.
- **Pins:** Löschen und Neuanlage, geleerter Cache. Dazu kam ein Test „genau ein weiterer Abruf“. Gegenprobe: ohne Single-Flight rot, denn die Versionsprüfung allein macht den ersten Test schon grün.
- Die Attrappe in `test_notify_reconnect.py` liefert jetzt `(data, version)`, die Erwartung blieb unverändert.
- **Grün:** 7 Tests ohne Datenbank; `test_config_store.py` und `test_pg_locks_notify.py` gegen Postgres.

### D2 · erledigt (2026-10-03)
- `ConfigStore.all_data()` liest alle Bereiche aus der Datenbank. `config_loader.current_config()` ist jetzt `async` und nutzt sie.
- Schnappschuss, Werksstand, Sicherung, Seed-Status und Seed-Anwenden (beide Vergleiche) lesen damit den gespeicherten Stand.
- **Rot vorher:** `test_die_sicherung_kommt_aus_der_datenbank_nicht_aus_dem_cache`. Eine andere Replik schreibt per `UPDATE`, der Cache hält noch `alt`, und die Sicherung enthielt `alt`.
- Zwei Tests riefen `current_config()` synchron auf; sie warten jetzt darauf, die Erwartung blieb unverändert.
- **Grün:** 35 passed (`test_snapshots_endpoints`, `test_seed_sync`).

### D3 · erledigt (2026-10-03), mit zwei Abweichungen vom Plan
- **Vorab geteilt:** `api/config.py` hatte 391 Zeilen, und D3/D5 kommen dazu.
  - Die Schlüssel- und Dokumentprüfungen stehen jetzt unverändert in `api/config_guards.py`, verschoben per Skript an festen Markierungen.
  - Nachweis: 18 Testdateien mit Bezug zu `/api/config`, 244 passed, vor jeder inhaltlichen Änderung.
- **Modellprüfung:** `modell_fehler(key, data)` ist die eine Prüfung für Formular, Rohtext und Wiederherstellen. Bereiche ohne Modell passieren.
  - Das Wiederherstellen sammelt alle Einwände, jeder mit `area`, und antwortet mit einem 422. Geschrieben wird dann nichts.
  - Der Rohtext-PUT parst vor dem Schreiben (`config_loader.parse_config_file`), prüft und schreibt dann über die bekannte Grenze `write_config_file`. Dazwischen liegt kein `await`, das Gespeicherte ist also das Geprüfte.
- **Schlüssel:** `is_restorable_area_key` lehnt `.`-Segmente und die Gruppen selbst ab. Unter `03-patterns/` und `04-personas/` gilt genau ein Blatt, mit derselben Hilfsfunktion wie `_is_file_key`.
- **Abweichung 1:** Der Plan nannte `bad-mode` als ungültigen Wert. `Choices` prüft aber bewusst nicht (Kommentar in `_shared.py`: Bedienhilfe, keine Verschärfung). Die Tests nehmen deshalb `quick_replies: not-a-list`.
- **Abweichung 2:** Der Rohtext-PUT bekommt auch die Schlüsselregel. Ihr Docstring nannte sie schon „die Pfadregel des rohen Datei-Schreibens“.
- **Studio:** Ein 422 mit `area` zeigt den Bereich vorn an („03-patterns/m04-… › frontmatter.priority: …“). Ohne ihn sagte ein Einwand in einer Sicherung mit dreißig Bereichen nicht, welches Muster gemeint ist.
- **Rot vorher:**
  - `test_config_guards.py`: Schlüssel und Modellprüfung, ohne Datenbank;
  - `test_restore_prueft_gegen_das_modell_und_schreibt_nichts`;
  - `test_der_rohtext_wird_gegen_das_modell_geprueft`;
  - `test_der_rohtext_legt_keine_verschachtelten_muster_an`;
  - ein Studio-Spec (`studio-api.service.spec.ts`).
- **Grün:** Backend 190 passed in den Config-Tests; Studio 421 passed (core, schema-form, Sicherung).
- **OpenAPI:** Nur die Beschreibung von `PUT /config/file` änderte sich. Der Vertrag ist neu erzeugt, der Vergleich zeigt sonst nichts.

### D4 · erledigt (2026-10-03), mit einer Abweichung vom Plan
- **Store:** `ConfigStore.put_many(items, updated_by, delete=())` schreibt alle Upserts und Verlaufszeilen, danach die Löschungen, in einem `begin()`.
  - Der Cache folgt erst nach dem Commit.
  - `put` ist jetzt `put_many` mit einem Bereich.
  - Fassade: `config_loader.write_areas`.
- **Wiederherstellen** schreibt über `write_areas`.
- **Seed-Anwenden:** Die Rückrufe von `seed_sync.anwenden` sammeln nur noch; danach schreibt und löscht ein `write_areas`.
- **Abweichung:** `anwenden` selbst und seine Tests ohne Datenbank bleiben unverändert. Der Atomaritäts-Test steht beim Endpunkt (`test_seed_anwenden_schreibt_alles_oder_nichts`), nicht in `test_seed_sync.py`.
- **Prüfstein:** Postgres weist `\u0000` in jsonb ab. Das ist ein Fehler der Datenbank selbst, im letzten Bereich, nach allen Prüfungen davor.
- **Rot vorher:**
  - Wiederherstellen hinterließ `rag-retrieval` und die neue Begrüßung.
  - Seed-Anwenden hinterließ die Seed-Begrüßung, ohne zu löschen.
  - `put_many` fehlte (2 Store-Tests).
- **Grün:** 60 passed (Store, Sicherung, Seed, Frische, NOTIFY).
- Ein Datenbankfehler bleibt ein 500 wie bisher. Die Umsetzung in eine 400 („Bereich nicht speicherbar“) ist nicht Teil von D4.

### D5 · erledigt (2026-10-03), mit drei Abweichungen vom Plan
- **Store:** `put(…, expected_version=, create_only=)` schreibt bedingt.
  - Mit Version gilt `UPDATE … WHERE version = :v`; beim Anlegen gilt `INSERT … ON CONFLICT DO NOTHING`.
  - Ohne Treffer liest der Store den Stand nach und wirft `ConfigConflict` (Version, Zeitpunkt, Weg). Ist die Zeile gelöscht, steht dort `None`.
  - Eigenes Modul `services/config_conflict.py`, damit `config_store.py` eine Aufgabe behält. Die Datei hat trotzdem 309 Zeilen; das kommt in die Befundliste §5.
  - Ohne Bedingung bleibt der Upsert wie bisher. Die Version ist auf dem Server optional.
- **API:**
  - `PUT /config/data`, `/config/file` und `/mcp-servers` nehmen `expected_version`; die ersten beiden auch `create`.
  - 409 trägt `detail = {message, version, updated_by, updated_at}`. Meldungen `config.conflict`, `config.conflictGone` und `config.exists` (de/en).
  - Die PUT-Antworten tragen `version`.
- **Abweichung 1, frische Lesart:** `GET /config/data` und `GET /config/file` lesen Daten und Version aus der Datenbank (`ConfigStore.read`), nicht aus dem Cache. Sonst zeigte „Neu laden“ nach einem 409 denselben veralteten Stand, solange die NOTIFY einer anderen Replik unterwegs ist.
- **Abweichung 2, MCP-Registry:** Das GET liefert eine Liste. Die Version steht deshalb im Kopf `X-Config-Version`, der Körper bleibt unverändert. Die BFF reicht Antwortköpfe durch (`studio_proxy.py` schreibt nur `Location` um).
- **Abweichung 3, „Wer“:** Den Namen einer Person kennt der Server nicht, das Studio teilt eine Anmeldung. Der Hinweis nennt deshalb Zeitpunkt und Weg („Formular“, „Rohtext“, „Wiederherstellung“ …); einen unbekannten Weg zeigt er so, wie er kam.
- **Studio:**
  - `StudioApiError.conflict` liest das 409-Objekt, `detail` ist dessen `message`. `StudioApi.getVersioned` liest den Kopf.
  - `ConfigApi.saveCondition(version)`: eine Zahl wird `expected_version`, `null` (keine Zeile) wird `create`, ein fehlendes Feld bleibt ohne Bedingung.
  - `AreaDocEditor` hält `version` und `conflict`. `save(…, {force})` speichert gegen genau die gemeldete Version; kam inzwischen noch etwas, gibt es wieder 409.
  - Neue Komponente `studio-save-conflict`: Satz mit Zeitpunkt (ortsüblich über `StudioFormat.dateTime`) und Weg, „Neu laden“ und „Trotzdem speichern“, beide gesperrt, solange gespeichert wird.
    - Bei jedem neuen Konflikt holt die Gruppe den Fokus (`afterRenderEffect`). Ihr Name ist der Satz.
    - Den Fokusring stellt der globale `:focus-visible`.
  - Eingebaut in Bereichs-Editor (Formular und Rohtext), Bereichs-Abschnitt, Gruppen-Abschnitt und MCP-Registry. Der Entwurf bleibt bis zur Wahl erhalten.
  - „Neues Dokument“ sendet `create`, die Kennung kommt aus dem ganzen Titel. Bei 409 steht „gibt es schon“.
  - „Duplizieren“ vergibt `<id>_kopie`, `_kopie_2` …
- **Rot vorher:**
  - Backend: 3 Store-Tests, 7 Endpunkt-Tests für Daten und Rohtext, 4 MCP-Tests.
  - Studio: 2 Specs für API-Fehler und Version, 5 für den Editor-Kern, 4 im Bereichs-Editor, 1 im Bereichs-Abschnitt (neue Spec-Datei), 3 im Gruppen-Abschnitt, 2 in der MCP-Registry, 2 in der Objektliste und 6 für den Hinweis (neu).
- **Angepasst:**
  - Bisherige Erwartungen:
    - die Liste der Objektliste: Ihr Test sagte die doppelte Kennung zu;
    - die exakte Antwort eines MCP-PUT und eines Daten-GET: jetzt mit `version`;
    - ein D3-Test: Er nahm einen leeren Bereich an, die Modul-Datenbank ist aber geteilt; jetzt prüft er „unverändert“.
  - Vorbedingungen: Attrappen der Schreibgrenzen (`FakeStore.put`, Spione) nehmen die neuen Schlüsselwörter.
- **Grün:** Studio komplett 1364 passed (114 Dateien); `check:*` und eslint sauber. Backend: Config-Tests grün; die volle Suite folgt unten.
- **OpenAPI:** bewusst erweitert, drei optionale Felder und Beschreibungen, nichts entfernt. Der Vertrag ist neu erzeugt.

**Volle Backend-Suite nach D1–D5:** 5126 passed, 4 skipped, 1 failed (`test_i18n_messages`, Meldungs-Wächter).
- Zwei Meldungen stehen seit der Teilung in D3 in `config_guards.py`; ihre Einträge in `BEWUSST_EINSPRACHIG` sind mitgezogen.
- Das 409-Objekt aus D5 hielt der Wächter für freien Text: Die Schlüssel in `cur.get("version")` sind Zeichenketten. Die Werte stehen jetzt vorab in Variablen, und der Wächter sieht nur noch Namen.
- Danach grün.

### D6 · erledigt (2026-10-03), mit einer Ergänzung zum Plan
- **Speichern:** `_assert_area_document_safe` prüft in `02-domain/guide-rules` jedes `message_rules[].pattern` so, wie der Lotse es übersetzt (getrimmt, `re.IGNORECASE`). Ein Fehler ergibt 400 mit Nummer und Beschriftung (`guide.patternInvalid`, de/en). Das gilt für Formular, Rohtext und Wiederherstellen.
- **Ergänzung, nachsichtiges Laden:** Laut Plan sollte das Laden nachsichtig *bleiben*. Das war es nicht: `_compiled()` übersetzte alle Regeln in einem Zug, ein `re.error` brach die Liste ab, und `guide_markers` schaltete damit alle Lotsen-Knöpfe ab. Jetzt kostet ein ungültiges Muster nur seine Regel (Warnung im Log).
- **Texte:** Studio-Hinweise (`fields-lotse.ts`, de/en, auch der Kopfkommentar) und der Kommentar in `area_effects.py` sagen nicht mehr „nach Neustart“. `test_area_effects` pinnt diesen Kommentar nicht; dort war nichts zu ändern.
- **Rot vorher:**
  - `test_ein_ungueltiges_muster_kostet_nur_seine_regel` (`re.error`);
  - `test_ein_ungueltiges_lotsen_muster_wird_beim_speichern_abgewiesen`.
- **Dazu:** ein Endpunkt-Test gegen Postgres (400, nichts geschrieben).
- **Grün:** 119 passed (Wächter, Injektor, MCP, i18n) plus der Endpunkt-Test.

### D7 · erledigt (2026-10-03)
- **Abhängigkeit:** `langgraph-checkpoint-postgres` ist aus `pyproject.toml` gestrichen. `uv lock` entfernt mit ihm `psycopg`, `psycopg-pool` und `tzdata` (nur Windows, für psycopg); `uv sync --locked`.
  - Kein Code nutzt `zoneinfo`.
  - Keine Migration nutzt den Checkpointer: 0002 ist `usage_events`. Die Zeile im Neubau-Plan war eine nie gebaute Absicht.
- **CI:** Die `--ignore-packages psycopg psycopg-pool`-Ausnahme samt Kommentar ist weg, ebenso der Verweis darauf im npm-Gate. `ci.yml` parst.
- **Prüfungen lokal:**
  - Lizenz-Gate ohne Ausnahme, Exit 0;
  - `pip-audit==2.10.1 --strict` gegen den Lock-Export (136 Pakete): keine bekannten Schwachstellen;
  - `test_alembic_logging`: grün ohne psycopg, der Offline-Modus lädt den Treiber nicht; unverändert;
  - frisch migrierte pg-Datenbank (`test_config_store`): 13 passed.
- **Neubau-Plan:** Ausnahme §0.1, die Stack-Tabelle und der Checkpointer-Absatz sind nachgezogen.
- **Offen für L5:** die Zeile in `offene-befunde-und-todo.md` (Z. 181). In der CI zusätzlich der Image-Smoke.

### D8 · erledigt (2026-10-03)
- **Neues Modul `services/safety/zusatz_begriffe.py`:** liest `extra_crisis_terms` und `extra_pii_terms` aus `01-base/safety-config`.
  - Normalisiert wie die Nachricht: Das Gate reicht `normalize_for_matching` herein, das vermeidet einen Kreisimport.
  - Leere und doppelte Einträge fallen weg; danach `re.escape` und eine Alternation ab Wortanfang (`(?<!\w)`).
  - Übersetzt wird einmal je Stand der Listen. Scheitert das Laden, gibt es eine Warnung, und das Gate läuft mit seinen eigenen Listen weiter.
- **Gate:** `regex_gate.py` hat 274 Zeilen.
  - Krise: eingebaute Muster, dann die Zusatz-Begriffe, mit derselben Folge (M01, Sperre, `crisis_signal_detected`), vor den Drohungen.
  - PII: eingebaute Paare, dann die Zusatz-Begriffe, mittlere Stufe.
  - Gilt auf allen sechs Wegen des Gates (Assess, Preflight, Tour, Agent-Gate, Dienst).
- **Modell:** höchstens 200 Begriffe zu je 100 Zeichen (`_Begriff`). Mit `Field(default=[], …)`, damit das Schema seine Vorgabe behält; `default_factory` hätte `"default": []` gestrichen.
- **Studio:**
  - Fixture neu erzeugt (`export_area_schemas.py`): Der Unterschied sind genau die vier Deckel.
  - `JsonSchema` kennt jetzt `maxLength` und `maxItems`, sonst kompilierte die Fixture nicht.
  - Hinweise (de/en) und Kopfkommentar in `fields-sicherheit.ts` sagen nicht mehr „Wird derzeit nicht ausgewertet“; sie nennen Wirkung, Wortanfang und Deckel.
- **Rot vorher:**
  - 5 Gate-Tests: Krise; Nullbreite und NFD; PII; Wortanfang;
  - 2 Modell-Tests für die Deckel.
- **Pins:** leere Begriffe treffen nichts; ohne Begriffe bleibt alles, wie es war.
- Ein eigener Test erwartete `enforced_pattern is None`. Die Vorgabe des Modells ist aber `""`; das war ein Fehler des Tests, nicht des Codes.
- **Grün:** 86 Gate-Tests einschließlich der Laufzeit-Tests, 94 mit Modell, Choices und Agent-Gate; Fixture-Wächter grün; Studio komplett 1364 passed.

**Volle Backend-Suite nach Phase D:** 5140 passed, 4 skipped, 0 failed; `ruff` sauber. Studio komplett: 1364 passed; `check:*` und eslint sauber.

### E1 · erledigt (2026-10-03)
- `list_runs` und `get_trends` laden mit `defer(EvalRun.conversations)`. Der Docstring von `get_trends` („transcripts stay untouched“) stimmt damit erst jetzt.
- **Test zuerst:** Die Attrappe der Session hält das gesendete SQL fest, und es darf `conversations` nicht nennen; je ein Fall pro Abfrage, beide rot vorher.
- **Grün:** 5 passed (`test_eval_queries`).

### E2 · erledigt (2026-10-03)
- **Migration `0006_ein_laufender_eval`:** `CREATE UNIQUE INDEX IF NOT EXISTS uq_eval_runs_ein_laufender ON eval_runs ((true)) WHERE status = 'running'`.
  - Davor gehen überzählige `running`-Zeilen (Absturz-Reste) bis auf die jüngste auf `failed`. Sonst ließe sich der Index nicht anlegen, und die Migration hielte den Start der Anlage auf.
- **Anlegen:** `run_store._lauf_anlegen(session, run)` macht aus `IntegrityError` dieselbe 409 wie die Vorab-Prüfung, mit der Kennung des Laufs, der gewonnen hat. Golden- und generativer Start nutzen es.
  - Das Aufräumen nach `created_at` bleibt.
  - **Bekannte Grenze:** Ein Lauf über 2 h wird beim nächsten Startversuch beendet. Ein Lebenszeichen steht im Backlog.
- **Rot vorher:** `test_zwei_gleichzeitige_starts_ergeben_genau_einen_lauf_und_eine_409` (pg) zeigte zwei laufende Läufe. Eine `asyncio.Barrier(2)` lässt beide Starts die echte Prüfung bestehen, bevor einer anlegt.
- **Grün:** 48 passed (`test_eval_pg`, `test_eval_run_store`, `test_eval_queries`, `test_eval_runner`); `ruff` sauber.
- **Migrations-Probe** (Wegwerf-Datenbank, Skript im Scratchpad):
  - head mit Index, `downgrade -1` ohne, `upgrade head` wieder mit;
  - zwei Reste `running`: der ältere wird `failed` mit Begründung, der jüngere bleibt.

### L4 · erledigt (2026-10-03)
- **Vorgabe:** `compose.prod.yml` hat `replicas: ${BACKEND_REPLICAS:-1}`, mit Begründung (C-H1). In `.env.example` steht `# BACKEND_REPLICAS=1`, die Faustregel erst nach C-H1.
- **Doku angeglichen:**
  - `INSTALL.md`: keine „3 für 6 Kerne“ mehr;
  - `deploy/README.md` „Skalieren“;
  - `docs/cluster-checkliste.md`: 3 Replikas bewusst gesetzt, nur zum Prüfen;
  - `README.md`: „clusterfähig angelegt, Vorgabe 1“.
- **Befundliste §4:** Hinweis auf die neue Vorgabe; dort ist auch Migration 0006 nachgetragen.
- **Rot vorher:** `test_ohne_eintrag_laeuft_genau_eine_replik`. Grün: `test_deploy_compose` 8 passed.

### L2 · erledigt (2026-10-03)
- **Skript `frontend/scripts/check-audit.mjs`:** `bewerte(bericht, ausnahmen, heute)` ist rein, `main()` ruft `npm audit --json` auf.
  - Unter Windows läuft es über eine Shell, die Argumente sind fest.
  - `maxBuffer` 64 MiB.
- **Regeln:**
  - ab `high` rot;
  - Ausnahmen in `frontend/audit-ausnahmen.json` mit `ghsa`, `grund` und `bis` (inklusive);
  - abgelaufene oder unvollständige Ausnahmen sind rot, auch ohne zugehörigen Fund.
- **Test zuerst:** `node --test scripts/check-audit.test.mjs`, 8 Fälle, rot vorher (Modul fehlte), dann grün. Keine neue Abhängigkeit.
- **npm-Skript:** `check:audit`.
- **CI:** zwei Schritte nach dem npm-Lizenz-Gate, erst die Bewertung, dann der echte Baum. `ci.yml` parst.
- **Erster echter Lauf (vor L1):** rot mit `GHSA-ff3f-86qr-9cv3` (@angular/router), `GHSA-67c8-pqhq-4rmx` (piscina, critical) und `GHSA-ch52-4w7c-c8xp` (http-cache-semantics).

### L1 · erledigt (2026-10-03), mit zwei Abweichungen vom Plan
- **Update:** `ng update @angular/core@22.2 @angular/cli@22.2 @angular/material@22.2 --allow-dirty`.
  - `--allow-dirty`, weil über dem Staging-Ordner ein Git-Arbeitsbaum liegt; Sicherungen von `package.json` und Lock lagen im Scratchpad.
  - 12 Pakete gingen auf 22.2.1. `piscina` ist jetzt 5.3.2. Keine Migrationen nötig.
  - `angular-eslint` (22.5) bewusst nicht, es ist kein `@angular/*`.
  - Zeilenenden (CRLF) unverändert.
- **Gate danach:** nur noch `GHSA-ch52-4w7c-c8xp`.
  - `http-cache-semantics` 4.2.0 ist die letzte Version, eine behobene gibt es nicht.
  - Es kommt nur über den Lizenz-Prüfer `license-checker-rseidelsohn` (dev, CI) via `@npmcli/arborist`. Die Lücke betrifft geteilte HTTP-Caches, und die gibt es dort nicht.
  - Ausnahme bis 2026-12-31, mit Begründung. Gate grün (Exit 0).
- **Abweichung 1:** Die Abnahme „`npm audit` meldet nichts ab `high`“ gilt nur mit dieser Ausnahme. Das rohe `npm audit` zählt 11 high, alle Abhängige dieses einen Funds. Kein `npm audit fix --force`: npm schlägt dort nur ein Major-Downgrade des Prüfers vor.
- **Abweichung 2, Studio-Budget:**
  - Unter 22.2 scheitert `build:studio` an `initial` 1,08 MB > 900 kB.
  - **Ursache gemessen:**
    - main-CI-Log (Angular 22.1): `main` 516 kB als einziger initialer Chunk, der gemeinsame 552-kB-Chunk unter „Lazy“;
    - lokal (22.2): derselbe Chunk mit `@angular/core`, `@angular/common`, `material`, `marked`, `dompurify` initial; `main` importiert ihn statisch, `index.html` lädt ihn per `modulepreload`;
    - A/B mit dem main-Quellstand und 22.2: 1,07 MB.
  - Der Chunk trägt also `@angular/core`, das `main` beim Start braucht. Er lud schon immer beim Start; 22.1 hat ihn nur falsch als „lazy“ ausgewiesen.
  - **Budget:** jetzt Warnung 1,1 MB, Fehler 1,2 MB, also nah am echten Stand, damit Wachstum weiter auffällt.
  - **Echter Befund für die Befundliste:** Beide Sprach-Kataloge (434 kB) laden eager.
- **Abnahme:**
  - lint, `check:*` grün;
  - Unit: ui 867, widget 71, studio 1364;
  - Widget-Budget 554/600 kB raw, 161/175 kB gzip;
  - `build:studio` grün;
  - E2E 50 passed.

### L3 · erledigt (2026-10-03), Nachweis erst nach dem Merge
- **Auslöser:** `push` (main und Tags) ist durch `workflow_run: workflows: [ci], types: [completed]` ersetzt. `pull_request` (Bau und Smokes) und `workflow_dispatch` bleiben.
- **Neuer Job `stand`:**
  - läuft nur bei `success` eines `push`-Laufs, oder wenn der Workflow nicht über `workflow_run` gestartet wurde;
  - setzt `art`: main, Tag (per `gh api …/git/ref/tags/<name>`), `sonst` (Feature-Branch: kein Image, wie bisher), `pull_request` oder `workflow_dispatch`;
  - liefert `sha` und `name` aus `workflow_run.head_sha` und `head_branch`.
- **`build-and-smoke`:** `needs: stand`, Checkout auf `stand.sha`.
  - `latest` und die Tag-Marke hängen an `art`.
  - Handstart wie bisher über `GITHUB_REF` bzw. `GITHUB_REF_TYPE`.
  - `concurrency` nach `head_branch`.
- **Sicherheit:** Fork-PRs lösen `workflow_run` mit ihrem `ci`-Lauf ebenfalls aus. Weil nur `event == 'push'` zählt, bekommt Fremd-Code kein `packages: write`.
- **Kopfkommentar** neu gefasst, Begründung samt Preis: Das Image kommt um die `ci`-Dauer später.
- **Geprüft lokal:** YAML parst; Struktur geprüft (Auslöser, Jobs, `needs`/`if`, Checkout-Ref).
  - `actionlint` ist nicht installiert. Laut Plan „falls vorhanden“, also nicht nachgeladen.
- **Nachweis nach dem Merge (Nutzer bzw. Upload-Lauf):** `gh run list` zeigt `image` erst nach grünem `ci` für denselben Commit. `workflow_run` wirkt nur aus der Datei auf dem Standard-Branch, vorher also nicht prüfbar.
- **Bekannte Grenze:** Trägt ein Feature-Branch denselben Namen wie ein vorhandener Tag, gilt sein Push als Tag. Die Marke käme trotzdem erst nach grünem `ci`.
- **Dateigröße:** `image.yml` hat 360 Zeilen, überwiegend Begründungs-Kommentar.

### L5 · erledigt (2026-10-03)
- **Audit 2026-09-29 §6:** 23 Punkte haken, je mit Paket und Aufgabe (Pakete 1, 3, 4). Teilweise Erledigtes steht mit ◐ und nennt den Rest. Die Legende ist erweitert. F-M6 (Live-Regionen) und `color-scheme` folgen mit Phase S.
- **`architektur.md`:** Zählstände mit Datum:
  - 74 Settings-Felder;
  - 285 Backend-Testdateien, > 5100 Tests;
  - 69 Seed-Dateien;
  - 195 Frontend-Spec-Dateien.
- **`INSTALL.md`:** TLS-ALPN-01 statt HTTP-01. Die Einleitung nennt den Auto-Import durch `migrate` (`--only-missing`, einmal, vor den Backends) statt „kein Auto-Import“.
- **Befundliste:**
  - Kopf und Paket-4-Status nachgezogen.
  - §5 Dateigrößen: `agent_loop` 623, `config_store` 309, `image.yml` 360.
  - Der Angular-Block ist ersetzt durch: Audit-Ausnahme mit Ablauf, Studio-Startpaket mit Katalog-Befund, Formular-Anzeige der Wissensbereiche (C6) sowie 500 statt 400 bei Datenbankfehlern (D4).
  - Gestrichen: Zusatz-Begriffe (D8) und `langgraph-checkpoint-postgres` (D7) unter „Einstellungen ohne Leser“.
  - §2: Die RAG-Frage (beantwortet in P4-4, Zweig durch C6 erreichbar) ist ersetzt durch den Widerspruch in M10 (A2, Nutzer-Entscheid).
  - §4: Migration 0006 und die neue Replika-Vorgabe (L4).
- **Plan:** Status im Kopf auf „freigegeben und umgesetzt“.

### S1 · erledigt (2026-10-04), mit einer Ergänzung zum Plan
- **Muster:** Die Region steht dauerhaft im DOM, nur ihr Inhalt ist bedingt.
  - Leer belegt sie keinen Platz und zeichnet nichts (kein Rand, kein ⚠ aus `::before`). Sie bleibt aber im Barrierefreiheitsbaum.
  - Dafür gibt es das neue Partial `views/_live-region.scss`: `.live:empty` übernimmt `.sr` per `@extend`, ohne weitere Kopie der Technik.
  - `:empty` verlangt echte Leere. Der Inhalt steht deshalb in `{{ … }}` ohne Zwischenraum oder in einem `@if`-Block.
- **Sieben Stellen.** Das Audit nannte sechs, die siebte (4.) fiel beim Bau auf:
  1. `schema-form/json-value.component.ts`: „Kein gültiges JSON“.
  2. `schema-form/object-list.component.html`: Schlüssel-Fehler im Liste│Editor.
  3. `schema-form/schema-field.component.html`: Chip-Fehler.
  4. `schema-form/schema-field.component.html`: Schlüssel-Fehler einfacher Karten.
  5. `views/loadtest-run.component.html`: Fortschritt „Stufe n von m fertig“.
  6. `views/rag-ingest.component.html`: Ergebnis des Einlesens.
  7. `views/eval-generative-start.component.html`: Kostenbestätigung. Der Kasten steht ungeschärft und leer im DOM; seine Form trägt jetzt `.egs-confirm--armed`.
- **Tests:** je Stelle ein Spec. Die Region existiert vor der Meldung und ist ganz leer (`textContent === ''`; nur getrimmt reicht nicht, sonst griffe `:empty` nicht). Danach steht der Text in derselben Region.
  - Rot vor dem Umbau: 7 von 7, die Region fehlte.
  - Grün danach: 6 Dateien, 179 Tests.
  - Gegenprobe: Leerzeichen um `{{ error() }}` machen den Test rot (`'  '`).
- **Ergänzung:** `role="status"` ist ebenfalls eine Live-Region. Zehn solche Stellen entstehen samt Inhalt, sechs davon wechseln die Rolle zwischen `alert` und `status`. Das braucht einen eigenen Entwurf und steht deshalb als Folgebefund in der Befundliste §5.
- **NVDA-Prüfung:** macht der Nutzer (Befundliste §3).

### S2 · erledigt (2026-10-04)
- **Änderung:** `color-scheme: light dark` am `:root` in `theme/_studio-tokens.scss`, also dort, wo beide Schemata stehen. Die geteilten Token aus `@boerdi/ui` kippen per `prefers-color-scheme`, nicht per `light-dark()`; ihre Werte ändern sich also nicht.
- **Nebenwirkung:** Die Widget-Vorschau im Studio setzt kein `theme` (= `auto`). Sie erbt das Schema jetzt wie auf jeder Gastseite, die beide Schemata erklärt, und ist im Dunkelmodus dunkel.
- **Abnahme:**
  - `check:contrast` grün (Exit 0), ebenso `check:tokens`, `check:a11y` und `check:radii`.
  - Browser (Testcontainer, Dunkelmodus emuliert): Vor dem Neubau meldete `getComputedStyle(document.documentElement).colorScheme` den Wert `normal`, obwohl `prefers-color-scheme: dark` zutraf. Danach meldet es `light dark`, das Passwortfeld erbt es.
  - Bildschirmfoto der Anmeldeseite: dunkler Grund, dunkles Feld mit hellem Rand, Knopf und Sprachwahl lesbar.
- **Kein Unit-Test:** Eine einzelne Deklaration, und jsdom rechnet keine Kaskade. Der Nachweis ist der Messwert im echten Browser, vorher und nachher.

### Review mit frischem Blick (2026-10-04)

Drei Prüfer ohne Kontext haben den Diff gelesen, je einer für Backend Agent/LLM/RAG, Backend Konfiguration/Eval/CI und Studio. Sie fanden zwei Blocker, zwei mittlere und 18 kleine Befunde. Alle 22 sind am Code nachgeprüft; die Blocker zusätzlich mit einer Probe gegen die installierte Bibliothek. Behoben ist jeder mit einem zuvor roten Test, sofern nicht anders vermerkt.

**Blocker (A3, Ergebnis-Schema):**
- **R-1, SSRF:** `jsonschema` 4.26 holt ohne eigene Registry jede unbekannte Adresse per `urlopen`. Der Plan nahm das Gegenteil an („Vorgabe von `jsonschema` ohne Registry“).
  - Ein `$id` unterhalb der Wurzel mit eigenem `$schema` reichte, über einen anonymen Chat-Aufruf (Probe: `urlopen` auf `169.254.169.254`).
  - Jetzt: Prüfung mit leerer `referencing.Registry()`. Der Eingang weist `$id`/`$schema` unterhalb der Wurzel, Anker und dynamische Verweise ab. Jedes `$ref` muss als JSON-Pointer im Schema landen.
  - Der Test zählt die `urlopen`-Aufrufe mit. Ein werfender Stub hätte nichts bewiesen, weil `referencing` jede Ausnahme beim Nachladen in `Unresolvable` hüllt. Gegenprobe ohne leere Registry: rot.
- **R-2, ReDoS:** Ein `pattern` des Gastgebers lief gegen die Modell-Ausgabe (`^(a+)+$` gegen 40 × a plus `!`: Stunden).
  - Jetzt prüft der Server Muster nicht. Sie bleiben ein Hinweis an das Modell; P4-3 verlangt freie Gastgeber-Schemata, Abweisen schied deshalb aus.
  - Die Prüfkopie fällt nie strenger aus als das Original: Mit `patternProperties` fällt auch `additionalProperties` desselben Objekts, und `unevaluatedProperties` fällt überall.

**Mittel:**
- **R-3 (A3):** Lokale `$ref` zeigten auf die Werkzeug-Hülle; Pydantic-Schemata mit `$defs` ergaben `PointerToNowhere` und 500. Jetzt ist das Gastgeber-Schema seine eigene Wurzel, auch für rekursive `#`. Nicht Auflösbares wird zur Abweichung, nicht zur Ausnahme.
- **R-16 (D5, Studio):** Der Bereichs-Editor nahm für beide Reiter die Version des späteren Lesevorgangs. Speicherte jemand dazwischen, überschrieb das Formular die fremde Änderung ohne 409. Jetzt hat der Rohtext seine eigene Version (`rawVersion`).

**Klein:**
- **R-4 (B1):** Lief die Frist mitten in einer `wissen_suchen`-Abfrage ab, verwarf SQLAlchemy die Verbindung, und `persist` scheiterte. `CancelledError` rollt jetzt zurück und geht weiter.
- **R-5 (B1):** Ein abgebrochener Aufruf fehlte in `tools_called`/`outcomes`; jetzt steht er dort mit `timeout`. Ein bestätigter Schreibaufruf (`confirmToken`) läuft zu Ende, gedeckelt durch `MCP_CALL_TIMEOUT_S`. Abgeschnitten wüsste niemand, ob er schrieb.
- **R-6 (C4):** Beim lokalen Embedding-Backend stellte ein Import den Rerank-Pool voll; jetzt gilt dort der Ingest-Deckel (`llm.ingest_semaphore()`).
- **R-7 (C5):** Ein tröpfelnder Rumpf unterlief die Gesamtfrist, denn `iter_content` wartet auf volle 64 KB. Der alte Test lieferte Ein-Byte-Stücke, die `requests` nie liefert.
  - Jetzt schließt ein Wächter den Socket zur Frist (`HTTPResponse.shutdown()`).
  - Der neue Test läuft gegen einen echten lokalen Socket.
  - Restlücke: Tröpfelnde Kopfzeilen schneidet der Wächter nicht ab (Befundliste §5).
- **R-8 (C5):** Der URL-Import gab für PDF & Co. 400 mit der rohen markitdown-Meldung; jetzt 415 wie beim Datei-Upload.
- **R-9 (A3):** Draft-04/07-Schemata galten als kaputt (422); der Dialekt folgt jetzt `$schema`.
- **R-10 (C6):** Die alte Route `PUT /api/config/patterns` machte aus `rag_areas: []` „nicht gesetzt“; jetzt `list[str] | None`.
- **R-11 (D1/D5):** Eine neu angelegte Zeile begann wieder bei Version 1. Das ergab ABA beim Konfliktschutz, und ein Resync verwarf die neue Zeile. Neue Zeilen zählen jetzt ab dem Höchststand der Historie weiter (`FIRST_VERSION`), getestet an echtem Postgres.
- **R-12 (L3):** `latest` konnte auf einen älteren Commit zurückspringen, durch spätes oder wiederholtes `ci`. Jetzt wird `latest` nur für die aktuelle Spitze von main gesetzt. Läufe nach `ci` werden eingereiht statt abgebrochen.
- **R-13 (L3):** Der PR eines Forks von dessen `main` teilte die `concurrency`-Gruppe mit main; jetzt gehören Ereignis und Herkunfts-Repo dazu.
- **R-14 (L3):** Ein Branch, der wie ein Tag heißt, belegte die Tag-Marke neu. Jetzt gilt er nur als Tag, wenn der Tag (annotiert: aufgelöst) auf genau diesen Commit zeigt. Die im L3-Log vermerkte „bekannte Grenze“ ist damit behoben.
  - Kein Unit-Test: Der Skriptteil von `stand` lief lokal mit nachgebautem `gh` durch fünf Fälle (main, leichter Tag, annotierter Tag, Branch mit Tag-Namen, Feature), der Veröffentlichungsschritt mit nachgebautem `docker`/`gh` durch vier Fälle.
- **R-15 (D3):** Über den Formularweg kam `03-patterns/.` durch, das Wiederherstellen wies es ab; jetzt weist auch `_single_group_leaf` `.`/`..` ab.
- **R-17 (S1):** Eine leere Fehlerzeile trug ihr ⚠ aus `::before` weiter im Barrierefreiheitsbaum; jetzt `content: none` im Leerzustand. Kein Unit-Test, denn jsdom rechnet kein CSS; geprüft im gebauten CSS und in Chromium.
- **R-18 (S1):** `json-value` und `schema-field` vergaben beide `<feld>-err`; die JSON-Zeile heißt jetzt `<feld>-json-err`.
- **R-19 (D5):** „Verwerfen“ ließ den Konflikt-Hinweis stehen, und „Trotzdem speichern“ tat dann nichts; jetzt verschwindet er.
- **R-20 (C2):** Die Zahl der Abschnitte ohne Einbettung stand in einem Absatz, der mit dem Ergebnis entstand, und wurde nicht angesagt. Jetzt steht sie in der Ergebniszeile, der Live-Region.
- **R-21 (D5):** Die Kennung eines neuen Dokuments stand ungequotet im YAML. `2024` wurde zur Zahl, und das Anlegen scheiterte mit 422.
- **R-22 (L2):** Das Audit-Gate wertete unbekanntes JSON als „kein Fund“, und ein fehlschlagender Einstiegs-Wächter beendete es still mit 0. Jetzt gilt nur `auditReportVersion: 2`, die Bewertung liegt in `audit-bewertung.mjs`, und der Einstieg läuft immer.

**Bewusst nicht geändert:**
- Ein ungültiges Ergebnis-Schema bleibt auch im Muster-Modus ein 422. Die Eingangsprüfung ist für beide Modi dieselbe; der häufigste Fehlalarm (draft-07, R-9) ist behoben.
- Die neuen Antwortfelder (`version`, 409-Detail, `X-Config-Version`) stehen nicht im OpenAPI-Vertrag. Die Handler geben ungetypte Dicts zurück, wie zuvor; das ist undokumentiert, nicht widersprüchlich.

**Als Folgebefund aufgenommen (vor Paket 4, Befundliste §5):** ReDoS in Lotsen-Regeln, tröpfelnde Kopfzeilen beim URL-Import, Markdown-Bereich nach dem Speichern im Formular als YAML, Dokumente, die mit „Fehler“ beginnen.

**Prozess:** S2 stand noch nicht im Log; nachgetragen. Die Browser-Abnahmen von C2 und D5 folgen unten.

### Browser-Abnahmen (2026-10-04)
- **S2:** im Testcontainer geprüft, siehe S2.
- **S1, Mechanik in Chromium:**
  - Eine leere Region (Anker-Kommentar plus Textknoten der Länge 0) trifft `:empty`, liegt absolut und belegt 0 px Höhe.
  - Mit Text steht sie im Fluss. Ein einzelnes Leerzeichen bricht `:empty`; genau das prüfen die Specs mit `textContent === ''`.
  - Im gebauten Bundle stehen `.sr, .live:empty { … }` und `.live:empty::before/::after { content: none }`.
- **D5, Server live:** gegen den Testcontainer, ohne zu schreiben.
  - Eine veraltete Version und ein Anlegen auf eine vorhandene Kennung ergeben beide 409 mit Detail-Objekt (Meldung, Version, wer, wann).
  - Die Version blieb unverändert.
- **Offen, macht der Nutzer:** die Ansicht von C2 (auch per Tastatur) und D5 mit zwei Tabs im Studio des Testcontainers.
  - Beide brauchen eine Anmeldung im Studio.
  - Das Passwort an die Seite zu reichen, ohne es auszugeben, hat der Auto-Modus als Credential Materialization gesperrt. Die Sperre wurde nicht umgangen.
  - Die Schritte stehen in der Abschlussmeldung des Pakets.

### Abschluss (2026-10-04)
- **Endstand nach dem Review:**
  - Backend: 5168 passed, 4 skipped, 0 failed. `ruff` ist sauber, der OpenAPI-Vertrag unverändert (`export_openapi.py --check`).
  - Frontend:
    - lint und alle `check:*` grün;
    - Unit ui 867, widget 71, studio 1377, zweimal;
    - E2E 50, zweimal;
    - Studio-Build grün (Startpaket 1,08 MB);
    - Widget-Budget 554/600 kB, gzip 161/175 kB.
  - Testcontainer `edu-chatbot-sc:paket4-lokal`, die Datenbank per `alembic upgrade head` auf `0006`.
- **Upload:** Branch `paket-4-audit-extern` von main `e38006d`, fünf Commits nach Bereichen: Backend, Frontend-Werkzeuge, Studio, CI/Deploy, Doku.
  - **Abweichung vom Plan** („ein Commit je Aufgabe“): Mehrere Dateien tragen Änderungen aus mehreren Aufgaben, etwa `api/schemas.py` (A3, D5), `i18n/messages.py` (C5, D5, D6) und der OpenAPI-Vertrag. Der Staging-Baum ist kein Repo. Ein Schnitt je Aufgabe wäre Handarbeit an einzelnen Hunks ohne Gewinn; die Zuordnung je Aufgabe steht in diesem Log.
- **Nach dem Merge (Nutzer):**
  - L3 prüfen: `gh run list` zeigt `image` erst nach grünem `ci`.
  - Beim Deploy Migration `0006` und `BACKEND_REPLICAS=1`.
