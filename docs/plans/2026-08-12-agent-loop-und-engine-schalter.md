# Agent-Schleife, Agent-Endpunkt und Engine-Umschalter

**Ziel.** Den Chatbot in fremden Kontexten nachnutzbar machen — Browser-Plugin,
edu-sharing-Einbettung — für Qualitätsprüfung und Kuratierung. Dazu ein
**Agent-Loop**, der alle MCP-Werkzeuge und die Sammlungs-Skills nutzt und bis zur
Fertigstellung oder einem sinnvollen Abbruchsignal läuft, ohne Begrüßung, ohne
Muster, ohne Klassifikator. Und derselbe Kern als **optionaler Umschalter** für
den Chatbot selbst, damit messbar wird, ob er schneller und besser ist.

**Randbedingung des Nutzers, die alles überlagert:** *„Der Chatbot soll
standardmäßig weiter laufen wie bisher. Ich will nichts der bisherigen
Pattern-Engine verlieren und diese auf Wunsch weiter nutzen können."* Der Bau ist
deshalb **rein additiv**: kein Bestandsmodul wird umgebaut, nur umgangen.

---

## 1. Was schon da ist (gemessen, nicht angenommen)

| Baustein | Stand |
|---|---|
| MCP-Werkzeuge | 40 im Katalog: 26 lesend (`tool_defs.py`) + 14 kuratierend (`tool_defs_curation.py`). Server hat 42 — die zwei Zusätzlichen sind `search`/`fetch`, die ChatGPT-Konvention, also Doubletten von `search_wlo_all`. Keine Lücke. |
| Anmeldung / Schreibrecht | **fertig.** `WLO-Access-Block` → `set_turn_auth_block` (ContextVar) → `Authorization: Bearer` am MCP. Schreiben ist am MCP frei, sobald `source: 'user'` gilt. |
| Skills je Sammlung | `get_skill_registry` / `search_skill` / `get_skill` im Katalog; der Katalog reist bei Sammlungs-Ergebnissen ohne Zusatzabruf mit. |
| Ereignisse | `TurnProgress` + SSE-Rahmen `connected/phase/result/error`. `phase.data` ist ein freies Dict. |
| Struktur-Ausgabe | Präzedenz `instructor.from_litellm` (`services/classify.py`). |
| Kosten | K1–K5: `usage_acc` + `record_turn_usage`, Preistafel `01-base/pricing`. |
| Schreib-Abnahme | E1-Wall (`domain/write_confirm.py`): Vorschau und Bestätigung in getrennten Zügen. |

**Nicht nachnutzbar:** `_run_tool_loop` (`services/tool_loop.py:472`) — 22
Parameter, `max_iterations = 5` fest, gebunden an `pattern_output`,
`classification`, Karten, RAG, Inline-Modus, und ALT-verbatim unter dem
Fidelity-Gate. Sie wird **nicht angefasst.** Der Agent bekommt eine eigene
Schleife über denselben Bausteinen darunter.

## 2. Entscheidungen (vom Nutzer, 2026-08-12)

1. **Schreiben ist erlaubt**, wenn eine echte Person dahintersteht — App mit
   WLO-Nutzersitzung, Browser-Plugin, oder angemeldeter Chat. Umgesetzt als
   `write_mode: propose | execute` je Anfrage, **Vorgabe `propose`**: nichts, was
   schreibt, darf standardmäßig schreiben.
2. **Sicherheits-Gate bleibt an.** Gemessen (`graph/nodes/assess.py:82-95`):
   `assess_safety` nimmt nur Nachricht + Signale, hängt also **nicht** am
   Klassifikator. Der Agent-Pfad behält `regex_gate` (synchron, gratis) und die
   Moderation; nur `classify_input` fällt weg.
3. **Der Chatbot bleibt Vorgabe.** Umschalter im Studio, Vorgabe `pattern`.

## 3. Architektur

```
services/agent_loop.py     ← der Kern. Kein Muster, kein Klassifikator.
services/agent_write.py    ← die E1-Wall, propose | execute
      ↑                  ↑
POST /api/agent        engine=agent im route-Zweig
(neu, Plugin/Repo)     auf dem bestehenden /api/chat
```

**`submit_result` ist Abbruchsignal UND Struktur-Ausgabe in einem.** Der Agent
ruft es, wenn er fertig ist. Gibt der Aufrufer ein `result_schema` mit, wird es zu
dessen `parameters` — dann erzwingt der Anbieter selbst die Form, und
„Sachrichtigkeit 0–5" ist ausdrückbar, ohne dass wir es kennen.

**Vier Abbruchgründe**, weil ein MCP-Aufruf gemessen bis 23 s steht:
`submit_result` (sauber) · Iterationsdeckel · Wanduhr-Frist · Token-Budget.
Dazu ein Stillstands-Erkenner (gleiches Werkzeug, gleiche Argumente zweimal
hintereinander).

**Der Umschalter liegt zweifach**, und das ist Absicht:
* **`01-base/engine.yaml`** (Studio, redaktionell pflegbar) = die Vorgabe.
* **Kopfzeile `X-Boerdi-Engine`** = Übersteuerung je Anfrage. Ohne sie ließe sich
  im Golden-Lauf nicht **eine** Suite gegen **beide** Maschinen fahren, und im
  Betrieb keine Stichprobe ziehen. Undeklariert aus `Request` gelesen, also
  **null Vertragsänderung** — Präzedenz `Accept-Language` (C1-e1) und
  `WLO-Access-Block` (C5-a).

Gleiche Schichtung wie `MCP_AUTH_TOKEN` (Anlage) ↔ `WLO-Access-Block` (Zug).

## 4. Warum ein eigener Endpunkt — und warum der Chatbot-Versuch keiner ist

