# Hybrid: der Musterkatalog als Werkzeug in der Agent-Schleife

**Frage des Nutzers (2026-08-16):** „Gefühlt ist der Agent-Loop schneller als der
Muster-Modus … wäre es möglich, beides zu kombinieren, z. B. die jetzigen Muster
in eine Art Tools zu überführen? Wie würde man Pattern-Tools und MCP-Tools
verbinden?"

---

## 1. Gemessen, bevor gebaut wurde

| | Muster-Engine | Agent-Schleife |
|---|---|---|
| Klassifikation | 1× · ~1.800–2.400 gerenderte Prompt-Zeilen aus 6 Konfig-Bereichen | 0 |
| Antwort-Schleife | 1–5 (`tool_loop.py:135`, hart) | 1–12 (`01-base/engine`) |
| Quick-Replies | 1 | 1 |
| typisch | 3–4 (max. 9) | 3–5 (min. 2) |

Der Agent spart **nicht** an der Zahl der Aufrufe, sondern am seriellen
Klassifikations-Kopf mit dem größten statischen Prompt des Zuges.

**Der Befund, der den Umbau trägt:** die Musterwahl ist längst eine
LLM-Entscheidung. In `domain/pattern_engine.py` sind Phase 1 (Gate) und Phase 2
(Score) entfernt; es gilt *Safety-Zwang → `pattern_id_hint` → Rückfall M15*. Der
Klassifikations-Aufruf ist für die Musterwahl ein eigener LLM-Zug, dessen
tragende Ausgabe ein einziger String ist.

**Die Mechanik gab es im Code schon zweimal:** virtuelle Werkzeuge in derselben
Liste wie MCP-Werkzeuge (`select_top_cards`, `respond_to_user`, `query_knowledge`,
`submit_result` — am Namen abgefangen, bevor ein MCP-Aufruf passiert), und
„Anweisung als Werkzeug-Ergebnis" (genau das tut `get_skill` in Produktion).

**Größen:** 20 Muster = 57.808 Bytes Frontmatter + 56.661 Bytes Body. Das
Frontmatter **ist** eine Werkzeugbeschreibung — und wird heute schon jeden Zug
gerendert, nur im *Klassifikations*-Prompt.

## 2. Entscheidungen des Nutzers

| Frage | Entscheidung |
|---|---|
| Ziel | Tempo · mehr Denkschritte · eine Maschine statt zwei · Muster bleiben redaktionell steuerbar |
| Schnitt | **Dritte Maschine `hybrid`** |
| Slots | **Modell füllt sie als Werkzeug-Argumente** — kein Klassifikator im Hybrid |

`hybrid` ist das Übergangsfahrzeug: gegen *beide* Bestandsmaschinen mit derselben
Golden-Suite messbar. Gewinnt es, kann `pattern` später stillgelegt werden.

## 3. Was gebaut wurde

| Paket | Inhalt |
|---|---|
| **H1** | `hybrid` als dritter Wert: `engine_choice` (`HYBRID`, `_ERLAUBT`), `config_models/engine.py` (`Literal`), Seed-Kommentar. Vorgabe bleibt `pattern`. |
| **H2** | **Neu `domain/pattern_catalog.py`** (127 Z.): `waehlbare_muster` / `finde_muster` / `katalog_text`. `agent_tools.waehle_vorgehen_tool` — **ein** Werkzeug mit `enum` statt 20 Einzelwerkzeugen. |
| **H3** | Dispatch in `agent_loop.py` an der Stelle von `submit_result`: Body als `role:"tool"`, aktives Muster vermerkt, **ohne** Fremdtext-Rahmen (Eigen-Inhalt). |
| **H4** | Werkzeugliste wechselt **im Moment der Wahl** (`werkzeuge_fuer`-Rückruf) statt einmal pro Zug. |
| **H5** | Vorabruf ohne Klassifikator: `_looks_like_search_query` (existierte bereits) tritt an die Stelle von `intent_id ∈ {I03,I04}`. |
| **H6** | `laeuft_ueber_die_schleife()` an vier Knoten; `hybrid_pattern()`; Safety-erzwungenes Muster nimmt den Katalog weg; `effective_pattern_id` trägt das ausgeführte Muster. |
| **H7** | fällt mit H6 zusammen — `effective_pattern_id` ist die Muster-Spalte der Qualitätslogs. |

