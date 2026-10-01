# Muster-Modus: zeitlich optimierte Kette

Stand: 2026-10-01, **umgesetzt** (Freigabe 2026-09-30: „umsetzen“). Phase 1–3 sind gebaut, dazu der Fast-Modus-Schalter und der Agent-Weg hinter einem Schalter. Abweichungen, Messungen und die offenen Schritte stehen unter „Umsetzung“ am Ende.

## Ziel

Eine einfache Antwort im Muster-Modus soll im Median unter 10 s ankommen statt in ~16 s. Die Schnellantworten sollen dabei zur Antwort passen.

## Auftrag

Der Nutzer schrieb:

> „15 Sekunden für eine einfache Antwort sind viel zu viel. […] die überlegung wäre ob es mit dem antwort-aufruf zu lösen ist — prüfe dies bitte. wenn das nicht geht dann die parallele version testen. sicherheitstest und klassifikation können wahrscheinlich auch parallel laufen. vielleicht auch rag? […]“

Dazu kam: „teste auch deine vorschläge unter anderem klassifikator ohne reasoning“.

## Die Kette heute

Die Kette ist linear (`graph/build.py:184-201`):

```
setup → tour → page_context_enrich → context_greeting → persist_user → preflight
→ assess (Sicherheit ∥ Klassifikation ∥ Erinnerung) → safety_log → merge → route
→ respond (RAG-Vorabruf → Antwort-Schleife) → assemble (Schnellantwort-Aufruf) → persist
```

Das Widget bekommt Antwort und Schnellantworten zusammen in einem einzigen `result`-Frame nach `persist`. Der Stream-Endpunkt baut den Graphen ohne `on_token` (`api/chat.py:169-174`), also gibt es kein Token-Streaming. Jede Sekunde der Kette ist Wartezeit.

## Messung

**Aufbau.** Ein Mess-Server aus dem Staging-Code (nur im Scratchpad) misst jeden Graph-Knoten, die Klassifikation, die Sicherheitsprüfung, RAG und jeden LLM-Aufruf je Phase.
- Fragen: vier Fragen mit dem Seitenkontext „Optik“, jede zweimal in neuer Sitzung, nach einem Aufwärmzug.
  - „Was ist WissenLebtOnline?“ (M15)
  - „Was ist Photosynthese?“ (M04)
  - eine Arbeitsblatt-Suche (M05)
  - „Ich suche Inhalte zu einem Thema.“ (M03)
- Modell und Daten: `gpt-6-luna` über die Responses-Brücke, lokale Datenbank.

| Variante | Median gesamt | Klassifikation | Antwort | Warten auf Schnellantworten |
|---|---|---|---|---|
| V0 · heute | **15,9 s** | 3,5 s | 6,9 s | 5,3 s (Aufruf 6,0 s) |
| V1 · Klassifikator `reasoning_effort=none` | 13,7 s | 3,3 s | 5,0 s | 3,7 s |
| V2 · Schnellantwort-Aufruf `none` | 14,7 s | 4,3 s | 4,8 s | 4,1 s (Aufruf 5,3 s) |
| **V3 · Schnellantworten im Antwort-Aufruf** | **9,3 s** | 5,0 s | 4,0 s | **0 s** |
| V5 · V3 + Klassifikator `none` | 11,7 s | 4,3 s | 5,1 s | 0 s |

Die Unterschiede zwischen V0, V1, V2 und V5 liegen in der Streuung, denn die Klassifikation schwankt zwischen 2,2 und 12,1 s. Robust ist nur V3: Der zweite Aufruf entfällt, das Warten auf Schnellantworten fällt auf 0.

### Klassifikator: Aufwand und Modell

Grundlage sind 26 Fragen: die 22 Einstiege der Golden-Suite und die 4 Testfragen. Klassifiziert wurde in der voll gestarteten App.

| Vergleich | Median-Zeit | Persona gleich | Intent gleich | Muster-Hinweis gleich |
|---|---|---|---|---|
| `low` gegen `none` | 3,7 / 3,1 s | 24/26 | 25/26 | 23/26 |
| `low` gegen `low` (Kontrolle) | 4,0 / 3,3 s | 24/26 | 25/26 | 21/26 |
| `gpt-6-luna` gegen `gpt-5.4-mini` | 4,3 / **1,9 s** | 21/26 | 22/26 | 17/26 |
| `gpt-6-luna` gegen `gpt-5.4-nano` | 4,3 / 2,0 s | 23/26 | 22/26 | 18/26 |