`/api/agent` hat eine andere Zielgruppe (Maschine im Gastgeber statt Mensch im
Chat), andere Eingabe (Sammlungs-ID, nodeIds, `result_schema`), andere Ausgabe
(freies JSON), andere Anmeldung und ein anderes Limit. In `ChatRequest` gequetscht
wäre es dieselbe Unwahrheit wie damals `scope` bei `/api/quality/stats`.

Der Chatbot-Versuch dagegen **muss** auf `/api/chat` bleiben: der Sinn des A/B ist
*gleiche Eingabe, gleiche Ausgabe, anderer Mittelteil*. Zwei Routen zu vergleichen
hieße, den Unterschied mitzumessen, den man selbst gebaut hat.

## 5. Aufgaben

### A0 — Konfigurationsbereich `01-base/engine.yaml` ✅
- [x] `domain/config_models/engine.py`: `EngineArea` (`mode`, `agent.*`)
- [x] Registry + `NEUE_BEREICHE`-Eintrag mit Begründung
- [x] Seed `backend/seeds/01-base/engine.yaml`, Vorgabe `mode: pattern`
- [x] Loader `services/config_loader/engine.py` (`load_engine`)

### A1 — Werkzeugliste + `submit_result` ✅
- [x] `services/agent_tools.py`: Katalog (lesend + kuratierend, letztere nur mit
  Zugangsblock — dieselbe Regel wie `_nameable_tools`) + `submit_result`
- [x] `result_schema` des Aufrufers wird zu `parameters` von `submit_result`

### A2 — Die Schleife ✅ (2026-08-12)
- [x] `services/agent_loop.py` (239 Z.): Nachrichten → LLM mit Werkzeugen →
  Dispatch → wiederholen, `messages` an Ort und Stelle fortgeschrieben
- [x] `services/agent_write.py` (103 Z.): die E1-Wall in zwei Betriebsarten
- [x] Vertrauensgrenze: `frame_untrusted` hinter der Redaktion, vor der Kette
- [x] `TurnProgress`-Ereignisse je Iteration und je Werkzeug
- [x] `usage_acc` je Aufruf gebucht, Phase `agent`
- [x] 20 Tests (`tests/test_agent_loop.py`)

**Nachtrag zum Entwurf: es sind sieben Abbruchgründe, nicht vier.** Die vier
Deckel (`max_iterations`, `deadline`, `token_budget`, `no_progress`) stehen neben
zwei Ziellinien (`submit` und `text`) und dem Fehlerfall (`error`). `text` war im
Entwurf nicht vorgesehen und ist keine Kür: antwortet das Modell in Prosa ohne
Werkzeug, liefe die Schleife ohne diesen Zweig gegen dieselbe Nachrichtenkette
weiter, bis ein Deckel greift.

**Der Schlüssel zählt zur Identität eines Aufrufs.** `_call_key` nimmt die
Argumente **einschließlich** `confirmToken` — anders als
`write_confirm.change_fingerprint`, das ihn absichtlich streicht. Eine
Bestätigung wiederholt den Vorschau-Aufruf ja wortgleich bis auf den Schlüssel;
zählte er nicht mit, hielte die Stillstands-Erkennung genau die Einlösung für
Stillstand. Deshalb läuft die Wall **vor** der Schlüsselbildung.

**Zwei Funde beim Bauen:**

1. *Der Buchungs-Wächter hat mich korrigiert, und er hatte recht.* Ich hatte die
   Schleife selbst buchen lassen (`add_usage` hinter dem Aufruf) — aus dem
   falschen Grund: weil mein Test `llm.chat_completion` wegfälschte und die
   Buchung sonst nicht sah. Das ist die Produktion an die Attrappe angepasst.
   `tests/test_usage_coverage.py` schlug an; `_run_tool_loop` steht dort mit
   einem *echten* Grund (sein Phasen-Etikett folgt erst aus `finish_reason`),
   meiner ist im Voraus bekannt. Richtig ist Durchreichen — und die drei
   Buchungstests fälschen jetzt eine Ebene tiefer (`llm._acompletion`, Vorbild
   `tests/test_tool_loop.py::_run`).
2. *Das Token-Budget misst den eigenen Verbrauch, nicht den Zählerstand.* Im
   Chat-Modus (A4) trägt der Zug-Zähler schon Token aus Safety und Vorlauf; ohne
   den Nullpunkt beim Eintritt wäre das Budget der Schleife aufgebraucht, bevor
   sie den ersten Aufruf gemacht hat. Rot belegt.

**Gemessen, für A4 relevant:** die Schritt-Karte des Widgets
(`ui/stream/phase-label.ts`) ist eine **Erlaubnisliste** mit acht Einträgen; ein
unbekannter Schritt ergibt bewusst `null`. `agent_iteration`/`agent_tool`
erzeugen dort also **kein** Ladelabel — kein Schaden (der Spinner läuft weiter,
wie heute), aber der A/B im Chat sieht die Fortschritte erst, wenn die Karte
zwei Einträge bekommt. Für `/api/agent` (A3) ist das ohne Belang: dessen
Verbraucher liest `data.tool` bzw. `data.iteration`.

**Zwei Tests sind Gegenrichtungs-Wächter, kein Rot-Grün-Beleg** — sie waren mit
und ohne die Wall grün (`propose` setzt nie einen Schlüssel; `execute` setzt ihn
nicht für eine andere Änderung). Sie halten fest, dass das Gefährliche *nicht*
passiert; belegt wird die Wall von den drei anderen.

### A3 — Endpunkt `POST /api/agent` (+ `/stream`)

**Vor dem Bau geteilt.** A3 trägt Schemas, Systemprompt, Vorabauflösung,
Orchestrator, zwei HTTP-Routen, SSE und eine Vertragsänderung — das ist keine
Scheibe, das sind zwei. Der Schnitt liegt an der HTTP-Grenze, weil alles darunter
ohne Router prüfbar ist und die Vertragsänderung dann allein und sichtbar steht.

