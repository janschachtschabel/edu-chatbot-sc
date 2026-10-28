# Paket 18 — Externes Audit, Fehlerbehandlung und Datenschutz in Logs

Stand: Entwurf 2026-10-28. Grundlage: externes Audit (Störversuche und Code-Hinweise, ohne Datum), eine Diskussion dazu mit vier vorgeschlagenen Prüfaufträgen, und fünf eigene Prüfungen am Staging-Baum (nur lesend, 2026-10-28). Die Prüfungen deckten ab: mehrere Medientypen, Exceptions im ganzen Code, Inhalte in Logs und Fehlertexten, die vier Prüfaufträge sowie Retries und Readiness.

Pfade ohne Präfix beziehen sich auf `backend/src/boerdi/`.

## 1 Ziel

1. Was vom Audit im aktuellen Code noch gilt, wird behoben.
2. Fehler werden nicht mehr verschluckt, aber sie zeigen Nutzern auch keine Interna.
3. Logs enthalten keine Nutzer- oder Antworttexte mehr (DSGVO).
4. Ein Ausfall einer Sicherheitsstufe ist sichtbar und wird nicht als „geprüft“ verbucht.

## 2 Das Audit am aktuellen Stand

Das Audit beschreibt einen **älteren Stand** (vor Paket 3/4, etwa Ende September). Belege:

| Merkmal im Audit | Entfernt in |
|---|---|
| Meldung „Fehler bei der Verarbeitung: litellm…“ | Paket 3 (`11fd33e`) |
| `num_retries=2` in `services/llm.py` | Paket 4 (`445232d`) |
| `replicas: ${BACKEND_REPLICAS:-3}` | CI-Umbau (`f1e791c`) |
| Log „moderation failed“ | Pakete 6–12 (`824b2b5`) |

| Befund im Audit | Stand heute | Paket |
|---|---|---|
| Kein Readiness-Check | **erledigt**: `/ready` auf Port 8101 prüft Postgres, und der Container-Healthcheck nutzt ihn (Paket 17, `api/intern.py:93`, `Dockerfile:126`) | – |
| Retries auch bei 401 | **erledigt**: kein `num_retries` mehr; das SDK wiederholt 401 nicht (`services/llm.py:10-15`) | – |
| Moderation fällt still aus | **gilt teilweise**. Sie loggt jetzt („moderation skipped“, `services/safety/moderation.py:179`). Aber ohne Zugangsdaten bleibt sie stumm (`:153-155`), die Entscheidung verbucht die Stufe als gelaufen, und `_maybe_downgrade` stuft trotzdem herab („downgraded_by_llm_check“, `services/safety/service.py:174-186`). Kein Zähler, und das Aufwärmen meldet Erfolg. | A |
| Mehrere Medientypen | **gilt vollständig** (Prüfung 1): Liste → −32602; Retten nur durch den Modell-Retry; Type-Focus wählt `sorted(...)[0]` und **überschreibt die Antwort**; die Such-URL hat nur einen Typ; der Watchdog stürzt ab (`turn_links.py:443`) | B |
| `tool_args.py`: zweite Validierung verschluckt | **gilt**, aber geloggt; die rohen Argumente gehen weiter (fail-open, `tool_args.py:177-199`) | B |
| Nutzertexte in Logs | **gilt, größer als gemeldet**: etwa 55 Stellen in 22 Dateien auf INFO/WARNING, dazu die MCP-Argumente bis 500 Zeichen (`mcp/client.py:98,299`), das Access-Log mit IP und SQL-Parameter in Fehlern | C |
| Fehlerklasse in der Nutzerblase („gaierror“, „AuthenticationError“) | **gilt** (`api/chat.py:172`, `tool_loop.py:340`, `respond.py:480-484` hart kodiert deutsch, `canvas_fast_path.py:518`) | D |
| Log nennt bei 401 nicht den Schlüssel als Ursache | **gilt** (`respond.py:470` loggt nur `str(err)`) | F |
| Viele Aufrufe gegen einen toten Endpunkt (Circuit-Breaker) | gilt, nur Latenz im Fehlerfall | später |
| Liste der `except …: pass`-Stellen | **gilt fast vollständig** (Prüfung 2, §4); `chat.py` loggt inzwischen auf debug | E |
| „test message“ → `medientyp='quiz'` | **gilt**: Schlüsselwörter werden als Teilzeichenkette gesucht (`domain/content_types.py:37,104-118`), auch „Protest“ wird zu Quiz | B |