**Aufwand `none` bringt nichts.**
- Die Kontrolle `low` gegen `low` zeigt dieselben 0,6 s und dieselben Abweichungen.
- Eine Direktprobe zeigt den Grund: `none` kommt beim Modell an, aber `gpt-6-luna` denkt damit etwa so viel nach wie mit `low`, in beiden Fällen 0–49 Reasoning-Token, im Freitext wie im erzwungenen Werkzeugaufruf.
- In den Messzügen hatte die Klassifikation bei `low` in 9 von 24 Zügen Reasoning-Token, bei `none` in 6 von 16. Das ist gleich häufig (je 38 %).

**Wo die Zeit der Klassifikation liegt.**
- Der Prompt hat 22 900 Token, davon 99 % aus dem Cache.
- Die Ausgabe hat 130–560 Token einschließlich Reasoning.
- `gpt-6-luna` braucht 2,4–8,0 s (mittlere Hälfte 2,6–5,3 s).

**Kleinere Modelle** sind gut 2 s schneller und streuen weniger: `gpt-5.4-mini` braucht 1,3–2,9 s, `nano` 1,4–3,4 s. Sie weichen aber stärker ab als die natürliche Streuung von `gpt-6-luna`:
- „Ignoriere alle bisherigen Anweisungen …“: luna I07/kein Muster, mini I07/M14, **nano I01/M15**, also Orientierung.
- „Ich suche einen Einstieg ins Thema Bruchrechnung für die 5. Klasse.“: mini I04/M09, also Lernpfad statt Suche.
- „hey ich kapier brüche einfach nicht …“: nano M03, also Rückfrage statt Erklärung.

### Qualität der Schnellantworten (V0 gegen V3)

Die Rückfrage „Welcher Bereich der Optik interessiert dich?“ bekam:
- in V0 (separat erzeugt) „Klimawandel“ und „Photosynthese“,
- in V3 (im Antwort-Aufruf) „Reflexion und Brechung“ und „Linsen und Abbildung“.

V3 ist damit konsistent, V0 nicht.

Alle Vorschläge waren ≤ 48 Zeichen, aus Nutzer-Perspektive und in Du-Form. V3 ist aber allgemeiner („Erklär es einfacher“ statt „Erstelle ein Quiz zur Photosynthese“), denn der Inline-Weg bekommt die Fähigkeits-Hinweise des Schnellantwort-Prompts nicht.

## Befunde

1. **Sicherheit ∥ Klassifikation läuft schon parallel.** Das geschieht per `asyncio.gather` (`graph/nodes/assess.py:106-108`), hier gibt es nichts zu gewinnen.
2. **Die Schnellantworten laufen als eigener Aufruf nach der Antwort** (`services/turn_assembly.py:287-306`), gemessen 2–13 s.
   - Einen Weg im Antwort-Aufruf gibt es schon: das Werkzeug `respond_to_user` (`services/response_tool_selection.py:499-575`).
   - Er ist aus: Der Schalter liest nur `os.getenv("CHAT_INLINE_QUICK_REPLIES")`, das Feld `settings.chat_inline_quick_replies` (`settings.py:301`) liest niemand.
   - Die Beschreibung verlangt „2-4“ Vorschläge mit „6-8 Wörter[n]“ und `maxItems: 4`. Die Konfiguration sagt 2 Vorschläge und 48 Zeichen (`seeds/01-base/display-rules.yaml:44,49`).
   - Die Übernahme (`services/tool_loop.py:489-494`) kappt nur auf 4 und prüft keine Zeichengrenze.
3. **Der spekulative Parallel-Aufruf** (`graph/nodes/respond.py:354-401`) läuft bei aktivem Inline-Weg umsonst mit.
   - In V3 und V5 kamen die Schnellantworten in **16 von 16 Zügen** aus dem Antwort-Aufruf.
   - Alle 8 spekulativen Aufrufe (M03, M05) wurden gestartet und verworfen („speculative Task gecancelt — QRs kamen aus Inline-Antwort“).
