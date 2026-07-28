# P3-2 Structured Classify — Portierungs-Vertrag (ALT → instructor)

> Erhoben 2026-07-11 gegen `badboerdi/backend/app/services/{llm_service,llm_classify_prompt}.py`.
> Ziel: `services/classify.py` (Orchestrierung) + `services/classify_prompt.py` (Prompt/Tool-Assembly).
> Baut auf `services/llm.py` (route/Transport), `obs/usage.py` (Usage), Loader-Fassade (Config),
> `boerdi.api.schemas.ClassificationResult` (Modell existiert bereits). instructor-API verifiziert:
> `from_litellm(litellm.acompletion, mode=Mode.TOOLS)` → AsyncInstructor; `create_with_completion`
> liefert `(model, raw_completion)` für Usage; `InstructorRetryException` für Fallback.

## 1. `classify_input` — Signatur + Fluss (llm_service.py:76-136)
```python
async def classify_input(message, history, session_state, environment,
                         canvas_state=None, usage_acc=None) -> ClassificationResult
```
- `system = _build_classify_system_prompt(session_state, environment, canvas_state)`; `classify_tool = _build_classify_tool()`.
- messages = `[{"role":"system","content":system}]` + `history[-10:]` (**Cap 10, bestätigt**) + `{"role":"user","content":message}`. System immer erster, User-Message immer letzter.
- Call: `create(**build_chat_kwargs(model=MODEL, messages, tools=[classify_tool],
  tool_choice={"type":"function","function":{"name":"classify_input"}}, temperature=0.1))` — **forcierter Tool-Choice**.
- Usage: `add_usage(usage_acc, extract_usage(resp), phase="classify")`.
- Parse: `raw = json.loads(resp.choices[0].message.tool_calls[0].function.arguments)` → `ClassificationResult.model_validate(raw)`.
- Deterministische Post-Overrides sind **entfernt** (Welle E v4+12) — kein Post-Processing nötig.

## 2. Mechanismus mit instructor (NEU)
- `client = instructor.from_litellm(litellm.acompletion, mode=Mode.TOOLS)` (Modul-Singleton).
- Patchbares Boundary: `_acreate = client.chat.completions.create_with_completion` (Tests faken es).
- Call: `result, raw = await _acreate(model=<routed>, messages=messages,
  response_model=ClassificationResult, api_base=..., api_key=..., timeout=..., num_retries=2,
  temperature=0.1, max_retries=1, extra_headers=<b-api>)`. Routing via `llm.route(get_chat_model())`.
- Usage aus `raw` (create_with_completion): `add_usage(usage_acc, extract_usage(raw), "classify")`.
- **Wichtige instructor-Nuance:** `Mode.TOOLS` generiert das Tool AUS `ClassificationResult` — es trägt
  NICHT ALTs config-getriebene Enum-Constraints (persona/intent/state-IDs) noch die Rich-Descriptions.
  Da `ClassificationResult` KEINE Enum-Validatoren hat, würden ungültige IDs durchvalidieren. ALT
  verließ sich auf die Tool-Enums. **Erhaltung:** Der System-Prompt zählt ohnehin alle Personas/Intents/
  States/Entities/Patterns auf (§3) — das trägt die Constraints als Prompt-Guidance. (Optional härter:
  eigenes Tool mit `json_schema_extra`-Enums; für Parität nicht nötig, Prompt reicht wie in ALT-Praxis.)
- Instructor's `Mode.TOOLS` = forcierter Named-Tool-Choice intern → matcht ALTs `tool_choice`.

## 3. Prompt-Assembly (`_build_classify_system_prompt`, llm_classify_prompt.py:688-820)
Config via Fassade: `load_intents/load_states/load_entities/load_persona_definitions/
load_pattern_definitions/load_classify_overrides_config`. **Signals: aus ROH-YAML** `area("04-signals/
signal-modulations")["signals"]` (nicht `load_signal_modulations` — die Fassade STRIPPT das
`dimension`-Feld, bestätigt test_config_loader_classification.py:40-51).

Reihenfolge: `header + _static_block + override_block + pattern_disambig_block + fewshot_block + _dynamic_block`
(dynamic ZULETZT für max. Prompt-Cache auf dem langen statischen Prefix).
- **header:** "Du bist der Klassifikations-Modul des WLO-Chatbots.\nAnalysiere … Persona, Intent, Signale, State, Entities. Optional: Pattern-Hint + Tool-Hint.\n"
- **_static_block:** Sektionen in Reihenfolge: `## Personas (WICHTIG: Genau zuordnen!)` + personas_block,
  `## Intents` + intents_block, `## Signale` + signals_block, `## States` + states_block, `## Entities`
  + entities_block, `## Patterns (Hint-Feld, optional)` + patterns_block, dann `"\nRufe classify_input auf mit den erkannten Werten."`
