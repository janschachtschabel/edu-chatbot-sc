# Token-Streaming der Antwort ins Widget

Stand 2026-10-03 · **Freigegeben** — der Nutzer folgt allen Empfehlungen in §4 (E-S1…E-S7,
Ansatz B; 2026-10-03). Bau nach §8, Log in §10.
Auftrag: „wie empfohlen fortfahren“ (Reihenfolge der Befundliste: Paket 1 → Paket 2 → Plan für
das Token-Streaming, `offene-befunde-und-todo.md` §2 „Kette-Plan, nächste Hebel“).

## 1 Ziel

Die Antwort erscheint im Widget, während das Modell sie schreibt. Die fertige Antwort mit
Karten, Kästen und Schnellantworten ersetzt sie am Ende wie heute — in den häufigen Fällen
ohne sichtbaren Sprung. Screenreader hören wie heute genau eine Ansage je Antwort.

**Umfang.**
- Drin:
  - der Muster-Weg über `respond_to_user`;
  - der Agent-Weg über `respond_to_user` (Phase 4);
  - die Anzeige im Widget samt Barrierefreiheit;
  - der Schalter, die Messung und die Doku.
- Draußen:
  - freier Inhaltstext (E-S1) und das Mitwachsen des Dokument-Kastens (E-S6);
  - der Verbindungsabbruch (E-S7);
  - `/api/agent/stream`;
  - der Studio-Probelauf und der Eval-Läufer — beide rufen `POST /api/chat` und bleiben, wie
    sie sind.

**Projektregeln, die jede Aufgabe einhält** (CLAUDE.md):
- Die vier SSE-Namen bleiben byte-gleich.
- Die neuen Domänen-Module (`stream_gate`, `stream_preview`, `tool_pflicht`) importieren nur
  stdlib.
- Kein Modul-Global: `TokenStrom` entsteht je Anfrage.
- Jede neue Datei bleibt unter 300 Zeilen.
- Test zuerst.

## 2 Messung

**Heute** (Tempo-Kette, Variante V3, `2026-09-30-muster-kette-zeit.md`): Median 9,3 s je
Muster-Zug, davon Klassifikation 5,0 s und Antwort 4,0 s. Das Widget bekommt alles in einem
`result`-Rahmen nach `persist`; bis dahin zeigt es Punkte und ein Phasen-Label.

**Spike 2026-10-01** (`gpt-6-luna` über die Responses-Brücke, `stream=True`, LiteLLM 1.91.5,
Skript `s_stream_spike.py` im Scratchpad; Aufrufweg wie `llm_streaming._stream_completion`):

| Fall | erster Chunk | `respond_to_user.text` läuft | Ende |
|---|---|---|---|
| Antwort über `respond_to_user`, ≈ 400 Zeichen, `tool_choice=required` | 1,46 s | 1,46 → 2,67 s | 2,67 s |
| dasselbe mit Suchwerkzeug im Angebot, `tool_choice=auto` | 1,70 s | 1,71 → 3,09 s | 3,09 s |
| Suchrunde (`search_wlo_content`) | 1,17 s | — | 2,21 s |

- Jeder Chunk trägt genau eine Choice mit Index 0. Die Annahme `choices[0]` in
  `_stream_completion` hält also; die Zwei-Choices-Form der Brücke (`llm_choices`) tritt beim
  Streamen nicht auf.
- Keine Vorrede in Werkzeugrunden. Der Text fließt ab dem ersten Chunk mit ≈ 300 Zeichen/s.
- **Erwarteter Gewinn:** Die ersten Wörter stehen etwa um die Schreibzeit der Antwort früher da
  (Länge ÷ 300 Zeichen/s) plus den Nachlauf nach der Antwort (≈ 0,3 s). Bei 400 Zeichen sind
  das ≈ 1,5 s, bei 2 000 Zeichen ≈ 6–7 s. ALT fand „nur die letzten 1–2 s“; das deckt sich
  mit kurzen Antworten.
- **Was Streaming nicht ändert:** Die Klassifikation (5,0 s) bleibt Wartezeit mit Phasen-Label.

## 3 Bestand

- **Ruhende Naht:** `graph/build.py:139,183-185` → `graph/nodes/respond.py:67,428` →
  `services/generate.py:59,177` → `services/tool_loop.py:282-286` →
  `services/llm_streaming._stream_completion`. `_RespondToUserExtractor` liest das `text`-Feld
  mitlaufend. `/api/chat/stream` reicht nichts herein (`api/chat.py:169-174`), und
  `tests/test_chat_stream.py:228-234` pinnt das.
- **Mängel der ruhenden Teile** (`services/llm_streaming.py`):
  - `\uXXXX` wird zu `uXXXX` (Z. 141-146; Audit 2026-09-29, offen).
  - Der Extraktor bekommt das rohe `on_token` und umgeht den Denkmarken-Filter (Z. 245).
  - Freier Inhaltstext jeder Runde geht an den Client (Z. 228-230), auch eine Vorrede vor
    Werkzeugaufrufen.
- **SSE:** `api/sse.py` macht aus jedem Sink-Ereignis einen `phase`-Rahmen. Die Warteschlange
  fasst 200 Ereignisse; beim Überlauf fällt still etwas weg (Z. 71-76).