#### A3a — Der Lauf ohne HTTP ✅ (2026-08-12)
- [x] `api/schemas_agent.py` (64 Z.): `AgentRequest` / `AgentResponse`
- [x] `services/mcp/auth.py`: `has_personal_auth()` (additiv)
- [x] `services/agent_run.py` (151 Z.): Limits + Systemprompt + Vorabauflösung
- [x] Sammlungs-ID → `get_skill_registry`, nodeIds → `get_nodes_details`, beide
  als erledigte Werkzeugaufrufe injiziert; `get_skill_registry` gerahmt (H9)
- [x] 18 Tests (`tests/test_agent_run.py`)

**Der Fund dieser Scheibe: wo die Schreib-Prüfung sitzt.** Naheliegend wäre, nur
die Übersteuerung des Aufrufers zu prüfen (`if req.write_mode is None: return
vorgabe`). Das wäre ein Loch: ein in `01-base/engine` redaktionell gesetztes
`execute` käme ungeprüft durch, für **jeden** Aufrufer. Richtig ist die Prüfung
am *Ergebnis* — `execute` verlangt immer eine angemeldete Person, egal woher es
kommt. Rot belegt: mit der naiven Fassung fällt genau
`test_auch_die_konfigurierte_vorgabe_verlangt_eine_person`, die übrigen 17
bleiben grün.

**Dafür neu: `has_personal_auth()` neben `has_auth_token()`.** Der Unterschied
ist die Anlage: deren `MCP_AUTH_TOKEN` gehört einem Dienstkonto, nicht der Person
vor dem Bildschirm. Für Lesen egal (der MCP entscheidet selbst), für Schreiben
der ganze Unterschied — der Nutzer-Entscheid lautet „Rechte eines WLO-Users",
nicht „Rechte der Anlage".

**Vorab aufgelöst wird nur, was der Aufrufer mitgegeben hat.** Ein
fehlgeschlagener Abruf (gelöschter Knoten, wackliger MCP) wird zu einem Satz in
der Kette statt zu einem Fehler: der Agent arbeitet weiter und sagt selbst, was
ihm fehlt.

#### A3b — Die HTTP-Grenze ✅ (2026-08-12)

Zwei **verhaltenserhaltende Umzüge zuerst**, getrennt vom Feature — die
Duplikation entstand ja erst jetzt, und beide Stücke sind sicherheitsrelevant:

- [x] `api/sse.py` (129 Z.): der SSE-Rahmen aus `chat.py` herausgezogen; `chat.py`
  darauf umgestellt. Beleg sind die **18 Bestandstests** von `test_chat_stream.py`
  — angepasst wurde daran nur der *Ort* der zwei Konstanten
  (`chat._SSE_KEEPALIVE_SECONDS` → `sse.KEEPALIVE_SECONDS`), keine Zusicherung.
- [x] `api/turn_auth.py` (46 Z.): `adopt_turn_auth_block` + Kopfzeilen-Konstante.
  Dass es sie **nur einmal** gibt, ist kein Ordnungssinn: die Funktion *löscht*
  den ContextVar auch im Fall „keine Kopfzeile". Eine zweite Fassung, die das
  vergisst, ließe eine Anfrage an der Anmeldung der vorigen hängen.
- [x] `api/chat.py` von 319 auf 223 Zeilen — ohne Vertragswirkung (gemessen).

Dann das Feature:

- [x] `api/agent.py` (74 Z.): `POST /api/agent` + `/api/agent/stream`, hinter
  `require_studio_key`; Registrierung in `main.py`
- [x] Vertrag neu erzeugt + zwei Zeilen in `bewusste-vertragszusaetze.md`
- [x] **Beide** Vertragswächter gepflegt (siehe unten)
- [x] 8 Tests (`tests/test_agent_api.py`)

**Vor dem Neu-Erzeugen gemessen, nicht danach.** Die Drift war *genau* zwei neue
Pfade und zwei neue Schemas, **null** veränderte Bestandsoperationen — das ist
zugleich der Beleg, dass die zwei Umzüge oben vertragsneutral waren, obwohl sie
`chat.py` anfassten. 88 → 90 Pfade, 116 → 118 Operationen.

**Der zweite Wächter hat zugeschlagen, wie sein Docstring es ankündigt.**
`test_openapi_additions.py` war nach den Tabellenzeilen sofort grün (er zählt
gegen den abgelegten Vertrag), `test_openapi_contract.py` nicht — der vergleicht
das Routen-Inventar der *laufenden App* gegen eine Liste im Test. „Wer nur einen
von beiden pflegt, merkt es an dieser Stelle." Genau so eingetreten.

**Kein zusätzliches Rate-Limit, und das ist eine Entscheidung.** Den Kreis der
Aufrufer schnürt der Schlüssel zusammen; die Kosten eines *einzelnen* Laufs
decken die drei Deckel aus `01-base/engine`. Was fehlt, ist eine Grenze für die
**Zahl** der Läufe — die gehört an den Tag, an dem ein Gastgeber ohne
Studio-Schlüssel zugelassen wird (siehe offene Frage unten).

**Offene Frage für A3b, gehört dem Nutzer:** mit dem Studio-Schlüssel ist der
Endpunkt für ein **Browser-Plugin nicht bedienbar** — der Schlüssel ist der
Admin-Schlüssel und läge dann im Browser. Server-zu-Server (edu-sharing-Backend)
geht damit sofort. Das Plugin bräuchte eine eigene Anmeldung; der Plan setzt das
nicht voraus und verbaut es nicht.

### A4 — Engine-Umschalter im Chat-Zug

**Vor dem Bau geteilt** (gemessen: `respond` hat 471 Zeilen mit
`generate_response` mittendrin, `route` 297 mit Musterwahl, Karten-Fast-Paths
und RAG-Auflösung — das ist der Kernweg des Produkts und keine Scheibe):