4. **Die Rückfrage M03 brauchte in V0 zwei Modellrunden.** In Runde 1 wählte das Modell per `select_top_cards` die Sammlung aus dem Seitenkontext als Karte (~5 s ohne Nutzen). Mit Inline-Weg war es in 4 von 4 Zügen eine Runde.
5. **RAG** startet erst nach der Musterwahl (0,4–1,8 s).
6. **Der Seitenkontext** kostet nur bei kaltem Zwischenspeicher Zeit.
   - Im Aufwärmzug ~5 s (Metadaten ~2 s, Bestandszahlen ~3 s laut Protokoll), danach 1 ms, auch in neuen Sitzungen.
7. **Nach dem Umbau ist die Klassifikation der größte Block:** in V3 5,0 s Median gegen 4,0 s für die Antwort.
8. **Der Debug-Block zeigt keine Zeiten**, nur Token je Phase.

## Ansätze für die Schnellantworten

| Ansatz | Bewertung |
|---|---|
| **A1 · Inline über `respond_to_user` (Empfehlung)** | Vorhanden und gemessen (−6,6 s Median, konsistent, 16/16 Treffer). Arbeit: Schalter, Zahlen aus der Konfiguration, Filter. |
| A2 · Marker-Block im Antworttext | Nicht nötig, weil A1 dasselbe mit getestetem Code leistet |
| A3 · Parallel und spekulativ | Inkonsistent (siehe M03-Beleg). Die Prüfung verwirft Antworten, die mit „?“ enden, das trifft M15 immer. |
| A4 · Eigener Aufruf ohne Reasoning | Nur −0,7 s, bleibt nachgelagert |

**Rückfall:** Liefert das Modell keine Inline-Vorschläge, läuft der exakte Aufruf wie heute (`turn_assembly.py:287-306`). Es geht also keine Schnellantwort verloren, nur die Zeitersparnis dieses Zugs.

## Umfang

**Enthalten**
- (A) Schnellantworten im Antwort-Aufruf als Vorgabe, mit Zahlen aus der Konfiguration, Filter und ohne überflüssigen Parallel-Aufruf.
- (B) Keine Kartenauswahl im Rückfrage-Muster, als Absicherung.
- (C) Zeiten je Phase und je Schritt im Debug-Block und im Debug-Panel. Das ist der Wunsch des Nutzers, und der API-Vertrag bleibt gleich, weil `token_usage` ein freies Dict ist.

**Nicht enthalten**
- Token-Streaming zum Widget. Es ist der größte Hebel für die *gefühlte* Wartezeit und bekommt einen eigenen Plan.
- Die Fähigkeits-Hinweise im Inline-Weg.
  - Sie hängen an Persona, Arbeitsfläche und Thema, wechseln also je Zug.
  - Im Werkzeugblock würden sie den Cache-Präfix brechen, den der Plan `2026-09-29-responses-systemteil-und-cache.md` stabil halten will.
  - Folgepaket, falls die Vorschläge im Betrieb zu allgemein sind.
- Bestandszahlen parallel zur Klassifikation.
  - Hilft nur bei kaltem Zwischenspeicher (~3 s beim ersten Zug je Sammlung).
  - Braucht eine Aufgabe über drei Knoten hinweg: Begrüßung, `route`, Antwort-Prompt.
- RAG parallel: klein, 0,4–1,8 s.
- Klassifikator-Aufwand `none`: kein Effekt, siehe Direktprobe.
- Der Agent-Modus.

**Nach Entscheidung**
- (E) Das Klassifikator-Modell einstellbar machen. Die Vorgabe bleibt `gpt-6-luna`, ein Wechsel erst nach einem Golden-Lauf (Nutzer).

## Aufgaben

Je Phase ist Schritt 0 `/better-coding-workflow`, in Phase 3 zusätzlich `/better-coding-frontend`. Jede Aufgabe beginnt mit einem Test, der zuerst rot ist. Neue Bezeichner sind deutsch wie im umgebenden Code (`dokument_werkzeug`, `skill_bruecke`).

### Phase 1: Schnellantworten im Antwort-Aufruf