## 3 Neue Befunde aus den eigenen Prüfungen

**Auf der Nutzerseite sichtbar oder sicherheitsrelevant:**
- `services/canvas_service.py:334` schreibt den **rohen Ausnahmetext** des Anbieters in das Material, das die Person sieht.
- `ChatResponse.debug` geht **ungefiltert an jeden Client** und wird gespeichert. Er enthält `outcomes[].error = str(e)` (`outcome_service.py:73`), `validator error: {exc}` (`route.py:111`), Modell- und Werkzeugnamen. Das Audit 2026-09-29 führt das als offenen Kleinbefund.
- Moderation: Bei Last fällt sie still aus (4 Plätze, 8 s mit Wartezeit). Sie liest nur die ersten 4000 Zeichen, und die Nachricht hat keine Längengrenze. `host_instruction` wird nicht geprüft. In `crisis_blocked_tools` fehlt `search_wlo_all`.
- Die Prüfung `gather(..., return_exceptions=True)` testet nur auf `Exception`, sodass `CancelledError` als Daten weiterläuft (`safety/service.py:265`, `assess.py:150`).

**Exceptions** (Prüfung 2; 434 Handler, davon 124 ohne Log und ohne Weiterwurf):
- 87 sind in Ordnung so, 30 sollten loggen.
- 7 Stellen bergen 4 echte Risiken:
  - Ein ungültiger Wert schaltet das Rate-Limit still ab (`rate_limits.py:75`).
  - Eine Policy-Regel mit ungültigem Regex fällt still weg (`domain/policy.py:61`).
  - Kaputter Frontmatter wird auch beim Speichern im Studio still geschluckt (`seed_io.py:60`).
  - Nach `cancel()` + `await` wird die **eigene** Abbruch-Anforderung verschluckt, und es gibt kein Zeitlimit (`respond.py:179,263,280`, `obs/tasks.py:43`). Das Herunterfahren kann hängen.
- 13 Stellen loggen `logger.error` ohne Stacktrace, darunter der Schreibpfad `write_approval.py:275`.
- Ist die Datenschutz-Konfiguration nicht lesbar, werden Nachrichten trotzdem gespeichert, mit nur einem debug-Log (`db_sessions.py:120`).
- Im Frontend sollten 9 Stellen loggen, etwa das Laden der Widget-Konfiguration (`guide-boot.ts:109`) und der Verlauf (`chat-api.ts:456`).

**Betrieb und Last** (Prüfung 4):
- Das Warten auf einen LLM-Platz hat **kein Zeitlimit**, sodass ein hängender Anbieter eine Replika füllt.
- Musterzüge haben keine Gesamtfrist.
- Es gibt keinen Zähler für Warteschlange, DB-Pool oder Moderationsausfälle.
- Das äußere Limit beträgt **20/min je IP**. Hinter einem Schul-NAT ist das zu knapp, und das Studio beschreibt es als 1200/min.
- Ein 429 erscheint im Widget als generischer Fehler.
- Es gibt **keine Kostenbremse**: Anonyme Personen haben dieselben Agent-Deckel wie angemeldete (30 Runden, 900 s, 900k Token). Den Agent-Modus kann jeder Client per Kopfzeile wählen.

**Bekannt und bewusst angenommen** (nicht in diesem Paket): Die Sitzungskennung kommt vom Client. Wer sie kennt, kann den Verlauf lesen und weiterschreiben. Schreibfreigaben sind an die Person gebunden (`docs/entscheidungen-offen.md:17-20`).

## 4 Entscheide (Nutzer)