- **Widget:**
  - `text_delta` ist bewusst ein No-op (`ui/shell/send-message.ts:93-96`).
  - Die Ladeblase zeigt nur Punkte und Phase.
  - Die ganze Liste ist `role="log" aria-live="polite"` (`chat-shell.component.html:20`).
  - Der Render-Cache ist nach dem Volltext geschlüsselt (`markdown-renderer.ts:104`).
- **Agent:**
  - Er streamt nicht (`services/agent_loop.py:274`).
  - Text einer Runde mit Werkzeugaufrufen wird verworfen (Z. 282-287).
  - `respond_to_user` gibt es dort nur mit `AGENT_INLINE_QUICK_REPLIES` (Vorgabe aus).
- **Was den Text nach der Generierung ändert** (Bestandsaufnahme 2026-10-01):

| Schritt | Wirkung | vor der Antwortrunde bekannt? | Umgang (Ansatz B) |
|---|---|---|---|
| Denkmarken (`strip_reasoning_markers`) | ändert | — | Filter im Strom |
| A1-Reflexion (`tool_loop.py:877ff.`) | verwirft die Antwort | ja, je Runde | Runde streamt nicht, wenn A1 sie verwerfen kann |
| Optionszeilen am Ende (`_strip_trailing_option_lines`) | kürzt am Ende | nein | Austausch am Ende (selten) |
| Hinweise (`append_answer_notes`) | hängt an | — | erscheinen am Ende |
| Ansage-Zeile (`mit_ladehinweis`; Agent `mit_ladehinweisen` + `mit_master_ansage`) | setzt voran, räumt Modell-Ansagen | ja | dieselbe Funktion im Vorschau-Filter |
| Typ-Fokus M05/M06 (`turn_links.py:339-370`) | ersetzt alles | ja (Suchmuster) | Sperre |
| Anti-Halluzination (`turn_links.py:397ff.`) | schreibt Sätze um | nur M05/M06 | Sperre |
| Links → Label (`domain/url_helpers._extract_web_links_from_text`) | ändert die Darstellung | — | dieselbe Funktion im Vorschau-Filter |
| Box-Routing M09–M11 (`turn_persist.py:551`) | Text wandert in den Kasten | ja | Sperre (E-S6) |
| M16-Auflöser (`turn_persist.py:624-631`) | kann den Text ersetzen | ja | Sperre |
| Lotsen-URLs (`widget_postprocess.py:428-441`) | ändert URLs | nur mit Karten | über die Sperre M05/M06 weitgehend abgedeckt, sonst Austausch |

## 4 Entscheide (freigegeben 2026-10-03: alle Empfehlungen)

- **E-S1 — Was gestreamt wird:** nur das `text`-Feld von `respond_to_user`, in beiden Maschinen,
  nie freier Inhaltstext. Eine Vorrede vor einem Werkzeugaufruf würde sonst aufblitzen und
  wieder verschwinden. Folge: M01/M02 (Krise, Ablehnung), Muster ohne Schnellantworten und der
  Agent mit `AGENT_INLINE_QUICK_REPLIES=aus` antworten wie heute auf einmal. *Empfehlung: so.*
- **E-S2 — Abgleich mit der Endverarbeitung:** drei Ansätze, siehe unten. *Empfehlung: B.*
- **E-S3 — Darstellung:** fortlaufendes Markdown in der Ladeblase, ohne Render-Cache. Das
  Phasen-Label weicht dem Text, die Punkte bleiben darunter. Alternative: Klartext und
  Markdown erst am Ende — ruhiger, aber die Formatierung springt am Ende. *Empfehlung:
  fortlaufend.*
- **E-S4 — Barrierefreiheit:** Der vorläufige Text steht unter `aria-hidden="true"`; angesagt
  wird wie heute nur die fertige Antwort. *Empfehlung: so.*
- **E-S5 — Schalter:**
  - `CHAT_TOKEN_STREAMING`, Vorgabe aus. Eingeschaltet wird nach der Live-Probe (Phase 5).
  - Der Agent hängt zusätzlich an `AGENT_INLINE_QUICK_REPLIES`, das auf den
    Master-Skill-Abschnitt „Schnellantworten“ wartet.
  - *Empfehlung: so.*
- **E-S6 — Dokument-Muster M09–M11:** in v1 sperren, sonst wanderte der Text am Ende aus der
  Blase in den Kasten. Später als eigener Schritt: den Dokument-Kasten mitwachsen lassen —
  dort liegt bei langen Dokumenten der größte Gewinn. *Empfehlung: sperren.*
- **E-S7 — Abbruch der Verbindung** (Audit 2026-09-29, Entscheid 6) bleibt außerhalb. Das
  Verhalten ist unverändert.

### Ansätze zu E-S2

**A — Rohtext streamen, am Ende austauschen.**
- Wie: Der Extraktor-Text geht unverändert hinaus, `result` ersetzt die Blase.
- Dafür: am wenigsten Code.
- Dagegen: sichtbare Sprünge. Der Typ-Fokus ersetzt den ganzen Text, die Ansage-Zeile schiebt
  sich oben davor, Links verlieren am Ende ihr Aussehen.
- Risiko: genau das Flackern, an dem ALT scheiterte.

**B — Sperre vorab, Vorschau-Filter, Austausch am Ende (empfohlen).**
- Wie:
  - Vor der Antwortrunde entscheidet eine reine Funktion, ob der Zug streamt.
  - Der empfangene Text läuft durch dieselben Domänenfunktionen wie später die
    Endverarbeitung, soweit sie nur vom Text abhängen (Ansage-Zeile, Links → Label).
    Unfertige Konstrukte am Ende werden zurückgehalten.
  - Gesendet wird nur, was das schon Gesendete fortsetzt.
  - `result` bleibt maßgeblich und ersetzt die Blase; im Normalfall ist der Text gleich.