#### A4a — Die Entscheidung ✅ (2026-08-12)
- [x] `services/engine_choice.py` (62 Z.): Kopfzeile > Studio-Vorgabe; unbekannte
  Werte fallen auf die Vorgabe, ein unlesbarer Bereich auf `pattern`
- [x] 8 Tests (`tests/test_engine_choice.py`), darunter der
  **Gegenrichtungs-Wächter**: mit dem ausgelieferten Bereich und ohne Kopfzeile
  kommt `pattern` heraus — die Zusage „läuft standardmäßig weiter wie bisher"
  steht damit in einem Test statt in einem Vorsatz.

**Rot belegt:** mit einer Übersteuerung, die nur *nach* `agent` schaltet, fällt
`test_die_kopfzeile_uebersteuert_auch_zurueck`. Ohne die Gegenrichtung ließe
sich eine auf `agent` gestellte Anlage nie stichprobenweise gegen den Bestand
messen — und genau dafür gibt es die Kopfzeile.

#### A4b — `assess` ohne Klassifikator ✅ (2026-08-12)
- [x] Im Agent-Modus entfällt `_classify()`, Safety und Memory bleiben
- [x] Ersatzform ist `_fallback_classification` — nichts Neues erfunden; damit
  laufen alle nachgelagerten Knoten unverändert
- [x] `engine` als DI-Naht durch `build_turn_graph` bis in `assess`
- [x] `X-Boerdi-Engine` an der HTTP-Grenze gelesen (beide Chat-Routen)
- [x] 6 Tests (`tests/test_assess_engine_mode.py`) + Nahtstellen-Wächter in
  `test_graph_build.py`

**Die Verzweigung sitzt IN der Coroutine, nicht am `gather`.** So bleibt der Weg
der Muster-Engine Zeile für Zeile derselbe; ein Umbau der Parallel-Gruppe hätte
den Bestandspfad angefasst, um einen Zweig danebenzusetzen.

**Rot belegt:** mit dem Parameter, aber ohne die Verzweigung fallen genau zwei
Zusicherungen (Klassifikator läuft noch, Ersatzform fehlt) — die vier übrigen
bleiben grün und belegen, dass Safety, Memory, Krisen-Kurzschluss und
Gegenrichtung unberührt sind.

**Der Fund dieser Scheibe ist ein Bug, den meine eigenen Attrappen zwei Scheiben
lang verdeckt haben.** `load_engine` ist **synchron**; ich hatte `await
load_engine()` geschrieben — in `agent_run.py` (A3a) **und** in
`engine_choice.py` (A4a). Beide Male war die Testattrappe `async` und damit nach
meiner Annahme gebaut statt nach der Wirklichkeit; grün war sie trotzdem. Der
Fehler flog erst auf, als der **echte Chat-Zug** die Funktion rief: 25 Tests auf
einen Schlag, `TypeError: object EngineArea can't be used in 'await' expression`.
In Produktion wäre das jeder Agent-Lauf gewesen.

Dieselbe Fehlerklasse wie der P11-Live-Fund (LiteLLM liefert dicts, die Attrappe
lieferte Objekte). **Regel, die daraus folgt: eine Attrappe wird nach der echten
Signatur gebaut, nicht nach dem eigenen Aufruf** — die korrigierten Attrappen
tragen den Grund jetzt als Kommentar. `choose_engine` ist dabei ganz synchron
geworden; async war nur die Folge des Fehlers.

**Zweiter Befund aus demselben Lauf:** die Kopfzeile wird an der HTTP-Grenze
gelesen und in `_stream_turn` **hineingereicht**, nicht darin aus `request`
geholt. Der Anlass war ein Testobjekt ohne `headers` — die richtige Antwort war
nicht, die Attrappe aufzublähen, sondern die Entscheidung dorthin zu setzen, wo
`adopt_turn_auth_block` schon steht.

**Zwischenzustand, bewusst:** mit `engine=agent` läuft der Zug jetzt ohne
Klassifikator, aber noch über die Musterwahl — die arbeitet dann auf der
Ersatz-Klassifikation, wie sie es bei einem Classify-Fehler auch tut. Degradiert,
nicht kaputt; A4c schließt das.

#### A4c — `route` + `respond`

**Vor dem Bau noch einmal geteilt** (gemessen, nicht geschätzt): der Agent-Zweig
hätte `route.py` von 297 auf ~313 Zeilen gebracht — über die 300er-Regel; und
`respond.py` steht bei 471 Zeilen mit `generate_response` mittendrin. Zwei
Knoten, zwei eigenständig prüfbare Zustände:

- **A4c-1** `route` ohne Musterwahl und ohne Schnellwege ✅
- **A4c-2** `respond` mit der Agent-Schleife statt `generate_response`, samt
  Karten aus `messages` ✅

Der dritte Punkt der alten Liste (`X-Boerdi-Engine` lesen und über
`build_turn_graph` einspeisen) war mit A4b bereits erledigt.

#### A4c-1 — `route` ohne Musterwahl ✅ (2026-08-12)
- [x] `domain/agent_pattern.py` (50 Z.): `agent_pattern()` liefert **dieselbe
  Rückgabeform wie `select_pattern`** — synthetisches `PatternDef(id="AGENT")`
  durch die **echte** `phase3_modulate`
- [x] `route`: Musterwahl verzweigt, beide Schnellwege (LP + Canvas) gesperrt
- [x] `engine` über `build_turn_graph` auch in `route` (Naht-Wächter erweitert)
- [x] 7 Tests `tests/test_route_engine_mode.py` + 6 Tests
  `tests/test_agent_pattern.py`

**Die Verschiebung, die den Zweig bezahlt hat:** die drei *reinen* Kopf-Helfer
(`_update_persona`, `_resolve_rag_areas`, `_render_memory_context`) saßen in
einem Graph-Knoten. Sie sind nach `domain/route_head.py` gewandert (Präzedenz:
`domain/route_tail.py`) und werden zurückimportiert, damit die Randkonvention
„Nachbarn sind AN DIESEM Modul patchbar" gilt — **null Teständerungen**, 62
Bestandstests vorher wie nachher grün. Danach passte der Agent-Zweig hinein und
`route.py` steht wieder bei 297 Zeilen.