| # | Frage | Empfehlung |
|---|---|---|
| E1 | Verhalten bei einem Moderationsausfall | Schalter `MODERATION_BEI_AUSFALL` = `offen` \| `geschlossen`. Bei Vorgabe `offen` wird der Ausfall laut gemacht: Zähler, Kennzeichen in der Entscheidung, keine Herabstufung. Bei `geschlossen` bekommt die Person eine freundliche Absage, solange die Moderation fehlt. Für Schulbetrieb `geschlossen` erwägen. |
| E2 | Debug-Block in öffentlichen Antworten | Nur mit Studio-Anmeldung oder explizitem Debug-Schalter der Einbettung, der serverseitig freigeschaltet sein muss. Sonst entfernt. |
| E3 | Inhalte in Logs | Nie auf INFO oder höher. Auf DEBUG nur mit `LOG_CONTENT=true` (Vorgabe aus). |
| E4 | Äußeres Rate-Limit je IP | Vorgabe 120/min je IP. Die inneren Grenzen je Sitzung bleiben. 429 bekommt eine eigene Meldung im Widget. |
| E5 | Agent-Deckel für Anonyme | Eigene, kleinere Werte (Vorschlag: 8 Runden, 120 s, 150k Token), im Studio einstellbar. |

**Entschieden (Nutzer 2026-10-28):**
- E1: Schalter, Vorgabe `offen`.
- E2: Debug-Block nur mit Freigabe.
- E3: nach Empfehlung.
- E4: 120/min je IP.
- E5: bleibt wie bisher, für später notiert (Kosten eines anonymen Zugs erst messen).

## 5 Pakete

Für jedes Paket gilt:
- Schritt 0 ist `/better-coding-workflow`, bei UI zusätzlich `/better-coding-frontend`.
- Zuerst kommt ein Test, der den Fehler zeigt; danach die Behebung.
- Jedes Paket bekommt eine eigene Änderungsnotiz und thematische Commits.

### 18A Sicherheitsstufen ehrlich (Moderation)
- Die Entscheidung führt je Stufe ein Ergebnis: `ok`, `fehlgeschlagen` oder `keine_zugangsdaten`. Daraus ergeben sich `stages_failed[]` und der Grund `moderation_unavailable`.
- `moderate()` unterscheidet „sauber“ von „nicht geprüft“, etwa über ein Feld `geprueft: false` statt `{}`.
- `_maybe_downgrade` stuft nur herab, wenn die Moderation **erfolgreich** lief.
- Fehlen die Zugangsdaten, gibt es eine Warnung (einmal je Prozess).
- Neuer Zähler `boerdi_safety_stage_total{stage,outcome}`.
- Das Aufwärmen meldet einen Ausfall der Moderation ehrlich.
- `gather`-Auswertung auf `BaseException` (hier und in `assess.py`).
- E1: der Schalter mit freundlicher Absage, Text i18n.
- `search_wlo_all` kommt in `crisis_blocked_tools` (Seed).
- Lange Nachrichten: Anfang und Ende moderieren, je 4000 Zeichen.

### 18B Mehrere Medientypen
- **Entitäten normalisieren:** `domain/content_types.py` bekommt einen Helfer, den `merge.py` aufruft. Aus einer Liste für `medientyp` wird `medientypen`; `medientyp` behält den ersten Wert. Für `fach`, `stufe`, `thema` und `lizenz` wird aus einer Liste der erste Wert. Die Heuristik in `merge.py:180` setzt alle gewünschten Typen.
- **Schlüsselwörter nach Wortgrenzen** suchen statt als Teilzeichenkette („Protest“ ist kein Quiz).
- **Eine Engstelle in `mcp/client.py`:**
  - Eine Liste mit einem Element wird ausgepackt.
  - Längere Listen für die Suchwerkzeuge werden in einzelne Aufrufe aufgefächert (höchstens 3), die Ergebnisse zusammengeführt und nach nodeId entdoppelt.
  - Die Beschreibungen in `tool_defs.py` und Regel 8b werden angepasst.