**T1 · Das Werkzeug in ein eigenes Modul, Zahlen aus der Konfiguration**
- Neu: `backend/src/boerdi/domain/antwort_werkzeug.py` mit `antwort_werkzeug(anzahl: int, max_zeichen: int) -> dict[str, Any]`. Vorbild ist `domain/inline_documents.dokument_werkzeug()`.
- Die Definition zieht aus `services/response_tool_selection.py:503-570`. Die Datei hat heute 576 Zeilen und schrumpft damit.
- Die Texte bleiben wörtlich. Nur „2-4 … (max 6-8 Wörter …)“ wird zu „{anzahl} … höchstens {max_zeichen} Zeichen“, und `maxItems` wird `anzahl`.
- Die Beschreibung hängt so nur an der Konfiguration, nicht am Zug. Das hält den Werkzeugblock cachebar.
- Tests in `tests/test_antwort_werkzeug.py`:
  - Mit Anzahl 2 und 48 Zeichen stehen beide Zahlen in der Beschreibung, und `maxItems` ist 2.
  - Die Du-Form-Regel und das `__guide__`-Format sind unverändert enthalten.

**T2 · Schalter aus den Einstellungen, Vorgabe an**
- In `services/response_tool_selection.py:499-502` wird statt `os.getenv` der Wert `get_settings().chat_inline_quick_replies` gelesen. Die Vorgabe in `settings.py:301-303` wird `True`.
- Die Anzahl ist dieselbe wie im exakten Aufruf: `domain/quick_reply_policy._qr_policy(pattern_id)[1]` (`quick_replies_max` des Musters), sonst `_qr_default_count()`. Die Zeichengrenze liefert `quick_replies_llm._max_chars()`.
- Tests in `tests/test_response_tool_selection.py`:
  - Ohne Umgebungsvariable steht `respond_to_user` im Angebot.
  - Mit `CHAT_INLINE_QUICK_REPLIES=0` fehlt es.
  - Hat das Muster `quick_replies_max: 3`, nennt die Beschreibung 3.

**T3 · Ein gemeinsamer Filter**
- Neu in `domain/quick_reply_policy.py`: `filtere_vorschlaege(vorschlaege: list[str], *, anzahl: int, max_zeichen: int) -> list[str]`.
  - Er entfernt Dubletten ohne Rücksicht auf Groß- und Kleinschreibung und verwirft Vorschläge über der Zeichengrenze, ohne sie zu kürzen.
  - Er kappt auf `anzahl`. Die Lotsen-Zeile kommt zusätzlich, wie heute in `quick_replies_llm.py:170-197`.
- `quick_replies_llm.generate_quick_replies` und die Übernahme in `tool_loop.py:489-494` nutzen ihn. Das ist dieselbe Regel an beiden Stellen, ohne Kopie.
- Tests in `tests/test_quick_reply_policy.py`:
  - Ein 49-Zeichen-Vorschlag fällt weg.
  - Zwei gleiche in anderer Schreibweise ergeben einen.
  - Aus drei wird bei `anzahl=2` zwei.
  - Die Lotsen-Zeile bleibt zusätzlich erhalten.
- Die bestehenden Tests von `test_quick_replies_llm.py` bleiben grün.

**T4 · Kein spekulativer Aufruf bei aktivem Inline-Weg**
- In `graph/nodes/respond.py:358` gilt zusätzlich `not get_settings().chat_inline_quick_replies`, dieselbe Einstellung wie in T2. Die Werkzeugwahl (`_select_active_tools`, `services/response_tool_selection.py:130`) läuft erst danach in `generate_response`, ihr Rückgabewert steht hier also noch nicht bereit.
- Test in `tests/test_respond_node.py`: Mit Inline-Weg und `quick_replies_mode: speculative` entsteht kein `qr_spec_task`.

**T5 · Nachweis Phase 1**
- Der Mess-Server wiederholt dieselben 4 Fragen × 2.
- Erwartet werden:
  - Median < 10 s,
  - kein `llm:quick_replies` bei Inline-Treffern,
  - alle Vorschläge ≤ 48 Zeichen,
  - zwei Vorschläge je Zug.

### Phase 2: Rückfrage absichern