**Warum `phase3_modulate` und kein handgeschriebenes Dict:** `turn_assembly`
liest `max_items`/`format_follow_up`, `turn_persist` schreibt
Ton/Länge/Detailgrad in die Qualitätslogs. Ein eigenes Dict hätte dieselben
Werte ein zweites Mal festgelegt und wäre beim nächsten Studio-Feld
auseinandergelaufen — der A/B-Vergleich hätte dann einen Unterschied gemessen,
den er selbst gebaut hat. Zwei Tests belegen, dass die echte Modulation läuft
(Geräte-Deckel 6/3, Persona-Ton).

**Der Befund dieser Scheibe: eine der beiden Sperren wäre „geliehen" gewesen.**
Der Canvas-Schnellweg hängt an Intent `I05`, und der Agent-Modus klassifiziert
seit A4b gar nicht — er käme also *zufällig* schon nicht dran, ganz ohne Sperre.
Der Lernpfad-Schnellweg dagegen feuert **an der Nachricht**: ein „Lernpfad"
irgendwo im Satz genügt, der Ersatz-Intent `I01` blockiert ihn nicht. Beide
hängen jetzt am selben Schalter (`fast_paths_on`), und der Canvas-Wächter prüft
ausdrücklich mit einer I05-Klassifikation. **Regel: ein Verhalten, das nur aus
einer Eigenschaft eines ANDEREN Knotens folgt, ist nicht zugesichert, sondern
geliehen** — und fällt aus, sobald dort jemand etwas ändert.

**Rot belegt, in zwei Stufen.** Der erste Lauf war ein `AttributeError` in der
Testvorrichtung — der schwache Rote, der nichts beweist (dieselbe Klasse wie der
`ImportError` in A2, der `TypeError` in A4b). Erst mit dem Baustein und dem
Parameter auf **Status-quo-Verhalten** fielen 6 von 7 Zusicherungen aus dem
richtigen Grund. Der siebte war schon grün: „Policy und Werkzeug-Sperren gelten
auch im Agent-Modus" ist ein **Wächter, kein Beweis** — er hält fest, was NICHT
ausfallen darf. Der Naht-Wächter im Graphen fiel danach genau in der Ausprägung
`[route]`, während `[assess]` grün blieb.

**Eigene Fehlannahme, per Roter korrigiert:** meine Gegenrichtungs-Zusicherung
pinnte den Vorgabewert `intent_id == "I01"` — der Default ist `I03`. Die
Zusicherung prüft jetzt die *Verdrahtung* (der Intent kommt bei `select_pattern`
an) statt einen Vorgabewert, den sie gar nicht meinte.

**Verifikation:** `pytest -q` → 3116 passed, 4 skipped (3102 vorher, +14) ·
`ruff check .` → All checks passed · `export_openapi.py --check` → unchanged.

**Zwischenzustand, bewusst:** mit `engine=agent` läuft der Zug jetzt ohne
Klassifikator, ohne Musterwahl und ohne Schnellwege — die Antwort erzeugt aber
noch `generate_response` auf dem synthetischen `pattern_output`. A4c-2 schließt
das.

#### A4c-2 — `respond` mit der Agent-Schleife

**Wieder vor dem Bau geteilt.** Die Karten-Ernte ist kein Nebensatz: die Logik
dafür lag als 68-Zeilen-Block mitten im Tool-Loop. Erst das Werkzeug, dann der
Umbau:

- **A4c-2a** Karten-Ernte teilbar machen + Naht in der Agent-Schleife ✅
- **A4c-2b** `respond_agent` + Verdrahtung ✅

#### A4c-2a — die Ernte-Naht ✅ (2026-08-12)
- [x] `services/card_collect.py` (135 Z.): `collect_cards()` +
  `CARD_YIELDING_TOOLS`, verhaltensgleich aus `tool_loop._run_tool_loop` gezogen
- [x] `run_agent_loop(on_tool_result=…)`: sieht jedes echte Werkzeug-Ergebnis
- [x] 5 Tests in `tests/test_agent_loop.py`

**Warum überhaupt eine Naht — und nicht einfach `messages` auslesen.** Der
naheliegende Weg wäre, nach dem Lauf die `role=tool`-Nachrichten zu parsen. Das
**funktioniert heute** — ich habe nachgesehen: `frame_untrusted` rahmt nur
`FREE_TEXT_TOOLS` und `WEB_TEXT_TOOLS`, und beide Mengen sind von
`CARD_YIELDING_TOOLS` **disjunkt**. Aber genau das ist die Sorte Verhalten, die
A4c-1 als **geliehen** benannt hat: es hängt an einer Eigenschaft eines anderen
Moduls. Sobald jemand `get_collection_contents` zu den Prosa-Werkzeugen nimmt —
plausibel, seine Nutzlast ist redaktioneller Text —, fänden die Karten still
niemanden mehr. Die Naht macht daraus eine Zusage.

**Wo genau sie sitzt, ist die eigentliche Entscheidung:** *nach* der Redaktion,
*vor* dem Rahmen. Der Bestätigungs-Schlüssel ist ein Geheimnis und darf diese
Naht nicht passieren; der Fremdtext-Rahmen dagegen ist eine Anweisung ans Modell
und für einen Parser nur Störung. Beide Richtungen stehen als Test.

**Was die Verschiebung wert war:** wer die Karten „mal eben selbst" parst,
verliert vier Dinge still — die Parser-Auswahl je Werkzeug (`search_wlo_all`
antwortet in drei Töpfen; der Standardparser gab darauf **null** Karten, live
gemessen 13 verlorene Treffer, W9b), die Sammlungs-Markierung, die
Themenseiten-Mischung und die Entdopplung. Der Block gehört genau deshalb an
eine Stelle und nicht an zwei.