- **`tool_args.py`:** Der zweite Validierungsfehler wird geloggt. Die rohen Argumente bleiben wie bisher (fail-open, dokumentiert).
- **`turn_links.py`:**
  - Das Label nennt alle Typen.
  - Die URL filtert alle LRT-URIs.
  - ~~Bei mehreren Typen wird die Antwort **nicht ersetzt**, der Suchhinweis wird angehängt.~~
    **Abweichung (Umsetzung, Bestätigung durch Nutzer offen):** Der Ersatz bleibt wie bei einem
    Typ. Er verhindert Sätze wie „Hier sind passende Videos …“, obwohl die Inhalte erst hinter
    dem Suchhinweis stehen; der Hinweis nennt jetzt alle Typen und die Suche filtert alle. Ohne
    Inhaltskarte (etwa bei ausgefallener Suche) bleibt die Antwort des Modells (seit 2026-10-17).
  - Watchdog und Rückfall-Meta nutzen den Str/Liste-Helfer.
- Ein Prefetch-Fehler wird als `error` verbucht, nicht als `empty`.

### 18C Logs ohne Inhalte
- **Helfer `obs/log_inhalt.py`:** `inhalt(text)` ergibt `‹N Zeichen, fp=xxxxxxxx›`. `_args_for_log` kürzt alle Zeichenketten auf ihre Länge.
- Etwa 55 Aufrufstellen umstellen (Liste in Prüfung 3, §5).
- Ein **Wächtertest** scannt per AST die Logger-Aufrufe auf verbotene Namen (`req.message`, `response_text`, `quick_replies` …).
- `hide_parameters=True` in `db/session.py`.
- Pydantic-Fehler: nur Anzahl und Stellen loggen.
- Access-Log des Hauptservers aus.
- `slowapi` und LiteLLM auf WARNING begrenzen, solange `LOG_CONTENT` aus ist.
- Deploy-Doku: Hinweis zum Traefik-Access-Log.

### 18D Fehlertexte für Nutzer
- Ein einheitlicher, übersetzter Text mit kurzer Fehlernummer (Trace-ID), nie Klasse oder Meldung. Betrifft `chat.py:172`, `tool_loop.py:340`, `respond.py:480` (über `bot_text`), `canvas_fast_path.py:518`, `canvas_service.py:334`.
- Debug-Block gemäß E2. `outcomes[].error` und `state_transition.reason` bekommen generische Codes, die Details stehen im Log.

### 18E Exceptions
- **Helfer `abbrechen_und_warten(task, frist)`:** Er gibt die eigene Abbruch-Anforderung weiter (`current_task().cancelling()`), loggt unerwartete Fehler auf debug und hat eine Frist. Er ersetzt die drei Kopien in `respond.py` und `cancel_and_drain`.
- Die (c)-Liste beheben:
  - `rate_limits._window`: Warnung.
  - `policy`: Warnung bei ungültigem Regex.
  - `seed_io`: strenger Modus für Studio-PUT und Wiederherstellen.
  - Datenschutz-Konfiguration: Warnung.
- TRY400: 13× `logger.exception`.
- Die 30 (b)-Stellen auf debug oder warning, den Fang dabei, wo sinnvoll, enger fassen.
- Im Studio-Pfad vor `HTTPException` loggen (`config.py:181`, `sessions.py:140`, `judge*.py`).
- Frontend: 9 Stellen mit `console.warn`/`debug`.
- Ruff-Regeln `S110` und `TRY400` in die Projekt-Konfiguration aufnehmen, damit nichts Neues dazukommt.

### 18F Betrieb und Last
- Bei 401 bzw. `AuthenticationError` eine klare Logzeile: „LLM-Anbieter lehnt den Schlüssel ab: Anbieter, Route“, gedrosselt.
- Frist beim Warten auf einen LLM-Platz (Vorschlag 30 s), danach eine freundliche „gerade ausgelastet“-Blase.
- E4 (Rate-Limit und 429-Meldung) und E5 (Agent-Deckel für Anonyme).
- **Später:** Circuit-Breaker, Zähler für Warteschlange und DB-Pool, Gesamtfrist für Musterzüge.

## 6 Abnahme