**Gesperrt, hart:** M01/M02 (Safety-erzwungen), M03 (Klärungs-Mechanik), M15
(Rückfall-Anker) stehen **nicht** im Katalog. Die Sperre greift zweimal: nicht im
`enum` *und* `finde_muster` weist sie zurück — Werkzeug-Argumente sind
Modell-Ausgabe und damit unvertraute Eingabe.

## 4. Der Fund, den erst die Live-Probe zeigte

Der erste Hybrid-Lauf lieferte **0 Karten**, obwohl das Protokoll „8 Karten"
erntete. Ursache im Log wörtlich:

```
turn_assembly: Cards unterdrückt — kein konkretes Thema/Fach im Slot (pattern=HYBRID)
```

Der Filter schließt von „kein Slot" auf „die Suche lief ohne Thema". Im Bestand
stimmt das. In den Schleifen-Maschinen nicht: dort wählt das **Modell**
Suchbegriff und Filter selbst und übergibt sie als Werkzeug-Argumente — gemessen
`search_wlo_content(query='Optik', educationalContext=…, discipline=…)`. Die Slots
sind leer, die Suche hatte sehr wohl ein Thema.

**`agent` kam bisher nur zufällig durch:** sein Modell greift meist zu
`search_wlo_all`, dessen Themenseiten-Karten die Ausnahme darüber treffen. Wählt
es `search_wlo_content`, fielen die Karten genauso weg — ein Verhalten, das nur
aus der Werkzeugwahl eines Laufs folgt, ist geliehen und nicht zugesichert.
Beide Maschinen sind jetzt ausgenommen, mit drei Tests (Bestandsweg unverändert,
Schleifen-Maschinen behalten ihre Karten).

## 5. Verifikation

```
pytest -q      3760 passed, 1 failed, 4 skipped   (Fehlschlag = test_auth, vorbestehend)
ruff check .   All checks passed!
openapi        contract unchanged
```

Live gegen den lokalen Backend (Port 8100), dieselbe Frage durch alle drei Maschinen:

| Maschine | Zeit | Muster | Intent | Werkzeuge | Karten |
|---|---|---|---|---|---|
| `pattern` | 12,5 s | M06 | I03 (klassifiziert) | 3× Prefetch + `select_top_cards` | 7 |
| `agent` | 14,7 s | AGENT | I01 (Ersatz) | `search_wlo_all` | 7 |
| `hybrid` | 15,2 s | **M05** | I01 (Ersatz) | `lookup_wlo_vocabulary` ×2, `search_wlo_content` | 3 |

Protokollzeilen des Hybrid-Zuges:

```
agent_loop:    Hybrid: Vorgehen M05 (Material-Suche gefiltert) gewaehlt — 5 Werkzeuge
respond_agent: Agent-Modus: 4 Schritte, Ende=text, 3 Werkzeuge, 8 Karten
respond_agent: Hybrid: ausgefuehrtes Muster M05 (Material-Suche gefiltert) statt HYBRID
```

Damit ist belegt: **kein Klassifikator** (Intent I01 = Ersatzform), das **Modell
wählte das Muster** (M05), die **Werkzeugliste wechselte** auf M05s fünf, und das
**ausgeführte Muster** steht in `effective_pattern_id`.

## 6. Ehrliche Grenzen

* **Tempo ist nicht belegt.** Drei Einzelzüge sind keine Messung; `hybrid` war in
  dieser Stichprobe sogar am langsamsten. Der A/B-Lauf über die Golden-Suite
  (`EVAL_CHAT_HEADERS='{"X-Boerdi-Engine":"hybrid"}'`) steht aus — er gehört dem
  Nutzer und ist der eigentliche Beleg für Ziel 1.
* **H5 zurückgenommen (Review-Befund 2, 2026-08-22).** Das Hybrid-Gate startete
  den spekulativen Vorabruf, aber die Verbrauchsseite wurde nie gebaut:
  `respond_agent._verwirf_vorabruf` bricht `spec_task` unbedingt ab, für agent
  UND hybrid — jeder such-artige Hybrid-Zug bezahlte einen verworfenen
  MCP-Roundtrip (die Live-Probe in §5 zeigt entsprechend keinen Prefetch).
  Der Hybrid startet jetzt KEINEN Vorabruf; das Tempo-Ziel auf Such-Zügen
  bleibt damit offen. Nachrüstweg: Einspeisung in die Schleife (Fremdtext-
  Rahmen + Karten-Ernte + `tools_called`-Annotation), dann das Gate zurück.