**T6 · Keine Kartenauswahl im Rückfrage-Muster**
- In `services/response_tool_selection.py:454` wird `select_top_cards` bei `output_mode: clarify` nicht angeboten, analog zu `dokument_werkzeug` in Zeile 477-478.
- Test: `test_im_rueckfrage_muster_gibt_es_keine_kartenauswahl`, analog zu `test_im_rueckfrage_muster_gibt_es_nichts_zu_liefern`.

### Phase 3: Zeiten sichtbar

**T7 · Dauer je LLM-Phase**
- `obs/usage.add_usage(acc, usage, phase=None, ms: int | None = None)` zählt `per_phase[phase]["ms"]` hoch.
- `llm.chat_completion` (`services/llm.py:231-238`) misst die Wanduhr-Zeit einschließlich Warteschlange und gibt sie mit.
- Die Eval-Summen (`services/eval/metrics.py:96-128`) lesen Schlüssel einzeln aus und bleiben unberührt.
- Test in `tests/test_usage.py`: Zwei Aufrufe derselben Phase summieren `ms`.

**T8 · Dauer der Schritte**
- Neu: `backend/src/boerdi/obs/zeiten.py`.
  - `messe_knoten(name, action)` umhüllt einen Graph-Knoten und schreibt `ctx.usage["zeiten_ms"][name]`.
  - `schritt(acc, name)` ist ein Kontextmanager für Teilschritte.
- Einsatzorte:
  - `graph/build.py:166-181` umhüllt jeden Knoten.
  - `graph/nodes/assess.py:84-104` misst Sicherheit und Klassifikation getrennt.
  - Der RAG-Vorabruf in `services/tool_loop_messages.py:120-154` misst RAG.
- Weil `token_usage` der ganze Sammler ist (`services/turn_persist.py:222`), landen die Zeiten ohne weitere Änderung im Debug-Block.
- Test in `tests/test_zeiten.py`: Ein Graph mit zwei Test-Knoten füllt `zeiten_ms` mit beiden Namen, und eine Ausnahme im Knoten wird trotzdem gemessen und weitergereicht.

**T9 · Debug-Panel**
- Neu: `frontend/projects/ui/src/debug/debug-zeiten.component.ts`.
  - Sie zeigt die Knoten in Kettenreihenfolge mit Millisekunden sowie `ms` je LLM-Phase.
  - Die Summe der Knoten ist die Zugzeit ohne `persist`.
- `debug-panel.component.ts` hat 290 Zeilen und bindet die neue Komponente bei `:266-269` nur ein.
- Der Typ in `frontend/projects/ui/src/grouping/message-types.ts:158` bekommt `ms?: number` und `zeiten_ms?: Record<string, number>`.
- Das Debug-Panel ist eine Entwickler-Ansicht mit deutschen Festtexten wie heute, ohne i18n.
- Test in `debug-zeiten.component.spec.ts`:
  - Die Zeiten werden in Kettenreihenfolge gezeigt.
  - Ohne `zeiten_ms` rendert nichts.

### Phase 4: nach Entscheidung (E)

**T10 · Klassifikator-Modell einstellbar**
- Neue Einstellung `LLM_CLASSIFY_MODEL`, leer bedeutet das Chat-Modell. `services/classify.py:77` liest sie.
- Test: Die Klassifikation nutzt das eingestellte Modell.

## Nachweis und Erfolg

- **Tests:** Jede Aufgabe hat ihren Test, rot vor dem Fix und grün danach.
- **Volles Tor:** Backend, pg, Verträge unverändert, Ruff, UI/Widget/Studio, ESLint.
- **Mess-Server mit denselben 4 Fragen × 2:**
  - Median **< 10 s**,
  - Warten auf Schnellantworten 0 s,
  - Rückfrage mit einer Modellrunde.
- **Live im Testcontainer:** Das Debug-Panel zeigt die Zeiten. Das Widget-Bundle wird neu gebaut und geprüft.
- **Qualität:** Die Golden-Suite startet der Nutzer.
  - An `per_phase` ist je Zug ablesbar, ob Inline getroffen hat: Fehlt die Phase `quick_replies`, kamen die Vorschläge aus dem Antwort-Aufruf.

## Risiken