| Paket | Nachweis |
|---|---|
| A | Tests: Moderation wirft bzw. hat keine Zugangsdaten. Dann steht `moderation_unavailable` in der Entscheidung, es wird nicht herabgestuft, der Zähler steigt; bei `geschlossen` kommt die Absage. Volle Safety-Suite grün. |
| B | Tests: `medientyp` als Liste. Die Normalisierung greift, zwei Typen werden aufgefächert und zusammengeführt, Label und URL nennen beide (Antwort-Ersatz: siehe Abweichung in 18B), der Watchdog läuft mit Liste. „Protest“ ergibt kein Quiz. Kleiner Chat-Smoke mit „Arbeitsblatt oder interaktives Material“. |
| C | Wächtertest grün; caplog-Tests für die wichtigsten Pfade zeigen keinen Nachrichtentext; `LOG_CONTENT=true` zeigt ihn auf DEBUG. |
| D | Tests: Die Nutzerblase enthält weder Klasse noch Meldung, aber eine Fehlernummer. Der Debug-Block fehlt ohne Freigabe. Der Canvas-Fehler zeigt keinen Anbietertext. |
| E | Tests für den Abbruch-Helfer: Die eigene Abbruch-Anforderung kommt durch, die Frist greift, unerwartete Fehler werden geloggt. Ruff mit S110/TRY400 grün. |
| F | Test: 401 erzeugt die klare Logzeile; Frist beim Platz (mit Attrappe). |
| alle | volle Backend-Suite, Frontend-Tests, E2E, Lint |

## 7 Nur live prüfbar (für einen Prüfauftrag)

- Moderation tot, dann Testsätze aus `evals/moderation_messung.py`: Wie viel fängt der Regex allein?
- Eine Injection, versteckt im Volltext eines Materials oder im Seitentext.
- `get_url_text` auf eine interne Adresse; die Prüfung liegt beim MCP-Server.
- Langsame Dienste mit 10/30/60 s Verzögerung (toxiproxy).
- Mehr als 20 parallele Züge gegen einen hängenden Anbieter.
- Lasttest über HTTP/SSE durch Traefik.
- Kosten eines absichtlich teuren anonymen Agent-Auftrags.

## 8 Log

- 2026-10-28: Plan angelegt nach fünf Prüfungen. Das Audit bezieht sich auf einen älteren Stand; Readiness und Retries sind erledigt, der Rest gilt.
- 2026-10-28: **18A umgesetzt.**
  - **Entscheidung:** Neues Feld `SafetyDecision.stages_failed` mit dem Grund `moderation_unavailable`. Eine leere Moderation gilt als Ausfall, `gather` wird auf `BaseException` ausgewertet, und `_maybe_downgrade` stuft nur nach erfolgreicher Prüfung herab.
  - **Sichtbarkeit:** Zähler `boerdi_safety_stage_total{stage,outcome}`; eine Warnung je Prozess bei fehlendem Zugang; das Aufwärmen meldet einen Ausfall ehrlich.
  - **Lange Nachrichten:** Abschnitte zu je 4000 Zeichen, höchstens 8, in einem Aufruf.
  - **Schalter `MODERATION_BEI_AUSFALL`:** Neuer Graph-Knoten `pruefung_fehlt` nach `safety_log` beendet den Zug bei `geschlossen`; Direktaktionen im Preflight ebenso. Eingetragen in Deploy und Doku.
  - **Seed:** `crisis_blocked_tools` enthält jetzt `search_wlo_all`.
  - **Kleinigkeit:** `assess` wertet ebenfalls auf `BaseException` aus.
  - **Sicherheitsprotokoll:** Das Studio-Format bleibt bei den ALT-Schlüsseln; `stages_failed` steht nur in den Daten, der Grund in `reasons`.
  - **Tests:** 17 neu plus je 2 in Preflight und Graph; der OpenAPI-Vertrag ist neu erzeugt. Volle Suite: 6616 grün, die 3 Folgetests angepasst.