**Der Fund beim Verschieben:** sie war **nicht testtransparent**. Zwei Tests
fielen, und der Log zeigte warum — sie patchen `tool_loop.parse_wlo_cards`, und
die Aufrufstelle war umgezogen. Belegt, dass nur der **Ort** anders ist (die
Zusicherungen prüfen Markierung/Entdopplung, nicht den Parser), dann umgehängt:
`_run_loop` zeigt jetzt auf `card_collect`, `_run_assemble` bleibt bei
`tool_loop` — dort sind die Prefetch-Karten geblieben. Und der historische
W9b-Kommentar ist **mit** seiner Menge umgezogen; am alten Ort hätte er etwas
beschrieben, das dort nicht mehr steht.

**Rot, wieder zweistufig:** erst `TypeError` (schwach), dann mit angenommenem
aber ungenutztem Parameter 3 echte Fehlschläge — und 2 der neuen Tests schon
grün: „`submit_result` geht nicht durch die Naht" und „ohne Naht läuft die
Schleife unverändert" sind **Wächter**, keine Beweise.

**Verifikation:** `pytest -q` → 3121 passed, 4 skipped (3116 vorher, +5) ·
`ruff check .` → All checks passed.

#### A4c-2b — `respond_agent` + Verdrahtung ✅ (2026-08-12)
- [x] `domain/answer_notes.py` (70 Z.): Policy-Disclaimer + Medium-Risk-Notiz
  verhaltensgleich aus `respond` gezogen (471 → 447 Zeilen)
- [x] `graph/nodes/respond_agent.py` (159 Z.): Kette, Schleife, Karten-Ernte,
  die vier geerbten Zusagen, Ersatzsatz bei textlosem Ende
- [x] `respond(engine=…)` reicht früh weiter; sein Rumpf bleibt unangetastet
- [x] `build_agent_tools(blocked_tools=…, include_submit=…)`
- [x] `agent_write.enforce_write_mode(…)` — die Schreib-Regel aus `agent_run._limits`
- [x] `obs/tasks.cancel_and_drain(…)` + Verwurf des Vorabrufs
- [x] `i18n/bot_text`: `agent.incomplete` / `agent.failed`
- [x] `engine` über `build_turn_graph` in `respond`; Naht-Wächter auf drei Knoten
- [x] 18 Tests `tests/test_respond_agent.py` + 4 in `tests/test_agent_tools.py`

**Der Gegenstand der Scheibe war nicht die Schleife, sondern was der Agent-Modus
ERBT.** Vier Zusagen des Chat-Zuges hätten den Wechsel sonst *still* nicht
überlebt — jede davon gemessen, nicht vermutet:

1. **Die Werkzeug-Sperre.** `route` streicht `safety.blocked_tools` aus
   `pattern_output['tools']`. Gemessen: `agent_pattern` liefert `tools: []` —
   die Sperre hätte im Agent-Modus **keinen Empfänger** mehr, und der Agent
   bekäme den vollen Katalog samt gesperrtem Werkzeug. Sie greift jetzt VOR
   `submit_result`: das Abschluss-Werkzeug ist virtuell und darf nicht sperrbar
   sein, sonst nähme eine Sperre dem Lauf seine Ziellinie.
2. **Die Schreib-Regel.** `execute` verlangt eine angemeldete Person — die
   Prüfung saß allein in `agent_run`. Ein im Studio auf `execute` gestelltes
   `01-base/engine` hätte im Chat ohne Person geschrieben. Die Regel ist nach
   `agent_write` gewandert, weil jetzt ein zweiter Aufrufer da ist; eine
   Sicherheitsregel in zwei Fassungen ist eine Fassung zu viel.
3. **Die Hinweise an der Antwort.** `assess_policy` und das Sicherheits-Gate
   laufen im Agent-Modus unverändert — ihre Ergebnisse wären an keiner Antwort
   mehr angekommen. Daher die Verschiebung nach `domain/answer_notes` **vor**
   dem Zweig: sie hängen an `policy`/`safety`, nicht daran, wer den Text machte.
4. **Der spekulative Vorabruf.** Wird hier nie verbraucht → abgebrochen. Nicht
   eingespeist, und das ist die ehrlichere Messung: ein vorgefüllter Treffer
   stammte aus der Muster-Engine und verfälschte den A/B-Vergleich.

**Der Fund beim Selbst-Review — ein Loch, das kein Test der Scheibe suchte.**
`AgentRun.text` ist nur bei `text` und `submit` gefüllt; bei **Frist,
Token-Budget, Iterationsdeckel, Stillstand und LLM-Fehler** bleibt er leer. Mit
`deadline_s: 90` und zwölf Iterationen ist das kein Sonderfall — der Nutzer hätte
eine **leere Blase** bekommen, während der Bestandsweg an derselben Stelle
freundlich degradiert. Zwei Katalog-Sätze schließen das. Geprüft wird der TEXT
und nicht der Grund: auch `stop_reason='text'` kann leer sein.

**Zwei bewusste Abweichungen vom Endpunkt-Lauf.** *Kein* `submit_result`: im
Chat liest niemand das strukturierte `result`, und seine Beschreibung verlangt
einen zusätzlichen Modellzug (2–9 s gemessen), um zu sagen, was die Prosa schon
sagt. Deshalb schweigt der Systemprompt auch dazu — zwei einander
widersprechende Anweisungen wären schlechter als keine (Lehre aus C1-f1). Und
*kein Streaming*: `run_agent_loop` kennt keinen `on_token`-Haken; der A/B misst
Inhalt und Dauer, nicht die Tropfgeschwindigkeit.