- **Das Modell ruft `respond_to_user` nicht auf.** Dann greift der exakte Aufruf wie heute, verloren geht nur Zeit. Gemessen wurden 16 von 16 Treffern, der Golden-Lauf zeigt die Quote über alle Muster.
- **Die Vorschläge werden allgemeiner als heute.** Das ist beobachtet in V3. Ist es im Betrieb zu viel, gibt es das Folgepaket „Fähigkeits-Hinweise“, cachegerecht im Zug-Teil des Prompts.
- **Die Knoten-Hülle verändert das Verhalten von LangGraph.** Der Mess-Server hat genau diese Hülle über alle Messzüge benutzt, ohne Abweichung. T8 testet zusätzlich, dass Ausnahmen durchgereicht werden.

## Entscheidungen des Nutzers

1. **Klassifikator-Modell (2026-10-01):** Es bleibt `gpt-6-luna`, T10 entfällt.
2. **Fast-Modus (2026-10-01):** prüfen. Siehe T11 unten.
3. **Ziel:** < 10 s Median, stillschweigend angenommen mit der Freigabe.

## Umsetzung (2026-10-01)

### Abweichungen vom Plan

- **T1 · Ersatzzeile.** Das Werkzeug fragt `anzahl + 1` Vorschläge an, gekappt wird im Filter. So hält es auch der exakte Aufruf (Paket A, Tor E-5): Zu lange Vorschläge werden verworfen, nicht gekürzt, und ohne Ersatz kostete jeder eine Pille. Die Einzahl-Sonderform entfällt, sie käme nie vor.
- **T2 · Krise und Bedrohung.** `inline_anzahl` gibt 0 zurück, wenn das Muster `quick_replies_mode: none` trägt (M01, M02). In der Zusammenstellung stehen Inline-Vorschläge *vor* `none`, ein Krisen-Zug hätte mit der neuen Vorgabe sonst Pillen bekommen. Dazu gibt es einen eigenen Test.
- **T3 · Ort des Filters.**
  - `filtere_vorschlaege` liegt in `services/quick_replies_llm.py`, neben `_display_length`. Die Plan-Fassung sah `domain/quick_reply_policy.py` vor.
  - Angewendet wird er in `turn_assembly` beim Übernehmen, denn dort ist die Anzahl des Musters bekannt.
  - Die feste Kappung `[:4]` in `tool_loop` ist weg.
  - Das Auslesen von Text und Vorschlägen teilen sich beide Schleifen: `domain/antwort_werkzeug.antwort_aus_argumenten`.
- **T7 · Phasen-Etikett.** Kommt die Antwort per `respond_to_user`, endet die Runde mit `finish_reason == "tool_calls"` und wurde als `tool_loop` gebucht. Im Golden-Bericht stünde sonst „response: 0 Aufrufe“. Eine Runde mit `respond_to_user` bucht jetzt als `response`.
- **T9 · keine neue Oberfläche.** Das Debug-Panel zeigt `debug.trace` schon als „· [step] label – N ms“. Das ist ein ALT-Port, bis hierher im Muster-Weg leer. `obs/zeiten.spur_zeilen` macht aus den Zeiten Trace-Zeilen:
  - zuerst `gesamt`,
  - dann je Knoten in der Reihenfolge der Kette, mit seinen Teilschritten darunter,
  - zuletzt je LLM-Phase mit Aufrufzahl.

  Kein Frontend-Code, kein Widget-Neubau. Alle Leser von `trace` filtern nach `step` (Golden-Lauf: `skill`, Studio: `agent_round`/`agent_stop`/`skill`), die neuen Zeilen (`zeit`, `llm`) stören sie nicht.
- **T10** entfällt (Entscheidung 1).

### T11 · Fast-Modus (`LLM_SERVICE_TIER`)

- **Leitfaden** (developers.openai.com, Fast mode, Stand 2026-10-01):
  - Der Parameter ist `service_tier: "fast"`, der ältere Name ist `priority`.
  - Er gilt für Responses und Chat Completions.
  - Laut OpenAI ist er bis zu 2,5-mal schneller.
  - Mit EU-Datenresidenz ist er für GPT-6 Luna nicht verfügbar.