- Dafür: kein doppelter Regelcode, Sprünge nur in seltenen Fällen, messbar über die
  Drift-Zeile.
- Dagegen: mehr Teile (Sperre, Filter, Strom).
- Aufwand: ≈ 2–3 Arbeitstage samt Widget.
- Risiko: Ein übersehener Umschreiber macht den Austausch sichtbar; die Drift-Zeile zeigt ihn.

**C — Entwurfs-Blase.**
- Wie: Der Text wird sichtbar vorläufig (gedämpft) gestreamt und dann ersetzt.
- Dafür: ehrlich.
- Dagegen: mehr UI-Arbeit, der Austausch bleibt sichtbar, und das Voranstellen löst es nicht.

*Begründung der Empfehlung:* A wiederholt den ALT-Fehler, C kostet UI-Arbeit, ohne die Ursache
zu beheben.

## 5 Architektur

### Datenfluss (Muster-Weg)

```
POST /api/chat/stream → _stream_turn: strom = TokenStrom(progress)   (nur mit Schalter)
  build_turn_graph(on_token=strom)
  respond: grund = sperrgrund(...)
           grund → strom.sperren(grund), generate(on_token=None)
           sonst → strom.oeffnen(umformen), generate(on_token=strom)
    tool_loop: Runde streamt nur, wenn A1 sie nicht verwerfen kann → _stream_completion(strom)
      _RespondToUserExtractor → ThinkSafeStreamer → strom(stück)
        TokenStrom → VorschauStrom (zurückhalten, umformen, Präfix-Regel)
                   → höchstens alle 50 ms progress.text(text, pos)
          sse_turn: Art "text" → event: text_delta, data: {"text", "pos"}
  … assemble → persist → result
_to_payload: strom.abschluss(result.content) → Logzeile (Rahmen, Zeichen, erstes Stück, Drift)
Widget: text_delta → appendStreamText(id, text, pos) → Ladeblase zeigt Markdown (aria-hidden)
        result     → Ladeblase weg, fertige Antwort wie heute
```

### Rahmen-Vertrag

`event: text_delta` mit `data: {"text": "<angehängter Text>", "pos": <Länge des bisher gesendeten
Vorschautexts in Unicode-Zeichen (Codepunkte, wie Python `len`)>}`.
- Name und `text` wie ALT (`frontend/src/app/services/api.service.ts`, dort zurückgerollt).
  `pos` ist neu.
- Reihenfolge: `connected` → (`phase` | `text_delta`)* → `result` | `error`.
- `result.content` ist maßgeblich. Ein Client, der `text_delta` nicht kennt, verhält sich wie
  heute; die vier bestehenden Namen bleiben byte-gleich (CLAUDE.md, Regel 6).

### Dateien

Neu (Backend):
- `domain/stream_gate.py` (≈ 50 Z.): `sperrgrund(...)`.
- `domain/stream_preview.py` (≈ 120 Z.): `stabiler_teil`, `VorschauStrom`.
- `domain/tool_pflicht.py` (≈ 40 Z.): die A1-Bedingung als reine Funktion.
- `services/token_stream.py` (≈ 100 Z.): `TokenStrom`.
- Tests: `tests/test_stream_gate.py`, `tests/test_stream_preview.py`, `tests/test_tool_pflicht.py`,
  `tests/test_token_stream.py`, `tests/test_token_streaming_e2e.py`.

Geändert (Backend):
- `services/llm_streaming.py`: `\u`-Escapes; Extraktor hinter `ThinkSafeStreamer`; freier
  Inhaltstext nicht mehr an `on_token`.
- `obs/progress.py`: `TurnProgress.text(text, pos)`.
- `api/sse.py`: Art `text` → Rahmen `text_delta`.
- `settings.py`: `chat_token_streaming`.
- `api/chat.py`: `_stream_turn` bindet `TokenStrom` hinter dem Schalter; `_to_payload` ruft
  `abschluss`.
- `graph/nodes/respond.py` (520 Z., + ≈ 15): Sperre und Umformen verdrahten.
- `services/tool_loop.py` (971 Z., + ≈ 6): Runden-Regel; der Reflexions-Block nutzt
  `tool_pflicht`.
- Agent (Phase 4): `services/agent_loop.py`, `graph/nodes/respond_agent.py`, `graph/build.py`.

Geändert (Widget, `frontend/projects/ui/src/`):
- `grouping/message-types.ts`: `streamText?: string`.
- `shell/message-store.ts`: `appendStreamText`, `clearStreamText`.
- `shell/send-message.ts`, `shell/chat-shell.component.html` (+ Stil).
- `markdown/markdown-renderer.ts`: `render(text, sender, cache = true)`.
- `stream/stream-client.ts`: `text_delta` zählt für die Wächter.

### Schnittstellen