**Rot, wieder zweistufig — und die erste Stufe war diesmal ein Fehler im
Testgerüst, kein Befund.** Der erste Lauf war `ImportError`. Der zweite ließ
*alle elf* Tests fallen, weil mein gemeinsames `_patch` jeden von ihnen an das
noch nicht gebaute `enforce_write_mode` koppelte — ein Aufbau-Grund, kein
Sach-Grund. Erst nach dem Bau der Regel war der Rote ehrlich: **7 Fehlschläge,
jeder aus eigenem Grund**, 22 grün. `test_execute_mit_angemeldeter_person…` war
schon vorher grün und ist damit ein **Wächter**, kein Beweis.

**Zwei Bestandstests umgehängt, beide vorher angesagt:** `test_agent_run`
patchte `agent_run.has_personal_auth` — nur der ORT ist gewandert. Und meine
eigene Zusicherung `assert "submit_result" in namen` stammte aus einer früheren
Fassung des Entwurfs; sie steht jetzt als **eigener** Test der Gegenrichtung da,
nicht als stille Streichung.

**Gemessen und für gut befunden (kein Loch):** `_qr_policy("AGENT")` gibt
`("exact", None)` — nicht `speculative`; `turn_assembly` prüft `qr_spec_task is
not None` an jeder Stelle. Der Agent-Modus verliert also keine Quick-Replies,
obwohl `respond_agent` keinen Spekulativ-Task startet.

**Verifikation:** `pytest -q` → 3144 passed, 4 skipped (3121 vorher, +23) ·
`ruff check .` → All checks passed · `export_openapi.py --check` → unchanged.

**Nebenbefund, nicht angefasst (gehört dem Nutzer):** `AgentLimits.safety`
(`01-base/engine`) hat **null Konsumenten** — 9. Fall „dokumentiert ohne
Konsumenten". Das Feld liest sich als Schalter, schaltet aber nichts: im Studio
auf `false` gestellt bliebe das Sicherheits-Gate an. Der IST-Zustand ist der
sichere, deshalb ist „echt machen" hier keine Verbesserung, sondern das Einbauen
eines Aus-Schalters für die Sicherheit. Entweder das Feld entfernen (Seed +
Bereichsmodell) oder es bewusst als Zusage stehen lassen — eine
Produktentscheidung, keine Aufräumarbeit.

**Damit ist A4c zu.** Mit `engine=agent` läuft der Zug jetzt ohne Klassifikator,
ohne Musterwahl, ohne Schnellwege und ohne `generate_response` — und mit allen
Zusagen des Chat-Zuges. Was fehlt, ist die Messbarkeit: A5.

### A5 — Messbarkeit ✅ (2026-08-12)
- [x] `run_golden.py`: `chat_headers()` + `EVAL_CHAT_HEADERS` an jeden Zug
- [x] `run_golden.py`: `latency_ms` je Zug + `latency_summary()` (p50/p95/max) in
  Scorecard und Konsole
- [x] `compare_golden.py`: `--ignore-classification`
- [x] 18 Tests (`tests/test_golden_ab.py` 13, `tests/test_golden_compare.py` +5)
- [x] `evals/README.md`: der A/B-Ablauf als Kopiervorlage

**Der wichtigste Test dieser Scheibe prüft ein Scheitern.** Unlesbares
`EVAL_CHAT_HEADERS` bricht ab (Exit 2), statt ohne Kopfzeilen weiterzulaufen.
Ein stiller Rückfall wäre der teuerste Ausfall der ganzen Reihe: die Suite liefe
gegen die Muster-Engine, der Report hieße „agent", und der A/B-Vergleich verglich
einen Lauf mit sich selbst — **ohne dass irgendwo etwas rot wird**.

**Der Report nennt die Kopfzeilen-NAMEN, nie die Werte.** Er soll sagen, womit
gemessen wurde; aber eine Kopfzeile kann ein Geheimnis tragen
(`WLO-Access-Block` führt die Zugangs-Kennung). Steht als Test.

**Latenz als Verteilung, nicht als Mittelwert.** Gemessen schwankt die
MCP-Suche im selben Lauf zwischen 1,2 und 23,3 s (C9-Messung) — ein Durchschnitt
verwischt genau den Unterschied, den der A/B sehen soll. Auch der **Fehl-Zug**
trägt seine Zeit: eine Zeitüberschreitung ist der teuerste Zug des Laufs,
ausgerechnet den nicht zu messen wäre die falsche Auslassung.

**Warum `--ignore-classification` nicht einfach „weniger vergleichen" ist.** Der
Agent klassifiziert nicht (A4b) und wählt kein Muster (A4c-1) — Persona, Intent
und Muster weichen an fast jedem Zug ab, von Bauart wegen. Ungefiltert stünden
dort zwei harte Regressionen JE ZUG, `is_blocking` wäre immer wahr, und die eine
echte Abweichung ginge unter. Ausgeblendet werden deshalb genau die beiden
Check-Kategorien aus dem Klassifikator; Register, Struktur, Quick-Replies und
Host beschreiben die ANTWORT und bleiben — ein Test hält fest, dass eine echte
Struktur-Regression auch mit der Flagge blockiert.

**Zwei Bestandstests umgehängt, vorher angesagt:** die `post_chat`-Attrappen in
`test_golden_runner.py` hatten drei Positionen. Die A4b-Regel gilt — eine
Attrappe wird nach der ECHTEN Signatur gebaut; der Fehlerfall zeigte es sofort,
weil das `except Exception` die falsche Signatur als „Chat-Fehler" verbuchte.

**Eigene Fehlannahme, per Rotem korrigiert:** meine Zusicherung „3
Klassifikations-Wechsel" ging nicht auf — die Testvorlage trug bereits
`intent: "I03"`, also genau den Wert der Ersatz-Klassifikation. Der Referenz-Zug
heißt jetzt `_pattern_turn()` und trägt einen echten Muster-Intent.

**Verifikation:** `pytest -q` → 3162 passed, 4 skipped (3144 vorher, +18) ·
`ruff check .` + `ruff check ../evals` → All checks passed ·
`export_openapi.py --check` → unchanged.