- **Preis für `gpt-6-luna`** (OpenAI-Preisseite): Eingabe 0,40 $ statt 0,10 $, Ausgabe 2,40 $ statt 0,50 $ je 1 Mio. Token, rund das 4- bis 5-Fache.
- **Direktprobe bei OpenAI:** Die Antwort meldet `service_tier: "fast"`. Eine Antwort mit ~250 Token dauerte im Median 3,1 statt 4,3 s. LiteLLM reicht den Parameter auch über die Responses-Brücke durch, im Anfragekörper nachgesehen.
- **Umsetzung:**
  - Die Einstellung `LLM_SERVICE_TIER` ist leer = Standard. Unbekannte Werte fallen auf den Standard zurück, wie bei Verbosity und Reasoning.
  - `wire_transport` setzt `service_tier` nur bei `LLM_PROVIDER=openai`. Über die b-api ist der Modus ungemessen, und die b-api wird nicht getestet.
  - Der Schalter ist dokumentiert in `deploy/.env.example` und verdrahtet in `compose.prod.yml`.

### Messungen (Mess-Server, 4 Fragen × 2, Seitenkontext „Optik“)

| Variante | Median | Warten auf Schnellantworten | Bemerkung |
|---|---|---|---|
| V0 · Muster, vorher | 15,9 s | 5,3 s | |
| **V6 · Muster, neue Kette** | **9,1 s** | 0 s | 8/8 Vorschläge aus dem Antwort-Aufruf; Rückfrage 2× eine Runde |
| V7 · V6 + `fast` | 7,7 s | 0 s | Antwort-Aufruf 3,3 statt 4,5 s |
| A0 · Agent, heute | 12,2 s | 4,4 s (2,5–8,0) | eigener Aufruf nach jeder Antwort |
| **A1 · Agent + Inline-Schalter** | **6,8 s** | 0 s | 8/8 per `respond_to_user`; Antwortlängen wie A0 |

- **V6-Rückfrage:** „Licht und Reflexion“ / „Linsen und Abbildung“, passend zur Optik.
- **Einzelzeiten V6:**
  - Der Klassifikator braucht 3,4 s, er ist der größte Block vor der Antwort.
  - RAG im Orientierungs-Muster M15 braucht bis 2,0 s.
- **Nachweis T9:** Die Trace-Zeilen stehen in der echten `/api/chat`-Antwort, zum Beispiel `zeit · gesamt 8926`, `assess 3195`, `assess.safety 869`, `respond 5704`, `respond.rag 1992`, `llm · classify · 1× 3193`.
- **Antwortlängen A0 zu A1** (volle Antworten aus der DB): 533/465, 301/277, 365/430, 169/197, 540/547, 324/318, 325/449, 159/167. Die Antworten werden also nicht dünner als in Prosa. Das war der Befund aus J1 bei `submit_result`.

### Agent-Modus

- **Was ohne Zutun wirkt:**
  - die Zeiten im Debug-Block (derselbe Graph, derselbe Transport),
  - der Fast-Modus (Transport).
  - Die Agent-Runden trugen ihre Dauer schon vorher (AG-1).
- **Was nicht zutrifft:**
  - Klassifikator: Der Agent hat keinen.
  - Spekulativer Aufruf und Kartenauswahl bei Rückfragen gibt es nur im Muster-Weg.
- **Schnellantworten im Antwort-Aufruf — gebaut, Vorgabe AUS** (`AGENT_INLINE_QUICK_REPLIES`):
  - `respond_to_user` ist eine virtuelle Ziellinie der Agent-Schleife, wie `submit_result`.
  - Ausgewertet wird am Rundenende: Ein `zeige_dokument` oder `liefere_ergebnis` derselben Runde kommt noch an, echte Werkzeuge danach laufen nicht mehr und bekommen eine ehrliche Werkzeug-Nachricht.
  - Ohne Text endet der Lauf mit `empty`.
  - Die Vorschläge gehen über `_inline_quick_replies` in dieselbe Zusammenstellung und denselben Filter wie im Muster-Weg.
  - `CHAT_INLINE_QUICK_REPLIES=0` schaltet beide Modi ab.
- **Warum aus:** Der Live-Master-Skill beschreibt die alte Mechanik: „Die Pillen unter deiner Antwort schreibst du **nicht selbst**. Ein zweiter, eigener Modellaufruf liest … die ersten 500 Zeichen“. Die beschriebene Mechanik muss für den Agent-Zug stimmen (Plan Agent-Runde 2, Tabelle der Steuerflächen), und den Master-Skill ändert nur der Nutzer. A1 lief trotz des alten Textes 8/8 über das Werkzeug. Der Widerspruch bleibt trotzdem stehen, bis der Text angepasst ist.