- 2026-10-28: **18B umgesetzt.**
  - **Stichwörter:** `test`, `tests`, `spiel`, `kurs`, `kurse` zählen nur als ganzes Wort.
  - **Entitäten:** `als_text`, `als_liste` und `normalisiere_entitaeten` (in `merge`); `medientypen` hält mehrere Typen, die Heuristik setzt alle.
  - **Suche:** Prefetch und Werkzeugschleife reichen die Liste weiter. Das neue Modul `services/mcp/listen_argumente.py` packt sie in `call_mcp_tool_status` aus oder fächert sie auf: höchstens 3 Werte, Ergebnisse zusammengeführt und nach `nodeId` entdoppelt.
  - **`tool_args`:** Der zweite Fehler wird geloggt, Fehler nur mit Ort und Art, ohne Eingabewerte.
  - **`turn_links`:**
    - Das Label nennt alle Typen („Arbeitsblätter oder interaktive Medien“), dazu neue Labels für interaktiv, Kurs, Spiel und Grafik.
    - Die Such-URL filtert alle LRT-URIs.
    - Wächter und Rückfall-Meta vertragen Listen.
    - Der Text-Ersatz bleibt nach Design: Die Antwort verweist auf die gefilterte Suche, die jetzt beide Typen zeigt.
  - **Werkzeugbeschreibungen und Regel 8b:** „ein Typ je Aufruf“.
  - **Tests:** 30 neu plus je 2 in Merge und Prefetch.
- 2026-10-28: **Review 18A/18B** (frischer Prüfer, 4 schwere, 9 kleinere, 5 Kleinstbefunde), behoben:
  - **Lange Nachrichten:** Abschnitte überlappen (200 Zeichen). Über 8 Abschnitten gehen die ersten und letzten 4 hinaus, die Prüfung gilt als teilweise (`moderation_partial`, Zähler `teilweise`), und der geschlossene Schalter greift. Eine unvollständige Antwort (weniger Ergebnisse als Abschnitte) gilt als Ausfall.
  - **Schalter überall:** `sperrt_ohne_moderation` liegt jetzt in `services/safety/service.py` und gilt auch für `/api/agent`. Scheitert `assess_safety` als Ganzes, trägt der Regex-Rückfall `moderation_unavailable` (`regex_rueckfall`, in assess, preflight und agent_gate). Abgewiesene Züge stehen in der Auswertung; der Preflight benennt sie als `SAFETY: moderation_unavailable`.
  - **Rechtsprüfung:** Ein Ausfall steht in `stages_failed` (`llm_legal`) und verhindert die Herabstufung. Zähler mit den Stufen-IDs `openai_moderation` und `llm_legal`.
  - **Startwarnungen:** ein unbekannter Schalterwert; `geschlossen` ohne Moderationszugang.
  - **Medientypen:** Klassifikatorwerte werden wieder als Teilzeichenkette abgebildet („Onlinekurs“ → kurs). In der Nachricht zählen `test`/`spiel`/`kurs` am Wortende, auch im Kompositum („Klassentest“), mit einer Liste von Ausnahmen („Protest“, „Beispiel“, „Exkurs“, „latest“). Ein englisches „test message“ bleibt ein Quiz: „Test“ ist auch das deutsche Wort dafür.
  - **Keine wachsende Typliste:** Nennt die Nachricht Typen, gelten nur sie; sonst bleiben die der Sitzung.
  - **Auffächern:** Der Begleittext des Servers bleibt erhalten, eine gescheiterte Teilsuche wird dem Modell genannt und geloggt (Anzahl), Ausnahmen lassen die übrigen Treffer zählen, `total` summiert nur die Inhaltssuche.
  - **Typ-Fokus:** höchstens so viele LRT-URIs, wie Typen gewünscht sind.
  - **Tests:** Verdrahtung Client → Auffächern, Weitergabe in der Werkzeugschleife, echte Vokabelschlüssel.
  - **Bleibt offen (vorbestehend):** Die Rechtsprüfung sieht nur `message[:2000]`. Sitzungen von vor 18B können noch Listen in Entitäten tragen (`canvas_fast_path` ruft `.strip()`). Logzeilen mit Antworttext gehören zu 18C.