**Bewusst NICHT gebaut (Folgearbeit, gehört dem Nutzer):** der Studio-getriebene
Golden-Lauf geht über `eval_service` → `runner.run_flows(url, flows)` **ohne**
Kopfzeilen und misst damit immer die Muster-Engine. Den Umschalter dorthin zu
ziehen hieße, den Eval-API-Vertrag zu erweitern (`POST /api/eval/golden` bräuchte
ein Feld) — eine Produktentscheidung, keine Auslassung. Der Weg über die CLI
steht und reicht für die Messung.

### A6 — Fortschritt im Agent-Modus sichtbar ✅ (2026-08-12)

Der Nebenbefund aus A4 (oben, „Gemessen, für A4 relevant") eingelöst — er war
kleiner beschrieben, als er ist. **Das Etikett fror nicht nur ein, es log auch.**
`respond_agent` setzt beim Eintritt `progress.start("response", …)`, also steht
in der Ladeblase „Formuliere Antwort …" — und `send-message.ts:98`
(`if (!label) return`) behält bei `null` das vorige Etikett. Die Schleife meldet
danach nur `agent_iteration`/`agent_tool`, beide fielen aus der Erlaubnisliste.
Ergebnis: den **ganzen** Lauf über „Formuliere Antwort …", während der Agent in
Wahrheit Werkzeuge ruft — gemessen 1,2–23,3 s je Aufruf (C9). Die Muster-Engine
wechselt hier durch vier Etiketten; ausgerechnet der langsamere Weg schwieg.

**Zwei Einträge, zwei Katalog-Schlüssel je Sprache — mehr nicht.** Die Etiketten
wechseln sich ab (`agent_iteration` vor jedem Modellzug, `agent_tool` vor jedem
Werkzeug), und genau dieser Wechsel ist das Fortschritts-Signal.

Drei Entscheidungen, jede mit einem Grund und einer Alternative, die verworfen
wurde:

* **Kein Werkzeugname in der Blase**, obwohl das Ereignis ihn trägt (`data.tool`)
  und es eine Zeile wäre. Gemessen: der Widget-Katalog enthält **kein einziges**
  Maschinenwort — kein „Werkzeug", kein „tool". Ein „wlo_delete_content" in der
  Ladeblase wäre das erste. Als Test gepinnt, nicht als Vorsatz.
* **Keine Richtungsangabe** (lesen/ändern), obwohl `is_confirmable()` sie im
  Backend kennt. Sie ins Widget zu holen hieße, eine **zweite Werkzeugliste**
  dort zu führen; sie über das Ereignis mitzuschicken hieße, das Backend um ein
  Feld zu erweitern, dessen einziger Zweck ein Etikett ist. „Arbeite mit
  WLO-Inhalten …" ist für Suche, Abruf und Kuration gleichermaßen wahr.
* **Kein Zähler** („Schritt 3 von 8"), obwohl `{iteration}` mitkommt und der
  Übersetzer Platzhalter kann. Keines der acht Bestands-Etiketten nennt Zahlen;
  ein Zähler in der Ladeblase ist außerdem eine Aussage über die Mühe, nicht
  über die Sache.

**Der Deckel der Fortschritts-Warteschlange wurde geprüft und NICHT angefasst**
(`api/sse.py:43`, 200 Plätze): der Generator leert laufend, ein Lauf meldet
~2 Ereignisse je Schritt. Es gibt hier nichts zu härten — nur etwas, das man
fälschlich härten könnte.

Rot-Grün: beide neuen Tests scheiterten zuerst mit ihrem eigenen Grund
(`null`, weil der Eintrag fehlte), nicht mit einem Sammelfehler.
Zwei Doku-Zeilen wurden durch die Erweiterung falsch („die vollständige
8-Einträge-Map") und sind mitgezogen — der Bestands-Test heißt jetzt
`vollständige step→Label-Map der Muster-Engine`.

**Verifikation:** `npx ng test ui` → 703 passed (701 vorher, +2) ·
`npx eslint` über die vier geänderten Dateien → 0 Befunde.
Backend unberührt, also kein neuer Suite-Lauf nötig.

**Kein Handbau nötig:** anders als in ALT baut das Prod-Image das Widget selbst
(`Dockerfile:36`, `npm run build:widget`) — genau um den Fehler „Studio neu,
Widget alt" auszuschließen. Der nächste Image-Bau trägt die Etiketten mit.

### M — MCP-Seite
- [x] **M1 fertig 2026-08-12** — Zugangszähler nach `jti` statt Adresse.
  Plan + Belege im MCP-Baum: `docs/plans/2026-08-12-relay-credential-limiter.md`,
  Abschluss in dessen `STATUS.md`.
- [ ] **M2** Session-Berechtigung (Cookie-Pfad) — dort entworfen, bewusst
  ungebaut bis eine konkrete edu-sharing-Einbettung existiert.

## 6. Was NICHT gebaut wird

* Kein Umbau an `tool_loop.py`, `pattern_engine.py`, `response_prompt_builder.py`,
  `_select_active_tools`, `assemble`, `persist`, `card_pipeline`.
* Keine zweite Antwort-Zusammensetzung: der Agent-Modus im Chat liefert ein
  synthetisches `pattern_output`, damit `assemble` **unverändert** läuft.
* Keine Session-Berechtigung am MCP (das ist P2 dort, wartet auf eine konkrete
  Einbettung).

## 7. Verifikation

`OTEL_TRACES_EXPORTER=none uv run pytest -q` (mit Postgres) · `ruff check .` ·
`uv run python scripts/export_openapi.py --check` · `npx ng test studio` +
`npx ng test ui` · Rot-Grün je Scheibe.

**Der Bestandsschutz ist die vorhandene Suite:** Vorgabe `pattern` heißt, die
~3028 Bestandstests fahren weiter den alten Weg. Ein Wächter prüft zusätzlich die
Gegenrichtung.