**Zum Einschalten (Nutzer):**

1. Im Master-Skill (Knoten `535cabca…`) die beiden Stellen „Schnellantworten“ ersetzen, siehe unten. Danach dieselbe Änderung in die Vorlage `docs/skills/vorgehen.md` übernehmen.
2. `AGENT_INLINE_QUICK_REPLIES=1` setzen (Testcontainer: `deploy/.env.testcontainer`; Betrieb: `deploy/.env`).

**Vorschlag für den Master-Skill.** Der Kurzverweis unter den Chat-Flächen wird zu:

> ### Schnellantworten
>
> Siehe _Schnellantworten_. Der Kern in einem Satz: du lieferst die Pillen selbst — mit deiner Antwort in `respond_to_user`.

Der Hauptabschnitt „## Schnellantworten“ ersetzt den ersten Absatz und die Liste „Was das für deine Antwort bedeutet“. Die Tabelle „Was du je Lage anbietest“ bleibt unverändert.

> ## Schnellantworten
>
> Die Pillen unter deiner Antwort schreibst du **selbst**: Beende deinen Zug mit `respond_to_user` — die Antwort in `text`, die Vorschläge in `quick_replies`. Antwortest du stattdessen als reiner Text, schreibt sie ein zweiter Modellaufruf nach, der nur die ersten 500 Zeichen deiner Antwort sieht — das kostet die Person mehrere Sekunden und passt schlechter.
>
> ### Was für deine Vorschläge gilt
>
> -   **Anzahl und Zeichengrenze nennt das Werkzeug** (eingestellt im Studio unter Anzeige). Längeres wird verworfen, nicht gekürzt.
> -   **Der Pillentext IST die Nachricht**, die beim Klick gesendet wird. Er muss also als Anfrage funktionieren und das gemeinte Vorgehen auslösen: „Lücken in der Sammlung prüfen" — nicht „Lücken?".
> -   **Konkret statt generisch.** Kein „Mehr Infos", kein „Weiter", keine Platzhalter: setze Thema, Fach oder Stufe wörtlich ein.
> -   **Stellst du eine Rückfrage, sind die Vorschläge mögliche Antworten darauf** — nicht neue Fragen.

### Nachweis

| Prüfung | Ergebnis |
|---|---|
| Backend | 4618 bestanden, 229 abgewählt, 2 xfailed |
| pg | 28 bestanden |
| Verträge (OpenAPI, Bereichsschemata) | unverändert |
| Ruff | sauber |
| Frontend | ungeändert, deshalb kein Lauf |
| Testcontainer (Image `edu-chatbot-sc:kette-lokal`) | Das Debug-Panel zeigt die Trace-Zeilen. „Was ist WissenLebtOnline?“ im Muster-Modus: `gesamt 6757 ms`, davon `assess 2364`, `respond 4370` (`respond.rag 778`), `assemble 1`; zwei passende Schnellantworten |

**Neue Tests:**
- `test_antwort_werkzeug.py`, `test_zeiten.py`, `test_tool_loop_messages_rag.py`
- Ergänzungen in Werkzeugwahl, Pattern-Naht, Generator, Zusammenstellung, Werkzeugschleife, Antwort-Knoten, Assess, Graph, Persistenz, LLM, Settings, Agent-Schleife, Agent-Katalog und Agent-Antwort-Knoten.

### Offen

- **Agent-Schalter:** Einschalten nach der Master-Skill-Anpassung (Nutzer), danach Nachmessung und Golden-Lauf (Nutzer).
- **Fast-Modus:** Einsatz entscheiden (Kosten ×4–5, nicht mit EU-Datenresidenz, b-api ungemessen).
- **Token-Streaming zum Widget:** eigener Plan. Er ist der größte Hebel für die gefühlte Wartezeit.
- **RAG parallel zur Klassifikation:** in M15 bis 2,0 s, eigener kleiner Plan, falls gewünscht.
- **Klassifikation:** Sie ist jetzt der größte Block (3–4 s). Der Prompt hat 22 900 Token, die Ausgabe 130–560 Token.