- **_dynamic_block:** `## Aktueller Turn-Kontext` mit State, bekannte Entities (json), Persona-Zeile (nur
  wenn session_state.persona_id gesetzt), Turn-Nr, Seite, Seitenkontext-Rohdaten (whitelisted keys),
  Device, canvas_prompt, _page_block (page_context_service, best-effort/swallowed).

### Renderer (was jeder injiziert) — Marker die Tests pinnen fett
- **personas** (:223-334): Head mit HARD-OVERRIDE-Regel ("Explizite Selbst-ID dominiert IMMER"); pro
  Persona `### {id} — {label}`, description, `Positiv-Marker: "…"` (positive_markers|hints),
  `Anti-Marker (NICHT diese Persona): "…" → redirect`, `Diskriminatoren: vs. {id}: {rule}`.
- **intents** (:337-433): `Intent-Übersicht: {id (label), …}` + Regel-Head (Negativ>Positiv, edit-verb+
  canvas→I06); pro Intent `### {id} — {label}`, description, `Trigger-Verben`, `Negativ-Trigger: - "phrase" → target (wenn when) — rationale`, `Diskriminatoren`, `Beispiele`.
- **signals** (:627-644): aus ROH-YAML; gruppiert IDs nach `dimension` → `"{dim}: {id, id}"`. **Pin: "D1-Zeit:"**.
- **states** (:436-471): Regel-Head (Slot komplett→S3, fehlt→S2, kein Anliegen→S1) + pro State `- {id} ({label})`, description, `Wahl-Kriterien` (selection_criteria).
- **entities** (:474-539): Regel-Head (Slots leer lassen wenn nicht eigenständig) + pro Entity `- {id}: {desc}`, `Positiv-Beispiele: "text" → value`, `Negativ-Beispiele (Slot bleibt leer)`, `Diskriminator vs. {vs}: {rule}`.
- **patterns_hint** (:542-624): Head deklariert pattern_id_hint als PRIMARY-Selektor (nicht Telemetrie),
  M15-Fallback wenn leer; pro Pattern `### {id} — {label}`, `_Zweck:_`, `**Einsetzen wenn:**`,
  `**NICHT einsetzen wenn:**`, `**Typische User-Phrasen:**`, `**Tie-Breaks:**`.
- **classify_overrides** (:823-909): `## HARD-OVERRIDE-REGELN`, `### Persona-Override` (triggers/
  requires_all/requires_any→persona, except_explicit_role), `### Intent-Override`, `**Konflikt-Regel:**`
  (intent_conflict_rule), `### Topic-Slot-Override` (phantom_topic_phrases, fach_as_topic_fallback).
- **fewshot** (:933-950): `## FEW-SHOT-BEISPIELE (User → erwartetes Pattern)` + nummeriert `"{input}" → {intent}, {pattern} ({note})`.

## 4. Tool-Schema (`_build_classify_tool`, llm_classify_prompt.py:20-189)
`{"type":"function","function":{"name":"classify_input","description":…,"parameters":{…}}}`.
Properties: persona_id(enum=persona_ids), persona_confidence(number), intent_id(enum=intent_ids),
intent_confidence, signals(array[str]), entities(object, props je entity-id), turn_type(enum:
initial/follow_up/clarification/correction/topic_switch), next_state(enum=state_ids),
pattern_id_hint(enum=pattern_ids, optional), pattern_reasoning, tool_id_hint(enum=tool_hint_ids,
optional), tool_reasoning. **required = die 8 Kernfelder** (persona_id, persona_confidence, intent_id,
intent_confidence, signals, entities, turn_type, next_state); die 4 Hint-Felder optional. Enums
config-getrieben; tool_hint_ids = Union aller Pattern-`tools:`-Frontmatter.
> Bei instructor Mode.TOOLS wird das Tool aus dem Pydantic-Modell generiert → Enums NICHT automatisch.
> Für Parität: Prompt trägt die IDs (§3). Optional eigenes Tool bauen wenn harte Enums gewünscht.

## 5. Fallback (2 Layer)
- **Schema-Defaults** (ClassificationResult, existiert bereits): persona_id="P-AND", persona_confidence=0.8,
  intent_id="I03", intent_confidence=0.8, signals=[], entities={}, turn_type="initial", next_state="S1",
  4 Hints=None. Keine Enum-Validatoren → plain str.
- **Layer A (in classify_input, llm_service.py:129-136):** bei ValidationError:
  `ClassificationResult.model_construct(**{k:v for k,v in raw.items() if k in ClassificationResult.model_fields})`
  (gültige Teilmenge behalten, Rest = Schema-Defaults).