```python
# domain/stream_gate.py
def sperrgrund(*, eingeschaltet: bool, antwort_werkzeug: bool, muster_id: str,
               risiko: str) -> str | None:
    """None = streamen. Sonst der Grund für die Logzeile: "aus" | "ohne_antwort_werkzeug"
    | "suchmuster" (M05, M06) | "dokumentmuster" (M09–M11) | "aufloeser" (M16)
    | "risiko" (risk_level != "low")."""

# domain/stream_preview.py
def stabiler_teil(roh: str) -> str:
    """Bis vor das erste noch offene Konstrukt: eine `[` ohne abgeschlossenen Link
    (`]` fehlt, `]` am Ende, `](` ohne `)`), eine mit `[` beginnende Zeile ohne
    Zeilenende (Ansage-Kandidat), ein ungepaartes `**` im letzten Absatz."""

class VorschauStrom:
    def __init__(self, umformen: Callable[[str], str]) -> None: ...
    def weiter(self, stueck: str) -> str:
        """Den neu anzuhängenden Vorschautext ("" = nichts). Vorschau =
        umformen(stabiler_teil(roh)); gesendet wird nur, was mit dem schon
        Gesendeten beginnt — sonst rueckschritte += 1 und nichts."""
    gesendet: str        # property
    rueckschritte: int   # property

# domain/tool_pflicht.py — dieselbe Bedingung wie heute im A1-Block
def fehlende_pflichtwerkzeuge(pattern_output: dict[str, Any],
                              tools_called: list[str]) -> list[str]: ...

# services/token_stream.py
class TokenStrom:
    def __init__(self, progress: TurnProgress, *, takt_s: float = 0.05,
                 uhr: Callable[[], float] = time.monotonic) -> None: ...
    def oeffnen(self, umformen: Callable[[str], str]) -> None: ...
    def sperren(self, grund: str) -> None: ...
    def __call__(self, stueck: str) -> None: ...   # das on_token-Protokoll
    def schliessen(self) -> None: ...              # Rest senden
    def abschluss(self, endtext: str) -> dict[str, Any]: ...  # Kennzahlen + Logzeile

# obs/progress.py
def text(self, text: str, pos: int) -> None:
    # Sink-Ereignis {"kind": "text", "step": "", "label": "", "data": {"text": ..., "pos": ...}}
```

```ts
// ui/shell/message-store.ts — nur die Ladeblase, nur wenn pos === bisherige Länge
appendStreamText(loadingId: string, text: string, pos: number): void;
clearStreamText(loadingId: string): void;
// ui/markdown/markdown-renderer.ts
render(text: string, sender: 'bot' | 'user' = 'bot', cache = true): SafeHtml;
```

**Umformen im Muster-Weg** (Closure in `respond`; sie liest `entities` bei jedem Aufruf, damit
eine in der Schleife geholte Anleitung rechtzeitig vorne steht):

```python
def umformen(text: str) -> str:
    ohne_links, _ = _extract_web_links_from_text(text, cards=None)
    return mit_ladehinweis(ohne_links, ctx.session_state.get("entities"),
                           ctx.session_state.get("turn_count"))
```

**Sperre in `respond`:**
- `eingeschaltet` = Schalter an und `on_token` ist ein `TokenStrom`.
- `antwort_werkzeug` = `inline_anzahl(pattern_output) > 0` — dieselbe Funktion, mit der
  `services/response_tool_selection.py:506-509` das Werkzeug anbietet.
- `muster_id` = das Gewinner-Muster nach `route`.
- `risiko` = `ctx.safety.risk_level`.

**Takt:**
- `TokenStrom` sammelt die Stücke und sendet, sobald seit dem letzten Senden ≥ 50 ms vergangen
  sind (gemessen beim Eintreffen eines Stücks).
- `schliessen()` sendet den Rest. Kein Timer, keine eigene Task.

## 6 Nicht-funktional

- **Leistung:**
  - Höchstens 20 `text_delta` je Sekunde; die Bytes entsprechen etwa der Antwortlänge plus
    Rahmen.
  - Markdown je Rahmen ohne Cache (marked + DOMPurify; Dauer bei 3 000 Zeichen in Phase 3
    messen).
  - Der LLM-Platz (Semaphore) bleibt wie heute für die Dauer des Aufrufs belegt.
- **Sicherheit:**
  - Derselbe Render-Pfad mit DOMPurify, kein Bypass; `pos` wird im Client als Zahl geprüft.
  - M01/M02 streamen nie (kein `respond_to_user`), erhöhtes Risiko sperrt.
  - Es gibt keine Ausgabeprüfung, die umgangen würde — geprüft wird nur die Eingabe.
- **Barrierefreiheit:** wie E-S4. Fokus unverändert, keine neue Animation (reduzierte Bewegung
  unberührt), dieselben Blasen-Stile und damit derselbe Kontrast.
- **i18n:** keine neuen Texte.
- **Datenschutz:** keine neuen Daten; die Rahmen tragen nur, was `result` ohnehin trägt.
- **Beobachtbarkeit:** eine INFO-Zeile je Zug, etwa `Token-Strom: muster=M04 rahmen=23
  zeichen=812 erstes=1480ms rueckschritte=0 drift=nein` bzw. `Token-Strom: gesperrt
  (suchmuster)`.

## 7 Risiken

- **R1 Sichtbarer Austausch am Ende (Drift):** Sperre und Filter halten ihn klein; die
  Drift-Zeile misst ihn; der Schalter nimmt alles zurück.
- **R2 Flackern wie in ALT:** Takt 50 ms; die Blase wächst nur; fortlaufendes Markdown, ohne
  dass der Cache wächst. Bildfolge in Phase 5.
- **R3 Buchung gestreamter Aufrufe:** Die Usage kommt im letzten Chunk; im Spike warnte
  pydantic „Expected `ResponseAPIUsage`“. Test T3: gebuchte Token je Phase gleich wie ohne
  Streaming.
- **R4 Form der Brücke ändert sich mit einem LiteLLM-Update:** Das Spike-Skript dient als
  Wiederholungsprobe; eine Warnzeile, wenn ein Chunk eine Choice mit Index > 0 trägt.
- **R5 Puffernde Proxys in Produktion:** `phase`-Rahmen laufen heute über denselben Weg. Die
  Staging-Probe macht der Nutzer.
- **R6 Eine verworfene Antwort (A1) ist schon sichtbar:** Die Runden-Regel verhindert das.
- **R7 Screenreader:** `aria-hidden`, Template-Test, Handprobe mit NVDA (Nutzer).
- **R8 Dateigrößen:** `respond.py` (520), `tool_loop.py` (971) und `respond_agent.py` (499)
  wachsen um wenige Zeilen; die Logik liegt in neuen Modulen. Eintrag in Befundliste §5.
- **R9 Rückfall auf POST nach Abbruch:** Die Teilantwort darf nicht stehen bleiben →
  `clearStreamText` beim Rückfall.

## 8 Aufgaben (je Paket Schritt 0, Test zuerst)

### Phase 1 — Grundlage im Backend (Schalter aus, nichts sichtbar)

Schritt 0: `/better-coding-workflow`

| # | Inhalt | Dateien | Test zuerst / Nachweis |
|---|---|---|---|
| T1 | `\uXXXX` im Extraktor, auch über Chunk-Grenzen und als Surrogatpaar | `services/llm_streaming.py` | `test_llm_streaming.py::test_extraktor_dekodiert_unicode_escapes` (`ä`; geteilt `\u00` + `e4`; `😀` → 😀) |
| T2 | Extraktor hinter `ThinkSafeStreamer`; freier Inhaltstext nicht mehr an `on_token` (bleibt in `msg.content`) | `services/llm_streaming.py` samt Docstring | `test_antwort_text_laeuft_durch_den_denkfilter`, `test_freier_inhaltstext_erreicht_den_client_nicht` |
| T3 | Buchung gestreamter Runden | `services/tool_loop.py` (nur falls nötig) | `test_tool_loop.py::test_gestreamte_runde_bucht_wie_ungestreamte` (echter Transport, gefälschtes `llm._acompletion` mit Usage im letzten Chunk) |
| T4 | `stabiler_teil` und `VorschauStrom` | `domain/stream_preview.py` | `tests/test_stream_preview.py`: Link erst komplett; `[`-Zeile bis zum Zeilenende; ungepaartes `**`; Präfix-Regel zählt einen Rückschritt und sendet nichts; Umformen mit Präfix → das erste Stück beginnt mit dem Präfix |
| T5 | `TurnProgress.text` und `text_delta`-Rahmen | `obs/progress.py`, `api/sse.py` | `test_chat_stream.py::test_text_ereignis_wird_text_delta_rahmen` (Reihenfolge, Umlaute, `phase` unverändert) |
| T6 | `TokenStrom` | `services/token_stream.py` | `tests/test_token_stream.py` mit Uhr-Attrappe: Takt, `pos`-Folge, gesperrt → nichts, `schliessen` sendet den Rest, `abschluss` meldet Drift ja/nein |
| T7 | Schalter `CHAT_TOKEN_STREAMING` (Vorgabe aus) | `settings.py`, Umgebungsliste in den Docs | Test: Vorgabe ist aus |

### Phase 2 — Muster-Weg

Schritt 0: `/better-coding-workflow`

| # | Inhalt | Dateien | Test zuerst / Nachweis |
|---|---|---|---|
| T8 | `sperrgrund` | `domain/stream_gate.py` | Tabellentest je Grund in `tests/test_stream_gate.py` |
| T9 | A1-Bedingung als reine Funktion (verhaltensgleich) | `domain/tool_pflicht.py`; der Reflexions-Block in `tool_loop.py` nutzt sie | `tests/test_tool_pflicht.py` (ANY/ALL); die bestehenden Reflexions-Tests bleiben grün |
| T10 | Eine Runde streamt nur ohne drohende A1 | `services/tool_loop.py:282` | `test_runde_mit_drohender_reflexion_streamt_nicht`, `test_runde_nach_erfuellter_pflicht_streamt` |
| T11 | `respond` verdrahtet Sperre und Umformen | `graph/nodes/respond.py` | gesperrt → `generate` bekommt `on_token=None`, der Strom kennt den Grund; offen → `generate` bekommt den Strom; das Umformen setzt die Ansage-Zeile voran, wenn eine Anleitung geholt wurde |
| T12 | Der Endpunkt bindet `TokenStrom` hinter dem Schalter; Logzeile mit Drift | `api/chat.py` | `test_chat_stream.py`: Schalter aus → `on_token is None` (der bestehende Pin, parametrisiert); an → `TokenStrom`; `_to_payload` ruft `abschluss` |
| T13 | Ende zu Ende im Backend | `tests/test_token_streaming_e2e.py` | Vorbild `test_agent_schreib_abnahme.py`: echte Knoten, gefälscht nur Prozessgrenzen (`llm._acompletion` mit Strom-Chunks wie im Spike, MCP, DB). M04-Zug: die verketteten `text_delta` ergeben `result.content`. M05-Zug: kein `text_delta` |

### Phase 3 — Widget

Schritt 0: `/better-coding-workflow` und `/better-coding-frontend`

| # | Inhalt | Dateien | Test zuerst / Nachweis |
|---|---|---|---|
| T14 | `streamText`, `appendStreamText`/`clearStreamText` mit `pos`-Regel | `message-types.ts`, `message-store.ts` | passt `pos` → anhängen; Lücke → ignorieren; nur die Ladeblase |
| T15 | `text_delta` in `runSendMessage`; der Rückfall auf POST leert | `send-message.ts` | die Stücke landen in der Ladeblase; `result` ersetzt; `error` entfernt den Teiltext; der POST-Rückfall leert; der bisherige No-op-Test wird ersetzt |
| T16 | Die Ladeblase zeigt den Text (`aria-hidden`), die Phase weicht, die Punkte bleiben | `chat-shell.component.html` (+ Stil) | `chat-shell-template.spec.ts`: Teiltext `aria-hidden="true"`, die fertige Antwort nicht; `role="log"` unverändert |
| T17 | Rendern ohne Cache | `markdown-renderer.ts` | `cache=false` lässt den Cache unverändert, die Ausgabe gleicht der mit Cache |
| T18 | `text_delta` zählt für die Leerlauf- und Stillstands-Wächter | `stream-client.ts` | `stream-client.spec.ts` |
| T19 | Bau, Budget, Lint | — | `npm test`, Lint, Widget-Build, gzip ≤ 175 kB |

### Phase 4 — Agent-Weg (wirksam erst mit `AGENT_INLINE_QUICK_REPLIES=an`)

Schritt 0: `/better-coding-workflow`

| # | Inhalt | Dateien | Test zuerst / Nachweis |
|---|---|---|---|
| T20 | Die Naht auch an `respond_agent` | `graph/build.py` | `test_graph_build.py` |
| T21 | `run_agent_loop(..., on_token=None)` streamt nur, wenn `respond_to_user` im Angebot ist | `services/agent_loop.py` | ohne Antwort-Werkzeug ungestreamt; mit → der Text kommt an; Werkzeugrunden senden nichts |
| T22 | `respond_agent`: Sperre (Schalter, Antwort-Werkzeug, Risiko) und Umformen in der Reihenfolge des Abschlusses (`mit_ladehinweisen` → `mit_master_ansage`, `respond_agent.py:434-445`) | `graph/nodes/respond_agent.py` | `test_respond_agent.py` |

### Phase 5 — Probe, Messung, Doku

Schritt 0: `/better-coding-workflow`

| # | Inhalt | Nachweis |
|---|---|---|
| T23 | Live-Probe im Testcontainer mit Schalter an: 4 Fragen × 2 (M04, M15, M03, M05) über ein SSE-Skript; Zeit bis zum ersten `text_delta` gegen `result`; Drift-Quote; Bildfolge der wachsenden Blase | Tabelle im Log |
| T24 | Doku: `docs/agent-modus.md` (Strom; Z. 341-345 stimmt dann wieder), Befundliste, Plan-Log | — |
| T25 | Entscheid über die Vorgabe des Schalters | Nutzer |

## 9 Abnahme

- **A1:** Mit Schalter aus ist die Rahmenfolge byte-gleich wie heute; die bestehenden Tests
  bleiben grün.
- **A2:** Mit Schalter an kommt bei M04/M15 das erste `text_delta` bei Antworten ab 400 Zeichen
  mindestens 1 s vor `result` (Probe T23). Die verketteten Stücke ergeben in ≥ 90 % der Züge
  `result.content` (Drift-Quote).
- **A3:** M05, M06, M09–M11, M16, M01 und M02 senden kein `text_delta`.
- **A4:** Genau eine Screenreader-Ansage je Antwort (Template-Test und Handprobe).
- **A5:** Keine Abweichung in der Token-Buchung (T3).
- **A6:** Das Widget-Budget hält.

**Regression:** volle Backend-Suite, Frontend-Tests, e2e `frontend/e2e/chat.spec.ts`
(Abbruch → POST-Rückfall).

## 10 Log

### Phase 1 — Grundlage im Backend (2026-10-03, erledigt)

- **T1** Unicode-Escapes: `_escape_at` dekodiert mit `json`; Surrogatpaare werden
  zusammengesetzt, ein einsames Surrogat wird zu U+FFFD. Der Test prüft jede Chunk-Grenze;
  die Testdaten entstehen über `json.dumps(..., ensure_ascii=True)`.
- **T2** Der Extraktor läuft hinter `ThinkSafeStreamer`; freier Inhaltstext wird gesammelt,
  aber nicht gesendet (E-S1). Drei ALT-Pins passen jetzt zur neuen Vorgabe (zwei
  Content-Tests, der Routing-Test prüft den rekonstruierten Text statt der Weitergabe).
- **T3** Buchung: gemessen an `gpt-6-luna` über die Brücke. Gestreamt kommt dasselbe
  `Usage`-Objekt wie ohne Streaming (765/113/26 gegen 765/124/22). R3 ist entkräftet; der
  Test pinnt das ohne Codeänderung.
- **T4** `domain/stream_preview.py` (`stabiler_teil`, `VorschauStrom`), 16 Tests.
- **T5** `TurnProgress.text` und `api/sse._rahmen_fuer` (Art `text` → `text_delta`).
- **T6** `services/token_stream.py` (`TokenStrom`: Takt 50 ms, Kennzahlen, Drift-Logzeile),
  6 Tests.
- **T7** Schalter `CHAT_TOKEN_STREAMING` (Vorgabe aus) in `settings.py` und `deploy/.env.example`.
- Nachweis: 143 Tests in den betroffenen Dateien grün, `ruff` sauber.
- `services/llm_streaming.py` steht jetzt bei 302 Zeilen → Befundliste §5.

### Phase 2 — Muster-Weg (2026-10-03, erledigt)

- **T8** `domain/stream_gate.sperrgrund`, Tabellentest mit 13 Fällen.
- **T9** `domain/tool_pflicht` (`fehlende_pflichtwerkzeuge`, `gerufene_werkzeuge`).
  Verhaltensgleich herausgelöst; die bestehenden Reflexions-Tests sind grün.
- **T10** `tool_loop`: eine Runde streamt nur, wenn die A1-Reflexion ihre Antwort nicht mehr
  verwerfen kann (`_reflection_done` oder keine Pflicht offen).
- **T11** Neues Modul `graph/nodes/respond_strom.strom_fuer_muster_zug` (Sperre und Umformung:
  `mit_ladehinweis`, dann Links → Label). `respond.py` ruft es vor der Antwortrunde und danach
  `schliessen()`; das sind +6 Zeilen auf 526.
- **T12** `api/chat._stream_turn` legt den `TokenStrom` nur mit Schalter an; `_to_payload` ruft
  `abschluss(result.content)` (Logzeile mit Drift).
- **T13** `tests/test_token_streaming_e2e.py`: Ende zu Ende im Backend.
  - M04 mit Unicode-Escapes und Link, Häppchen à 3 Zeichen. Die verketteten `text_delta`
    ergeben den umgeformten Antworttext, ohne Lücke und ohne Drift.
  - M05 sendet nichts und läuft ungestreamt.
- Abweichung vom Plan: Die Abfrage `antwort_werkzeug` brauchte keine eigene Funktion,
  `inline_anzahl` trägt den Schalter schon. Aus T11 im Plan wurden T11 und T12 hier.
- Nachweis: Backend-Suite 4936 passed, 4 skipped.

### Phase 3 — Widget (2026-10-03, erledigt)

- **T14** `ChatMessage.streamText`; `MessageStore.appendStreamText` mit `pos`-Regel. Nach einer
  Lücke bleibt der Strom stehen, `result` bringt den Rest. `clearStreamText` verwirft
  den Text samt Lücke.
- **T15** `runSendMessage`: `text_delta` → `appendStreamText` (nur mit Text als Zeichenkette und
  `pos` als Zahl). Der Rückfall auf POST leert vorher. Der alte No-op-Test ist durch die neue
  Vorgabe ersetzt.
- **T16** Ladeblase: der vorläufige Text als Markdown mit `aria-hidden="true"` und `inert`.
  Die Phase weicht, die Punkte bleiben. Den KI-Hinweis trägt erst die fertige Antwort.
- **T17** `MarkdownRenderer.render(text, sender, cache = true)`: `false` bereinigt genauso, legt
  aber nichts ab. `ShellRender.markdown` reicht das durch.
- **T18** Kein Codewechsel nötig: der Stillstands-Wächter zählt schon jedes benannte Ereignis.
  Ein Test pinnt `text_delta`, der Doku-Kommentar ist berichtigt.
- **T19** `npm run lint` sauber; `check:tokens/a11y/contrast/radii/docs` grün.
  - Budget §5.5: roh 553,5 / 600 kB, gzip 161,0 / 175 kB. Die Angular-Warnschwelle von
    550 kB war schon vorher überschritten (552,3 kB) und wächst um 1,2 kB.
  - Tests: ui 851, widget 70, studio 1327, alle grün.

### Phase 4 — Agent-Weg (2026-10-03, erledigt)

- **T20** `respond` reicht `on_token` an `respond_agent` weiter.
- **T21** `run_agent_loop(..., on_token=None)`: mit Strom ein gestreamter Aufruf, gebucht von Hand
  wie `chat_completion` (Phase `agent`). Eine Runde mit `respond_to_user` ist immer die
  letzte, ihr Text wird also nie verworfen.
- **T22** `respond_strom.strom_fuer_agent_zug`; `respond_agent` öffnet den Strom nur mit
  `respond_to_user` im Angebot und schließt ihn nach dem Lauf.
  - Die Umformung: Modell-Ansagen weg, Master-Ansage voran, Links → Label.
  - **Befund beim Bau:** `mit_master_ansage` schreibt den Merker `ANSAGE_KEY` in `entities`.
    Die Vorschau ruft sie deshalb mit einer Kopie; sonst fehlte die Zeile in der fertigen
    Antwort. Ein Test pinnt das.
  - Bewusste Vereinfachung (`simplify:` im Code): Die Anleitungs-Ansagen des laufenden Laufs
    fehlen in der Vorschau. Ihre Liste entsteht erst im Lauf; die Folge ist Drift am Ende.
- Wirksam erst mit `AGENT_INLINE_QUICK_REPLIES=1`, der auf den Master-Skill-Abschnitt
  „Schnellantworten“ wartet.
- Nachweis: Backend-Suite 4942 passed, 4 skipped.

### Phase 5 — Live-Probe (2026-10-03)

**T23 Aufbau:**
- Testcontainer `boerdi-chat-test` aus `edu-chatbot-sc:streaming-lokal`: Klon-Zweig
  `paket-2-schreib-abnahme` plus Staging, mit `CHAT_TOKEN_STREAMING=1`, im Muster-Modus mit
  `gpt-6-luna`.
- SSE-Probe `s_strom_probe.py`: 4 Fragen × 2, je in neuer Sitzung.

| Frage | Muster | erstes Stück | `result` | Rahmen | Zeichen gesendet / fertig | Drift |
|---|---|---|---|---|---|---|
| Photosynthese (7. Klasse) | M04 | 8,1 s / 6,2 s | 14,6 s / 7,2 s | 12 / 11 | 305/305 · 324/324 | nein |
| Was ist WissenLebtOnline? | M15 | 4,6 s / 6,3 s | 5,5 s / 7,2 s | 10 / 10 | 368/368 · 310/310 | nein |
| Inhalte zu einem Thema | M03 | 4,9 s / 4,6 s | 6,3 s / 5,2 s | 2 / 2 | 66/66 · 61/61 | nein |
| Arbeitsblätter Bruchrechnung | M05 | — | 11,8 s / 4,3 s | 0 | gesperrt (Suchmuster) | — |

- **Ergebnis:**
  - 6 von 8 Zügen gestreamt, wie vorgesehen; M05 gesperrt.
  - Drift 0/6: der gestreamte Text war zeichengleich mit der fertigen Antwort.
  - `pos` war in 6/6 lückenlos.
  - Vorsprung des ersten Stücks vor `result`: Median 1,0 s (0,6–6,6 s). Das passt zur
    Erwartung für kurze Antworten von 300–370 Zeichen.
- **Bildfolge im Widget** (Playwright, längere Antwort, `widget_strom.cjs`):
  - Die Blase wächst zwischen 4,5 s und 5,7 s von 46 auf 640 Zeichen; der vorläufige Text ist
    durchgehend `inert`.
  - Bei 6,5 s ersetzt ihn die fertige Antwort (663 Zeichen): derselbe Anfang, dazu KI-Hinweis
    und Schnellantworten, kein sichtbarer Sprung.
  - Das erste Stück stand damit 2,0 s vor der fertigen Antwort.
  - Die Bilder S1–S3 liegen im Scratchpad und sind nicht eingecheckt.
- Abnahme: A1 (Schalter aus byte-gleich) gilt laut Testsuite. A2 lässt sich an diesen kurzen
  Antworten nicht prüfen (die Schwelle sind 400 Zeichen); bei 663 Zeichen lag der Vorsprung
  bei 2,0 s. A3 ist für M05 belegt. A5 und A6 sind belegt. A4 (Screenreader) ist als
  Template-Test belegt; die Handprobe mit NVDA steht beim Nutzer aus.

**Review mit frischem Blick (2026-10-03):** kein hoher Befund, zwei mittlere; alle Fixes
erst mit rotem Test.
- **M1, behoben:** `pos` zählte im Server Unicode-Zeichen (Python `len`), im Widget
  UTF-16-Einheiten. Nach jedem Emoji außerhalb der BMP stand der Strom still. Das Widget zählt
  jetzt mit `Array.from(text).length`; der Vertrag nennt die Einheit.
- **M2, behoben:** Zeilen, die die Endverarbeitung als Ganzes entfernt (Aufzählungen nur aus
  einem Link, Modell-Ansagen `▸ … aktiv`), stauten den Strom. `stabiler_teil` hält solche
  Zeilen jetzt bis zum Zeilenende zurück; nachgestellt mit den echten Umformungen
  (0 Rückschritte).
  - Den Fall „Modell kopiert die Master-Ansage“ konnte ich nicht nachstellen: am Anfang wie
    mittendrin 0 Rückschritte, die `[`-Regel greift. Deshalb keine Extraregel.
- **L1, behoben:** Höchstens eine gestreamte Antwortrunde je Zug, in Tool- und Agent-Schleife.
  Vorher hing bei unlesbaren `respond_to_user`-Argumenten eine zweite Antwort an der ersten.
  - Bleibt: Antwort und Stillstand in derselben Agent-Runde. `result` ersetzt dann den Text;
    das ist selten.
- **L2, behoben:** `ThinkSafeStreamer` rechnet mit `_ohne_marker(...).lstrip()`; vorher
  verrutschte der Index bei führendem Leerraum. `strip_reasoning_markers` behält seine
  Semantik.
- **L3, behoben:** Links → Label nur mit Ergebnis-Gruppen, wie in `turn_links`.
- **L4, behoben:** Die Vorschau rechnet höchstens einmal je Takt (50 ms) und am Ende statt
  je Stück.
- **L5, behoben:** veraltete Kommentare in `respond_agent`, `generate`, `sse`, `chat`,
  `progress`.
- **Nicht behoben, selten:** HTML-Links `<a href>` im Modelltext und führender Leerraum vor
  dem ersten Link. Beide stauen bis `result`.

**T25 Empfehlung zur Vorgabe des Schalters:**
- Code-Vorgabe bleibt **aus**.
- Auf Staging per Umgebung `CHAT_TOKEN_STREAMING=1` einschalten und dort die Logzeilen
  `Token-Strom:` (Drift, Rückschritte) sowie den Proxy-Weg (R5) beobachten.
- Danach die Vorgabe umstellen. Die Entscheidung trifft der Nutzer.