* **Slot-Degradation, M03-Rückfrage und Filter-Injektion entfallen im Hybrid** —
  Entscheidung des Nutzers. Nachrüstweg wäre ein kleiner Slot-Klassifikator (nur
  Entities, ~1/10 des heutigen Prompts).
* **M09/M10-Schnellwege sind im Hybrid aus.** Die Muster stehen im Katalog, laufen
  aber über die Schleife statt über ihre ~750 Zeilen Python.
* **Die Werkzeugbeschreibung teilt sich den Renderer NICHT** mit
  `classify_prompt_blocks._render_patterns_hint_block`: jenes Modul trägt die
  Zusage „byte-identisch zu ALT". Geteilt wird die *Konvention* (Aufbau,
  Fünfer-Deckel), nicht der Code — Begründung im Kopf von `pattern_catalog.py`.
* **`agent_pattern`-Ereignis ohne Widget-Empfänger.** Die Phasen-Karte des Widgets
  ist eine Erlaubnisliste; `agent_pattern` steht nicht darin. Kein Schaden (das
  Etikett der laufenden Iteration bleibt stehen und ist wahr), aber wer es
  anzeigen will, braucht eine Frontend-Änderung samt Bundle-Neubau.
* **Test-Reihenfolge:** H1–H5 sind test-first entstanden (Rot belegt), H6 wurde
  implementiert und danach abgesichert; dort tragen die Zusicherungen paarweise
  (Katalog da / Katalog weg bei Safety-Zwang), sodass ein fehlender Zweig
  mindestens eine von beiden fallen lässt.

## 7. Nutzer-Domäne

Commit, Docker-Build, Deploy, Seed-Import (damit `hybrid` im Studio wählbar ist)
und alle Golden-/Eval-Läufe. **Kein Frontend-Code berührt ⇒ kein
Widget-Bundle-Neubau nötig.**

---

## 8. H8 — Die Deckel greifen richtig, aber am falschen Verbrauch (2026-08-17)

Ausgelöst durch einen Live-Abbruch: „Ich bin damit nicht fertig geworden" nach
**3 von 12 Schritten und 10 von 90 Sekunden** — `Ende=token_budget`. Nutzer-Frage:
zählen die Deckel je Antwort, und was ist mit dem Gesprächsverlauf?

### 8a. Prüfung: ja, alle drei Deckel gelten je Antwort

| Deckel | Nullpunkt | Beleg |
|---|---|---|
| `max_iterations` | `AgentRun()` je Aufruf, `for _ in range(...)` | `agent_loop.py:234/246` |
| `deadline_s` | `start = clock()` bei Eintritt | `agent_loop.py:239/247` |
| `token_budget` | `start_tokens = _spent(acc)` als **Nullpunkt**, nicht Zählerstand | `agent_loop.py:243/250` |

Der Zähler selbst (`ctx.usage`) entsteht per `default_factory=new_accumulator`
je `TurnContext` (`graph/state.py:100`), also je Zug. **Nichts läuft über Züge
hinweg** — die Anforderung „je Antwort" ist erfüllt, ohne Änderung.

### 8b. Wohin die 60 000 Token wirklich gehen (gemessen)

| Teil des Prompts | Zeichen | ~Token |
|---|---|---|
| Systemprompt | 450 | 112 |
| Werkzeugsatz vor der Musterwahl (28 Werkzeuge) | 55 931 | ~14 000 |
| Werkzeugsatz **nach** `waehle_vorgehen('M05')` (6 Werkzeuge) | 31 742 | ~7 900 |
| davon `waehle_vorgehen` **allein** | **25 251 (80 %)** | **~6 300** |
| Muster-Body in der Kette (Median / Maximum M10) | 2 924 / 7 382 | 730 / 1 850 |
| ein Suchergebnis (`search_wlo_content`, gemessen) | 12 339 | ~3 100 |

Gemessener Lauf: **45 930 Prompt-Token für 3 Runden** — also ~15 300 je Runde,
und der Werkzeugsatz ist davon der größte Posten. Der Katalog wird **jede Runde
neu mitgeschickt**, auch nachdem das Modell längst gewählt hat: `waehle_vorgehen`
steht in `VIRTUELLE_WERKZEUGE` und bleibt darum in jeder eingeschränkten Liste.
Nach der Wahl braucht das Modell aber nur noch *wechseln* können — dafür genügen
Kennung, Etikett und Zweck.