- **Layer B (Caller, chat_pipeline_phases.py:124-133, gehört zu P4):** wenn der ganze Task wirft
  (Netz/Timeout, in `asyncio.gather(..., return_exceptions=True)`):
  `ClassificationResult(persona_id=session_state.get("persona_id") or "P-AND", intent_id="I01",
  intent_confidence=0.0, next_state=session_state.get("state_id") or "S1")`. **Abweichung:** Layer B
  nutzt intent_id="I01"/confidence=0.0 + sticky persona/state (NICHT Schema-Default I03/0.8).

## 6. Tests (ALT-Mock-Muster → NEU portieren)
- **test_classify_input.py** (3): `_FakeClient.chat.completions.create` → `_FakeResp` mit
  `choices[0].message.tool_calls[0].function.arguments = json.dumps(args)`; `monkeypatch.setattr(ls,"client",fake)`.
  Pins: Tool-Args→Felder; leere `{}`→Defaults; ungültiges Feld→ValidationError→model_construct behält gültige.
- **test_llm_service_generators.py** (classify :153-193): Cap-10+Reihenfolge (12-msg→len 12, [0]=system,
  [1:11]=history[2:], [-1]=user); forcierter classify-Tool + tool_choice; usage_acc per_phase={"classify":…}.
- **test_llm_classify_prompt.py** (5, pure): tool type/name/parameters; signals `"D1-Zeit:"`; Blöcke non-empty.
- **test_config_loader_classification.py**: load_classify_overrides_config Defaults; **load_signal_modulations
  DROPPT dimension** (→ Signals-Block aus Roh-YAML!); get_state_directive.

**NEU-Boundary:** `classify._acreate` (= AsyncInstructor.create_with_completion) patchbar; Tests faken es
mit einem Callable, das `(ClassificationResult(...), raw_with_usage)` zurückgibt bzw. `InstructorRetryException`
wirft → Layer-A-Fallback. Prompt-Renderer separat gegen echte Config testen (Marker "D1-Zeit:", non-empty).

## 7. UMGESETZT (2026-07-11) — Abweichungen vom Vor-Entwurf oben
- **`_build_classify_tool` NICHT portiert.** Spec §3-2 + Tech-Tabelle mandatieren instructor
  (`from_litellm` → ClassificationResult) als bewusste Verbesserung; instructor generiert das Tool aus dem
  Modell → ALTs config-Enums/Beschreibungen entfallen. **Erhalten:** der System-Prompt zählt alle IDs auf
  (§3). Offener Follow-up: persona_confidence-„<0.6"-Guidance lebte nur in ALTs Tool-Description → könnte
  via `Field(description=…)` an ClassificationResult zurückgeholt werden (P0-Schema, bewusst NICHT in 3-2).
- **GPT-5-Gating wiederverwendet statt dupliziert.** `llm.build_chat_kwargs` wird mit einem
  `_TOOL_GATING_MARKER` (Platzhalter-Tool) aufgerufen, damit der *Tool-Call*-Zweig greift (kein
  reasoning_effort, verbosity), dann werden `messages`/`tools` gestrippt und Routing/timeout/num_retries=2
  überlagert — bit-gleich zu `chat_completion`. instructor spritzt sein eigenes Tool ein.
- **`max_retries=2`** (eine Validierungs-Wiederholung) realisiert die von der Tech-Tabelle genannte
  „Validierungs-Retries"-Verbesserung; Common-Path == ALT-Single-Shot (Retry feuert nur bei
  Malformed-Output). Netz-Retries `num_retries=2` bleiben orthogonal (wie ALT SDK-Default).
- **Layer-A treu:** `InstructorRetryException.last_completion` → Tool-Args → `model_construct`(gültige
  Teilmenge); nicht extrahierbar → Schema-Defaults. `_extract_tool_args` fängt AttributeError/IndexError/
  TypeError/JSON-Fehler → Defaults (kein Crash).
- **Bulkhead geteilt:** neuer öffentlicher `llm.semaphore(background=False)`-Wrapper; classify läuft
  `async with _llm.semaphore()` → gleicher Per-Loop-Limit wie chat_completion.
- **`simplify:`** page_context_service-Block + tiktoken-Prompt-Size-Histogramm ausgelassen (eigenes
  späteres Paket bzw. Nicht-Verhaltens-Telemetrie); Roh-`_raw_pc`-Whitelist bleibt, Seam markiert.
- **Dateien:** `services/classify_prompt_blocks.py` (5 Dim-Renderer, 357 Z.), `services/classify_prompt.py`
  (Assembly + Signals/Canvas/Overrides, 298 Z.), `services/classify.py` (Orchestrierung, 132 Z.).
  Tests: `test_classify_prompt.py` (22, pure + min-store + ALT-Baum-Pin „D1-Zeit:"), `test_classify.py`
  (10, `_acreate`-Fake). Suite **241 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert.