### 8c. Der Gesprächsverlauf ist gedeckelt, aber nur nach ANZAHL

`respond_agent.py:225` nimmt `ctx.history[-10:]` wörtlich. Über 490 gespeicherte
Nachrichten gemessen: Median **95** Zeichen, p95 **3 904**, Maximum **8 190**.
Typisch ist der Verlauf also leicht (~250 Token je Nachricht), im Randfall aber
10 × 8 190 Zeichen ≈ **20 500 Token** — ein Drittel des Budgets, bevor der Lauf
arbeitet. Ein Zeichen-Deckel fehlt.

### 8d. Änderungen

| # | Änderung | Erwartung |
|---|---|---|
| H8-1 | `token_budget: 60000 → 120000` (Seed + lokaler Stand) | Deckel ist wieder `max_iterations`, nicht das Budget |
| H8-2 | Kurzkatalog **nach** der Wahl: `katalog_kurz()`, `waehle_vorgehen_tool(..., kurz=True)`, gesetzt im `werkzeuge_fuer`-Rückruf | ~6 300 Token je Runde ab Runde 2 |
| H8-3 | Verlaufs-Deckel je Nachricht **und** über den ganzen Verlauf, mit sichtbarem Kürzungs-Hinweis | Randfall 20 500 → ~2 500 Token |

**Bewusst nicht gebaut:** Verdichtung der *Werkzeug-Ergebnisse* in der Kette.
Nach H8-1 + H8-2 ist sie nicht der bindende Deckel (10 Runden mit 8 Suchen
rechnen sich auf ~55 000 von 120 000), und das Kürzen älterer Treffer kann die
Antwort verschlechtern — eine Qualitätsfrage, die eine Messung braucht und keine
Vermutung.

**Nicht konfigurierbar gemacht:** die Verlaufs-Deckel sind Modul-Konstanten, keine
Studio-Felder. `token_budget` ist der Kosten-Knopf des Betriebs; wie viele Zeichen
einer alten Antwort in den Prompt gehören, ist Prompt-Hygiene und keine
redaktionelle Entscheidung. Ein Studio-Feld dafür bleibt jederzeit nachrüstbar.

### 8e. Gemessene Wirkung (live, derselbe Satz, frische Sitzung)

„Material zur Optik für Klasse 8", beide Male Muster M05:

| | vorher | nachher |
|---|---|---|
| Prompt-Token der Schleife | 45 930 | **38 928** |
| LLM-Runden | 3 | **4** |
| **je Runde** | 15 310 | **9 732 (−36 %)** |
| Ende | `token_budget` möglich | voller Text, 3 Karten |

Mehr Runden für weniger Token — die Ersparnis steckt nicht in weniger Arbeit,
sondern im nicht mehr wiederholten Katalog.

Der Verlaufs-Deckel, live gegen eine Sitzung mit einer 8 190-Zeichen-Antwort:

```
Verlauf gedeckelt: 6 von 6 Nachrichten, 4561 von 8718 Zeichen
```

Keine Nachricht fiel weg, nur gekürzt — und die Antwort auf „Fasse in einem Satz
zusammen, worum es hier ging" blieb richtig („Planung einer 45-minütigen
Einführungsstunde zur Optik"). Genau der Fall, den der Deckel nicht kaputt machen
durfte.

### 8f. Ehrliche Grenzen von H8

* **Je eine Messung.** Ein Zug vorher, ein Zug nachher, ein Verlaufs-Fall. Die
  −36 % sind an *diesem* Satz und *diesem* Muster gemessen; ein M04-Zug ohne
  Werkzeuge spart nichts, weil er nie ein zweites Mal fragt.
* **Der A/B-Lauf zählt.** Ob die Kurzfassung die *Qualität* der Musterwechsel
  hält, sagt die Golden-Suite und nicht ein Einzelzug — insbesondere den Fall
  „Suche leer → M12", der jetzt aus einer Ein-Zeilen-Beschreibung heraus fallen
  muss.
* **Der Verlaufs-Deckel gilt nur in der Schleife**, nicht im Bestandsweg
  (Begründung an ``_HISTORY_TURNS`` in ``respond_agent.py``). Der A/B-Vergleich
  vergleicht damit zwei Maschinen, die ihren Verlauf verschieden behandeln.
* **Die Deckel sind unverändert je Antwort** — an der Zählweise war nichts zu
  reparieren, nur am Verbrauch.
