# boerdi-chat — Neubau-Blaupause v2 (verbindlicher Bauplan)

> **KANONISCHE FASSUNG** (dieses Repo). Ersetzt die v1-Blaupause
> `../badboerdi/docs/plans/2026-07-08-neubau-blaupause.md`; eine eingefrorene Kopie dieser v2
> liegt auch dort. Änderungen an der Spec passieren NUR HIER.
> Erstellt 2026-07-10 nach vollständiger Code-Re-Inventur (3 Explore-Läufe: Backend-Endpoints/
> Env/Config, Widget-Embed-Vertrag, Studio-Views) + Lizenz-Verifikation der Kernbausteine.
> **Zielordner:** `C:\Users\jan\staging\Windsurf\wlo-suche\boerdi-chat\` (dieses Repo/Monorepo).
> **Referenz-Codebasis (ALT):** `…\wlo-suche\badboerdi\` — Stand 2026-07-10, Suiten grün:
> Backend 1849 · Widget 167 · Studio 11 · (extern: wlo-mcp-server 96). Umfang heute:
> Backend-App 38,3k LOC + 21,1k Test-LOC · Widget 9,3k · Studio 14k · 55 Config-Dateien.
>
> **Für die Implementierung gilt:** Jede Session beginnt mit `/better-coding-workflow`
> (UI-Pakete zusätzlich `/better-coding-frontend`); Abnahme je Paket mit `/better-coding-verify`.
> Dieses Dokument ist die Spec — bei Abweichungen zuerst HIER ändern, dann Code.
>
> ## ⏱ Umsetzungs-Status (nach jedem Paket hier nachführen!)
> | Paket | Status | Abnahme-Beleg |
> |---|---|---|
> | P0 Fundament & Verträge | ✅ 2026-07-11 | 65 pytest grün, ruff clean; OpenAPI-Vertrag 108 Routen eingefroren (`scripts/export_openapi.py --check` grün); Lizenz-Gate aktiv (LGPL-Fund psycopg → dokumentierte Ausnahme §0.1); Compose-Dev live verifiziert (/health ok, pgvector aktiv, Jaeger 200); Golden-Runner-Smoke GS-1 gegen ALT 18/19 hart (`evals/reports/golden-20260710-223550-smoke-alt.json`). Offen (Nutzer): git init/Commit, CI-Lauf auf GitHub, voller 12-Flow-Referenzlauf |
> | P1 Backend-Kern | ✅ 2026-07-11 | Suite 108 grün (inkl. Live-PG: Migration-0001-Introspektion, Advisory-Lock-Serialisierung, NOTIFY-Kette; Live-Jaeger: /health-Trace via Query-API belegt); Auth-Port fail-closed + 401/403-Matrix, Security-Header, CORS-Credentials-Regel; slowapi-Limit V7 default an (TRUST_FORWARDED_FOR-Semantik getestet); /api/health + Modell-Auflösungskette; Dev-DB auf head; CI + PG/Jaeger-Services; OpenAPI-Diff nur `/`-Redirect (bewusst neu eingefroren) |
> | P2 Config-Subsystem | ✅ 2026-07-11 | Alle 8 Tasks: 2-1 Modelle (35 Areas, alle 55 ALT-Dateien validieren) · 2-2 config_store (Version+History transaktional, **write-through Cache** + refetch-overwrite-NOTIFY, delete) · 2-3 Loader-Fassade (53 Fn, Surface-Test 58 grün gegen ALT-Baum; Writes async) · 2-4 seed_io + CLI (55 Areas real importiert; YAML-1.1-`off:`-Bool-Key→"false") · 2-5 typisierte GET/PUT (privacy/tone/welcome/context/canvas + intents/states/personas/patterns/entities + file-CRUD + elements-Browser + mcp-GET; jsonb-nativ statt YAML-Text, Validierungs-Codes 400/422 wie ALT; mcp-PUT/discover→P5/P6) · 2-6 schema/{area} (alle 35) · 2-7 Snapshots/Backup/Factory (ZIP-Blobs in config_snapshots, Zip-Bomben-Cap `_copy_zip_member_capped` 600 MB Budget portiert + getestet; DB-Include→P10, builder-Rolle→P9) · 2-8 guide-mode-Bundle. **Suite 224 grün** (inkl. Live-App-Smoke: DB→Store→Fassade→API liefert echte 16 Patterns/6 Personas; backup 78-KB-ZIP). OpenAPI-Vertrag 3× bewusst nachgezogen (18 Config-Routen mit echten Modellen) |
> | P3 LLM/Klassifikation/Safety | ✅ 3-1 ✅ · 3-2 ✅ · 3-3 (reasoning+QR+3-3a Prompt-Builder) ✅ · 3-3b _select_active_tools ✅ · 3-4 Safety ✅ · 3-5-Writer ✅ (R3b 2026-07-18; Aufruf+Gate im Persist = P4-6/R4) | **3-1 ✅** `obs/usage.py` (Usage-Extraktion+Akkumulator, 7 T) + `services/llm.py` (LiteLLM-Transport: `build_chat_kwargs`-GPT-5-Gating, Provider-Routing openai/b-api-openai/b-api-academiccloud + api_base + X-API-KEY-Dual-Auth, per-Loop-Semaphore-Bulkhead + öffentl. `semaphore()`-Wrapper, `num_retries=2`, Usage-Hook, `litellm.drop_params=True`; 17 T, `_acompletion`-Fake). Vertrag `docs/plans/p3-llm-transport-contract.md`. Simplify: `_shape_max_tokens` weg (drop_params). **3-2 Classify ✅** `services/classify.py` (instructor `from_litellm`→ClassificationResult, `create_with_completion`-`_acreate`-Boundary; messages=[system]+history[-10:]+[user]; GPT-5-Gating via `build_chat_kwargs`+Tool-Marker-Strip; Routing+timeout+`num_retries=2`+geteilter Bulkhead; `max_retries=2`=Validierungs-Retry [Spec-Verbesserung]; Layer-A-Salvage `model_construct` aus `InstructorRetryException.last_completion`) + `services/classify_prompt{,_blocks}.py` (System-Prompt-Renderer 1:1 aus ALT `llm_classify_prompt.py`; `_build_classify_tool` NICHT portiert [instructor auto-gen, IDs via Prompt]; Signals aus ROH-`area()` wegen `dimension`; page_context+tiktoken-Histogramm simplify-deferred). 32 T inkl. ALT-Baum-Pin „D1-Zeit:". Vertrag+Umsetzungsnotiz `docs/plans/p3-classify-contract.md` §7. **3-3-Teil ✅** `domain/reasoning_filters.py` (`strip_reasoning_markers` + `ThinkSafeStreamer` Holdback-Guard; 13 T). **3-3 QR-Gen ✅** `services/quick_replies_llm.py` (`generate_quick_replies` 1:1 aus ALT `llm_quick_replies.py`: Capability-Hints didaktisch/analytisch, `{thema}`/`{fach}`-Fill, Parse/Dedup/Cap, best-effort→`[]`; Transport via `llm.chat_completion` phase="quick_replies"; `_analytical_personas` liest `load_canvas_persona_priorities` [Default P-ENT/P-RED]; page-context simplify-deferred; verbatim-Prompt → per-file `E501`-ignore in pyproject). 13 T (`_acompletion`-Fake). **3-3a Response-Prompt-Builder ✅** `_build_system_prompt` (P1-P9) 1:1 aus ALT `llm_prompt_builder.py:40-880`, Split in 4 Module (`response_prompt_{builder,pattern,display_blocks,tools_text}.py`): Orchestrator hält `if/append`-Kontrolllogik → `system_parts`-Struktur byte-identisch; `render_pattern_layer` + `_formality_guidance`/`_render_pattern_brief` aus ALT `llm_classify_prompt.py:953-1111` mitportiert; `_get_state_meta_safe` try/except→{}. Deviations: P3 page_context + P9 `_log_system_prompt_size` simplify-deferred, 3 tote Locals (`_pattern_id_for_m11`/`has_rag_tools`/`mode`) nicht portiert (F841), 3× E501-per-file-ignore (verbatim Prompt). 24 T (Layer-Order, State/unbekannt, M11-8000-Cap, card-Modi, Inline-Grouping/KEIN-Suche/Inline-Link + Interior-Pins, Degradation+Tool-Lock, Session-100-Char-Cap, Flags). Vertrag+Umsetzungsnotiz `docs/plans/p3-response-prompt-contract.md` §9. Suite **278 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **3-3b _select_active_tools ✅ (2026-07-11)** `services/response_tool_selection.py` — 1:1-Port ALT `llm_prompt_builder.py:883-1219` (P10-P11: Tool-Wahl [pattern.tools / [] / mcp-Source / Fallback] → medientyp-Strip [collections+topic_pages+all raus, `search_wlo_content` garantiert] → RAG-Sources-Gate [`sources is None or "rag" in sources`] + `query_knowledge`-vorn → `select_top_cards` [ENV `CHAT_DISABLE_SELECT_TOP_CARDS`, Inline- vs. Re-Rank-Beschreibung] → Degradation-Wipe → `respond_to_user`-hinten [ENV `CHAT_INLINE_QUICK_REPLIES`]). Entsperrt durch 5-2 `TOOL_DEFINITIONS`. **Eigenes Modul** (Contract §8.4) statt in `response_prompt_builder` — Tool-LISTE ≠ Prompt-TEXT; ~340 Z./1 Verantwortung (bewusst >300, verbatim Prompt-Bytes wie `display_blocks`). **Deviation NUR Import-Root** (`mcp_client`→`mcp.tool_defs`, kein Facade); Funktions-Rumpf **byte-identisch** → E501-per-file-ignore (verbatim Tool-Descriptions, wie Geschwister). **Verifikation:** AST-Diff `_select_active_tools`-Body ALT↔NEU = **IDENTISCH, 0 Divergenz**. **ALT-Test war Integration** (`test_active_tools_selection.py` via `generate_response`; Harness [Tool-Loop/P4-P6] noch nicht gebaut) → Contract §5 sanktioniert **direkte Unit-Tests**: 22 T gegen die §6-Marker (4 Basis-Zweige · medientyp strip/keep/add-content · RAG allowed/blocked/none + query_knowledge-enum · select_top_cards default/disabled/asymmetrisch-„yes"/Inline+Re-Rank-Desc · Degradation-Wipe + respond-danach · respond default/last/„yes" · Rückgabe-Tupel). Autouse-Fixture snapshottet `TOOL_DEFINITIONS` (Determinismus). **Latenter ALT-Quirk verbatim übernommen + geflaggt (NICHT gefixt, Scope-Control §13):** mcp-Zweig `active_tools = TOOL_DEFINITIONS` (Referenz) → bei bare-mcp + kein-RAG + select-on mutiert das spätere `.append` das Modul-Global (Regel-3-Smell); `simplify:`-Marker im Docstring → `list(TOOL_DEFINITIONS)` sobald Nutzer die bewusste Verbesserung freigibt (Rückgabe provable unverändert). Suite **529 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **3-3 damit KOMPLETT** (reasoning_filters + QR + 3-3a Prompt-Builder + 3-3b Tool-Selection); **P3 Services komplett — 3-5-Writer ✅ R3b 2026-07-18** (Logging-Aufruf+Gate im Persist = P4-6/R4). **3-4 Safety ✅** Paket `services/safety/{regex_gate,moderation,legal,service}.py` — ALT `safety_service.py` (467 Z., 1 Modul) nach Verantwortung gesplittet: `regex_gate` (alle Regex-Assets + Stufe-1-Backstop, verbatim → per-file E501-ignore), `moderation` (`_moderation_target` 3-Zweig-Credential-Port von `get_moderation_client` + `moderate` via **`litellm.amoderation`**, fail-open→{}), `legal` (`classify_legal` via `llm.chat_completion`, `_LEGAL_SYSTEM` 1:1), `service` (Orchestrator + Merge-Extraktion `_merge_moderation`/`_merge_legal`/`_maybe_downgrade`, verhaltens-erhaltend). `__init__` exportiert nur `assess_safety` (Modul/Funktion-Shadow vermieden). Deviations: 2 Transport-Swaps (Moderation→litellm, Legal→chat_completion), toter `if…:pass` entfernt, native-OpenAI-Base rstrip (ALT-Parität). 40 T (Port ALT regex_gate+escalation + neu `test_safety_stages`: 3-Zweig-Routing/moderate-Parse+Fail-open/B-API-Header/classify_legal). **Fresh-Eyes-Reviewer: 0 Verhaltens-Divergenzen** (jede Regex/Schwelle/Branch/Mapping/Schema-Default geprüft). Vertrag `docs/plans/p3-safety-contract.md`. Suite **318 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **3-5 Writer ✅ R3b 2026-07-18** (`obs/quality_events.py`: log_safety_event+log_quality_event → data jsonb + promoted, _field dict/obj/None-Fix, 6 pg-Pins; Gate/Aufruf = P4-6) — bewusst mit **P4-6 Persist** gepaart (Persist ist der Aufrufer des Loggings; beide sind pg-gebunden und werden zusammen gegen Dev-Compose verifiziert, statt 3-5 isoliert ohne belegbaren Write-Pfad zu bauen). Follow-up 3-2: persona_confidence-„<0.6"-Guidance via `Field(description=…)` nachrüstbar. |
> | P4 Orchestrierung | ✅ 4-1 ✅ · 4-2a ✅ · 4-3 ✅ · 4-4a policy ✅ · 4-4b pattern_engine ✅ · 4-4c state_machine ✅ · 4-4 route-node Kern ✅ · context/build_context ✅ (2026-07-11) · 4-2b/c/d-Nodes + 4-4-Tail pure Prerequisites ✅ (QR + LP-Diversity + Route-Tail-Decisions + LP-Intent-Gate) · **LP-Fast-Path-Body ✅** (`services/lp_fast_path.py`) · **canvas_postprocess ✅** (`domain/canvas/postprocess.py`, Canvas-Subtree-Start) · **canvas_types ✅** (`domain/canvas/types.py`) · **canvas_intent ✅** (`domain/canvas/intent.py`) · **completion_messages ✅** (`domain/completion_messages.py`) · **wikipedia_service ✅** (`services/wikipedia_service.py`) · **canvas_service ✅** (`services/canvas_service.py`, Fassade-Drop) · **canvas_fp ✅** (`services/canvas_fast_path.py`) · **route-fp-tail ✅** (`graph/nodes/route.py`, LP- + Canvas-Fast-Path verdrahtet) · **spec-prefetch ✅** (`services/prefetch.py` + `obs/tasks.py`) · **card-build ✅** (`domain/cards/build.py`, 4-5-Prereq) · **guide-strip ✅** (`domain/guide_markers.py`, 4-5-Prereq) · **guide_qr_injector ✅** (`services/guide_qr_injector.py`, netz-frei) · 4-5/4-6 offen → **beide ✅ (R4)**: `graph/nodes/{setup,merge,respond,persist,assemble}.py` · `graph/build.py` · `api/chat.py`, alle vorhanden und stubfrei — Status-Marker am 2026-08-13 nachgezogen (stand auf 🔄, obwohl P8–P10 darauf aufbauen) | **4-1 TurnContext ✅** `graph/state.py` — mutierbares pydantic-Modell des Turn-Zustands (framework-frei, kein `langgraph`-Import; Graph-Bau = 4-6). Felder aus den ALT-Phasen-Signaturen abgeleitet (`_setup_turn`/`_classify_and_merge`/`_produce_answer`/`_assemble_cards_and_qrs`): Input/Session (req·env·client_ip·session_state·history·early_response), Assessment (safety·classification·memories·signals·signal_history·state_id·context_snapshot·policy·usage), Answer (response_text·cards·quick_replies·page_action·pagination·web_links), Observability (debug). Jeder Feld-Typ = existierendes `boerdi.api.schemas`-Modell (keine erfundenen Typen). Bewusst VERTAGT (kein Produzent/Typ vor der jeweiligen Slice — Modul-Docstring listet sie vollständig): Routing-Interna (winner/pattern_output/scores/rag_config/tools_called/trans_check → 4-4), Prefetch/Canvas/QR-Policy (spec_*/canvas_*/qr_* → P5/4-5); `response_outcomes`/`final_confidence` bereits via `debug.outcomes`/`debug.confidence` abbildbar. `session_state`=dict (ALT-Parität, in-place-Mutation; SessionState-Konvertierung am DB-Rand). TDD: 5 T (Defaults, req-Pflichtfeld, Phasen-Mutation, early_response, Kern-Feldvertrag als Superset-Pin) RED→GREEN. Suite **323 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **Sequenz-Entscheid:** 3-5 DB-Logging mit **P4-6** gepaart (s. P3), daher 4-1 (pur, sofort belegbar) vor 3-5 gezogen. **4-2a tour-Domäne ✅ (2026-07-11)** `domain/tour.py` — 1:1-Port der reinen ALT `tour_service.py` (Web-Tour-State-Machine `_norm_path`/`match_group`/`detect_entry`/`expected`/`render` + `__guide__`-Nav-QRs; nur `re`+`typing`, kein I/O → Domäne, Regel 4). Deviations: `l`→`link` (ruff E741), 3 Signatur-/Comprehension-Zeilen umbrochen (100-Zeichen-Limit), sonst verbatim. Test `tests/test_tour.py` = Port ALT `test_tour_service.py` (16 T, synthetische Mini-`CFG`; ALTs 4 „echte-Config"-Smokes sind config-AGNOSTISCH → in die synthetischen Tests gefaltet statt die 30-Z.-`seed`+`bind_store`-Fixture aus `test_config_loader_surface.py` zu duplizieren). Suite **339 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **4-2-Abhängigkeitskarte:** tour-NODE (`_handle_tour`) + context_greeting (Domäne+Node) brauchen den **Persist-Seam** (`update_session`/`save_message` — noch nicht gebaut; Memory=4-3/Persist=4-6); context_greeting zusätzlich `page_context_service` (in NEU NICHT portiert); **preflight** braucht `chat_direct_actions._handle_*` (P5). Daher 4-2 in Teilstücken: 4-2a (pur) jetzt, Nodes nach Seam/P5. **Design-Vormerkung 4-6:** ALTs Inline-Persist der Early-Exit-Nodes wandert in NEU in den Persist-Node (läuft auch auf Early-Exit-Kanten) → Nodes bleiben rein, Netto-DB-Zustand paritätisch. **4-3 assess-Node ✅ (2026-07-11)** `graph/nodes/assess.py` — Port ALT `_assess_safety_classify_memory`: Regex-Pre-Gate → Krise-Kurzschluss (minimale `ClassificationResult` I07, kein LLM; Pattern-Engine wählt M01 später via `safety.enforced_pattern`) → sonst `asyncio.gather(assess_safety ∥ classify_input ∥ memory_fetch, return_exceptions=True)` + Per-Zweig-Fallbacks (safety→`regex_gate`, classify→Default-CR I01, memory→`[]`). **DI (Regel 3 — kein globaler Engine):** `memory_fetch` injiziert (Memory braucht pro-App-DB-Handle; P4-6 bindet echtes `get_memory` an die Engine); `assess_safety`/`classify_input` sind global konfiguriert → Direktaufruf (in Tests am Node-Modul monkeypatchbar). simplify: Studio-Tracer-Instrumentierung (`tracer.parallel_group`) zurückgestellt. `_fallback_classification` = verhaltens-erhaltende DRY-Extraktion der 2 ALT-Inline-CRs. 5 T voll gefaked (Krise-Kurzschluss+kein-LLM, Parallel-Merge, safety/classify/memory-Fallback) — kein DB/LLM/PG. **4-1-Korrektur:** `TurnContext.memories` `list[MemoryEntry]`→`list[dict]` (get_memory liefert `{key,value,memory_type}`-Dicts, ALT-Parität; `test_turn_context` nachgezogen). Suite **344 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **Offen (P4-6/Live-PG):** `services/memory.py::get_memory(factory, session_id, memory_type=None)` (rule-3: Factory-Param) + Graph-Wiring `memory_fetch=partial(get_memory, factory)`. **4-4a policy ✅ (2026-07-11)** `domain/policy.py` — 1:1-Port ALT `policy_service.py` (`assess_policy(message, persona_id, intent_id)`: Regel-Match persona/intent/message_regex → `matched_rules`/`blocked_tools`[dedupe, Reihenfolge stabil]/`required_disclaimers` auf `PolicyDecision`; R-01 = nie harte Blockade; kaputte Regex via `re.error` übersprungen). `load_policy_config` (Read-Fassade) direkt importiert → „framework-frei" bleibt (kein Web/DB/Graph). Test `tests/test_policy.py` = Port ALT `test_policy_service.py` (6 T, `load_policy_config` am Modul gemockt; test-6 zusätzlich config-gemockt für NEU-bound-store-Unabhängigkeit — Assertion prüft `PolicyDecision`-Shape, `allowed` default True nie False). Suite **350 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **4-4 offen:** `domain/pattern_engine.py` (382 Z., rein+pydantic; Seams `_load_config_tables`/`get_tone_modifier_for_persona`/`get_patterns`/`phase3_modulate` mockbar; 152-Z.-Test) + `domain/state_machine.py` (150 Z., `get_state_directive`; **KEIN** ALT-Test → Charakterisierungstests neu schreiben) + Route-Node (`graph/nodes/route.py`, verdrahtet die drei Domänen). **4-4b pattern_engine ✅ (2026-07-11)** `domain/pattern_engine.py` — 1:1-Port ALT `pattern_engine.py`: `PatternDef`-Modell + `_load_config_tables`/`_pattern_from_dict`/`load_patterns`/`get_patterns` + rein `_apply_length_bias` + `phase3_modulate` (Tone-Override/Length-Bias/Formality/Card-Mode + Helper-Tool-Auto-Add bei Such-Tools + Signal-Mods + `reduce_items`-max_items-Clamp + Slot-Degradation) + `select_pattern` Hint-Primary (enforced → hint → Fallback M15/M03/patterns[0]). Lazy `config_loader`-Importe in den Funktionen erhalten (Test mockt am Facade). **Verifikation:** mechanischer Code-Diff ALT↔NEU = NUR Docstring-Umformulierungen, **0 Code-Divergenz** (Tests asserten nicht alle ~30 phase3-Output-Keys → Diff schließt die Lücke). Test `tests/test_pattern_engine.py` = Port ALT (14 Fn / 19 Fälle: length_bias·pattern_from_dict[label/legacy]·phase3[override+helper/signal+degradation]·select[6 Pfade]·load-Pfade). Suite **369 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **4-4c state_machine ✅ (2026-07-11)** `domain/state_machine.py` — 1:1-Port ALT `state_machine.py` (`validate_transition(prev, next_, intent=None, *, auto_correct=False)`: erster-Turn/Self-Loop/kein-next_likely → plausibel; `next_ in next_likely` → plausibel; Canvas-Intent-Override I05/I06→S3 trotz Fehlen in next_likely; sonst implausibel → bei `auto_correct=False` reine Telemetrie [`validated_state` unverändert], bei `True` Korrektur auf `next_likely[0]`). `get_state_directive` (Read-Fassade) per Name importiert → am Modul mockbar; framework-frei. **Verifikation:** mechanischer AST-Diff des `validate_transition`-Body ALT↔NEU = **IDENTISCH, 0 Code-Divergenz** (Deviation nur im Modul-Docstring: ALTs 2., widersprüchliches Doctest-Beispiel behauptete `plausible=False` für einen Self-Loop, den der Code als plausibel wertet → durch wahrheitsgemäße Prosa ersetzt). **KEIN ALT-Test** → `tests/test_state_machine.py` frisch geschrieben (9 T, alle 7 Zweige + 2 Override-Guards; `get_state_directive` am Modul gemockt; `test_self_loop` pinnt exakt den Input des kaputten ALT-Doctests `prev=next_="S3", intent="I02"` auf das korrekte `plausible=True`). Suite **378 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **4-4 Route-Node (Entscheidungs-Kern) ✅ (2026-07-11)** `graph/nodes/route.py` — **Scoping-Befund:** ALT-`_route_pattern` (630 Z.) ist KEIN dünner Draht, sondern eine fette Orchestrierung; ihr Tail (Spec-Prefetch `_launch_speculative_prefetch`, LP-Fast-Path, Canvas-Create-Fast-Path, Effective-Pattern-Reconciliation, QR-Policy) hängt komplett an P5-MCP/Canvas + `build_context`/context_service (in NEU nicht portiert). Portiert daher der **buildbare Entscheidungs-Kern** aus zwei ALT-Phasen: aus `chat_turn_setup` Persona-Update (R-06) + Signal/`signal_history`-Merge + `new_state` + `validate_transition` (try/except, Telemetrie-only, nie Turn-fail) + `assess_policy` + Merge `policy.blocked_tools`→`safety.blocked_tools` (ein Enforcement-Pfad); aus dem Kopf von `chat_turn_routing._route_pattern` `select_pattern` (Enforce>Hint>Fallback; `enforced=safety.enforced_pattern or None`, `pattern_id_hint`) + Blocked-Tools-Strip aus `pattern_output["tools"]` + strenge RAG-Whitelist je Pattern (`_resolve_rag_areas`, 3 Zweige) + Memory-Render (`_render_memory_context`, cap 10). Reine Helfer + `_update_persona` extrahiert → Node-Body linear/lesbar; `_resolve_rag_areas`/`_render_memory_context`-Rümpfe verbatim aus ALT `chat_turn_routing.py:161–192`. `async` (Parität + vertagte Fast-Paths brauchen `await`), zero-await heute. **TurnContext erweitert** (state.py, die in 4-1 vertagten Routing-Felder): `winner_id`/`winner_label` (kein voller `PatternDef` — Downstream braucht nur id/label + `pattern_output`), `pattern_output`/`scores`/`eliminated`/`trans_check` + RAG (`rag_config`/`available_rag_areas`/`memory_context`). **simplify:-vertagt (P5/4-5):** Prefetch, LP-/Canvas-Fast-Path, Effective-Pattern (`effective_pattern_id`/`label`), `tools_called`, QR-Policy, `context_snapshot` (build_context). Parität-Check: `turn_type=classification.turn_type` (ALT `chat_turn_setup:270`, keine Neubindung bis Persona-Block:442) verifiziert → kein Divergenz. `tests/test_route_node.py` 16 T (4 Persona-Fälle parametrisiert, Signal/State-Merge + validate-Verdrahtung, validate-Exception→Fallback, Policy→Safety-Merge, Tool-Strip, Enforce/Hint-Weitergabe + „" →None, Ausgabe-Felder, RAG 3 Zweige direkt, Memory-Render leer/format/cap; 3 Domänen + `load_rag_config` am Node gemockt). Suite **394 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **4-4 rest (Tail):** Fast-Paths/Prefetch/Effective-Pattern/QR-Policy nach P5; dann Graph-Bau in 4-6. **domain/context.py (build_context) ✅ (2026-07-11)** — reiner 1:1-Port ALT `context_service.py` (env/session_state/classification/memories → `ContextSnapshot`: page/device/locale/session_duration + turn_count + entities [interne `_`-Keys verborgen] + recent_signals[-10:] + memory_keys[:10] + last_intent/last_state aus classification). AST-Diff `build_context`-Body ALT↔NEU = **IDENTISCH** (Deviation nur Import-Pfad + Prosa→DE); pure → `domain/`. **KEIN ALT-Unit-Test** → `tests/test_context.py` 8 T frisch (Defaults/env-str+None→int-Koerzierung/turn_count/`_`-Entity-Filter/signals-cap/memory-cap/classification). **In Route-Node verdrahtet:** `ctx.context_snapshot = build_context(ctx.env, ss, cls)` an der ALT-`chat_turn_setup:521`-Stelle, wie ALT OHNE `memories` (→ memory_keys leer = Parität; +1 Route-Test pinnt es trotz gesetztem `ctx.memories`) → schließt die in 4-4 vertagte `context_snapshot`-Lücke. Suite **403 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. · **4-4-Tail-QR ✅** (2026-07-12) `domain/quick_reply_policy.py` — Port der 4 framework-freien QR-Helfer aus ALT `chat_quick_replies.py` (`_qr_policy`/`_qr_default_count`/`_spec_qr_response_block`/`_apply_state_auto_followup`, 30 T); entsperrt QR-Policy des Route-Tails + M09-Spec-QR (LP-Fast-Path) + QR-Postproc — alle P4-5. Layer domain/ (config_loader-Read-Fassaden). AST 4/4 identisch modulo 2 norm. Deviations (Lazy-Import-Pfad; `_display_rules`→`load_display_rules_config`, verhaltensident. da ALT-Wrapper-Fallback `quick_replies.max_count`=4). Guide-QR-Helfer separat. Suite **744 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **Update 2026-07-18:** 4-4 komplett ✅ (beide Fast-Paths im Route-Node verdrahtet — `route.py` ruft `run_lp_fast_path` + `run_canvas_create_fast_path`; Spec-Prefetch-Producer portiert, Launch/Konsum sitzt beim Tool-Loop 5-3/4-5); offen im Paket nur noch **4-2d context_greeting (R6-blockiert)** + 4-5 respond/SSE + 4-6 Persist/Graph-Bau (zusammen = Restplan R4); **4-2b preflight ✅ + 4-2c tour ✅ 2026-07-18** (graph/nodes/{preflight,tour}.py, je Node-Test, ctx.early_response-Seam); Suite inzwischen 1570/2 mit pg oben (Vollcheck 2026-07-18: Gates frisch bestätigt). |
> | P5 WLO-Tools & Karten | ✅ 5-1 ✅ · 5-2 ✅ · **5-3 ✅** (outcome_service ✅ Vorstufe + 5-3-Rest pure Inline-Grouping-Helfer ✅ + **Tool-Loop-Start ✅ 2026-07-18** [`services/tool_loop.py`: `_max_iterations_fallback` P16, 5 Pins; SSE-Abtrennbarkeits-Check bestanden — der Loop RETURNIERT das Tupel, streamt nicht, einziger Stream-Touchpoint = optionaler `on_token`-Callback]; **`_assemble_messages` [P12/P14] ✅ 2026-07-18** — AST 29/29 nach 5 sankt. Transforms, 17 Pins, session-first pg-DI; **`_run_tool_loop` [P15] ✅ 2026-07-18** — AST-Gate 206 verschachtelte Stmts nach sankt. Transforms, 24 Pins, dazu **R1b-1 `services/llm_streaming.py` ✅** [ALT-Port, 13 Pins, Live-Semaphor über die GANZE Stream-Konsumption]; P5-3-Funktionsfläche komplett — inkl. `generate_response`-Orchestrator ✅ [R1c 2026-07-18, `services/generate.py`] — 5-3 Tool-Loop 3/3 komplett) · **5-4 ✅** (5-4a Normalisierung ✅ · 5-4b Selektion/Ranking ✅ · guide_mode ✅ · 5-4c Card-Links ✅ + async I/O-Tail `services/card_pipeline.py` ✅ = **Card-Paket komplett**) (2026-07-12) · **5-5 Reranker-Gate ✅ (2026-07-12)** · **5-6 ✅** (5-6a LLM-Generatoren ✅ · 5-6b topic_pages-Helfer ✅ · **Direct-Actions ✅ R5 2026-07-18** [`services/direct_actions.py`: browse/lernpfad/curate + `_direct_action_safety_text`, 14 Pins] — offen nur M16-Resolver [mit R4/R6] → **M16-Resolver ✅ 2026-07-24** (`_resolve_m16_topic_page_view` in `services/topic_pages.py`, in `turn_persist` verdrahtet); Status-Marker am 2026-08-13 nachgezogen) | **5-3-Rest pure Inline-Grouping-Helfer ✅ (2026-07-12)** `domain/inline_grouping.py` — **Voll-verbatim-Port** des puren P13-Layers aus ALT `llm_tool_loop.py` (Z. 37–196 zusammenhängend): `_strip_trailing_option_lines` (QR-/Guide-Zeilen am Antwort-Ende strippen) + Card-Sichtbarkeits-Prädikate `_is_einzelinhalt_card`/`_is_themenseite_card`/`_is_pure_sammlung_card` + `_ui_box_state_footer` (Anti-Halluzination-UI-Box-Status, Wahrheitspflicht) + `_redact_search_content_for_llm` (Einzelinhalt-Redaction aus LLM-sichtbarem Tool-Result-Text) + Konstante `_EINZELINHALT_LEAK_TOOLS`. **Alle pure** (stdlib + `_logger`) → `domain/`; der I/O-Tool-Loop-Body (`_assemble_messages`/`_run_tool_loop`) bleibt P6/4-5. **KEINE Deviation** (kein Import-Swap — der Block hängt nur an `_logger` + sich selbst); Byte-exakte CONTIGUOUS-Slice-Extraktion (bewahrt die Inter-Funktions-Kommentare, die `ast.get_source_segment` verlöre). **Prädikat-Duplikat:** ALT hält diese Prädikate doppelt (`llm_tool_loop` + `chat_cards`, T-4-synchron); NEU hat sie nur hier — der spätere `chat_cards`-Slice (P4-5) soll sie reusen statt neu zu duplizieren. **Verifikation:** AST-Diff ALT↔NEU über **alle 7** Namen (6 Fn + `_EINZELINHALT_LEAK_TOOLS`) = **byte-identisch, 0 NEU-only** → 0 Divergenz. Test `tests/test_inline_grouping.py` (18 T): strip 7 direkte ALT-Ports (`test_llm_service_helpers.py`) · Prädikate/Footer 1 direkter ALT-Test (topic_page T-4) + 5 Charakterisierung · `_redact` 5 Charakterisierung (ALT hatte nur Integration→P6). **Latenter Quirk geflaggt (nicht gefixt, Parität):** bare `topic_page`-Card OHNE `topic_pages`-Array zählt im Footer doppelt (themenseite+einzelinhalt), real nie erreicht (Parser liefert topic_pages) → Test nutzt realistische Card. Suite **714 grün + 50 pg-skips**, ruff clean (Test-`I001`/`E501` gefixt), OpenAPI unverändert. **→ 5-3 = outcome_service + pure Helfer komplett; offen nur der Tool-Loop-Body (P6/4-5).** — **5-6b topic_pages-Such-Helfer ✅ (2026-07-12)** `services/topic_pages.py` — Port der drei buildbaren Such-Helfer aus ALT `chat_topic_pages.py`: `_is_empty_topic_pages_response` (Leerheits-Check: DE-Marker „Keine Themenseiten" ODER leeres `results`/`items`-JSON-Array) + `_filter_topic_pages_by_title` (JSON-Envelope-Titel-Filter für den Global-Fallback, `_query_fallback`-Marker) — **beide pure/offline** — + `_topic_pages_with_warmup` (async: `search_wlo_collections`-Warmup [best-effort, verworfen] → Primary `search_wlo_topic_pages` → bei 0 Treffern Global-List-Fallback: erst Titel-Filter, sonst bis 5 globale TPs `_global_fallback`, sonst Primary). **Landeort `services/`** — alle drei kohäsiv (Warmup ruft beide puren Helfer), = `outcome_service`-Muster (pure+async zusammen) / Sibling `card_pipeline.py` (Such-Orchestrierung, konsumiert `mcp.client`, nicht Teil davon). **M16-Resolver `_resolve_m16_topic_page_view` deferred → P4-5** (braucht `tracer`/`winner`/respond-Kontext + Swimlane-Schemas). **Deviation (AST-neutral):** nur die eine lazy MCP-Import-Root im Warmup (`app.services.mcp_client`→`boerdi.services.mcp.client`, kein Facade); redundantes `import json as _json` verbatim belassen (AST-Parität). **Verifikation:** AST-Diff ALT↔NEU (ImportFrom.module normalisiert): 2 pure Helfer **byte-identisch** (0 ImportFrom), Warmup identisch modulo **1** ImportFrom.module → **0 Logik-Divergenz**; Byte-Extraktion via `ast.get_source_segment` (deutsche Kommentare 1:1). Test `tests/test_topic_pages.py` = Port der drei buildbaren ALT-Klassen (31 T: is_empty 11 · filter 14 · warmup 6; `TestResolveM16TopicPageView` [8 T] bewusst nicht portiert = deferred). Boundary Warmup = `boerdi.services.mcp.client.call_mcp_tool` (lazy → am Quellmodul gepatcht), pure Helfer echt. Suite **696 grün + 50 pg-skips**, ruff clean (Test-`I001` auto-fix), OpenAPI unverändert. — **5-6a LLM-Generatoren ✅ (2026-07-12)** `services/llm_learning_path.py` + `services/llm_curation.py` — Port der zwei Single-LLM-Call-Blatt-Generatoren aus ALT `llm_learning_path.py`/`llm_curation.py`: `generate_learning_path_text` (paedagogisch strukturierter Lernpfad aus Sammlungs-Inhalten: Fach/Stufe-Ableitungs-Hinweis, Schritt-Anzahl-Regeln, No-LaTeX) + `generate_curation_text` (SOLL-vs-IST-Gap-Analyse Kompendium↔Inhalte, strikt geerdet). **Scoping-Befund 5-6:** NICHT vollständig jetzt baubar — diese zwei **reinen** Generatoren sind der unblockierte Leaf; `chat_direct_actions.py` (browse/lernpfad/curate-Handler) hängt am ganzen `routers/chat_*`-Helfer-Ökosystem (Cards-Build/Guide-Marker/Inline-Render/`save_message`), `chat_topic_pages._resolve_m16_topic_page_view` an `tracer`/`winner`/respond-Kontext → beide **P4-5**. **Transport-Adaption (dokumentiert, = `quick_replies_llm`-Muster):** ALT modul-globale `client=get_client()`/`MODEL=get_chat_model()` + `client.chat.completions.create(**build_chat_kwargs(...))` → NEU `llm.chat_completion(messages=…, temperature=…, max_tokens=…)`; `strip_reasoning_markers` aus `domain.reasoning_filters`. **Prompt-Bau verbatim ALT** (byte-exakte `ast.get_source_segment`-Extraktion → deutsche Sonderzeichen/Klammern 1:1, nur die eine Transport-Zeile getauscht). **Verifikation:** AST-Diff ALT↔NEU mit Normalisierung NUR des `resp = await …`-Assign (genau 1 je Funktion) → Rest (Prompt-Bau/messages/Parsing/Fallback-Kette/except) **byte-identisch** = **0 Logik-Divergenz**. Tests: LP hatte **5 direkte ALT-Tests** (`test_llm_service_generators.py`) → 1:1 portiert (Prompt-Bau verbatim → gleiche Asserts, Boundary `llm._acompletion`-Fake); Kuration hatte **KEINEN** ALT-Direkttest (nur gemockte Boundary) → 5 **Charakterisierungs-Tests** frisch (SOLL/IST-Struktur+Persona · Persona-Default P-AND · Leer-Fallback · reasoning-strip · Exception-Embed), pinnen ALTs reales Verhalten. `llm_learning_path.py` per-file `E501`-ignore (verbatim Prompt-Zeilen, wie Geschwister `quick_replies_llm.py`); Kuration verletzt E501 nicht → kein Ignore (YAGNI). 10 T. Suite **665 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **5-6-Rest (P4-5):** `chat_topic_pages.py` stateless+warmup-Helfer (`_is_empty…`/`_filter…`/`_topic_pages_with_warmup`, nur `call_mcp_tool`) buildbar als nächster Sub-Slice; Handler + M16-Resolver mit dem respond/graph-Layer. — **5-4-Tail (async I/O) ✅ (2026-07-12) → 5-4 + Card-Paket komplett** `services/card_pipeline.py` — 1:1-Port der beiden async-Funktionen aus ALT `card_pipeline.py`: `fetch_card_pool` (Beschaffung: je `intent_kind` 1 od. 3 MCP-Tools [`asyncio.gather` bei general = topic_pages∥collections∥content], Pool-Default 20 aus `card-pipeline.yaml`, Defensiv-Clamp 1–50; collection-contents→`get_collection_contents` mit `nodeId`) + `run_pipeline_v2` (End-to-End: `infer_intent_kind` → fetch [od. `prefetched_pool` = Curation-Modus, model_dump/dict-Konvert] → `normalize_cards` → `select_final_cards` → `annotate_cards_with_link` → Diagnose-Dict pool/normalized/final-Counts). **Scoping-Befund:** `run_pipeline_v2` ruft den Reranker **NICHT** (Gate sitzt früher im Tool-Loop) → 5-4-Tail war nie 5-5-abhängig; alle Deps ✅ (call_mcp_tool/parsers + domain/cards + load_card_pipeline_config). **Landeort `services/`** (async I/O, nicht `domain/`). Deviation: nur die lazy MCP-Importe → NEU-Leaf-Module (client+parsers, kein Facade); `run_pipeline_v2` sonst body-identisch. **Verifikation:** AST-Diff ALT↔NEU (Import-Statements gestript, Rest verglichen): `fetch_card_pool` Rumpf identisch + Import-Namenmenge identisch {call_mcp_tool, parse_wlo_cards, parse_wlo_topic_page_cards}; `run_pipeline_v2` **byte-identisch** → **0 Logik-Divergenz**. Byte-Extraktion via `ast.get_source_segment` (deutsche Kommentare 1:1). Test `tests/test_card_pipeline.py` = Port ALT (7 T: fetch collection-nodeId/leer-ohne-id/type-focus-LRT+Disc/general-Reihenfolge · run prefetched-skip/pydantic-Konvert/type-focus-Fetch); MCP-Seam gefaked, `run_pipeline_v2` gegen **ECHTE** domain-Stufen (= Integrationstest normalize+select+links). Suite **655 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. — **5-5 Reranker-Gate ✅ (2026-07-12)** `services/card_reranker.py` — 1:1-Port ALT `card_reranker.py` (184 Z.): Env-/Schwellen-/Doc-Helfer (`_env_float`/`_env_int`/`threshold_for_tool` [Sammlungen+Themenseiten `CARD_CE_GATE_COLLECTION` 0.0 / Einzelinhalte `CARD_CE_GATE_CONTENT` -1.5]/`_doc_text`) + `rerank_gate_envelope` (CE-Rank+Gate+Top-N `CARD_CE_TOP_N` 3 auf dem MCP-Envelope; Soft-Gate für `_global_fallback`/`_query_fallback`-Browse-Sets [nur ranken, nie 0-gaten]; 3 Degrade-Modi fallback-no-ce/-ce-error/leere-Query). **Reines Python (json/os/logging) — KEIN Modell, 0 Ressourcen-Kosten**; der Scorer liegt hinter dem lazy Seam `_get_reranker()` (ALT `rag_service`, NEU P6), Abwesenheit → graceful `ImportError`→fallback. **Entscheid 2026-07-12 (Nutzer): kein Netzwerk-Dienst** (TEI-Sidecar aus Kostengründen verworfen) → Verbatim-Port hält alle kostenarmen Backends offen (lokales Modell / lexikalisch via `select._relevance_score` / keiner), Backend-Wahl = P6; Spec-Widerspruch (Eiserne Regel 12 Parität vs. Zeile 675 TEI) zugunsten Parität aufgelöst. **Deviations (AST-neutral):** 2 lazy Import-Roots (`mcp_client`→`mcp.parsers._first_json_object`, `rag_service`→`boerdi.services.rag_service`) + `zip`-`# noqa: B905` (verbatim default-zip). **Verifikation:** AST-Diff ALT↔NEU: Modul-Docstring + 4 pure Helfer + `__all__` + top-level Imports **byte-identisch**; `rerank_gate_envelope` divergent NUR Import-Root (per ImportFrom-Normalisierung bewiesen) → **0 Logik-Divergenz**. Test `tests/test_card_reranker.py` = Port ALT (11 T). **Test-Anpassung:** Fake-Scorer als Modul unter `boerdi.services.rag_service` registriert (sys.modules + Eltern-Attribut), da P6 ungebaut. **5-4-Tail entsperrt** (async `run_pipeline_v2`-Rerank-Schritt hat jetzt seinen Gate). Suite **648 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. — **5-4c Card-Links ✅ (2026-07-11) → pure Card-Domäne komplett** `domain/cards/links.py` — 1:1-Port der Link-Bau-Hälfte von ALT `card_pipeline.py:463-798`: `build_card_link` (Single-Source-of-Truth-URL: topic_page [topic_page_url→Variante→topic-pages-Renderer] / collection [Browse-URL +`&q=`] / content [Normal=externe url, Lotsen=Repo-Render] Lookup + `_infer_node_type`-Fallback) + `validate_card_link` (Schema+Host-Allowlist, `allowed_hosts`-Override oder guide-mode-Fallback) + `annotate_cards_with_link` (In-place `link`-Set, `require_allowed`→Repo-Render-Fallback, Lotsen-`url`-Override) + Helfer `_card_as_dict`/`_host_of`/`_set_link_field`/`_get_node_id`. Pure Domäne — Deps: config `get_repo_base_url` + `.normalize` (Repo-URL-Builder/`_infer_node_type`) + `domain/guide_mode` (`host_matches_pattern` top-level, `host_is_allowed` lazy in `validate_card_link` = verbatim ALT). **Deviations (alle behaviour-neutral):** Import-Roots + 2× `setattr`-B010-noqa (verbatim); `validate_card_link` Lazy-Import-Root (`guide_mode_service`→`domain.guide_mode`) → einzige AST-Divergenz, per ImportFrom-Normalisierung als **rein Import-Root bewiesen** (Rümpfe sonst identisch). **Verifikation:** AST-Diff ALT↔NEU: **6/7 Fn byte-identisch + `validate_card_link` identisch-außer-Import-Root** = 0 Logik-Divergenz. Test `tests/test_cards_links.py` = Port 6 ALT-Klassen (29 T: build topic/collection/content/defensiv 16 · validate 9 · annotate 3 + Modul-Lotsen-url-Override). **Test-Anpassung:** `validate`-Default-Allow-List-Tests pinnen die guide-mode-Allow-Liste via `_cfg`-Patch (NEU-Test-Env hat leere seed-Allow-Liste; ALT las ambiente `guide-mode.yaml`) → deterministisch. Suite **637 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. — **guide_mode ✅ (2026-07-11) [entsperrt 5-4c Card-Links + Web-Tour]** `domain/guide_mode.py` — 1:1-Voll-Port ALT `guide_mode_service.py` (257 Z.): Host-Allowlist `host_matches_pattern` (exakt/`*.domain`-Wildcard, bare-Host NICHT) + `host_is_allowed` + `_normalize_host` (www/Port-Strip) + `is_guide_eligible_url` (Schema+Host) + `pick_guide_url` (url_fields_priority → topic_pages-Varianten → Sammlungs-Render→Browse-Rewrite via `_ES_RENDER_RE`) + `annotate_cards_with_guide_url` (In-place `guide_url`-Set, max_targets „0=unlimited"-Regression-Pin, dict+Pydantic-Model-Pfad). Pure Domäne (wie tour/policy/context) — einzige Dep = config-Read-Fassade `load_guide_mode_config`. **Deviations (alle AST-neutral):** Import-Root + `import re as _re_es` von Modul-Mitte an den Kopf (E402); `setattr`-B010 via `# noqa` (verbatim, symmetrischer Objekt-Pfad); langer Regex `# noqa: E501` (verbatim Asset, wie regex_gate). **Verifikation:** AST-Diff ALT↔NEU über **alle 9 Fn + `_ES_RENDER_RE`** = **0 Divergenz**. Test `tests/test_guide_mode.py` = Voll-Port ALT `test_guide_mode_service.py` (31 T inkl. parametrisiert; `_cfg` gefaked → kein PG). **Entsperrt 5-4c** (`build_card_link`/`validate_card_link`/`annotate_cards_with_link` aus `card_pipeline`) + Web-Tour-Node (P7). Suite **608 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. — **5-4b Card-Selektion/Ranking ✅ (2026-07-11)** `domain/cards/select.py` — 1:1-Port der puren Selektions-Hälfte von ALT `card_pipeline.py` (Pipeline-v2-Final-Selection): `select_final_cards` (type-focus-Strikt-Filter → deterministische Ordnung [general=`_deterministic_mix` mit Intra-Gruppen-Relevance-Sort + Score-0-Gruppen-Drop-wenn-andere-matcht; type-focus=Gesamt-Relevance; collection-contents=kuratiert-unverändert] → LLM-Re-Rank-Merge `_select_by_ids` [picked vorn, Rest dedupt] → final_size/min_displayed-Schnitt) · reine Helfer `_tokenize_query` (Unicode-Regex + Stopwort-Strip, lokaler `import re` für AST-Parität) · `_relevance_score` (Title 2.0/Keywords 1.0/Disciplines 0.5/Desc 0.3) · `_sort_by_relevance` (stabil) · `_filter_to_wanted_content_types` · `_deterministic_mix` · `summarize_pipeline_result` (ASCII-Log). Pure Domäne — Deps nur config-Read-Fassade `load_card_pipeline_config` (final=5/min=5-Defaults settings-getrieben → kein PG) + `IntentKind` aus `.normalize`. **Deviation nur Import-Roots** (`app.`→`boerdi.`; `IntentKind` aus `.normalize` statt in-Modul); Funktions-Rümpfe byte-identisch. **Verifikation:** AST-Diff ALT↔NEU über **alle 8 Fn + `_RELEVANCE_STOPWORDS`** = **0 Divergenz**. Test `tests/test_cards_select.py` = Port von 6 ALT-Klassen (31 T: SelectFinalCards 8 [Mix/LLM-Pick/Halluzination/type-focus-Filter/small-pool/collection-contents/empty] · TokenizeQuery 6 · RelevanceScore 5 · SortByRelevance 3 · SelectFinalCardsRelevance 6 [Live-Bug-Repros: relevante Sammlung gewinnt, Score-0-Gruppen-Drop] · Summarize 2 + Modul-Fill-Test). **5-4-Rest (vertagt):** Link-Bau (`build_card_link`/`validate_card_link`/`annotate_cards_with_link` — **blockiert auf `guide_mode_service`**, NEU-ungebaut) · async `fetch_card_pool`/`run_pipeline_v2` (MCP+Links+Reranker → nach guide_mode + 5-5). Suite **577 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. — **5-4a Card-Normalisierung ✅ (2026-07-11)** `domain/cards/normalize.py` — 1:1-Port der puren Normalisierungs-Hälfte von ALT `card_pipeline.py` (1285-Z.-Monolith wird nach Verantwortung in ein `domain/cards`-Paket gesplittet): `infer_intent_kind` (collection→type-focus→general) · `normalize_cards` (Host-Rewrite bidirektional → node_type-3-Wege-Inferenz [topic_page/collection/content] → wlo_url-Repair render↔collections → Dedup per node_id → general-Sort topic>collection>content, stabil) · `_infer_node_type`/`_rewrite_card_urls` + geteilte Repo-URL-Builder `_is_render_uuid`/`_repo_render_url`/`_repo_collection_browse_url`/`_repo_topic_page_url`. Pure Domäne — einzige Deps = config-Read-Fassade `get_repo_base_url`/`rewrite_repo_host_v2` (aus `domain/` sanktioniert) + stdlib `quote`. **Deviation nur Import-Root**; Funktions-Rümpfe byte-identisch. **Verifikation:** AST-Diff ALT↔NEU über **alle 8 Fn + 3 Konstanten** (IntentKind/NodeType/_NODE_TYPE_PRIORITY) = **0 Divergenz**. Test `tests/test_cards_normalize.py` = Port der 5 ALT-Normalisierungs-Klassen (17 T: intent_kind 4 · node_type 4 · Dedup+Sort 4 · Host-Rewrite 3 · wlo_url-Repair 2). Config-Helfer-Tests (`rewrite_repo_host_v2` etc.) bereits in `test_config_loader_surface.py` (P2) → nicht dupliziert. **5-4-Rest (vertagt):** 5-4b Selektion/Ranking (`select_final_cards`/`_relevance_score`/`_deterministic_mix` — pure, buildbar als nächster Sub-Slice) · Link-Bau (`build_card_link`/`annotate_cards_with_link` — **blockiert auf `guide_mode_service`**, in NEU nicht portiert) · async `fetch_card_pool`/`run_pipeline_v2` (MCP+Links+Reranker → nach 5-4b/5-5). Suite **546 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. — **5-3 (Teilstück, Vorstufe) outcome_service ✅ (2026-07-11)** `services/outcome_service.py` — 1:1-Port ALT `outcome_service.py` (90 Z., Triple-Schema T-23/24/25/27): `call_with_outcome` (umschließt den in 5-1c gebauten `call_mcp_tool` → `ToolOutcome`: Latency, Status success/empty/error, item_count-Heuristik [Such-Tools `count("nodeId") or count("- ")`, sonst 1], Exception→error+`str(e)[:200]`+`""`-Result) · `adjust_confidence` (pur: error −0.20/empty −0.10/success+items +0.05/timeout −0.15, Clamp [0,1]) · `derive_state_hint` (pur: leer→""; alle failed→"state-clarification"; ein success+items→"S3"; sonst ""). **Scoping-Befund 5-3:** der eigentliche Tool-Loop-Body (`_run_tool_loop`/`_assemble_messages` in ALT `llm_tool_loop.py`, 1159 Z.) hängt an **noch nicht gebauten** Subsystemen — `rag_service` (ganz P6), `_stream_completion` (4-5 respond/SSE) — daher die buildbare Vorstufe vorgezogen (Muster wie Route-Node-Kern 4-4). Deps nur `ToolOutcome` (✅ `boerdi.api.schemas`) + `call_mcp_tool` (✅ 5-1c) + stdlib. Deviations: nur Import-Roots; `call_mcp_tool` als Modul-Name importiert (Patch-Ort + AST-Parität). **Verifikation:** AST-Diff ALT↔NEU über alle 3 Funktionen = **0 Divergenz, 0 ALT/NEU-only**. **KEIN ALT-Test** → `tests/test_outcome_service.py` 10 T frisch (nodeId-Count/Nicht-Such→1/Bullet-Fallback/empty/Exception-Trunk; confidence-Deltas+Clamp; state-hint 4 Zweige; `call_mcp_tool` gefaked). Suite **507 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **5-3-Rest (vertagt):** reine Inline-Grouping-Helfer (`_strip_trailing_option_lines` / Card-Prädikate `_is_einzelinhalt/_themenseite/_pure_sammlung_card` / `_ui_box_state_footer` / `_redact_search_content_for_llm`) sind buildbar als eigener Slice (pure, ohne RAG/Streaming); `_assemble_messages`/`_run_tool_loop` erst nach P6-RAG + 4-5-Streaming. — **5-2 (Teilstück, damit 5-2 KOMPLETT) parsers ✅ (2026-07-11)** `services/mcp/parsers.py` — **vollständig verbatim** 1:1-Port ALT `mcp_parsers.py` (471 Z.): zustandslose JSON/Text→Boerdi-Card-Dict-Parser `parse_total_count` (3-stufige Regex-Zählung) · `_topic_page_display_title` (Placeholder-Guard PAGE_VARIANT/variant_/UUID/=cid → „Themenseite (Stufe)") · `parse_wlo_topic_page_cards` (Varianten-Map + Dedup gleicher url/target/label + UNINFORMATIVE-Label-Strip) · `_cards_from_json_envelope` (v2-FormattedNode→Card-Schema, node_type-abhängige wlo_url render/collections) · `parse_wlo_cards` · `_first_json_object` (balancierter Brace-Extraktor) · `parse_search_all_cards` (3 Töpfe content/collections/topic_pages + Fragment-Fallback) · `parse_topic_page_swimlanes` · `_normalize_card_repo_hosts`. Einzige Dep = config_loader `get_repo_base_url`/`rewrite_repo_host` (settings-getrieben → **kein PG**, im Test out-of-the-box). **Kein Facade-Re-Export** (ALTs `_first_json_object`-Durchreiche über `mcp_client` entfällt; Konsumenten [5-3 Tool-Loop / 5-5 Reranker] importieren direkt aus `parsers`) → ALTs `test_fassade_reexportiert_first_json_object` bewusst nicht portiert. Deviations: nur Import-Root (`app.`→`boerdi.`) + 1 umbrochene `for`-Tupel-Zeile (E501). Linter: B023 auf der `_clean`-Closure (`UNINFORMATIVE` loop-lokal) via `# noqa`+Begründung — false-positive (loop-invariante Konstante, Nutzung nur in der Definitions-Iteration → Late-Binding kann nicht feuern), AST bleibt identisch. **Verifikation:** mechanischer AST-Diff ALT↔NEU über **alle 11** Top-Level-Namen (9 Fn + `_TP_UUID_RE` + logger) = **0 Divergenz, 0 ALT-only/NEU-only** — der stärkste Fidelity-Beleg des Pakets (echter Voll-verbatim-Port, inkl. der redundanten lokalen `import re` in `parse_total_count` für AST-Parität belassen). Test `tests/test_mcp_parsers.py` = Port aller 26 ALT-Tests (imports auf `parsers` umgelenkt): total_count 3-stufig · wlo_cards Feld-Map/node_type-URL/non-JSON/kein-v2/kein-nodeId · topic_page basic/Placeholder/non-envelope/Varianten-Dedup · first_json_object balanciert/String-Braces/absent · display_title 4 Placeholder-Fälle · search_all 3-Töpfe/Fragment/leere-Buckets · swimlanes happy/leere-Form. Suite **497 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **5-2 damit KOMPLETT** (tool_defs + arg_resolvers + parsers); **5-1+5-2 = MCP-Schicht vollständig**. Nächste: 5-3 Tool-Loop/Prefetch (verdrahtet `call_mcp_tool` + Parser + Reranker-Hook). — **5-1c (Teilstück von 5-1, damit 5-1 KOMPLETT) call_mcp_tool-Client ✅ (2026-07-11)** `services/mcp/client.py` — Port ALT `mcp_client.py` (379 Z.; dort zusätzlich Re-Export-Fassade → im NEU-Baum importieren Konsumenten direkt aus den Leaf-Modulen, sodass nur der Eigen-Code bleibt): `call_mcp_tool` (Orchestrierung `_get_server_url_for_tool` → `validate_tool_args` → `TOOL_PREPROCESSORS`-Pipeline → outputFormat-json-Injektion → Cache-Lookup/Blocklist + Meta-Re-Emit → `transport.call_tool` → Fehler→Retry-once → `_queryMeta`-Extraktion → `get_subject_portals`-Kompaktierung → cache_set), `_query_metas`-ContextVar (+`reset_query_metas`/`get_query_metas`), `_compact_subject_portals`, `_get_server_url_for_tool`. **Late-bound-Shim aufgelöst:** arg_resolvers' `call_mcp_tool`-Shim importiert nun `..client` (lazy, kein Load-Zyklus: client→arg_resolvers am Kopf, Rück-Import in der Shim-Funktion). **3 bewusste Deviations:** (1) Transport-Seam ALT `_ensure_initialized_with_session`+`_json_rpc` → `transport.call_tool` (dict-Form aus 5-1b → Rumpf nahezu verbatim); (2) Retry ohne Session-Reset (Transport öffnet pro Call frische Session → Retry = simpler Zweit-Call, kein modul-globaler Session-State, Regel 3); (3) **weggelassen** `__getattr__`-PEP-562-Shim (`_session_id`/`_initialized`) + `resolve_discipline_labels`-No-op — ALT-Altlasten ohne NEU-Konsument (grep-verifiziert: nur eigener Docstring referenziert sie). Linter: 1× E501 (verbatim `logger.debug` im ohnehin adaptierten `call_mcp_tool`) umbrochen — fidelity-neutral, kein noqa/pyproject nötig. **Verifikation:** mechanischer AST-Diff ALT↔NEU über die 5 vergleichbaren Namen (`_compact_subject_portals`/`_query_metas`/`get_query_metas`/`reset_query_metas`/logger) = **0 Divergenz**; die 2 adaptierten Defs (`call_mcp_tool`/`_get_server_url_for_tool`) + 2 gedroppte Shims korrekt als ausgeschlossen/ALT-only erkannt. Test `tests/test_mcp_client.py` = Port des Client-Clusters aus ALT `test_mcp_client.py` (15 T am `transport.call_tool`-Seam re-verdrahtet: happy-join+cache · outputFormat set/nicht-überschrieben · Retry-Erfolg · Doppel-Fehler→„MCP error"-String+nicht-gecached · `_queryMeta`→ContextVar+Meta-Cache · Cache-Hit-Re-Emit · Nur-Meta→roher-Dump · Blocklist-nie-gecached · Preprocessor-Fehler→Args-durch · subject_portals-Kompakt/Fehlschlag-roh · query_metas-Kopie · compact-pur · server-url Registry/Fallback). Call-Zähler sinken ggü. ALT (Handshake liegt UNTER dem Transport-Seam, in 5-1b getestet). Suite **471 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **5-1 damit KOMPLETT** (tool_cache + transport + client). Offen im Paket: 5-2-Parser (Cards/Swimlanes, `mcp_parsers.py`) → 5-3 Tool-Loop/Prefetch → 5-4 Cards → 5-5 Reranker → 5-6 Direct-Actions/M16. — **5-2 (Teilstück) arg_resolvers ✅ (2026-07-11)** `services/mcp/arg_resolvers.py` — 1:1-Port ALT `mcp_arg_resolvers.py` (579 Z.): Request-Hints (ContextVar `set/get_request_hint`/`set_active_fach`), Selbstheilungs-Resolver (`_find_portal_by_name`/`_resolve_browse_node_id` Fach→UUID+Hint-Override/`_resolve_collection_node_id` Name→Such-UUID+Regex-Fallback), Vokabular-Kette (`_ensure_label_cache` Markdown-Parse+B5-Kein-Latch · `_fuzzy_lookup` Substring-längster · `_llm_vocab_match` LLM-Fallback+FIFO-5000-Cache · `_resolve_filter_uris` Label→URI) + `TOOL_PREPROCESSORS`-Registry (5 Tools). **Dependency-first:** 5-1c `client` importiert `TOOL_PREPROCESSORS` beim Laden; die Resolver rufen `call_mcp_tool` via **Late-bound-Shim** (`from ..client import` lazy → Patch-Ort bleibt `client.call_mcp_tool`, kein Import-Zyklus). **3 bewusste Deviations:** (1) Shim→`..client` (5-1c); (2) `_llm_vocab_match` Transport-Swap ALT `get_client()/get_chat_model()`→`llm.chat_completion` (LiteLLM kein persistenter Client; = `quick_replies_llm`-Muster); (3) `from boerdi.services import llm` top-level (Hausstil, kein Zyklus). Linter-erzwungen (NEU-ruff strenger als ALT): E402 `import contextvars` an den Kopf gezogen; B039/B905 via `# noqa`+Begründung (mutable-Default read-only da `set_request_hints` stets rebindet; zip equal-length by `gather`) → **byte+AST-Parität erhalten**. **Verifikation:** mechanischer AST-Diff ALT↔NEU über **alle 22** nicht-adaptierten Defs = **0 Divergenz** (ausgeschlossen nur `call_mcp_tool`-Shim + `_llm_vocab_match` = die 2 dokumentierten Adaptionen). Test `tests/test_mcp_arg_resolvers.py` = Port des arg_resolvers-Clusters aus ALT `test_mcp_client.py` (28 T: Hints-Cleaning/`0`-überlebt · portal-Match 4 Strategien · browse Fach→UUID/junk+hint/UUID-Override/passthrough · collection Name/Regex/passthrough · norm/fuzzy · label_cache Markdown+Latch-frei · prewarm best-effort · **llm_vocab** cache/NONE/dekoriert/Guards/non-URI+Exception gegen gefaktes `llm._acompletion` · filter_uris Label/URI-passthrough/LLM-Fallback · Registry-Verdrahtung). Suite **456 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. Offen in 5-1: **5-1c** Client-Kern (jetzt entsperrt: `call_mcp_tool` verdrahtet tool_cache + transport.call_tool + `validate_tool_args` + **`TOOL_PREPROCESSORS`** + `_queryMeta`-Extraktion + Retry + `_compact_subject_portals` + `_get_server_url_for_tool`; ALT `mcp_client.py` 379 Z.). **5-1b (Teilstück von 5-1) transport-SDK ✅** `services/mcp/transport.py` — ALT `mcp_transport.py` (317 Z. hand-gerolltes HTTP/JSON-RPC 2.0 + SSE + Handshake + Per-URL-Session-State) **auf das offizielle `mcp`-SDK (streamable HTTP) umgebaut** (Spec §5-1 „→SDK"): `_json_rpc`/`_parse_sse`/`_parse_response`/`_ensure_initialized_with_session`/`_build_headers`/`_get_http_client` entfallen ersatzlos (SDK macht Framing/SSE/Handshake/Session-ID). Übrig: dünner Adapter — `resolve_mcp_url` (settings/Override/Leer-Fallback/Trailing-Slash, aus ALT `MCP_URL`), `_open_session` (SDK-Seam: `streamablehttp_client`→`ClientSession`→`initialize`), `call_tool`→ALT-`_json_rpc`-Dict-Form (`{"result":{"content":[…]}}`/`{"error":{"message":…}}`, SDK-`CallToolResult` hier normalisiert → 5-1c portiert nahezu verbatim), `discover_server_tools` via `list_tools`. **Design-Entscheide (dokumentiert im Modul-Docstring):** (1) **Session pro Call** statt ALT-Keep-Alive — die statefulle SDK-`ClientSession` ist unter Multi-User-Nebenläufigkeit NICHT teilbar (eigener Request-ID-Zähler/Streams); pro-Call ist korrekt + Regel-3-sauber (kein modul-globaler Session-State); der 5-1a-Cache sitzt davor → Handshake nur bei Miss. Funktionale Parität bleibt (Handshake→Call→Result je Call). (2) `call_tool` **total** (jeder Transportfehler → Fehler-Dict statt Exception) — ALT ließ Connection-Errors zur Tool-Loop propagieren; NEU vereinheitlicht sie in den Retry-Pfad von 5-1c (netto identische graceful Degradation). `simplify:` (Perf): geteilter httpx-Keep-Alive-Pool via `httpx_client_factory` + 5s-Connect-Cap (ALT `MCP_MAX_CONNECTIONS`) spätere Iteration. **Verifikation:** 9 frische Charakterisierungs-Tests gegen gefakte `_open_session` (ALT-`_json_rpc`-Tests prüfen die entfernte Handroll-Schicht → nicht portierbar): resolve-URL (3), call_tool Normalisierung/Args/isError→Fehler/Exception→Fehler/Multi-Block (5), discover-Mapping+Filter (1). **+ Live-Smoke gegen den echten WLO-MCP:** `discover_server_tools` = **12 Tools** (deckt sich mit 5-2 `TOOL_DEFINITIONS`), `call_tool("wlo_health_check")` → `{"result":…}` mit `"ok":true` → SDK-Draht (`_open_session`, den die Fakes nicht abdecken) end-to-end belegt. Suite **428 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. Offen in 5-1: **5-1c** Client-Kern (`call_mcp_tool` verdrahtet tool_cache + transport.call_tool + `validate_tool_args` + Preprocessors + `_queryMeta`-Extraktion + Retry + `_compact_subject_portals`; ALT `mcp_client.py` 379 Z.). **5-1a (Teilstück von 5-1) tool_cache ✅** `services/mcp/tool_cache.py` — 1:1-Port ALT `mcp_tool_cache.py` (LRU-`OrderedDict` + Per-Tool-TTL `_TOOL_CACHE_TTL_PER_TOOL` + Negativ-Cache `__NEG__::`-Sentinel + Hit/Miss/Neg-Stats + `_TOOL_META_CACHE`-Mit-Eviction [B5-Kopplung]; `_cache_key`/`_cache_get`/`_cache_set`/`_ttl_for_tool`/`_is_empty_response`/`get_tool_cache_stats`/`clear_tool_cache`). **Modul-globaler mutabler State bewusst beibehalten** — Eiserne Regel 3 erlaubt „MCP-TTL-Cache pro Prozess … da nur Performance" ausdrücklich (kein DI nötig, Cluster-safe da nur lokale Perf). Reiner stdlib-Port (json/time/collections), kein Netzwerk. Deviation ggü. ALT: nur Modul-Docstring + **1× `UP037`** (Forward-Ref-Quotes am `_TOOL_CACHE`-Annotation entfernt; unter `from __future__ import annotations` verhaltens-inert — NEU-ruff hat `UP`, ALT nicht). **Verifikation:** ganzes Modul-AST ALT↔NEU identisch (modulo Modul-Docstring) VOR dem Fix; nach dem Fix: alle 7 Funktions-Bodies + alle Modul-Assignment-**Values** identisch, einzige Divergenz = die inerte `_TOOL_CACHE`-Annotation → **0 Verhaltens-Divergenz**. Test `tests/test_mcp_tool_cache.py` = Port ALT (9 T: key-order-unabh./differ + `_is_empty_response` 6 Fälle + per-tool/default-TTL + set/get-Hit + miss-None + **Negativ-Marker-Strip+neg_hit** + clear-reset + stats-shape). Suite **419 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. Offen in 5-1: **5-1b** Transport (ALT `mcp_transport.py` 317 Z. → offizielles `mcp`-SDK streamable-HTTP) + **5-1c** Client-Kern (`call_mcp_tool` verdrahtet Cache+Transport+`validate_tool_args`, ALT `mcp_client.py` 379 Z., 887-Z.-Test). **5-2 (Teilstück) tool_defs ✅** `services/mcp/tool_defs.py` — 1:1-Port ALT `mcp_tool_defs.py` (pure, zustandsloser Leaf des neuen `services/mcp`-Pakets): `TOOL_DEFINITIONS` (12 OpenAI-Function-Defs), `_TOOL_ARG_MODELS` (10 Einträge), `validate_tool_args` (Pydantic-Validierung + Leerstring-Strip; C7-Fix `v != ""` erhält explizite `False`/`0`), `_JSON_CAPABLE_TOOLS` (9). Arg-Modelle NICHT neu portiert — bereits in `api/schemas_mcp.py` (P0-5), Import über Fassade `boerdi.api.schemas`. Deviations ggü. ALT: nur Modul-Docstring + Import-Pfad; lange LLM-facing Tool-Beschreibungen verbatim → per-file `E501`-ignore in pyproject (wie QR/Prompt/regex_gate). **Verifikation:** mechanischer Diff ALT↔NEU (literal_eval/AST, ohne Import) = `TOOL_DEFINITIONS` deep-equal (12≡12), `_JSON_CAPABLE_TOOLS` gleich, `_TOOL_ARG_MODELS` gleich (10), `validate_tool_args`-Body AST-**identisch** → **0 Divergenz**. Test `tests/test_mcp_tool_defs.py` = Port ALT (7 T: passthrough/Defaults/leer-bleibt-leer/**C7 False-Pin**/Defs-Shape/JSON-Set/Arg-Models). Suite **410 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **Entsperrt 3-3b** `_select_active_tools` (`TOOL_DEFINITIONS` jetzt in NEU vorhanden). Offen im Paket (Stand dieses alten Eintrags, Suite-410-Ära): 5-1, 5-2-Rest, 5-3, 5-4, 5-5, 5-6 — **inzwischen überholt: alle ✅ bis auf 5-6-Rest M16-Resolver (Tool-Loop 3/3 ✅ R1 · Direct-Actions ✅ R5, je 2026-07-18); aktueller Stand am Zeilenkopf + in der P5-Detailtabelle.** |
> | P6 RAG & Reranker | ✅ im Kern 2026-07-17 (offen NUR 6-3 Reranker-Backend = Nutzer-A/B-Entscheid) | 6-1 Retrieval-Pfad ✅ (chunking + retrieval-settings + embedding-Seam + pgvector-Cosine `search_rag_chunks`/`query_rag` + rerank-Seam V13 + `get_rag_context`) · 6-2 Router ✅ (0 Stubs: query / ingest file/url/text / Admin-CRUD ×5 / embed) · 6-4 Import-CLI ✅ (`boerdi import-rag`, ALT-sqlite→pg re-embed, Quell-DB read-only SHA-gepinnt). pg-Beweise gegen echtes pgvector: Cosine-Suche, CASCADE, SAVEPOINT-je-Chunk, import-rag-CLI-e2e (62 pg-Tests liefen, Suite 1470/2 mit pg oben); Ragas-Vergleich + Reranker-A/B = Nutzer-Domäne |
> | P7 Feature-Parität Rest (Golden 12/12) | ⬜ offen | — |
> | P8 Widget | ✅ 2026-07-25 (8-1 ✅ 2026-07-24 | Angular-21-Workspace (zoneless, `projects/ui` pfad-gemappt + `widget`-App). `build-widget` **110 kB raw / 32,8 kB gzip** (≪ §5.5-Budget 420/140; ALT war 455 kB *mit* zone.js). `npm test` = `ng test ui && ng test widget` → **ui 6 + widget 2 = 8 grün** (Vitest, exit 0). `provideZonelessChangeDetection` als stabile 21.2-API verifiziert. Abweichungen: `ui`=Shared-Source-Barrel ohne ng-packagr (nie publiziert), `studio`-Projekt→P9 (kein spekulatives Leergerüst), kein Angular Material im Widget (Budget). **8-2a `session/` ✅ 2026-07-24**: `ui/session/{session-id,trusted-host}.ts` verbatim-Port + V5-`buildTrustedDomains` (Core-WLO-Domains immer + backend + attr, normalisiert/dedup — ALT-Asymmetrie Chat-prependet-Core vs Widget-nur-merge aufgelöst); 23 Charakterisierungs-Specs (bsid-Injektions-Guard, Subdomain-Suffix ohne Confusion, `withBsid`-Gating, URL→Cookie→localStorage-Precedence + bsid-URL-Strip); `link-handoff`→8-4; **ui 29 + widget 2 grün**. **8-2b markdown ✅ 2026-07-24**: volle `MarkdownRenderer`-Klasse verbatim → `ui/markdown/{markdown-renderer,latex}.ts` (marked→DOMPurify-Policy identisch: `ADD_ATTR target/rel/data-bb-type` + `USE_PROFILES html/svg`) + `ui/icons/icons.ts` (Inline-SVG, kein Font-CDN); 13 Specs (XSS-Defang script/onerror/`javascript:`, Trusted-bsid, Canvas-Sentinel-Strip, `@@ICON@@`→Label, FIFO-Cache); Seam `MarkdownRenderContext` (bypassSecurityTrustHtml/isHostTrusted/withBsid)→Widget-Shell 8-4; **ui 42 + widget 2 grün**, Bundle 173/51,8 kB gzip ≪ Budget (marked+DOMPurify via Barrel, ab 8-4 genutzt). **8-2c chips ✅ 2026-07-24**: `ui/chips/{action-qr,guide-qr}.ts` verbatim — ALT `action-qr.spec.ts` **verbatim mitportiert** (grün) + guide-qr-Charakterisierung; QR-Typen §5.5 Text/`__guide__`/`__action__` (Label/URL-Extraktion, params-JSON-Split-nur-erste-2-Pipes, kaputt→null-Fallback, Lotsen-Modus-Gating); 17 Specs, **ui 59 grün**. **8-2d page-context-detector ✅ 2026-07-24**: `ui/page-context/page-context-detector.ts` verbatim-Port (URL+DOM→`DetectedContext`, wirft nie — jeder DOM-Zugriff try/catch, malformed-`filters`-JSON gefangen; UUID/SLUG-Allowlist + Längen-Caps an Host-Trust-Boundary); ALT-Spec **verbatim mitportiert** = 7-URL-Golden (render/collections/themenseite/fachportal/topic-pages-vor-collection/bare-search/`?q`) + Publisher-Filter + Host-Agnostik staging≡prod, 14 Specs; DOM-/Orchestrierungs-Layer fidelity-portiert (URL-Layer getestet wie ALT — jsdom navigiert nicht); Datei 311 Z. = dok. Port-Ausnahme; Bundle unverändert 173,7/51,8 kB (tree-geshaked bis 8-4); **ui 73 + widget 2 grün, exit 0**. **8-2e cards-Logik ✅ 2026-07-24**: `ui/cards/{card-types,card-utils}.ts` verbatim — `WloCard`-Typ aus ALT-`api.service`-Monolith herausgetrennt + 6 Card-Helfer (URL-Fallback-Kette topic_pages→link→guide_url→wlo_url→url→'#', 3-Wege-Klassifikation Themenseite/Sammlung/Inhalt disjunkt+vollständig, Icon/Label-Wahl); ALT `card-utils.spec.ts` **verbatim mitportiert** (10 Golden-Klassifikations-Fälle) + Render-Charakterisierung 8 Specs (Link/Icon/Label, vorgezogen weil Tile sie gleich konsumiert); alle 12 ICONS-Keys vorab verifiziert; Bundle unverändert 173,7/51,7 kB; **ui 91 + widget 2 grün**. **8-2f WloCard-Tile ✅ 2026-07-24**: erster echter Angular-Komponenten-Build — `ui/cards/wlo-card-tile.component.{ts,scss}` (standalone, OnPush, Signals `input`), visueller Verbatim-Port der ALT-`.wlo-card` (chat.component.html:246-294): Header (Typ-Icon+Label), Body (Titel, 120-Zeichen-Desc, Thumb+Lizenz-Badge), Footer (Stufe/Fach); präsentational — `href`/`tooltip` als Inputs (= ALT `cardUrl`/`cardTooltip`; Session-/Trusted-Host-Logik bleibt beim Elternteil), Klassifikation/Icon/Label/Lizenzkürzel aus portierter Logik. Prereqs mitportiert: `SafeSvgPipe` (ALT `shared/safe-svg.pipe.ts` verbatim → `ui/icons/`) + `getLicenseShort` (ALT `chat-text-utils.ts` verbatim → `ui/cards/license.ts`, 6-Branch-Spec). SCSS byte-nah (ALT `$brand-blue #1c4587` etc. als lokale Vars, bewusst NICHT ans kundenüberschreibbare `--boerdi-primary` gebunden) + additiver `prefers-reduced-motion`-Block (a11y). TestBed-Komponenten-Spec (3 Karten-Arten: Link-Attr/`is-*`-Klassifikation/Label/Icon-SVG/Desc-Kürzung/Thumb+Lizenz/Footer/Leerzustände) fand echten Bug: `[title]="null"` schrieb ein title-Attribut → auf `[attr.title]` gefixt (ALT-Intent „null lässt title weg"). `@if` statt `*ngIf` (Angular-21), DOM gleich. **ui 100 + widget 2 grün, exit 0**; Bundle 173,7/51,8 kB gzip (Tile/Pipe tree-geshaked bis Widget-Konsum). **Re-Slice** (8-2f-Bündel war nicht ein Slice): 5-Box-Typen (Themenseiten/Sammlungen/Materialien/Webseiten/Search-CTA) brauchen `result-grouping.utils.ts`-Port + `ChatMessage`-Typ → **8-2g** (Logik) + **8-2h** (Box-Render); Flat-Cards-Grid+Pagination+`.card-actions` hängen an Chat-Shell-State/-Methoden → **8-2i** (nach 8-4). **8-2g result-grouping ✅ 2026-07-24**: `ui/grouping/result-grouping.ts` **verbatim**-Port des ALT `chat/result-grouping.utils.ts` — alle `grouped*`-Box-Selektoren (Themenseiten/Sammlungen/Materialien: dedup per node_id∨norm.Titel + Limit aus displayRules), `groupedSearchUrl` (Tool-Priorität content>collections>topic_pages + repository_url-Fallback-Komposition), `groupedWebLinks` (webLinks→debug._web_links→Content-Regex; type-focus→[]), `displayContent` (Bullet-Link-Strip mit den 2 ALT-Regexes), `itemTooltip`/`cardTooltip`/`searchCtaTooltip`, `hasGroupedResults`, `GroupingContext` — KEINE Logik-Änderung; + `ui/grouping/message-types.ts` (schmaler `ChatMessage` = nur die 6 Grouping-Felder, wächst mit Chat-Shell 8-4; `QueryMetaEntry`/`WebLink` voll verbatim). ALT ohne eigene Spec → 25 Charakterisierungs-Specs (Dedup/Limits/Such-URL-Fallback/WebLinks-Kette/Content-Strip/Tooltips/Visibility). Datei 364 Z. = dok. Fidelity-Ausnahme (wie ALT eine Datei). **ui 125 + widget 2 grün, exit 0**, Bundle 173,7/51,8 kB (tree-geshaked). **8-2h ResultGroups-5-Box-Renderer ✅ 2026-07-24**: `ui/grouping/result-groups.component.{ts,scss}` — visueller Verbatim-Port des ALT Inline-Result-Grouping-Blocks (chat.component.html:133-236 + `.result-group*`-SCSS 433-702): 4 List-Boxen (Themenseiten/Sammlungen/Materialien/Webseiten-Inhalte) + Such-CTA (`_self`/`_blank` je `isTrustedSearchUrl`), konsumiert die 8-2g-Grouping-Utils + `getCardIcon`. Wrapper self-gated auf `hasGroupedResults` (ALTs „kein leerer Rahmen" + Tour-Unterdrückung); Host-Flags (`inline-result-grouping`/`hideCards`) bleiben beim Elternteil (8-4). `ResultGroupsContext extends GroupingContext` + `isTrustedHost` (einzige Extra-Abfrage über den 8-2g-Seam, für die CTA-Target-Entscheidung). `*ngIf`→`@if`/`*ngFor`→`@for track $index`, `[title]`→`[attr.title]` (null lässt Attribut weg, wie 8-2f); SCSS byte-nah (lokale `$border/$text/$text-muted` wie Tile, CTA-Akzent am `--boerdi-primary`) + additiver `prefers-reduced-motion`. 7 TestBed-DOM-Specs (5 Boxen/Item-hrefs+Titles/CTA-Term±/Target _self±_blank/Leer+Tour-Unterdrückung). Dateien 233/146 Z. (< 300). a11y-Feinschliff (Heading-Semantik/aria-hidden Icons/Fokus) → koordinierter Sweep 8-6. **ui 132 + widget 2 grün, exit 0**, Bundle 173,7/51,8 kB (tree-geshaked). **swimlanes ✅ 2026-07-24**: `ui/grouping/swimlanes.component.{ts,scss}` visueller Verbatim-Port ALT Themenseiten-Schwimmlinien (chat.component.html:97-131) — je Swimlane `result-group--topic`-Box + Themenseiten-CTA (rohe `topic_page_url`, immer `_blank`, kein withBsid — wie ALT); `SwimlaneBox`/`TopicPageView` verbatim aus ALT api.service → message-types.ts; `.result-group`-SCSS mit 8-2h geteilt via extrahiertem `_result-group.scss`-Partial (behavior-preserving Refactor, byte-identisch verschoben, beide Komponenten `@use`); `swimlanes ?? []` defensiv im TS (kein NG8107); 3 TestBed-DOM-Specs; **ui 135 + widget 2 grün, exit 0**, Bundle 173,7/51,8 kB. **inline-doc ✅ 2026-07-24**: `ui/inline-doc/{inline-doc.ts, inline-documents.component.{ts,scss}}` visueller Verbatim-Port ALT `.inline-document`-Box (chat.component.html:37-52 + SCSS 450-564) — Lernpfade/KI-Materialien/Edits: je Doc Kind-Icon+Titel/Fallback+Print-Button+Markdown-Body; `InlineDocument`-Typ verbatim → message-types.ts; präsentational — `renderMarkdown`-Fn-Seam (MarkdownRenderer 8-2b liefert sanitisiertes SafeHtml) + `print`-Output (print-utils→8-4); 3 pure Helfer `inlineDoc{FontSize [Klammer 70-100/Default 85], Icon, FallbackLabel}` verbatim; 6 Specs (3 Helfer + 3 TestBed-DOM); **ui 141 + widget 2 grün, exit 0**, Bundle 173,7/51,8 kB. **8-2-Renderer komplett.** **8-3 Stream-Client ✅ 2026-07-24** (`ui/stream/stream-client.ts` — s. Task-Zeile 8-3: streamChat SSE-Kern + Watchdogs 90/100 s + postChat-Fallback, 11 Specs, ui 152 grün). **8-4 Chat-Shell ✅** (in Sub-Slices a–f zerlegt), **8-2i Flat-Cards ✅**, **8-5 Element-Definition ✅**, **8-6 A11y+States ✅**, **8-7 E2E+Budget ✅** — Details je Slice in den Task-Zeilen unten. **P8 abgeschlossen**: `<boerdi-chat>` ist ein echtes Custom Element mit allen 6 §5.5-Methoden, **ui 454 / widget 29 / E2E 28 grün**, `npm run lint` exit 0, Bundle **412,77 kB raw / 128,09 kB gzip** (§5.5 420/140 — raw ist mit ~7,2 kB Puffer die bindende Grenze), CI-Job install→lint→unit→Lizenz→build→budget→e2e. Nutzer-Domäne offen: Compose-Live-Lauf, Screenreader-Durchgang, 200-%-Zoom am Gerät. |
> | P9 Studio | ✅ **komplett 2026-07-26** — 9-1 ✅ · 9-2 ✅ · 9-3 ✅ · 9-4 ✅ · 9-5 ✅ (a–f) · 9-6 ✅ (Sicherung + Vorschau) | **9-4e „Wissen" ✅** schließt 9-4 ab: drei Panels (RAG-Bereiche+Dokumente aus der DB, Ingest Datei/Webseite/Text, MCP-Registry+Discover) neben EINEM Config-Abschnitt. Dabei eine **echte Lücke im eigenen Backend gefunden und geschlossen**: die MCP-Registry liegt im Bereich `05-knowledge/mcp-servers`, und die zwei generischen Schreibwege aus 9-3 (`PUT /config/data/{area}` und `PUT /config/file`) umgingen den SSRF-Check, den `PUT /config/mcp-servers` seit 2-5 hat — beide Bypässe nachgestellt (200 mit `http://169.254.169.254/mcp` in der Registry), dann per Area-Gate geschlossen. **Backend 66 Config-/MCP-Tests grün · studio 307 · OpenAPI unverändert.** · **9-3 SchemaForm ✅**: generischer Bereichs-Editor — **jeder** der 35 Config-Bereiche ist jetzt editierbar (V3), im Formular oder im Rohtext, erreichbar über die neue View „Alle Bereiche". Ohne formly und ohne Monaco (Entscheid mit Messwerten in der Task-Tabelle). Neuer Backend-Endpunkt `GET/PUT /api/config/data/{area}`, weil das exportierte Schema bis dahin kein JSON-Gegenstück hatte. Kern-Erkenntnis: **357 ungepinnte, verschachtelte Config-Pfade** ⇒ das Formular editiert das ganze Dokument, PUT ersetzt. Review fand **6 MAJOR** — allesamt Wege zu stillem Datenverlust in der eigenen Oberfläche (u.a. `arr[NaN]`-Schreibvorgänge, die spurlos verschwanden, und ein Speichern über einem offenen JSON-Fehler) — alle behoben und getestet; beim Fixen fiel ein vorbestehender **500 statt 400** bei kaputtem YAML auf. **Backend 2009 pytest + 2 skips · studio 225 grün · 12/12 Live-Checks gegen echtes PG + gebautes SPA.** · **9-1 studio-bff ✅**: In-Process-Rewrite `/studio/api/*`→`/api/*` (ASGI-Middleware) statt HTTP-Proxy, ALT-Token verbatim (Cookie-Interop für den Cutover), Härtungen fail-closed / Header-Trust-Boundary / Login-Limit, SPA-Mount `/studio`. Review fand **1 echten CRITICAL** (`BOERDI_ALLOW_OPEN_ADMIN` hätte einen konfigurierten `STUDIO_API_KEY` ausgehebelt) + 1 unauth. 500 (non-ASCII-Cookie) — behoben, mit Tests. **9-2 Studio-Shell+Auth ✅**: neues `projects/studio` (Angular 21 zoneless + Router), 16-View-Registry als EINE Quelle für Routen+Nav, Login/Guard/Logout/401-Interceptor, validierter `?from=`-Redirect, a11y-Floor (Skip-Link, `aria-current`, `role=status`, echte Labels) und responsive Drawer — beides in ALT gar nicht vorhanden. **Backend 1986 pytest grün + 2 skips · studio 49 grün · eslint 0 · build 255,97 kB.** Details je Slice in der P9-Task-Tabelle |
> | P10 Cluster & Betrieb | ✅ **komplett 2026-07-27** — P10-1 Prod-Image · P10-2 compose.prod.yml · P10-3 §8-Checkliste als Testprotokoll · P10-4 Runbook + Security-Checkliste · P10-5 Image-Gate in CI · P10-6 Speicher auf Valkey | Ein Image für API + Widget + Studio, **Frontend im Image gebaut** (beendet ALTs häufigsten Deploy-Fehler); Stack aus postgres→redis→migrate→backend ×3 live hochgefahren, alle drei Replikas `healthy`, Backup+Restore wörtlich durchgespielt. **Kein TEI** (V13), `redis` als Abhängigkeit nachgezogen (Nutzer-Entscheid). Belege im Abschnitt „Betrieb (P10)". |
> | P11 Migration & Cutover | ⬜ offen | — |
>
> **Restplan — Abarbeitungs-Reihenfolge der offenen Pakete (Stand 2026-07-18, dependency-geordnet, ALT-Quellen vermessen):**
> **R1** Tool-Loop fertigstellen (5-3): `_assemble_messages` (~326 Z.) ✅ 2026-07-18 → `_run_tool_loop` (~560 Z.) ✅ 2026-07-18 (inkl. R1b-1 Streaming-Zwilling `services/llm_streaming.py`) → `generate_response`-Orchestrator ✅ 2026-07-18 (`services/generate.py`, Verbatim-Port + session-Seam, AST 7 Stmts ident modulo 3 Seams, 4 Pins; Prefetch-KONSUM verdrahtet, Launch = R4/turn_setup) → **R1 komplett**
> **R2** Turn-Setup-Nodes (**4-2b preflight ✅** · **4-2c tour ✅** 2026-07-18 [je Node-Test] · **4-2d context_greeting ✅ 2026-07-23** [#116, `graph/nodes/context_greeting.py`, früher Kurzschluss tour→persist_user; Greeting-Text latent bis setup `resolve_page_context` ruft]) → R2 komplett →
> **R3** pg-Persistenz-Gruppe (**R3a ✅** `db_sessions`-Memory-Port [9 Fn] + **R3b ✅** 3-5 DB-Logging-Writer [`obs/quality_events.py`, 6 pg-Pins], beide 2026-07-18 → **R3 komplett**; Logging-Aufruf+Gate im Persist = R4) →
> **R4** Endpoint-Schicht (4-5: `_setup_turn`/`_classify_and_merge` [`chat_turn_setup.py` 550 Z.] → `_produce_answer` [`chat_turn_answer.py` 522 Z.] → `_chat_impl` + POST /api/chat + /stream-SSE [`chat.py` 557 Z., Event-Namen byte-ident] · 4-6: Persist-Node + graph/build + Checkpointer) — **R4-Decomposition (Scope-first 2026-07-18, aktualisiert nach dem merge-Befund): R4b setup-Node ✅ 2026-07-18 (`graph/nodes/setup.py`, 9 Pins) → **R4d merge-Node ✅ 2026-07-18** (`graph/nodes/merge.py`, 13 Pins, state.py +7 `spec_*`-Felder; P5-9-Entity-Seite: turn_type-Entity-Merge/placeholder-Filter/material-Heuristik/I05/spec-prefetch-launch — ECHTER Node, NICHT der vermutete no-op-Check; `route.select_pattern` braucht die gemergten entities → korrekte Reihenfolge **assess→merge→route→respond**; respond hängt an merges `spec_*`-Feldern, state.py um 7 Felder erweitern) → **R4c respond-Node ✅ 2026-07-19** (`graph/nodes/respond.py`, 15 Pins, state.py +`wlo_cards_raw`; ALT `_produce_answer` P16-19; 4 Deviationen: session/on_token-DI, tracer+resolve_discipline_labels+run_in_rerank_pool gedroppt [CE-Gate sync]) → **R4g assemble-Node ✅ 2026-07-19** (`graph/nodes/assemble.py`, 6 Pins, P20-24-Adapter über turn_assembly #71) → **R4-persist-Prereqs #114 ✅ 2026-07-19** (chat_facets → domain/facets.py + _spawn_background → obs/tasks.py; _display_rules via load_display_rules_config direkt) → R4a persist-Node [ENTSPERRT; M16-Resolver=R6-vertagt] → R4e graph/build.py → R4f api/chat.py-Endpoint; Detail im Topic-Memory** = **Meilenstein erster e2e-Chat-Turn + Golden-Teilmenge „reine Text-Flows"** →
> **R5** 5-6-Rest — **Direct-Actions ✅ 2026-07-18** (`services/direct_actions.py`: browse/curate/lernpfad + `_direct_action_safety_text`, DI-Rewrite, 14 Pins; Dispatch = R2-preflight); **M16-Resolver ✅ 2026-07-24** (`_resolve_m16_topic_page_view` → `services/topic_pages.py`, verdrahtet in `turn_persist.persist_and_build_response` [ersetzt R6-STUB `topic_page=None`]; #120) → **R5 komplett** →
> **R6** P7-Rest, bereinigt — **page_context ✅ + 6 Backend-Router ✅ 2026-07-24** (sessions/speech/quality/safety/eval/loadtest, 42 Ep., #121 Subagent-Fan-out; 2 slowapi-Prod-500 nebenbei gefixt; pytest 1953/2). **Offen: Widget-Auslieferung + Demo-Seiten = P8** (frontend/ leer). Restfeinheiten: generative eval-Engine, golden-judge, psutil. (s. P7-Abschnitt) → **Golden 12/12** →
> danach P8 Widget → P9 Studio → P10 Cluster → P11 Cutover. (6-3 Reranker-A/B = Nutzer-Domäne, jederzeit parallel.)

---

## 0. Eiserne Regeln für den Implementierer (gelten in JEDEM Paket)

1. **Lizenz-Gate:** Nur MIT / Apache-2.0 / BSD / PSF / PostgreSQL-Lizenz. Vor JEDER neuen
   Dependency Lizenz prüfen (`pip-licenses` / `license-checker` läuft in CI, Task P0-6).
   Explizit VERBOTEN (geprüft 2026-07-10): `shepherd.js` (AGPL-3.0), `intro.js` (AGPL),
   Arize `phoenix` (Elastic License 2.0).
   **Dokumentierte Einzel-Ausnahme (P0-6, 2026-07-11):** `psycopg`/`psycopg-pool`
   (LGPL-3.0-only) kommen transitiv über das in §2 gesetzte
   `langgraph-checkpoint-postgres` und werden unverändert per Import genutzt
   (schwaches Copyleft, kein Code-Einfluss). Sie stehen im CI-Gate als explizite
   `--ignore-packages`-Ausnahme; JEDE weitere GPL/AGPL/LGPL/SSPL/Elastic-Dependency
   bricht den Build. Rückbau-Pfad: eigener asyncpg-Checkpointer, falls die Ausnahme
   fallen soll.
2. **Parität vor Schönheit:** Die Inventare in §5 sind die Checkliste. Kein Feld, kein
   Endpoint, kein Attribut wird weggelassen, ohne dass §5 hier im Doc geändert wurde.
3. **Kein modul-globaler veränderlicher State** im Backend (Cluster!). Caches nur über die
   dafür vorgesehenen Stellen (Config-Cache mit NOTIFY-Invalidierung, MCP-TTL-Cache pro Prozess
   erlaubt, da nur Performance). Session-Serialisierung NUR über Postgres Advisory Locks.
4. **Domäne framework-frei:** `backend/src/boerdi/domain/**` importiert weder FastAPI noch
   LangGraph noch SQLAlchemy — nur stdlib + pydantic. Graph-Nodes sind dünne Adapter.
5. **Portieren = Test zuerst:** Zu jedem portierten Modul wird ZUERST die zugehörige
   Bestands-Testdatei portiert (Patch-Pfade anpassen), rot laufen gelassen, dann das Modul.
   Die Alt-Tests sind die Verhaltens-Spezifikation.
6. **Byte-genaue Verträge:** Magic-Präfixe `__guide__|` und `__action__|<label>|<action>|<json>`,
   Element-Name `<boerdi-chat>`, Pfad `/widget/boerdi-widget.js`, SSE-Event-Namen
   (`connected`/`phase`/`result`/`error`), Session-ID-Format `bb-<uuid>` — identisch zu ALT.
7. **Dateigrenze ~300 Zeilen**, Funktionen ~50 — beim Portieren großer Alt-Module direkt am
   Verantwortlichkeits-Schnitt splitten (die Alt-Zerlegung gibt die Schnitte bereits vor).
   **`Fidelity-Port-Ausnahme` (ergänzt 2026-08-13, Audit F-8):** die Klammer oben trifft nicht
   immer zu. Wo ALT selbst *eine* Funktion hat, ist Zerlegen kein Verschieben, sondern ein
   Rewrite — und gibt das AST-Gate auf, mit dem der Verbatim-Port gegen die Vorlage abgenommen
   wurde; dasselbe gilt für einen geordneten Daten-Literal, dessen Reihenfolge tragend ist.
   Solche Dateien dürfen über der Grenze liegen, wenn **alle drei** Punkte gelten:
   (a) der Überhang steckt in EINER Funktion bzw. EINEM Literal — nicht in mehreren
   Verantwortlichkeiten, die man trennen könnte; (b) der Modul-Docstring (Python) bzw. der
   Kopfkommentar (TS) trägt das Wort **`Fidelity-Port-Ausnahme`** und begründet sie, damit
   `grep -r "Fidelity-Port-Ausnahme"` alle Ausnahmen des Repos auflistet — Backend und
   Frontend gleichermaßen; (c) es kommt nichts Neues hinzu — neue
   Verantwortlichkeiten wandern in ein eigenes Modul, die Ausnahme ist kein
   Wachstumsfreibrief. Sie **erlischt mit dem Cutover**: sobald ALT abgeschaltet ist, bindet
   das AST-Gate nicht mehr, und die Dateien werden regulär zerlegt. Eine Datei über 300 Zeilen
   **ohne** dieses Wort ist keine Ausnahme, sondern unentschiedene Schuld.
8. **Secrets nur aus Env** (pydantic-settings); nie loggen, nie in Responses. Fehlermeldungen
   nach außen generisch (Audit-Erbe: Speech-502 generisch, keine Stacktraces).
9. **Sicherheits-Erbe ist Anforderung ab Tag 1:** SSRF-Guard für alle ausgehenden URL-Fetches
   (Ingest!), Zip-Entpack-Caps (600 MB Budget, Pfad-Traversal-Schutz), Security-Header-
   Middleware, FK-Enforcement, Upload-Größen-Caps (`BOERDI_MAX_INGEST_MB`), non-root-Container,
   Rate-Limit auf public Endpoints, CORS restriktiv konfigurierbar.
10. **Deutsch ist Inhalts-, Englisch ist Code-Sprache:** Alle nutzersichtbaren Texte kommen aus
    Config/DB (de). Identifier, Kommentare, Commits englisch. UI-Chrome-Strings über Angular
    `$localize` (Quellsprache de).
11. **Golden-Gate:** Ab P4 läuft nach jedem Paket die Golden-Flow-Suite (12 Flows GS-1…GS-12)
    gegen NEU; die Paket-Abnahme nennt die erwartete grüne Teilmenge. Volle Suite grün = P7.
12. **Keine Feature-Erfindungen:** Nur die in §3 gelisteten bewussten Verbesserungen. Alles
    andere ist 1:1-Parität.

---

## 1. Ziel & Kontext

**Ziel:** Cleaner Neubau der drei Elemente (Backend, Chat-Widget als Angular-Webkomponente,
Studio/Webadmin als Angular-SPA) im neuen Monorepo `boerdi-chat/` — clusterfähig (N stateless
Backend-Replikas, Postgres statt SQLite), minimaler Eigencode durch maximale Nachnutzung
etablierter OSS (nur MIT/Apache/BSD-artig), bei **vollständiger** Funktions- und
Konfigurations-Parität zum heutigen BadBoerdi. Generisch: Der Bot bleibt über deklarative
Config (Personas/Intents/Patterns/States/…) auf andere Domänen umstellbar.

**Warum Neubau statt Umbau:** Frontend-Vereinheitlichung (ein Angular-Workspace, geteilte
UI-Lib statt Next.js-Studio + Angular-Widget), Cluster-Fundament (SQLite → Postgres) und
Orchestrierungs-Vereinfachung (`_chat_impl`-Erbe → LangGraph) zusammen machen den Umbau im
Bestand teurer als den Neubau mit Portierung der bereits sauber geschnittenen, getesteten
Domänen-Module (die Zerlegungs-Kampagne 2026-07 hat genau diese Schnitte geschaffen).

**Scope:**
- **In:** alles in §5 Inventarisierte; Betrieb via Docker Compose (dev+prod), k8s-ready.
- **Out:** Feature-Redesign; Big-Bang-Cutover (Parallelbetrieb + A/B, §9); Vendor-Bindung
  (LLM bleibt OpenAI-kompatibel hinter LiteLLM); der externe **wlo-mcp-server bleibt
  unverändert** (eigenes Repo, bereits MIT-sauber, wird nur konsumiert); Mehrsprachigkeit
  der Inhalte (Struktur i18n-fähig, Inhalte de).

---

## 2. Verbindliche Stack-Entscheidungen (Lizenz-verifiziert 2026-07-10)

| Zweck | Bibliothek (Version-Pin bei P0) | Lizenz | ersetzt heute |
|---|---|---|---|
| HTTP/API, SSE | FastAPI + uvicorn | MIT / BSD-3 | bleibt |
| Settings/Validierung | pydantic v2 + pydantic-settings | MIT | config_loader-Validierung, os.getenv-Streu |
| Turn-Orchestrierung | **LangGraph** (Library) + langgraph-checkpoint-postgres | MIT | `_chat_impl`-Phasenkette, Session-State-Wiring |
| LLM-Transport (B-API/OpenAI-kompat., Retry, Timeout) | **LiteLLM** (SDK, nicht Proxy) | MIT | llm_provider, Retry-Eigenbau |
| Structured Output (Classify) | **instructor** (`from_litellm`) | MIT | Hand-Parsing + Validierungs-Retries |
| MCP-Client | offizielles `mcp`-Python-SDK (streamable HTTP) | MIT | mcp_transport.py |
| DB | **PostgreSQL 17 + pgvector** | PostgreSQL-Lizenz | SQLite + sqlite-vec |
| ORM/Migrationen | SQLAlchemy 2 async (asyncpg) + alembic | MIT / Apache-2.0 | Hand-SQL, DB-in-Git |
| Rate-Limit | **slowapi** (Storage-URI per Env: `memory://` → `redis://` im Cluster) | MIT | rate_limiter.py |
| Reranker | **In-Proc-Scorer (kein Netzwerk-Dienst, V13)** hinter `card_reranker._get_reranker()`: Cross-Encoder (ALT `mmarco-mMiniLMv2-L12-H384-v1`) / **Bi-Encoder-Cosine (mehrsprachig, teilt 6-1-Embedder)** / lexikalisch / aus — **entschieden 2026-07-17: Embedding-Order-Default** (Bi-Encoder über den geteilten Embedder ≡ pgvector-Retrieval-Ordnung → kein Re-Compute; Seam `services/rag/rerank._get_reranker`, CE-Slot offen) | Apache-2.0 / MIT | In-Proc, `RERANK_*`-Threads-Knöpfe; TEI-Sidecar verworfen (Kosten, Nutzer 2026-07-12) |
| Ingest-Extraktion | MarkItDown + SSRF-Guarded-Session (portiert) | MIT | bleibt |
| Observability | **OpenTelemetry SDK** (+ FastAPI/HTTPX/SQLAlchemy-Instrumentierung) → **Jaeger all-in-one** | Apache-2.0 | Eigen-Tracer + Studio-Trace-Tab (DebugInfo je Turn BLEIBT als Response-Feld — Widget-Debugpanel + Quality-Logs sind Parität) |
| Frontend | **Angular 22** Workspace (3 Projekte, TypeScript 6 — Sprung von 21 am 2026-08-13), Angular Material **M3**, `@angular/elements` | MIT | Next.js-Studio + getrennter Widget-Build |
| Studio-Formulare | **eigener Schema-Renderer** (`schema-to-fields.ts`, JSON-Schema-getrieben) — **ngx-formly 2026-07-25 verworfen** (Begründung in 9-3); MD/MD-Rohtext im `<textarea>`, **Monaco vertagt** | — (keine neue Dep) | handgebaute React-Views |
| Markdown im Widget | marked + DOMPurify | MIT / Apache-2.0∥MPL | bleibt |
| Tour-UI | **KEINE Fremd-Lib** — Tour ist Multi-Page-Chat-Navigation (QR + Ticks), wird 1:1 portiert | — | v1-Fehlannahme korrigiert (shepherd wäre zudem AGPL) |
| Tests | pytest(+pytest-asyncio), Vitest (Angular-Builder), Playwright (E2E) | MIT/Apache | bleibt-artig |
| Optionaler Wachstumspfad | Redis (Rate-Limit/Cache), Langfuse (MIT-Core; braucht ClickHouse+Redis+S3 → erst bei Bedarf) | BSD/MIT | — |

**Verworfene Alternativen (Kurzbegründung):**
- *Phoenix als Trace-UI* (v1): ELv2, nicht OSI → Jaeger (Apache-2.0, 1 Container).
- *shepherd.js/driver.js für Tour* (v1): Lizenz (AGPL) bzw. falsches Modell — die heutige Tour
  navigiert über echte WP-Seiten hinweg (Ticks pro Page-Load), kein Single-Page-Overlay.
- *Nur-instructor ohne LangGraph:* Orchestrierung (Parallel-Gruppe Safety∥Classify∥Memory,
  Early-Exits, Checkpointing) wäre wieder Eigenbau — genau der 3000-Zeilen-Fehler von ALT.
- *Nx/Turborepo:* Angular-CLI-Multi-Projekt-Workspace reicht; weniger Werkzeug-Magie.
- *Studio als Web Component:* bringt nichts (Studio wird nie fremd-eingebettet) und kostet
  (Routing/Auth-Cookies im Shadow-DOM). Entscheidung: Studio = normale Angular-SPA im selben
  Workspace; Vereinheitlichung kommt aus der geteilten `ui`-Lib, nicht aus dem Element-Build.

---

## 3. Bewusste Verbesserungen gegenüber ALT (abschließende Liste)

| # | Verbesserung | Begründung |
|---|---|---|
| V1 | Widget-Auslieferung: `/widget/boerdi-widget.js` bleibt stabiler Pfad, liefert aber Redirect/Alias auf gehashte Datei `boerdi-widget.<hash>.js` mit `Cache-Control: immutable`; heute `no-store` (jeder Load lädt 455 KB neu) | Performance + beendet die „Studio neu, Widget alt"-Fehlerklasse |
| V2 | Config in Postgres (jsonb, versioniert) + LISTEN/NOTIFY-Invalidierung; YAML-Import/Export bleibt (Git-Ops/Snapshots kompatibel) | Cluster-Korrektheit; mtime-Cache funktioniert nur single-node |
| V3 | **Jeder** Config-Bereich bekommt Pydantic-Schema + JSON-Schema-Export → Studio rendert generisch (formly). Behebt ALT-Lücke: `classify-overrides.yaml` ist heute im Studio faktisch NICHT editierbar (InfoView behauptet es nur) | weniger Studio-Code, keine „vergessenen" Bereiche |
| V4 | Element-API offiziell: `openChatbot/closeChatbot/toggleChatbot/isChatbotOpen` **plus** `resetSession()/updateContext(ctx)` ans Custom Element durchgereicht (heute nur dokumentiert, nicht erreichbar) | ALT-Befund Widget-Agent |
| V5 | Trusted-Host-Logik EINMAL in `libs/ui` (heute doppelt: Chat mit CORE-Prefix vs. Widget) | ALT-Befund; Drift-Quelle |
| V6 | Session-Serialisierung via `pg_advisory_xact_lock(hash(session_id))` statt In-Proc-Locks | Cluster |
| V7 | Rate-Limit clusterfähig (slowapi Storage-URI); public Endpoints (`/api/chat*`, speech, sessions/{id}/messages) limitiert **per Default an** (ALT: default aus) | Audit-Erbe |
| V8 | Studio: Monaco statt `<textarea>`, Live-Widget-Preview-Tab (Widget-Element aus demselben Workspace gegen Staging-Backend), Logout-Button (Endpoint existiert in ALT ungenutzt) | Redaktions-UX |
| V9 | Loadtest-Runs persistiert (Tabelle `loadtest_runs` statt in-memory) | Parität der Ansicht über Neustarts |
| V10 | OTel-Spans mit GenAI-Attributen (Modell, Tokens aus LiteLLM-Usage) zusätzlich zum DebugInfo-Echo | Betriebssicht ohne Studio |
| V11 | Ein Secrets-/Settings-Modul (pydantic-settings) mit **Alias-Tabelle ALT→NEU** (§5.4) — alte Env-Namen bleiben gültig | sanfte Migration |
| V12 | Non-root-Container ab Tag 1, Healthchecks, Graceful Shutdown (SSE zu Ende streamen) | Audit-Erbe T-9 |
| V13 | **Reranker-Backend austauschbar, KEIN Netzwerk-Dienst**: statt fix ONNX-Cross-Encoder ein In-Proc-Scorer hinter `card_reranker._get_reranker()` — Optionen: Cross-Encoder (ALT-Parität, bestes Gate) · **Bi-Encoder-Cosine (mehrsprachig, teilt den RAG-Embedder aus 6-1 → kein Zweitmodell; Cosine∈[-1,1] → kalibrierbarer Gate)** · lexikalisch (`_relevance_score`, 0 Modell) · aus. Gate-Schwellen `CARD_CE_*` sind backend-spezifisch (env-überschreibbar, je Scorer neu kalibriert). **Modell in ALLEN Varianten mehrsprachig** (ALT-CE `mmarco-mMiniLMv2` war es bereits; der 6-1-Embedder MUSS es für Retrieval ohnehin sein). | Ressourcen-Schonung 2-Kern-vServer bei erhaltener Mehrsprachigkeit; TEI-Sidecar aus Kostengründen verworfen (Nutzer 2026-07-12) |

Alles andere: 1:1-Parität. Insbesondere bleiben erhalten: DebugInfo im ChatResponse,
`display_rules`-Echo, `tour`-Feld, Quality-/Safety-Logging-Semantik, Golden-Flows unverändert.

---

## 4. Zielarchitektur & Monorepo-Layout

```
                         ┌────────────────────────────────┐
  Host-Seiten ──────────▶│ traefik (TLS, LB)              │◀── Studio-Nutzer
  <boerdi-chat> Element  └───┬─────────────┬──────────────┘
   SSE /api/chat/stream      │             │  statisch: widget.<hash>.js, Studio-SPA
                     ┌───────▼───┐ ┌───────▼───┐
                     │ backend-1 │ │ backend-N │   stateless (uvicorn, FastAPI+LangGraph)
                     └─┬──┬──┬───┘ └─┬──┬──┬───┘
        Postgres 17    │  │  │       │  │  │   OTLP
      ┌────────────────▼┐ │  └───────┼──▼──┴─────────┐
      │ sessions/messages│ │  MCP    │ Jaeger        │
      │ config(+NOTIFY)  │ │  SDK    │ (all-in-one)  │
      │ pgvector chunks  │ │         └───────────────┘
      │ checkpoints/locks│ └──▶ wlo-mcp-server (extern, unverändert)
      └──────────────────┘ ──▶ B-API/OpenAI-kompatibel (via LiteLLM)
                           ──▶ TEI-Reranker (Sidecar, optional per Env)
```

```
boerdi-chat/
├─ backend/
│  ├─ pyproject.toml            # uv-verwaltet; ruff, pytest, pip-licenses-Gate
│  ├─ alembic/                  # Migrationen (inkl. pgvector-Extension)
│  ├─ src/boerdi/
│  │  ├─ main.py                # App-Factory, Router-Mounts, Middlewares (≤150 Z.)
│  │  ├─ settings.py            # pydantic-settings; §5.4-Aliase
│  │  ├─ api/                   # 1 Datei je ALT-Router-Gruppe (chat, sessions, config,
│  │  │                         #   config_elements, config_snapshots, rag, quality,
│  │  │                         #   safety, eval, loadtest, speech, widget, health)
│  │  ├─ graph/                 # LangGraph: state.py (TurnContext), nodes/*.py, build.py
│  │  ├─ domain/                # portierte pure Module (§6.2) — framework-frei
│  │  ├─ services/              # llm.py (LiteLLM+instructor), mcp/ (client, cache,
│  │  │                         #   parsers, arg_resolvers, tool_defs), rag/ (ingest,
│  │  │                         #   retrieval, rerank_client), safety/, memory.py,
│  │  │                         #   speech.py, config_store.py, snapshots.py, eval/,
│  │  │                         #   loadtest.py, wikipedia.py, url_safety.py
│  │  ├─ db/                    # models.py, session.py, locks.py, notify.py
│  │  └─ obs/                   # otel.py, quality_events.py, debug_info.py
│  └─ tests/                    # portierte Charakterisierungs-Tests + neue
├─ frontend/                    # EIN Angular-21-Workspace (npm)
│  ├─ angular.json
│  └─ projects/
│     ├─ widget/                # Angular Element <boerdi-chat> (zoneless, Signals)
│     ├─ studio/                # Studio-SPA (Routing, Guards, formly, Monaco)
│     └─ ui/                    # Shared Lib: M3-Theme/Tokens, WloCard, Karten-Boxen,
│                               #   Markdown(marked+DOMPurify), QR-Chips (__guide__/
│                               #   __action__-Parser), InlineDoc(+Print), Swimlanes,
│                               #   Pagination, trusted-host.ts, session-id.ts
├─ evals/                       # gold-flows.yaml (kopiert) + runner-CLI (portiert)
├─ deploy/
│  ├─ compose.dev.yml           # postgres+pgvector, jaeger, backend(reload), [tei]
│  ├─ compose.prod.yml          # traefik, backend xN, postgres, tei, jaeger, static
│  └─ README.md                 # Runbook (Backup/Restore, Scale, Rollback)
├─ docs/ (plans/, api/openapi.json eingefroren, runbook)
└─ .github/workflows/ci.yml    # lint+licenses+tests+budgets+golden-gate
```

**Datenfluss Chat-Turn (LangGraph, Nodes ↔ ALT-Module):**

```
preflight(rate_limit, direct_actions)          ← chat_pipeline_phases._run_preflight_guards
 └─ tour(early_exit)                           ← chat_tour + tour_service
 └─ context_greeting(page_event, early_exit)   ← chat_context_greeting
 └─ [parallel] safety | classify | memory      ← safety_service | instructor-Classify | memory
 └─ route(pattern_engine + policy)             ← pattern_engine, policy_service, state_machine
     ├─ canvas_fast_path (M10/M11)             ← canvas_service(+intent,+postprocess,+types)
     ├─ m16_topic_view                         ← chat_topic_pages
     └─ tools(mcp ∥ prefetch) → respond(SSE)   ← llm_tool_loop, chat_prefetch, llm_streaming
          └─ cards(boxing/filter/caps)         ← chat_cards, card_pipeline, card_reranker→TEI
postprocess(widget_modes, qr_policy, guide,    ← chat_postprocess, chat_quick_replies,
            web_links, completion)                chat_guide_markers, chat_turn_links,
                                                  chat_completion_messages, chat_inline_rendering
persist(messages, quality_log, state)          ← chat_turn_persist (+LangGraph-Checkpointer)
```
Early-Exits sind Graph-Kanten; `TurnContext` (graph/state.py) trägt exakt die Felder, die heute
zwischen den Phasen wandern (req, env, session_state, history, classification, safety, policy,
winner, cards, response_text, debug, usage, …) — Feldliste wird in P4-1 aus den Signaturen der
ALT-Module abgeleitet und im Code dokumentiert.

---

## 5. Paritäts-Inventare (VERBINDLICH — die Abnahme-Checkliste)

> Quelle: 3 Inventur-Läufe gegen ALT am 2026-07-10. Bei Zweifel gilt ALT-Verhalten.
> Portier-Referenzen zeigen auf `badboerdi/…`-Pfade.

### 5.1 API-Vertrag (OpenAPI wird in P0 aus dieser Tabelle eingefroren)

Auth: `public` · `studio` (Header `X-Studio-Key`, aktiv wenn `STUDIO_API_KEY` gesetzt) ·
`studio+builder` · `public(guide)`.

| Methode | Pfad | Auth | Zweck |
|---|---|---|---|
| GET/HEAD | /health, /api/health, / | public | Health/Redirect/Providerstatus |
| GET | /api/debug/mcp-test | studio | MCP-Verbindungstest |
| GET | /api/static/* | public | Assets (Logo) |
| POST | /api/chat | public | Chat-Turn |
| POST | /api/chat/stream | public | SSE-Turn (`connected`/`phase`/`result`/`error`) |
| GET | /api/speech/status · POST /api/speech/transcribe · POST /api/speech/synthesize | public | Speech (Caps!) |
| GET | /widget/boerdi-widget.js · /widget/ · /widget/inline · /widget/classic · /widget/frameless · /widget/{asset} | public | Widget-Bundle/Demos (V1: hash+immutable); `/frameless` additiv in U1 ergänzt |
| GET | /api/sessions/ · /api/sessions/db-stats · /api/sessions/{id} · /api/sessions/{id}/memory | studio | Session-Verwaltung |
| POST | /api/sessions/purge · /api/sessions/optimize · /api/sessions/{id}/memory | studio | Pflege/Memory |
| GET | /api/sessions/{id}/messages | **public** | Widget-History-Restore (Rate-Limit!) |
| DELETE | /api/sessions/{id} · /api/sessions/{id}/messages | studio | Löschen |
| GET/PUT | /api/config/file (+GET /api/config/files, DELETE /api/config/file) | studio | generisches Bereichs-CRUD (NEU: DB-Areas statt Datei; Pfad-Parameter bleibt der Bereichs-Schlüssel) |
| GET/PUT | /api/config/{privacy, tone-modifiers, welcome, context-actions, canvas/material-types, intents, states, personas, patterns, entities, mcp-servers} | studio | typisierte Bereichs-Endpoints |
| GET | /api/config/elements | studio | ID-Browser aller Elemente |
| GET | /api/config/guide-mode | public(guide) | Allowlist+header_nav+welcome fürs Widget-Boot |
| POST | /api/config/mcp-servers/discover | studio | Tool-Discovery |
| GET | /api/config/backup · POST /api/config/restore | studio(+builder) | Voll-ZIP (Config+DB-Export) |
| POST/GET/DELETE | /api/config/snapshots[…/{id}, /restore, /download] | studio(+builder) | Snapshots |
| GET/POST | /api/config/factory[…/download, /restore, /save, /upload] | studio(+builder) | Factory-Stand |
| POST | /api/rag/ingest/{file,url,text} · /api/rag/query · /api/rag/embed | studio | RAG |
| GET/DELETE | /api/rag/areas · /api/rag/area/{area}[…/doc] | studio | RAG-Verwaltung |
| GET | /api/safety/logs · /api/safety/stats | studio | Safety |
| GET/DELETE/POST | /api/quality/{logs, logs/{id}, logs/clear, stats, matrix, state-transitions, tight-races, degradations, empty-entities, low-confidence} | studio | Quality-Analytics |
| GET/POST/DELETE | /api/eval/{config, estimate, runs, runs/golden, runs/{id}, trends, gold-flows, quality-logs, analytics/pattern-usage} | studio | Eval (generativ + golden) |
| GET/POST/DELETE | /api/loadtest/{mix-options, runs, runs/{id}} | studio | Lasttest (Gate `ALLOW_LOADTEST`) |
| **NEU** GET | /api/config/schema/{area} | studio | JSON-Schema je Bereich (V3, generischer Renderer) |
| **NEU** GET/PUT | /api/config/data/{area} | studio | Bereichs-Daten als JSON (9-3a). Gegenstück zu `/schema/{area}`: `/config/file` liefert nur YAML-**Text**, damit lässt sich kein Formular binden. **PUT ersetzt, `data` ist das GANZE Dokument** (Read-Modify-Write). Grund: gemessen am ALT-Baum sind **357 Daten-Pfade** nicht vom Bereichs-Modell gepinnt und liegen *verschachtelt* (`01-base/policy` → `rules[*].effect.disclaimer`, `01-base/classify-overrides` → `pattern_disambiguators_legacy[*]`). Ein Server-Merge rettet das nicht: flach schützt die falsche Ebene, tief kann Löschen nicht ausdrücken. Also editiert das Formular eine Kopie des ganzen Dokuments; ungepinnte Teile fahren unberührt mit. Validierung ist ein Tor, keine Transformation — persistiert wird das rohe Dict, nie der `model_dump()` (der würde Defaults für jedes fehlende Optional-Feld einspritzen) |
| **NEU** POST | /api/auth/… bleibt Studio-seitig (SPA-Login wie ALT: HMAC-Cookie) | — | §7 |

**ChatRequest:** `session_id:str · message:str (Deckel ≤10000 entfernt 2026-08-18) · environment:Environment ·
action:str|None · action_params:dict · canvas_state:dict|None`
**Environment:** `page:"/" · page_context:dict · device:"desktop" · locale:"de-DE" ·
session_duration:0 · referrer:"direkt" · guide_mode:True · host:"" ·
ai_content_enabled:bool|None(deprecated) · tour_action:"start"|"tick"|None ·
page_event:"context_open"|None`
**ChatResponse:** `session_id · content · cards:[WloCard] · follow_up:"none" ·
quick_replies:[str] · debug:DebugInfo · page_action:dict|None · pagination|None ·
query_metas:[QueryMetaEntry] · web_links:[WebLink] · inline_documents:[InlineDocument] ·
topic_page:TopicPageView|None · display_rules:dict · tour:dict|None`
(Sub-Modelle 1:1 aus `badboerdi/backend/app/models/schemas.py` portieren.)
**page_action.action-Werte:** navigate, show_collection, show_results, share_content,
canvas_open, canvas_update, canvas_show_cards, canvas_close.
**Direct Actions (req.action):** browse_collection, generate_learning_path, curate_collection
(+ tolerierte Legacy-Namen canvas_create/edit/remix ohne Dispatch).

### 5.2 Konversations-Bausteine (Seed-Inhalte = ALT-Dateien, importiert)

- **Patterns M01–M16** (+ deren MD-Dateien 1:1): M01 Krisen-Empathie · M02 Bedrohungs-Refusal ·
  M03 Slot-Klärung · M04 Wissens-Antwort · M05 Suche-gefiltert · M06 Suche-Cascade ·
  M07 Fachportale · M08 Sammlung-Drilldown · M09 Lernpfad · M10 KI-Generierung ·
  M11 Nachbearbeitung · M12 Null-Treffer · M13 Einreichen/Melden · M14 Bot-Feedback ·
  M15 Orientierung · M16 Themenseiten-Inhalt.
- **Intents I01–I08:** Orientierung, Wissensfrage, Inhalte-Suchen, Lernpfad, Inhalt-Generieren,
  Inhalt-Nachbearbeiten, Feedback-Bot, Einreichen/Melden.
- **States:** S1 Orientierung · S2 Klärung · S3 Aktion. **Personas:** P-AND, P-ELT, P-ENT,
  P-LEH, P-LER, P-RED. **Slots:** fach, stufe, thema, medientyp, lizenz.
- **QR-Encodings:** `__guide__|label|url` · `__action__|label|action|json` (Split auf erste
  3 Pipes; JSON darf `|` enthalten). Intern (kein QR): `__NEG__::`-Cache-Sentinel.
- **MCP-Tools (12, für LLM-Loop):** search_wlo_collections, search_wlo_content,
  search_wlo_topic_pages, search_wlo_all, get_topic_page_content, get_collection_contents,
  get_node_details, lookup_wlo_vocabulary, get_subject_portals, browse_collection_tree,
  wlo_health_check, get_nodes_details. Direktaufrufe zusätzlich in: page_context (get_node_details),
  prefetch (search_wlo_all), routing (collections/content/contents), card_pipeline
  (search_wlo_content), arg_resolvers (lookup_wlo_vocabulary). Kanonische Arg-Namen
  (`educationalContext`, `learningResourceType`, `maxResults`, `vocabulary`) + Legacy-Aliase.

### 5.3 Config-Bereiche (ALT-Datei → NEU DB-Area; Seed-Import in P2)

Alle 35 Bereiche werden Areas in `config_areas` (Schlüssel = ALT-Pfad ohne `.yaml/.md`),
jede mit Pydantic-Modell + `/api/config/schema/{area}`:

01-base: base-persona(md), guardrails(md), card-pipeline, classify-overrides,
context-actions, device-config, display-rules, guide-mode, header-nav, placeholder-topics,
policy, privacy-config, quality-log-config, safety-config, tone-modifiers, website-tour,
welcome-config, widget-modes · 02-domain: domain-rules(md), guide-rules,
wlo-plattform-wissen(md) · 03-patterns: m01…m16(md, Frontmatter+Body) ·
04: entities, intents, personas(6×md), signal-modulations, states ·
05-canvas: create-triggers, edit-triggers, material-types, persona-priorities, type-aliases ·
05-knowledge: mcp-servers, rag-config · eval: gold-flows.

Loader-Namen (Parität der internen API): wie ALT `config_loader`-Fassade
(`load_welcome_config`, `load_context_actions`, … — vollständige Liste =
`badboerdi/backend/app/services/config_loader/*`), implementiert gegen `config_store`
(DB + Prozess-Cache + NOTIFY-Drop).

### 5.4 Env-Vars (pydantic-settings; ALT-Name bleibt als Alias gültig)

Gruppen (vollständige Liste, Defaults wie ALT): **Core:** LOG_LEVEL, STUDIO_API_KEY,
CORS_ORIGINS, TRUST_FORWARDED_FOR, BOERDI_ALLOW_OPEN_ADMIN · **LLM:** LLM_PROVIDER,
LLM_CHAT_MODEL, OPENAI_MODEL, LLM_EMBED_MODEL, EMBED_DIM, LLM_MAX_CONCURRENCY,
LLM_READ_TIMEOUT, BG_LLM_MAX_CONCURRENCY, LLM_VERBOSITY, LLM_REASONING_EFFORT,
OPENAI_API_KEY, OPENAI_BASE_URL, B_API_BASE_URL, B_API_KEY, B_API_AUDIO ·
**Speech:** SPEECH_FORCE_ENABLE, STT_MODEL, TTS_MODEL · **MCP:** MCP_SERVER_URL,
MCP_MAX_CONNECTIONS, REPO_BASE_URL · **RAG/Rerank:** RAG_RERANKER_ENABLED,
BOERDI_MAX_INGEST_MB, TEXT_EXTRACTION_URL, RAG_TOP_K, RAG_MIN_SCORE, RAG_MAX_CHARS_PER_AREA ·
**Cards:** CARD_PIPELINE_V2, CARD_CE_TOP_N, CARD_CE_GATE_COLLECTION, CARD_CE_GATE_CONTENT,
CHAT_DISABLE_SELECT_TOP_CARDS, CHAT_INLINE_QUICK_REPLIES · **Guide:** GUIDE_TRUSTED_DOMAINS ·
**Eval/Loadtest:** BOERDI_ALLOW_LOADTEST, EVAL_CHAT_URL, EVAL_SIMULATOR_MODEL, EVAL_JUDGE_MODEL.

**NEU:** DATABASE_URL (postgres+asyncpg), RATE_LIMIT_STORAGE_URI (`memory://`),
RATE_LIMIT_CHAT (z. B. `20/minute`), OTEL_EXPORTER_OTLP_ENDPOINT, RERANK_URL (TEI; leer=aus),
CONFIG_SEED_DIR (Erst-Import), WIDGET_DIST_DIR, STUDIO_COOKIE_SECURE (default 1; nur für
lokales Plain-HTTP auf 0 — ALT riet das an `NODE_ENV` und verlor das Flag im Staging),
STUDIO_DIST_DIR (gebautes Studio; fehlt ⇒ `/studio` wird nicht gemountet).
**Entfallen (durch Stack ersetzt):** DATABASE_PATH, RERANK_INTRA_OP_THREADS,
RERANK_MAX_CONCURRENCY (TEI-seitig). Settings-Modul dokumentiert jede Variable.

**B-API-Provider-Fähigkeits-Matrix (Nutzer 2026-07-24):** `b-api-openai` unterstützt inzwischen
ALLE OpenAI-Funktionen (Chat, Embeddings, **Speech**, **Moderation**); `b-api-academiccloud` hat
**kein Speech + keine Moderation**. Code-Verzweigung: Moderation (`safety/moderation._moderation_target`)
→ academiccloud nutzt OpenAI-Seitenkanal (`OPENAI_API_KEY`) oder überspringt (Regex-Floor bleibt);
Speech (`speech_proxy.speech_enabled`, #122, Option B) → academiccloud **ehrlich deaktiviert** (kein
Audio-Endpunkt, kein Seitenkanal gebaut); Embeddings laufen über denselben Provider wie Chat (`EMBED_DIM`
muss zur `rag_chunks`-pgvector-Dim passen). Für Speech/Moderation auf academiccloud → `LLM_PROVIDER=b-api-openai`/`openai`
oder `OPENAI_API_KEY`-Seitenkanal. Details: Memory `bapi-provider-capabilities`.

### 5.5 Widget-Embed-Vertrag (Element `<boerdi-chat>`)

- **Host-Attribute (18, kebab-case, Bool nur `true`/'true'):** api-url, page-context, position
  (bottom-right|bottom-left|top-right|top-left), initial-state (collapsed|expanded, auch
  Runtime), primary-color, persist-session(true), session-key(boerdi_session_id),
  session-cookie-domain, session-cookie-max-age(2592000), trusted-domains(CSV), greeting,
  auto-context(true), show-debug-button(true), show-language-buttons(true),
  intercept-edu-sharing-links(false), emit-guide-suggestion(false), emit-routing-debug(false),
  inline-result-grouping(true; `false` = flaches Karten-Grid statt Ergebnis-Boxen).
  Alternativ `window.BOERDI_API_URL` vor Bundle-Load.
- **Element-Methoden:** openChatbot, closeChatbot, toggleChatbot, isChatbotOpen **+ (V4)**
  resetSession, updateContext. Duplikat-Guard (2. Element versteckt), Doppel-Define-Guard.
- **CustomEvents (window):** `badboerdi:page-action{action,payload}`,
  `badboerdi:query-meta{queries[]}`, `badboerdi:guide-suggestion{url,title,node_id,node_type,
  query,alternatives[]}` (gated), `badboerdi:routing-debug{…}` (gated).
- **Storage:** localStorage `boerdi_session_id` (bzw. session-key), `boerdi_tour_active`,
  `boerdi_owl_hint_session`; optional Cookie (Domain-konfiguriert, SameSite=Lax, Secure);
  URL-Params transient `bsid` (`bb-<uuid>`-Format, wird gestrippt), `bgm`.
- **Backend-Calls:** POST /api/chat(+/stream mit Idle-Watchdog 90s/Stale 100s),
  GET /api/sessions/{id}/messages, GET /api/config/guide-mode, /api/speech/* (status-gated).
- **Feature-Katalog (31 — vollständige Abnahmeliste):** FAB+Puls, Begrüßung+Start-QRs,
  Owl-Hint (1×/Session), Owl=Tour-Start, Kontext-Begrüßung (Silent-Ping `context_open`, kein
  Loading-Bubble), Web-Tour (Start-Chip + Ticks), Guide-Mode+Navigate-Banner, Trusted-Host-
  Navigation+bsid-Handoff(+bgm), Karten-Boxen (Themenseiten/Sammlungen/Materialien/Webseiten/
  Such-CTA), Swimlane-Boxen+Absprung, Tile-Cards (Icon/Thumb/Lizenz/Fach/Stufe), Card-Aktionen
  (Inhalte/Lernpfad/Themenseiten-Dropdown), Pagination (client „Mehr anzeigen" + server
  „Weitere laden"), QR-Typen (Text/`__guide__`/`__action__`), Inline-Dokumente
  (lernpfad/ki_material/edit/bericht/remix) + Druck, STT (Mic, Timer, Transcribe→Send),
  TTS (Auto-Vorlesen-Toggle + pro Bubble), Debug-Panel (6 Gruppen + Token + Trace-Bars),
  Header-Nav (Studio-konfiguriert), Neustart, SPA-URL-Watcher (1,5 s), Live-Phasen-Label (SSE),
  Auto-Follow-Scroll (User-Scroll-Erkennung), Externe-URL-Warnung, A11y (role=log/aria-live/
  Fokus/Escape), Lazy-Mount + State-Erhalt, kein Datei-Upload (nur STT-Audio).
- **Seitenkontext-Detector (Muster in Prioritätsreihenfolge):** /components/render/<uuid>→content ·
  /components/collections?id=→collection(+q) · /components/topic-pages?collectionId=→topic ·
  ?node|node_id|nodeId= · ?collection|collection_id|collectionId= · /themenseite/<slug> ·
  /fachportal/<subject>[/<slug>] · /components/search[?q][&filters(publisher)] · generisch ?q=.
  DOM-Marker: meta boerdi:node-id/collection-id/topic-slug, body data-edu-*; page_text≤3000B.
- **Bundle-Budget:** Single-File, zoneless; CI-Gate ≤ 600 KB raw / ≤ 175 KB gzip.
  **Angehoben 2026-07-31** von 420/140 auf Nutzer-Weisung („das Größenlimit darf
  dafür steigen") für Angular Material 3 — gemessene Kosten **+75,8 KB roh /
  +33 KB gzip** (416,57 → 492,41 KB roh). Die ursprüngliche Begründung („ALT:
  455 KB roh mit zone.js — Budget erzwingt die zoneless-Einsparung") ist damit
  erledigt: die zoneless-Einsparung IST realisiert (416,57 KB vor Material,
  38 KB unter ALT), das Budget deckt jetzt zusätzlich die Komponenten-
  bibliothek. Der Wert steht an **drei** Stellen, die zusammen wandern müssen:
  `angular.json` (build-widget), `scripts/check-widget-budget.mjs`, dieser Satz.
- **Komponentenbibliothek:** Angular Material 3 + CDK (beide MIT), Theme an
  `:host` des Widget-Roots. Kehrt die frühere Festlegung „nur CSS-Custom-
  Properties, keine Material-Bibliothek" um (Nutzer-Entscheid 2026-07-31,
  Details in `docs/plans/2026-07-31-material3-edu-sharing.md`). Ein globales
  Stylesheet wird weiterhin **nicht** ausgeliefert (`"styles": []`), damit das
  Widget die Gastseite nicht umstylt.

### 5.6 Studio-Funktionsumfang (Views NEU = Angular-Routen)

> **Befund aus 9-2 (wichtig für 9-3…9-6):** ALT hat **keine Routen** — alle 17 Views hängen an
> einem `useState<Layer>` in einer einzigen `page.tsx`; im ganzen `studio/src` gibt es keinen
> Router-Import. Es gibt also keinen URL-Vertrag zu portieren, keine Deep-Links und kein
> Back-Button-Verhalten, das erhalten werden müsste. Die Slugs sind in 9-2 NEU festgelegt
> (deutsch, `studio-views.ts` ist die einzige Quelle für Routen UND Navigation). Die Zählung
> „18" hier = 16 geroutete Views + Architektur-Untertab der Übersicht + Snapshots-Modal
> (Kopfzeilen-Chrome, keine View). Ebenso NEU statt portiert: WCAG-Floor (ALT hatte außer
> Landmarks + `aria-hidden` nichts) und Responsive (0 `@media` in 1226 CSS-Zeilen).

Parität zu ALT (18 Views) + V8: Übersicht(Home+Architektur) · Begrüßung · Kontext-Aktionen ·
Identität&Schutz (Safety-Level-Picker off/regex/standard/strict/paranoid + base-persona/
guardrails/safety-config/policy) · Domain-Wissen (domain-rules, wlo-plattform-wissen,
website-tour) · Patterns (16, 5 Tabs, +Neu) · Dimensionen (Personas+Tonalität, Intents, States,
Entities, Signals) · Material-Formate (18 Typen GUI + aliases/triggers/priorities) · Wissen
(RAG-Bereiche mode always/on-demand + Doc-Verwaltung + Ingest file/url/text; MCP-Registry +
Discover) · Anzeige (display-rules GUI+YAML, header-nav, device-config) · Datenschutz
(Toggles, purge, optimize) · Sessions (Liste, Verlauf, Debug-Badges, Löschen) · Analyse
(Quality: 4 Tabs, Scope Alle/Prod/Eval) · Evaluation (generativ: Matrix/Judge/TurnTrace mit
Schritten+ms+Confidence+Hint-Judge; golden: Scorecard + A/B-Vergleich mit Δ pp) · Lasttest
(Stufen-CSV≤6×≤32, req/Stufe≤60, p95-Schwelle, Mix-Gewichte; Charts; „stabil bis N") ·
Safety-Logs · Header: Snapshots-Modal (+Factory), Backup-ZIP, Restore(wipe/merge+DB), Status-Dot ·
**NEU:** generischer Schema-Formular-Renderer für alle §5.3-Bereiche ohne eigene View
(9-3, **ohne formly** — Begründung dort), Live-Widget-Preview, Logout-Button, Jaeger-Link.
Monaco ist **vertagt**: 97,9 MB entpackt + Worker-/Asset-Pipeline für eine YAML/MD-Rohansicht;
9-3 liefert dafür ein `<textarea>` (wie ALT), der Editor-Aufsatz wird in 9-6 neu entschieden.
**Auth wie ALT:** Login-Page → HMAC-Cookie `boerdi_studio_auth` (STUDIO_PASSWORD-gated,
konstantzeitiger Vergleich, httpOnly/strict/30d); Backend-Key X-Studio-Key NUR server-seitig —
NEU: da Studio-SPA statisch ist, übernimmt ein schlanker **studio-bff** (Teil des Backends:
`/studio/api/*`-Proxy-Router mit Cookie-Gate + Key-Injektion) die ALT-Next-Proxy-Rolle.
Env: BACKEND_URL entfällt (same origin), STUDIO_PASSWORD, STUDIO_API_KEY bleiben.
**Umsetzung 9-1 (verbindlich, ersetzt „Proxy-Router"):** der studio-bff ist KEIN HTTP-Proxy,
sondern ein In-Process-Path-Rewrite (ASGI-Middleware `/studio/api/<x>` → `/api/<x>`) — same
origin heißt, es gibt keinen zweiten Prozess mehr, den man anrufen könnte. Folgen:
Multipart/SSE streamen unverändert (dieselbe `receive`/`send`-Kette, kein Puffern), der
120-s-Timeout entfällt (bewachte in ALT einen Socket, den es nicht mehr gibt), und die
Location-Umschreibung dreht sich (`/api/…` → `/studio/api/…`, sonst folgt der Browser dem
307 der Trailing-Slash-Umleitung am BFF vorbei). **Fail-closed statt ALTs fail-open:**
fehlendes STUDIO_PASSWORD sperrt das Studio (503) statt es zu öffnen — `BOERDI_ALLOW_OPEN_ADMIN=1`
ist der einzige Dev-Ausweg, genau wie bei `require_studio_key`. Unauthentifizierte `/studio/api`-
Aufrufe liefern **401 JSON** statt ALTs HTML-Redirect; der SPA-Guard fragt `GET /studio/api/auth/session`.

### 5.7 Golden-Flows & Loadtest (Abnahme-Instrumente, unverändert portiert)

`eval/gold-flows.yaml`: 12 Flows GS-1…GS-12 (persona, intents, turns[{message,
expect{persona,intent,register(sie|du|any),structure(idoc|cards|none),qr,host_ok,must_offer}}]).
Runner: `evals/run_golden.py` (portiert aus eval_golden/eval_service; Ziel-URL per
EVAL_CHAT_URL). Loadtest-Caps: MAX_STAGES=6, MAX_CONCURRENCY=32, MAX_REQUESTS_PER_STAGE=60,
MAX_TOTAL=200, 1 Run gleichzeitig; Mix: wissen/suche/orientierung/lernpfad.

---

## 6. Datenmodell (Postgres — alembic-Migration 0001)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE sessions (
  session_id text PRIMARY KEY,            -- 'bb-<uuid>'
  persona_id text NOT NULL DEFAULT '',
  state_id   text NOT NULL DEFAULT 'S1',
  entities   jsonb NOT NULL DEFAULT '{}'::jsonb,
  signal_history jsonb NOT NULL DEFAULT '[]'::jsonb,
  turn_count int  NOT NULL DEFAULT 0,
  tour_state jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX idx_sessions_updated ON sessions(updated_at);

CREATE TABLE messages (
  id bigserial PRIMARY KEY,
  session_id text NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user','assistant')),
  content text NOT NULL,
  cards jsonb, debug jsonb,
  created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX idx_messages_session ON messages(session_id, id);

CREATE TABLE memory (
  id bigserial PRIMARY KEY,
  session_id text NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  key text NOT NULL, value text NOT NULL, memory_type text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(session_id, key, memory_type));

CREATE TABLE safety_logs (   -- Spalten 1:1 wie ALT (…risk_level, stages_run, reasons,
  id bigserial PRIMARY KEY,  --  legal_flags, flagged_categories, blocked_tools,
  session_id text, ip text,  --  enforced_pattern, escalated, rate_limited, message,
  data jsonb NOT NULL,       --  categories_json) — als jsonb `data` + Promoted-Spalten:
  risk_level text, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX idx_safety_created ON safety_logs(created_at);
CREATE INDEX idx_safety_risk ON safety_logs(risk_level);

CREATE TABLE quality_logs (  -- Promoted: session_id, pattern_id, intent_id, created_at;
  id bigserial PRIMARY KEY,  -- Rest (28 ALT-Spalten) in data jsonb — Analytics-Queries
  session_id text, pattern_id text, intent_id text,   -- aus db_analytics.py portieren
  data jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX idx_quality_created ON quality_logs(created_at);
CREATE INDEX idx_quality_pattern ON quality_logs(pattern_id);

CREATE TABLE eval_runs (LIKE-ALT: id text PK, created_at, completed_at, status, mode,
  config jsonb, totals jsonb, summary jsonb, conversations jsonb, error_message text);
CREATE TABLE loadtest_runs (id text PK, created_at timestamptz, status text,
  config jsonb, result jsonb);                                   -- V9

CREATE TABLE config_areas (
  area text PRIMARY KEY,                  -- z. B. '01-base/welcome-config'
  data jsonb NOT NULL,                    -- MD-Bereiche: {"body": "...", "frontmatter": {...}}
  version int NOT NULL DEFAULT 1,
  updated_at timestamptz NOT NULL DEFAULT now(), updated_by text NOT NULL DEFAULT '');
CREATE TABLE config_history (id bigserial PK, area text, version int, data jsonb,
  updated_at timestamptz, updated_by text);
CREATE TABLE config_snapshots (id text PK, created_at timestamptz, label text,
  include_db bool, blob bytea);           -- ZIP-Bytes; Factory = Zeile mit id='factory'

CREATE TABLE rag_documents (id bigserial PK, area text NOT NULL, title text, source text,
  created_at timestamptz DEFAULT now());
CREATE TABLE rag_chunks (
  id bigserial PRIMARY KEY,
  document_id bigint REFERENCES rag_documents(id) ON DELETE CASCADE,
  area text NOT NULL, chunk_index int NOT NULL, content text NOT NULL,
  embedding vector(1536));               -- Dim aus EMBED_DIM; Migration parametrisiert
CREATE INDEX idx_rag_area ON rag_chunks(area);
CREATE INDEX idx_rag_embedding ON rag_chunks
  USING hnsw (embedding vector_cosine_ops);

-- Config-Invalidierung (Cluster): Trigger auf config_areas → NOTIFY
CREATE OR REPLACE FUNCTION notify_config_changed() RETURNS trigger AS $$
BEGIN PERFORM pg_notify('config_changed', NEW.area); RETURN NEW; END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_config_notify AFTER INSERT OR UPDATE ON config_areas
  FOR EACH ROW EXECUTE FUNCTION notify_config_changed();
```
Zusätzlich: LangGraph-Checkpointer-Tabellen (liefert `langgraph-checkpoint-postgres` per
`.setup()` — eigene Migration 0002 ruft das auf). Session-Lock:
`SELECT pg_advisory_xact_lock(hashtext(:session_id))` zu Turn-Beginn in `db/locks.py`.
Privacy-Gates wie ALT: privacy-config-Toggles schalten messages/memory/quality-Writes ab
(safety immer an).

---

## 7. Frontend-Architektur (Kurzreferenz für P8/P9)

- **projects/ui** (Lib, keine App): `theme/` (M3-Design-Tokens, Light/Dark, --boerdi-primary-
  Override), `markdown/` (marked+DOMPurify, identische Sanitizer-Policy wie ALT),
  `cards/` (WloCard-Tile, 5 Box-Typen, Pagination), `chips/` (QR-Rendering + Parser
  `guide-qr.ts`/`action-qr.ts` — aus ALT portieren inkl. Specs), `inline-doc/` (+Print-CSS),
  `swimlanes/`, `session/` (session-id.ts, trusted-host.ts — V5 vereinheitlicht),
  `page-context/` (Detector — aus ALT portieren inkl. 7-URL-Golden-Spec).
- **projects/widget:** `widget-main.ts` (Element-Define + Public-API-Patch + Duplikat-Guard),
  Shell (FAB/Panel/Position/Farbe), Chat (Stream-Client mit Watchdogs, History-Restore,
  Begrüßung/Kontext-Ping/Tour-Controller/SPA-Watcher — Controller-Klassen aus ALT portieren),
  Speech-Service, Debug-Panel. Zoneless (`provideExperimentalZonelessChangeDetection` bzw.
  Angular-21-stabile API), Signals, KEIN zone.js im Bundle.
- **projects/studio:** Routen je §5.6-View; `app/schema-form/` = eigener Renderer (9-3,
  **kein formly**): `schema-to-fields.ts` (rein, Schema→Feldbaum) + `form-value.ts` (rein,
  unveränderliche Pfad-Operationen) + `SchemaFormComponent`/`SchemaFieldComponent` (rekursiv)
  + `JsonValueComponent` (Freiform-Felder als JSON). `views/area-editor.component` bindet das
  an `/config/schema/{area}` + `/config/data/{area}`, `views/areas.component` listet alle
  Bereiche. Spezial-Views nur wo GUI-Mehrwert (Patterns-Tabs, Safety-Level-Picker, Wissen,
  Analyse/Eval/Lasttest-Dashboards); MD/YAML-Rohansicht im `<textarea>` (Monaco vertagt,
  s. 9-3); Live-Preview-Route bettet `<boerdi-chat api-url=…>` ein.
  Auth-Guard gegen `/studio/api/auth/session`; alle Datenzugriffe über studio-bff (§5.6).
  Stand 9-2: `baseHref: /studio/`, `studio-views.ts` (Registry → Routen + Nav), `core/`
  (`StudioApi` mit `StudioApiError.status`, 401-Interceptor), `auth/` (SessionStore/Service/
  Guard/Login + `safeRedirectTarget`), `shell/` (Chrome + Status-Dot), `theme/_studio-tokens.scss`
  (auf den geteilten M3-Tokens, jede Farbe mit gerechnetem Kontrast).

---

## 8. Nicht-funktionale Anforderungen

- **Performance:** p95 Chat-Turn (ohne LLM-Streamdauer) ≤ ALT; Widget-Bundle-Budget §5.5;
  Lasttest-Abnahme P10: „stabil bis ≥ 8 parallel auf 2-Kern-Referenz" (Profil wie ALT-Caps).
- **Cluster-Checkliste (P10-Abnahme):** N=3 Replikas hinter traefik: Session-Turns
  serialisiert (Advisory-Lock-Test), Config-Änderung propagiert < 2 s (NOTIFY-Test), Rate-Limit
  konsistent mit redis://-Storage, SSE über LB stabil, Graceful Shutdown verliert keinen Turn.
- **Security:** Regeln #8/#9; CORS default restriktiv (`CORS_ORIGINS` explizit); CSP für
  Studio/Demos; Auth-Modi wie ALT (offen nur mit BOERDI_ALLOW_OPEN_ADMIN).
- **A11y (Widget+Studio):** WCAG 2.2 AA-Floor gemäß /better-coding-frontend; Widget-Verhalten
  aus Feature-Katalog (role=log, aria-live, Fokus-Management, Escape) ist Abnahmekriterium.
- **Observability:** OTel-Traces (Turn=Root-Span, Nodes=Child-Spans, GenAI-Attrs);
  DebugInfo/quality_logs wie ALT; strukturierte Logs (json) mit session_id-Feld.
- **Privacy:** wie ALT privacy-config; keine PII in URLs/Logs; Widget setzt nur die §5.5-Keys.

---

## 9. Migration & Cutover (P11)

1. **Config-Import:** CLI `boerdi import-config --from <badboerdi/backend/chatbots/wlo/v1>`
   liest alle 35 Bereiche (YAML/MD→jsonb; Patterns: Frontmatter+Body), schreibt config_areas
   v1 + Factory-Snapshot. Roundtrip-Test: Export erzeugt byte-äquivalente YAML-Struktur.
2. **RAG-Re-Ingest:** CLI `boerdi import-rag --sqlite <badboerdi.db>` liest rag_chunks
   (Text!) und re-embedded via LiteLLM in pgvector (Embedding-Modell/Dim aus Env; ALT-BLOBs
   werden NICHT binär übernommen). Alternativ frischer Ingest aus knowledge/-Seeds.
3. **Sessions:** werden NICHT migriert (TTL-Natur); Stichtag kommunizieren.
4. **Parallelbetrieb:** NEU auf Zweit-Port/Zweit-Host; Golden-Suite gegen ALT und NEU
   (EVAL_CHAT_URL umschaltbar) — Abweichungs-Report pro Flow/Turn; Stichproben-Redaktion.
5. **Widget-Umschaltung:** Host-Snippet zeigt auf NEU-URL (`api-url`-Attribut) — pro Seite
   schaltbar; Rollback = Attribut zurück.
6. **Stilllegung ALT** nach 2 Wochen fehlerfreiem Betrieb; badboerdi-Repo archivieren
   (Referenz für Ports bleibt lesbar).

---

## 10. Risiken

| Risiko | Gegenmittel |
|---|---|
| Paritätslücken in Detail-Semantik | §5-Inventare + portierte Alt-Tests + Golden-Gate + A/B-Parallelbetrieb |
| LangGraph-API-Churn | Domäne framework-frei (Regel 4); Nodes < 50 Z.; Checkpointer-Zugriff nur in graph/ |
| pgvector-Ranking ≠ sqlite-vec-Ranking | Ragas-/Stichproben-Vergleich in P6; RAG_MIN_SCORE nachjustierbar (Config, nicht Code) |
| Zoneless-Angular-Fallstricke (Streams/3rd-party) | ui-Lib mit Signals from Scratch; ALT-Specs portiert; E2E Playwright |
| Reranker auf 2-Kern-Server zu schwer | Austauschbarer In-Proc-Scorer (V13): Bi-Encoder-Cosine (leichter, teilt 6-1-Embedder) / lexikalisch `_relevance_score` / ganz aus (Fallback Top-N, Parität zum ALT-Knopf `RAG_RERANKER_ENABLED=false`) — kein Netzwerk-Dienst |
| Studio-bff-Umbau (Next→Backend-Proxy) übersieht Header-Semantik | ALT-Proxy-Verhalten als Kontrakt-Test portieren (Location-Rewrite, 120s-Timeout, Multipart-Streaming) |
| Doppelbetrieb bindet Kräfte | ALT einfrieren (nur Security-Fixes) ab P4 |

## 11. Offene Fragen

Keine — alle Produktentscheidungen sind in §2/§3 fixiert (Nutzer-Vorgaben 2026-07-10:
Ordnername boerdi-chat, Struktur Backend+Widget+Studio, OSS-Maximierung mit MIT/Apache,
clusterfähig mit anderer DB, volle Parität, generisch, bewusste Verbesserungen erlaubt,
Studio-Technologie freigestellt → Entscheidung Angular-SPA im Workspace).

---

# Arbeitspakete & Task-Listen

> **Jedes Paket:** Schritt 0 = `/better-coding-workflow` laden (P8/P9 zusätzlich
> `/better-coding-frontend`); Schritt Z (letzter) = `/better-coding-verify` + Paket-Abnahme.
> Netz-first: Für Portierungs-Tasks IMMER zuerst die genannte ALT-Testdatei portieren
> (Patch-Pfade `badboerdi.app.…` → `boerdi.…`), rot sehen, dann Modul portieren, grün.
> Commits macht der Nutzer; ein Commit je Task-Gruppe.
> **Referenz-Wurzel ALT:** `C:\Users\jan\staging\Windsurf\wlo-suche\badboerdi\`.

## P0 — Fundament & Verträge (Größe M)

| # | Task | Dateien (NEU) | Inhalt/Verify |
|---|---|---|---|
| 0-1 | Monorepo-Skeleton | Ordnerbaum aus §4, README, .editorconfig, .gitignore | `tree` entspricht §4; `git init` durch Nutzer |
| 0-2 | Backend-Gerüst | backend/pyproject.toml (uv; deps §2 mit Pins), src/boerdi/{main,settings}.py, tests/test_health.py | `uv run pytest` → 1 Test grün (GET /health==ok); ruff clean |
| 0-3 | Settings+Aliase | settings.py mit ALLEN §5.4-Vars (Field alias/validation_alias für ALT-Namen), tests/test_settings.py | Test: ALT-Name und NEU-Name setzen dasselbe Feld |
| 0-4 | OpenAPI-Vertrag einfrieren | docs/api/openapi-v1.json | Skript exportiert Schema der §5.1-Stub-Router (Response-Modelle aus P0-5); Datei committen; CI-Diff-Gate |
| 0-5 | Schemas portieren | src/boerdi/api/schemas.py (+_cards/_inline Teilmodule ≤300 Z.) | Port 1:1 aus `badboerdi/backend/app/models/schemas.py`; Test: model_json_schema() aller Modelle baubar |
| 0-6 | CI | .github/workflows/ci.yml | Jobs: ruff, pytest, **pip-licenses --fail-on 'GPL;AGPL;LGPL;SSPL;Elastic'**, npm-lint/test/licenses, Widget-Budget (P8), OpenAPI-Diff |
| 0-7 | Compose-Dev | deploy/compose.dev.yml | postgres:17+pgvector (Init-SQL Extension), jaeger all-in-one, backend (reload); `docker compose up` → /health ok |
| 0-8 | Golden-Runner-Port | evals/gold-flows.yaml (Kopie), evals/run_golden.py, evals/README | Port aus `backend/app/services/eval_golden.py`+`eval_service.py` (nur Runner-Teil, httpx gegen EVAL_CHAT_URL); Lauf gegen **ALT** (läuft lokal) = Referenz-Report grün |

**Abnahme P0:** CI grün; Golden-Runner produziert Referenz-Report gegen ALT; Lizenz-Gate aktiv.

## P1 — Backend-Kern (M)

| # | Task | Dateien | Inhalt/Verify |
|---|---|---|---|
| 1-1 | DB-Fundament | db/{models,session}.py, alembic 0001 (§6-DDL) | `alembic upgrade head` gegen Compose-PG; Tabellen existieren (Test mit asyncpg-Introspektion) |
| 1-2 | Advisory-Locks + NOTIFY | db/locks.py, db/notify.py, tests | Test: 2 parallele Tasks auf gleiche session_id laufen seriell; NOTIFY-Listener empfängt Area-Namen |
| 1-3 | Auth + Security-Header + CORS | api/deps.py (require_studio_key — Port aus `app/services/auth.py` inkl. BOERDI_ALLOW_OPEN_ADMIN-Semantik), main.py-Middlewares (Port `_security_headers` aus `app/main.py`) | ALT-Tests portieren (`tests/test_auth*.py`-Pendants); 401/403-Matrix grün |
| 1-4 | Rate-Limit | api/ratelimit.py (slowapi-Limiter, Storage-URI aus Settings; Keys: session_id∨IP wie ALT `rate_limiter.py`) | Test: Limit greift auf /api/chat-Stub; TRUST_FORWARDED_FOR-Verhalten wie ALT |
| 1-5 | OTel | obs/otel.py (FastAPI/HTTPX/SQLAlchemy-Instrumentierung, OTLP-Export optional per Env) | Dev-Compose: Trace eines /health-Calls in Jaeger sichtbar (manueller Check dokumentiert) |
| 1-6 | Health/Readiness | api/health.py (Port Semantik aus ALT `main.py` /api/health: Provider/Modell-Anzeige ohne Secrets) | Tests grün |

## P2 — Config-Subsystem (M–L)

| # | Task | Dateien | Inhalt/Verify |
|---|---|---|---|
| 2-1 | Bereichs-Modelle | domain/config_models/*.py (je §5.3-Bereich 1 Pydantic-Modell; MD-Bereiche = {frontmatter, body}) | Vollständigkeit gegen §5.3-Liste (35); Test iteriert Registry |
| 2-2 | config_store | services/config_store.py (get/put/history/subscribe; Prozess-Cache + NOTIFY-Drop; updated_by) | Tests: Roundtrip, Version++, Cache-Invalidierung über echten NOTIFY |
| 2-3 | Loader-Fassade | services/config_loader.py (ALLE ALT-Loader-Namen → config_store; Signaturen identisch) | Port der ALT-Loader-Tests (`tests/test_config_loader*.py`, `test_context_actions_config.py` …) — grün |
| 2-4 | YAML-Import/Export | services/seed_io.py + CLI `boerdi import-config`/`export-config` | Roundtrip-Test gegen Kopie des ALT-Baums (55 Dateien): import→export strukturgleich |
| 2-5 | Bereichs-Endpoints | api/config.py, api/config_elements.py (Pydantic-Payloads wie ALT `config_elements.py`-Konvention) | Port relevanter ALT-Router-Tests (`test_config_router*.py`); 422-Verhalten identisch |
| 2-5-Tail ✅ | **PUT /api/config/mcp-servers** (war auf P5/P6 vertagt, entsperrt durch `url_safety` ✅) | api/config.py: `McpServerUpdate` + SSRF-Gate vor dem Write (Primary `wlo-mcp` ausgenommen — Env-URL, wird beim Save verworfen); `save_mcp_servers` lag seit P2 fertig → reiner Router-Slice | ALT `test_config_mcp_servers.py` portiert (4 SSRF-Pins) + 4 neue = 8, offline (numerische IPs, Save gespiegelt). ALT-Body-AST nach 4 sanktionierten Transforms **identisch**. Vertrag bewusst regeneriert: +requestBody/+McpServerUpdate/+422/+description, sonst byte-ident. `POST /mcp-servers/discover` folgte als **2-5-Tail-2** (nächste Zeile) |
| 2-5-Tail-2 ✅ | **POST /api/config/mcp-servers/discover** (letzter Config-Stub → Config-Router jetzt **0 Stubs**) | api/config.py: einmaliger MCP-Handshake ohne Registrierung; SSRF-Guard **VOR** dem Egress (url-Pflicht 400 · `assert_public_url` 400 · Transportfehler 502), `transport.discover_server_tools` seit 5-1b da → reiner Router-Slice | ALT `routers/config_mcp.py:118-140` verbatim: Body-AST nach 3 sanktionierten Transforms (fn-Importe hoch · Modul-Seam · `+from e`/B904) **`ast.dump()`-identisch** (3 Stmts), args byte-ident, nur `-> dict` als Signatur-Deviation. 4 Pins offline (ALT discover-intern + 3 aus `test_config_router.py`: url-Pflicht/Erfolg/502), Netzgrenze gespiegelt. Vertrag regeneriert: Delta exakt +`url`-Query +422 |
| 2-5-Tail-3 ✅ | **GET /api/config/mcp-servers Tool-Description-Enrichment** (letzte nicht portierte ALT-MCP-Funktion → ganze MCP-Fläche komplett) | NEU `services/mcp/tool_descriptions.py` (Regel 4: I/O raus aus dem Router, ALT hielt Cache+Fetch im `config_mcp`-Router): `_fetch_tool_descriptions` (5-min-TTL `_TOOL_DESC_CACHE`, A7 „Fehler nicht cachen") + `load_mcp_servers_with_descriptions`; TTL-Cache als Modul-Global **per Eiserner Regel 3 explizit erlaubt** („MCP-TTL-Cache pro Prozess … nur Performance", wie `tool_cache`). GET-Signatur unangetastet → **0 OpenAPI-Drift** | tier-B: BEIDE Bodies `ast.dump()`-**identisch** (7 + 3 Stmts) nach 2 Seams (`discover_server_tools`→`transport.…` · `load_mcp_servers`→`config_loader.…`) + fn-Import-Hebung. 5 Tests offline (3 ALT-Service-Units normalize/cache/A7 + Enrichment-Regel + HTTP-Wiring); Regression-Spy im pg-gegateten `test_config_area_endpoints` (Primary-URL=Vercel-Default). Suite 1398/62 |
| 2-6 | Schema-Export | api/config_schema.py (GET /api/config/schema/{area} → model_json_schema) | Test: alle 35 Areas liefern valides JSON-Schema |
| 2-7 | Snapshots/Backup/Factory | services/snapshots.py, api/config_snapshots.py (ZIP mit Caps — Port `_copy_zip_member_capped` aus ALT `config_backup.py`) | ALT-Tests portieren; Zip-Bomben-Test grün |
| 2-8 | guide-mode public | api/config.py public_router (GET /api/config/guide-mode bündelt trusted_domains+header_nav+welcome wie ALT `config_areas.py:176-207`) | Kontrakt-Test: Response-Shape identisch ALT |

**Abnahme P2:** Import des ALT-Config-Baums; alle Bereiche über API les-/schreibbar; NOTIFY-Propagation < 2 s über 2 Prozesse.

## P3 — LLM, Klassifikation, Safety (M)

| # | Task | Dateien | Port-Quelle / Verify |
|---|---|---|---|
| 3-1 | LLM-Transport | services/llm.py (LiteLLM: acompletion, Semaphore LLM_MAX_CONCURRENCY, Timeout, Usage-Hook→obs) | ALT `llm_provider.py`/`llm_usage.py`-Semantik; Tests mit respx/Fake |
| 3-2 | Structured Classify | services/classify.py (instructor.from_litellm → ClassificationResult; Prompt-Port aus `llm_classify_prompt.py`; Fallback-Result wie ALT) | ALT-Klassifikations-Tests portieren |
| 3-3 | Reasoning-Filter + QR-Gen + Prompt-Builder | domain/reasoning_filters.py, services/quick_replies_llm.py, services/prompt_builder.py | Port aus `llm_reasoning_filters.py`, `llm_quick_replies.py`, `llm_prompt_builder.py` + Tests |
| 3-4 | Safety-Pipeline | services/safety/{regex_gate,moderation,legal,service}.py (Stufen wie ALT `safety_service.py`; Regex-Listen aus Config-Area safety-config) | ALT-Safety-Tests portieren; Stufen-Eskalation identisch |
| 3-5 ✅ | Logging-Writer (R3b ✅ 2026-07-18; R3a `db_sessions` ✅) | obs/quality_events.py: log_safety_event+log_quality_event → data jsonb + promoted cols; Gate/Aufruf = R4-Persist | Port `db_logs.py`-Writer-Semantik; 6 pg-Pins; Reader (get/delete) = R6-Router |

## P4 — Orchestrierung (L)

| # | Task | Dateien | Inhalt/Verify |
|---|---|---|---|
| 4-1 | TurnContext | graph/state.py | Feldliste aus ALT-Phasen-Signaturen (`chat_turn_setup._setup_turn`-Return + `_classify_and_merge`-21-Tupel dokumentiert die Felder); typed dict/pydantic |
| 4-2 ✅ | Nodes: preflight/tour/context_greeting (= Restplan R2; 4-2a domain/tour ✅ · **4-2b preflight ✅** · **4-2c tour-Node ✅** 2026-07-18 · **4-2d context_greeting ✅ 2026-07-23** [#116, `graph/nodes/context_greeting.py` 203 Z. Port `chat_context_greeting.py` + Node-Adapter, Kurzschluss tour→persist_user, 13 Pins + build.py-Wiring] · **page_context_enrich ✅ 2026-07-23** [#117, `graph/nodes/page_context_enrich.py` 59 Z., dedizierter Node ZWISCHEN tour↔context_greeting (nicht in setup: tour-Tick spart MCP-Latenz), 7-Key-Inject + best-effort `resolve_page_context` → populiert `_page_metadata`-Cache auf dem Normalpfad, **Greeting-TEXT-Pfad komplett** (Prod hängt nur an MCP), 5 Pins, pytest 1741/2]) | graph/nodes/{preflight,tour,context_greeting}.py + domain/{tour.py,context_greeting.py} | Port aus `chat_pipeline_phases._run_preflight_guards`, `chat_tour.py`+`tour_service.py`, `chat_context_greeting.py`; ALT-Tests (test_chat_endpoint Tour/CTX-Fälle, test_context_greeting.py) portieren |
| 4-3 | Parallel-Gruppe | graph/nodes/assess.py (safety∥classify∥memory mit Fallbacks wie ALT `_assess_safety_classify_memory`) | Timing-unabhängige Tests (Fakes) |
| 4-4 ✅ | Route-Node (+Tail) | graph/nodes/route.py + domain/{pattern_engine.py,policy.py,state_machine.py,quick_reply_policy.py,route_tail.py,lp_intent.py} + domain/cards/lp_diversity.py | Kern ✅ + **4-4-Tail-QR ✅** (`domain/quick_reply_policy.py`, 30 T) + **LP-Diversity ✅** (`domain/cards/lp_diversity.py`, 24 T) + **Route-Tail-Decisions ✅** (`domain/route_tail.py`: `_thema_plausible` [Topic-Gate, nested→top-level, AST byte-identisch] + `reconcile_effective_pattern` [inline→Fn, 4 Statements AST-identisch], 14 T) + **LP-Intent-Gate ✅** (`domain/lp_intent.py`: `detect_lp_intent` [Prolog-Entscheidung Z.196–281 inline→Fn: `_has_lp_intent` + `_thema`-Garbage-Reject + Force-Degradation, konsumiert `_thema_plausible`; 8 Statements AST-identisch modulo `req.message`→`message`], 13 T). **Reine LP-Prerequisites komplett** + **LP-Fast-Path-Body ✅** (→ `services/lp_fast_path.py`, s. 4-5). **Flip auf ✅ 2026-07-18 (Doku-Prüfung, Code-verifiziert): alle 3 Offen-Punkte in den 4-5-Slices erledigt** — Route-Node-Verdrahtung beider Fast-Paths ✅ (`route.py` ruft `run_lp_fast_path` + `run_canvas_create_fast_path`, inkl. `reconcile_effective_pattern`/`_qr_policy`/fp-Marker) · Canvas-Fast-Path-Body ✅ (`services/canvas_fast_path.py`) · Spec-Prefetch-Producer ✅ (`services/prefetch.py`; Launch/Konsum bewusst beim Tool-Loop 5-3/4-5 — bis dahin 0 Aufrufer, per grep verifiziert) |
| 4-5 🔄 | Respond-Node + SSE (+ Fast-Path-Bodies) | graph/nodes/respond.py, api/chat.py (POST /api/chat + /stream; Event-Namen/Format byte-identisch ALT `chat.py`-SSE) + services/lp_fast_path.py | **LP-Fast-Path-Body ✅** (`run_lp_fast_path`: Verbatim-Port ALT `_route_pattern` Z.282–597 = P1/P2/P3-Content-Gathering + Generierung + M09-Spec-QR + Canvas-State; AST-Block byte-identisch modulo Lazy-Import + 5 No-op-`resolve_discipline_labels`; 11 T faked-MCP/LLM). **Canvas-Subtree bottom-up gestartet: `domain/canvas/postprocess.py` ✅** (3 pure Markdown-Helfer + 10 LaTeX-Regexes, AST voll-Modul byte-ident, 19 T) + **`domain/canvas/types.py` ✅** (Material-Typ-Registry: 8 `_DEFAULT_*` + 8 config-Getter, AST voll-Modul byte-ident, 19 T; `config_loader/canvas` existierte bereits aus P2) + **`domain/canvas/intent.py` ✅** (7 pure Regex-Intent-Fn, AST voll-Modul byte-ident, 27 T). Der Canvas-Create-Fast-Path sitzt auf ~1500 Z./5 Modulen (config_loader/canvas→canvas_types→canvas_intent→canvas_service[+wikipedia_service]→`_canvas_completion_message`); **`domain/completion_messages.py` ✅** (Canvas-/LP-Bubble-Builder, pur/offline, AST voll-Modul byte-ident 0 Deviation, 18 T) + **`services/wikipedia_service.py` ✅** (volle Datei byte-ident, 20 T) + **`services/canvas_service.py` ✅** (eigene Fläche: 3 QR/Kategorie-Fn + async `generate_canvas_content` + `__getattr__`; **1 Transport-Deviation** `client.chat.completions.create(**build_chat_kwargs)`→`llm.chat_completion`; ALT-Re-Export-Fassade gedroppt [Konsumenten importieren aus `domain/canvas/*`]; AST 4 Fn byte-ident + gen modulo Transport, 22 T). **Ganzer Canvas-Teilbaum portiert.** + **`services/canvas_fast_path.py` ✅** (`run_canvas_create_fast_path`: Verbatim-Body-Port ALT `_try_canvas_create_fast_path` Z. 243–681, Schwester von run_lp_fast_path; kw-only + `CanvasFastPathResult`-NamedTuple [Feld-Reihenfolge = ALT-7-Tupel], `_lp_routed`→`lp_routed`; AST-Body 7/7 identisch, 12 T). **Beide Fast-Path-Bodies (LP + Canvas) fertig.** + **Route-Tail Teil 1+2 ✅** (`route.py`: LP-Fast-Path [Head-Gate `detect_lp_intent` + Body `run_lp_fast_path`] + Canvas-Create-Fast-Path + `reconcile_effective_pattern` + `_qr_policy` + fp-Marker verdrahtet; 11 neue TurnContext-Felder; Integrations-Glue, per Tests + ALT↔NEU-Statement-Mapping (Z. 196-674) verifiziert; +2 T, Suite 948; bei lp_routed→effective M09 + QR aus M09-Policy, Canvas weicht als Passthrough zurück). **Beide Fast-Paths im Route-Node verdrahtet.** + **Spec-Prefetch-Producer ✅** (`services/prefetch.py::run_speculative_prefetch`, Verbatim-Body-Port ALT `_launch_speculative_prefetch` Z. 111–399, AST 11/11 Nicht-Return byte-ident, Bare-7-Tupel→`SpeculativePrefetch`-NamedTuple; Sub-Dep `_retrieve_task_exception`→`obs/tasks.py`; 15+4 T; Konsum=Tool-Loop/P6). + **Card-Build ✅** (`domain/cards/build.py`: Verbatim-Port ALT `chat_cards`-Build/Relevanz-Cluster — `_build_cards`/`_sort_topic_pages`/`_PERSONA_TO_TARGET`/`_collection_matches_topic`/`_norm_words`; AST 4 Fn+Dict byte-ident, Import-Root-only-Deviation; 28 T aus ALT `test_chat_card_helpers.py`; 4-5-Assembly-Prereq). + **Guide-Marker-Strip ✅** (`domain/guide_markers.py`: `_strip_guide_markers_from_text`/`_strip_guide_qrs`/`_GUIDE_MARKER_RE`, 0-Deviation-Verbatim-Port ALT `chat_guide_markers.py`-Strip-Cluster — null app-Import, Alias `_re_guide_markers` verbatim; 10 T aus `test_guide_marker_strip.py`+`test_chat_guide_qrs.py`; 4-5-Prereq). + **guide_qr_injector ✅** (`services/guide_qr_injector.py`: whole-module Verbatim-Port ALT — 13 Fn + `_RULES`/`_RAG_AREA_URLS` + `inject_guide_qr`-Orchestrator; netz-frei verifiziert [kein httpx/requests, statische Ziel-URLs]; 3 lazy Import-Roots getauscht; AST 13 Fn+6 Tabellen byte-ident; UP035/E501-noqa/I001-Deviationen AST-neutral; 29 T/39 Fälle; Stage-3b-rag-chunk + 1 Test mit `rag_url_index`/P6 vertagt). + **Guide-Marker-Attach ✅** (`services/guide_markers.py`: `_attach_guide_qr` [Guide-QR an QR-Spitze via `inject_guide_qr`, gegated guide-mode+host-allow-list, Strip-Fallback bei Gate-zu] + `_attach_guide_urls` [`card.guide_url`-Annotation inline+canvas-payload]; Verbatim-Port ALT `chat_guide_markers.py`-Attach-Hälfte, AST 2/2 Fn byte-ident modulo 4 Import-Root-Swaps + UP037-Dequote; kein ALT-Unit-Test → 14 Verhaltens-Pins inkl. End-to-End gegen echten `inject_guide_qr`). + **Turn-Assembly ✅** (`services/turn_assembly.py`: `_assemble_cards_and_qrs`, Verbatim-Body-Port ALT `chat_turn_assembly.py` P20-P24 = Card-Enrichment + build + Pagination + Session-Refs + QR-Kaskade [forced>inline>none>Spec-Gate>exakt, Orphan-Cancel] + Guide-Deko + page_action-Ladder; AST byte-ident **0-Transform** [Body nutzt Bare-Names]; Prereqs `PAGE_SIZE`+`_is_themenseite_card`-Obj-Version verbatim in `cards/build`; kein ALT-Unit-Test → 21 Verhaltens-Pins). + **Session-Locks ✅** (`api/session_locks.py`: `_get_session_lock`/`_release_session_lock` + Registry aus ALT `chat_session_utils`, Per-Session-Turn-Serialisierung mit Refcount-TOCTOU-Cleanup; AST byte-ident **0-Transform** [pure stdlib asyncio], 10 Concurrency-Pins; beide Endpunkte klammern jeden Turn in `async with lock`). + **content-types ✅** (`domain/content_types.py`: whole-module Verbatim-Port ALT `chat_content_types.py`, 4 pure Fn + `_CONTENT_TYPE_KEYWORDS`, null app-Importe → ganzes Modul AST **byte-ident**; produziert `wanted_content_types`, das cards/normalize·select + card_pipeline schon konsumieren; 19 Verhaltens-Pins). Endpunkt-Layer (Respond/SSE) auf 3 blockierten Subsystemen (Graph 4-6 + Widget-Postprocess-692-Z.-Subtree + pg-`save_message`) → **bottom-up Endpunkt-Blocker-Leaves**. + **url_helpers ✅** (`domain/url_helpers.py`: whole-module Verbatim-Port ALT `chat_url_helpers.py`, `_extract_web_links_from_text` + `_rewrite_external_urls_to_repo`, null app-Importe → 8 Nodes AST **byte-ident**, 6 verbatim-noqa [ALT-Warzen F401/F811/E731/B023/UP037]; 23 Verhaltens-Pins). + **widget_modes ✅** (`domain/widget_modes.py`: `_widget_modes` Compat-Echo **byte-ident** [1 noqa UP037; Swap nur TYPE_CHECKING-Schema-Pfad], `_display_rules` BEWUSST weggelassen — NEU umgeht den Wrapper via quick_reply_policy [load_display_rules_config direkt]; 3 Pins). + **inline_rendering ✅** (`domain/inline_rendering.py`: whole-module Verbatim, 10 reine Fn + 2 Konst, 15 Top-Level-Nodes AST byte-ident, 4 verbatim-noqa [I001/F401/2×F811/E731], 45 Pins). + **_apply_llm_card_selection ✅** (`domain/cards/build.py` +42 Z., Port ALT `chat_cards`, rein/sync, Fn-AST byte-ident, build.py +logger, 8 Pins). Widget-Postprocess-Subtree = 2 Fn in `chat_postprocess.py`. + **_apply_widget_modes_postprocess ✅** (`domain/widget_postprocess.py` sync 265 Z., Fn-AST byte-ident modulo Import-Roots, 2 noqa, Dead-Branches verbatim erhalten [Vereinfachung deferred], 9 Pins). + **_looks_like_search_query ✅** (`domain/search_intent.py`, rein/sync, Fn-AST byte-ident, 0 noqa, 7 Pins; Orchestrator-Scope-Check: 5/7 Deps schon ✅). + **_fallback_inline_search ✅** (`services/prefetch.py`, async Verbatim-Body, Fn-AST byte-ident modulo 2 in-function Import-Pfade, 2 E501-Ternaries AST-erhaltend umgebrochen, 0 noqa, 7 Pins MCP-gemockt). **MEILENSTEIN: alle 7 externen Orchestrator-Deps ✅.** + **widget-postprocess-orch ✅** (`services/widget_postprocess.py`, async `_postprocess_response_for_widget_modes` 692 Z. Verbatim + Konstante, Fn-AST byte-ident modulo 5 in-function Import-Swaps [1 Split + 1 Reloc + 3 root], 7 noqa [5 Body + 2 I001], 8 Charakterisierungs-Pins Boundaries-gemockt; Dead not-cards_enabled-Zweige verbatim erhalten). **MEILENSTEIN: Widget-Postprocess-Subtree KOMPLETT** (sync + async Fn). + **turn_links ✅** (`services/turn_links.py`, `_finalize_links_and_metas` P27-P28 793 Z. Verbatim, Fn-AST byte-ident modulo 4 in-function Import-Swaps, 5 noqa, 8 Pins). Endpunkt-Scope-Check: `chat`/`chat_stream` sitzen auf `_chat_impl`→8 Turn-Phasen; 2 portiert (P20-24 ✅ + P27-28 ✅), Rest 6 pg-/Tool-Loop-gated. Scope-Check `_route_pattern` erledigt → **VERWORFEN** (route.py deckt P10-15 Kopf+Tail schon ab; 5 gedroppte resolve_discipline_labels-No-ops brächen das AST-Gate; Prefetch-Wiring auch geblockt). **P6-RAG-Pivot: rag-chunking ✅** (`domain/rag_chunking.py`, 3 pure Chunk-Fn `chunk_markdown`/`_merge_sections`/`_split_by_sentences` byte-ident, 8 Pins). **get_retrieval_settings ✅** (`services/rag/retrieval.py`, ENV>yaml-area>Defaults, byte-ident modulo 1 config-backend-Swap `_load_yaml`→`area`, 10 Pins). + **embedding-seam ✅** (`llm.embedding` + patchbare `_aembedding`-Boundary, Geschwister von chat_completion, Transport-Rewrite statt ALT-Side-Channel, 7 Pins netz-frei) + **rag-home an 6-1 angeglichen** (`services/rag/retrieval.py` + `rag/__init__.py`). + **P6-1-Kern search_rag_chunks + query_rag ✅** (pgvector-Cosine-Rewrite). **V13 entschieden+umgesetzt** (Embedding-Order-Seam `rag/rerank`) + **get_rag_context/get_always_on ✅**. + **RAG-Ingest-Kern ✅** (`rag/ingest.py`: convert verbatim + Store-Rewrite 1 Dok + N Chunks in 1 Transaktion). + **url_safety ✅** (whole-module verbatim, 21 Pins) + **convert_url_to_markdown ✅** (RAG-Service-Schicht komplett) + **6-2a ✅** (Session-DI `api/deps.get_session` + POST /query, Vertrag bewusst regeneriert) + **6-2b ✅** (Ingest-Endpunkte file/url/text, AST 3/3 byte-ident modulo 4 Transforms inkl. V11-config-swap, 19 frische Pins) + **6-2c ✅** (Admin-CRUD: neu `services/rag/admin.py` + 5 Endpunkte, created_at-Entscheid getroffen, operationIds stabil, 29+6 Pins). **Stand 2026-07-18: die hier genannten „Nächsten" sind erledigt** (6-2d ✅ · save_mcp_servers ✅ · pg läuft pro Session · Tool-Loop gestartet — 5-3: `_max_iterations_fallback` P16 ✅). Offen: Respond-Node/SSE (Port `test_chat_endpoint.py`, Catch-all-Degradations-Bubble) (`generate_response`-Orchestrator ✅ R1c 2026-07-18 `services/generate.py` — Tool-Loop 3/3 ✅ inkl. `llm_streaming`, Prefetch-Konsum verdrahtet) |
| 4-6 | Persist-Node + Checkpointer (= Restplan R4a persist + R4e graph/build; Vorstufe R3 ✅ = `db_sessions`-Memory + 3-5-Logging) | graph/nodes/persist.py, graph/build.py (Advisory-Lock um Turn; Postgres-Checkpointer) | End-to-End-Text-Chat (ohne Tools) gegen Dev-Compose; Golden-Teilmenge „reine Text-Flows" grün |

## P5 — WLO-Tools & Karten (L)

| # | Task | Port-Quelle | Verify |
|---|---|---|---|
| 5-1 | MCP-Client (SDK) + TTL-Cache + `__NEG__`-Sentinel | `mcp_transport.py`→SDK, `mcp_client.py`, `mcp_tool_cache.py` | ALT-Cache-Tests |
| 5-2 | Arg-Resolver + Tool-Defs + Parser | `mcp_arg_resolvers.py` (Vocab-Cache FIFO 5000), `mcp_tool_defs.py`, `mcp_parsers.py` | ALT-Parser-Tests (Cards/Swimlanes) |
| 5-3 ✅ | Tool-Loop + Prefetch | **outcome_service ✅** (`services/outcome_service.py`, Vorstufe) · **5-3-Rest pure Helfer ✅** (`domain/inline_grouping.py`: strip + Card-Prädikate + UI-Box-Footer + redact, 18 T, AST 7/7 byte-identisch) · **Tool-Loop-Body START ✅** (`services/tool_loop.py` NEU — Home-Name droppt ALT-`llm_`-Präfix wie `chat_prefetch`→`prefetch`, sitzt bei den Turn-Orchestratoren): **`_max_iterations_fallback` (P16) portiert**, 5 Pins (3 Branches: LLM-Summary / Card-Count-Fallback / no-cards-„keine Antwort" + Reasoning-Strip + no-cards-skip-LLM). Fidelity move-with-seam: 2/3 Statements `ast.dump()`-byte-ident, der 1 differierende Stmt hat Message+`temperature=0.4` byte-verbatim — nur `client.create(**build_chat_kwargs,model=MODEL)`→`llm.chat_completion` weicht ab (Regel 3, kein Modul-globaler Client; Präzedenz llm_curation). **Abtrennbarkeits-Check BESTANDEN**: `_run_tool_loop` RETURNIERT `(text,cards,tools,outcomes)\|None`, emittiert KEIN SSE — einziger Stream-Touchpoint ist der optionale `on_token`-Callback (→ Upstream-LLM-Token via `_stream_completion`, NICHT der Widget-SSE-Layer; ALT trennt `llm_tool_loop`/`llm_streaming` als eigene Module, Plan-Z. 231) → sauber ohne 4-5-Streaming baubar. + **`_assemble_messages` (P12/P14) ✅ 2026-07-18** (Verbatim-Port ALT Z. 239–563; 2 NEU-Deviationen: `session` als 1. Param [pg-DI für `get_rag_context` — ALT holte sqlite im rag_service selbst] + `resolve_discipline_labels`-Calls gedroppt [ALT-No-op-Stub, lp_fast_path-Präzedenz]; AST-Gate 29/29 Statements ident nach 5 sanktionierten Transforms [6 Import-Swaps · 2 No-op-Drops · session-Seam im `_get_rag_ctx`-Call · Signatur-Prepend · Docstring]; kein ALT-Unit-Test → 17 frische Pins: Canvas-Kontext [material/cards/empty + 4000-Cap] · RAG-Always-Prefetch [Gate zu/leerer Kontext/out_sources-Dedupe in session_state] · MCP-Primary [Parser-Wahl topic_pages/collections-node_type/blocked/Parse-Fehler-Degrade] · Extras [eindeutige tool_call_ids, ALT-Wart „Seeding zählt auch geskippte Extras"] · node_id-Dedupe+topic_pages-Backfill · UI-Box-Footer nur inline · Settings-Passthrough). **`_run_tool_loop` (P15) ✅ 2026-07-18** — Verbatim-Port ALT Z. 565–1158 (tool_choice-Gates, Verbosity-Mapping, Stream-vs-Create, Usage-Phase-Label, select_top_cards/respond_to_user/query_knowledge, Blocked/maxResults/Entity-Filter-Injektion, call_with_outcome-Dispatch, Card-Parse-Merge-Dedupe, Reflection-Retry A1). AST-Gate: 206 verschachtelte Statements identisch nach sanktionierten Transforms (5 Import-Swaps · 1 resolve-Drop · Transport-Swap ×2 [`build_chat_kwargs(model=MODEL,…)`→`dict(…)`, `client.…create`→`llm.chat_completion`] · 2 Usage-Renames [obs.usage `add_usage`/`extract_usage`] · session-Seam am `get_rag_context` · Signatur-Prepend · Docstring); Signatur session + 22 identische ALT-Params. 24 frische Pins (kein direkter ALT-Unit-Test; u.a. Reflection ANY/ALL + „(prefetch)-Suffix erfüllt"-Wart, B8-malformed-JSON, P16-None-Marker, Entity-Filter-Injektion, Card-Gate/Merge/Promote). **Dazu R1b-1 `services/llm_streaming.py` ✅ 2026-07-18** — ALT-llm_streaming-Port: 4 Rekonstruktions-Klassen + `_RespondToUserExtractor` verbatim; `_stream_completion` = Streaming-Zwilling von `chat_completion` auf semantischen kwargs (NEU-Deviation dokumentiert: kein client-Singleton, `wire_transport`-Helper aus llm.py geteilt, Patch-Punkt bleibt `llm._acompletion`; Live-Semaphor hält über die GANZE Stream-Konsumption — ALT-Bulkhead war der httpx-Pool; `_make_think_safe_on_token`→`ThinkSafeStreamer`); 13 Pins = 10 ALT-Test-Ports (test_llm_service_generators) + 3 NEU-Transport-Pins. **R1c ✅ 2026-07-18**: `generate_response`-Orchestrator (`services/generate.py`, Verbatim-Port ALT `llm_service.py:160-312` + session-Seam; ruft `_build_system_prompt`/`_select_active_tools`/assemble/loop/fallback ✅; AST 7 Stmts `ast.dump`-ident modulo 3 Seams [1 Sig + 2 Call-Args], 4 Pins [2 Spy-Wiring inkl. mcp/aa-Reorder + session-Seam + blocked→[] · 2 Integration real assemble+loop+fallback]; Prefetch-KONSUM verdrahtet, Launch = R4/`turn_setup`) → **5-3 Tool-Loop 3/3 komplett** | ALT-Loop-Tests |
| 5-4 | Cards-Domain | `chat_cards.py`, `card_pipeline.py`, `chat_facets.py`, `chat_url_helpers.py`, `chat_turn_links.py` | ALT-Tests (Boxing/Merge/Diversity/Facetten) |
| 5-5 | Reranker-Gate ✅ | **`services/card_reranker.py` (1:1-Port, In-Proc-Scorer-Seam `_get_reranker`)** — **Entscheid 2026-07-12: KEIN Netzwerk-Dienst** (TEI-Sidecar aus Kostengründen verworfen); Scorer-Backend (lokales Modell / lexikalisch / keiner) = P6-Entscheid; alte „HTTP zu TEI"-Zeile obsolet | Fake-Scorer-Test; Gate-Envs CARD_CE_* wirken |
| 5-6 🔄 | Direct Actions + M16 | **5-6a ✅** `services/llm_learning_path.py` + `services/llm_curation.py` (reine 1-LLM-Call-Generatoren, Transport→`llm.chat_completion`, Prompts verbatim, 10 T, AST-Diff 0 Divergenz). **5-6b ✅** `services/topic_pages.py` (3 stateless+warmup Such-Helfer aus `chat_topic_pages.py`, 31 T, AST 0 Divergenz). **Direct-Actions ✅ R5 2026-07-18** (`services/direct_actions.py`: browse/lernpfad/curate + `_direct_action_safety_text`, DI-Rewrite [session-Inject → save_message/update_session, entities jsonb-dict statt json.dumps, resolve_discipline_labels-Drop, _display_rules()→load_display_rules_config()], PAGE_SIZE aus domain/cards/build wiederverwendet, 14 Pins). Offen nur `_resolve_m16_topic_page_view` (M16 collectionId-Kurzschluss, braucht tracer/winner/Swimlane-Schemas → mit respond/R4) | ALT-Tests; Golden-Such-Flows grün |

## P6 — RAG & Reranker (M)

| # | Task | Inhalt | Verify |
|---|---|---|---|
| 6-1 ✅ | Retrieval | services/rag/retrieval.py (pgvector cosine, RAG_TOP_K/MIN_SCORE/MAX_CHARS, Area-Modi always/on-demand aus rag-config) | **Chunking ✅** (`domain/rag_chunking.py`, 3 pure Fn AST byte-ident, 8 Pins) + **get_retrieval_settings ✅** (ENV>yaml-area>Defaults, byte-ident modulo config-backend-Swap `_load_yaml`→`area`, 10 Pins) + **Embedding-Boundary ✅** (`services/llm.embedding` über LiteLLM `aembedding`, Geschwister von chat_completion, patchbares `_aembedding`; Transport-Rewrite statt ALT-OpenAI-Side-Channel, Modell/Dim aus Env → MUSS zur pgvector-Dim passen; 7 Pins netz-frei). + **search_rag_chunks + query_rag ✅** (pgvector-Cosine-**Rewrite**: `<=>` + area-Filter in-query [ALT-Over-Fetch `top_k*5` entfällt], score=1−cosine_distance [ALT: 1/(1+L2)] → Ranking weicht bewusst ab, RAG_MIN_SCORE ist der Stellhebel; LEFT JOIN `rag_documents` für title/source [NEU normalisiert], NULL-Embeddings raus, `AsyncSession` per DI/Regel 3; Dict-Contract ALT-identisch; 8 lokale Pins [DB gefakt + SQL gegen PG-Dialekt kompiliert] + 2 pg-gegatete Integrationstests `tests/test_rag_search_pg.py` [lokal geskippt]). + **V13-Entscheid umgesetzt** (`services/rag/rerank.py`: `rerank_results`+Env-Knopf ALT-verbatim, `_get_reranker`-Seam mit Embedding-Order-Default [Bi-Encoder≡No-op-Beweis], CE-Slot offen; card_reranker-Import auf den Seam gefixt) + **get_rag_context/get_always_on_rag_context ✅** (Bodies AST-byte-ident per Transform-Beweis modulo Session-DI/Transport/Pool-Drop/Root-Swap; 22 Pins) → **6-1 Retrieval-Pfad komplett**. + **Ingest-Kern ✅** (`rag/ingest.py`: `convert_to_markdown` verbatim [AST byte-ident] + `ingest_document`/`get_rag_chunks` Schema-Rewrites [1 Dok + N Chunks, Float-Embeddings, 1 Transaktion], 5 Pins). + **url_safety ✅** (`services/url_safety.py` whole-module verbatim byte-ident, T8/T9/N-2, 21 Pins) + **convert_url_to_markdown ✅** (Fn-AST byte-ident modulo 1 Import-Root-Swap, 9 Pins; **RAG-Service-Schicht komplett** — ALT rag_service 15/23 portiert + 8 dokumentierte Drops, db_rag 2/3 + store_rag_chunk absorbiert). **Flip auf ✅ 2026-07-18 (Doku-Prüfung): die Offen-Punkte sind eingelöst** — RAG-Router = 6-2 ✅ (eigene Zeile) · pg-Tests unter Compose LIEFEN (`test_rag_search_pg`/`-admin_pg`/`-embed_pg` gegen echtes pgvector, Teil der 62 pg-Tests, Suite 1470/2). **Ehrliche Restlücke:** ein EXPLIZITER Ingest→Search-Roundtrip-pg-Test existiert nicht — stückweise abgedeckt (Ingest-Endpunkt-Pins offline + pgvector-Suche auf geseedete Chunks + import-rag-CLI-e2e); Ragas-Vergleich = Nutzer-Domäne (wie 6-3). Port `rag_service.py`-Tests (Embedding-Boundary gefakt) |
| 6-2 ✅ | Ingest + Router | services/rag/ingest.py (MarkItDown + SSRF-Guard-Port aus `url_safety.py`, Größen-Caps) + api/rag.py (alle §5.1-RAG-Routen) | **Ingest-Modul ✅** (convert/convert_url verbatim + pg-Store-Rewrite) + **url_safety ✅** (SSRF T8/T9/N-2). **In 4 Slices geschnitten**: **6-2a ✅** Session-DI (`api/deps.get_session` + Lifespan-`session_factory`, Regel 3) + POST /query (Fn-AST byte-ident inkl. Decorator modulo 2 Session-DI-Transforms; Vertrag bewusst regeneriert: nur /api/rag/query rückt auf ALT zu; Konvention `Annotated[AsyncSession, Depends(...)]` = kein B008-noqa; 7 Pins, Router offline testbar via TestClient-ohne-`with` + dependency_overrides) · **6-2b ✅** Ingest-Endpunkte file/url/text (Verbatim-Port ALT Z. 23-124, Fn-AST 3/3 byte-ident inkl. Decorator modulo 4 Transforms: annotated-param-Swap [6-2a-Konvention trägt File()/Form() → 0 B008-noqa], Session-DI-Arg, Call-Arg, **V11-config-swap** `os.getenv`+try/except→`settings.max_ingest_mb` [V11 = settings.py:4-7 fail-fast statt silent fallback, P0-3-Beschluss; Default 25/Env 50 in test_settings schon gepinnt; RAG_* bleiben bei os.getenv, weil None-Default = 'layer decides']; Größen-Cap Iron Rule 9 mit exakter Byte-Grenze gepinnt [`>` nicht `>=`], cap=0→unbegrenzt; 19 frische Pins — **kein ALT-Test existierte**; tempfile.tempdir→tmp_path statt Mock; on-disk-413 über HTTP unerreichbar [starlette setzt `size` immer] → per Direktaufruf gepinnt; ALT-Quirk ingest_text verbatim) · **6-2c ✅** Admin-CRUD (neu `services/rag/admin.py` = **Regel-4-Layering**: ALT fuhr roh-sqlite IM Router, NEU hält DB-Zugriff im Service; nur `get_rag_area` ist Verbatim-Port [Fn-AST byte-ident modulo Rename + Session-DI + Call-Arg], die 4 pg-Rewrites sind verhaltens-gepinnt. **`created_at`-Entscheid getroffen**: sitzt in NEU auf `rag_documents` → jeder Chunk meldet den Doc-Stempel, Response-Form bleibt exakt ALT, Wert faktisch identisch [ALTs Chunks eines Ingests teilten die Sekunde]; ISO-String aus dem Service, damit der Router-Body verbatim bleibt. **rag_vec-Sweeps ersatzlos gestrichen** [pgvector = Spalte auf rag_chunks, Vektor stirbt mit dem Chunk; sqlite-vec brauchte den Sweep, weil eigene Tabelle+Handle ausserhalb der Transaktion]. Stub-Namen behalten → alle 5 operationIds stabil. `delete_area` räumt zusätzlich `rag_documents` [sonst leere Hüllen]. 29 Pins + 6 pg-gegatete [CASCADE-Beweis, lokal ungelaufen]) · **6-2d ✅** POST /embed = **letzter RAG-Stub** (`embed_missing_chunks` in `services/rag/ingest.py`, Regel-4-Layering wie 6-2c; Router baut ALTs 2 asymmetrische Antwortformen [message-ohne-total vs total-ohne-message], `-> dict` behalten → Vertrag nur um die Docstring-`description` erweitert, Schema/operationId/security byte-ident. **Fidelity als Rewrite**: kein AST-Vergleich möglich → mechanische Enumeration ALT↔NEU [10 Verhalten übernommen, 7 Drops enumeriert, 0 unerklärt] + Literale byte-ident [`ok`, `All chunks already have embeddings`, `Embedding failed for chunk %d: %s`]. Drops: `embedding_to_bytes`/`struct.pack`, `rag_vec`-Mirror + `EMBED_DIM*4`-Guard, `aiosqlite`/`_connect_vec`/`DB_PATH`, dazu ALTs totes `import struct`. **SAVEPOINT je Chunk = einzige Zutat, verhaltens-ERHALTEND**: ALTs `except`-continue funktionierte nur auf sqlite; pg bricht die ganze Transaktion ab → ohne `begin_nested` würde ein Dim-Mismatch alle Folge-Chunks + den Commit reißen [500], ALT antwortete 200. Nebenbei entfällt eine ALT-Falle: falsch-dimensioniertes Embedding wurde VOR dem Guard in `rag_chunks` geschrieben → Chunk non-NULL [nie erneut versucht] aber nie in `rag_vec` [nie suchbar]. **Befund**: in NEU erzeugt KEIN Pfad `embedding IS NULL` — `ingest_document` bettet inline ein; ALTs Produzent war der Seed-Import [`db_init.py` Z. 437-448] + Startup-Hook [`main.py:83`], NEU hat kein RAG-Seed-Gegenstück → `/embed` ist Backfill für Dump-Restore/Manual-Insert, Startup-Auto-Call bewusst NICHT portiert. 10 Pins + 4 pg-gegatete [Savepoint gegen echtes pgvector, lokal ungelaufen]; `todo`-Import entfiel → **0 Stubs im RAG-Router**). **`text_extraction_service.py` NICHT portieren** — in ALT toter Code (0 App-Importeure, nur Eigen-Test) — ursprüngliche Verify-Spalte: ALT-Ingest-Tests inkl. SSRF-Fälle |
| 6-3 | Reranker-Backend (V13, **kein Netz-Dienst**) | In-Proc-Scorer hinter `card_reranker._get_reranker()`: **Bi-Encoder-Cosine als Default-Option** (mehrsprachiges sentence-transformers-Modell = derselbe 6-1-Embedder → kein Zweitmodell; Query+Doc→Cosine→Score; Gate `CARD_CE_*` auf Cosine re-kalibriert) · Cross-Encoder (ALT-Parität) · lexikalisch (`_relevance_score`) · aus. A/B auf echten WLO-Queries entscheidet | RAG-Golden-Stichprobe Top-3 ALT-CE vs NEU-BiEncoder dokumentiert; **Mehrsprachigkeit geprüft (DE + nicht-DE Query)** |
| 6-4 ✅ | Import-CLI | `boerdi import-rag --sqlite <kopie>` → `services/rag/import_rag.py`: liest ALT `rag_chunks` NUR Text (`mode=ro`, read-only), gruppiert nach (area,source,title) → `rag_documents` + N `rag_chunks`, **re-embedded** jeden Chunk via LiteLLM in pgvector (BLOBs NICHT übernommen §9.2, NEU-Dim kann abweichen). Guardrail: Quell-DB nie geschrieben, `--sqlite` required (kein Default auf ALT-DB). tier-C Greenfield (keine ALT-Vorlage). | 7 Tests: 5 offline (read text-only + Reihenfolge, pure Gruppierung, CLI missing-arg/missing-file, **Quell-DB-Hash unverändert**) + 2 pg-e2e (Service→rag_documents/chunks korrekt + `main(["import-rag",…])` gegen **echte pg**, embedding gemockt dim-agnostisch via `get_embed_dim`). Suite **1465/2** (pg oben), ruff clean, Vertrag unchanged |

## P7 — Feature-Parität Rest (L)

**Bereinigt 2026-07-18 — bereits in P4-5-Slices erledigt, NICHT mehr P7-Scope:** Canvas-Cluster ✅
(`domain/canvas/*` + `services/canvas_service`), Inline-Docs+Completion ✅ (`domain/inline_rendering`
+ `domain/completion_messages`), QR-Policy ✅ (`domain/quick_reply_policy`), Guide-Cluster ✅
(`domain/guide_mode` + `services/guide_qr_injector` + `domain/guide_markers` + `services/guide_markers`),
Widget-Modes/Display-Echo ✅ (`domain/widget_modes` + `domain/widget_postprocess` +
`services/widget_postprocess`), Wikipedia-Service ✅.

**Verbleibender P7-Scope (= Restplan R6), Ports mit ihren Tests:** page_context
(`page_context_service.py` 596 Z. mit compendium/fulltext — wird vom Tool-Loop NICHT gebraucht,
Konsument ist die Endpoint-/Setup-Schicht), Memory-API + sessions-Router (`db_sessions.py` 213 Z. —
der Memory-Port selbst ✅ R3a 2026-07-18 (`services/db_sessions.py`), hier nur der Router), Speech-Proxy (`speech.py` mit Caps),
Quality-/Safety-/Eval-/Loadtest-Router (inkl. V9-Persistenz), Widget-Auslieferung V1 (hash+301),
Demo-Seiten.
**Abnahme P7: volle Golden-Suite (12/12) grün gegen NEU; Endpoint-Inventar §5.1 komplett
(Skript diff't OpenAPI gegen eingefrorenen Vertrag).**

## P8 — Widget (L; + /better-coding-frontend)

| # | Task | Inhalt |
|---|---|---|
| 8-1 ✅ | Workspace + ui-Lib-Gerüst | Angular 21 zoneless, `@angular/build`-Builder; `projects/ui` (pfad-gemappt `@boerdi/ui`, kein ng-packagr) + `projects/widget` (Element `<boerdi-chat>`); M3-Token-Layer `ui/theme/tokens.scss` + `applyPrimaryColor` (`--boerdi-primary`, CSS-Injektion validiert); `build-widget`-Budget 420 kB in angular.json; je Projekt eigenes `@angular/build:unit-test`-Target. `studio`-Projekt→P9 |
| 8-2 🔄 | ui-Ports mit Specs | **8-2a ✅** trusted-host+session-id (V5) → `ui/session/`, 23 Specs · **8-2b ✅** markdown+latex+icons → `ui/markdown/`+`ui/icons/`, DOMPurify-Policy identisch, 13 Specs · **8-2c ✅** chips guide-qr/action-qr → `ui/chips/` (ALT-Spec verbatim), 17 Specs · **8-2d ✅** page-context-detector → `ui/page-context/` (ALT-Spec verbatim = 7-URL-Golden, 14 Specs; DOM/Orchestrierung fidelity-portiert, URL-Layer getestet wie ALT) · **8-2e ✅** cards-Logik → `ui/cards/{card-types,card-utils}.ts` (WloCard-Typ + 6 Helfer verbatim; ALT-Klassifikations-Spec verbatim + Render-Charakterisierung, 18 Specs) · **8-2f ✅** WloCard-Tile → `ui/cards/wlo-card-tile.component.{ts,scss}` (standalone/OnPush/Signals; visueller Verbatim-Port ALT `.wlo-card` chat.component.html:246-294; präsentational — href/tooltip als Inputs) + Prereqs `SafeSvgPipe` (ALT-verbatim →`ui/icons/`) & `getLicenseShort` (ALT-verbatim →`ui/cards/license.ts`); SCSS byte-nah (ALT-`$brand-blue` fix, nicht `--boerdi-primary`) + reduced-motion; TestBed-Komponenten-Spec fand `[title]="null"`-Bug (→`[attr.title]`); ui 100 + widget 2 grün, Bundle 173,7/51,8 kB. **Re-Slice** (Bündel ≠ 1 Slice): 5-Box-Typen → 8-2g (`result-grouping.utils`-Port + `ChatMessage`-Typ) + 8-2h (Box-Render); flat-cards-Grid+Pagination+`.card-actions` → 8-2i (nach Chat-Shell 8-4). · **8-2g ✅** result-grouping → `ui/grouping/{result-grouping,message-types}.ts` (verbatim-Port ALT `result-grouping.utils.ts`: grouped*-Selektoren/Such-URL-Fallback/webLinks-Kette/Bullet-Strip/Tooltips/hasGroupedResults + `GroupingContext`; schmaler `ChatMessage`=6 Grouping-Felder [wächst in 8-4] + `QueryMetaEntry`/`WebLink` verbatim; 25 Charakterisierungs-Specs; 364 Z. dok. Ausnahme; ui 125 grün). · **8-2h ✅** ResultGroups-5-Box-Renderer → `ui/grouping/result-groups.component.{ts,scss}` (visueller Verbatim-Port ALT Inline-Grouping-Block chat.component.html:133-236 + `.result-group*`-SCSS: Themenseiten/Sammlungen/Materialien/Webseiten-Boxen + Such-CTA `_self`/`_blank`; konsumiert 8-2g-Utils; Wrapper self-gated auf `hasGroupedResults`; `ResultGroupsContext extends GroupingContext`+`isTrustedHost`; `@if`/`@for track $index`, `[attr.title]`; 7 TestBed-DOM-Specs; 233/146 Z.; a11y-Sweep→8-6; ui 132 grün). · **swimlanes ✅** Themenseiten-Schwimmlinien → `ui/grouping/swimlanes.component.{ts,scss}` (Verbatim-Port ALT chat.component.html:97-131: je Swimlane `result-group--topic`-Box [Heading+„(Auszug)", Fallback „Inhalte"] + Themenseiten-CTA [rohe `topic_page_url`, `_blank`]; `SwimlaneBox`/`TopicPageView` verbatim aus ALT; teilt `.result-group`-SCSS mit 8-2h via extrahiertem `_result-group.scss`-Partial [behavior-preserving Refactor]; 3 TestBed-DOM-Specs; ui 135 grün). · **inline-doc ✅** InlineDocuments-Box → `ui/inline-doc/{inline-doc.ts, inline-documents.component.{ts,scss}}` (Verbatim-Port ALT chat.component.html:37-52 + `.inline-document`-SCSS 450-564: je Doc Kind-Icon+Titel/Fallback+Print-Button+Markdown-Body; `InlineDocument`-Typ verbatim; präsentational — `renderMarkdown`-Seam [MarkdownRenderer 8-2b] + `print`-Output [print-utils→8-4]; Helfer `inlineDoc{FontSize,Icon,FallbackLabel}` verbatim; 6 Specs; ui 141 grün). **8-2-Renderer komplett** — Offen nur 8-2i (flat-list/pagination/actions, nach Chat-Shell 8-4) · **8-2i Flat-Cards ✅ 2026-07-25** → `ui/cards/card-list.component.{ts,scss}` (227/199 Z.): Tile-Grid + Sammlungs-Aktionsleiste (Inhalte/Lernpfad/Themenseite + Varianten-Dropdown samt ALTs `@HostListener('document:click')`-Schließen) + Pagination (Zähler, client-seitiges Aufdecken, server-seitiges Nachladen); visueller Port ALT chat.component.html:240-378 + SCSS 420-425/905-1039/1073-1113 (Range-Extraktion). Das Tile (8-2f) bekam `<ng-content />` IM `.wlo-card-wrapper`, weil ALTs `.card-actions` dort als Geschwister liegt (die Rundungsregel `:not(:has(.card-actions))` hängt daran) — Projektion, damit das Tile präsentational bleibt. **BEFUND + Nutzer-Entscheid**: ALTs Flat-Block ist hinter `!inlineResultGroupingBool` **unerreichbar**, weil das Flag seit Welle E eine auf `true` eingefrorene Compat-Hülle ist (chat.component.ts:201, ALT-Kommentar: „View-Conditionals werden separat aufgeräumt“). Statt totes Template zu portieren ist `inline-result-grouping` **wieder ein echtes Host-Attribut** (`input<boolean|string>(true)` + `_attrIsTrue`): Default `true` = Boxen-Layout wie bisher (kein Verhaltensunterschied für bestehende Embeds), `false` = klassischer Tile-Grid. Shell: 4 Delegates auf `collection-actions` (browseCollection/generateLearningPath/showMoreCards/loadMoreCards) über den 8-4S-d1-Context; `cardsEnabledBool` kehrte zurück (jetzt MIT Konsument). Selbst-Review-Fixes: `onCard*`-Wrapper raus (Template destrukturiert `$event` direkt), `topicPages()`-Accessor statt `?.`/`!` im Template (NG8107 weg; `WloCard.topic_pages` ist im Typ nicht-optional, in echten Payloads aber oft ungesetzt — ALT prüfte darum explizit). Falle: **Backticks in einem `template:`-Literal beenden den String** (mein Tile-Kommentar brach die Datei; Symptom waren irreführende NG2012/NG8110 in *anderen* Dateien). Verifikation: `npx ng test ui` **46 Dateien / 390 Tests** grün (373→390), `npm run build:widget` 179,90 kB/54,33 kB unverändert. Shell-Komponente ~508 Z. (dok. Integrator-Ausnahme). **UNVERIFIZIERT (visuell)**: ob `:has(.card-actions)` bei emulierter Encapsulation auf den projizierten Knoten greift — betrifft nur die Kartenecken-Rundung, prüfen in 8-7/live. |
| 8-3 ✅ | Stream-Client | `ui/stream/stream-client.ts` — Verbatim-Port ALT `ApiService.sendMessageStream`/`sendMessage`-SSE-Kern: `streamChat` (fetch+ReadableStream, event/data-Parse, `connected`/`phase`→onEvent, `result`→resolve, `error`→reject), Watchdogs **B9 Idle 90 s** (Byte-Reset→Abort/non-stale) + **B10 Stale 100 s** (nur benannte Events reset→`StreamStaleError`, Aufrufer fällt NICHT auf POST), `parseSseBlock` (pure, Keepalive-Skip/multi-data/JSON-Fallback), `postChat` (Fallback-POST). `fetchImpl`/`idleMs`/`staleMs` injizierbar für Tests; environment-Formung + `ChatResponse`-Typ → 8-4. `StreamStaleError`-Klasse (`.name`-Kontrakt wie ALT + instanceof). 11 Specs (parse + Contract + beide Watchdogs via fake-timers + postChat); 190 Z.; **ui 152 + widget 2 grün**, Bundle 173,7 kB |
| 8-4 🔄 | Chat-Shell + Controller-Ports | In Sub-Slices zerlegt. **8-4a ✅ print-utils + logo** → `ui/print/print-utils.ts` (Verbatim-Port ALT chat/print-utils.ts: `printMdToHtml`/`safePrintHref`/`PRINTABLE_CANVAS_RE` + 3 window.open-Print-Fns [InlineDoc/Canvas/Lernpfad]; Imports umgehängt stripLatex→`markdown/latex`, ChatMessage→`grouping/message-types`, Logo→`branding/`; ALT-Spec verbatim = 5 Tests) + `ui/branding/boerdi-logo.ts` (byte-exakt kopiert: `BOERDI_LOGO_SVG`/`_DATA_URL`/`boerdiLogoUrl`). Encoding-Falle: verbatim-Datei-Ports via `Copy-Item`/`[IO.File]::ReadAllText(UTF8)`, NICHT `Get-Content -Raw` (ANSI). 350 Z. dok. Ausnahme; Bundle 179,9 kB (+6,2 Logo-IIFE, ≪420); ui 157 grün. **8-4b ✅ tour.controller + Response-Modell** → `ui/controllers/tour.controller.ts` (Verbatim `TourController`+`TourContext`-Seams: startTour/sendTourTick/applyTourState/tourEnv/localStorage-Flag) + `message-types.ts` gewachsen um **`ChatResponse`+`PaginationInfo` voll, `DebugInfo` minimal** (`pattern?`+Index-Sig; volle Debug-Sub-Typen → Debug-Panel-Slice). 7 Charakterisierungs-Specs (kein ALT-Standalone-Spec); ui 164 grün. **8-4c ✅ context-greeting.controller** → `ui/controllers/context-greeting.controller.ts` (Verbatim `ContextGreetingController`: stiller `sendContextPing` [env page_event=context_open+page_context, Render nur bei Inhalt], Ping-Guard + resetForNewPage; 5 Specs; ui 169 grün). **8-4d ✅ collection-actions** → `ui/controllers/collection-actions.ts` (byte-exakter Copy-Item-Port ALT chat/collection-actions.ts: `browseCollection`/`generateLearningPath`/`showMoreCards`/`loadMore` + `CollectionActionsContext`-Seams [deferred Arrows, Muster TourContext]; Imports umgehängt WloCard→`cards/`, Response-/Message-Modell→`grouping/`; `ChatMessage` +`id?`/`pagination?`/`visibleCardCount?` [optional, Shell konsolidiert zu ALT-required]; 15 Charakt.-Specs pinnen Render-Arg-Reihenfolge (queryMetas=undefined@Pos7)/Loading-Guards/Fehlertexte/+5-Fenster+Scroll-Ziel/newSkip+Card-Merge; ui 184 grün, Bundle 179,9 kB unverändert). **8-4e ✅ speech.service** → `ui/speech/{speech.service.ts,tts-text.ts}` (Copy-Item-Verbatim-Port ALT chat/speech.service.ts [STT-Recorder + TTS-Playback, plain class mit Komponenten-Lebenszeit, `SpeechContext`-Seams]; ALT bewusst UNGETESTET [jsdom ohne MediaRecorder/getUserMedia/Audio] → 8 Charakt.-Specs decken NUR Nicht-Browser-Pfade [autoSpeak sender/isLoading-Selektionsfilter, Stop-Guards, Empty-Text-Frühausstieg, mic-loser toggleRecording-Catch, destroy-No-Throw]; Audio/Recorder-Erfolg dok. ungetestet, live via 8-7. `tts-text.ts` = 2 pure TTS-Helfer `stripMarkdown`/`splitSentences` byte-genau aus ALT chat-text-utils [dekomponiert: stripLatex→markdown 8-2b, getLicenseShort→cards 8-2f bereits portiert; formatPhaseLabel/_attrIsTrue folgen mit Shell/8-5], 6 Specs [Test-Erwartungs-Bug Merge-Schwelle <20 gefangen+gefixt, Code korrekt]. `ChatMessage` +`sender?`/`isLoading?` [optional]; 342 Z. dok. Fidelity-Ausnahme wie print-utils; ui 198 grün, Bundle 179,9 kB unverändert). **quick-replies ✅ (nachgezogener 8-2-Renderer)** → `ui/chips/quick-replies.component.{ts,scss}` (visueller Verbatim-Port ALT Chip-Reihe chat.component.html:400-416 + `.quick-replies`/`.qr-btn`/`.qr-btn--guide`-SCSS: Standard- vs. Guide-Chip [`__guide__`], Action-Pill-Label statt Roh-String, Guide-Ausblendung bei Lotsen-Modus-aus; konsumiert die 8-2c-Chip-Helfer [actionQuickReplyLabel/isGuideQuickReply/shouldHideGuideQuickReply/guideQuickReplyLabel] statt Reimplementierung; **präsentational** — nimmt QR-Strings DIREKT als Input [kein ChatMessage-Wachstum in diesem Slice] + emittiert bei Klick den ROHEN qr-String via `output()` [quickReply/guideQuickReply], der Shell routet Tour/Action/Text bzw. Same-Tab-Navigation [ALT onQuickReply/onGuideQuickReply]; erster event-emittierender Renderer; `@if`/`@for track $index`, statischer guide-`title`; SCSS byte-nah + reduced-motion; 8 TestBed-DOM/Emit-Specs; a11y-Sweep→8-6; ui 206 grün, Bundle 179,9 kB unverändert). **Debug-Panel ✅** → `ui/debug/debug-panel.component.{ts,scss}` (visueller Verbatim-Port ALT Diagnose-Panel chat.component.html:422-607 + `.debug-*`-SCSS 1227-1308: 6 Phasen-Gruppen [State/Klassifikation/Pattern-Engine/Modulation/Tools/Safety-Policy-Context] + Pattern-Hint/Tie-Breaker/Token-Usage; präsentational — 2 Inputs `debug`/`show`, Selbst-Gate wie ALT [`showDebug && latestDebug`]; `Math` als Feld exponiert für die Parallel-Trace-Bars; `*ngIf`→`@if`, `else linearTrace`→`@else`, `@for track $index`; **volles `DebugInfo` + 5 Sub-Typen** [ToolOutcome/SafetyDecision/PolicyDecision/ContextSnapshot/TraceEntry] verbatim aus ALT api.service.ts in message-types.ts nachgewachsen — Blast-Radius sauber: 3 controller-spec `makeResp`-Fixtures `debug: {…} as DebugInfo` gecastet [RED bewies: nur die fehlende Komponente, keine weiteren TS-Brüche durchs Modellwachstum]; 9 Feld-für-Feld-TestBed-Specs [Gate, 6 Sektionen, State-Übergang-Warn, Safety-Zeile, Outcomes, Trace linear+parallel mit Offset/Breite %, phase2-scores]; erroneous `.debug-score`-SCSS entfernt = byte-verbatim [ALT hat keine]; Datei >300 Z. dok. Fidelity-Ausnahme [kohäsive Diagnose-Ansicht]; a11y-Sweep→8-6, hier Farbe+Symbol+Text [nie nur Farbe]; ui 215 grün, Bundle 179,9 kB unverändert). **Offen 8-4: nur noch die Shell** (Integrator — verdrahtet session/stream/page-context/grouping/tile/swimlanes/inline-doc/quick-replies/debug-panel + alle Controller/Speech; das volle ChatMessage-Modell [id/sender/timestamp required + loadingPhase/inlineDocuments/topicPage/quickReplies] konsolidiert HIER). Scoping 2026-07-24: Header/Avatar/Status = ALT `widget.component.ts` = Shell/8-5-Territorium (kein Standalone); „Owl-Hint" existiert im ALT-Template NICHT (Platzhalter-Label). **8-4S Explore→Plan ✅ 2026-07-24** (ALT `ChatComponent` = 1480-Z.-Monolith → Re-Architektur in ≤300-Z.-Stücke, NICHT verbatim; Zerlegung in MEMORY: Prereq-Leaves 0a host-events / 0b link-handoff · a ChatMessage-Vollmodell · b State-Core · c sendMessage · d Controller-Wiring · e ngOnInit · f message-row-Template · g host-events-Wiring). **8-4S-0b link-handoff ✅** → `ui/session/link-handoff.ts` (Copy-Item-Verbatim-Port ALT `widget/link-handoff.ts`: `resolveGuideNavUrl` T7-fail-closed-Open-Redirect-Guard [http(s) + isTrustedHost, sonst null; Cross-Origin-Handoff hängt bsid+bgm an] + `maybeRewriteOutgoingLink` bsid-Klick-Rewrite; Imports→portiertes `./trusted-host`/`./session-id`; 11 Charakterisierungs-Specs [Guard-fail-closed-Fälle + Intercept + Middle-Click-href-Rewrite; Plain-Left-Click-`window.location`-Nav jsdom-untestbar→live/8-7]; ui 226 grün, Bundle 179,9 kB). **8-4S-0a host-events ✅** → `ui/host-events/host-events.ts` (Copy-Item-Verbatim-Port: `maybeDispatchGuideNavigate` [Nav-Intent-Regex-Gate + Card-`link`/`guide_url` → `navigate`-page_action] + `maybeDispatchGuideSuggestion`/`maybeDispatchRoutingDebug` [emit-Gate via `_attrIsTrue`, dual-channel `window`-CustomEvent + Output-Kanal, DebugInfo→Payload-Mapping]; Imports→`../cards`/`../grouping`/`../element`; Prereq `_attrIsTrue`→`ui/element/attr.ts` aus 8-5 vorgezogen [Element-Def 8-5 reimportiert]; 13 Charakterisierungs-Specs [window-CustomEvent-Capture + Mock-Context]; ui 239 grün, Bundle 179,9 kB). **8-4S-a ChatMessage-Vollmodell ✅** (message-types.ts: `ChatMessage` auf volles ALT-Modell konsolidiert — id/sender/timestamp required + quickReplies/loadingPhase/inlineDocuments/topicPage; `debug` bleibt bewusst `unknown` [`simplify:` — Grouping castet nur `as any` auf dynamische _web_links/_type_focus/pattern, typisierte Debug-Anzeige läuft übers separate latestDebug-Signal; **KEIN `follow_up`** — der lebt auf ChatResponse, meine Notiz war ungenau, ALT-Quelle maßgeblich]; Blast-Radius = 5 Fixture-Sites [speech ×4 + collection-actions `makeMsg`] compiler-getrieben um required timestamp/sender ergänzt, kein Test geschwächt; ui 239 grün). **8-4S-b State-Core ✅** → `ui/shell/chat-shell.component.{ts,spec.ts}` (ChatShellComponent = Zustands-Container: Signals messages/isLoading/latestDebug + Reducer uid/addUserMessage/addBotMessage[11-Positionen-Seam]/removeMessage/updateLoadingPhase — Bodies+Gates verbatim ALT chat.component.ts:1273-1321; **RE-ARCHITEKTUR** [kein Verbatim — ALT-Monolith]: 2 dokumentierte zoneless-Anpassungen [isLoading/latestDebug Signals statt plain fields; ALT-private Reducer → öffentliche Message-API des Cores]; Platzhalter-Template [echtes Row-Template 8-4S-f]; NICHT in public-api exportiert bis Widget-Konsum 8-5; `scrollTargetId` bewusst auf 8-4S-d/e verschoben [dort set/consume]; test-first RED→GREEN, 8 Charakt.-Specs [Default-State/Feldmapping/pageSize-Default/`pagination||undefined`/inlineDocs-Length-Gate/topicPage-swimlanes-Gate/id-Eindeutigkeit/removeMessage/updateLoadingPhase-`&& isLoading`-Guard]; 105 Z.; ui 247 grün, Bundle 179,9 kB unverändert). **8-4S-c sendMessage-Orchestrator ✅** → `ui/shell/send-message.ts` (`runSendMessage(text, action, actionParams, ctx)` = ALT-`sendMessage`-Turn-LIFECYCLE 448-569 als reine Fn hinter `SendMessageContext`-Seam [deferred Arrows, Muster CollectionActionsContext]: Guard [leer/isLoading] → clearInput → User-Bubble → Loading-Bubble → `stream`(8-3)/Stale/POST-Fallback → Ergebnis-Bubble [11-Arg] → Fehler-Bubble → isLoading/Fokus; **RE-ARCHITEKTUR**: ALTs Erfolgs-Seiteneffekte [Tour/latestDebug/query-meta/page-action/Guides/autoSpeak] zu EINEM `onResult(resp, msg)`-Hook zusammengefasst [Shell verdrahtet 8-4S-d/e/g, ALT-Sequenz + Gates dort]; Transport-URL/Body-Formung bleibt Shell [`stream`/`post`-Arrows rufen streamChat/postChat mit LIVE-sessionId]; Stale-Detektion via `err.name==='StreamStaleError'` [ALT-verbatim, KEIN Fallback bei Stale]; `console.warn` nur im non-stale-Fallback [ALT-treu]; test-first RED→GREEN, 8 Lifecycle-Specs [Guards/Happy-Path-Sequenz/Input-trim-Fallback/Stale-no-Fallback/POST-Fallback/Fehler-Bubble/onEvent→Phase-Label]; 138 Z.; ui 255 grün, Bundle 179,9 kB unverändert). **8-4S-d0 ChatApiClient ✅** → `ui/stream/chat-api.ts` (Port des ALT-`ApiService`-Request-/Transport-Layers api.service.ts:296-470,650-686, den 8-3 der Shell überließ: `ChatApiClient`-Klasse mit baseUrl-Mgmt [setBaseUrl-Normalisierung + Konstruktor-`window.BOERDI_API_URL`-Override] + setGuideEnv [guideMode/guideHost lowercased] + private buildEnvironment/buildBody + `stream`/`post` [wrappen streamChat/postChat 8-3 mit baseUrl+`/chat/stream`‖`/chat`, ChatResponse-Cast, fetchImpl injizierbar]; Helfer `detectDevice` [innerWidth-Schwellen] + `extractPageContext`/`_extractPageContextFromUrl` [reiner URL-Kern herausgezogen, Muster page-context-detector] + `Environment`-Typ verbatim; **2 dok. Re-Architekturen**: buildEnvironment entfernt ALTs wortgleiches sendMessage/sendMessageStream-Duplikat [behavior-preserving DRY], `_extractPageContextFromUrl(url)` testbar ohne window; kein Modul-Global-State [Instanzfelder]. test-first RED→GREEN, 12 Specs [5 URL-Golden + Query-Precedence, Device-Schwellen, post-URL/Body/action-Gates, env-Override-Precedence, setGuideEnv-Lowercase, setBaseUrl-Normalisierung, BOERDI_API_URL-Override, stream-URL/onEvent/resolve]; 185 Z.; ui 267 grün, Bundle 179,9 kB unverändert). **8-4S-d Controller-Wiring ✅ (6 Sub-Slices, 267→300 grün, Bundle 179,9 kB unverändert)** — die Shell ist jetzt der Integrator. **d-α** `ui/stream/phase-label.ts` (Verbatim-Port ALT `formatPhaseLabel` chat-text-utils: SSE-`phase`→dt. Lade-Label; 7 Specs). **d-β** ChatApiClient +`transcribe`/`synthesize`/`getSpeechEnabled` (Verbatim ALT api.service:609-648, FormData/Blob, fetchImpl injizierbar; 6 Specs). **d1** `ui/shell/shell-contexts.ts` (`ShellHost`-Seam [~19 Live-Accessoren] + `buildControllerContexts(host)` → die 5 Controller-Contexts, aus der Komponente herausgezogen damit sie schlank bleibt + ohne TestBed testbar; geteilte `send`/`post`-Helfer binden LIVE-sessionId, Arität spiegelt ALT; 7 Fake-Host-Specs). **d2a Turn-Maschinerie** (Component wächst: Felder sessionId/userInput/parsedPageContext/scrollTargetId/showDebug/`_api` + inputs/outputs + `_host`-Objekt-Literal [deferred Arrows] + `buildControllerContexts` + _tour/_contextGreeting/_speech + `_sendCtx` + public `sendMessage`→runSendMessage + `_onResult` [ALT-Tail 522-560: applyTourState/latestDebug/query-meta-Event/dispatchPageAction/3× host-dispatch/autoSpeak — **subsumiert 8-4S-g**] + dispatchPageAction/focusInput; `runInZone`=`markForCheck` [zoneless-Äquiv. NgZone.run]; 4 TestBed-Specs mit fake `_api`). **d2b Input-Routing** → `ui/shell/input-routing.ts` (reine `routeQuickReply`/`guideQuickReplyTarget`/`resolveGuideNavTarget` hinter `InputRoutingContext`; Component = dünne Delegates onQuickReply/onGuideQuickReply/onGuideNavigate[T-3-fail-closed]/onKeydown/toggleDebug/startTour/_effectiveTrustedDomains; 9 Specs). Zwei Arität-Fallen [d1 send/post, d2b routing] gefangen+gefixt via Aufruf-Arität-erhaltendes Spread. **Component 316 Z. = dok. >300-Ausnahme** [Integrator: State-Core + Wiring-Seams + dünne Delegates, alle Logik in Modulen; §3 split-by-responsibility statt Wiring zerstreuen]; NICHT public-api bis 8-5. `restart` bewusst → 8-4S-e verschoben (session/greeting-gekoppelt). **8-4S-e Lifecycle & Session-Boot ✅ (6 Sub-Slices, 300→331 grün, Bundle 179,9 kB unverändert)** — der Lebenszyklus liegt jetzt in Modulen, die Komponente hält nur Angular-Hooks + Public-API-Delegates. **e-0** ChatApiClient +`loadHistory` (Verbatim ALT api.service:556-602: GET /sessions/:id/messages, hebt `debug._web_links`/`_query_metas` auf Top-Level, `_type_focus`-Override→[]; Fehler/nicht-ok/Nicht-Array→[]; 4 Specs). **e1** `ui/shell/session-boot.ts` (`bootSession(cfg)→{sessionId,resumed,viaBsid}` = ALT-ngOnInit-286-305-Kaskade als pure Fn, reuse session-id.ts; `viaBsid`-Rückgabe ersetzt ALTs `_resumedViaBsid`-Seiteneffekt; 4 jsdom-Specs). **e2** `ui/shell/scroll-follow.ts` (`ScrollFollowController` = scrollToBottom/scrollToLatest/_setupAutoFollowTail[MutationObserver-Tail-Follow]/scrollToMessage/afterViewChecked-Konsum/destroy, Container-Seam=Messages-ViewChild [No-Op bis 8-4S-f]; ALT-Bodies verbatim 1323-1409 + ngOnDestroy-Cleanup 433-440, `_speech.destroy` bleibt Komponente; 5 deterministische Specs mit Fake-El+Fake-MutationObserver). **e3** `ui/shell/history-restore.ts` (`restoreHistory(ctx)` = ALT 347-399: leer→Begrüßung, sonst Begrüßung-prepend+QR-Strip+user/assistant-Render[Cards/WebLinks/QueryMetas/Debug]+Scroll; 3 Specs). **e4** `ui/shell/lifecycle.ts` (`ShellLifecycle` = init[apiUrl/getSpeechEnabled/pageContext-Parse/bootSession/Resume-vs-Begrüßung]/showGreeting/restart/resetSession/updateContext/onSpaContextChange + _afterResume/_maybeStartTourTick/_maybeSendContextPing hinter `LifecycleContext`; nutzt e1/e3 + tour/context-greeting-Controller; ALT-Bodies verbatim 258-315/322-344/402-415/717-766/1262-1270; 11 jsdom-Specs). **e5** Component-Wiring (8 Session-/Lebenszyklus-`@Input()`s [apiUrl/pageContext/persistSession/sessionKey/sessionCookieDomain/sessionCookieMaxAge/greeting/startReplies] + `speechBackendEnabled`-Signal + `_resumedViaBsid` + `_scroll`/`_lifecycleCtx`/`_lifecycle`-Seams + dünne Angular-Hooks [ngOnInit→init, ngAfterViewChecked→scroll, ngOnDestroy→scroll.destroy+speech.destroy] + Public-API-Delegates [restart/resetSession/updateContext/onSpaContextChange/scrollToLatest]; `scrollTargetId`-Feld → ScrollFollowController verlagert; 4 TestBed-Wiring-Specs inkl. realem ngOnInit-Lauf). **ngOnChanges[trustedHosts→markdown-cache] bewusst → 8-4S-f verschoben** (braucht die MarkdownRenderer-Instanz + DomSanitizer/withBsid-Kontext, die erst im Row-Template instanziiert werden — YAGNI: kein Vorziehen des Render-Setups). **Component ~430 Z. = dok. Integrator-Ausnahme** (keine Logik: 4 Seam-Literale + State-Core-Reducer + Hooks/Delegates; liest top-to-bottom; FOLLOW-UP Größe: State-Core→`message-store.ts` als eigener behavior-preserving 8-4S-b-Refactor [~430→~380], NICHT hier gebündelt). **8-4S-f Message-Row-Template ✅ 2026-07-25** in 4 Sub-Slices, jede test-first RED→GREEN: **f0 Split-first** (§3 „split before the feature pushes the file past the threshold") — State-Core → `shell/message-store.ts` (messages-Signal + set/update/uid/addUserMessage/addBotMessage/removeMessage/updateLoadingPhase, Bodies verbatim ALT 1273-1321+1455); = das geplante Follow-up, JETZT gezogen, damit das Template nicht auf 429 Z. draufsattelt; Reducer sind bewusst NICHT mehr Component-API (die 4 Seams rufen `_store.*`), Charakterisierungs-Spec zog mit (ohne TestBed) → Komponente 429→375. **f1 `print/print-gates.ts`** (isLearningPath/isPrintableCanvasMaterial/printableCanvasLabel/printInlineDocument verbatim ALT 859-916 + `SHELL_PRINT`-Fassade, damit das Template `print.*` ruft statt 6 Delegates; eigene Datei weil print-utils.ts mit 363 Z. schon über der Schwelle liegt; Spec-Falle: `vi.spyOn` auf einen ESM-Export greift unter esbuild NICHT → stattdessen `window.open` gestubbt = echter Pfad bis ins HTML). **f2 `shell/shell-render.ts`** (`ShellRender`: MarkdownRenderer-Instanz + clearCache + withBsid/isHostTrusted/externalLinkWarning + groupingCtx/resultGroupsCtx + displayContent, hinter `ShellRenderContext`; Bodies aus ALT 254-256/970-973/1021-1023/1221-1230/1469-1479). **f3 Template+Styles+Wiring**: `chat-shell.component.html` (202 Z., ALT 1-419+609-632 mit @if/@for; komponiert inline-documents/swimlanes/result-groups/quick-replies/debug-panel) · `chat-shell.component.scss` (274) + `_chat-footer.scss` (109, Eingabe-Chrome = eigene Änderungs-Ursache) + `markdown/_markdown-content.scss` (155, `.msg-content`-Typografie neben dem Renderer; Partial-Konvention wie `_result-group.scss`) — SCSS per Range-Extraktion aus ALT statt abgetippt, danach reviewt · Komponente: templateUrl/styleUrl/imports, `showLanguageButtons`-Input, `render`/`print`/`renderBotMarkdown`/`ICONS`/`boerdiLogo`, languageButtonsVisible (Host UND Backend-Capability), Speech-Getter/-Delegates, `ngOnChanges`[trustedHosts→clearCache] verbatim ALT 214-222. Eingabefeld `[value]`+`(input)` statt `[(ngModel)]` (Signal + kein FormsModule im Bundle). 3 Selbst-Review-Fixes: totes `cardsEnabledBool` raus (erst 8-2i hat Konsumenten) · result-groups/quick-replies bekamen `sender==='bot'` bzw. das ALT-Length-Gate, sonst wurde je Nachricht (auch User-Bubbles) eine Komponente instanziiert, die nie etwas rendert · Footer-SCSS ausgelagert (371→274). **Bewusst offen**: das Eingabefeld hat nur `placeholder`, kein `aria-label` (ALT-Stand, WCAG 4.1.2) → gehört in den koordinierten a11y-Sweep **8-6**. Komponente ~460 Z. = weiter dok. Integrator-Ausnahme (reines Wiring, EINE Änderungs-Ursache). Verifikation: `npx ng test ui` **45 Dateien / 373 Tests** grün (356→373), `npm run build:widget` 179,90 kB/54,33 kB gzip unverändert (Shell tree-shaked bis 8-5). **Nächster Build = 8-2i Flat-Cards** (Card-Grid + `.card-actions` + Pagination + Topic-Dropdown; hängt an Shell-State visibleCardCount/openTopicDropdown + collection-actions loadMore/showMoreCards), dann 8-5 Element-Def+public-api, 8-6 a11y-Sweep, 8-7 E2E[live=Nutzer]. |
| 8-5 ✅ 2026-07-25 | Element-Definition + Widget-Hülle | ALT `widget/widget.component.{ts,html,scss}` (693/147/440 Z.) + `widget-init.ts` + `guide-mode-config.ts` portiert und nach Änderungs-Ursache zerlegt (§3), NICHT als ein 700-Zeilen-Monolith. **Neue `ui/widget/`-Module**: `widget-init.ts` (117, verbatim: `computeInitialExpanded` [initial-state / valide ?bsid= / laufende Tour] + `resolveMergedPageContext` [auto-URL+Detector, manueller Override zuletzt, `widget:true`-Marker NACH dem Merge = C10]) · `guide-mode-config.ts` (119, verbatim: `parseGuideModeConfig` [`null` je Feld = Signal nicht anfassen] + `headerNavIconSvg` + `headerNavHrefWithBsid`) · `panel-state.ts` (128, `PanelState`: `expanded`/`everExpanded`-Lazy-Mount-Latch/`hintActive`, `setExpanded` mit doppeltem rAF → Scroll+Fokus bzw. Fokus-Rückgabe an den FAB, Owl-Hint 1×/Session mit sessionId-Polling) · `guide-boot.ts` (95, `GuideBoot`: `GET /api/config/guide-mode` → Signals + Trusted-Domain-Merge/Cache; Fehler = kein Show-Stopper) · `guide-nav.ts` (75, `GuideNav`: `navigate`-Page-Action → Banner → T7-Guard) · `host-bridges.ts` (139, `HostBridges`: window-`page-action`/`query-meta`-Fallbacks, bsid-Klick-Rewrite **am Widget-Host statt am document**, SPA-URL-Watcher 1,5 s; `init()`/`destroy()` symmetrisch). **Widget-App**: `widget.component.ts` (304 = Element-Kontrakt [17 Inputs/4 Outputs] + Verdrahtung, alle Logik in den Modulen) + `.html` (165, `@if`/`@for`, `chatRef?.`→`shell()?.`) + SCSS in 4 Dateien per Range-Extraktion aus ALT (`widget.component.scss` 51 + `_widget-fab.scss` 115 + `_widget-panel.scss` 252 + `_widget-nav-banner.scss` 67) · `element-api.ts` (62) + `widget-main.ts` (33): `customElements.define` mit Doppel-Define-Guard + Prototyp-Patch der §5.5-JS-API (open/close/toggle/isChatbotOpen/resetSession/updateContext) — `createCustomElement` reicht Methoden nicht durch; vor dem Upgrade No-Op statt Exception. **Shell-Prereqs** (8-5c): `showDebugButton`-Input + `debugButtonVisible`, `autoSpeak`+`toggleAutoSpeak`, `setGuideEnv`-Delegate (ALT teilte den `ApiService` per DI, NEU besitzt die Shell ihren Client), `focusInput` public. **ALT-Befund + behoben (Fehlerbehebung, keine Verhaltensänderung für bestehende Embeds)**: ALTs Positionsregeln lauteten `:host([data-position=…])` und matchten **nie**, weil das Host-Element `position` trägt (`data-position` sitzt am inneren `div`) — das in §5.5 dokumentierte `position`-Attribut war für alles außer dem Default wirkungslos. NEU `:host([position=…])`. **Verifiziert statt angenommen**: die Emulated-Stile der Chat-Shell landen im Shadow-Root der Hülle (eigener Test prüft `.chat-wrapper` **und** `.boerdi-panel` im injizierten CSS) — das war das offene Risiko des 8-1-ShadowDom-Entscheids. simplify: Signals statt `NgZone`/`cdr.markForCheck()` (zoneless plant selbst); `initial-state`-Laufzeitwechsel per `effect` mit First-Run-Guard = ALTs `!firstChange`. Eigener Testfehler gefunden und korrigiert (nicht der Port): `GuideBoot.load()` invalidiert den Domain-Cache nur, wenn die Antwort `trusted_domains` **liefert** — ein Offline-Boot lässt ihn stehen; beide Fälle jetzt gepinnt. Verifikation: `npx ng test ui` **52 Dateien / 449 Tests** grün (390→449), `npx ng test widget` **21** grün (2→21), `npm run build:widget` **408,95 kB raw / 109,16 kB gzip** — erstmals mit erreichbarer Shell, innerhalb §5.5 (420/140, ALT war 455 kB *mit* zone.js), Budget-Gate warnt ab 400/Fehler ab 420 → **nur ~11 kB Luft, 8-6/8-7 im Auge behalten**. **REVIEW-NACHBESSERUNG** (frischer Reviewer mit eigenem Kontext: 0 critical / 3 major / 3 minor / 2 nits — alle Verdrahtungs-, keine Architekturfehler; alle behoben): (M1) **Shadow-DOM-Retargeting**: der bsid-Klick-Rewrite hing am Shadow-**Host**, dort ist `event.target` auf `<boerdi-chat>` retargetiert → die Anchor-Suche in `link-handoff.ts` fand nie einen Link, `intercept-edu-sharing-links` + `(linkClicked)` waren tot. Seam heißt jetzt `clickScope` und zeigt auf den **Shadow-Root**; `host-bridges.spec.ts` legt seinen Test-Host per `attachShadow` an (vorher Light-DOM = Lücke unsichtbar). Live verifiziert: vor dem Fix `target=BOERDI-CHAT` / kein bsid, danach echte Navigation auf `…/testziel?bsid=bb-9075d6e1-…`. (M2) **Guide-Env erreichte die Shell nie beim Default-Embed**: `this.shell()?.setGuideEnv(…)` lief, während die Shell noch am Lazy-Gate hing (collapsed) → das Optional-Chaining verschluckte es, der Client sendete dauerhaft `guide_mode: false` und überschrieb damit den Backend-Default `True` (Lotsen-Modus faktisch aus für die häufigste Embed-Variante). `GuideBoot` schreibt jetzt nur eigene Signals (`guideMode`/`guideHost`), die Hülle zieht per `effect` nach dem Mount nach; Test spioniert am **Prototyp**, weil die Instanz erst später existiert. (M3) **Single-Instance-Guard** aus ALT `widget-main.ts:85-113` fehlte ersatzlos (echter WP-Vorfall Welle C Sprint 7: Snippet in Theme-Header UND Content-Block → zwei gestapelte Chatbots; `customElements.get` deckt nur doppelte *Registrierung* ab) → neu `widget/src/single-instance.ts` (62 Z.) + 4 Specs inkl. des per MutationObserver nachgeladenen Duplikats. (m4) Owl-Hint auf den Auto-Open-Pfaden (`?bsid=` / laufende Tour) fehlte (ALT 310) → `PanelState.showOwlHintIfDue()` + Aufruf in `ngAfterViewInit`. (m5) `trustedDomains()` war ein Null-Cache ohne Signal-Abhängigkeit → `[trustedHosts]` wurde nach dem async Boot nicht neu ausgewertet (in ALT der Grund für `cdr.markForCheck()`). Jetzt `computed` über ein `_backendTrustedDomains`-Signal + Attribut. **Erster Versuch (Signal-Cache mit Write beim Lesen) warf `NG0600` — von den eigenen Tests gefangen**, daher `computed`. ALT-Abweichung: ein NACH dem Boot gesetztes `trusted-domains` wirkt nun sofort (ALTs Cache ignorierte es still) — live bestätigt. (m6) `track b.id` → `track $index` (`id` ist optional, zwei Studio-Einträge ohne id kollidierten → NG0955). (n8) totes `data-position` am inneren `div` entfernt. (n7) `widget.component.ts` 328 Z. = **dokumentierte Integrator-Ausnahme** im Docstring (Follow-up: Seam-Literale → `widget-contexts.ts`, Muster `shell/shell-contexts.ts`). Nach den Fixes: **ui 454 / widget 28 grün**, Bundle **412,63 kB / 110,15 kB gzip**. |
| 8-6 ✅ 2026-07-25 | A11y + States-Pass | Audit über den ganzen Widget-Baum, dann Fixes test-first (4× RED zuerst gesehen). **Behoben**: (1) das Chat-Eingabefeld hatte nur `placeholder`, keinen programmatischen Namen → `aria-label="Nachricht an BOERDi"` (WCAG 1.3.1/4.1.2 — es ist das zentrale Bedienelement des Widgets). (2) Der Kopfzeilen-Status („denkt nach …" / „spricht …") liegt außerhalb des `role="log"`-Verlaufs und war für Screenreader stumm → `role="status" aria-live="polite"`. (3) Fokus-Ringe: ALT hatte `:focus-visible` nur am Eulen-Kopf → weiß auf dem dunkelblauen Kopf für `.boerdi-action-btn`/`.boerdi-close` (Akzentfarbe im `is-on`-Zustand, dort liegt der Button auf weißem Pill), zweifarbig (Akzent + weißer Hof) für den FAB, weil die Host-Seite jede Hintergrundfarbe haben kann. (4) Das Themenseiten-Dropdown war nur mit der Maus schließbar (ALTs `document:click`) → `aria-haspopup` + Escape schließt und gibt den Fokus an den Toggle; `stopPropagation` ist load-bearing, sonst reißt Escape das ganze Panel mit (eigener Test dafür). (5) **Zoneless-Zustandsfehler**: `isRecording` wurde nach einem `await` zurückgenommen (verweigerter Mikrofon-Zugriff = häufiger Fall) — außerhalb des Klick-Turns plant im zoneless Betrieb nichts eine Prüfung, der Mikro-Button wäre im Aufnahme-Zustand hängen geblieben und das Eingabefeld gesperrt → `runInZone`. (6) **Kontraste gerechnet statt geschätzt** (WCAG-Luminanzformel über alle real verwendeten Paare): weiß auf Akzent 9,33:1 · Status mit `opacity .85` 7,24:1 · Bot-Text 17,06:1 — **ein echter Fail: `$text-muted: #777` = 4,48:1 (nötig 4,5)** → `#767676` (4,54:1) in 5 Dateien. `#94a3b8` am Inline-Icon bleibt bewusst (dekorativ, Label steht daneben → SC 1.4.11 ausgenommen). (7) **Live-Befund, den kein Unit-Test sehen konnte**: nach `openChatbot()` landete der Fokus NICHT im Eingabefeld, nach `closeChatbot()` nicht auf dem FAB. Ursache gemessen: ALTs doppeltes `requestAnimationFrame` ist im zoneless Betrieb die falsche Uhr — Angulars Prüfung ist nicht garantiert vorher gelaufen, und in einem nicht komponierenden Tab feuert rAF überhaupt nicht (`visibilityState: hidden`, Animation bei `currentTime: 0`); solange das Panel `display: none` trägt, verpufft `focus()`. → neuer Seam `PanelStateContext.afterRender`, von der Hülle mit `afterNextRender` bedient. Rot→grün am echten Verhalten: beide Fokus-Pfade jetzt `true`. **Geprüft und sauber**: kein Icon-Button ohne zugänglichen Namen (Skript über alle Templates) · Trefferflächen 28×26 bis 36×36 px (≥ SC 2.5.8) · `.boerdi-panel--hidden` = `display: none` (kein unsichtbar-fokussierbarer Inhalt) · Fehler-Zustand vorhanden und im `aria-live`-Verlauf („Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.") · Leer-Zustand existiert nicht (der Chat startet stets mit Begrüßung) · `prefers-reduced-motion: reduce` schaltet alle Animationen ab · 320 px ohne Horizontal-Overflow, Media-Query greift (`320×640`, `border-radius: 0`) · keine externen Fonts/CDNs (DSGVO-Guardrail erfüllt). **Live-Verifikation im Browser-Pane** (Dev-Harness :4200, Backend absichtlich aus): Element definiert + aufgewertet, alle 6 §5.5-API-Methoden am Element, FAB 64×64 mit geladenem Logo, Panel öffnet mit Begrüßung + 4 Quick-Replies, Escape schließt, `position="top-left"` wirkt (= der ALT-Bugfix aus 8-5). **Ehrlich offen**: i18n — alle Strings sind hart deutsch (Projekt-Konvention „deutsch=Inhalt", ALT war einsprachig); Screenreader-Durchgang (NVDA/VoiceOver) und 200-%-Zoom am echten Gerät sind NICHT gelaufen → 8-7/live. Verifikation: **ui 454 / widget 28 grün**, Bundle 412,63 kB / 110,15 kB gzip (§5.5 420/140 — **nur ~7 kB Luft zum Fehler-Gate**). |
| 8-7 ✅ 2026-07-25 | E2E + Budget | **Budget-Gate** `frontend/scripts/check-widget-budget.mjs`: prüft §5.5 vollständig — nicht nur die Größe, sondern auch **Single-File** (ein Lazy-Chunk durch ein dynamisches `import()` erzeugt eine zweite `.js` neben `main.js`; die lädt niemand, und jedes Embed bräche still). kB dezimal (1000) = die **strengere** Lesart: Angulars eigenes `budgets` in angular.json liest „420kb" als 420 KiB (430 080 B), wer dieses Gate besteht besteht also auch das Build-Budget. Rot/grün belegt: 500-kB-Zufallsdatei → exit 1, zweite `.js` → exit 1, fehlendes Bundle → exit 1 mit Bau-Hinweis, echtes Bundle → exit 0. **Messfehler aus 8-6 korrigiert**: die dort berichteten „110,15 kB gzip" waren Angulars *Estimated transfer size* = **brotli**; echtes gzip sind **128,09 kB** (gemessen: gzip-6 128,08 / gzip-9 127,91 / brotli 110,15). Der Puffer ist also **raw ~7,2 kB** und **gzip ~11,9 kB** — raw bleibt die bindende Grenze. **E2E** `frontend/e2e/` (Playwright 1.62, Chromium): 27 Specs in `embed/chat/guide.spec.ts` + `fixtures/{harness,backend-payloads}.ts`. **Abweichung vom Plan-Wortlaut („gegen Dev-Compose")**: Host-Seite UND Backend liefert Playwright selbst per `page.route` aus — kein Port, kein Compose, kein Backend. Drei Gründe: das Artefakt unter Test ist das **ausgelieferte Single-File-Bundle**; die Seiten-URL ist frei wählbar, sodass der Seitenkontext-Detektor über eine echte WLO-URL (`/components/render/<uuid>`) gefahren werden kann; und die Suite ist deterministisch (ein Compose-Lauf hängt am LLM → Nutzer-Domäne wie die Golden-Läufe). Abgedeckt: die 5 Plan-Smokes (Begrüßung+Start-QRs aus der Studio-Config · Karten in Ergebnis-Boxen UND flaches Grid · Aktions-Pill → `action`+`action_params` statt Text · Tour-Chip → `tour_action:start` · Kontext-Ping → `page_event:context_open`) plus Element-Vertrag (alle 6 §5.5-Methoden am DOM-Knoten), Lazy-Mount+State-Erhalt, `position=top-left` (8-5-Bugfix), Escape+Fokus-Rückgabe (8-6-Live-Fix), Single-Instance, Backend-Ausfall, Fehler-Zustand, **DSGVO-Guard (kein einziger Request an einen Dritt-Host)** und die `?bsid=`-Übergabe (8-5-Befund M1 — jetzt CI-Regressionsschutz statt Handprobe). **Vier Befunde am echten Bundle**: (1) **`inline-result-grouping` war ein totes Host-Attribut** — die Shell hat den Input seit 8-2i, die Hülle reichte ihn NIE durch; am echten Embed war das flache Karten-Grid also unerreichbar (**dieselbe Klasse wie der `data-position`-Bug aus 8-5**). Gefixt (`widget.component.{ts,html}`) + Unit-Regressionstest, rot/grün belegt (Forwarding entfernt → Test fällt). (2) Playwrights `reducedMotion`-Context-Option landet in `project.use`, erreicht die Seite aber nicht (gemessen: `matchMedia(...).matches === false`); explizites `page.emulateMedia` wirkt. Deshalb emuliert die Harness es sichtbar selbst — der FAB bobbt endlos, ohne reduzierte Bewegung läuft **jeder** FAB-Klick in Playwrights Stabilitäts-Timeout. Kein `force: true`: der Weg über `prefers-reduced-motion` ist ein echter Code-Pfad, beide Zweige sind gepinnt. (3) Tour und Kontext-Ping laufen non-streaming über `POST /api/chat` (verbatim ALT) — die Harness stubbt jetzt beide Transporte. (4) **Kein Port-Bug, sondern eine geprüfte ALT-Grenze**: eine FRISCHE Session pingt nie. ALT ruft `_maybeSendContextPing()` nur aus `_afterResume()` (chat.component.ts:738) und `onSpaContextChange()` (752) — der Erstbesucher bekommt keine proaktive Kontext-Begrüßung. Als IST-Verhalten gepinnt (eigener Test), NICHT geändert. Die zwei echten Auslöser sind stattdessen abgedeckt: fortgeführte Session (localStorage-Seed) und SPA-Navigation über den 1,5-s-URL-Watcher. **Lint** (CI rief `npm run lint` auf, das Skript existierte nicht → der Frontend-Job wäre rot gewesen): `eslint.config.js` mit typescript-eslint recommended + angular-eslint tsRecommended + **templateRecommended/templateAccessibility**; `stylistic` bewusst AUS (würde einen byte-nahen Port nach Geschmack umschreiben), `no-explicit-any` AUS (ALTs `any` an den Backend-Grenzen zu typisieren wäre Re-Architektur). Nur **7 Funde** im ganzen Workspace, alle behoben: 2 ungenutzte `catch (err)`-Bindungen, 1 toter Import, 1 `prefer-const` (→ Box-Objekt, das `let` war ohne Initialisierung deklariert), 1 veraltete `eslint-disable`-Direktive; zwei mit begründetem Disable statt Änderung: das `<\/script>`-Escape (schützt Inline-Embeds der Host-Seite, verbatim ALT) und `interactive-supports-focus` am Dropdown-Wrapper (Delegat, Escape kommt per Bubbling — ein `tabindex` wäre ein nutzloser Tab-Stop). Falle dabei: **ein Backtick in einem Kommentar innerhalb eines Inline-`template:` beendet das TS-Template-Literal** (Parse-Fehler). **Lizenz-Gate** gegen den echten Baum verifiziert (CI-Kommentar aus P0 verlangte das für P8): 14 Prod-Pakete = MIT 10 / Apache-2.0 1 / 0BSD 1 / `(MPL-2.0 OR Apache-2.0)` 1 (dompurify, dual → Apache-2.0-Zweig) / UNLICENSED 1 (= das eigene private Root-Paket). **Deny-Liste → Allow-Liste umgestellt** (`--onlyAllow` + `--excludePrivatePackages`): §0 Regel 1 erlaubt nur MIT/Apache-2.0/BSD/PSF/PostgreSQL, und eine Deny-Liste übersieht jede neue Schreibweise (`LGPL-2.1-only` ≠ `LGPL-2.1`). Gegenprobe: mit einer verengten Allow-Liste schlägt das Gate wirklich fehl (exit 1). **CI-Job neu geordnet**: install → lint → unit → Lizenz → **build:widget** → budget → Chromium → e2e (+ Playwright-Report als Artefakt bei Fehlschlag). Die `Detect frontend workspace`-Weiche aus P0 ist **entfernt** — sie hätte den ganzen Frontend-Job bei einem Fehlgriff still übersprungen. **REVIEW-NACHBESSERUNG** (frischer Reviewer mit eigenem Kontext, 0 critical / 2 major / 6 minor / 7 nits — alle geprüft, alle behoben): (M1) **Die beiden „pingt nicht"-Tests konnten ihre eigene Regression nicht sehen**: der Ping ginge per `setTimeout(…,0)` raus, das synchrone `toHaveLength(0)` direkt nach dem Begrüßungs-Render war ein Münzwurf. Statt Abwarten wird jetzt die REIHENFOLGE bewiesen — ein selbst getippter Turn muss Request #0 sein. (M2) **Der Fehlschlag-Artefakt-Schritt konnte nie etwas hochladen**: er zeigte auf `playwright-report/`, das nur der html-Reporter erzeugt (CI nutzt github+list); die `retain-on-failure`-Traces liegen in `test-results/`. Mit `if-no-files-found: error` gepatcht, damit ein leerer Upload künftig auffällt statt grün durchzulaufen. (m3) **Meine Budget-Gate-Begründung war schlicht falsch**: `@angular/build` definiert `BYTES_IN_KILOBYTE = 1000` (utils/bundle-calculator.js) — Angulars „420kb" sind exakt dieselben 420 000 B, das Gate ist also NICHT strenger, sondern beim raw-Wert ein Duplikat. Kommentar korrigiert; der eigenständige Wert des Skripts sind **gzip + Single-File**, die Angulars budgets gar nicht ausdrücken können. (m4) `maximumWarning` stand auf 400 kB und feuerte damit bei **jedem** Build — eine Dauer-Warnung ist kein Signal. Jetzt 418 kB (feuert, wenn nur noch 2 kB Luft sind); aktuell still. (m5) Single-File-Prüfung zählte nur `.js` — eine ausgelagerte CSS-Datei oder ein kopiertes Asset bricht den Embed genauso; jetzt zählt jede Datei im Ausgabeordner. (m6) Das Lizenz-Gate lief über ein **ungepinntes `npx license-checker`** — ausgerechnet die Gate, an der §0 Regel 1 hängt, holte ihr Werkzeug bei jedem Lauf frisch aus dem Netz. Jetzt als devDependency gepinnt, und zwar der gepflegte Fork **`license-checker-rseidelsohn@5.0.1`** (BSD-3-Clause): identische Flags, verifiziert grün + Gegenprobe rot, und die Dev-Verwundbarkeiten sinken von 17 auf 13 (Prod-Baum ist und bleibt bei 0). (m7) `budget`/`e2e` bauten nicht selbst — genau die „Studio neu, Widget alt"-Falle des ALT-Projekts. Beide Skripte bauen jetzt vorweg; CI ruft das Skript bzw. `npx playwright test` direkt, weil dort schon gebaut wurde. (m8) `allowEmptyCatch` entfernt (nutzlos: `no-empty` erlaubt kommentierte Blöcke ohnehin, und es gibt 0 unkommentierte `catch {}`) — die Option hätte nur künftige stille Fehler-Schlucker durchgelassen. (m10) `resetSession`/`updateContext` waren nur per `typeof` geprüft und wären auch bei kaputter Verdrahtung „function" gewesen (dieselbe Falle wie `data-position`) → echter Verhaltenstest: `updateContext` muss im nächsten `page_context` auftauchen, `resetSession` den Verlauf auf die Begrüßung kürzen UND eine neue Session-ID erzeugen. Nits: Docstring 17→18 Inputs · **§5.5 zählte 18 Attribute auf, listete aber nur 17 — `inline-result-grouping` ergänzt, jetzt stimmt beides** · CI-Kommentar benennt die drei dokumentierten Erweiterungen der Lizenz-Allowlist (ISC/0BSD/dual-MPL) statt sie stillschweigend zu führen · totes Fixture-Link raus · expliziter 15-s-Timeout für den 1,5-s-URL-Watcher (knappste Marge der Suite) · `.js`/`.mjs` werden jetzt mitgelintet — **was sofort einen toten Import im Gate-Skript selbst fand**; die dafür nötige Ausnahme für `eslint.config.js` musste ans ENDE der Flat-Config (das spätere Objekt gewinnt). Verifikation nach den Fixes: `npm run lint` exit 0 · **ui 454 / widget 29** grün · `npm run build:widget` 412,77 kB raw / **128,09 kB gzip**, keine Budget-Warnung mehr · Gate rot/grün erneut belegt (zu groß=1, zwei Dateien=1, fehlt=1, echt=0) · `npm run e2e` **28 grün** · ALT-Baum unberührt (`find -newermt` = 0). **Zwei 8-6-Restposten mit Messung geschlossen**: `:has(.card-actions)`-Rundung (Karte ohne Aktionsleiste 10 px rundum, mit Leiste unten eckig) und **200-%-Zoom** (640×512-Viewport = 200 % auf 1280×1024: kein Horizontal-Overflow in Panel und Body, Eingabe + Senden sichtbar). **Nutzer-Domäne bleibt**: Compose-Live-Lauf, Screenreader-Durchgang (NVDA/VoiceOver), Zoom/Reflow am echten Gerät. |

## P9 — Studio (L; + /better-coding-frontend)

| # | Task | Inhalt |
|---|---|---|
| 9-1 ✅ | studio-bff | **✅ 2026-07-25.** 4 Module: `api/studio_auth.py` (Token+Gate-Primitive), `api/studio_bff.py` (Router `/studio/api/auth/{login,logout,session}`), `api/studio_proxy.py` (`StudioProxyMiddleware`), `api/studio_static.py` (`SpaFiles`-Mount `/studio`). **Token verbatim ALT** `auth-token.ts:17-28` (HMAC-SHA256, **Passwort = Key**, Message = fixe Konstante `boerdi-studio-auth-v1`, hex) → ein von ALT gesetztes Cookie öffnet das neue Studio (P11-Cutover loggt niemanden aus); der Test rechnet den Token UNABHÄNGIG nach = Interop-Pin, nicht Tautologie. **Architektur-Entscheid: In-Process-Rewrite statt HTTP-Proxy** (§5.6 nachgezogen) — `/studio/api/<x>` → `/api/<x>` in `scope`, `X-Studio-Key` aus `deps.expected_studio_key()` injiziert (EINE Quelle, sonst könnte ein `CHANGE_ME`-Platzhalter an einer der zwei Stellen durchrutschen). Multipart/SSE streamen dadurch unverändert; **kein 120-s-Timeout** (ALTs `AbortSignal` bewachte einen Socket zu einem anderen Prozess — in-process würde ein künstliches Limit Backup-ZIP/Eval-Start willkürlich abschneiden); **Location-Rewrite invertiert** `/api/…` → `/studio/api/…` (FastAPIs Trailing-Slash-307 auf `/api/sessions/` würde der Browser sonst AM BFF VORBEI folgen und käme key-los an einer Studio-Route an — von `test_proxy_rewrites_the_redirect_back_into_the_bff` gepinnt). **3 Härtungen gegen ALT:** (1) **fail-closed** — fehlendes STUDIO_PASSWORD → 503 statt „Studio offen" (ALTs `middleware.ts:31` = die Form von Audit-Blocker T1); `BOERDI_ALLOW_OPEN_ADMIN` ist der einzige Ausweg, `CHANGE_ME…` gilt als unkonfiguriert. (2) **Header sind Trust-Boundary** — Client-`Cookie` + Client-`X-Studio-Key` werden verworfen (ALT reichte ALLE Header verbatim durch und überschrieb den Key nur, wenn einer konfiguriert war). (3) **Login rate-limited** 10/min (ALT: keine Bremse, Rateraten = 2 HMACs/Versuch). Weiter: 401 JSON statt HTML-Redirect (ALT ließ jeden XHR an HTML scheitern), `secure`-Cookie per `STUDIO_COOKIE_SECURE` default 1 statt ALTs `NODE_ENV`-Rateversuch, Clear-Cookie behält die Flags. `GET /auth/session` = NEUE Fläche (ALT hatte keine Möglichkeit zu fragen „bin ich angemeldet?") und trägt via `APIKeyCookie`+`Security` einen echten OpenAPI-Marker → Contract-Gate `test_studio_routes_carry_security_marker` blieb unverändert gültig, nur `EXPECTED_ROUTES`+`PUBLIC_ROUTES` (Login-Paar) nachgezogen + `openapi-v1.json` neu (108→111 Routen). SPA-Mount fällt bei unbekanntem Pfad auf `index.html` zurück (Angular-Routing) und ist geskippt, solange kein Build liegt (Dev/CI). **Abweichung vom ALT-Wortlaut:** malformed JSON → 422 (FastAPI-Konvention) statt ALTs 400. Verifikation: **1980 pytest grün + 2 skips** (25 neu, rot→grün belegt), ruff clean, `export_openapi.py --check` grün, Dateien 103/110/122/58 Z. **REVIEW-NACHBESSERUNG (Fresh-Eyes-Reviewer, jeder Fund selbst reproduziert):** 🔴 **1 CRITICAL echt** — `BOERDI_ALLOW_OPEN_ADMIN=1` machte einen KONFIGURIERTEN `STUDIO_API_KEY` wirkungslos: offenes Cookie-Gate + Key-Injektion ⇒ `GET /studio/api/config/backup` **ohne Cookie = 200** (direkt an `/api` = 401). `require_studio_key` behandelt das Flag als inert, sobald ein Key gesetzt ist (deps.py:60-66) — 9-1 hätte also genau die Fail-Open-Form von Audit-Blocker T1 NEU eingebaut. Fix: `_injectable_key()` mintet nichts, solange `gate_is_open()`; das Downstream entscheidet. Selbst reproduziert (401 vs 501) vor dem Fix. 🟠 **MAJOR:** (a) ein **nicht-ASCII-Cookie** war ein unauthentifizierter **500** — `hmac.compare_digest` wirft auf non-ASCII-`str`, Starlette dekodiert Cookies als latin-1 ⇒ ein Byte ≥ 0x80 per curl reichte; `isascii()`-Guard + derselbe Fix im **vorbestehenden** `deps.py:75` (X-Studio-Key, gleiche Bug-Klasse). (b) Der Query-String-Test testete keinen Query-String (Reviewer mutierte `query_string=b""` → 25/25 weiter grün) und (c) der Cookie-Drop war **von 0 Tests** gedeckt → beide jetzt als Middleware-Unit-Test mit Sink-App (`path`/`raw_path`/`query_string`/Header-Liste explizit). (d) `test_proxy_does_not_touch_the_public_api` bestand auch ohne Middleware → jetzt MIT gültigem Cookie + `detail`-Diskriminator. 🟡 **MINOR:** SPA-Fallback schluckte `/studio/api/auth/<typo>` als `200 text/html` (= genau das ALT-Symptom, das der Port beseitigen sollte) — `SpaFiles` re-raist jetzt für `api/`-Pfade; **Windows-Falle dabei gefunden**: `StaticFiles` normalisiert per `os.path.normpath`, also `api\auth\x` — ein `startswith("api/")` hätte auf dem Linux-Ziel gehalten und lokal still versagt. `root_path` wurde ignoriert (hinter Pfad-Präfix-Proxy = stiller Totalausfall der Studio-API, fail-safe aber tot) → `_route_path()` + Test. Middleware-Reihenfolge: CORS lag INNEN, ein Preflight (trägt per Definition kein Cookie) bekam 401 → `StudioProxyMiddleware` jetzt VOR CORS registriert (später hinzugefügt = außen). `.strip()` auf dem Passwort brach die ALT-Cookie-Interop (Passwort ist der HMAC-Key, ALT liest ihn roh) → verbatim, nur die Leer-/Platzhalter-Prüfung trimmt. **NITs:** `message.get("headers")`, latin-1-unkodierbarer Key ⇒ 401 statt 500, explizite `HTTPException` statt `*authorize(None)`, 404-Tests prüfen jetzt `content-type: application/json`. **Reviewer-Mutations-Matrix**: 9 von 11 injizierten Defekten wurden von den 25 Tests gefangen; die 2 Lücken (Cookie-Drop, Query-String) sind geschlossen. Bewusst NICHT geändert: `logout` ist unauthentifiziert (CSRF = Nuisance, identisch ALT). Endstand: **1986 pytest grün + 2 skips** (31 in test_studio_bff.py), ruff clean, OpenAPI unverändert. |
| 9-2 ✅ | Shell+Auth | **✅ 2026-07-25.** Neues Angular-Projekt `frontend/projects/studio` (zoneless, standalone, `baseHref: /studio/`, eigene build/serve/test-Targets; **neue Dep `@angular/router@21.2.18` MIT**, exakt auf die Workspace-Version gepinnt). **Befund, der das Paket umdeutet: ALT hat GAR KEINE Routen** — alle 17 Views hängen an einem `useState<Layer>` in EINER `page.tsx` (kein Router-Import im ganzen `studio/src`), also keine URLs, keine Deep-Links, kein Back-Button. §5.6 „Views NEU = Angular-Routen" ist damit **Neubau, kein Port**; die ALT-`Layer`-IDs sind nur Namens-Präzedenz. Ebenso neu: a11y war in ALT bis auf Landmarks + `aria-hidden` an Deko **komplett abwesend** (0× `aria-current`, 0× `aria-live`, kein Skip-Link, Nav-Items als `<button>` ohne href, Modal ohne Fokus-Falle/Escape, `<h1 onClick>` als Home-Link, `.form-label` ist ein `<div>`) und **responsive gab es nicht** (fixes `280px 1fr`-Grid, 0 `@media` in 1226 CSS-Zeilen). **Gebaut:** `studio-views.ts` = EINE Registry (16 Views: slug/label/desc/group/paket) → daraus werden Routen UND Sidebar abgeleitet; ALT hielt Nav-Liste und Render-`switch` getrennt und sie WAREN divergent (`Layer` deklarierte ein totes `'info'`) — `studio-views.spec.ts` pinnt die Invariante in beide Richtungen. `core/studio-api.service.ts` = die eine HTTP-Grenze auf `/studio/api` (Trailing-Slash bleibt erhalten, `null`-Params fallen raus, Fehler → `StudioApiError` **mit Status-Feld**; ALTs `fetchJson` warf `Error("HTTP 403 …")`, Status nur per String-Match, und wurde von 3 von 17 Komponenten benutzt — der Rest rief `fetch` roh mit genau den Defekten, die sein eigener Docstring anklagt). `auth/`: `SessionStore` (Signals, dependency-frei — bricht den Zyklus Interceptor→AuthService→StudioApi→HttpClient), `AuthService` (4 echte Zustände: unknown/signed-in/signed-out/**disabled**=503, weil ein Login-Formular bei fehlendem STUDIO_PASSWORD eine Sackgasse ist), `authGuard`, `authErrorInterceptor` (401 nach dem Guard → `/login?abgelaufen=1`, Login-Request ausgenommen), **`redirect-target.ts`** = Allow-List für `?from=` (ALT wies den Wert ungeprüft `window.location.href` zu = Off-Site-Redirect per Link; die Tests decken `//host`, **`/\host`** und `javascript:` ab). `shell/`: Skip-Link, `<a routerLink>` + `aria-current="page"`, gruppierte `<ul>`-Nav in `<nav aria-label>`, Marke als echter Link, Logout (V8 — ALT hatte den Endpunkt, aber KEINEN Knopf), Drawer < 60rem mit ehrlichem `aria-expanded`, `status-indicator` (pollt `/health` alle 10 s in `role="status"`; ALT leitete den Punkt aus EINEM `/api/config/elements` beim Mount ab, prüfte nie nachf, hatte keinen „unbekannt"-Zustand und zeigte deshalb beim Laden immer erst rot). `login.component`: echtes `<label for>`, `role="alert"`, Fehler nach Ursache getrennt (401/429/503/0/x — ALT zeigte „Falsches Passwort" auch bei 500), Eingabe bleibt erhalten, reservierte Fehlerhöhe. `theme/_studio-tokens.scss` auf den geteilten M3-Tokens: **jede Farbe mit gerechnetem Kontrast dokumentiert**, `-text`- und `-dot`-Varianten getrennt (ALTs `--success: #10B981` = 2,56:1 wurde als Textfarbe benutzt → hier `#047857` = 5,55:1), rem-Sidebar statt 280px (überlebt 200 % Zoom), Systemfont-Stack (kein CDN, DSGVO). `PlaceholderComponent` nennt View + implementierendes Paket (Muster wie `todo("P9-3")` im Backend) statt einer leeren Seite. **Bewusst offen:** Nav-Icons (15 Inline-SVGs, rein dekorativ, `aria-hidden`) → 9-6; i18n bleibt hart deutsch (Projekt-Konvention wie P8). Lint fand genau 1 Fund (`autofocus`, hatte ALT) — **Regel nicht abgeschaltet, Attribut entfernt**, weil Heading+Hinweis vor dem Feld die bessere Orientierung sind. **Verifikation:** `ng test studio` **49 grün** (6 Dateien), `eslint .` exit 0 (inkl. Template-a11y), `npm run build:studio` 255,97 kB raw / 71,52 kB transfer, Lizenz-Gate 14 Prod-Pakete grün, größte Datei 194 Z.; **echter End-to-End-Beweis**: das GEBAUTE `dist/studio/browser` vom echten Backend-Mount serviert → `/studio/` 200 mit `<base href="/studio/">`, Deep-Link `/studio/dimensionen/intents` → SPA-Shell, `/studio/api/debug/mcp-test` mit Cookie → 501 (Key injiziert), `/studio/api/nix` → 404 JSON. CI-Job erweitert (unit = ui+widget+studio, plus `build:studio` als strictTemplates-Gate über ALLE Templates). |
| 9-3 ✅ | SchemaForm | **✅ 2026-07-25.** **Entscheid (ersetzt „formly-Renderer + Monaco-Custom-Type"):** eigener Renderer, keine neue Dep. Gemessen vor der Entscheidung: (a) die 32 Bereichs-Modelle erzeugen genau **4** JSON-Schema-Merkmale — `$defs`/`$ref` (26 Modelle), `anyOf` (11, = `X \| None`), Arrays, Objekte; **kein** enum/oneOf/allOf/const/discriminator/patternProperties/if-then. Formlys Wert ist der lange Schwanz — den gibt es hier nicht, und das Schema stammt aus unseren eigenen Modellen. (b) Der Workspace hat **kein** Material/Bootstrap-Preset, formly liefert selbst **kein** UI → alle Feld-Widgets wären so oder so handgeschrieben; formly hieße Dep **plus** derselbe Widget-Code. (c) formly kennt `additionalProperties` nicht (0 Treffer im json-schema-Service) — die einzige echte Datenintegritäts-Anforderung (s. `/api/config/data`) läge ohnehin außerhalb. (d) Eine reine `schemaToFields()`-Funktion ist direkt gegen alle 32 echten Schemas testbar, ein FieldConfig-Graph nicht. Monaco vertagt (97,9 MB entpackt, Worker-/Asset-Pipeline) → `<textarea>` wie ALT, Neuentscheid in 9-6. **Der zweite Messbefund kippte das Speicher-Design mitten im Paket:** ein Lauf über die ALT-Konfiguration fand **357 Daten-Pfade**, die ihr Bereichsmodell nicht pinnt — und zwar *verschachtelt* (`01-base/policy` → `rules[*].effect.disclaimer`, `01-base/classify-overrides` → `pattern_disambiguators_legacy[*]`), nicht auf der obersten Ebene. Der zuerst gebaute Top-Level-Merge hätte das nicht gerettet (falsche Ebene), ein tiefer Merge kann Löschen nicht ausdrücken. Also: PUT **ersetzt**, und das Formular editiert eine **Kopie des ganzen Dokuments** statt eines aus dem Schema gebauten Werts. Genau das ist auch der Grund, warum `form-value.ts` unveränderlich mit Strukturteilung arbeitet: nur die Wirbelsäule bis zum geänderten Wert wird neu gebaut. **Slices:** 9-3a Backend `GET/PUT /api/config/data/{area}` (14 Tests; Traversal-Test auf die *kodierte* Form gestellt, weil httpx `..` schon im Client wegnormalisiert — der Test hätte sonst nichts geprüft) · 9-3b `schema-to-fields.ts` (rein; Specs gegen eine generierte Fixture **aller 32 echten Schemas**, `scripts/export_area_schemas.py`; pinnt die **13** Felder, die als JSON-Editor enden, weil ihr Modell `dict[str, Any]`/`Any` deklariert) · 9-3c `form-value.ts` (rein: get/set/remove/renameKeyAt) · 9-3d `SchemaFormComponent`+`SchemaFieldComponent` (rekursiv, `forwardRef` auf sich selbst) + `JsonValueComponent` (eigene Komponente, weil nur sie Entwurfszustand hat: JSON wird auf `change` geparst, nicht je Tastendruck) · 9-3e `AreaEditorComponent` (Formular/Rohtext; Tabwechsel bei ungespeicherten Änderungen wird **abgelehnt** statt still aufgelöst — beide Reiter sind Sichten auf ein Dokument) · 9-3f `AreasComponent` „Alle Bereiche" + `bereich/**`-Route + Doku. **Nebenbefund gefixt:** `detailOf()` im StudioApi ließ FastAPIs 422-Liste durchfallen und zeigte „Unprocessable Content" ohne Feldnamen. **Review (0 CRITICAL / 6 MAJOR / 8 MINOR / 5 NITS) — alle abgearbeitet, jeder Fund vorher an der Quelle nachgestellt:** (M1) `writeInto` schrieb einen benannten Schlüssel auf ein Array als `arr[NaN]` — von `JSON.stringify` verworfen, also verschwand jede Eingabe spurlos UND `formDirty` blieb false, „Speichern" also grau; jetzt ersetzt `shapeFor` einen unpassenden Container, und der Renderer zeigt eine Form-Kollision gar nicht erst als leere Gruppe, sondern als JSON mit Hinweis. (M2) Ein abgelehntes Umbenennen (Name vergeben/leer) ließ das Eingabefeld den getippten Namen behalten, während das Dokument den alten hatte — zwei Zeilen mit gleichem Schlüssel, Speichern meldete Erfolg; jetzt Feld zurückgesetzt + Fehler am richtigen Feld. (M3) Tabwechsel wurde bei ungespeicherten Änderungen verweigert, aber Wegnavigieren verwarf sie still → `unsavedChangesGuard` + `beforeunload`. (M4) Kein Generations-Token: eine spät ankommende Antwort konnte Bereich A unter Bereich B installieren, `savedDoc` als sauber markieren und beim nächsten Speichern B durch A ERSETZEN. (M5) `'body' in data && 'frontmatter' in data` war eine Obermenge des Backend-Prädikats (`set(keys) == {frontmatter, body}`) → ein `.md`-Save auf ein YAML-Dokument hätte den Bereich durch `{frontmatter:{}, body:"<YAML-Dump>"}` ersetzt; gelöst durch ein neues `type`-Feld in `/config/data`, damit es das Prädikat nur EINMAL gibt. (M6) Ein offener JSON-Parse-Fehler blockierte das Speichern nicht — PUT ging mit dem alten Wert raus und meldete „Gespeichert."; jetzt melden Felder ihren Fehler nach oben. Dazu MINOR: `loc.filter(≠'body')` entfernte auch den echten Config-Schlüssel `body` (jedes Layer-Doc, jedes Pattern) · `_resolve_area` akzeptierte `03-patterns`, `03-patterns/` und `03-patterns/a/b` und hätte Müll-Zeilen erzeugt (Schema-Endpunkt bleibt bewusst laxer: ein Modell je Gruppe) · `/bereich` ohne Schlüssel lud ewig · ARIA-Tabs ohne Roving-Tabindex/Pfeiltasten und mit `aria-controls` auf ein nicht existierendes Panel · ID-Sanitizer kollabierte `größe`/`gr_e` auf eine ID (`\w` ist ASCII) und Map-Schlüssel-IDs waren ungeprüft · der Ungepinnt-Hinweis war nur top-level, obwohl die 357 Pfade verschachtelt liegen. **Beim Fixen selbst gefunden:** `PUT /api/config/file` antwortete auf kaputtes YAML mit **500** statt 400 (`yaml.YAMLError` ist kein `ValueError`) — vorbestehend seit P2, sichtbar geworden, weil der Rohtext-Reiter die erste UI ist, die beliebiges YAML einreichen lässt. **Verifikation (nach Review-Nachbesserung):** Backend **2009 pytest + 2 skips**, ruff clean, OpenAPI-Gate grün (2 neue Routen bewusst) · Frontend ui 454 / widget 29 / studio **225** (49 → +176), eslint exit 0 (ein a11y-Fund: `(keydown)` saß auf der Tabliste, die nicht fokussierbar sein darf — Regel nicht abgeschaltet, Handler auf die Tabs verschoben), `build:studio` grün · **Live gegen echtes Postgres + gebautes SPA: 12/12** (Deep-Link `/studio/bereich/01-base/welcome-config` → SPA-Shell, Cookie-Gate, Schema+Daten durch den BFF, Speichern mit **überlebenden ungepinnten Schlüsseln**, YAML-Sicht identisch, 422 mit Feldname, unbekannter Bereich → 404 JSON) |
| 9-4 ✅ | Spezial-Views | **Alle 10 Views fertig** 2026-07-25 — **nicht** als 10 handgeschriebene Views, sondern als 4 Bausteine + eine Datendatei, weil die gemessenen ~6 300 ALT-TSX-Zeilen zu ~85 % „Bereich laden, Felder zeigen, speichern" waren — das kann seit 9-3 der Schema-Renderer. · **9-4a `AreaDocEditor`** (`schema-form/area-doc-editor.ts`, 162 Z.): Lade-/Speicher-/Dirty-Kern EINES Bereichsdokuments inkl. Generations-Wache; der Route-Editor aus 9-3 nutzt ihn jetzt auch (280 → 224 Z., Verhalten unverändert — die 225 Bestands-Specs blieben grün). Beim Extrahieren aufgefallen und behoben: das naive `nextGeneration()` NACH einem `await load()` hätte einen parallel laufenden Ladevorgang für einen ANDEREN Bereich entwertet → `load()` meldet jetzt, ob es installiert hat, und Folge-Requests hängen sich an `currentGeneration`. · **9-4b Kuratierte Views** (`views/curated-views.ts` = Daten, `curated-view.component` + `area-section.component`): je Bereich ein `<details>`-Panel (native Disclosure statt selbstgebautem Akkordeon), das erst beim Öffnen lädt und **nur den eigenen Bereich** speichert — kein „alles speichern", weil der Store pro Bereich schreibt und ein Sammel-Speichern halb scheitern kann. · **9-4c `SafetyLevelComponent`**: Radiogruppe statt ALTs Button-Reihe; ALT schrieb per Regex im YAML-Text und **sofort**, hier ist die Stufe ein Feld im Dokument des Panels. Zeigt zusätzlich an, für welche Stufe **kein Preset** in der Datei steht (dann greift der Escalation-Block) — ALT bot alle fünf als gleichwertig an. ALTs Hex-Skala (#f59e0b ≈ 2,2:1) ist ersetzt; Auswahl trägt der Radio, nicht die Farbe. · **9-4d `GroupSectionComponent`**: Patterns UND Personas — Liste aus `GET /api/config/elements` (`file` = `<key>.md`), Bearbeiten je Dokument über `/api/config/data/03-patterns/x`. **Bewusst NICHT `PUT /api/config/patterns`**: die (byte-treu portierte) ALT-Route baut jede Frontmatter aus einem Typmodell neu und schreibt den ganzen Satz — jeder ungepinnte Schlüssel wäre nach einem Speichern weg. · **Selbst-Review fand 3 echte Fehler** (alle mit Test behoben): „Neu anlegen" wechselte die Auswahl und verwarf dabei offene Änderungen; ein Name mit Doppelpunkt zerbrach das erzeugte YAML (400) und einer mit Zeilenumbruch schmuggelte einen Frontmatter-Schlüssel ein (beides in Python nachgestellt) → Label wird JSON-kodiert; eine Ablehnungs-Meldung blieb nach dem Speichern in der Live-Region stehen. · **9-4e „Wissen" ✅ 2026-07-25** — die einzige der 10 Views ohne Config-Formulare. Dafür wurde `CuratedSection` zur **Union**: ein Abschnitt ist entweder ein Bereich (`area`) oder ein **Panel** (`panel`), und die drei Panels sind genau das, was kein Schema-Formular sein kann. `rag-areas` + `rag-documents` (Bereiche/Dokumente aus der DB, Löschen zweistufig bestätigt, Volltext **inline** statt in ALTs Overlay — kein Fokus-Trap, der schiefgehen kann), `rag-ingest` (Datei/Webseite/Text; der Bereich ist EIN Textfeld mit `<datalist>` statt ALTs Select+„neuer Bereich"-Umschalter, weil ein Bereich durch Hineinschreiben entsteht), `mcp-registry` (Liste/Bearbeiten/Discover). **Gelöscht statt portiert:** ALTs 60-Zeilen-Zeilenscanner für `rag-config.yaml` und sein 35-Zeilen-YAML-Schreiber — `05-knowledge/rag-config` ist ein registrierter Bereich, den der 9-3-Renderer als Map darstellt. Geteilter Zustand über `core/rag-api.service.ts` (ein Signal für die Bereichsliste), damit ein Upload die Zähler daneben **sofort** korrigiert; ALT lud nach dem Upload nie nach. **MCP bewusst NICHT als Bereichs-Abschnitt gelistet** (eine Spec pinnt das): nur `/config/mcp-servers` liefert die Werkzeug-Beschreibungen des laufenden Servers und prüft URLs. **Backend-Fund beim Bauen:** genau diese Prüfung fehlte auf den zwei generischen Schreibwegen — `PUT /config/data/05-knowledge/mcp-servers` und `PUT /config/file` schrieben `http://169.254.169.254/mcp` mit 200 in die Registry (beides zuerst als Test nachgestellt). Gate `_assert_area_document_safe` sitzt jetzt an beiden; die dedizierte Route teilt dieselbe Prüffunktion. **Selbst-Review fand 3 weitere echte Fehler:** die Fehlermeldungen zeigten den Transport-Umschlag („HTTP 400 /rag/ingest/text — …") statt des Backend-Satzes — meine eigenen `toContain`-Assertions hatten das durchgelassen, deshalb erst die Zusicherung verschärft, dann `detail` statt `message` gelesen; „Einlesen" war grau ohne zu sagen, was fehlt; und ein MCP-Server ohne Kennung wird von `save_mcp_servers` **still verworfen** — jetzt blockiert und benannt. A11y: die scrollbare Abschnittsliste ist tastaturerreichbar (`tabindex="0"` + Name), Bestätigungen tragen Rahmen **und** Text, nicht nur Farbe. Ebenfalls offen: ALTs **5 Feld-Tabs** im Pattern-Formular (21 Frontmatter-Felder liegen jetzt in einem Fieldset in Modell-Reihenfolge) — eine Tab-Zuordnung müsste 21 Feldnamen im Frontend nachführen; ohne sie ist kein Feld unerreichbar, nur die Liste länger. · **Größen gemessen 2026-07-25** (ALT-TSX): ElementEditor 1531 · KnowledgeManager 1378 · PatternEditor 1045 · DisplayRulesView 476 · PrivacyView 441 · CanvasFormatsEditor 381 · HeaderNavView 278 · ContextActionsView 256 · WelcomeView 178 · ConfigTextEditor 138 · ListFields 123 · SecurityLevelPicker 101 ⇒ ~6 300 Z.; NEU dafür ~1 900 Z. Produktivcode + ~985 Z. Specs (a–d ~1 100/~460, e ~800/~525). **Bindende Regel aus 9-3 eingehalten:** jede View editiert eine Kopie des GANZEN Bereichsdokuments und schickt es ganz zurück. **studio 307 grün (225 → +82) · ui 454 · widget 29 · eslint 0 · build:studio 267,56 kB / 75,86 kB · größte neue Datei 176 Z.**  **A7 ✅ 2026-07-26 — die fünf Feld-Reiter im Pattern-Formular.** Ein Pattern-Dokument hat 21 Kopf-Felder plus Anweisungstext; in einem Fieldset ist das eine Wand. ALTs Schnitt (`PatternEditor.tsx:388-406`) ist übernommen — Reihenfolge und Beschriftungen wörtlich (Identität · Antwort-Form · Tools & Wissen · Slots & Degradation · Anweisungen). **Nicht wörtlich portiert, weil gemessen:** ALT rendert `short_purpose`, `output_mode` und `card_text_link_required` in KEINEM Reiter — dort waren sie nicht editierbar; NEUs generisches Formular zeigt sie, ein wörtlicher Port hätte drei Felder versteckt. Sie stehen jetzt bei ihrer Bedeutung, `id` (in ALT nur Überschrift) in „Identität“. Fünf ALT-Felder (`card_text_mode`, `default_detail`, `format_primary`, `format_follow_up`, `quick_replies_max`) fehlen, weil es sie im NEU-Modell nicht gibt. **Beobachtet, nicht gefolgt:** der Judge bündelt `response_type` mit `default_length`/`output_mode` unter „Antwort-Form“ (`services/eval/judge.py:68-79`), ALT hat es in „Identität“ — A7 ist die Wiederherstellung von ALTs Gliederung, nicht ihre Revision. · **Gebaut als Ausschnitt, nicht als zweites Formular:** `schema-form/pick-fields.ts` (42 Z.) schneidet den Feld-Baum auf eine Pfadmenge, `SchemaFormComponent` bekommt dafür einen `visiblePaths`-Input. **`unmapped` rechnet weiter über den VOLLEN Baum** — sonst meldete jeder geschlossene Reiter seine eigenen Felder als „kennt das Bereichsmodell nicht“. Der Schnitt selbst liegt als Datentabelle in `views/pattern-field-tabs.ts`, das Merkmal `feature: 'pattern-tabs'` in `curated-views.ts` (zweiter Wert neben `safety-level`, wie dort vorgesehen). Reiterleiste = `TabBarComponent` aus 9-5c (Pfeiltasten, `aria-controls`), der Feldbereich trägt `role="tabpanel"` mit der zugesagten Id. · **Zwei Ehrlichkeits-Regeln, rot-grün belegt:** ein Feld, das die Tabelle nicht kennt, landet im Korb „Weitere“ (kann nicht verschwinden — dieselbe Regel wie bei den Material-Typen), und ein Reiter ohne Felder fällt weg (behauptet sonst Inhalt). Die Vollständigkeit ist gegen das ECHTE Schema geprüft: alle 22 Pfade genau einmal. · **Selbst gestellte Falle, vom Rot-Grün-Nachweis gefangen:** die Zusicherung „nennt den Reiter im Sperrhinweis“ prüfte `el.textContent` — und „Tools & Wissen“ steht ohnehin in der Reiterleiste, also war sie immer erfüllt; jetzt prüft sie die Meldung selbst. (Die Meldung nennt den Reiter, weil ein gesperrtes Speichern sonst in fünf Reitern gesucht werden müsste.) · **Rot-Grün:** Auffang-Korb weg · Formular ignoriert den Ausschnitt · Reiter-Name weg ⇒ je **genau 1** rot, jede Umkehrung ihr eigener Test. · **Belege:** studio **719** grün (700 → +19) · `npx eslint .` exit 0 · `ng build studio` Initial 295,15 kB, Chunk `curated-view-component` 65,49 → **67,68 kB** (+2,19) · größte neue Datei 89 Z. |
| 9-5 ✅ | Dashboards | Sessions, Analyse(4 Tabs+Scope), Evaluation(TurnTrace, Golden-A/B), Lasttest, Safety-Logs. **Größe gemessen**: EvaluationView 1490 · QualityView 1280 · InfoView 825 · GoldFlowView 668 · HomeOverview 477 · LoadTestView 417 · SessionsView 300 ⇒ **~5 450 Z.** (überwiegend lesend, daher weniger heikel als 9-4). · **9-5a ✅ 2026-07-25 — Lese-Primitiv + Sessions.** Zuerst gemessen statt vermutet: 4 Komponenten hatten das Lade-/Fehler-Muster am Ende von 9-4 bereits handkopiert, 5 Templates den „Erneut versuchen"-Block — und die Kopien waren uneins. Zwei verwarfen den letzten guten Wert bei einem fehlgeschlagenen Refresh (eine leere Tabelle liest sich als „es gibt nichts", nicht als „die Anfrage ist gescheitert"), und nur zwei hatten die Generations-Wache. Beides steckt jetzt EINMAL in `core/async-data.ts` (63 Z.) + `views/async-state.component` (Reihenfolge Laden > Fehler > Leer an einer Stelle: ein Retry, der die alte Meldung stehen lässt, liest sich als „schon wieder gescheitert"). **Rot-Grün belegt**: Wache entfernt → genau die 2 Renn-Tests rot (`expected ['alt'] to deeply equal ['neu']`), Wache zurück → 337 grün. **Sessions-View**: Liste + Verlauf, beide Löschaktionen zweistufig bestätigt und in der Rückfrage benannt (»Verlauf leeren« behält Session+Auswertung, »Löschen« nimmt alles — verwechselbar genug, dass die Bestätigung sagt, welche gerade scharf ist). **ALT-Defekt nicht mitportiert**: dort war die ganze Karte ein `<div onClick>` mit zwei verschachtelten Buttons und `stopPropagation` — per Tastatur gar nicht erreichbar; hier ist der Zeilentitel ein `<button>` und die Aktionen sind Geschwister. **Selbst-Review fand 3 eigene Fehler**: „Verlauf leeren" schloss das Panel der Session, die man gerade liest (Test zuerst rot, jetzt bleibt die Auswahl und der Verlauf lädt neu); ein `effect`, das nur ein Signal in ein anderes kopierte (→ `computed`); und ein nie aufgerufenes `clear()` (gelöscht). **studio 337 grün (324 → +13 · gesamt +30 seit 9-4) · eslint 0 · build 267,88 kB / 76,60 kB · größte neue Datei 164 Z.** · **9-5b ✅ 2026-07-25 — Safety-Logs.** Zweiter Nutzer der 9-5a-Bausteine und der erste Fall, in dem die Trennung der Lesevorgänge wirklich etwas rettet: ALT holte Liste und Kennzahlen mit EINEM `Promise.all`, prüfte `res.ok` und schob alles andere nach `console.error` — ein kaputtes `/stats` ließ veraltete Zahlen stehen, ein kaputtes `/logs` las sich als „Keine Safety-Events gefunden". Hier sind es zwei unabhängige `AsyncData` mit je eigenem Lade-/Fehler-/Leer-Zustand. **Ehrlichkeit statt Rätsel**: `/stats` aggregiert serverseitig immer das ganze Fenster und ignoriert den Risiko-Filter — das steht jetzt IN der Oberfläche, statt dass eine Redakteurin es durch Misstrauen gegenüber den Summen herausfinden muss; folgerichtig lädt ein Filterwechsel nur die Liste neu (eine Runde weniger). Der Leerzustand unterscheidet „gefiltert leer" von „wirklich leer", und das Detail-Panel ist aus den Zeilen **abgeleitet**, nicht gemerkt: fällt das gewählte Event aus dem Filter, verschwindet auch sein Datensatz. **ALT-Defekte nicht mitportiert**: `<div onClick>` je Karte (per Tastatur unerreichbar → `<button>`), die drei Risikofarben als TEXT (`#9ca3af`/`#f59e0b`/`#ef4444` ≈ 2,5:1 / 2,2:1 / 3,8:1, alle unter AA → geprüfte Token-Paare, deutsches Wort + farbige Rahmenkante als zweites Signal), Filter-`<select>` ohne Label, englische Stufen in deutscher Oberfläche. **DSGVO**: die Zeile trägt eine IP, die Oberfläche zeigt sie nirgends — ein Test nagelt das fest, damit die Auslassung eine Entscheidung bleibt und kein Zufall wird. **Nebenbefund im eigenen Token-Layer, behoben**: `--st-surface-variant` wurde von **9** Stylesheets gelesen und war **nie definiert** — jede dieser Flächen berechnete sich zu transparent; eine Zeile im Token-File repariert alle neun (Kontrast bleibt ≥ 6,6:1 in beiden Schemata, weil das M3-Token selbst umschaltet). **Rot-Grün belegt**: vier gezielte Regressionen (Stats-Refetch beim Filtern · Stats-Zustand aus dem Template · gemerktes statt abgeleitetes Detail · IP im Detail) → **genau die 4 zugehörigen Tests rot, kein Kollateral**; zurückgespielt → 350 grün. **studio 350 grün (337 → +13) · eslint 0 · build 268,01 kB / 76,63 kB · größte neue Datei 244 Z. (Spec), größte Produktivdatei 126 Z.** · **9-5e ✅ 2026-07-25 — Lasttest.** Die einzige Studio-Fläche, deren Knopf Geld kostet: jede Anfrage läuft durch die echte Chat-Pipeline mit echtem LLM und echtem MCP. **Kern-Befund: `validate_profile` klemmt STILL** (`services/loadtest.py`) — Parallelität über 32 wird gedeckelt, alles ab der siebten Stufe fällt weg, Requests/Stufe bei 60; rundheraus abgelehnt werden nur drei Dinge (keine Stufe, >200 Requests gesamt, leerer Mix). ALT zeigte die **getippten** Zahlen und multiplizierte sie: „1, 2, 4, 8, 16, 32, 64" versprach 7 Stufen und 448 Anfragen, gelaufen wären 6 und 200. Der Rot-Lauf hat genau das wörtlich reproduziert (**„56 echte Chat-Anfragen … 1 → 2 → 4 → 8 → 16 → 32 → 32"** — sieben Stufen angekündigt, sechs gefeuert). Deshalb rechnet `views/loadtest-profile.ts` (rein) das **effektive** Profil und benennt, was das Backend ändert; die vier Grenzen sind bewusst gespiegelt und mit ihrer Quelle kommentiert, weil kein Endpunkt sie veröffentlicht. **ALT-Defekte nicht mitportiert:** (a) der Start war nur gesperrt, wenn der GEÖFFNETE Lauf lief — das Backend erlaubt global einen und antwortet 409, der übliche Weg das zu erfahren war also die Fehlermeldung; hier kommt `busyRun` aus der LISTE. (b) `confirm()` → Inline-Rückfrage. (c) `setInterval` → `setTimeout`-Kette (eine langsame Antwort kann keine zweite Anfrage stapeln) mit `DestroyRef`-Aufräumen. (d) `catch { /* weiter pollen */ }` ließ ein gestorbenes Backend dauerhaft „läuft" sagen — jetzt wird der Fehlschlag sichtbar UND der letzte gute Stand bleibt stehen. (e) Löschen eines laufenden Laufs war anklickbar (Endpunkt: 409) → deaktiviert. **Bewusste Vereinfachung, deklariert:** ALTs zwei Ressourcen-Sparklines (CPU/RSS über die Zeit) sind NICHT portiert — die Spitzenwerte stehen im Fazit, der Verlauf fehlt. **Rot-Grün belegt:** vier gezielte Regressionen (effektives Profil → getippte Zahlen · `busyRun` aus dem offenen statt aus allen Läufen · Poll-Fehler geschluckt · Poll-Kette ohne Abbruch) → **genau die 5 zugehörigen Tests rot, kein Kollateral**; zurückgespielt → 387 grün. **studio 387 grün (350 → +37) · eslint 0 · build 268,21 kB / 76,75 kB, Lasttest-View als eigener 26,40-kB-Lazy-Chunk (7,50 kB gzip) · größte neue Datei 255 Z. (SCSS), größte Produktivdatei 175 Z. · ALT-Bäume 0 Dateien, `badboerdi.db` unverändert (11.07. 00:35:50).** · **9-5c ✅ 2026-07-26 — Analyse (4 Tabs + Scope).** Größtes Lese-Paket (QualityView 1280 Z.) und das erste, in dem eine **gemessene Endpunkt-Leiche** das Design bestimmt: `/quality/tight-races` kann für KEINE Datenlage etwas liefern. Beweis am NEU-Code: `phase2_scores` trägt seit Welle E v4 genau einen Eintrag (`{winner: 1.0}`), also erreicht `obs/quality_events.py:109` seinen `len(sorted_scores) >= 2`-Zweig nie ⇒ `phase2_runner_up` ist auf **jeder** Zeile `''` und `phase2_score_gap` `0.0`; der Endpunkt filtert auf `runner_up != ''`. Ebenso konstant: `phase2_winner_score` = 1.0. Folge: der Endpunkt wird **nicht angebunden** (eine Spec hält fest, dass `QualityApi` keine Methode dafür hat), und die **drei** ALT-Anzeigen, die aus diesen Feldern lesen, fallen weg — die Live-Kachel „Ø Score-Gap“ (zeigte permanent 0,000, ALT hatte die Tight-Races-Kachel schon auf „—“ gesetzt, diese aber stehen gelassen), die Spalte „Gap“ samt „Tight Race“-Markierung in den Log-Zeilen und die zwei Felder im Detail-Block. Statt sie kommentarlos zu schlucken, sagt ein Satz unter den Kennzahlen, **warum** sie fehlen. · **Struktur:** eine Hülle (`quality.component`, 86 Z.) besitzt genau zwei Dinge — Scope und Log-Filter —, weil beide geteilt sind; die vier Panels sind eigene Komponenten mit **je eigenem `AsyncData` pro Endpunkt**. ALTs `load()` war ein `useCallback` über die drei Filtertexte, aus einem `useEffect` gerufen: **fünf Requests pro Tastendruck**, von denen vier nur `scope` akzeptieren. Hier hat das Log-Panel ein echtes `<form>` (Enter-to-Submit von der Plattform, kein Debounce-Timer) und ist **controlled** — die Hülle hält die Filter, damit ein Drill-down aus Matrix/Diagnose und die Formularfelder nicht auseinanderlaufen können. Ein Panel-Element liegt immer im DOM (`aria-controls` eines Tabs muss auflösen), sein **Inhalt** entsteht beim ersten Besuch und bleibt dann — ALT war auch lazy, lud aber bei **jedem** Tab-Wechsel neu, weil sein Effekt am aktiven Tab hing. · **ALT-Defekte nicht mitportiert:** (a) Matrix-Zellen waren `<td onClick>` — die dichteste Information im Studio war ohne Maus **gar nicht** erreichbar (jetzt `<button>`); (b) die **Alternativen** je Zelle standen nur im `title=`-Tooltip, für Tastatur und Touch also nirgends (jetzt Text in der Zelle, `title` bewusst leer); (c) die Zellfärbung war ein **Hash auf die Pattern-ID** (`hsl(hash % 360, 55%, 78%)`) mit `opacity: 0.55 + 0.45*share` — ein Hash-Farbton kann 3:1 nicht halten und die Opazitätsrampe drückte den Text unter 4,5:1; beide kodierten nur Pattern-ID und Anteil, die als Text in der Zelle stehen (ersetzt durch einen `aria-hidden`-Balken); (d) Log-Zeilen und Diagnose-Blöcke als `<div onClick>`; (e) `confirm()` → Inline-Rückfrage wie in der Sessions-View; (f) die Flow-Balken hatten eine 200px-Labelspalte mit `text-overflow: ellipsis` — sie schnitt genau die IDs ab, deren Anzeige der Zweck der Tabelle ist. · **Zwei weitere Messbefunde:** ALTs `properTrans.slice(0, 20)` ist **unerreichbar** — `04-states/states.yaml` definiert genau **drei** Phasen (S1 Orientierung, S2 Klärung, S3 Aktion), also gibt es höchstens neun geordnete Paare; die Deckelung ist nicht portiert (kein stiller Cut). Und ALTs Flow-Legende erklärt noch Unterphasen („S3 Suche“ → „S3 Ergebnis-Kuratierung“), die in S3 Aktion aufgegangen sind — der Text nennt jetzt die drei, die es gibt. · **Wiederverwendung statt Kopie:** das Flow-Panel füttert `QualityBarsComponent` **dreimal** (Phasen, Übergänge, Wiederholungen) — ein Übergang ist ein Schlüssel mit einer Zahl, genau wie eine Verteilung; ALT schrieb dafür zwei eigene Balken-Implementierungen. Neu `core/format.ts`, weil **gemessen** derselbe `maximumFractionDigits: 2`-Formatter in 2 Dateien und derselbe `toLocaleString('de-DE')`-Helfer mitsamt NaN-Wache in **4** lag — 9-5c hätte 3 und 5 daraus gemacht; die zwei 9-5c-Konsumenten sind migriert (die vier Bestands-Dashboards **bewusst nicht**, das ist ein eigener Aufräum-Schritt). · **Eigene Fehler, beide vor dem Grün gefunden:** ich habe die 9-5b-Falle selbst neu gestellt — `--st-mono` und `--st-radius-sm` in einer neuen SCSS benutzt, **beide nie definiert**; der Abgleich „definiert vs. benutzt“ zeigte sie als einzige Waisen und zwar nur in meiner Datei (ersetzt durch den im Repo dreifach benutzten Monospace-Stack und `--st-radius`). Und ein Output hieß `close` — wie `select` in der Tabliste ein **nativer DOM-Event-Name**, den ein Elternteil versehentlich mitfängt; Lint hat beides gemeldet, die Regel bleibt an, jetzt `dismiss` bzw. `tabChange`. · **Eigener Test korrigiert, nicht der Code:** die Zusicherung „Min-Count 0 → Anfrage mit `min_count=1`“ war falsch — die Klemmung auf 1 lässt das Signal unverändert, also **fällt die Anfrage ganz aus**, was das bessere Verhalten ist; jetzt pinnen zwei Tests beides (Klemmung über einen echten Wechsel, und `http.verify()` für „kein Refetch ohne Änderung“). · **Verifikation:** **studio 493 grün (387 → +106, 9 neue Test-Dateien)** · `eslint .` exit 0 · Token-Abgleich „benutzt aber nie definiert“ = leer · `ng build studio` grün, Analyse-View als eigener **59,36-kB-Lazy-Chunk (12,72 kB gzip)**, Initial 268,64 kB / 76,82 kB · größte neue Datei 248 Z. (SCSS), größte TS-Produktivdatei 183 Z., **alle ≤ 300** · Route `analyse` in `DASHBOARDS` verdrahtet — **die View hängt jetzt an einer URL** (vorher Platzhalter). · **Selbst-Review fand zwei eigene Auslassungen:** (1) keinem der vier Panels lag ein „Aktualisieren“ bei, obwohl ALT eines hatte und alle drei Schwester-Dashboards eines haben — eine Analyse auf Live-Daten braucht das (4 Tests zuerst rot, dann je Panel ein Knopf; die Übersicht reicht ihn per `viewChild` an die Diagnose-Blöcke weiter, wie die Sessions-View das mit ihrem Transkript tut). Dabei fiel auf, dass der Alias in `@if (value(); as stats)` das Feld `stats` verdeckt — die Leiste liegt deshalb außerhalb. (2) Die Übersichts-Spec flüschte die drei Diagnose-Reads ihres Kindes nie, also hätte sie zwei offene Anfragen je Endpunkt nicht bemerkt; ihr `mount` räumt jetzt tolerant auf (`match`, weil bei leerer/fehlerhafter Antwort kein Kind entsteht) und der neue Test schließt mit `http.verify()`. Die Log-Spec überschritt danach 300 Z. → nach Verantwortung geteilt (`quality-logs.harness.ts` 99 Z. + lesen 130 + löschen 96), nicht an der Zeilenzahl abgeschnitten. · **9-5d 🔄 2026-07-26 — Evaluation (Läufe + Trends), mit vorgezogenem Backend-Port.** Vor dem Bauen gemessen, was die 12 Endpunkte wirklich leisten — und dabei den Grund gefunden, warum diese View anders lag als die vier Schwestern: **der generative Eval-Motor war in NEU nicht portiert.** `_execute_generative_run` markierte JEDEN generativen Lauf als `failed`, und `GET /eval/trends` liest ausschließlich `summary.classification_metrics`, das nur dieser Motor schreibt ⇒ **alle fünf Klassifikations-Serien waren dauerhaft leer**, nicht bloß ungenutzt. Anders als `/quality/tight-races` (9-5c) war das aber **schlafend, nicht tot**: der Vertrag war vollständig, es fehlte die Ausführung. Nutzer-Entscheid: Motor bauen statt View kastrieren. · **E1–E6 Backend-Port** (`services/eval/`, ALT-Modulschnitt gespiegelt, ~1 400 Z.): `text_utils` (nur `_strip_id` + `_has_persona_marker` — `_detect_register`/`_repo_host` sind Gold-only und liegen schon im framework-freien `evals/run_golden.py`, also NICHT dupliziert) · `prompts` **byte-exakt** (ALTs Test pinnt 3 994 / 1 566 / 12 164 Zeichen + die Platzhalter-Mengen — ein echtes Fidelity-Gate, mit einem Skript kopiert statt abgetippt) · `metrics` (die drei Aggregatoren verbatim; `estimate_cost` und `aggregate_golden` waren schon portiert und wurden **nicht** ein zweites Mal geschrieben) · `scenario_gen` · `judge` · `runner`. **Zwei bewusste Abweichungen:** die LLM-Grenze ist `llm.chat_completion(..., background=True)` statt ALTs `get_background_client()`-Objektkette (gleiche Wirkung: der Eval läuft auf der Hintergrund-Bulkhead und kann Live-Verkehr keine Slots wegnehmen), und die Modellnamen lösen **pro Aufruf** aus den Settings auf statt zur Import-Zeit aus `os.getenv` — ALTs eigene Test-Datei listet ihre `DEFAULT_*_MODEL`-Konstanten ausdrücklich als nicht pinnbar; ALTs `or "gpt-4o-mini"`-Wache bleibt, weil docker-compose `${VAR:-}` durchreicht (im Container GESETZT aber LEER → `model=""` → HTTP 400 und die Generierung stirbt), und **zwei neue Tests belegen genau das**. · **Struktur-Entscheid:** `runner.py` ist reine Orchestrierung und berührt keine DB — die Persistenz bleibt in `eval_service` (Spec-Regel 4). Der Runner schreibt in eine **vom Aufrufer besessene** `conversations`-Liste; genau deshalb überlebt ein Lauf, der nach 100 von 144 Kombis stirbt, als Teilergebnis mit Fehlermeldung (ALT erreicht das über eine lokale Variable in seinem eigenen except-Block). Der Fortschritts-Schreiber ist ein **Closure**, wo ALT einen modul-globalen, nie aufgeräumten Zähler-Dict je Run-ID hielt (Invariante „kein Modul-Global-State“); die Drossel „Zusammenfassung immer, Transkript jeden 5.“ ist ALTs Verhältnis. · **Zwei ALT-Tests ersetzt statt umgebogen:** `test_execute_generative_run_marks_failed` und `..._without_factory_is_noop` pinnten das „nicht portiert“-Verhalten, das dieses Paket entfernt — sie sind jetzt vier Tests über den echten Pfad (Persistenz des Ergebnisses, Teilergebnis bei Absturz, Transkript-Drossel 4×nichts/1×Transkript, ein fehlgeschlagener Fortschritts-Schreibvorgang darf den Lauf nicht töten). · **E7 Frontend:** `trend-chart.ts` (rein, Geschwister von `loadtest-chart.ts`) mit zwei bewussten Achsen-Regeln — Raten auf **fester** 0..1-Achse, weil die vier Charts nebeneinander stehen, um verglichen zu werden (Auto-Skalierung malt 2 % wie 90 %), Scores auf das vorhandene Maximum. Ein Lauf ohne `avg_score` wurde nie bewertet und wird **übersprungen, nicht auf 0 gezeichnet** — 0 liest sich als „katastrophal bewertet“. Die Ein-Punkt-Mitte statt `length - 1` als Divisor ist die Lehre aus dem Lasttest-Chart (NaN ⇒ SVG zeichnet gar nichts). A11y wie beim Lasttest: `role="img"` + gesprochene Zusammenfassung (aktueller Wert **und** Richtung), die echte `<table>` ist die zugängliche Quelle für **jede** Zahl. Tool-Compliance je Pattern liegt hinter `<details>` — ohne erfundene Kennzahl, denn ein Mittelwert über Patterns wäre eine Behauptung, die die Daten nicht hergeben. Solange nur Gold-Läufe existieren, **sagt** die Oberfläche, warum die fünf Serien leer sind, statt kaputt zu wirken. · **Eigener Defekt, vom Test gefunden:** `AsyncData` lädt nicht von selbst — die Komponente hätte **nie** Daten geholt (alle 11 Specs rot am `expectOne`). Und eine Zusicherung erwartete die falsche Beugung („generativen“ statt „generativer Lauf“) — Test korrigiert, nicht Text. · **Hülle + Route:** `evaluation.component` (47 Z., `TabBarComponent`) macht Läufe UND Trends erreichbar; ein Test lädt die Route aus `app.routes` und prüft, dass sie **diese** Komponente liefert — die 9-5c-Lehre, dass eine fertige, unverlinkte View nicht gebaut ist. · **Verifikation:** Backend **2082 pytest grün + 2 skips** (110 davon eval), `ruff check .` „All checks passed“, `export_openapi.py --check` „openapi contract unchanged“ (kein HTTP-Vertrag berührt — er war schon ALT-treu) · **studio 547 grün (520 → +27)** · `eslint .` exit 0 · Token-Abgleich leer · alle neuen Dateien ≤ 300 Z. · Offen: **9-5d Lauf-Detail, Gold-Start, Generativ-Start (mit Kosten-Band), Pattern-Nutzung** · 9-5f Übersicht — alle in der Rubrik **Offene Aufgaben** am Dokumentende · **A3 ✅ 2026-07-26 — Generativ-Start mit Kosten-Band.** Der Knopf löst echte LLM- und MCP-Aufrufe aus, deshalb **zwei Schritte**: „Kosten prüfen" holt `POST /eval/estimate` und öffnet damit die Inline-Rückfrage, erst der zweite Knopf startet. Damit ist das Band nicht überspringbar UND kostet genau eine Anfrage — eine live mitrechnende Schätzung wäre die 9-5c-Falle „ein Request je Tastendruck" gewesen. Eine verbrauchte Bestätigung wird verworfen (Start oder jede Formularänderung), damit nie ein Preis neben anderen Zahlen stehenbleibt. **Kein stilles Klemmen:** 1…10 wird lokal geklemmt, weil `StartRequest` mit 422 antwortet und kein Feld nennt; „nichts ausgewählt = alle" steht in der Oberfläche, statt geraten werden zu müssen, und die Kombinationszahl rechnet genau die Serverregel nach. **`busy` kommt aus der Liste**, nicht aus einem zweiten Leser von `/eval/runs` — die 9-5e-Lehre, dass das Backend global einen Lauf erlaubt (409). Die Hülle verdrahtet beides über `viewChild`. Eine **gescheiterte Schätzung blockiert den Start nicht** (der Mensch autorisiert die Ausgabe, nicht der Endpunkt), aber die Rückfrage sagt dann „ohne Kostenschätzung". `warnings` werden gezeigt: das Backend **filtert** unbekannte IDs statt abzulehnen, ein Lauf kann also weniger abdecken als bestellt. Neu `formatUsd` in `core/format.ts` (de-DE stellt das Symbol hinter die Zahl — „$0.14" wäre in beide Richtungen falsch). **Rot-Grün belegt:** `check()` zusätzlich startend gemacht → **genau 5** Tests rot, kein Kollateral. **Eigener a11y-Fund im Selbst-Review:** die Rückfrage lag komplett in einer `aria-live`-Region, also hätte jedes Umschalten des Knopf-Labels („Startet …") den ganzen Kostenabsatz neu vorgelesen — jetzt ist nur die Prosa live. **Zwei falsche Kommentare gefunden und korrigiert**, beide aus der Zeit vor dem E-Paket: `start_generative_run`s Docstring und der Kopf von `eval-runs.component.ts` behaupteten noch, der generative Motor sei nicht portiert. **studio 561 grün (547 → +14) · eslint 0 · Token-Abgleich leer · Evaluation-Chunk 40,86 kB / 10,18 gzip, Initial 268,72/76,84 · größte neue Datei 235 Z. (Spec), Produktiv 208** · **A1 ✅ 2026-07-26 — Lauf-Detail.** `GET /eval/runs/{id}` als Panel: Kopf, Gold-Scorecard (Quote je Kategorie, harte Gesamtquote, Judge-Schnitt SEPARAT), Turn-Tabelle nach Flow gruppiert mit eigener Zwischenquote je Flow, aufklappbare Bot-Antwort. **Reine Logik ausgelagert** (`views/gold-scorecard.ts`, 128 Z.): Gruppierung + harte Quote ohne DOM testbar. **Nicht nachgebaut, was der Server schon rechnet:** ALT rechnete mit `flowAgg` clientseitig nach, was `golden_metrics.per_flow` liefert — zwei Implementierungen einer Summe, die Client-Kopie ohne Test. **Backend-Fund, am Interpreter belegt:** `per_flow` trägt KEINE Persona, obwohl es so aussieht — `aggregate_golden` baut `{'title':…, 'persona': conv['persona_id'], **{c: cell for c in GOLDEN_CATS}}`, und `GOLDEN_CATS` enthält `persona`, also überschreibt der Spread die ID mit der Kategorie-Zelle (in ALT genauso); die Persona kommt daher aus `conversations[].persona_id`. Mein Test-Fixture hat den Konflikt ausgelöst — TS meldete „'persona' is specified more than once". **Kein Polling, mit Grund:** diese Antwort trägt die vollen Transkripte, die Lauf-Liste pollt schon und zeigt `current_activity` — ein laufender Lauf wird hier deshalb ausdrücklich „Momentaufnahme" genannt und hat einen „Aktualisieren"-Knopf. **Zwei Darstellungen, nie beide**: mit `golden_metrics` die Turn-Tabelle (Bot-Text in der aufgeklappten Zeile, wie ALT), ohne sie die Transkript-Liste — kein Gespräch doppelt. **ALT-Defekte nicht mitportiert:** `<tr onClick>` als Klickziel (die dichteste Information ohne Maus unerreichbar → `<button>` mit `aria-expanded`, Test prüft Fokussierbarkeit) und `rateColor`s Hex-Trio (`#16a34a`/`#d97706`/`#dc2626` ≈ 3,4/2,9/4,0∶1 auf Weiß, alle unter AA für diese Textgröße → geprüfte `--st-*-text`-Token; die Zahl steht ohnehin daneben). **Rot-Grün:** `host` in die harte Quote gefaltet → genau 2 Tests rot (einer je Ebene). **Eigene wertlose Zusicherung gefunden und ersetzt**: `querySelector('tr[onclick]')` kann nie etwas finden, Angular erzeugt kein `onclick`-Attribut. · **A2 ✅ 2026-07-26 — Gold-Start.** Gleiche Zwei-Stufen-Rückfrage wie A3, aber **exakte Zahl statt Schätzung**: ein Gold-Lauf feuert einen Chat-Aufruf je konfiguriertem Turn, und die Turns stehen in `gold-flows.yaml` — also wird summiert, nicht `/eval/estimate` gefragt, und der Text sagt „keine Schätzung". Der `judge`-Schalter ist der teure: seit C3 läuft er wirklich und kostet einen LLM-Aufruf je beantwortetem Turn, die Oberfläche nennt diese Zahl statt „mit Judge" der Deutung zu überlassen. **Typ-Fund:** `GoldFlow` im Studio deklarierte `name`/`description` — die Felder heißen `title`/`persona`/`intents`; die Liste hätte leere Titel gezeigt. **Rot-Grün:** `judge` aus dem Request entfernt → 1 Test rot. · **A4 ✅ 2026-07-26 — Pattern-Nutzung** als dritter Tab. Liest `quality_logs`, also unabhängig vom Eval-Motor; der Bereichsfilter (alle/Eval/echt) entscheidet, welche Frage die Zahlen beantworten, und steht deshalb zuerst. **Wiederverwendung statt Neuzeichnen:** die zwei Verteilungen füttern `QualityBarsComponent` aus 9-5c (Tabelle mit versteckter Balkengrafik) — neu ist nur die Umformung `[{id,count}] → Record`. `since` ist ein natives `<input type="date">`, weil `datetime.fromisoformat` ein bloßes Datum akzeptiert (kein Datepicker, kein Format zu erklären). `avg_conf: null` heißt „kein Turn trug eine Konfidenz" und wird als „–" gezeigt, nicht als 0; ein leeres Pattern-Feld heißt „(ohne)" statt einer leeren Zelle. **studio 602 grün (547 → +55) · eslint 0 · Token-Abgleich leer · Evaluation-Chunk 74,12 kB / 16,34 gzip, Initial 268,99/76,87 · alle neuen Dateien ≤ 300 Z.** |
| 9-6 ✅ | Header-Tools | Snapshots-Modal, Backup/Restore, Factory, Status-Dot, Jaeger-Link, Live-Preview(V8). · **A6 ✅ 2026-07-26 — View „Sicherung" (Snapshots + Werksstand + Voll-Backup).** **Vor dem Bauen gemessen, was diese Zeile überhaupt noch fordert:** Status-Dot steht seit 9-2; **Modell-Auswahl gibt es in ALT nicht** (`grep`: `chat_model` erscheint nur als *Anzeige* in `HomeOverview.tsx:266` und `InfoView.tsx:94-95`, und **kein** Endpunkt in ALT oder NEU setzt ein Modell — `llm_models.py` löst aus Settings/ENV auf), die Anzeige selbst steht seit A5 auf Startseite und Referenz; **Jaeger-Link nicht ehrlich baubar**: Jaeger existiert nur in `deploy/compose.dev.yml` (`localhost:16686`), kein Setting und kein Endpunkt veröffentlicht eine UI-Adresse, `OTEL_EXPORTER_OTLP_ENDPOINT` ist der Collector (4318), nicht die Oberfläche — ein hartkodierter Link wäre in jedem Deploy außer einem lokalen Compose-Lauf tot (Aufwertungspfad: ein Setting + ein Feld in `/api/health`); **Monaco-Neuentscheid: unverändert nein** — weder `monaco-editor` noch ein CodeMirror liegt in `node_modules`, an der 9-3-Messung (97,9 MB entpackt + Worker-/Asset-Pipeline für eine YAML/MD-Rohansicht) hat sich nichts geändert, das `<textarea>` bleibt. · **Eine View, kein Header-Dialog:** jsdom 29.1.1 implementiert `HTMLDialogElement` mit **ausschließlich** `open` — kein `showModal`, kein `close` (probiert, bevor entschieden wurde); genau die tragenden Modal-Eigenschaften (Fokusfalle, Esc, inerter Hintergrund) kann ein Stub nicht belegen, und eine handgebaute Fokusfalle ist die klassische a11y-Falle. Also Registry-Eintrag `sicherung` (System, 9-6) ⇒ Route + Nav-Eintrag ohne Drift-Risiko; das korrigiert die 9-2-Notiz „Snapshots = Header-Chrome" und hebt `STUDIO_VIEWS` von 17 auf **18** (Testkommentar mitgezogen). · **Was ein Snapshot ENTHÄLT, entscheidet, was die Oberfläche verspricht** — dritter Fall der C2/A5-Klasse: ALTs Snapshots trugen die SQLite-Datei, NEU packt Config-Bereiche und sonst nichts (`create_snapshot` setzt `include_db` nie, der Dump ist P10). Nicht portiert wurden deshalb ALTs Checkbox „Datenbank einschließen", das „+ DB"-Abzeichen und die Warnungen über Sessions/Memory/Quality-Logs/RAG-Chunks. Ebenfalls ohne Gegenstück: die wipe/merge-Frage (`_apply_config` merged immer) und „Snapshot als Factory übernehmen" (`save_factory` kennt kein `from_snapshot`). · **Downloads werden geholt, nicht angesurft:** ALTs `window.location.href` ersetzte bei einem 404 das ganze Studio durch rohes JSON; `StudioApi.blob()` + `core/download.ts` halten den Fehler auf dem Fehlerpfad, wofür der Fehler-Body eigens aus dem Blob gelesen wird (mit `responseType: 'blob'` ist `err.error` ein Blob, `detailOf` hätte nur „Not Found" gesehen). · **Neu und geteilt:** `core/action-state.ts` (Schreib-Zwilling zu `AsyncData` aus 9-5a; `busyKey` statt Boolean, damit nur der gedrückte Knopf „…" sagt; EIN Meldungs-Signal, damit „Erfolg und Fehler gleichzeitig" nicht darstellbar ist), `core/snapshots-api.service.ts` (12 Endpunkte; `FactoryInfo`/`SnapshotRow` von `overview-api` hierher gezogen, wo ihre Endpunkte liegen) und `views/_ops-panel.scss` (drei Panels, eine Partial — statt der drei Kopien, die 9-5a schon als Fehlerquelle belegt hat). · **Eigener a11y-Fund im Selbst-Review:** die Rückfragen erschienen für Screenreader lautlos (sie stehen unter dem auslösenden Knopf, der Fokus wandert nicht) → `role="alert"` an allen sechs, Test dafür. **Eigener Defekt beim Diff-Lesen:** nach erfolgreichem Einspielen setzte ich `file()` auf `null`, während das native `<input type="file">` den Namen weiter anzeigt — Anzeige und gesperrter Knopf hätten sich widersprochen; die Wahl bleibt jetzt stehen. **Zwei eigene Test-Zusicherungen waren falsch, nicht der Code:** `germanDateTime` (der geteilte Formatter, 6 Nutzer) schreibt `20.7.2026` ohne führende Null, und den gewählten Dateinamen zeigt das native Datei-Feld selbst — jsdom rendert ihn nur nicht. · **Rot-Grün belegt:** Core — Revoke synchron · Meldung nicht abgeräumt · Blob-Fehlerdetail verworfen ⇒ **genau 3** rot; Views — Restore ohne Rückfrage · „Datenbank" im Leertext · Werksstand-Knöpfe ohne `exists`-Sperre ⇒ **genau 3** rot. Beim ersten Anlauf biss die Datenbank-Umkehrung **nicht**, weil die Zusicherung nur den gefüllten Zustand prüfte — verstärkt, statt die Umkehrung zu wechseln. · **Belege:** studio **669** grün (635 → +34) · ui 454 · widget 30 · `npx eslint .` exit 0 · Token-Abgleich leer · `ng build studio` Initial **269,84 kB / 77,10 kB gzip**, Lazy-Chunk `backup-component` **25,08 kB / 5,07 kB gzip** · größte neue Datei 166 Z. (Spec), größte Produktivdatei 123 Z. · **A6-Rest ✅ 2026-07-26 — View „Vorschau" (Live-Preview, V8), damit ist 9-6 komplett.** Das echte `<boerdi-chat>` im Studio, gegen dasselbe Backend. **Die Frage des Pakets war, woher das Element kommt**: §5.6 sagt „aus demselben Workspace" — und die Alternative gibt es gar nicht, denn `api/widget.py` ist unverändert der P0-4-Stub (alle fünf Routen `raise todo("P7")` → 501), ein `<script src="/widget/boerdi-widget.js">` liefe ins Leere. Das ist beim Messen aufgefallen und steht jetzt als **C4** in der Rubrik; die Vorschau selbst ist davon nicht betroffen. Also dynamischer Import von `projects/widget/src/widget-main` hinter einer DI-Naht (`core/widget-element-loader.ts`) — nötig, weil dieser Import eine ZWEITE Angular-Anwendung startet (`createApplication`), die in jsdom nichts zu suchen hat; die View-Tests ersetzen die Naht. `customElements.whenDefined` mit **Frist (15 s)**: `widget-main.ts` fängt einen gescheiterten Bootstrap selbst ab und loggt ihn nur — ohne Frist bliebe „wird geladen …" für immer stehen und behauptete Fortschritt, den es nicht gibt. · **Vier Attribute weichen vom Default ab, jedes mit Messung:** `auto-context="false"` (der Default sammelt Pfad, Titel, Query und DOM-Text der TRAGENDEN Seite ein, `widget-init.ts:65-92` — im Studio also die Studio-Seite, verschickt als Besucher-Kontext), `persist-session="false"` (`bootSession` liest und schreibt bei `persist:false` **gar nichts**, `session-boot.ts:38-41` — sonst setzte jede Vorschau das Gespräch von gestern fort, statt den Konfigurations-Boot zu zeigen), `initial-state="expanded"` (zu prüfen ist die Begrüßung, und die steht im Panel) und `api-url` = eigene Herkunft (funktional gleich dem Client-Default `'/api'`, `chat-api.ts:120` — gesetzt, damit die Seite zeigt, mit welchem Backend sie spricht). · **Nicht in einen Rahmen gesperrt:** `:host { position: fixed; z-index: 999999 }` (`_widget-fab.scss:21`); ein Container mit eigenem Enthaltungsblock (`transform`/`contain`) würde `position: fixed` umdeuten und eine Anordnung zeigen, die es auf keiner echten Seite gibt — die Seite sagt stattdessen, wo das Widget sitzt. · **Der Seitenkontext ist ein Formular, keine JSON-Box**, und bietet **genau drei** Seitentypen an: `_GREETABLE_KINDS = ("collection", "content", "topic")` (`context_greeting.py:47`). `subject` und `search` kennt der Prompt-Block zwar, aber sie lösen weder proaktive Begrüßung noch Pills aus — sie anzubieten hieße, eine Wirkung zu versprechen, die ausbleibt. Die Schlüsselpaare (`page_kind` + `topic_page_slug`/`collection_id`/`node_id`) stammen aus dem Detektor (`page-context-detector.ts:79/101/110`); `detection_source: 'studio:vorschau'` macht Vorschau-Sitzungen in den Auswertungen unterscheidbar. Ohne Wert wird **kein halber Kontext** geschickt (ein `page_kind` ohne ID/Slug löst nichts auf: die Begrüßung bliebe aus, und die Vorschau sähe aus, als sei die Konfiguration kaputt). Übernommen wird erst beim Absenden (Lehre aus 9-5c) — sonst startete jeder Tastendruck eine neue Sitzung. · **Neustart = neues Element** (`@for (id of [boot()]; track id)`): der Konfigurations-Boot läuft nur beim Verbinden, ein „neu laden" ohne neues Element zeigte den alten Stand. · **Gemessener Preis der Workspace-Naht:** das Initial-Bündel wächst **269,95 → 295,13 kB raw (+25,18)**, isoliert belegt durch je einen Build mit und ohne die eine Routen-Zeile. Im initialen Rudel steckt **kein Widget-Code** (auf `boerdi-chat`, `boerdi-fab`, `createCustomElement`, `NgElementStrategy` geprüft — alle vier nicht vorhanden), es sind zurückbehaltene Framework-Pfade; welche genau, ist aus dem Output nicht attributierbar, weil esbuild die Chunks neu aufteilt — meine erste Vermutung (`attachShadow`) war falsch, die liegt in beiden Ständen drin. Budget: Warnung 600 kB, Fehler 900 kB. · **Selbst-Review strich Code:** `onKind` leerte beim Typwechsel das Wertfeld; Sammlung und Inhaltsseite meinen aber dieselbe UUID in anderer Bedeutung (`page_context.py` Z. 6-7), das Leeren war also ein Neu-Einfügen-Zwang — jetzt bleibt der Wert stehen, mit Test. · **Rot-Grün belegt:** `auto-context` entfernt · leerer Wert liefert trotzdem einen Kontext · Absenden startet nicht neu ⇒ **genau 3** rot, je Umkehrung genau der gemeinte Test; die nachgezogene „Wert bleibt"-Zusicherung einzeln geprüft (genau 1 rot). · **Belege:** studio **700** grün (683 → +17) · ui 454 · widget 30 · `npx eslint .` exit 0 · Token-Abgleich leer (28 definiert / 27 benutzt) · `ng build studio` Initial **295,13 kB / 85,69 kB transfer**, Lazy-Chunks `widget-preview-component` 8,06/2,82 kB und `widget-main` 252,20/63,56 kB · größte neue Datei 162 Z. (Spec), größte Produktivdatei 105 Z. · Registry 18 → **19** Views (`studio-views.spec.ts` nachgezogen). |

## P10 — Cluster & Betrieb (M)

compose.prod.yml (traefik, backend x3, ~~TEI~~, jaeger, PG mit Backup-Cron), Cluster-Checkliste §8
als Testprotokoll, Lasttest-Abnahme, Security-Review-Checkliste (Audit-Erbe-Punkte), Runbook.

**Ohne TEI** (Korrektur 2026-07-27): diese Zeile ist älter als V13. Der Sidecar wurde am
2026-07-12 aus Kostengründen verworfen (Nutzer-Entscheid, s. V13-Tabellenzeile), der Reranker
läuft seither in-proc — und `rerank_url` wird im gesamten `src/`-Baum von niemandem gelesen.
Auch die §4-Skizze nennt den Sidecar noch als „optional per Env"; er ist es nicht.

## P11 — Migration & Cutover (M)

§9-Schritte als Tasks; Abnahme = Golden-A/B-Report ohne inhaltliche Regression + Redaktions-Fahne.

### P11-Schritt 4a ✅ 2026-08-09 — der Abweichungs-Report, den §9-4 verlangt

Schritt 4 heißt „Golden-Suite gegen ALT und NEU — **Abweichungs-Report pro
Flow/Turn**". Der Runner schreibt beide Reports seit P0-8; **der Vergleich war nie
gebaut** — das README nannte ihn nur als Absicht („`--label alt` vs `--label neu`
Reports diffen"). Im ALT-Baum gibt es auch kein Vorbild: `eval_metrics.py` nennt die
Scorecard „A/B-vergleichbar", vergleicht aber nichts. Also Neubau, kein Port:
`evals/compare_golden.py` (264 Z., framework-frei wie der Runner, damit er gegen
jedes Backend läuft).

**Die eine Entwurfsentscheidung, die den Report brauchbar macht: was NICHT
verglichen wird.** Ein Golden-Turn trägt neben den Checks auch Wortlaut,
`content_len` und die Sie/du-Zähler. Die weichen bei jedem Lauf desselben Backends
ab — ein Vergleich, der sie mitmeldet, schlägt bei *jedem* Turn an und begräbt damit
die eine Abweichung, auf die es ankommt. Verglichen werden deshalb nur
Check-Ergebnisse, Klassifikation (persona/intent/pattern) und Struktur
(cards/idocs/qr). Das Register hat bereits einen eigenen Check; die Beobachtung
zusätzlich zu melden wäre dieselbe Aussage zweimal.

**Regression ist ausschließlich True→False.** `None` heißt im Runner „für diesen
Turn nicht geprüft" (Wildcard-Persona, leerer Intent, kartenloser Turn bei `host`) —
daraus eine Regression zu machen hieße, Beobachtungslücken als Fehler zu zählen.
`host` bleibt weich wie im Runner. Blockierend sind: harte Regression, Fehl-Turn in
NEU, oder ein Flow/Turn nur auf einer Seite — **ein abgebrochener NEU-Lauf darf
nicht als „keine Regression" durchgehen**, sonst belohnt der Report den Abbruch.

Für die in §9-4 ebenfalls geforderte **Stichproben-Redaktion** trägt der JSON-Report
beide Wortlaute an jedem abweichenden Turn mit — nur dort, sonst wäre er eine Kopie
der beiden Eingangs-Reports. Die Kategorien-Aufteilung hart/weich wird aus
`run_golden.py` **per Pfad geladen statt kopiert** (dieselbe Einschränkung, die der
Runner in seinem Kopf begründet); eine zweite Liste wäre stille Drift.

**Belege:** 17 neue Tests (`backend/tests/test_golden_compare.py`), Backend
**2541 / 4 skips**, ruff sauber. Nicht nur gegen Attrappen: der echte ALT-Smoke-Report
gegen sich selbst → „Keine Abweichung", Exit 0; gegen eine gezielt verfälschte Kopie
(Pattern M06→M15, Persona-Check gekippt, Karten weg, ein Turn auf Fehler) → alle drei
Befunde einzeln benannt, unveränderter Turn 4 taucht nicht auf, Exit 1.
**Offen bleibt Nutzer-Domäne:** die beiden echten Läufe (Parallelbetrieb auf
Zweit-Port), die Redaktions-Fahne, Schritt 5 (Widget-Umschaltung) und 6 (Stilllegung).

### 2026-08-11 ✅ — MCP-Anmeldeknopf, Reranker-Sichtbarkeit, Schreib-Abnahme

Drei Nutzer-Aufträge, je mit eigenem Plan-Dokument; hier nur, was über das
einzelne Paket hinaus gilt.

* **Anmeldeknopf unten rechts** neben der Eingabezeile, damit er im
  Einbettungs-Modus bleibt, plus Abmelden — `docs/plans/2026-08-11-mcp-anmeldung-knopf.md`.
  Nebenbei ein **vorbestehender WCAG-1.4.10-Fehler** bei 320 px behoben: die
  Zeile lief schon vorher um 9 px über, weil `min-width: auto` das Eingabefeld
  nicht unter seine ~193 px schrumpfen ließ. Ein `min-width: 0`.
* **Reranker-Sichtbarkeit:** `/api/health` führt jetzt `reranker` mit
  `ready` / `model-missing` / `off`. `model-missing` ist der teure Fall —
  eingeschaltet, Modell fehlt, Antworten werden unauffällig schlechter.
  `ready` sagt bewusst nicht „geladen": das Modell kommt erst beim ersten Zug
  in den Speicher. Kein Vertragsbruch, `/api/health` gibt ein untypisiertes
  `dict` zurück.
* **Schreib-Abnahme (S0–S4)** — `docs/plans/2026-08-11-schreib-abnahme.md`.

**Der Fund, der über alle drei hinausgeht — und die dritte Wiederholung
derselben Fehlerklasse.** Der Bestätigungs-Wall vor den kuratierenden
MCP-Werkzeugen legte seinen Merkposten in `session_state["_pending_write"]`,
also auf die **oberste Ebene**. Dort überdauert nichts einen Zug:
`graph/nodes/setup.py:63` baut den Zustand jeden Zug aus fünf Spalten neu, und
`update_session` schreibt genau diese fünf. Damit war `_pending_at_turn_start`
im Betrieb **immer `None`** — **keine Bestätigung konnte je eingelöst werden**,
jedes „ja" erzeugte nur eine neue Vorschau.

Warum 2888 grüne Tests das nicht fanden: die Naht-Tests *speisten* den
Merkposten direkt in den Tool-Loop ein, auf derselben obersten Ebene, die der
Code annahm. **Die Attrappe teilte die Annahme des Codes, statt die
Wirklichkeit abzubilden** — dieselbe Klasse wie bei den P11-Live-Funden
(LiteLLM lieferte dicts, die Attrappen Objekte) und bei
`prewarm_vocabularies()`. Gegenmittel hier: gepinnt wird jetzt die
**Verbindung** zwischen Tool-Loop und DB-Schreibung
(`test_offener_schreibvorgang_ueberlebt_den_zug`), nicht eine der beiden Seiten
— denn genau dazwischen lag der Fehler.

Der Merkposten wohnt seitdem in `entities`, wo die übrigen zugüberdauernden
Merker schon liegen (`_last_pattern`, `_frame`, `_canvas_material_type`) und wo
der Debug-Auszug `_`-Schlüssel wieder herausstreicht: gespeichert **und**
unsichtbar. Der Vorschautext dagegen bleibt bewusst auf der obersten Ebene — er
DARF den Zug nicht überdauern; dass dort nichts gespeichert wird, ist für ihn
die gewünschte Eigenschaft.

**Zweiter Befund, gleiche Familie wie C1-f1:** die Anweisung „zeige dem Nutzer
die Vorschau" stand an **zwei** Orten (M18-Kernregel im Seed und `_ZWEISTUFIG`
an jeder Werkzeug-Beschreibung). Nur einen zu ändern hätte die Doppelung
verschoben statt beseitigt. Beide tragen jetzt einen Wächter, der den anderen
namentlich nennt.

Gates am Ende: pytest **2905 / 4 skips**, ruff sauber, OpenAPI unverändert,
`ng test ui` **701**, `playwright` **46**, Widget-Budget eingehalten
(523,25 kB raw · 87,2 %). **Nutzer-Domäne:** Seed-Import (sonst wirkt S4 nur
zur Hälfte), Widget-Auslieferung, Live-Smoke gegen einen angemeldeten
MCP-Server.

### 2026-08-12 — E4: ein liegen gelassener Schreib-Vorgang verfällt

**Geändert:** `domain/write_confirm.py` (+`TOKEN_TTL_SECONDS`, +`is_expired`,
`remember_pending`/`token_for` bekommen `now`), `services/tool_loop.py` (Uhr an
beiden Nahtstellen + eigener Protokoll-Zweig), `tests/test_write_confirm.py`.

Der Merkposten eines offenen Vorgangs überdauert bis zum Sitzungsende. Fragte
jemand Stunden später zufällig **exakt** dasselbe erneut an, wurde der alte
Schlüssel eingesetzt, vom Server abgelehnt (er gilt zehn Minuten) und durch
eine neue Vorschau beantwortet — ein überflüssiger Werkzeugaufruf, keine
falsche Änderung, **kein Loch**: die Frist gilt serverseitig. Jetzt gilt sie
auch hier, und zwar als Ersparnis, nicht als Absicherung.

**Kein Erfinden nötig — das Muster stand schon da.** `services/page_context.py`
legt `"_resolved_at": time.time()` in ein persistiertes Dict und prüft
`(time.time() - ts) < ttl`. Dieselbe Form, dieselbe Ablage (JSONB in
`entities`), keine Migration.

**Der Fund beim Bauen:** die bestehende Protokollzeile hätte gelogen. Sie sagt
„Argumente weichen von der Vorschau ab" — bei einem abgelaufenen Vorgang
stimmen die Argumente aber überein. Ohne einen eigenen Zweig hätte E4 also
einen *falschen Grund* aufgezeichnet statt gar keinen. Deshalb zwei
unterscheidbare Zeilen, und ein Test, der beide gegeneinander pinnt.

**Aufwärtspfad benannt:** ein Merkposten ohne Zeitstempel (aus der Zeit vor E4)
gilt als abgelaufen — nicht beweisbar frisch heisst nicht absetzen. Das kostet
genau den einen Aufruf, den E4 sonst spart, und nur für die Sitzung, die beim
Deploy gerade lief; die nächste Vorschau legt einen vollständigen ab.

**Rot-Probe, alle vier ROT:** Fristprüfung entfernt · Merkposten ohne Zeitpunkt
gilt als frisch · Grenze `>` statt `>=` · eigener Protokoll-Zweig entfernt.

**Belege:** pytest **3010 passed / 4 skipped** (vorher 3003) · ruff sauber ·
`export_openapi.py --check` grün.

### 2026-08-11 (2) — Kostenüberwachung K1-0 + K1a, und **die vierte Wiederholung derselben Klasse**

Plan: `docs/plans/2026-08-11-kostenueberwachung.md` (Messung, Entscheidungen,
K1–K5). Gebaut sind bisher **K1-0** und **K1a**.

**Der Fund kam vor der ersten geplanten Zeile.** K1a sollte nur
Reasoning-Token lesen. Beim Nachsehen, wer den Token-Merkposten anlegt, stellte
sich heraus: **niemand.** `TurnContext.usage` stand auf `{}`, und
`new_accumulator()` hatte im ganzen Backend **keinen Aufrufer** — ALT ruft es
in `chat_turn_setup.py:175`, der Port hat die Zeile verloren. Weil `add_usage`
bei falsy `acc` still zurückkehrt, war **jede** der fünf Durchreichungen
(assess/route/respond/assemble/persist) ein No-Op und `debug.token_usage` in
**jeder** Bot-Nachricht `{}`. Nicht „zu niedrig" — null. Das Debug-Panel zeigte
die Token-Zeile nie an, weil ihre Bedingung `token_usage['calls']` ist.

Das ist der **9. Fall „dokumentiert ohne Konsumenten"** und die **4.
Wiederholung** der Attrappen-Klasse (P11-LiteLLM ×2, `_pending_write`,
`prewarm_vocabularies`): `obs/usage.py` hatte 7 Tests, jede Durchreichung
eigene — und **alle bauten den Merkposten von Hand**, also genau die Annahme
nach, die im Betrieb niemand erfüllte. Gepinnt wird deshalb wieder die
**Verbindung** (`test_frischer_zug_bringt_den_token_merkposten_mit` +
`test_buchung_auf_dem_frischen_zug_kommt_an`), nicht eine der Seiten. Ein
Bestandstest schrieb den Irrtum fest (`assert ctx.usage == {}`) und wurde mit
Begründung korrigiert.

**Wohnort des Fixes, bewusst abweichend von ALT:** nicht im setup-Knoten,
sondern als `default_factory` am Feld. ALTs lokale Variable entspricht in NEU
dem Zug-Zustandsfeld, nicht einem Knoten-Seiteneffekt — so bringt **jeder**
Zug den Merkposten mit, auch der in einem Node-Test direkt konstruierte. Die
Optionalität war die Ursache; sie zu beseitigen ist der Fix.

**Was ich mir selbst korrigieren musste:** §2.1 des Kostenplans hieß „Was schon
trägt — mehr als vermutet". Ich hatte die *Mechanik* gelesen und daraus
geschlossen, dass sie *läuft*. **Gelesene Mechanik ist kein Beleg für einen
Ablauf** — dieselbe Lehre wie „eine Zählung ist kein Befund", eine Ebene höher.

**K1a** selbst dann wie geplant: `extract_usage` liest
`completion_tokens_details.reasoning_tokens` (gegen die **echten** LiteLLM-Typen
gepinnt, nicht gegen eine Attrappe), der Merkposten führt sie in allen drei
Töpfen. `cached`/`reasoning` sind **„davon"-Zahlen** — enthalten in
`prompt`/`completion`, nicht zusätzlich; wer addiert, zahlt doppelt. Der
Kommentar in `api/schemas_debug.py` und der TS-Typ in `message-types.ts` sagen
das jetzt ausdrücklich.

Gates: pytest **2909 / 4 skips** (vorher 2905), ruff sauber, OpenAPI
unverändert, `ng test ui` **701**. Keine Anzeigeänderung — die gehört zu K5.

**Nachtrag desselben Tages — K1b–K1d gebaut** (Lernpfad, Kuration, Canvas,
Rechtsprüfung buchen jetzt). Vier der fünf Stellen aus der Messung sind
verdrahtet; offen bleibt K1e (Vokabular-Abgleich, Entscheidung nach Messung).

**Der Befund dabei ist eine Wiederholung, aber mit neuer Lehre:** die
Messtabelle im Kostenplan zählte **Aufrufstellen** zu niedrig — zwei der fünf
Funktionen haben je **zwei** Aufrufer (`generate_learning_path_text`:
LP-Fast-Path *und* Direkt-Aktion; `assess_safety`: assess-Knoten *und*
preflight). Das ist das **7. Mal**, dass eine eigene Aufzählung eine untere
Schranke war. Arbeitsregel daraus, enger als bisher: **vor dem Verdrahten auf
den Funktionsnamen greppen, nicht der eigenen Tabelle glauben.**

**Zweiter Fund, struktureller:** Direkt-Aktionen beenden den Zug im
preflight-Knoten. `turn_persist` — die einzige Stelle, die `token_usage`
füllt — läuft dort **nie**. Die Buchung wäre also wieder berechnet und
weggeworfen worden, derselbe Fehler wie M0 eine Ebene tiefer. Deshalb setzen
die beiden Direkt-Aktions-Handler `token_usage` in ihr **eigenes**
`DebugInfo`. Für K2 ist das eine Vorgabe, keine Fußnote: der
`usage_events`-Schreiber darf nicht allein in `turn_persist` sitzen.

**Dritter Fund, und er kam vom Nachsehen statt vom Abarbeiten:** auch das reine
**Blättern** (`browse_collection`) ruft den Quick-Reply-Generator — ein echter
LLM-Aufruf, der in keiner Liste stand. Die Messung zählte Module mit *eigenem*
Generator und übersah den **geteilten**. `generate_quick_replies` unterstützt
`usage_acc` ohnehin seit je und bekam in allen drei Direkt-Aktionen einfach
keines: kein Bau nötig, nur ein Argument. `show_content_text` ist dagegen
gemessen frei von LLM-Aufrufen und bleibt bewusst ohne Merkposten.

Gates nach K1b–K1d: pytest **2925 / 4 skips**, ruff sauber, OpenAPI
unverändert.

**Nachtrag 2 desselben Tages — K1e, und die Lehre heißt: nachsehen, wie das
Haus dieselbe Frage schon beantwortet hat.** Der Plan gab drei Wege vor und
empfahl „Zug-Kontext durchreichen". Die Messung davor brachte beides — die Zahl
**und** einen vierten Weg.

*Die Zahl:* der Vokabular-Abgleich schickt das **ganze** Vokabular im Prompt.
Gegen die echten WLO-Daten gemessen (Produktivpfad gefahren, nur der Netz-Aufruf
abgefangen): **2727 Token** für `lrt`, 2422 für `discipline`; vier Filter an
einem Werkzeug-Aufruf bis ~6150. Und der Pfad ist nicht selten: von 61
realistischen Filterwerten fallen **21,3 %** durch die Fuzzy-Heuristik zum LLM
durch — darunter `Gymnasium`, `Oberstufe` und, am deutlichsten, **`teacher` und
`learner`**, weil die englischen Wörter in der Zielgruppe nicht als Alias
stehen. Seit C1 sind englische Züge zugesagt, dieser Weg zieht also **häufiger**
statt seltener. „Nicht buchen" war damit widerlegt, nicht abgewogen.

*Der vierte Weg:* der empfohlene Weg 1 kostet nicht „drei Schichten", sondern
den Vertrag der `TOOL_PREPROCESSORS`-Registry plus **25 `call_mcp_tool`-Stellen
in 11 Dateien**, die mit Kosten nichts zu tun haben. Den Ausschlag gab dann
nicht mein Abwägen, sondern ein Fund: **dieselbe Frage ist in genau diesem Pfad
schon entschieden und begründet** — `mcp/auth.py` trägt den Zugangsblock per
`ContextVar`, „weil es 23 Aufrufstellen von `call_mcp_tool` in 9 Dateien gibt;
der Block interessiert unterwegs niemanden", und nennt `_query_metas` und
`_request_hints` als dieselbe Lösung. Drei Vorgänger, gleiche Lage, gleiche
Antwort. **Arbeitsregel daraus: bevor man eine Quer-durch-Frage neu abwägt,
nachsehen, ob das Haus sie schon beantwortet hat** — die Begründung steht dann
meist geschrieben da, und Abweichen wäre die Ausnahme, die man rechtfertigen
muss. Ein ContextVar ist dabei kein Modul-Zustand im Sinn der eisernen Regel:
der Wert hängt an der asyncio-Task, ist je Zug getrennt und bei N Repliken
richtig — anders als die verworfene Prozess-Summe (Weg 2).

Gebaut: `bind_turn_usage`/`current_turn_usage` in `obs/usage.py` (Standard
`None`, **nicht** `{}` — ein leeres Dict wäre M0 von vorn), gebunden im
setup-Knoten neben `reset_query_metas()` (`START → setup`, also erbt jeder
spätere Knoten und jede Task die Bindung), gelesen an der Aufrufstelle als
sichtbares `usage_acc` — so braucht der kommende K1f-Wächter dort **keine**
Ausnahme. Der Test über die Naht fährt setup und Blatt in EINER Task-Kette und
stand vor dem Fix auf `calls == 0`; zwei getrennt grüne Tests wären genau die
Konstellation gewesen, die M0 durchgelassen hat. Nebenfalle notiert:
`asyncio.run` kopiert den Kontext, eine Bindung **im** Lauf ist draußen
unsichtbar — die Prüfung muss innerhalb stehen.

**Nachtrag 3 — K1f, und der Wächter fängt beim ersten Lauf einen echten
Fehler.** Der AST-Wächter (`tests/test_usage_coverage.py`) zählt alle
`chat_completion`-Aufrufstellen unter `src/boerdi/` auf: 12 gefunden, 6 ohne
`usage_acc`. Fünf davon sind begründete Ausnahmen (vier Eval-Pfade, außerhalb
des Umfangs; `_run_tool_loop`, das selbst bucht, weil das Phasen-Etikett erst
aus `finish_reason` folgt). Die sechste war ein **echtes Loch**:
`_max_iterations_fallback` — der Abschluss-Aufruf, wenn der Tool-Loop die
Iterationsgrenze reißt, hängt die GANZE Nachrichtenkette an und lief ungebucht.
**Fünfte Wiederholung derselben Klasse — und die erste, die nicht ich gefunden
habe, sondern die Maschine.** Warum jede frühere Zählung sie übersah: sie suchte
Module mit *eigenem* Generator, und `tool_loop` galt als „bucht schon" — es
bucht auch, nur an einer anderen Stelle derselben Datei. Gebucht wird jetzt
unter eigener Phase `fallback_summary`, deren Auftauchen zugleich meldet, dass
der Zug die Grenze gerissen hat. Der Wächter prüft **beide** Richtungen (eine
tote Ausnahme lässt ihn fallen), sein Aufzähler ist gegen erfundene Quelltexte
selbst geprüft, und eine Untergrenze schützt vor dem stillen Totalausfall bei
kaputtem Pfad.

**Nachtrag 4 — K2a/K2b: Tabelle und Schreibpfad.** `usage_events` + Migration
0002, **beide Richtungen gegen die laufende Compose-PG gefahren** (up → down →
up, je mit Sichtprüfung der Tabelle). Die DSGVO-Zusage des Plans ist als Test
belegt, nicht behauptet: mit der Sitzung verschwinden ihre Verbrauchszeilen.

**Die Entscheidung, die von der Vorlage abweicht — Trichter statt
Aufzählung.** Der Plan wollte den Schreibvorgang in `turn_persist` plus eine
zweite Stelle für Direkt-Aktionen. Die geforderte Aufzählung wurde gemacht und
ergab: nur zwei Ausstiege kosten überhaupt Token (Hauptweg und preflight);
Tour und Kontext-Begrüßung rufen kein LLM. Trotzdem ist Aufzählen hier der
falsche Ansatz — die Fehlerklasse, an der dieser Plan fünfmal hing, heißt „ein
neuer Weg entsteht und fällt still heraus", und dagegen hilft nur ein Punkt,
den **jeder** Zug passiert. Das ist die Stelle hinter `ainvoke`; der Merkposten
liegt dort seit K1-0 als `state["usage"]` bereit. Zwei sichtbare Aufrufstellen
(POST und Stream) statt einer Liste, die veralten kann. **Regel: gegen „still
herausfallen" hilft ein Trichter, kein sorgfältiges Aufzählen.**

Gates nach K1e: pytest **2932 / 4 skips** · nach K1f **2940** · nach K2a/K2b
**2952 / 4 skips**, ruff sauber, OpenAPI unverändert.
**Alle fünf Stellen der Messung buchen jetzt**; von K1 fehlt nur der Wächter
K1f. Nebenbefund für die Redaktion, nicht für den Code: fehlende Vokabular-
Aliase (`teacher`, `learner`, `Gymnasium`, `Oberstufe`) kosten heute je einen
LLM-Aufruf, wo eine Alias-Zeile genügt hätte.

### W7 + W7b ✅ 2026-07-31 — Such-Prefetch entgiftet, MCP-Server gewechselt

**W7 (Nutzer-Entscheid).** Live gemessen: `search_wlo_topic_pages` lieferte bei
**jeder** Suche dieselben drei Treffer — „OERinfo", „Vorlage: Themenseite",
„Vorlage: Themenseite_Kopie" — und die standen als Karte 1–3 vor dem echten
Material. Ursache steht als Kommentar im eigenen Code (`prefetch.py`, `_primary_max`):
der Themenseiten-Index hängt serverseitig am letzten Collections-Call, nicht an
der Frage. Fix = **eine Zeile**: die Heuristik `_topic_first` nimmt jetzt
`search_wlo_all`; der ausdrückliche Nutzerwunsch bleibt beim dedizierten Tool
(Bestandstest `test_spec_explicit_topic_page_wish_beats_search_all_hint` blieb grün).
Nachher an denselben zwei Fragen: **kein Vorlagen-Treffer mehr**, Karte 1 ist
echtes Material, und der Zug ist schlanker (ein Round-Trip statt Primary + zwei
Extras). Zwei Tests umgeschrieben — ihre Prämisse hat der Entscheid geändert,
Begründung steht im Docstring.

**W7b (Nutzer-Vorgabe: neuer MCP-Host).** `MCP_SERVER_URL` →
`https://wlo-mcp.87.106.195.152.nip.io/mcp`. Tool-Liste **per `tools/list` vom
Server geholt**, nicht abgetippt: **23 Werkzeuge**, echte Obermenge der alten 12,
nichts weggefallen. Registry (`05-knowledge/mcp-servers.yaml`) darauf nachgezogen.
**Der eigentliche Fund:** `TOOL_DEFINITIONS` bot dem Modell 13 Werkzeuge an, die
Registry kannte 10, und der alte Server hatte `get_wlo_content_text` **gar nicht**
— M17 („Inhalt anzeigen") rief seit dem Bau ins Leere, ohne dass irgendwo etwas
auffiel. Zwei neue Wächter halten beide Lücken fest: die Registry muss jedes
angebotene Werkzeug kennen (sonst stiller Fallback auf die Default-URL), und die
**zwei** MCP-Default-URLs (`settings.mcp_server_url` + `transport._DEFAULT_MCP_URL`,
letzterer greift bei leerer Env — die Compose-Falle) müssen gleichziehen. Der
Zwilling stand tatsächlich noch auf dem alten Host; ohne den Wächter wäre genau
der Notfallpfad still auf dem toten Server gelandet. **Pattern brauchten nichts:**
alle 11 dort genannten Tools sind in TOOL_DEFINITIONS, der W5-4a-Wächter blieb grün.
Live belegt gegen den neuen Server: Suche 6 saubere Photosynthese-Karten;
**M17 liefert echten Volltext** (960 Zeichen „Dunkelreaktion" als Inline-Dokument),
und ein Material ohne Text bekommt die ehrliche Absage statt eines Fehlers.
Belege: ruff sauber, Backend **2240** (2 neue Wächter), Seed-Import 56 Flächen,
Registry in der DB 23 Werkzeuge.

### P11-Schritt 2 ✅ 2026-07-31 — RAG-Re-Ingest gefahren, und §9-Schritt 1 hat eine **Richtungsumkehr** gebraucht

Auftrag war „hol alles vom alten Chatbot rüber". Wörtlich ausgeführt wäre das ein
**Rückschritt** gewesen — das ist der eigentliche Befund dieses Pakets.

**Der ALT-Baum ist keine Obermenge des NEU-Seeds.** Datei-für-Datei-Vergleich der
55 gemeinsamen Dateien: **zwei weichen ab, beide zugunsten von NEU.** `m16-themenseiten-inhalt`
trägt in NEU den Ein-Call-Pfad des neuen MCP-Servers (W5-1); ALT ruft noch
`search_wlo_topic_pages` → `get_topic_page_content` in zwei Schritten. `m11-iterative-nachbearbeitung`
kennt in NEU M17 als Quelle für Vor-Inhalte. Dazu kommt `m17-volltext-anzeigen`, das
es in ALT gar nicht gibt. Ein `import-config --from ../badboerdi/...` hätte also drei
Arbeitspakete (W5-1, W5-4a, M17) stillschweigend zurückgedreht. **Regel daraus: der
NEU-Seed IST die migrierte ALT-Config plus bewusste Korrekturen — ab jetzt ist
`seeds/` die Import-Quelle, nicht der ALT-Baum.**

**Zweiter Befund: die Default-Datenbank war der veraltete Stand.** `DATABASE_URL`
zeigt auf `boerdi` — dort lagen 55 Flächen mit ALT-M16 und ohne M17 (Import vom
11.07.), während der korrekte Stand in `boerdi_p11` (Probelauf) lag, also in der
Datenbank, die beim normalen Start NICHT benutzt wird. `boerdi` ist jetzt aus
`seeds/` nachgezogen: **56 Flächen, M16 auf Ein-Call, M17 vorhanden** (per SQL
verifiziert, nicht angenommen). Vorher geprüft, dass dort niemand von Hand editiert
hatte (alle 55 Zeilen `updated_by='import'`) — sonst wäre der Import ein Datenverlust.

**Re-Ingest (§9-Schritt 2) gefahren:** `boerdi import-rag --sqlite <Kopie>` →
**906 Chunks in 80 Dokumenten**, exakt die vorab aus der Quelle gemessenen Zahlen,
**0 Chunks ohne Vektor**, 8 Wissensbereiche. Quelle war eine **Kopie** der ALT-DB
(die CLI verlangt das im Hilfetext); das Original trägt unverändert den Zeitstempel
vom 11.07. Vorab geprüft, was sonst erst nach 906 Aufrufen aufgefallen wäre: die
Einbettung liefert 1536 Dimensionen, die Spalte ist `vector(1536)` — bei Abweichung
hätte die Ein-Transaktions-Semantik den ganzen Lauf zurückgerollt.

**Abnahme inhaltlich, nicht per Zeilenzähler:** drei echte semantische Abfragen über
`query_rag`. „Was ist WirLernenOnline?" → 0,722 auf den FAQ-Eintrag mit genau dieser
Überschrift; „Welche offenen Lizenzen gibt es für OER?" → 0,741 auf die BMBF-OER-Strategie;
„Wie funktioniert die Redaktionsumgebung?" → 0,697 auf `002-redaktionen.md`.

**Kostenkorrektur:** vorher als Nutzer-Domäne eingestuft, weil „bulk embedding".
Gemessen: 715 k Zeichen ≈ 179 k Token ≈ **0,4 Cent**. Kein Grund zur Abgabe.
**Kein Code geändert** — reine Datenmigration. Offen bleibt `boerdi_p11` ohne RAG
(Probelauf-DB, bewusst nicht angefasst) sowie §9-Schritte 4–6 (Parallelbetrieb,
Widget-Umschaltung, ALT-Stilllegung).

### P11-Probelauf 2026-07-27 — §9-Schritt 1 belegt, und **zwei echte Defekte gefunden**

Ziel war „bringt den Chatbot zum Laufen" (Nutzer-Vorgabe). Vorgehen: eigene DB
`boerdi_p11`, `alembic upgrade head`, `boerdi import-config --from
../badboerdi/backend/chatbots/wlo/v1` — der ALT-Baum wurde dabei nur **gelesen**.

**Schritt 1 trägt:** 55 Bereiche importiert (29 YAML, 26 MD). Die Zahl ist nicht
35, und das ist richtig: 35 sind die *typisierten* Registry-Bereiche, der Baum
hat 55 Dateien (jedes Pattern ist eine eigene `.md`). Funktional geprüft statt
gezählt: `GET /api/config/guide-mode` liefert die echte ALT-Begrüßung, die vier
Quick-Replies und den Tour-Chip — **öffentlich**, also genau dort, wo das Widget
sie beim Boot abholt.

**Der Live-Chat fand, was 2135 grüne Tests nicht finden konnten.** Zwei Defekte,
eine Ursache: **ALT sprach mit dem nativen OpenAI-SDK (Pydantic-Objekte), NEU
spricht über LiteLLM — und das liefert an mehreren Stellen dicts.** Der
Fidelity-Port hat die Zugriffe wörtlich übernommen, obwohl der Transport darunter
getauscht wurde.

1. **`services/llm.embedding`** las `resp.data[0].embedding`. Gemessen ist
   `type(resp.data[0]) is dict`. Folge: **jeder** echte Embedding-Aufruf starb
   mit `'dict' object has no attribute 'embedding'` ⇒ jede RAG-gestützte Antwort
   fiel auf den Ersatztext des respond-Nodes zurück. Weil dieser Node
   LLM-Fehler bewusst abfängt, wurde daraus keine 500 — der Ausfall war **still**.
2. **`services/safety/moderation.moderate`** las `r.categories.model_dump()`.
   Gemessen: `results[0]` ist ein Objekt, aber `categories`/`category_scores`
   darin sind plain dicts. Folge: jeder Aufruf lief in den (dokumentierten)
   Fail-Open-Zweig — **die Moderationsstufe war im Betrieb tot**, während das
   Log `stages=openai` meldete.

**Warum die Suite grün war — das ist die eigentliche Lehre.** Beide Attrappen
waren *nach dem Code* gebaut, nicht nach der Wirklichkeit: `_FakeEmbedding` gab
`SimpleNamespace` zurück und berief sich dabei ausdrücklich auf
`litellm.types.utils.Embedding` — ein **TypedDict**, also zur Laufzeit ein dict;
aus der Feldliste wurde ein Objekt gelesen. `_fake_moderation_response` baute
eigens eine `_Bag`-Klasse mit `model_dump()`. Eine selbstgebaute Attrappe kann
eine Transport-Form nicht widerlegen. **Nur der Live-Lauf konnte das.** Beide
Formen sind jetzt in Tests gepinnt (dict = gemessene Wirklichkeit, Objekt =
Gegenprobe, damit der tolerante Zweig nicht ungeprüfter Vorratscode ist);
`EmbeddingResponse.data` ist als blankes `typing.List` annotiert, der Typ sagt
hier also nichts zu.

**Danach live belegt** (openai/gpt-5.4-mini, Nutzer-Freigabe): „Was ist
WissenLebtOnline?" → Pattern M15, `query_knowledge`, inhaltliche Antwort mit
aufgelösten Web-Links. „Materialien zum Thema Photosynthese" → Pattern M06,
MCP `search_wlo_content` (8182 Zeichen), `select_top_cards`, Typ-Filter,
gebaute Such-URL, 1 Karte. Kein `moderation failed` mehr im Log.
**Backend 2138 pytest grün (+3), ruff sauber.**

---

## Verifikations-Hierarchie (gesamt)

1. **Golden-Flow-Gate** (12 Flows, deterministisch) — Paket-Abnahmen P4–P7, A/B in P11.
2. **Portierte Charakterisierungs-Tests** (~21k LOC ALT-Tests als Fundus; je Port Pflicht).
3. **OpenAPI-Diff-Gate** (P0-4) + Kontrakt-Tests (guide-mode-Shape, SSE-Events, Encodings).
4. **CI:** ruff/eslint, pytest/vitest, Playwright-E2E, Lizenz-Gate, Bundle-Budget.
5. **Cluster-Protokoll** (P10) + Lasttest-Report.
6. Manuell nur: Jaeger-Sichtprüfung, Redaktions-Abnahme Studio (dokumentiert warum manuell).

---

### W1 ✅ 2026-07-27 — Nebenläufigkeits-Audit ALT↔NEU + Start-Vorwärmung

Auslöser: Nutzer-Frage „der Prozessablauf muss zeitoptimiert sein — im alten
Chatbot hatten wir parallelisiert, wo möglich".

**Ergebnis des Vergleichs: die Nebenläufigkeit IM Zug ist vollständig übernommen.**
Acht ALT-Stellen, acht NEU-Gegenstücke:

| ALT | NEU |
|---|---|
| safety ∥ classify ∥ memory (`chat_pipeline_phases.py:114`) | `graph/nodes/assess.py:94` |
| spekulativer MCP-Prefetch (`chat_prefetch.py:308-316`) | `services/prefetch.py:264-272` |
| Extra-Spec-Tasks (`chat_prefetch.py:386-390`) | `services/prefetch.py:344-348` |
| Quick-Replies ∥ Antwort-LLM (`chat_turn_answer.py:396`) | `graph/nodes/respond.py:324` |
| QR im LP-Pfad (`chat_turn_routing.py:528`) | `services/lp_fast_path.py:358` |
| Sammlungs-Inhalte (`chat_turn_routing.py:433`) | `services/lp_fast_path.py:264` |
| 3 Kartenquellen (`card_pipeline.py:215`) | `services/card_pipeline.py:143` |
| Tool-Loop-Gather (`llm_tool_loop.py:706`) | `services/tool_loop.py:569` |

Zwei Stellen, die seriell AUSSEHEN und es zu Recht sind: (a) ALTs `asyncio.gather`
über das CE-Karten-Gate (`chat_turn_answer.py:345`) — ALT gatherte, weil jeder
Aufruf `await _rerank_pool(...)` war (ausgelagerte CPU-Arbeit); NEUs
`rerank_gate_envelope` ist **synchron**, ein gather kaufte null Parallelität
(V13-Entscheid, im Code begründet). (b) Der M16-Kandidaten-Loop
(`topic_pages.py:253`) bricht beim ersten Treffer ab (`break`) — parallel wären
immer 3 Anfragen statt meist 1; ALT macht es identisch.

**Die Lücke lag VOR dem ersten Zug: ALT fährt sechs Start-Warmups
(`main.py:173-178`), NEU hatte davon einen** (den Config-Preload). Zwei sind zu
Recht entfallen (`_warmup_reranker`: V13 kein CPU-Reranker; `_warmup_tokenizer`:
keine tiktoken-Infra — beides dokumentierte `simplify:`). **Drei fehlten**, und
einer davon war der **fünfte Fall der Klasse „Dokumentiertes erreicht seinen
Konsumenten nie"**: `prewarm_vocabularies()` war gebaut, getestet, und
`mcp/tool_cache.py:46` beschrieb sie als „beim Backend-Start vorgewärmt" — **es
gab keinen Aufrufer**.

Gebaut: `services/warmup.py` (`warm_vocabularies`, `warm_llm_connection`,
`spawn_startup_warmups`), im `_lifespan` gerufen, fire-and-forget über das
vorhandene `obs/tasks._spawn_background`, je Warmup ein 10-s-Deckel, Fehler
geschluckt (Vorwärmung ist Beschleunigung, kein Pflichtpfad). **Der zentrale Test
fährt den echten `_lifespan`** — ein reiner Modul-Test hätte genau den Fehler
wiederholt, den er finden soll. Ein autouse-Fixture in `conftest.py` legt die
Warmups für die übrige Suite still (sie machen echtes Netz-I/O; 16
SDK-Warnungen und Netz in einer Unit-Suite).

**Bewusst NICHT vorgewärmt** (Nutzer-Entscheid): ALTs `_embed_seed_chunks`. Es
schreibt Embeddings — bei N Replicas berechneten alle gleichzeitig dieselben, und
ein Deploy löste LLM-Kosten aus. Bleibt beim Admin-Endpunkt `/api/rag/embed`.

**Live belegt:** `llm warmup done in 2673ms`, `vocabulary warmup done in 3243ms` —
Kosten, die vorher der erste Nutzer zahlte. Backend **2167 pytest** (+7), ruff
sauber, 1 Warnung (Basislinie).

### Zug-Latenz-Messung 2026-07-27 (fünf echte Züge über SSE)

Instrument: die `phase`-Zeitstempel aus C9. Dauer je Abschnitt in Sekunden:

| Abschnitt | n | min | median | max |
|---|---|---|---|---|
| Klassifikation (`safety_classify`→`context`) | 5 | 1,59 | 2,36 | 3,19 |
| `context`/`policy`/`pattern` (reine CPU) | 5 | 0,00 | 0,00 | 0,00 |
| MCP-Suche (`wlo_search`→`response`) | 2 | 1,16 | — | **23,27** |
| Antwort-LLM (`response`→`query_meta`) | 2 | 2,23 | — | 9,30 |

**Zwei Befunde:**

1. **Die Latenz wird von der MCP-Seite dominiert, nicht vom Ablauf.** Im
   Material-Zug: drei Suchen liefen parallel (2,7/3,0/2,9 s) — dann lieferte die
   gefilterte Themenseiten-Suche leer (141 Zeichen), woraufhin der globale
   Fallback startete und **18,9 s** brauchte. Serielle Abhängigkeit by design
   (Fallback nur bei leerem Ergebnis), ALT-identisch. Nicht im Chatbot lösbar —
   nur deckelbar. **Produkt-/Betriebs-Entscheidung, nicht gebaut.**
2. **Der Themenseiten-Pfad (M16) hat ein Fenster von 8,95 s ohne jede
   Rückmeldung** — die Phasen enden bei `pattern`, `response` entfällt (M16
   überspringt `generate_response`). Das ist genau der Schritt `topic_content`,
   den C9 bewusst offen ließ. **Die Messung widerlegt meine damalige Einschätzung
   („nur M16, erst nach der Antwort"):** es sind neun Sekunden, in denen das
   Widget ein veraltetes Label zeigt. Empfehlung: nachziehen.

### MCP-Fix verifiziert 2026-07-27 (abends) — die Latenz ist weg

Der MCP-Entwickler hat auf unseren Befund hin gefixt; Testinstanz
`https://wlo-mcp.87.106.195.152.nip.io/mcp` (statt `wlo-mcp-server.vercel.app`,
also vermutlich persistent statt serverless). Dieselben Fälle, derselbe
Client-Pfad (`call_mcp_tool`), gemessen:

| `search_wlo_topic_pages` | vorher | nachher |
|---|---|---|
| ohne query, `maxResults=20` | 19,42 s | **2,45 s** |
| ohne query, `maxResults=10` | 8,52 s | 1,97 s |
| ohne query, `maxResults=5` | 8,20 s | 1,45 s |
| `educationalContext`, `maxResults=20` | 3,39 s | 1,39 s |
| mit query | 2,17 s | 2,17 s |

Auch die `Math.max(50, …)`-Untergrenze ist weg: 5/10/20 skalieren jetzt sinnvoll.

**Ende-zu-Ende (dieselben fünf Züge wie beim Messlauf am Nachmittag):**

| Zug | vorher | nachher |
|---|---|---|
| Material-Suche | 28,78 s | **4,72 s** |
| Themenseite | 10,88 s | **3,92 s** |
| Folgefrage | 12,89 s | 5,34 s |
| Gruß | 10,67 s | 7,34 s |
| Wissensfrage | 7,67 s | 7,78 s |

`wlo_search`- und `response`-Abschnitte stehen bei **0,00 s** — der Prefetch ist
fertig, bevor der Graph dort ankommt. Die verbleibende Zeit ist LLM-gebunden
(Klassifikation ~2 s + Antwort-LLM ~2,5–5,4 s), also der erwartete Boden.

**Inhaltlich unverändert intakt:** `select_top_cards: 3 IDs picked` in den Logs,
Karten kommen an. **Kein Tool verschwunden** — alle 12, die wir kennen, gibt es
weiter.

**Zwei Dinge, die der Fix NICHT betrifft** (beide auch vorher schon so):

1. `parse_wlo_cards: JSON did not match v2 envelope shape` bei
   `search_wlo_topic_pages` — der Docstring in `mcp/parsers.py:96` behauptet, die
   Funktion parse genau dieses Tool. Der Chat funktioniert trotzdem, weil
   `services/topic_pages.py` die Antwort mit eigenem `json.loads` verarbeitet.
   Also entweder toter Anspruch im Docstring oder eine ungenutzte Fähigkeit —
   ungeklärt, eigener Faden.
2. `get_topic_page_content` liefert für die Themenseite „Nachhaltigkeit" weiter
   86 Zeichen (= leer) → `M16: keine Inhalte -> Fallback-Text gesetzt`. Sieht
   nach einem Daten-Thema aus, nicht nach Latenz.

**Neu: der Server bietet jetzt 22 Tools, wir kennen 12.** Nicht genutzt werden
`fetch`, `search`, `find_wlo_skills`, `get_collection_stats`,
`get_compendium_text`, `get_node_breadcrumb`, `get_related_content`,
`get_wikipedia_summary`, `lookup_wlo_publishers`, `search_wlo_within_collection`.
Anpassung an die weiterentwickelten Tools ist als eigenes Paket vorgemerkt
(Nutzer-Hinweis 2026-07-27).

**Folge für unseren offenen Punkt:** der `educationalContext`-Fix in
`topic_pages.py` bringt jetzt nur noch ~1 s statt 16 s. Er bleibt trotzdem
richtig (`discipline` existiert bei dem Tool nicht), ist aber keine
Performance-Frage mehr, sondern eine Korrektheits-/Relevanz-Frage.

### W2 ✅ 2026-07-30 — MCP-Client-Anpassung nach dem Server-Fix

Drei Stücke, alle test-first, alle gegen den laufenden Server nachgemessen.

**W2-1 — `parse_total_count` las eine Zahl, die nie da war.** Die Funktion ist
eine Regex-Kette über *Prosa*. Ihr einziger Aufrufer
(`direct_actions._handle_browse_collection`, Z. 115) fragt
`get_collection_contents` — ein Tool aus `_JSON_CAPABLE_TOOLS`, das also **immer**
den JSON-Envelope liefert. Gegen `{"total": 42, …}` matcht keine der drei Regexen
(zwischen Schlüssel und Doppelpunkt steht ein `"`). Belegt:

```
parse_total_count('{"total": 42, "count": 5, "results": […]}')  ->  0
```

Schlimmer als „liefert 0": auf einem Envelope, dessen Karten-Beschreibungen
Ziffern enthalten, griff die zweite Stufe und lieferte **die falsche Zahl**
(Test: `description: "Gesamt: 999 Übungen"` → 999 statt 7). Sichtbar wurde das im
Pager-Text `„**Titel** — Ergebnisse 1–5 von N"`: N fiel auf `skip_count +
len(cards)` zurück. Live gegen die Sammlung „Mathematik": Server meldet **15**
Inhalte, ausgeliefert werden 6 → ALT zeigte „von 6", jetzt „von 15".

Fix: JSON zuerst (`total`), Regex bleibt Fallback für Markdown-Server. Ein
JSON-Objekt **ohne** `total` liefert 0 statt durchzufallen — der Envelope ist
maßgeblich, Ziffern darin sind Kartentext, nie der Zähler.

**W2-2 — `discipline` raus, `educationalContext` durch.** Der Global-Fallback in
`_topic_pages_with_warmup` reichte `discipline` weiter (kennt das Tool-Schema
nicht → stumm verworfen) und warf `educationalContext` weg (der einzige Filter,
den das Tool dort auswertet). `maxResults` bleibt bewusst bei **20**: der
Fallback existiert, um eine Themenseite zu finden, die der Server-Matcher
übersehen hat, und der anschließende Titel-Filter lebt von der Fensterbreite. Der
Wert ist als Test gepinnt, damit die Entscheidung nicht später versehentlich
kippt.

**W2-3 — der M16-Resolver probiert nicht mehr blind drei Kandidaten.** Der Server
begründet den Leerfall seit dem Fix selbst; `parse_topic_page_swimlanes` reicht
das Feld jetzt als `reason` durch. Live gemessen (2026-07-30): **12 von 12**
Sammlungen ohne `topic_page_url` antworten `no_page_config_ref`, je ~1,0–1,5 s.
Deshalb: markierte Kandidaten zuerst, und trägt **keiner** den Marker, bleibt der
bestplatzierte als Rückfall-Netz — so verlieren wir keine Themenseite, wenn der
Server den Marker mal nicht mitliefert (kommt vor, s. u.).

A/B gegen das ALT-Verhalten auf **identischen** Kandidatenlisten, 9 Läufe:

| | ALT | NEU |
|---|---|---|
| Läufe mit Treffer | 3 | 3 |
| Probe-Calls gesamt | 21 | **9** |
| Ergebnis-Abweichungen | — | **0** |

Der Fallback-Text richtet sich nach den gemeldeten Gründen: melden *alle*
`no_page_config_ref`/`node_not_found`, sagt er „Zu »X« habe ich keine Themenseite
gefunden" statt ALTs „sie ist eventuell noch leer" — Letzteres behauptet, die
Themenseite existiere, und spekuliert über ihren Zustand. `no_variant`/
`empty_config` (Themenseite da, aber leer) und unbekannte Gründe behalten den
vorsichtigen ALT-Wortlaut; `no_match` bleibt bewusst draußen, weil seine
Bedeutung nicht dokumentiert ist.

**Nebenbefund aus der Live-Abnahme — eigener Punkt, nicht in W2 gebaut:** die
M16-Kandidatenquelle ist unzuverlässig. Dieselbe Abfrage
`search_wlo_collections(query, maxResults=8)` liefert von Lauf zu Lauf andere
Ergebnisse; die gesuchte Themenseite war in **6 von 9** Läufen gar nicht dabei
oder kam ohne `topic_page_url`. Die dedizierte `search_wlo_topic_pages` fand sie
im selben Zeitraum **6 von 6** Mal. Das erklärt Beobachtungen wie „Themenseite
Chemie existiert (7 Schwimmlinien), Resolver findet sie trotzdem nicht". Betrifft
ALT genauso (0 Abweichungen oben) — also kein Regress, aber der lohnendste
nächste Griff am Themenseiten-Pfad.

Verifikation: Backend **2179 pytest** (+12), 2 skipped (beide umgebungsbedingt:
ALT-Backend/Jaeger nicht gestartet), ruff sauber, `export_openapi.py --check`
unverändert.

### W3 ✅ 2026-07-30 — M16 fragt die Themenseiten-Suche, nicht die Sammlungs-Suche

Der Nebenbefund aus der W2-Abnahme, jetzt gebaut. `_resolve_m16_topic_page_view`
holte seine Kandidaten aus `search_wlo_collections(query, maxResults=8)`. Drei
Quellen gegeneinander gemessen, **7 Themen, je eigener Prozess** (kein geteilter
Tool-Cache — im ersten Anlauf lief C nach B im selben Prozess und war scheinbar
3× schneller; das waren Cache-Treffer, nicht Leistung):

| Quelle | Treffer | Median |
|---|---|---|
| A `search_wlo_collections` (ALT) | 3/7 | 2,78 s |
| B `search_wlo_topic_pages` | **7/7** | 3,76 s |
| C B + `_topic_pages_with_warmup` | 7/7 | 5,26 s |

**A ist nicht nur unzuverlässig, sondern kann falsch antworten:** bei „Chemie"
lieferte sie „Lebensmittelchemie" (6 Schwimmlinien) — der Nutzer bekäme die
falsche Themenseite als Antwort auf seine Frage. Also 2 von 7 korrekt, nicht 3.

**Gewählt: B, ohne den Warmup-Helfer.** Beide in dessen Docstring beschriebenen
Server-Haken sind auf dem gefixten Server nicht mehr beobachtbar: der enge
Query-Matcher am dort namentlich genannten Fall „Mathematik" greift nicht mehr,
und die Warmup-Bedingung (leerer Themenseiten-Index ohne vorherige
Sammlungs-Suche) ist genau die Lage im frischen Prozess — dort trifft B 7/7. C
kostete 1,5 s Median ohne Gegenwert. `_topic_pages_with_warmup` bleibt
unangetastet, der Prefetch-Pfad nutzt ihn weiter.

**Der W2-3-Marker-Filter ist entfallen** — samt seiner zwei Tests. Nicht um die
Suite grün zu halten: `parse_wlo_topic_page_cards` setzt `topic_page_url` immer
(sonst die Render-URL), live gegengeprüft mit **0 von 7** Karten ohne Marker. Die
Bedingung war unerreichbar geworden, und ihr Kommentar („Sammlungen ohne
Marker …, 12/12 gemessen") beschrieb eine Quelle, die diesen Code nicht mehr
speist. Die `reason`-Auswertung und der Drei-Versuche-Deckel bleiben.

**Live-Abnahme mit dem echten Resolver** (frischer Prozess, 7 Themen):
**7/7 Treffer**, je genau zwei MCP-Calls (`search_wlo_topic_pages` +
`get_topic_page_content`), Median 4,03 s. Der Seitenkontext-Kurzschluss bleibt
unangetastet: ein einziger `get_topic_page_content`, keine Suche.

**Eine Zahl, die stutzig machte und geklärt ist:** der Resolver meldet 1–2
Schwimmlinien, die Quell-Probe 7–8. Kein Verlust bei uns — der Server liefert für
„Chemie" sieben Abschnitte, von denen **fünf serverseitig leer sind** (`items: []`);
die beiden befüllten (3 und 1 Eintrag) werden vollständig zu Karten. Beobachtung
für den MCP-Entwickler, kein Client-Fehler.

Verifikation: Backend **2178 pytest** (+1 neu, −2 entfallen), 2 skipped
(umgebungsbedingt), ruff sauber, `export_openapi.py --check` unverändert.

### W4-1 ✅ 2026-07-30 — der Abgleich Client↔Server, und zwei Sachfehler daraus

Bisher war „unsere Tool-Liste ist veraltet" eine Vermutung. Jetzt liegt der
Abgleich vor (`tools/list` gegen `TOOL_DEFINITIONS`, Namen + Parameter +
Pflichtfelder + Beschreibungen):

| Befund | Wert |
|---|---|
| Tools auf dem Server | **23** (nicht 22, wie hier zuvor notiert) |
| davon in unserer LLM-Liste | 12 |
| Tools, die wir deklarieren und die es nicht gibt | **0** |
| Pflichtfelder, die wir übersehen | **0** |
| gemeinsame Tools mit abweichender Beschreibung | **12 von 12** |

**Zwei Sachfehler gefixt** — beide in dem, was das Modell über die Tools erfährt:

1. **`search_wlo_collections` bot `userRole` an, das Server-Schema kennt ihn dort
   nicht** (bei `search_wlo_content` schon — dort bleibt er). Dieselbe Klasse wie
   `discipline` in W2-2. Der Nachweis brauchte eine Kontrollmessung: mit und ohne
   Parameter kamen *unterschiedliche* Antworten, was zunächst nach Wirkung aussah
   — derselbe Aufruf **ohne** den Parameter liefert aber dreimal verschiedene
   Längen (5257/5138/4994), und die „mit"-Längen stammen aus derselben Menge. Es
   war die schon in W3 gemessene Instabilität dieser Suche, nicht der Parameter.
2. **Die Beschreibung setzte „Sammlungen (= Themenseiten)" gleich.** W3 hat das
   Gegenteil gemessen: nur ein kleiner Teil der Sammlungen trägt eine
   Seitenkonfiguration, und dafür gibt es ein eigenes Tool. Die Gleichsetzung
   schickte das Modell mit der Themenseiten-Frage in die Sammlungs-Suche — genau
   der Pfad, der 3/7 traf statt 7/7. Neue Beschreibung nennt die Abgrenzung und
   verweist auf `search_wlo_topic_pages`.

Das Validierungsmodell `SearchWloArgs` bleibt unangetastet (es ist mit
`search_wlo_content` geteilt, dort ist `userRole` echt), und in
`_resolve_filter_uris` war nichts zu tun: die Auflösung ist schlüssel-, nicht
toolgetrieben — kommt der Schlüssel nicht mehr an, überspringt die Schleife ihn.

Verifikation: Backend **2181 pytest** (+3), ruff sauber, `export_openapi.py
--check` unverändert.

**Bewusst NICHT gebaut, weil es Entscheidungen braucht (bleibt als W4-Rest):**

* **Die 11 ungenutzten Server-Tools** — welche der Bot bekommen soll, ist eine
  Produktentscheidung, und jedes braucht Argument-Validierung, ggf. einen Parser
  und Prompt-Führung. Auffällig darunter: `get_related_content` („mehr wie
  dieses"), `search_wlo_within_collection` (passt zur Sammlungs-Aktion),
  `get_wlo_content_text`/`get_compendium_text` (Volltexte, berühren RAG) — und
  `get_wikipedia_summary`, das sich mit unserem eigenen
  `services/wikipedia_service.py` überschneidet.
* **Die 12 gedrifteten Beschreibungen** — sie 1:1 zu übernehmen wäre ein
  Rückschritt: unsere tragen boerdi-eigene Führung („Mappe Klassenangaben IMMER
  auf eine Bildungsstufe", „PFLICHT wenn der Nutzer einen Inhaltstyp nennt"), die
  der Server nicht kennt. Das ist ein Zusammenführen je Tool, kein Kopieren.
* **Ein Drift-Wächter**, der diesen Abgleich automatisch fährt (Vorbild
  `export_openapi.py --check`), bräuchte Netz in der CI — eigene Entscheidung.

### W5-1 ✅ 2026-07-30 — M16 auf den Ein-Call-Pfad des neuen MCP

Der Nutzer hat den Quellbaum des neuen Servers bereitgestellt
(`../wlo-mcp-server-sc`, **nur Referenz, nie ändern**). Zwei Dinge daraus, die
sofort greifen — beide am Schema und live geprüft, nicht aus der Doku geglaubt:

**`get_topic_page_content` nimmt jetzt `query`.** Das Tool-Schema sagt es
wörtlich: „Resolves the best matching Themenseite internally and renders its
swimlanes in ONE call — no prior search_wlo_topic_pages needed." Damit entfallen
die vorgeschaltete Suche aus W3 **und** die Kandidaten-Rangfolge samt
Drei-Versuche-Schleife: wir hatten nachgebaut, was der Server inzwischen selbst
tut. Live: **7/7 Treffer, ein MCP-Call je Zug, Median 3,23 s statt 4,03 s.** Der
Seitenkontext-Kurzschluss bleibt und geht weiter als `collectionId` rein — eine
bekannte ID ist genauer als jede Themen-Auflösung.

**Der Titel stand im falschen Feld.** Der Server liefert `collectionTitle`
(lesbar) *und* `variantTitle` (technisch); unser Parser las `variantTitle`, das
bei **jeder** Fachportal-Themenseite „Fachportalstartseite" lautet — live bei
Mathematik, Chemie und Nachhaltigkeit gleichlautend bestätigt. Bisher verdeckte
das der Kandidaten-Titel aus der Vorsuche; auf dem Ein-Call-Pfad hätte in der
Antwort „Themenseite »Fachportalstartseite«" gestanden. Beide Änderungen mussten
deshalb zusammen kommen.

Vier Tests, die den entfallenen Such-Pfad pinnten, wurden **umgehängt statt
gelöscht** — ihre Absicht (kein Seitenkontext-Kurzschluss ⇒ Thema als `query`;
keine unzuverlässige Quelle) ist erhalten, der W3-Wächter jetzt als „gar keine
Suche". `topic_pages.py` schrumpft 365 → **333 Zeilen**.

Verifikation: Backend **2185 pytest**, ruff sauber, `export_openapi.py --check`
unverändert.

**W5-Rest — was der neue Server sonst noch bringt (Messung liegt vor, Bau
offen).** Der Server hat **23 Tools und 4 Widgets**; wir nutzen 12 Tools. Die
Widgets sind für uns **nicht** relevant: sie brauchen die ChatGPT-Erweiterung
`window.openai.sendFollowUpMessage`, auf anderen Hosts erscheinen die Buttons
laut Server-Doku bewusst gar nicht — unser Widget rendert ohnehin selbst. Was
inhaltlich lohnt und je eine eigene Entscheidung ist: `get_wlo_content_text`
(Volltext eines Materials — berührt RAG und die Inline-Dokumente),
`get_related_content` („was passt noch dazu"), `search_wlo_within_collection`
(passt zur Sammlungs-Aktion), `get_collection_stats`/`get_node_breadcrumb`
(Einordnung). Dazu unverändert der W4-Rest (Beschreibungen zusammenführen,
Drift-Wächter). **Der Server-Baum enthält außerdem `docs/systemprompt_boerdi
v2.md`** — ein für uns geschriebener Systemprompt-Vorschlag; ob und wie er in
unsere Pattern-/Prompt-Config einfließt, ist eine redaktionelle Entscheidung,
keine technische.

### W8 ✅ 2026-08-01 — Wikipedia-Eigenabruf gegen das MCP-Werkzeug getauscht

**Auftrag (Nutzer):** den internen Wikipedia-Abruf entfernen und das
gleichwertige MCP-Werkzeug nutzen — Begründung: externe Dienste soll pflegen,
wer sie ohnehin unterhält.

**Gebaut.** `services/wikipedia_service.py` sprach über zwei MediaWiki-REST-
Endpunkte (Titelsuche → Summary) mit eigenem User-Agent, eigenem Timeout und
eigener Weiterleitungs-Behandlung. Diese Hälfte ist ersetzt durch einen Aufruf
von `get_wikipedia_summary`; `outputFormat="json"` setzt zentral
`_JSON_CAPABLE_TOOLS` (wie bei `get_wlo_content_text`), gelesen wird der
Envelope von `parse_wikipedia_summary` in `mcp/parsers.py`. Netto ~55 Zeilen
Fremd-API-Anbindung weg.

**Der Relevanz-Filter bleibt — die Messung hat meine eigene Empfehlung
gekippt.** Ich hatte dem Nutzer geschrieben, der Filter könne auf einen kurzen
Rest schrumpfen. Live gegen den Server (2026-08-01) beantwortet das Werkzeug
aber `Stadt Berlin` mit **Bern** und `Dreiecke` mit **Dreiecker** (einem Berg).
Der Server löst Weiterleitungen sauber auf (`Bruchrechnen` → *Bruchrechnung*),
prüft aber keine Themen-Zugehörigkeit. Ohne `_is_relevant` landete die falsche
Sache samt CC-BY-SA-Quellenangabe im Unterrichtsmaterial. Die Heuristik ist
deshalb unverändert die ALT-Fassung geblieben.

**Zwei Zahlen richtiggestellt**, die ich vorher zu günstig genannt hatte:

| | alt (eigener Abruf) | neu (über MCP) |
|---|---|---|
| Lead-Absatz „Photosynthese" | 354 Zeichen | **354 Zeichen** (identisch) |
| Ende-zu-Ende-Dauer | ~570 ms | **~850 ms** |

Die früher genannten 0,16 s waren ein roher `curl`, verglichen mit unserem
*ganzen* Dienst — kein fairer Vergleich. Der SDK-Handschlag pro Aufruf kostet
~280 ms. Im Material-Pfad, der ohnehin Sekunden LLM-Zeit braucht, vertretbar;
ein Geschwindigkeitsgewinn ist es aber nicht.

**Weggefallen:** das Feld `description` (Wikidata-Untertitel) — der MCP führt es
nicht, und `canvas_service` las es nie. Ebenso der Parameter `timeout_s`, der
ohne eigenen HTTP-Client nichts mehr steuerte.

**Belege:** Backend 2243 grün · ruff sauber (die E501-Ausnahme für
`wikipedia_service.py` ist entfallen, die Begründung „byte-genaue ALT-Kopie"
trägt für die neu geschriebene Hälfte nicht mehr) · Live-Smoke: Photosynthese
trifft, `Stadt Berlin` und `Bruchrechnen` werden verworfen.

**Bekannte Grenze (unverändert, nicht gefixt):** der Filter ist an den Rändern
zu streng — `Bruchrechnen` → *Bruchrechnung* verwirft er, obwohl der Artikel
passt. Ursache ist Regel 3 (Prefix-Vergleich); dieselbe Regel 1 lässt umgekehrt
`Dreiecke` → *Dreiecker* durch, weil direkte Enthaltenheit vor der Suffix-
Prüfung greift (die Testdatei charakterisiert das seit dem Port). Beides zu
verbessern ist ein eigener Schritt mit eigener Absicherung.

**Folge-Entscheidung für den W4-Rest:** `get_wikipedia_summary` ist damit
belegt — deterministisch aus `canvas_service`. Bietet man es *zusätzlich* dem
Antwort-LLM an, gibt es zwei Wege zur selben Auskunft; das braucht dann eine
ausdrückliche Regel, welcher gewinnt.

### W9a ✅ 2026-08-01 — vier Einordnungs-Werkzeuge, und ein struktureller Fund

**Gebaut:** `get_collection_stats`, `get_node_breadcrumb`, `get_compendium_text`,
`lookup_wlo_publishers` — Schemata per `tools/list` VOM SERVER geholt, je ein
Pydantic-Argumentmodell, Beschreibungen = Server-Text plus boerdi-Führung
(wann NICHT, und welches Werkzeug stattdessen — das weiß der Server nicht).

**Bewusst nicht auf JSON gestellt.** `_JSON_CAPABLE_TOOLS` lohnt nur, wo wir
selbst parsen; diese vier liest das Modell direkt, und Markdown ist dafür
kürzer und lesbarer.

**Der eigentliche Fund: eine Ergänzung in `TOOL_DEFINITIONS` allein ist IMMER
wirkungslos.** Gemessen 2026-08-01: alle acht MCP-nutzenden Muster führen eine
eigene `tools:`-Liste, **kein einziges** nutzt `sources: [mcp]` ohne sie. Der
Zweig in `_select_active_tools`, der den ganzen Katalog anbietet
(`response_tool_selection.py:86`), wird also nie betreten. Dieselbe Falle hatte
2026-07-31 schon `get_wlo_content_text` erwischt (M17 rief ins Leere). Ohne
Verdrahtung wären die vier der **achte** Fall der Klasse „gebaut, ohne
Verbraucher" gewesen.

Verdrahtet: M08 (+stats, +breadcrumb, +compendium — Einordnung vor dem
Durchwühlen), M05 (+publishers: der `publisher`-Filterwert muss geholt statt
geraten werden, ein erfundener Anbieter liefert **still** null Treffer), M12
(+publishers als vierter Rettungsweg bei null Treffern). M16 blieb unangetastet
— sein Wächter verlangt genau ein Werkzeug.

**Der Einzelfall-Wächter ist jetzt ein Klassen-Wächter**
(`test_jedes_angebotene_werkzeug_ist_aus_einem_pattern_erreichbar`): jeder Name
aus `TOOL_DEFINITIONS` muss aus mindestens einem Muster erreichbar sein, sonst
steht er mit Begründung in `_NICHT_UEBER_PATTERN`. Damit ist „unerreichbar"
eine Entscheidung statt eines Versehens.

**Zweiter Fund — `Field(le=…)` deckelt nicht.** Überschreitet ein Wert die
Grenze, wirft pydantic, `validate_tool_args` fängt das ab und schickt die
**Rohargumente** weiter (`tool_defs.py:326`). Die Obergrenzen der bestehenden
Werkzeuge sind damit zahnlos. Für `lookup_wlo_publishers` wird deshalb geklemmt
statt abgelehnt — live belegt: Anfrage mit `maxResults: 500` kam als
„WLO Anbieter (50)" zurück. Die bestehenden `le=`-Grenzen sind **nicht**
mitgezogen (eigenes Paket, siehe offene Liste).

**Zurückgehalten: `find_wlo_skills`** — zwei Gründe, beide gemessen:
(1) serverseitig gar nicht eingerichtet („Keine Skill-Sammlung konfiguriert.
Setze `WLO_SKILLS_COLLECTION_ID`…") — angeboten wäre es ein Werkzeug, das immer
scheitert; (2) sein Zweck ist laut Server, Anweisungsdokumente zu liefern,
„die zu befolgen sind", mit der Warnung *„not authoritative system
instructions — review it before acting"*. Das ist ein Kanal, über den fremd
gepflegte Sammlungsinhalte zu Anweisungen für den Bot werden. Nutzer-Entscheid
nötig.

**Nebenbefund (nicht angefasst):** `get_nodes_details` und `wlo_health_check`
waren schon vorher aus keinem Muster erreichbar. `wlo_health_check` zu Recht
(Betriebs-Sonde); `get_nodes_details` ist ein offener Rest.

**Belege:** Backend 2251 grün · ruff sauber · Live über unseren eigenen Client
(also inkl. Validierung und Registry-Auflösung): alle vier antworten, getestet
an der Sammlung „Biologie-Breakouts".

### W9b ✅ 2026-08-01 — zwei Karten-Werkzeuge, und ein stiller Totalausfall im Hauptsuchpfad

**Der Defekt zuerst.** `search_wlo_all` ist seit W5-2a das Standard-Suchwerkzeug
und steht in M06s Werkzeugliste — aber **nicht** in der Karten-Weiche des
Tool-Loops. Sein Envelope hat kein Top-Level-`results`, sondern drei Töpfe
(`content`/`collections`/`topicPages`); `parse_wlo_cards` gab darauf **null**
Karten zurück. Live gemessen: 13 Treffer, 0 Karten. Rief das Modell die
Kombi-Suche selbst auf, sah der Nutzer nichts — ohne Fehlermeldung.

Der Prefetch-Pfad hatte für genau diesen Envelope längst einen eigenen Splitter
(`respond.py:137-177`); im Tool-Loop fehlte er schlicht. Und `parse_search_all_cards`
lag seit dem Port in `parsers.py` **ohne einen einzigen Aufrufer** — der neunte
Fall der Klasse „gebaut, dokumentiert, getestet, nie gerufen". Er ist jetzt der
Verbraucher: 14 Karten statt 0, live geprüft.

**`CARD_YIELDING_TOOLS` steht jetzt auf Modulebene.** Vorher wurde die Menge bei
JEDEM Tool-Aufruf neu gebaut und war von außen nicht prüfbar — genau deshalb fiel
die Lücke nie auf. Ein Werkzeug, das dort fehlt, scheitert nicht, es liefert
stillschweigend nichts.

**Gebaut:** `search_wlo_within_collection` (M08) und `get_related_content` (M06)
— je Argumentmodell, Werkzeug-Definition, `_JSON_CAPABLE_TOOLS` (anders als die
W9a-Vier parsen wir diese Antworten), `CARD_YIELDING_TOOLS` und Muster-Eintrag.

**Envelope-Heuristik korrigiert.** `_cards_from_json_envelope` verlangte `total`
oder `count`. `get_related_content` antwortet mit
`{seedNodeId, seedTitle, disciplines, educationalContexts, results}` und keinem
Zähler — die Regel warf drei einwandfreie Karten weg. Jetzt entscheidet der
Eintrag mit `nodeId`; nur der Leerfall braucht noch einen Kopf, sonst ginge
irgendein `{"results": []}` als „null Karten" statt als „kein Envelope" durch.
Der Bestandstest, der die alte Regel festhielt, wurde **umgeschrieben statt
gelöscht**, mit der Messung als Begründung.

**Ein Irrweg, den ein Bestandstest gestoppt hat — festhalten, er ist lehrreich.**
Ich hatte den `topicPages`-Topf durch den dedizierten Themenseiten-Parser
geleitet, weil dessen Einträge `collectionId`+`variants` tragen. Der
Bestandstest brach. Die Messung gab ihm recht: der `topicPages`-Topf von
`search_wlo_all` ist eine **gewöhnliche FormattedNode-Liste** (`nodeId` +
`topicPageUrl`) — nur `search_wlo_topic_pages` liefert die Varianten-Form. Zwei
Werkzeuge, zwei Antwortformen. Meine Attrappe war nach dem Code gebaut, die des
Bestandstests nach der Wirklichkeit; dieselbe Falle wie bei den
LiteLLM-Antwortformen im P11-Probelauf.

**Belege:** Backend 2261 grün · ruff sauber · live: `search_wlo_all` 14 Karten
(vorher 0), `get_related_content` 3 Karten, `search_wlo_within_collection` 5
Karten in „Biologie-Breakouts" (ohne `query`; die vorher gemessenen Nullen waren
leere Sammlungen, kein Codefehler).

**Offen bleibt W9c:** die 13 bestehenden Beschreibungen mit den Server-Texten
zusammenführen (W4-1 hatte gemessen: alle gedriftet).

### W9c ✅ 2026-08-01 — Beschreibungen zusammengeführt, drei Fähigkeiten geprüft

**Vorbehalt vorweg:** das sind Prompt-Texte fürs Modell, keine Logik. Tests
prüfen Struktur, nicht Wirkung — der Nachweis wäre ein Golden-Lauf (Nutzer-
Domäne). Deshalb streng additiv gearbeitet: Server-Fakten ergänzt, die
boerdi-eigene Führung nirgends angetastet.

**Neun Beschreibungen ergänzt** um Fakten, die uns fehlten. Die wichtigsten:

* `browse_collection_tree` — **`hasMoreChildren` heißt „hier steht nicht
  alles"**. Der Server verlangt ausdrücklich, das dem Nutzer zu sagen statt die
  Auswahl als vollständig auszugeben. Eine Wahrhaftigkeitsregel, die im Text
  komplett fehlte; ein Test pinnt sie jetzt.
* `search_wlo_all` — **nur `content.total` ist eine echte Trefferzahl**;
  `collections.total`/`topicPages.total` sind bloß die Anzahl der angezeigten
  Einträge. Ohne den Hinweis nennt der Bot dem Nutzer Zahlen, die es nicht gibt.
* `get_node_details` — stand bei **54 Zeichen** gegen 973 beim Server. Jetzt mit
  Feldliste, Tempo (~0,3 s) und der Abgrenzung zu `get_wlo_content_text` (1-3 s).
* `get_collection_contents` — die `contentFilter`-Semantik (files/folders/both)
  und die Rekursion von `includeSubcollections` fehlten dem Modell ganz.
* `get_nodes_details` — eine fehlschlagende nodeId kippt den Stapel nicht, sie
  kommt in einer `failed`-Liste.

**Drei zusammengelegte Fähigkeiten geprüft, zwei übernommen:**

| Fähigkeit | Messung | Ergebnis |
|---|---|---|
| `browse_collection_tree(subject="Mathematik")` | 11 Unterthemen | übernommen — spart den `get_subject_portals`-Vorlauf |
| `get_topic_page_content(query="Mathematik")` | 8 Schwimmlinien in EINEM Aufruf | übernommen — unser Text verlangte vorher „erst search_wlo_topic_pages" |
| `get_node_details(includeParents=true)` | `parents` **immer leer**, auch bei zwei Materialien, die nachweislich in „Biologie-Breakouts" liegen | **nicht** übernommen |

Der letzte Fall ist der interessante: der Server *dokumentiert* die Fähigkeit
(„useful to find which Sammlung a content item is in"), erfüllt sie aber nicht.
Angeboten hätte das Modell dem Nutzer „liegt in keiner Sammlung" geantwortet —
eine falsche Auskunft ist schlimmer als eine fehlende. `includeTextContent`
dagegen liefert nachweislich Text (2444 / 4011 Zeichen) und ist drin.

**Ein Server-Satz bewusst NICHT übernommen.** `search_wlo_collections` behauptet
serverseitig: „In WLO ist eine Sammlung dasselbe wie eine Themenseite." Unser
Text sagt seit W4-1 das Gegenteil — und der Server widerspricht sich selbst
(`search_wlo_topic_pages`: „sucht Sammlungen und prüft dann, WELCHE davon eine
Themenseite haben"). Gemessen: 5 Sammlungen zu 1 Themenseite bei „Mathematik".
Unsere Korrektur bleibt; ein blinder Merge hätte sie zurückgedreht.

**Neuer Wächter:** `test_every_offered_parameter_is_accepted_by_its_argument_model`
— ein angebotener Parameter, den das Pydantic-Modell nicht kennt, fällt beim
`model_dump` **still** heraus: das Modell füllt ihn aus, der Server sieht ihn
nie. Diese Richtung ist jetzt lückenlos abgesichert (aktuell 0 Verstöße).

**Belege:** Backend 2269 grün · ruff sauber · die drei Fähigkeiten live gegen
den Server geprüft (siehe Tabelle). Die Textänderungen selbst sind NICHT
verhaltensgeprüft — dafür braucht es den Golden-Lauf.

**Nebenbefund, korrigiert:** ich hatte U+FFFD-Ersatzzeichen in den
Beschreibungen vermutet — falsch, die Datei ist sauberes UTF-8, das `�` war die
Darstellung meines Terminals. Ursache der zunächst fehlgeschlagenen
Ersetzungen: ich hatte Suchtexte aus der Terminal-Ausgabe kopiert, samt der dort
dargestellten Ersatzzeichen.

## W10 — Obergrenzen, die nur dastanden (+ `get_nodes_details` entschieden) ✅ 2026-08-01

Zwei Reste aus W9, beide von derselben Sorte: ein Wächter, der nicht wacht.

**A — `Field(le=…)` deckelte nichts.** `validate_tool_args` fängt die
`ValidationError` ab und reicht dann die **rohen** Argumente weiter. Jede Grenze
auf jedem Bestands-Werkzeug war damit Dekoration: ein Modell, das
`maxResults: 100` gegen `le=20` anfordert, bekam die 100 zum Server
durchgereicht — genau der Fall, für den die Grenze existiert. Aufgefallen war
das in W9a nur punktuell, deshalb trugen `lookup_wlo_publishers`,
`search_wlo_within_collection` und `get_related_content` je einen
**handgeschriebenen** Klemm-Validator; die dreizehn älteren Werkzeuge hatten
nichts.

Gefixt an der Wurzel statt zehnmal per Hand: `_clamp_bound_violations` liest die
verletzte Grenze aus dem pydantic-Fehler (`ctx: {"le": 20}`), setzt das Feld
darauf und validiert einmal nach. Die drei Hand-Klemmen sind dadurch überflüssig
und **entfernt** — die Grenzen stehen jetzt überall deklarativ am Feld
(`schemas_mcp.py` 259 → 234 Zeilen).

Zwei Messbefunde, die den Entwurf entschieden haben:
* Beim Alias-Pfad (`maxItems: 100`) meldet pydantic den **kanonischen** Namen
  (`loc: maxResults`), weil der Pre-Validator vorher gelaufen ist. Die Reparatur
  trifft ihn deshalb; der Alt-Name bleibt im Dict stehen und wird ignoriert.
* Bewusst nur `ge`/`le` — `gt`/`lt` kommt in keinem Argument-Modell vor. Für
  eine dort erfundene Grenze wäre der bisherige Fail-Open-Pfad ehrlicher.

Nicht reparierbare Fehler (fehlendes Pflichtfeld, `maxResults: "viele"`) fallen
weiter auf die Rohargumente zurück — unverändert. **Eine bewusste Verhaltens-
änderung:** ein gebrochener Wert (`maxResults: 20.5`) wurde auf den drei
W9-Werkzeugen bisher per `int()` auf 20 gerundet und fällt jetzt wie überall
sonst auf die Rohargumente zurück. Einheitlich statt drei Sonderfälle.

**C — `get_nodes_details` bleibt draußen, jetzt mit Grund.** Es stammt aus ALT
und war dort ebenso in keinem Muster. Gemessen: der Prompt-Block
`render_tools_block` nennt es zwar namentlich, ist aber **statisch** — er zählt
alle zehn MCP-Werkzeuge auf, unabhängig von der aktiven Tool-Liste des Musters,
und trifft `wlo_health_check` genauso. Damit ist es kein Sonderfall, sondern
dieselbe Kategorie. Ein Muster nur zu verdrahten, damit der Wächter schweigt,
hieße einen Verbraucher zu erfinden: die Karten-Pipeline holt ihre Metadaten aus
den Suchtreffern selbst. Der Eintrag in `_NICHT_UEBER_PATTERN` trägt jetzt diese
Begründung statt „offener Rest".

**Neuer Wächter:** `test_der_werkzeug_prompt_nennt_nur_werkzeuge_die_es_wirklich_gibt`
— die umgekehrte Richtung. Wird ein Werkzeug umbenannt oder entfernt, verspricht
der statische Prompt dem Modell etwas, das der Katalog nicht mehr kennt.

**Belege:** 8 neue Tests, 4 davon zuerst rot (genau die Bestands-Grenzen) ·
`uv run pytest -q` → **2277 passed, 4 skipped** (vorher 2269) · `ruff check src
tests` → All checks passed · `scripts/export_openapi.py --check` → openapi
contract unchanged. Nicht abgedeckt: ein Live-Zug, der die Klemmung im Betrieb
auslöst — dafür müsste das Modell eine Grenze überschreiten, was sich nicht
erzwingen lässt.

## W11 — `parsers.py` zerlegt (622 Zeilen → Paket) ✅ 2026-08-01

Reine Struktur, kein Verhalten. Das Modul hatte **drei Gründe, sich zu ändern**,
in einer Datei: das Kartenschema, die Themenseiten-Formen und die
Textblock-Envelopes.

`services/mcp/parsers.py` → `services/mcp/parsers/` mit Fassade — dieselbe Form
wie beim `config_loader`-Split:

| Modul | Zeilen | Verantwortung |
|---|---|---|
| `cards.py` | 259 | FormattedNode-Envelope → Karten; dazu `parse_total_count`, das **dasselbe** Such-Envelope liest, nur das Zählfeld |
| `topic_pages.py` | 268 | Varianten (`collectionId` + `variants`) und Schwimmlinien — eine andere Antwortform als Karten |
| `text_blocks.py` | 107 | Volltext und Wikipedia: Envelope → Textblock, mit benanntem Leerfall statt Raten |
| `json_scan.py` | 39 | der Klammer-Scanner; weiß nichts über Karten, hat vier Verbraucher |
| `__init__.py` | 56 | Fassade + `__all__` |

**Warum die Fassade nicht optional war.** Bestands-Tests patchen per Zeichenkette
(`monkeypatch.setattr("boerdi.services.mcp.parsers.parse_wlo_cards", …)`), und
zwei Verbraucher (`card_reranker`, respond-Knoten) importieren sogar das private
`_first_json_object`. Die Modul-Adresse musste also erhalten bleiben. Vorher
gemessen: **kein Test patcht einen privaten Helfer** — sonst hätte der Schnitt
zwischen `topic_pages` und `_cards_from_json_envelope` still danebengelegen, weil
modulinterne Aufrufe im definierenden Modul auflösen, nicht an der Fassade. Diese
Grenze steht jetzt in beiden Modul-Docstrings.

**Beweis über die Tests hinaus:** ein Skript vergleicht jede bewegte Funktion per
AST (ohne Docstring) gegen das Original — **11/11 identisch**, eine einzige
Docstring-Abweichung, und zwar die beabsichtigte: die Querverweise in
`parse_topic_page_swimlanes` zeigten auf `parse_wlo_cards` im selben Modul und
wären nach dem Umzug falsch gewesen. Der erste Lauf des Skripts hat genau diese
Abweichung gemeldet, bevor ich sie erklären konnte — der Wächter funktioniert.

**Belege:** `uv run pytest -q` → **2277 passed, 4 skipped** (unverändert zum
Stand vor dem Schnitt) · die vier direkt betroffenen Testdateien einzeln 154 grün
vor **und** nach dem Umzug · `ruff check src tests` → All checks passed · alle
fünf Dateien unter der 300-Zeilen-Regel. Neue Tests gab es bewusst keine: eine
Extraktion, die neue Tests braucht, war keine Extraktion.

# Offene Aufgaben

Stand 2026-07-27 (nach P10). Eine Zeile pro noch nicht gebautem Stück, mit dem
Grund, warum es offen ist. Was hier NICHT steht, ist gebaut und verifiziert — die
Belege stehen in der jeweiligen Paket-Tabelle. **9-5 und 9-6 sind komplett**, und
mit ihnen **P9**; **die sechs Aufräum-Schritte B1–B6 sind es ebenfalls** (Belege im
Abschnitt darunter).

**Korrektur 2026-07-27, beim Start von P10 gefunden:** diese Rubrik versprach
„eine Zeile pro noch nicht gebautem Stück" und führte die **beiden offenen Pakete
P10 und P11 trotzdem nicht auf** — die Status-Tabelle ganz oben nennt beide seit
jeher als ⬜ offen. Wer nur hierher sah, las „nur noch zwei Kleinigkeiten", wo
zwei ganze Pakete fehlten. Genau die Fehlerklasse, die diese Rubrik sonst an ALT
protokolliert: was eine Übersicht **nicht** enthält, entscheidet mit, was sie
verspricht. Beide stehen jetzt in der Tabelle unten.

**Offen ist, was in der Tabelle unten steht** — sie ist die einzige Quelle.
Dieser Absatz hat die Zeilen früher noch einmal aufgezählt und ist dadurch
zweimal aus dem Takt gelaufen; zuletzt fehlten hier C6 und C7, die schon in der
Tabelle standen. Die Aufzählung ist deshalb entfernt statt nachgeführt: eine
Zusammenfassung, die dieselbe Liste ein zweites Mal führt, driftet wieder.
**P10 ist am 2026-07-27 komplett** (Belege im Abschnitt „Betrieb (P10)" weiter
unten).
**C4 (Widget-Auslieferung + Demo-Seiten) ist am 2026-07-27 erledigt**; Belege im
Backend-Abschnitt darunter. Damit gibt es **keinen öffentlichen 501-Stub mehr**,
und eine Host-Seite kann das Widget einbinden — die letzte Blockade vor P11.

**Neu aufgenommen bei B5, C5:** die Ressourcen-Sparklines waren als Aufräum-Schritt
gelistet, sind aber ohne eine Backend-Entscheidung nicht baubar (es gibt keine
Zeitreihe und auch keine Spitzenwerte — Messung in der B5-Notiz). Sie stehen jetzt
dort, wo ihre Voraussetzung liegt.

**Am 2026-07-26 mit A6 + A6-Rest erledigt und deshalb hier ersetzt:** die alte
A6-Zeile („Snapshots/Backup/Factory-Reset, Modell-Auswahl, Monaco-Neuentscheid")
und die A6-Rest-Zeile (Live-Preview). Gebaut sind die Views „Sicherung" und
„Vorschau"; die **Modell-Auswahl gab es in ALT nie** (nur eine Anzeige, die seit
A5 steht), der **Monaco-Entscheid bleibt nein**, und der **Jaeger-Link ist nicht
ehrlich baubar** — alle drei mit Messung in der 9-6-Zeile.

**Am 2026-07-26 mit A7 erledigt und deshalb hier entfernt:** die fünf
Feld-Reiter im Pattern-Formular. Beleg in der 9-4-Zeile.

**Am 2026-07-26 erledigt und deshalb hier entfernt:** A1, A2, A3, A4 (alle mit
vollem Beleg in der 9-5-Zeile) sowie C2 und C3 (Belege direkt hier darunter).
**9-5d ist damit komplett** — die Evaluation hat drei Tabs, zwei Start-Wege und
ein Lauf-Detail.

**C2 `/quality/tight-races` — repariert, nicht gestrichen.** Der Befund ist am
Quellcode bestätigt: `select_pattern` hat **drei** Return-Stellen und jede gibt
`{X.id: 1.0}` zurück, also erreicht `obs/quality_events.py` seinen
`len(sorted_scores) >= 2`-Zweig nie und `phase2_runner_up` ist auf jeder Zeile
`''`. Gestrichen wurde der Endpunkt trotzdem nicht: er ist Teil der eingefrorenen
107-Routen-ALT-Treue, und ein Löschen hätte eine dauerhafte Invariante gekostet,
um 46 Zeilen loszuwerden. Der eigentliche Defekt war auch nicht seine Existenz,
sondern dass er **stumm `total_tight: 0`** antwortete — das liest sich als
Messergebnis („in deinen Daten gibt es keine engen Rennen"), nicht als „diese
Metrik ist nicht erhebbar". Er zählt jetzt zusätzlich, wie viele Zeilen überhaupt
einen Zweitplatzierten tragen, und antwortet nur dann mit `unavailable_reason` +
`scanned`, wenn Zeilen da sind aber keine davon einen hat. **Datengetrieben, nicht
hartkodiert**: kommt je eine Score-Phase zurück, verschwindet der Hinweis von
selbst; eine 0 bei vorhandenen Zweitplatzierten bleibt eine echte Messung. Das
Studio bindet den Endpunkt weiterhin **nicht** an (der Grund dafür ändert sich
nicht) — die Begründung im Service-Kommentar zeigt jetzt auf beides.
**Kein OpenAPI-Bruch** (die Response ist untypisiert `dict`). +3 Tests
(`test_quality_pg.py`), 15 grün.

**C3 Golden-Runner LLM-Judge — ein Port, keine Neuerfindung.** ALT hat dafür ein
eigenes Modul (`app/services/eval_golden.py`), also galten die Fidelity-Regeln
und ALTs Tests waren die Spezifikation. Der Judge konnte nicht in
`evals/run_golden.py` (framework-frei, darf nichts aus `boerdi.*` importieren) —
und dessen README sagte das selbst vorher: „LLM-Judge … absichtlich NICHT hier".
Neu ist deshalb `services/eval/golden.py` (113 Z.) als framework-seitige Hälfte.
**Der Judge allein wäre unsichtbar geblieben**: sein Schnitt taucht nur über
`_aggregate`s `total_judged_turns`/`avg_score` auf, also gehören die drei
Aggregatoren zwingend dazu — und damit schreiben **Gold-Läufe jetzt auch
`classification_metrics`**, die einzige Quelle der fünf Trend-Serien (ALT tut das,
NEU tat es nicht). **Tragende Regel, rot-grün belegt:** die Headline `avg_score`
bleibt die deterministische harte Bestehensquote, der Judge steht als `judge_avg`
daneben — sonst zeigten Lauf-Liste und Scorecard verschiedene Zahlen für denselben
Lauf, und ein wärmerer Judge sähe wie Qualitätsgewinn aus. Zeile entfernt →
**genau 4** Tests rot (2 je Ebene), kein Kollateral. **Befund im Vorbeigehen:**
`run_flows` speicherte `debug` nur im Fehler-Zweig, nie im Erfolgs-Zweig — ohne
das hätte der Judge Pattern und Hint-Disagreement blind bewertet; jetzt liegt
dort ALTs flache Teilmenge (`flatten_debug`, dokumentierter Twin wie
`augment_bot_text`, KEIN voller Blob: `trace`/`context` wären Kilobytes je Turn in
jedem Report). Ebenfalls nachgezogen: `intent_id` je Konversation und
`expected_persona`/`expected_intent` je Turn, weil die Metriken darauf keyen.
**Eigene Härtung:** der Judge ist ein zweiter Fehlerpunkt **nach** ~40 teuren
echten Chat-Turns — `conversations` wird jetzt außerhalb des `try` gebunden, damit
ein Judge-Ausfall das Transkript nicht wegwirft (Test dafür). Ein einzelner
gescheiterter Judge kostet seinen Turn (0.0-Verdikt), nicht den Lauf; ihn
wegzulassen würde den Schnitt der Überlebenden heben. **Backend 2099 pytest grün +
2 skips · ruff clean · `export_openapi.py --check` unverändert** (+17 Tests:
`test_eval_golden.py` 10, `test_golden_runner.py` +2, Router +5).

**A5 Übersicht (9-5f) — Startseite steht, Referenz zu zwei Dritteln.** ALTs Home
war zwei Tabs (`page.tsx:447-470`: `homeTab` = Übersicht | Architektur & Referenz),
und die View-Registry sagt dasselbe („Start, Architektur & Status") — deshalb ist
die Referenz hier ein Tab und keine eigene Route; einen `info`-Slug gibt es nicht.
Neu: `views/overview.component` (Startseite, `DEFAULT_VIEW`, Route verdrahtet — sie
zeigte bis jetzt den Platzhalter), `views/overview-cards.ts` (6 Schicht- + 5
Betriebs-Karten als Daten), `core/overview-api.service.ts`,
`views/architecture-reference.component` + `views/reference-data.ts` +
`views/reference-widget.component` + `views/widget-contract-data.ts`,
`core/format.ts` → `relativeGerman`.

**Drei ALT-Verhalten bewusst nicht portiert, je mit Grund:** (1) kein
Offline-Banner — der Shell-Header pollt `/health` und besitzt den Zustand, zwei
Anzeigen könnten sich widersprechen; (2) keine verschluckten Fehler — ALTs vier
Fetches lagen in einem `Promise.allSettled`, dessen Rejections fallen gelassen
wurden, ein kaputter Endpunkt sah dauerhaft wie „keine Daten" aus; (3) keine
Schnellzugriffs-Leiste — zwei der drei Knöpfe verdoppelten Karten derselben Seite,
der dritte öffnete den A6-Dialog.

**Zwei Ehrlichkeits-Regeln, rot-grün belegt** (Umkehr → genau 3 Tests rot, einer je
Regel, kein Kollateral): Zahlen nur, wenn gemessen — ALT füllte sechs Zählwerte mit
`?? 16`, `?? 6`, `?? 8`, `?? 3`, `?? 5`, `?? 17` (HomeOverview.tsx:128-133), also
standen beim ersten Rendern und nach jedem gescheiterten Request Messwerte da, die
niemand gemessen hatte. Und: der Werksstand zeigt, was NEU **hat** —
`GET /config/factory` antwortet hier `{exists, created_at, label}`, ALTs `size`,
`mtime`, `has_db`, `config_files` existieren nicht, ein wörtlicher Port hätte drei
Gedankenstriche und ein falsches „0 Configs" gemalt (dieselbe Klasse wie C2).

**Vier ALT-Fehler in der Referenz gefunden und korrigiert statt mitportiert:**
(1) die Widget-Attribut-Tabelle listete **17** von 18 — es fehlte genau
`inline-result-grouping`, das Attribut, das 8-7 als tot entdeckte; jetzt pinnt
`widget.component.spec.ts` den Attribut-Satz und nennt `widget-contract-data.ts`,
wenn er bricht. (2) ALT führte `(pageAction)` als Angular-Output des Elements —
ALTs eigenes Widget deklarierte nur vier (`widget.component.ts:119-146`), dieselben
vier wie NEU; `page-action` erreicht Host-Seiten allein als window-Event. (3) die
Selbst-ID-Zeile nannte die Routing-Regel `lookup_persona_self_id__*`, zwei
Abschnitte nachdem derselbe Text den Ausbau dieser Engine beschreibt — in NEU
existiert die Regel nicht (`grep`: nur `persona_overrides` in
`classify-overrides.yaml` + `classify_prompt.py:108`). (4) die „Anzahl"-Spalte der
Input-Elemente ist entfallen: vier der sechs Zahlen misst der Übersicht-Tab, die
anderen zwei stehen als Aufzählung in derselben Zeile.

**Nachgeprüft und ALT hatte recht** (nicht „korrigiert"): 18 Material-Typen, 13
didaktisch, 5 analytisch — `05-canvas/material-types.yaml` hat 19 Einträge, davon
ist `auto` der „such du einen aus"-Selektor mit `category: didaktisch`. Die Zahl
bleibt mit Herkunftsangabe im Code, weil kein Endpunkt sie liefert.

**Eigene Entscheidungen:** native `<details>`/`<summary>` samt der 9-4b-Partial
`_section-shell.scss` statt ALTs `useState(open)` (tastaturbedienbar, als
aufklappbar angekündigt, von der Seitensuche auch zugeklappt findbar) ·
Navigation als `<a routerLink>` statt `<button onClick>` · Label und Beschreibung
der Karten kommen aus `STUDIO_VIEWS`, nicht aus einer Kopie (ALTs „Quality"-Karte
öffnete eine Seite mit Titel „Analyse"), und ein Test prüft, dass **jedes**
Kartenziel ein existierender Slug ist · `relativeGerman` nimmt den Bezugszeitpunkt
als Parameter (testbar ohne Fake-Timer) und rechnet über `Intl.RelativeTimeFormat`
— ALTs Konkatenation schrieb „vor 1 Tagen" und bei vorlaufender Server-Uhr
„vor -2 Min". **Zwei eigene Fehler fing der Test:** der Divisor `bound/60` stimmt
nur für Minuten (3 h wurden zu „vor 7 Stunden"), und `numeric: 'auto'` macht aus
einem Tag „vorgestern".

**Größe:** die Referenz wurde an der sichtbaren Naht geteilt, bevor die restlichen
Abschnitte sie über die 300-Zeilen-Grenze drücken — Widget-Vertrag (öffentliche
API) ≠ Prompt-Architektur, also eigene Sektions-Komponente + eigene Datendatei,
geteilte Inhalts-Stile in `views/_reference.scss`. Danach alle neuen Dateien
≤300 Z.; die vier Dateien darüber im Studio sind unverändert die bekannten.

**Beim Durchlesen des eigenen Diffs gefunden:** fällt das Backend ganz aus, melden
**alle fünf** Reads denselben Satz — die Fehlerliste zeigte „Backend nicht
erreichbar." fünfmal, und fünf identische Strings sind fünf identische
`@for`-track-Schlüssel. Jetzt entdoppelt (`Set`), Test dafür (rot: „expected 5 to
have a length of 1").

**Belege:** studio **635** Vitest grün (602 → +33) · widget **30** grün (29 → +1,
der Attribut-Satz) · `npx eslint .` exit 0 · Token-Abgleich „benutzt aber nie
definiert" leer · `ng build studio`: Initial 269,07 kB / 76,88 kB gzip, neuer
Lazy-Chunk `overview-component` 46,31 kB / 12,29 kB gzip · ALT-Bäume 0 geänderte
Dateien, `badboerdi.db` unverändert 11.07.2026 00:35:50.

**A5-Rest ✅ 2026-07-26 — die sechs restlichen Abschnitte, zwei davon LIVE.**
Der tragende Entscheid fiel beim Prüfen, nicht beim Schreiben: `GET
/config/elements` liefert je Signal den vollen Modulations-Dict mit, und `GET
/config/data/05-canvas/material-types` die ganze Typenliste — **also werden die
zwei Katalog-Abschnitte gelesen statt abgetippt.** Der Grund ist gemessen: ALTs
Handkopien genau dieser zwei Listen waren gedriftet. Vier Signal-Zeilen waren
**falsch** gegen `04-signals/signal-modulations.yaml` (`effizient` als „mittel"
statt `kurz`; `vertrauend` als „keine Overrides", setzt aber `empfehlend` +
`mittel`; `vergleichend` als „sachlich" statt `analytisch`; `delegierend` als
„kurz" statt `mittel`/`proaktiv`), fünf weitere ließen eine gesetzte Flagge weg
(`skip_intro` bei ungeduldig/gestresst/erfahren/entscheidungsbereit, `show_more`
bei neugierig, `show_overview` bei orientierungssuchend) — und die Material-Liste
ließ **`Vokabelliste` ganz aus**, sodass zwölf echte Typen unter „Didaktisch (13)"
standen (dieselbe Fehlerklasse wie die 17-von-18-Attributtabelle aus A5). Die
Startseite reicht die schon geholte `elements`-Nutzlast weiter, statt ein zweites
Mal zu fragen; die Material-Typen holt der Katalog selbst, bezahlt also erst beim
Öffnen des Referenz-Tabs.

**Vier weitere ALT-Aussagen am NEU-Code widerlegt und korrigiert statt portiert:**
(1) die „Konfliktregeln" („bei widersprüchlichen Signalen gewinnt die kürzere
Länge und das restriktivere Verhalten") **gibt es nicht** — `pattern_engine.py`
schreibt die Modulationen in Listenreihenfolge, das **letzte** Signal gewinnt;
ALTs eigener Code ist an dieser Stelle byte-gleich, die Aussage war also auch über
ALT falsch. Die zweite Hälfte („Signale überschreiben Pattern-Defaults") stimmt
und bleibt. (2) `reduce_items_signals` **deckelt** `max_items` auf 3
(`min(output["max_items"], 3)`), es halbiert nicht. (3) „10 MCP-Tools" — beide
Bäume definieren **zwölf** (`grep -c '"name":'`); `query_knowledge` ist der
RAG-Einstieg aus `response_tool_selection.py`, kein MCP-Werkzeug. (4) „SQLite-Vec"
— NEU sucht mit **pgvector** in Postgres. Bestätigt und unverändert übernommen:
die Resolver-TTLs (30 min / 2 min) und seine zwei MCP-Aufrufe.

**Struktur:** die Hülle war bei 252 Zeilen, also wurden die sechs Abschnitte drei
Sektions-Komponenten (nach der Mechanik, die `reference-widget` schon vorgibt):
`reference-flow` (Wechselwirkungen + Beispiel-Turn), `reference-catalogs` (die
zwei Live-Tabellen + `reference-catalogs.ts` als reine, testbare Transformation),
`reference-knowledge` (RAG/MCP, Themenseiten-Auflösung, Snapshots — Letzteres
verlinkt die A6-View). Dabei **eine Kopie entfernt statt angelegt**: die Hülle
behauptete „18 Material-Typen (13 didaktisch, 5 analytisch: …)" und verweist jetzt
auf den Live-Abschnitt.

**Eigener Defekt, vom eigens dafür geschriebenen Test gefangen:** die Übersicht
band `[signals]` nicht an — die Tabelle hätte dauerhaft „die Signale stehen hier,
sobald …" gezeigt. Das ist zum **dritten** Mal dieselbe Klasse (`data-position`
8-5, `inline-result-grouping` 8-7), diesmal vor dem Grün erwischt.

**Rot-Grün belegt:** Überschrift ohne Trennung · unbekannte Flagge verworfen ·
`auto` als Typ gezählt ⇒ **3** rot in der reinen Spec (+2 Folgefehler in der
Komponenten-Spec, die dieselbe Logik rendert). **Belege:** studio **683** grün
(669 → +14) · ui 454 · widget 30 · `npx eslint .` exit 0 · Token-Abgleich leer ·
`ng build studio` Initial 269,84 kB / 77,11 kB gzip, `overview-component`
76,94 kB / 17,13 kB gzip · größte neue Datei 138 Z. · **damit ist 9-5f komplett.**

## Studio (P9)

| # | Aufgabe | Warum offen / was fehlt genau |
|---|---|---|

## Aufräum-Schritte — am 2026-07-26 abgeschlossen (B1–B6)

Die Tabelle ist leer, weil alle sechs Schnitte gebaut und verifiziert sind. Was
sie ergeben haben, steht hier; jeder Schritt hat seinen eigenen Rot-Grün-Beleg.

**B1 `check:tokens`** — neu `frontend/scripts/check-tokens.mjs` (87 Z., node-only,
Muster von `check-widget-budget.mjs` inkl. optionalem Wurzel-Argument für ein
Fixture) + npm-Skript + **eigener CI-Schritt direkt nach `lint`**, nicht in `lint`
hineingezogen: ein fehlgeschlagener Schritt soll benennen, welche Regel gebrochen
ist. Gemessen am echten Baum: 395 Dateien, 48 Tokens definiert, 36 gelesen, 0 ohne
Definition. Rot-Grün am Fixture: eine Datei definiert `--fix-a`, eine zweite liest
`--fix-a` **und** `--fix-missing` ⇒ Exit 1, gemeldet wird **nur** `--fix-missing`
mit beiden Fundstellen (beweist: Pooling über Dateien hinweg, kein Rundumschlag).
Bewusste Grenze im Skript dokumentiert: Definitionen werden über den Baum gepoolt,
nicht je `@use`-Graph aufgelöst.

**B2 vier Datums-Kopien** — drei (`sessions`, `safety-logs`, `loadtest`) waren
zeichengleich mit `germanDateTime` und wurden zur Delegation. **Die Rubrik nannte
`MCP-Registry` als vierte — die hat keinen Datums-Helfer**; die vierte Kopie saß in
`session-transcript`, und sie **wich ab**: bei unparsbarem Zeitstempel gab sie `''`
zurück statt der Eingabe, also sah eine korrupte Zeile aus wie eine, die das
Backend nie gestempelt hat. Bewusst vereinheitlicht (`iso ? germanDateTime(iso) : ''`
— das Muster aus `eval-run-detail`), damit die Fälle unterscheidbar bleiben; neues
Spec `session-transcript.component.spec.ts` mit **genau 1 rot** vor der Änderung.

**B3 neun Handkopien in acht Stylesheets** — nicht acht: `quality-matrix` hatte
zwei, und **zwei der neun waren keine Utility-Klasse**, sondern direkt das
`<thead>` der Balken-Tabelle und ein Hinweis-`<span>`. Genau deshalb ging das
Zählen nach Klassennamen (`.er-sr`, `.lt-sr`, …) nie auf. Alle neun hängen jetzt an
`views/_visually-hidden.scss`; 15 Klassennamen in 11 Templates umbenannt, die zwei
Kommentare, die *welches Element* erklärten, sind in die Templates gewandert.
Verifiziert nicht nur über den Build: ein Skript prüft für **jede** der 12 Dateien
mit `class="sr"`, dass ihr Stylesheet die Regel bekommt (direkt oder über
`_section-shell`) — 12 abgedeckt, 0 ohne. Nebenbefund: die Partial hat zwei
Deklarationen mehr als die Kopien (`margin: -1px`, `padding: 0`), beides der
kanonische Schutz gegen geerbtes Padding.

**B4 `area-editor` auf `TabBarComponent`** — **erst gehärtet, dann migriert.** Der
Editor **lehnt** den Reiterwechsel bei ungespeicherten Änderungen ab und ließ den
Fokus dann stehen; die geteilte Leiste fokussierte bedingungslos. Ein wörtlicher
Austausch hätte also einen fokussierten Reiter mit `aria-selected="false"`
erzeugt — eine angesagte Panel-Umschaltung, die nicht stattfand. `focusTab(index)`
ist jetzt `focusActive()`: es fokussiert den **tatsächlich aktiven** Reiter. Erster
Versuch mit `queueMicrotask` schlug fehl und **der Bestandstest hat es gefangen**
(„takes the focus along" wurde rot): `active` ist ein Input und trägt die Antwort
des Aufrufers erst nach der Change Detection ⇒ `afterNextRender`. Neuer Test mit
einem ablehnenden Host: **1 rot** vor der Härtung. Für die Migration selbst ein
Wächter, der prüft, dass **jedes** `aria-controls` auflöst und das Panel
zurücklabelt (die Bug-Klasse „Attribut erreicht seinen Konsumenten nie", 3× in
diesem Projekt): grün vor der Migration, grün danach, und **2 rot**, sobald man eine
Panel-Id verstellt. Die Inline-Stile waren wirkungsgleich mit den geteilten und
sind gelöscht; `area-editor`-Chunk 10,77 → 9,41 kB.

**B6 Rückfragen ansagen** — 9 Rückfragen in 7 Templates tragen jetzt
`role="alert"`. **Die Rubrik sagte „keines davon eine Live-Region" — für
`eval-generative-start` ist das falsch**, A3 hatte dort schon eine (und die Knöpfe
bewusst außerhalb). Genau das wurde zur Regel für alle: **`role="alert"` trägt die
FRAGE, nicht den Container.** Fünf der Rückfragen haben Knöpfe, deren Label auf
„Wird gelöscht …" umschaltet — ein Container-`alert` hätte bei jedem Umschalten die
ganze Rückfrage erneut vorgelesen (die Falle, die A5 für den Kostenabsatz gefunden
hatte). 7 neue Tests, alle 7 rot vor der Änderung; die achte Fläche ist als
„schon abgedeckt" gepinnt, inkl. der Begründung, warum sie `polite` bleibt.

**B5 war nicht baubar — und deckte einen Defekt auf.** Die Zeile sagte „die
Spitzenwerte stehen im Fazit, der Verlauf fehlt". Am Backend gemessen: **es gibt
beides nicht.** `services/loadtest.py` hat ALTs psutil-Abtastung bewusst nicht
portiert — `resource_samples` bleibt `[]` und `_summary` liefert genau vier
Schlüssel, keinen davon eine Spitze. Es gibt also keine Zeitreihe für Sparklines
**und** keine Spitzen. Die Ansicht zeigte sie trotzdem: die Lauf-Liste rannte in
`Spitze NaN MB`, das Detail in `Spitzenwerte: NaN MB RSS, NaN % CPU` — im
Rot-Beleg wörtlich im gerenderten Text zu sehen. Warum es niemand merkte: der Typ
`RunSummary` erklärte `peak_rss_mb`/`peak_proc_cpu_pct` als vorhanden (der Compiler
hatte also keinen Grund zu meckern) **und beide Test-Fixtures erfanden Werte
dafür**, eine Zusicherung prüfte sogar `'481 MB'`. Geliefert ist deshalb die
Ehrlichkeit statt der Sparkline: Typ auf die vier echten Schlüssel, Fixtures auf
die echte Antwortform, beide Anzeigen benennen jetzt, was sie **nicht** messen (auch
der Einleitungssatz, der „Ressourcen je Stufe" versprach), toter `round()`-Helfer
weg. **Die Sparklines bleiben offen als C5** — sie brauchen zuerst eine
Backend-Entscheidung (psutil), und die gehört dem Nutzer.

**Belege für die ganze Reihe:** studio **734** grün (719 → +15) · ui 454 · widget 30
· `npx eslint .` exit 0 · `npm run check:tokens` exit 0 · `ng build studio` Initial
295,15 kB / 85,70 kB gzip · Widget-Budget 412,77 kB raw / 128,09 kB gzip (unberührt)
· größte neue Datei 87 Z. · Backend **nicht angefasst** (0 Dateien) · ALT-Bäume
0 geänderte Dateien · `badboerdi.db` unverändert (2026-07-11 00:35:50).

## Backend

**C4 Widget-Auslieferung + 3 Demo-Seiten — erledigt 2026-07-27.** Die fünf
`501`-Stubs in `api/widget.py` sind implementiert; damit ist **kein einziger
öffentlicher Stub mehr übrig** (es bleibt genau einer, studio-gated:
`GET /api/debug/mcp-test`, P5-1). Eine Host-Seite kann das Widget jetzt einbinden.

**C4a Auslieferung + V1.** `/widget/boerdi-widget.js` bleibt der stabile Pfad und
antwortet mit 302 auf `/widget/boerdi-widget.<12-hex-sha256>.js`; erst diese URL
trägt den Inhalt, mit `public, max-age=31536000, immutable`. Der Redirect selbst
ist `no-store` — wäre er cachebar, zeigte er nach einem Deploy weiter auf das alte
Bündel. Der Hash kommt aus dem Dateiinhalt, ein neuer Build erzeugt also von selbst
eine neue URL (Ende der Klasse „Studio neu, Widget alt"). **Kein Cache für den
Hash**: er wird pro Anfrage gerechnet, aber nur auf dem stabilen Pfad — einmal je
Seitenaufruf, danach hält der Browser die gehashte URL ein Jahr. Ein Cache bräuchte
seine eigene Invalidierung, also genau den Mechanismus, dessen Versagen diese
Verbesserung verhindern soll.

**Drei Entscheidungen, jede mit Grund:**
* **Keine sechste Route.** Der gehashte Name läuft durch die vorhandene
  `/{asset_name}`-Catch-All. Die Routen-Zahl ist eingefroren; ein zusätzlicher Pfad
  wäre Vertrags-Drift für ein Implementierungsdetail des Redirects.
* **Verzeichnis nur aus `WIDGET_DIST_DIR`.** ALT rechnete
  `parents[3]/frontend/dist/widget/browser` und hatte einen zweiten Fallback-Pfad,
  weil es kein Setting hatte. NEU konfiguriert statische Wurzeln explizit (wie
  `STUDIO_DIST_DIR`) — das deckt beide ALT-Fälle ohne Raten aus `__file__`.
* **Kein `/api/static`-Mount.** ALT hatte einen für ein Logo. Gemessen: das NEU-
  Widget trägt das Logo inline (`ui/src/branding/boerdi-logo.ts` exportiert SVG +
  Data-URL), im gebauten Bündel steht `api/static` **null**-mal, und der einzige
  Helfer, der so eine URL bauen würde (`boerdiLogoUrl()`), hat **keinen Aufrufer**
  außer dem Re-Export. Ein Verzeichnis mounten, das niemand abfragt, ist kein Port.

Sicherheit unverändert von ALT übernommen: der Containment-Check läuft **vor** dem
Existenz-Check (400 „invalid path", nie 404), sonst wäre der Endpunkt ein Existenz-
Orakel für das Host-Dateisystem.

**C4b Demo-Seiten — Demo-Seiten, nicht ALTs Integrations-Guide.** ALT hatte hier
942 Zeilen HTML, überwiegend eine Attribut-Referenz. **Nachgemessen: sie listet 17
der 18 Host-Attribute** — es fehlt `inline-result-grouping`, ausgerechnet das, das
8-7 als tot gefunden und repariert hat (dieselbe Lücke, die A5 in ALTs Studio-
Tabelle fand; zwei unabhängige Kopien, dieselbe Drift). Das Studio pflegt die volle
Liste aus einer Quelle, die ein Test gegen das Element festnagelt; eine dritte,
ungetestete Kopie in einem Python-String wäre die, die als Nächstes veraltet. Die
Seiten verweisen deshalb dorthin und tun, was nur sie können: das echte Element
gegen das echte Backend fahren.

Drei Varianten aus **einer** Vorlage (ALT hatte zwei fast gleiche Kopien plus ein
`str.replace` für die dritte — genau deshalb beschrieb sein `/classic` einen Modus,
den es nicht mehr gab: der Code-Kommentar sagt es selbst, `inline-result-grouping`
war „deprecated und immer auf True forciert"). **In NEU lebt das Attribut wieder**,
also ist `/widget/classic` hier ein echtes A/B gegen `/widget/inline` statt einer
Notiz darüber. Der Event-Inspector ist das einzige Stück ALT, das bleibt — klein
neu geschrieben, und seine Event-Liste ist eine Konstante, gegen die ein Test
prüft, dass **genau** die vier gezeigt werden, die das Widget wirklich feuert
(`guide-suggestion`, `routing-debug` aus `host-events.ts`, `query-meta`,
`page-action` aus `chat-shell`). Ein Panel für ein Event, das niemand feuert, liest
sich als kaputtes Widget.

**Live verifiziert, nicht nur im Test:** Server mit dem echten Bündel gestartet,
`/widget/boerdi-widget.js` → 302 auf `…05935c519496.js`, ausgelieferte Bytes
**byte-identisch** zu `main.js` (412 772 B); die Seite im Browser geladen —
`customElements.get('boerdi-chat')` definiert, Shadow-Root da, alle §5.5-Methoden
am Knoten (`openChatbot`/`closeChatbot`/`toggleChatbot`/`isChatbotOpen`/
`resetSession`/`updateContext`), **keine Konsolen-Fehler**. Dabei ein Layout-Fehler
gefunden und behoben, den kein Test gezeigt hätte: der Inspector (22 rem, unten
links) stieß bei 460 px Breite an den Widget-Knopf unten rechts → Breite jetzt
gegen den Viewport gedeckelt.

**OpenAPI:** 85 Pfade / 113 Operationen **unverändert**, alle Response-Typen
unverändert `application/json` — dieselbe Konvention, der `/api/chat/stream` (SSE)
und `/api/config/backup` (ZIP) schon folgen. Neu im Vertrag sind nur fünf
`description`-Felder aus den Handler-Docstrings; das ist die etablierte Praxis
(55 der 113 Operationen tragen bereits eine).

**Zwei Bestandstests umgehängt, nicht umgangen:** `test_stubs_return_501` und
`test_http_matrix_on_studio_route` benutzten den Widget-Bundle-Stub als ihren
Stellvertreter für „öffentliche 501-Route". Ersterer prüft jetzt, dass **keine** der
vier Widget-Routen mehr 501 gibt (die Behauptung wird geprüft statt erinnert),
letzterer prüft die 503 — sie beweist dieselbe Sache besser, nämlich dass ein
Request ohne Schlüssel den Handler erreicht.

**Belege:** Backend **2125** pytest grün (2099 → +26), 2 skipped · `ruff check
src/ tests/` clean · OpenAPI-Gate `openapi contract unchanged` · größte neue Datei
216 Z. (`widget_demo_html.py`) · Frontend unberührt.

## Betrieb (P10) — komplett 2026-07-27

**P10-1 Prod-Image.** `Dockerfile` in der Repo-Wurzel (Kontext = Repo), drei
Stufen: node baut Widget + Studio, uv baut die Deps, schlanke Runtime. **Das
Frontend wird im Image gebaut** — ALTs häufigster Deploy-Fehler steht in der
ersten Sektion seiner eigenen CLAUDE.md (von Hand gebautes `widget_dist` veraltet
still: „Studio neu, Widget alt"); hier ist der vergessbare Schritt weg. Nachweis:
SHA-256 des im Container ausgelieferten Bündels = SHA-256 des lokalen Builds
(`05935c519496c82c…`, 412 772 B). **Non-root ist hier erstmals wirklich
erreichbar** (V12): ALT hatte den Block auskommentiert, weil sein Container in
bind-gemountete Host-Pfade schrieb — hier liegt die Config in Postgres (V2), und
der einzige Laufzeit-Schreibzugriff im ganzen `src/`-Baum ist eine Temp-Datei
beim RAG-Ingest (gemessen, mit `finally: os.unlink`). Healthcheck über den
vorhandenen Interpreter statt curl (ALT installierte curl **und** build-essential
ins Runtime-Image). `uv sync --no-editable` ⇒ `/app` enthält **kein** `src/`:
eine Codekopie, nicht zwei. Smoke gegen echtes Postgres: `/health` 200 · `id` =
1000 · Widget-Redirect auf die gehashte URL, die mit `immutable` liefert ·
`/studio/` 200 text/html · Docker-HEALTHCHECK `healthy` · `alembic upgrade head`
aus **demselben** Image · `docker stop` = 3 s, ExitCode 0, „Application shutdown
complete" (V12 Graceful Shutdown) · keine `.env` irgendwo im Image. 683 MB.

**P10-2 `deploy/compose.prod.yml`.** Sieben Dienste: traefik (TLS+LB) · backend
×N · postgres · redis · migrate (Einmal-Lauf) · jaeger · pg-backup. **Zwei
Messungen haben den Bauplan korrigiert:** (1) **kein TEI** — die P10-Zeile nennt
ihn, aber V13 hat den Sidecar am 2026-07-12 verworfen und `rerank_url` liest im
gesamten `src/` **niemand**; ein Dienst, mit dem nichts sprechen kann, ist kein
Port (dieselbe Regel wie beim `/api/static`-Mount in C4a). (2) **`redis` fehlte
als Abhängigkeit** — V7/§8 verlangen ein clusterfähiges Rate-Limit über
`redis://`, `limits` braucht dafür das `redis`-Paket, und `import redis` schlug
fehl. Nutzer-Entscheid 2026-07-27: aufnehmen (redis 8.0.1, MIT, Lizenz-Gate
bestanden). **Der Fehler ist im Prüfstack real eingetreten**, weil das Image von
vor `uv add redis` stammte: `ConfigurationError: 'redis' prerequisite not
available`, drei Container in `Restarting (1)`. Genau deshalb steht die Regel
„Abhängigkeit geändert ⇒ Image neu bauen" jetzt im Runbook. Weitere Entscheide:
Migration als eigener Dienst (N Replikas dürfen nicht parallel `upgrade head`
fahren), **kein** Anwendungsdienst mit `ports:` (ALT-Audit T-2: published Ports
laufen an ufw vorbei), Docker-Socket für traefik nur `:ro` + `exposedByDefault=
false` (T-9), Secrets ohne Default (`:?`) statt ausgeliefertem Dev-Secret,
`stop_grace_period: 40s` > die 30 s des Images. **Live geprüft** (ohne traefik,
dessen ACME eine auflösbare Domain braucht): `docker compose config` exit 0 und
ohne Secrets exit 15 mit klarer Meldung · Kette postgres → redis → migrate
(ExitCode 0) → **backend ×3 alle `healthy`** · Backup-Schleife schreibt einen
echten Dump (`pg_restore -l` liest die TOC) · der Runbook-Restore-Befehl
**wörtlich** durchgespielt: Tabelle angelegt, gesichert, gelöscht, zurückgeholt,
Wert wieder da.

**P10-3 §8-Checkliste als Testprotokoll** (`docs/cluster-checkliste.md` +
`tests/test_cluster_checklist.py`, 3 Tests). Drei der fünf §8-Punkte sind
automatisiert, zwei brauchen einen echten Cluster — und das steht dort als
solches statt als Häkchen. **Punkt 2 war ungeprüft**: `test_pg_locks_notify.py`
prüft den *Inhalt* der Benachrichtigung und lässt dafür bis zu 5 s zu, die
§8-Schranke ist aber < 2 s. Der neue Test misst die Spanne (**0,02 s**, im
Umkehr-Lauf abgelesen). **Punkt 3 war vor P10-2 nicht baubar**; er prüft jetzt
die Eigenschaft, auf die es ankommt: zwei Limiter-Instanzen teilen sich *ein*
Kontingent, und eine später gestartete Replika erbt den Zählerstand statt ihn
zurückzusetzen (sonst wäre jeder Deploy ein Freifahrtschein). **Umkehr-Probe:**
Storage auf `memory://` ⇒ genau die zwei Redis-Tests rot; Schranke auf 0,0001 s
⇒ Propagations-Test rot mit dem echten Messwert im Text. Eigener Fund beim
Rot-Lauf: mein Prüf-App hatte kein `response: Response` in der Signatur — die
echten limitierten Endpunkte haben es, weil slowapi es bei `headers_enabled=True`
verlangt; der Prüfstand war unrealistisch, nicht der Code.

**P10-4 Runbook + Security-Checkliste** (`deploy/README.md`): Deploy in drei
Schritten (Migration getrennt, damit ihr Fehler vor dem Neustart der Replikas
sichtbar ist), Skalieren, Backup, Restore, Rollback, Logs/Traces per SSH-Tunnel
— plus eine Livegang-Checkliste aus dem Audit-Erbe, in der ✅ und ⚠️ getrennt
sind. **Ehrlich benannt:** Migrationen rollen nicht mit zurück; die
Backup-Schleife ist kein cron und verschiebt bei jedem Neustart ihren Takt.

**P10-5 Image-Gate in CI** (`.github/workflows/image.yml`, neu).
`ci.yml` prüft **Quellen, nicht das Artefakt** — ein falscher COPY-Pfad, eine
kaputte Stufe oder eine fehlende Abhängigkeit fiel bisher erst im Deploy auf.
**Der Anlass steht zwei Absätze weiter oben in P10-2**: das Image von vor `uv add
redis` ging mit `limits.errors.ConfigurationError` in eine Neustart-Schleife. Der
Smoke setzt deshalb `RATE_LIMIT_STORAGE_URI=redis://…` und **nicht** den
`memory://`-Default — mit dem Default wäre genau dieser Fehler unsichtbar
geblieben. Am installierten slowapi nachgelesen, warum das reicht:
`Limiter.__init__` ruft `storage_from_string` **beim Import**, der Prozess stirbt
also vor dem ersten Request; der Smoke muss dafür keinen limitierten Endpunkt
treffen.

Vier Abwägungen, jede mit ihrem Preis:

* **Eigener Workflow statt Job in `ci.yml`.** Pfad-Filter gibt es in Actions nur
  auf **Workflow**-Ebene, nicht pro Job — ein Job könnte nur nach Branch
  entscheiden oder bräuchte eine Fremd-Action (`dorny/paths-filter`). Trigger:
  `push` auf `main` **ohne** Filter (was gemergt ist, wird gebaut),
  `pull_request` nur bei Dockerfile/`.dockerignore`/pyproject/uv.lock/alembic/
  `backend/src`/`frontend`, plus `workflow_dispatch`. Übersprungen und damit
  gespart: `backend/tests/**`, `docs/**`, `evals/**`, `deploy/**`, Markdown.
  **`backend/src/**` steht bewusst drin**, obwohl es fast jeden Backend-PR
  trifft: `uv sync --no-editable` baut ein Wheel, und eine neue
  Nicht-`.py`-Datei unter `src/` kann in pytest (Quellbaum) funktionieren und im
  Image (Wheel) fehlen — dieselbe Drift-Klasse, gegen die das Gate existiert.
  Preis notiert: wird der Check je „required", blockiert ein PR ohne Treffer
  dauerhaft; dann braucht es einen Always-Skip-Zwilling.
* **Kein `needs:` auf backend/frontend** (ginge ohnehin nur im selben Workflow):
  es würde den grünen Normalfall — die große Mehrheit — etwa verdoppeln, um im
  roten Fall Minuten zu sparen. Beide Workflows laufen parallel.
* **Cache `type=gha,mode=max`, nicht `min`.** Bei einem Multi-Stage-Build enthält
  `min` nur die Layer des **finalen** Images; die teuren Zwischenstufen (npm ci,
  uv sync) wären damit nicht im Cache und liefen jedes Mal neu. Preis benannt:
  der Cache ist groß und kann im 10-GB-LRU des Repos die npm-/uv-Caches aus
  `ci.yml` verdrängen — falls `ci.yml` je spürbar langsamer wird, ist das die
  erste Stelle zum Nachsehen.
* **Eigenes Docker-Netz statt `services:`.** Die Dienste müssen für den
  App-Container unter ihrem **Namen** erreichbar sein, wie in `compose.prod.yml`.
  GitHubs Service-Container hängen in einem Runner-Netz, an das ein per `docker
  run` gestarteter Container nicht ohne Weiteres kommt — man landet bei
  `--network host` und published Ports, also bei einer Topologie, die es in
  Produktion nicht gibt.

Geprüft (lokal, Docker 27.5.1, Sequenz 1:1 wie im Workflow): Migration
`alembic upgrade head` aus **demselben** Image · `/health` 200 mit
`{"status":"ok"}` · Redirect **302 → `/widget/boerdi-widget.05935c519496.js`** (=
der in P10-1 belegte Digest) · gehashte URL 200 **mit `immutable`** · `/studio/`
200 · uid 1000 · Docker-HEALTHCHECK `healthy`. **Umkehr-Probe mit drei
simulierten Dockerfile-Defekten, alle drei korrekt rot:** `WIDGET_DIST_DIR`
falsch ⇒ 503 statt 302 · `STUDIO_DIST_DIR` falsch ⇒ 404 — **und der Container
startet dabei fehlerfrei**, weil `mount_studio_spa` den Mount nur mit einer
Info-Zeile überspringt; genau deshalb steht `/studio/` überhaupt im Smoke, es ist
die einzige der drei Oberflächen, deren Fehlen **stumm** ist · DB unerreichbar ⇒
die Warteschleife bricht nach **22 s mit ExitCode 3** ab statt 120 s zu warten
(der Früh-Abbruch bei totem Container ist die Redis-Vorfall-Klasse).
**Eigener Fund beim Selbst-Review:** Redis hatte keine Bereitschafts-Schranke,
nur Postgres. Weil `limits` beim **Import** verbindet, wäre ein noch nicht
bereites Redis kein später Fehler, sondern ein toter Container gewesen —
praktisch startet `redis:8-alpine` schneller als die zwei Schritte davor dauern,
aber „praktisch" ist bei einem Gate der Unterschied zwischen selten rot und
verlässlich. Jetzt haben beide Dienste einen Healthcheck und eine gemeinsame
Warteschleife (nachgefahren unter `bash -e`, der Shell von Actions: beide in 3 s
healthy; Umkehr-Probe mit einem nie gesunden Dienst ⇒ rc 1).
**Nicht von mir belegbar:** ein echter Actions-Lauf — es gibt kein Git-Repo
(Nutzer-Domäne). Ungeprüft bleiben damit die YAML-Syntax gegen GitHubs Parser
und das Cache-Verhalten von `docker/build-push-action`; die Smoke-Logik selbst
ist es nicht.

**Belege:** Backend **2129** pytest grün + 1 skip (Basis C4: 2125 + 2 skip;
+3 neue Tests, und der Jaeger-Test läuft jetzt statt zu überspringen) · `ruff
check src/ tests/` clean · Lizenz-Gate mit der neuen Abhängigkeit bestanden
(redis 8.0.1 MIT) · OpenAPI-Gate `openapi contract unchanged` · größte neue
Datei 248 Z. (`.github/workflows/image.yml`; davor `compose.prod.yml` mit 215) ·
Frontend-Quellen unberührt. **P10-5 fügt keine Zeile Python oder TypeScript
hinzu** — Workflow-YAML plus die zwei Doku-Stellen; Suite, ruff-Lauf und
OpenAPI-Vertrag sind davon per Konstruktion unberührt und wurden dafür nicht neu
gefahren.

**P10-6 Rate-Limit-Speicher: Redis → Valkey — erledigt 2026-07-27.**
Nutzer-Entscheid nach Vorlage der Messungen. **Der Auslöser ist eine Lizenz, kein
Fehler:** Redis 8 steht laut `redis/redis` `LICENSE.txt` unter RSALv2 **oder**
SSPLv1 **oder** AGPLv3 — **alle drei stehen auf der Verbotsliste der Eisernen
Regel 1** (`GPL;AGPL;LGPL;SSPL;Elastic;BUSL`); Redis ≤ 7.2 war BSD-3-Clause.
Valkey ist BSD-3-Clause (an `valkey-io/valkey` `COPYING` geprüft), spricht
dasselbe Protokoll und ist mit **42 statt 114 MB** auch das kleinere Image —
Redis 8 bringt die Stack-Module (Suche/JSON/Zeitreihen) mit, von denen hier
keines gebraucht wird. Leerlauf-RAM in beiden Fällen ~10 MB, das war nie das
Problem.

**Warum das Gate den Fall nicht gefangen hat — und das ist der eigentliche
Befund:** `pip-licenses` sieht **nur Python-Pakete**. Der Client `redis-py` ist
MIT und hat sauber bestanden, während der *Server* als Docker-Image komplett an
der Prüfung vorbeiläuft. Das trifft jeden künftigen Dienst im Compose gleichermaßen
(als **C7** aufgenommen — **am 2026-07-27 geschlossen**, Beleg direkt darunter).

**Umgestellt:** Abhängigkeit `redis` → `valkey` (6.1.1, MIT, vom Valkey-Projekt
selbst), URI-Schema `redis://` → `valkey://`, Images in compose.dev + compose.prod,
Dienst- und Healthcheck-Namen, der Test-Marker, sowie der P10-5-CI-Workflow — der
sonst eine Konfiguration geprüft hätte, die wir nicht mehr ausliefern. **Das
Schema wählt auch den Client** (`limits`: valkey-py für `valkey://`, redis-py für
`redis://`), und da redis-py entfernt ist, scheitert eine übriggebliebene
`redis://`-URI laut beim Start statt still pro Prozess zu zählen — belegt:
`import redis` schlägt fehl, `storage_from_string('valkey://…')` meldet
`target_server=valkey`, Client-Modul `valkey`, `check()` True.

**Verhalten unverändert, und das ist geprüft:** dieselben zwei §8-Tests, die die
geteilte Zählung pinnen, laufen unverändert grün gegen Valkey 8.1.9
(`server_name: valkey`; die gemeldete `redis_version: 7.2.4` ist der
Kompatibilitäts-Stand = der Fork-Punkt). Dazu die sieben Bestandstests des
Rate-Limits.

**Zwei eigene Fehler unterwegs, beide von der Prüfung gefangen:** (1) mein
zeilenweises Umschreiben des CI-Workflows hinterließ literale `
` statt
Zeilenumbrüchen in zwei `docker run`-Befehlen — gefunden, weil ich nach dem
YAML-Parsen zusätzlich jeden `run:`-Block mit `bash -n` geprüft habe (11 Blöcke
sauber nach der Reparatur). (2) Beim Umbenennen eines Compose-Dienstes bleibt der
alte Container als **Waise** zurück und hält seinen Port — der neue kam nicht
hoch, bis `--remove-orphans` lief; steht jetzt im Runbook.

**Im Vorbeigehen gemessen und als C6 aufgenommen:** die sitzungsbezogene Bremse
aus der Safety-Config existiert in NEU **nicht**. `ratelimit.py` behauptete im
Docstring, sie sei „ported with the P4 preflight" — eine Funktion
`check_rate_limit` gibt es nirgends, **kein** Feld von `RateLimitsBlock`
(`enabled`, `per_session`, `per_ip`, `ip_whitelist`, `blocked_message`) wird
außerhalb des Config-Modells gelesen, und `rate_limited=True` setzt niemand, der
Zähler in der Safety-Statistik kann sich also nie bewegen. Das Studio bietet den
Block trotzdem zum Bearbeiten an. Die falsche Docstring-Zeile ist korrigiert (sie
sagt jetzt, dass dieses HTTP-Limit das einzige ist), die Ehrlichkeitslücke in der
Oberfläche steht als C6. — **Nachtrag 2026-07-31: C6 ist gebaut**, die Bremse
existiert jetzt (`services/rate_limits.py`, Aufruf im preflight-Knoten); der
Docstring von `ratelimit.py` sagt seither „das äußere Limit" statt „das einzige".

### C7 ✅ 2026-07-27 — Lizenz-Gate für Container-Images

`backend/tests/test_image_licenses.py` (215 Z., 6 Tests) prüft **jede**
Image-Referenz im Repo gegen `IMAGE_LICENSES`, eine Positivliste mit belegter
Lizenz je Image. Gefunden werden aktuell **7** Images in 6 Dateien; alle sieben
Lizenzen am 2026-07-27 **upstream nachgelesen**, nicht aus dem Gedächtnis
notiert: pgvector `PostgreSQL`, valkey `BSD-3-Clause`, traefik `MIT`, jaeger
`Apache-2.0`, python `PSF-2.0`, node `MIT`, uv `MIT`.

**Gate statt CI-Schritt.** Die Rubrik-Zeile schlug „einen kleinen CI-Schritt"
vor; gebaut ist ein Test im bestehenden pytest-Job — dieselbe Wirkung ohne
zweite Mechanik, lokal mit demselben Befehl ausführbar, und `test_openapi_
contract.py` liest mit `parents[2]` längst über die Backend-Grenze hinaus.

**Vier Prüfungen, alle im Umkehr-Lauf rot gesehen** (je ein eingeschleuster
Defekt, danach zurückgebaut): unbekanntes Image (`redis:8-alpine` — der
historische Fall), Referenz ohne Default (`${SOME_IMAGE}`), verwaiste
Listen-Zeile, verbotene Lizenz (`traefik` auf AGPL-3.0 gesetzt). Die
Verwaisten-Prüfung ist zugleich die Leerlauf-Sperre: fände der Scanner nichts,
wäre jede Zeile verwaist und der Test rot — sonst ginge die erste Prüfung durch,
weil eine leere Menge keine Ausreißer hat.

**Tags sind mit gepinnt**, weil eine Lizenz mit der Version wechseln kann: genau
das ist bei Redis zwischen 7.2 (BSD-3-Clause) und 8 passiert. Ein Versionssprung
muss deshalb an der Liste vorbei.

**Beim Bauen selbst gefunden:** der erste Wurf las nur `image:`-Schlüssel und
`FROM` — `.github/workflows/image.yml` startet seine Dienste aber per
`docker run` im Shell-Block, Valkey und Postgres wären dort **ungeprüft**
geblieben. Dieselbe Lückenklasse, gegen die C7 antritt, im Werkzeug gegen sie
selbst. Jetzt mit abgedeckt; erkannt wird an der **Form** (`name:tag`) statt an
der Argument-Stellung, weil `--rm nginx:alpine` und `--name x nginx:alpine` das
Image an verschiedene Positionen legen und eine Flaggen-Tabelle ab der ersten
neuen Option still falsch wäre. Port-Abbildungen haben dieselbe Form und fallen
am rein numerischen Namensteil raus — ohne diese Sperre rutscht `8100:8100` aus
der echten `image.yml` durch (gemessen, indem ich sie kurz entfernt habe).

**Bewusste Grenze, im Docstring benannt:** geprüft wird die Lizenz der
*Hauptkomponente* — nicht die Systempakete der Basis-Schicht. Jedes debian-slim-
Image enthält GPL-Userland (bash, coreutils); ein Gate, das daran scheitert,
scheitert an allem und wird abgeschaltet. Regel 1 zielt auf Copyleft-Pflichten
für **unseren** Code, ein unverändert gezogenes Basis-Image erzeugt keine.

**Benannte Grenze statt stiller Lücke:** im Shell-Block wird an der
``name:tag``-Form erkannt, ein **ungetaggtes** `docker run alpine sh` hat sie
nicht. Aufgefangen wird das nicht — „jeder `docker`-Befehl muss ein Image
nennen" schlägt auf Prosa an (in `image.yml` erwähnen zwei Kommentare
`docker run`, probiert). Ungetaggt heißt ohnehin ungepinnt; heute trifft es
allein `docker run --rm boerdi-chat alembic …`, also das eigene Image. In YAML
und Dockerfiles gibt es die Lücke nicht.

**Warum Positivliste und keine Abfrage:** an den Images gemessen, die wir ziehen,
gibt es nichts auszulesen — `valkey/valkey:8-alpine` trägt nur
`org.opencontainers.image.source`, `pgvector/pgvector:pg17` und
`jaegertracing/jaeger:2.19.0` **gar keine** Labels. Die Entscheidung muss ein
Mensch festhalten, und das ist der Zweck.

**Am 2026-07-27 mit C7 erledigt und deshalb hier entfernt:** das Lizenz-Gate für
Container-Images. Beleg im Abschnitt „C7 ✅ 2026-07-27" oben — inklusive der
Lücke, die das Werkzeug im ersten Wurf gegen sich selbst hatte.

**Ebenfalls am 2026-07-27 erledigt: C9** (SSE-`phase`-Ereignisse). Die Zeile bleibt
durchgestrichen stehen statt zu verschwinden, weil sie zwei Messbefunde trägt, die
sonst verloren gingen: ALTs eigenes `safety_classify`-Label ist in ALT tot, und der
Rest-Schritt `topic_content` ist bewusst offen. Rest davon unten als eigene Zeile.

| # | Aufgabe | Warum offen |
|---|---|---|
| ~~W11~~ | ~~`services/mcp/parsers.py` zerlegen~~ **✅ ERLEDIGT 2026-08-01** | Aufgenommen und noch am selben Tag gebaut; Beleg im Abschnitt „W11" oben (Paket mit vier Modulen + Fassade, 11/11 Funktionen AST-identisch, Suite unverändert bei 2277). |
| ~~C1~~ | ~~i18n (Deutsch + Englisch)~~ **✅ ERLEDIGT 2026-08-08** | **Komplett gebaut.** Fünf Rubriken: **C1-a/b/c** (Sprach-Kern, Widget, Umschalter), **C1-d** (Studio-Oberfläche, zuletzt d5 in sieben Scheiben = 295 Texte), **C1-e** (Backend-Meldungen über `Accept-Language`), **C1-f** (Ausgabe-Sprache der LLM-Erzeuger + die deterministischen Bot-Sätze) und **C1-g** (die Studio-gepflegte Config, Suffix je Schlüssel). Kataloge: Widget 114, Studio 890, Backend-Meldungen 25, Bot-Texte 31 Schlüssel je Sprache. Gates zuletzt: studio **889** (76 Dateien) · widget **39** · pytest **2458 / 4 skips** · eslint, `check:a11y`, `check:tokens` sauber. **Drei Dinge bleiben bewusst einsprachig, je mit Grund:** die Studio-gepflegten Auslöser-Listen bleiben deutsch (Nutzer-Entscheid bei C1-f2c), 14 Backend-Meldungen bleiben englisch (gemessen in C1-e3, der Wächter `BEWUSST_EINSPRACHIG` hält jede sichtbar), und `Invalid path` bleibt englisch, weil `area-doc-editor` es als Protokoll-Marker liest. **Nutzer-Domäne bleibt der Live-Lauf je Sprache** — belegt ist, dass die Sprach-Direktive im Prompt ankommt, nicht die Trefferquote des Modells. **Der Verlauf darunter bleibt stehen**, weil er die Messbefunde je Scheibe trägt; die Quelle ist und bleibt `docs/plans/2026-08-02-c1-i18n.md`. — **Der Verlauf, wie er beim Bauen entstand:** **🔄 ab 2026-08-02 in Arbeit — Entwurf, Entscheidungen und Schnitt stehen jetzt in `docs/plans/2026-08-02-c1-i18n.md`; dort ist die Quelle, nicht mehr hier.** **C1-b, C1-c, C1-d1, C1-d2, C1-d3 (a–d), C1-d4a, C1-d4b (b1–b3), C1-d4c, C1-d4d (d1+d2, damit die ganze Rubrik), C1-d4e (e1–e4) und C1-d4f sind fertig** (C1-a Sprach-Kern · C1-b1 Seam + Widget-Hülle · C1-b2 Chat-Shell + die vier Inline-Renderer · C1-b3 reine Label-Funktionen · C1-b4 Bot-/Fehlertexte + Druckfenster + Guide-Chip-Rückfall · **C1-c Umschalter + `language`-Attribut + Host-/Browser-/Speicher-Quellen + eingebauter EN-Katalog** · **C1-d1 Studio-Spracheinstellung + Umschalter + Rahmen-Katalog** · **C1-d2 Ansichts-Registry auf Katalog-Schlüssel + ihre sechs Verbraucher** · **C1-d3a der generische Bereichs-Editor + der von 21 Ansichten geteilte Zustands-Streifen** · **C1-d3b der Katalog-Split (je Bereich eine Datei unter `i18n/catalogue/`, beide Sprachen beieinander, `de.ts`/`en.ts` nur noch Fassaden) + „Sicherung" + „Vorschau"** · **C1-d3c MCP-Registry + Wissensbasis (Bereiche, Dokumente, Einlesen), dazu `Intl.ListFormat` als dritter Grammatik-Griff** · **C1-d3d `curated-views.ts` — die zehn kuratierten Seiten tragen nur noch Struktur und Katalog-Schlüssel**; Widget-Katalog **114 Schlüssel je Sprache**, Studio-Katalog **890** Schlüssel je Sprache (die 515 bei C1-d4b3 waren 8 zu niedrig — die Teil-Tabelle führte `views.ts` mit 40 statt 48; nachgezählt lauten die Laufzahlen 500 → 523 → 615, geprüft als Summe je Teil UND als Vereinigung, ohne einen Schlüssel in zwei Teilen) (ab C1-d4b1 **gezählt statt aufsummiert** — die Laufsumme der Scheiben-Zuwächse war um 8 abgedriftet; maßgeblich ist die Messung über alle Teilkataloge, DE und EN gleich), ui 561 / widget 36 / studio 874 grün, eslint 0, `check:tokens`/`check:a11y` sauber, Budget 507,71/600 kB roh · 148,08/175 kB gzip — durch C1-d1 bis C1-d3d unverändert, weil der Studio-Katalog nicht im Widget-Bundle liegt). Ein Restliteral-Scan über `ui/src` + `widget/src` findet keinen sichtbaren deutschen Text mehr — übrig sind nur `console.*`-Meldungen, interne `Error`-Texte und zwei benannte Protokollwerte (`TOUR_START_LABEL`, der `'Sammlung'`-Filter in `print-utils.ts:248`). Offen sind **C1-d5 und C1-f2c**. **C1-f2b2 ist fertig** (2351 pytest, `openapi contract unchanged`, ruff sauber): die Material-Oberflaeche — `canvas_fast_path` + `domain/completion_messages` (Katalog jetzt 48 Schluessel je Sprache; `lang` als Parameter durch den reinen Domaenen-Helfer). **Der Schnitt wurde durch die Messung geaendert:** die in f2b1 notierten „vier Module" sind keine vier gleichartigen — `turn_links` hat 2 erreichbare und 3 hinter deutschen Regexen unerreichbare Saetze, und `guide_qr_injector`s „5 Beschriftungen" stehen in `02-domain/guide-rules.yaml` und schlagen die Code-Fassung, sind also eine Config-Schema-Frage. Beide wandern nach **C1-f2b3**. **Der Fund:** der Loesungen-Waechter in `canvas_fast_path` prueft mit deutschen Regexen auf `## Loesungen` — seit C1-f2a ist das Material aber englisch, also bekam JEDES englische Arbeitsblatt einen deutschen Stub angehaengt, auch mit sauberem `## Solutions`. Anders als bei f2b1 waere der Defekt nicht durch das Uebersetzen entstanden, er war schon da. **Regel daraus:** ein Analysator ueber unserer EIGENEN Ausgabe hat eine bekannte Sprache und gehoert zu f2b; nur Analysatoren ueber NUTZER-Eingabe sind die vertagte Produktentscheidung f2c. Zweiter Fund: „Automatisch" bleibt auch im englischen Satz stehen — das Wort ist ein Schluessel in `05-canvas/type-aliases.yaml`, uebersetzt waere der Satz eine Anweisung, die das System nicht ausfuehren kann. **C1-f2b1 ist fertig** (2338 pytest, `openapi contract unchanged`, ruff sauber): die deterministischen Sätze der Direkt-Aktionen (`content_text_action` M17 + `direct_actions`) folgen der Widget-Sprache, über einen ZWEITEN Katalog `i18n/bot_text.py` (31 Schlüssel je Sprache) neben `messages.py` — andere Zielgruppe (Nutzer vs. Redaktion), anderer Auslöser (`environment.locale` vs. `Accept-Language`); geteilt wird nur das Rendern, dafür ist `render()`/`_Keep` verhaltenserhaltend nach `i18n/catalogue.py` gezogen. **Der Fund dabei:** `direct_actions` entschied den Rendering-Pfad per `startswith` auf den eigenen deutschen Fehlersatz — ein Klasse-C-Analysator im übersetzten Modul; ersetzt durch einen `lp_failed`-Merker am Kontrollfluss, rot-grün belegt (erst der zweite Testentwurf unterschied die Zweige überhaupt). Details in `docs/plans/2026-08-02-c1-i18n.md`. **C1-f2a ist fertig** (2325 pytest, `openapi contract unchanged`, ruff sauber; Frontend nicht berührt): die Ausgabe-Sprache der übrigen vier LLM-Erzeuger — Canvas-Material, Kuratier-Text, Lernpfad, Quick-Replies — folgt jetzt der Widget-Sprache, über zwei Atome in `i18n/prompt_language.py` (`language_name` ersetzt den Sprachnamen an Ort und Stelle → deutscher Prompt bytegleich; `template_hint` hängt NUR bei Nicht-Deutsch an und ist für Deutsch leer). Vier der fünf Direktiven gab es schon, in vier verschiedenen Gestalten. **Die Messung davor ist der eigentliche Ertrag:** die AST-Aufzählung ergibt **755 deutsche Literale in 72 Dateien** (die „286" waren wieder eine untere Schranke) und zerfällt in drei Klassen — Ausgabe (übersetzen), Prompt (bleibt deutsch) und **Analysator** (Regex/Stichwortlisten ÜBER deutschem Text; weder übersetzen noch lassen, weil sie beim Sprachwechsel still aufhören zu greifen — inklusive des Selbstverletzungs-Gates auf der Eingabeseite). Details in `docs/plans/2026-08-02-c1-i18n.md`. **C1-f1 ist fertig** (2309 pytest, ui 564, widget 36, `openapi contract unchanged`, ruff/eslint sauber, Budget 507,86/600 kB roh): die Sprache des Widgets erreicht das Backend und lenkt die Bot-Antwort. Nutzer-Entscheid: **`environment.locale` beleben** (statt Accept-Language), Schnitt **nur der Antwort-Pfad**. Zwei Messungen VOR dem ersten Edit: das Feld steht seit je im eingefrorenen Vertrag und wird in `domain/context.py:30` gelesen — mit **null Verbrauchern** (**sechster Fall „dokumentiert ohne Konsumenten"**); und das Widget fuellte es aus `navigator.language` statt aus seiner seit C1-c aufgeloesten Sprache. Kein neues Vertragsfeld noetig, kein zweiter Sprachkanal. **Der rote Lauf hat den Entwurf umgeworfen:** der Prompt endet **bereits** mit „Antworte auf Deutsch. Formatiere mit Markdown." — und zwar **dreimal wortgleich** in den drei sich ausschliessenden P8-Bloecken. Ein angehaengter Block haette zwei widersprechende Anweisungen erzeugt; stattdessen wird die bestehende Zeile an Ort und Stelle sprachabhaengig (`_OUTPUT_LANGUAGE`, einmal statt dreimal). **Folge, die den Ausschlag gab: der deutsche Prompt bleibt bytegleich**, inkl. Position — drei Tests halten das je Zweig fest. Kein Signatur-Umbau noetig, weil `_build_system_prompt` `environment: dict` schon entgegennahm; `resolve_locale` ist derselbe Parser wie fuer den Header (C1-e1). **Nicht bewiesen:** ob das Modell der Direktive FOLGT — das zeigt nur ein Golden-/Eval-Lauf je Sprache (Nutzer-Domaene); Aufruestweg waere eine zweisprachige Direktive in derselben Konstante. **C1-f2** bleibt: die uebrigen LLM-Aufrufe (`llm_curation.py:45` traegt dieselbe harte Zeile) + die deterministischen Rueckfall-Saetze — gemessen **286 deutsche Literale in 42 Dateien** als OBERE Schranke „moegliche Bot-Ausgabe"; welche davon der Nutzer wirklich sieht, ist die erste Aufgabe von C1-f2, vor jedem Schnitt. **C1-e1 und C1-e2 sind fertig** — und zwei Messungen haben den Zuschnitt geändert: das **Widget sieht diese Sätze nie** (alle `detail`-Treffer im Frontend-Kern sind `CustomEvent.detail`, `chat.py` trägt null deutsche Literale), C1-e ist also **vollständig Studio-Sache**; und das erste Suchmuster hatte **untergezählt** (9 gefunden, 11 vorhanden — zwei Meldungen ohne Umlaut und ohne eines der gesuchten Wörter). Nutzer-Entscheid aus drei vorgelegten Wegen: **`Accept-Language` + kleiner Backend-Katalog**, nicht Fehler-Codes. **Der eingefrorene Vertrag ist unangetastet geblieben:** die Abhängigkeit liest den Header von `Request` statt ihn als `Header()` zu deklarieren — ein deklarierter Header stünde im OpenAPI-Dokument; `export_openapi.py --check` sagt `openapi contract unchanged`. Bewusst getragene Grenze: er steht damit nicht in `/docs`. 11 Aufrufstellen → **8 Schlüssel** (`field.empty` trägt vier mit dem Feldnamen als Parameter). `msg()` gibt bei unbekanntem Schlüssel den Schlüssel zurück und lässt einen vergessenen Platzhalter stehen — im Fehlerpfad machte ein `raise` aus einer brauchbaren 400 eine 500; gefunden werden beide stattdessen von einem Wächter, der **jeden in `api/` gelesenen Schlüssel** gegen den Katalog prüft (AST-Suche, Gegenstück zu `views-i18n.spec.ts`). **C1-e2 ist fertig** (2302 pytest, `openapi contract unchanged`, ruff sauber, studio 878 unverändert — kein Frontend berührt, der `languageInterceptor` aus C1-e1 trägt den Header schon). Wieder hat die Messung den Zuschnitt geändert, und wieder war meine eigene Zählung eine untere Schranke: statt eines Prosa-Suchmusters lief eine **AST-Aufzählung jedes `HTTPException`-Details in `api/`**. Ergebnis **7 Router, 20 Aufrufstellen, 17 Schlüssel** (Katalog 25 je Sprache) statt der berichteten „~21 in sieben Routern" — **`quality.py` fehlte ganz** (Satz ohne Umlaut und ohne Suchwort), und **`speech.py` fällt raus**: das Studio ruft `/speech/*` nirgends auf, der einzige Aufrufer ist das Widget, und `chat-api.ts:231/244` wirft `new Error('Transcription failed')`, **ohne die Antwort zu lesen** — die vier Sätze liest kein Mensch. Neu gebaut ist der **Wächter der Gegenrichtung**: `BEWUSST_EINSPRACHIG` friert jede Meldung ein, die NICHT durch `msg()` geht, je mit Grund; C1-e1 hatte Schlüssel-ohne-Text, dieser hat Text-ohne-Schlüssel. Er hat sich sofort bezahlt gemacht — nach dem Umbau meldete er `'Kein Factory-Stand gesetzt'`, **2 von 20 Stellen**, deren Signatur ich umgestellt, deren Ausnahme-Zeile ich aber vergessen hatte. Zwei Meldungen tragen deutsche Wörter ohne Umlaut („wuerde ALLE Quality-Logs loeschen", „Doppel-Bestaetigung") — vor der Übernahme geprüft: **ALT-Wortlaut**, also bindend, wandert unverändert in den Katalog. **Offene Rechnung, bewusst:** ~13 Meldungen bleiben einsprachig ENGLISCH (Zustände wie „File not found", Betreiber-/Entwickler-Meldungen, die vier Widget-Sätze) — ein englischer Satz im deutschen Studio ist genauso einsprachig wie umgekehrt; der Wächter hält sie sichtbar, bis die Produkt-Entscheidung fällt. Nachlauf: `config.py` steht bei **307 Zeilen** (Bestand, meine Änderung per Saldo ~0). Die andere Hälfte ist der `languageInterceptor` im Studio (aus `format.htmlLang`, nur gleicher Ursprung). Backend 2300, studio 878. **C1-d4e4 (Sicherheitslevel-Wähler, 10 Schlüssel) ist fertig — und zwar in `area-editor.ts`, nicht in einem eigenen Teil:** die Komponente heißt nach Safety, gerendert wird sie in `area-section`. Übersetzt sind nur die Beschreibungen; die fünf NAMEN („Off“/„Regex“/…) bleiben stehen, weil sie die Schlüssel aus dem `presets`-Block der Datei sind und ein eigenes Preset seinen Schlüssel unverändert als Namen trägt — dieselbe Lage wie `areas.importCmd`. **18. eingefrorener Konstanten-Fall:** `KNOWN` trägt jetzt Beschreibungs-Schlüssel statt fertiger Sätze. **C1-d4f (die sechs sprachgebundenen Formatierer) ist fertig — gemessen 48 Aufrufe in 20 Ansichten statt der geschätzten 25 in 12, wieder Faktor ~2**, aber nicht teilbar, weil eine Signaturänderung der Compiler nicht teilt. `core/format.ts` nimmt das BCP-47-Kürzel als ersten Parameter (`germanDateTime` → `formatDateTime`, `relativeGerman` → `formatRelative` — die Namen behaupteten Deutsch); das Kürzel steht im Katalog als **`format.locale`** neben `format.htmlLang`, weil es eine Entscheidung je Sprache ist und kein Text. **Der neue Dienst `StudioFormat` wohnt in `i18n/`, nicht in `core/`** — `core` darf nicht nach `i18n` importieren, dieselbe Begründung wie beim `Translate`-Typ; und er ist ein eigener Dienst statt sechs weiterer Methoden in `StudioLanguageService`, weil Grammatik und Zahlen-Typografie zwei Gründe zur Änderung sind. **Englisch ist `en-GB`, nicht `en-US`** (Produktentscheidung, in einer Zeile umkehrbar): der Tag bleibt vorn, sonst stünde „7/24/2026“ neben dem „24.7.2026“ der Kollegin. **„gerade eben“ kommt als Parameter herein**, weil `Intl.RelativeTimeFormat` keinen Fall unter einer Minute kennt und dieser eine Satz damit redaktionell ist. **Der eine rote Lauf war ein echter Befund:** `quality-overview.component.spec.ts` nagelte einen englischen Satz mit deutsch formatierter Zahl fest („Degradation rate at 22,0 %“) — der Test hatte die Verschiebung sogar selbst notiert. **Eine Annahme wurde von der Messung widerlegt:** die Vermutung, die Ansichts-Specs hingen an der Rechner-Sprache und fielen in einer CI mit `en-US` um, ist falsch — eine Sonde im Runner meldet `navigator.language = en-US` bei `Intl`-Standard `de-DE`, und **44 Spec-Dateien legen die Sprache fest** (die erste Zählung war bei 20 Zeilen abgeschnitten gewesen). Genau deshalb wurde nur EIN Test rot. **C1-d4e2 (Sitzungen, 27) und C1-d4e3 (Safety-Logs, 37) sind fertig — und diesmal lag die Schätzung zu HOCH** (~38 bzw. ~48): beide Ansichten lesen viel aus `shared.ts`/`views.ts` mit, die Rubrik-Schätzung zählte aber Texte auf dem Schirm statt neuer Einträge. **Der letzte handgeschriebene Mehrzahl-Griff des Studios ist weg** (`turn_count === 1 ? 'Turn' : 'Turns'`) — er war richtig, nur die deutsche Regel fest verdrahtet. **Vierter und fünfter Fall derselben A11y-Sache:** die Sessions-Zeile trägt ZWEI zerstörende Knöpfe mit `sr`-Anhang — genau der Fall, für den die Regel da ist, weil „Verlauf leeren" die Auswertungsdaten behält und „Löschen" sie mitnimmt. **16. und 17. eingefrorener Konstanten-Fall:** die zwei Karten in `safety-labels.ts` (Risikostufen, Rechtsfelder) — beide Rückfälle auf den rohen Schlüssel bleiben, weil das Backend Rechtsfelder anhängt, die die Liste nicht kennt. **Ein Fund, der eine eigene Scheibe bekam (C1-d4e4):** `safety-level.component` heißt nach Safety, wird aber in `area-section` gerendert — seine Texte gehören nach der Panel-Regel in `area-editor.ts`, also hat C1-d3a/d3b eine Komponente des eigenen Panels übersehen (derselbe Fall wie C1-d3d, nur kleiner; 18. Konstanten-Fall inklusive). **C1-d4e ist gemessen und dreigeteilt — zum zweiten Mal VOR dem Bau:** geschätzt waren ~53 für die ganze Rubrik, gemessen sind es **~140** über drei unabhängige Ansichten → **e1 Lasttest** (69) · **e2 Sitzungen** (~38) · **e3 Safety-Logs** (~48). **C1-d4e1 ist fertig** mit 69 Schlüsseln in `loadtest.ts`; das Lauf-Panel teilt sich den Teil mit dem Formular, weil es dort hinein gerendert wird. **Vier Anzahlen, alle vier bis hierher fest in der Mehrzahl** — Requests, Fehler, Messpunkte und Stufen; die roten Läufe gaben sie wörtlich aus (`1 Requests`, `1 Messpunkte`, `über 1 Stufen`). **Die Anzahl wählt hier die FORM, nicht nur das Substantiv:** „Stabil bis 1 gleichzeitig**en** Nutzer" gegen „bis 4 gleichzeitig**e** Nutzer" — die Beugung sitzt im Adjektiv, also steht der ganze Satz je Form da (`richPlural`, weil derselbe Satz Auszeichnung trägt). **Und der Bestandstest pinnte die falsche Form**: er prüfte mit `stable_concurrency: 1` auf die Mehrzahl — nach dem Code geschrieben, nicht nach der Sprache. **Dritter Fall derselben A11y-Sache:** der Löschen-Knopf der Lauf-Liste trug seinen Namen in zwei Bruchstücken (nach C1-d4b1 und C1-d4d2 — dieselbe Vorlage, dreimal kopiert). **Ein reines Modul bekommt den Übersetzer als Parameter:** `effectiveProfile(t, draft)`, wie `describeApiError` und `catLabel`; seine Zahlen sind Backend-Konstanten, eine Einzahl-Form könnte nie greifen. **Eine Doppelung mitgenommen:** `statusLabel` stand in beiden Lasttest-Komponenten wortgleich → `loadtest-status.ts` nach dem Vorbild von `eval-status.ts`. **Bewusst NICHT veändert:** die Zusammenfassung der Lauf-Liste bleibt ·-verbunden statt `list()` (technischer Streifen, keine Prosa), und `mixLine`/`byKindLine` bleiben roh — das sind Backend-Kennungen samt Gewicht. **C1-d4d ist komplett — 130 Schlüssel statt der geschätzten ~52**, in vier Teilkatalogen. Die Rubrik wurde **VOR dem Bau gemessen und geteilt** (erste Scheibe, bei der das gelang): **d4d1** Hülle + Übersicht + Diagnose (53, `quality.ts`) · **d4d2** Matrix (12) + Fluss (18) + Logs samt Detail (47). Ein Teil je PANEL — Diagnose gehört zur Übersicht und das Turn-Detail zum Log-Panel, weil beide dort hinein gerendert werden. **Fünf Mehrzahl-Defekte, die es heute schon auf Deutsch gibt**, haben die roten Läufe wörtlich ausgegeben — `1 Turns · 1 Muster`, `Aggregiert aus 1 Turns`, `1 Samples`, `1 Turns mit Phase, 1 Übergänge`, `1 Turns gelöscht.`. **Drei Anzahlen in EINEM Satz** (Fluss-Kopfzeile) entstehen als drei Wortgruppen über `plural()`; **der Artikel gehört dabei IN die Form** („letzter 1 Tag" gegen „letzte 30 Tage"), und der Leer-Text steht als zwei ganze Sätze da, weil er den Dativ braucht. **Ein A11y-Fehler aus C1-d4b1 wiedergefunden:** der Löschen-Knopf der Turn-Liste trug seinen Namen in zwei Bruchstücken (`Löschen` + `sr`-Anhang) — jetzt ein `aria-label`, das mit dem sichtbaren Wort beginnt. **Zwölfter und dreizehnter eingefrorener Konstanten-Fall:** `TABS` und `SCOPES` in `quality.component.ts`. **Eine bewusste Abweichung:** `<em>degradiert</em>` wird über `*…*` zu `<strong>` — `splitRich` kennt nur `strong` und `code`, und ein dritter Marker wäre eine Erweiterung des geteilten Bausteins für EINEN Verbraucher (die vier übrigen `<em>` stehen in der zurückgestellten Referenz-Prosa C1-d5). **Bewusst NICHT verändert:** `{scope}` bleibt der rohe Bezeichner (Übersetzung wäre Verbesserung, nicht Übersetzung), und die Filter-Aufzählung bleibt komma-getrennt statt `list()` — technische Liste, keine Prosa. **Neue Nacharbeit notiert:** „Persona", „Intent", „Confidence" und „Pattern" stehen in VIER Teilkatalogen gleichlautend; eine `label.*`-Gruppe in `shared.ts` wäre die Zusammenlegung, berührt aber drei fertige Scheiben und gehört in eine eigene. **C1-d4d ist zweigeteilt worden, und diesmal VOR dem Bau:** der Schnitt schätzte ~52 Schlüssel für die ganze Analyse, gemessen sind es gut **120** über acht Dateien — dieselbe Richtung wie bei d3b, d4b und d4c. Geteilt entlang der PANELS: **d4d1** Hülle + Übersicht + Diagnose (die Diagnose-Blöcke stehen IM Übersichts-Reiter, nicht daneben) · **d4d2** Matrix, Fluss, Logs + Log-Detail. **C1-d4d1 ist fertig** mit **53 Schlüsseln** in `quality.ts`. **Zwei Anzahlen in EINER Kopfzeile** („12 Turns · 3 Muster") entstehen als zwei Wortgruppen über `plural()`; der rote Lauf gab den deutschen Defekt wörtlich aus — `1 Turns · 1 Muster`. `qual.diag.counts` enthält dabei **kein Wort** und steht mit Begründung auf der Gleichlaut-Liste. **Zwölfter und dreizehnter eingefrorener Konstanten-Fall:** `TABS` und `SCOPES` in `quality.component.ts`. **Eine bewusste Abweichung:** `<em>degradiert</em>` wird über `*…*` zu `<strong>` — `splitRich` kennt nur `strong` und `code`, und ein dritter Marker wäre eine Erweiterung des geteilten Bausteins für EINEN Verbraucher (die vier übrigen `<em>` stehen sämtlich in der zurückgestellten Referenz-Prosa C1-d5). **Kein eigener Eintrag** für Krümel und Überschrift: beide lesen `nav.group.auswertung`/`view.analyse.label` mit; und „Leere Entities" steht EINMAL, gelesen als Kennzahl-Name UND als Substantiv des Zustands-Streifens. **C1-d4c** (Trends, Gold-Start, Generativ-Start) hat **92 Schlüssel statt der geschätzten 54** gebraucht, in zwei neuen Teilen: `eval-trends.ts` (35) und `eval-start.ts` (57). **Ein Teil für BEIDE Start-Panels**, weil sie im selben Reiter stehen und vier Texte wörtlich teilten. **Vier Mehrzahl-Defekte, die es heute schon auf Deutsch gibt**, haben die roten Läufe wörtlich ausgegeben — `1 Chat-Aufrufe`, `1 Chat-Anfragen`, `1 Kombinationen`, `über 1 Läufe` — dazu der `Flow(s)`-Notbehelf in der Gold-Kostenzeile. **Vier Anzahlen in EINEM Satz** (die generative Kostenzeile) entstehen als vier Wortgruppen über `plural()` statt als Schlüssel-Matrix aus 2⁴ Sätzen; Kostenzeile und Rückfrage stehen als je zwei GANZE Sätze da (mit/ohne Judge) statt als einer mit eingebautem `@if`. **Die gesprochene Zusammenfassung der Diagramme** war in der Komponente zusammengesetzt und steht jetzt als ganzer Satz im Katalog — in drei Fällen, weil ,,ein Lauf" etwas ANDERES sagt als ,,über N Läufe gestiegen" (Inhalt, nicht Grammatik). **Zehnter und elfter eingefrorener Konstanten-Fall:** `RATES` (vier Beschriftungen samt Erklärsatz, obendrein in einem `computed()` ständig neu gebaut) und `MODES`. Bewusst NICHT zusammengelegt: ,,Turns" steht an drei Stellen im Katalog — es sind verschiedene Tabellen, und ein gemeinsamer Eintrag hiesse, dass eine Übersetzung die anderen mitzieht. **C1-d4b3 hat die Rubrik abgeschlossen — und dabei etwas gefunden, das nicht auf der Liste stand.** Die Ansicht war nicht allein zu übersetzen: `QualityBarsComponent`, die geteilte Balken-Tabelle, trug **drei eigene deutsche Texte** (Screenreader-Spaltenkopf, voreingestellte Einheit, Beschriftung eines leeren Bezeichners) und steht in **drei Ansichten an sieben Stellen**. Sie übersetzt sie jetzt selbst aus `shared.ts` — wie der Zustands-Streifen seit C1-d3a; die fünf Aufrufstellen in C1-d4d ziehen ihre Hälfte kostenlos mit. `(ohne)` stand dabei **zweimal wörtlich** da (Balken-Tabelle + Pattern-Nutzung) → ein Eintrag `label.unclassified`. **Ein vierter Grammatik-Griff: `richPlural()`** neben `plural()`, `list()` und `rich()`. Die Summenzeile trägt **zwei** Anzahlen mit je eigener Mehrzahl und obendrein eine Hervorhebung; `splitRich(plural(…))` wäre genau falsch gewesen, weil `plural()` VOR dem Teilen einsetzt und damit die C1-d4b2-Zusage bräche. Jetzt wählt die Anzahl nur die FORM, geteilt wird der rohe Katalog-Text; die innere Wortgruppe kommt als `{combos}` herein. **Ein Fehler, den erst die Selbstdurchsicht fand:** die erste Fassung reichte die Zahl roh durch und verlor die Tausender-Trennung (`expected '12345 Turns' to be '12.345 Turns'`, als eigener roter Lauf nachgereicht) — behoben mit dem Muster, das `overview.snapshots` schon benutzte. **Neunter eingefrorener Konstanten-Fall:** `SCOPES` in `eval-pattern-usage.component.ts` trug Kennung UND Beschriftung. **Kein eigener Eintrag für den Namen der Ansicht:** Überschrift und Zustands-Streifen lesen `eval.tab.pattern` aus der Hülle mit — eine Doppelung hätte `en.spec.ts` bauartbedingt nicht gefunden. Und ein Alias ging mit seinem letzten Verbraucher: `@if (value(); as usage)` ist auf `@if (triples().length > 0)` zusammengezogen. **Damit ist C1-d4b vollständig: 104 Schlüssel statt der geschätzten 92, in drei Scheiben.** **C1-d4b2 hat die Entwurfsfrage gelöst, für die es die eigene Scheibe bekam — Auszeichnung MITTEN im Satz.** Gewählt ist **Marker im Text, geteilt beim Rendern** (`*so*` hebt hervor, `` `so` `` ist Code): der Übersetzer sieht den ganzen Satz mitsamt der Hervorhebung an ihrem Platz und darf sie verschieben. Drei Bausteine — `splitRich` in `ui/src/i18n/rich-text.ts`, `StudioLanguageService.rich()` neben `plural()`/`list()`, und `<studio-rich>` als Renderer. **Geteilt wird der KATALOG-Text, eingesetzt wird danach**, damit ein eingesetzter Wert (etwa `error_message` des Backends) niemals Auszeichnung erzeugen kann — eigens gepinnt. **Das Widget-Budget blieb aufs Byte gleich**: es importiert `splitRich` nicht, also fällt es beim Treeshaking heraus. **Ein Fehler, den erst der Test zeigte:** Angular behält den Leerraum INNERHALB der `@`-Blöcke — ein Umbruch je Zweig machte aus „harte Quote 83 %" ein „harte Quote  83 % "; die Vorlage steht jetzt ohne Umbrüche da, mit dem Grund im Dateikopf. **Achter eingefrorener Konstanten-Fall:** `CAT_LABELS` in `gold-scorecard.ts` → `catLabel(category, t)`. **Eine Doppelung beseitigt, bevor sie entstand:** Lauf-Liste und Lauf-Detail trugen je eine eigene Kopie derselben vier Status-Zeilen → `views/eval-status.ts`. **Ein Satz aus sechs Bruchstücken beseitigt:** die geöffnete Turn-Zeile ist jetzt EIN Eintrag mit sechs Platzhaltern. **Neuer Teilkatalog `eval-detail.ts` statt Anbau:** die Evaluation hat fünf Ansichten, ein Teil für alle stünde nach C1-d4c über 400 Zeilen — geteilt, BEVOR eine Grenze es erzwingt. **Erstmals traf die Schätzung** (~41 gegen 45 gezählt), weil sie aus einer Messung stammte. **Beobachtet, nicht mitgemacht:** „Status" steht jetzt an drei Stellen im Katalog — anders als bei `overview.refresh` sind das drei verschiedene Rollen (Überschrift, Formular-Beschriftung, Listen-Begriff), notiert als Kandidat für eine spätere `label.*`-Gruppe. **Auch C1-d4b war doppelt so gross wie geschätzt** (92 gezählt gegen ~46) — die dritte Messung in Folge mit demselben Faktor, und damit keine Ausnahme mehr, sondern die Regel dieser Rubrik. Dreigeteilt: **d4b1 Hülle + Lauf-Liste ✅** · d4b2 Lauf-Detail + `gold-scorecard.ts` · d4b3 Pattern-Nutzung. **C1-d4b2 bekommt eine eigene Scheibe, weil es eine Entwurfsfrage mitbringt:** Auszeichnung **mitten im Satz** (`<strong>`, `<code>`) an sieben Stellen. Je Bruchstück ein Katalog-Eintrag wäre genau der Fehler, den C1-d3a beim Zustands-Streifen abgestellt hat; `innerHTML` scheidet aus. Es braucht eine kleine geteilte Hilfe, die den übersetzten Satz an einem Platzhalter teilt — sie trägt auch die vier Erklär-Karten der Startseite (C1-d5). **C1-d4b1 im Einzelnen:** **siebter eingefrorener Konstanten-Fall** (`TABS` in `evaluation.component.ts`, dazu `STATUS_LABELS`/`STATUS_FILTERS` der Lauf-Liste — alle drei jetzt Erlaubnisliste Status → Schlüssel, nie zur Laufzeit zusammengesetzt). **Ein Fehler, der heute schon auf Deutsch sichtbar war:** die Zähl-Zeile stand fest als `{n} Läufe`, bei genau einem Lauf las sie sich „1 Läufe" — der rote Lauf gab es wörtlich aus; jetzt über `plural()`. **Ein Satz aus zwei Bruchstücken beseitigt:** der Löschen-Knopf trug `Löschen<span class="sr"> — Lauf {id}</span>`, jetzt **ein** `aria-label`, das mit dem sichtbaren Wort beginnt (WCAG 2.5.3). **Zwei Katalog-Doppelungen zusammengezogen statt eine dritte angelegt:** „Ja, löschen" stand als `snapshots.confirmDeleteYes` und `rag.confirmYes` gleichlautend da → `action.confirmDelete` in `shared.ts`, drei Aufrufstellen umgehängt. **Und ein Versäumnis aus C1-d4a berichtigt:** `overview.refresh` war eine wörtliche Doppelung von `action.refresh` in beiden Sprachen — der Gleichheits-Wächter in `en.spec.ts` kann das nicht finden, er vergleicht DE gegen EN **je Schlüssel**, nicht Schlüssel gegeneinander (ein globaler Doppelungs-Wächter wäre kein Ausweg: es gibt berechtigte Gleichlaute). **C1-d4 ist gemessen und in sechs Scheiben zerlegt** (≥242 statt geschätzt ~180 — dieselbe Richtung wie bei d3): d4a Fehler-Beschreiber + Übersicht ✅ · d4b/c Evaluation · d4d Analyse · d4e Lasttest/Sitzungen/Safety · **d4f die sechs sprachgebundenen Formatierer**. **Die Übersicht war in keiner Scheibe** — zweiter Fall derselben Art wie C1-d3d: der Schnitt zählte nach Rubrik, und die Startseite hat keine. **C1-d4a hat zwei Schulden eingelöst und eine neue gefunden.** Eingelöst: `describeApiError` nimmt jetzt den Übersetzer (28 Aufrufstellen in 20 Ansichten — der `simplify:`-Vermerk sagte 38, das waren 28 plus 10 im Test), `messageOf` in der MCP-Registry ist verschwunden. Die Schuld war **früher fällig als angesagt**: über `core/action-state.ts` erreichten deutsche Fehlersätze auch „Sicherung“, „Werksstand“ und „Voll-Backup“, die seit **C1-d3b** übersetzt sind. `AsyncData.error` ist dabei von gemerkt auf **abgeleitet** umgestellt worden (roher Fehler im Signal, Satz im `computed`), sonst bliebe eine stehende Meldung beim Sprachwechsel in der alten Sprache. Gefunden: **`core/format.ts` baut alle sechs Formatierer fest auf `'de-DE'`** — Datum, Relativzeit, Zahl, Prozent, Währung, 25 Aufrufstellen in 12 Dateien; auf Englisch steht „vor 3 Stunden“ neben „Last eval“. Als **C1-d4f** aufgenommen und nicht in d4a gezogen, weil diese Familie das **Locale** braucht und nicht den Übersetzer — eine eigene Entwurfsfrage. **Sechster eingefrorener Konstanten-Fall:** `overview-cards.ts` (Schicht-Karten) plus dessen `TABS`; neu daran ist, dass die Zahlen in Zeichenketten-Verkettung steckten (`${counts.patterns} Patterns` = deutsche Wortstellung, fest verdrahtet). Karten tragen jetzt Schlüssel **und die Zählungen, die sie benennen**, mit einem Wächter, der beides vergleicht — die Gegenprobe liess drei Tests fallen, darunter den, der dem Leser roh `{states} States` auf die Karte schreibt. **Werkzeug-Merksatz erweitert:** die d3d-Lehre gilt nicht nur für Block-*Ersetzung*, sondern auch fürs *Einfügen* — ein Import-Einfüger hinter „die letzte `import `-Zeile“ zerschnitt drei mehrzeilige Import-Anweisungen. **Bewusst gelassen:** die vier Erklär-Karten der Startseite (20 Texte, `<code>` mitten im Satz) sind der Gattung nach C1-d5. **C1-d3d war in keiner Scheibe** (Fund beim Bau von d3c, gebaut direkt danach): `views/curated-views.ts` trug **70** deutsche Texte auf Modulebene — zehn `intro` plus je Abschnitt `label` und `hint`. Der Unterschnitt hatte die *Komponenten* der Bedien-Ansichten gezählt, nicht die **Daten**, aus denen sie ihre Überschriften nehmen. Die Datei trägt jetzt nur noch Struktur (312 → 299 Z., 0 Texte); die Sätze stehen in `i18n/catalogue/curated.ts` (72 Schlüssel, samt der beiden aus `views.ts` gezogenen `curated.crumb`/`curated.empty`). C1-d3 ist gemessen worden (**~132** statt geschätzt ~150, 25 Dateien) und in drei Scheiben zerlegt; d3a und d3b sind davon die ersten beiden — **d3b brachte 73 statt der geschätzten ~41 Schlüssel**, die Schätzungen dieser Rubrik sind also durchweg zu niedrig gewesen (auch der Zeilenstand von `de.ts`: 292 gemessen gegen 230 gerechnet). Alle Merkposten aus C1-c sind abgearbeitet: `render.clearCache()` hängt am `[locale]`-Input der Shell (rot-grün belegt); die Quellen-Leser stehen jetzt in `public-api.ts`, weil das Studio der zweite Verbraucher ist; der Speicher-Schlüssel ist Parameter geworden (`boerdi_locale` vs. `boerdi_studio_locale`), weil beide Oberflächen denselben Origin teilen; und `I18n` nimmt seinen Basis-Katalog als Argument, damit der Kern keinen Katalog mehr kennt. **Der Studio-Umfang ist jetzt gemessen statt geschätzt: ~640 sichtbare deutsche Texte in 96 Dateien, das Siebenfache des Widgets** — daher fünf Scheiben statt einer; ~210 davon (C1-d5) sind technische Referenz-Prosa und ohne Rückbau streichbar oder zurückstellbar (Produktentscheidung, im C1-Plan als solche benannt). **Merkposten für C1-d4 ff.:** (0) **Der Katalog-Split ist mit C1-d3b erledigt** — mit C1-d3d neun Teile unter `i18n/catalogue/` (`frame` 26 · `views` 48 · `shared` 26 · `area-editor` 50 · `backup` 54 · `preview` 15 · `knowledge` 50 · `mcp` 19 · `curated` 72), beide Sprachen je Teil in einer Datei, `STUDIO_PARTS` als **eine** Liste von `{ de, en }`-Paaren. Neue Scheiben legen eine neue Teildatei an und hängen sie dort ein — der Wächter `catalogue/parts.spec.ts` deckt sie damit ohne Nacharbeit ab. Er prüft, was `en.spec.ts` **nicht** sehen kann: ein Schlüssel in zwei Teilen überschreibt beim `Object.assign` den anderen still, in beiden Sprachen gleich (rot-grün belegt). Ebenfalls aus d3b: vier wiederkehrende Beschriftungen liegen jetzt in `shared.ts` (`action.cancel/refresh/download/downloading`) — „Abbrechen" steht an 17 Stellen im Studio, „Aktualisieren" an 13; die noch nicht übersetzten Ansichten greifen in **ihrer** Scheibe darauf zu. Und der dritte Fall der Klasse „fertiger Text auf Modulebene" ist gefallen (`PREVIEW_CONTEXT_KINDS` trug deutsche Beschriftungen; jetzt `labelKey`/`fieldLabelKey`, ausgeschrieben statt zur Laufzeit zusammengesetzt, mit Existenz-Test) — nach `CONFIRM_LEAVE` (d3a) und dem Routen-Titel (d2) ist das ein Muster, nach dem in jeder Scheibe zu suchen ist. **C1-d3c fand den vierten** (`SOURCES` in `rag-ingest.component.ts`) und den grössten: `curated-views.ts` mit 70 Texten — als C1-d3d nachgezogen. Dort halten zwei Wächter das Schlüsselschema: jeder in `CURATED_VIEWS` genannte Schlüssel muss in **beiden** Katalogen stehen, und kein Abschnitt darf den `labelKey` eines anderen tragen (aus dem Katalog heraus nicht erkennbar, weil beide Sprachen ihn brav führen). **Werkzeug-Merksatz aus d3d:** strukturierte Quelltext-Umbauten in diesem Baum **ganz neu schreiben statt per Regex ersetzen** — ein `re.sub` über mehrzeilige Blöcke hat `curated-views.ts` verschluckt, und ohne Git gibt es kein `checkout`. Weiter aus d3c: **`StudioLanguageService.list()`** verbindet Aufzählungen über `Intl.ListFormat`, weil `gaps.join(' und ')` dieselbe fest verdrahtete deutsche Regel war wie `=== 1` vor d3a — ein übersetzter Binder wäre nur die nächste Satzbildung aus Bruchstücken gewesen. **Der `Translate`-Typ wohnt jetzt in `i18n/studio-language.service.ts`** (vorher im `schema-form`), sonst importierte `core` nach aussen statt nach innen. **`describeApiError` ist als einziger der drei Fehler-Beschreiber noch einsprachig** und mit `simplify:` markiert: er wird über `AsyncData` erreicht, das an **38 Stellen in 20 Ansichten** gebaut wird — alle davon C1-d4, dort gehört der Übersetzer durchgereicht. Bewusst **kein** optionaler Übersetzer mit deutschem Rückfall, der liesse die 38 Stellen hinter einer grünen Suite unübersetzt; `messageOf` in der MCP-Registry ist bis dahin seine übersetzte Zwillingskopie und verschwindet mit C1-d4. Und ein Bestandstest war **aus dem falschen Grund grün**: „lists every registered server" fand den Servernamen nur im `sr`-Anhang des Entfernen-Knopfs, weil er in `<input [value]>` steht und kein Textknoten ist — mit dem Knopfnamen in `aria-label` wurde er rot und prüft jetzt die Feldwerte. Dazu aus C1-d3a: der Zustands-Streifen `async-state` baute seinen Lade-Satz aus einem Verb hier und einem Substantiv **samt Artikel** aus 21 Aufrufstellen — das war **schon einsprachig falsch** („Der Lauf werden geladen …" an sechs Stellen), weil der Bestandstest nur den Plural übergab. Der ganze Satz ist jetzt ein Katalog-Eintrag mit `{label}`; die zehn Artikel in acht **C1-d4-Dateien** sind dabei entfallen. Mehrzahl läuft seit C1-d3a über `StudioLanguageService.plural()` (`Intl.PluralRules`, Suffixe `.one`/`.other`) — der in C1-d2 vertagte Snapshot-Satz in `overview.component.ts` kann damit in seiner Scheibe nachziehen. (1) **erledigt in C1-d2, und anders als hier vermutet:** die Registry trägt jetzt Katalog-**Schlüssel** (`view.<slug>.label`/`.desc`), nicht die deutschen Wörter — nur der **Slug** bleibt deutsch, weil er eine Adresse ist und ein Lesezeichen sonst beim Sprachwechsel ins Leere zeigte. Verbraucher waren **sechs**, nicht vier (zusätzlich `not-found` und die kuratierte Ansicht). Der Dokumenttitel musste von einer Konstante auf einen `ResolveFn` umgestellt werden, sonst fröre er in der Sprache ein, die beim Laden des Moduls aktiv war; **bekannte Grenze:** er wird erst bei der nächsten Navigation neu aufgelöst. Neuer Wächter `i18n/views-i18n.spec.ts`: jeder Registry-Schlüssel muss in **beiden** Katalogen stehen — ohne ihn zeigt eine Lücke den Schlüssel selbst als Beschriftung. (2) **jsdom meldet `navigator.language === 'en-US'`**, und der Browser ist im Studio die **zweitstärkste** Quelle — jede Suite mit deutschem Wortlaut muss `sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de')` setzen (kein globaler `navigator`-Stub: der träfe in Angular-Komponenten auch andere Leser). (3) `<html lang>` ist beim Studio **Ausgabe, nicht Quelle** (`index.html` liefert fest `lang="de"`, der Dienst schreibt dorthin) — wer die Rangfolge anfasst, darf sie nicht „auf vier Quellen vervollständigen". Die ursprüngliche Messung zur Einordnung: **Nutzer-Entscheid 2026-07-27: vertagt** — „erst den Chatbot zum Laufen bringen, i18n später nachrüsten". Die Abgrenzung ist dabei gemessen worden und muss nicht neu erarbeitet werden: **vier Textsorten, die nichts miteinander zu tun haben.** (1) **Oberfläche** Widget+Studio: 159 von 204 Dateien tragen deutschen Text — klassisches i18n, mechanisch. (2) **Backend-Meldungen** an Nutzer/Redaktion: ~34 Literale in `api/` (`greeting darf nicht leer sein`). (3) **Redaktioneller Inhalt** (Begrüßung, Quick-Replies, Tour, Personas, 57 Canvas-Typ-Labels): liegt in der DB über 35 Config-Bereiche ⇒ Schema-Ebene je Sprache + Studio-Pflege je Sprache + Migration der Bestandsdaten. (4) **Bot-Antworten**: ~150 Literale in Prompts (`tool_loop`, `classify_prompt*`, `response_prompt_pattern`, `eval/judge`, `quick_replies_llm`) ⇒ Prompt-Neubau plus Golden-/Eval-Baselines **je Sprache**, Abnahme nur mit echten LLM-Läufen. Gesamt 449 deutsche String-Literale im Backend (per AST gezählt, Docstrings ausgenommen — der reine grep-Wert 111 Dateien täuscht, weil Kommentare hier deutsch sind). **Technik ist damit auch schon entschieden:** `@angular/localize` scheidet aus (backt zur Bauzeit ein, ein Bundle je Sprache, Umschalten nur per Neuladen) ⇒ Laufzeit-Wörterbücher. ~~Und das zweite Wörterbuch gehört **nicht** ins Widget-Bundle: dessen §5.5-Budget hat bei ~413 von 420 kB nur ~7 kB Luft, die Sprachdatei muss nachgeladen werden.~~ **Falsch, korrigiert 2026-08-02:** die Zahl war veraltet — die Decke wurde am 2026-07-31 mit Material 3 auf 600/175 kB angehoben (`frontend/scripts/check-widget-budget.mjs:19`). Gemessen beim C1-b1-Gate: 493,69/600 kB roh, 143,88/175 kB gzip ⇒ **106 kB frei**. Der englische Katalog (~5 kB) gehört ins Bundle; **kein Nachladen**, damit auch kein Abruf-Fehlerpfad und kein Ladezustand im Umschalter. **C1-f2b3 ist fertig** (2358 pytest, ruff sauber, OpenAPI unveraendert): der Suchverweis bei Typ-Fokus (`services/turn_links.py`) und die zwei Ersatz-Beschriftungen, die der Lotsen-Injektor selbst formuliert (`services/guide_qr_injector.py`, jetzt mit einem `lang`-Parameter); Katalog 55 Schluessel je Sprache. **Der Schnitt wurde wieder vor dem Bauen geaendert** — diesmal nach der Frage, was auf Englisch SICHTBAR kaputtgeht (ein deutscher Satz erreicht den Nutzer) gegenueber dem, was nur STILL ausfaellt (ein Waechter greift nicht mehr). Nur das Erste ist f2b3; der Anti-Halluzinations-Waechter in `turn_links` und der Type-Focus-QR-Filter in `turn_persist` werden **C1-f2b4**, weil sie eine englische Grammatik brauchen, die ohne Live-Lauf nicht als richtig belegbar ist. **Der Fund:** `_type_focus_label` ist Anzeigetext UND Suchbegriff — es geht in den WLO-Vokabular-Lookup, der nur deutsche Canonicals kennt; blosses Uebersetzen haette den Typ-Filter still aus der Such-URL fallen lassen, auf die der Satz gerade verweist (dritte Wiederholung derselben Klasse nach dem `startswith`-Vergleich aus f2b1 und dem Loesungen-Waechter aus f2b2). Nebenher zwei ALT-Eigenheiten aktenkundig gemacht statt stumm repariert: das fehlende schliessende Anfuehrungszeichen hinter dem Thema, und die Ersatz-Beschriftung, die als „Quell Seite“ ohne Bindestrich erscheint, weil sie durch das Slug-Aufhuebschen laeuft. **C1-f2b4 ist fertig** (2374 pytest, ruff sauber, OpenAPI unveraendert): der Anti-Halluzinations-Waechter in `services/turn_links.py` und der Type-Focus-QR-Filter in `services/turn_persist.py` lesen ihre Wortlisten jetzt aus dem neuen `i18n/output_patterns.py` und ihre drei Ersatzsaetze aus `i18n/bot_text`. **Die Messung davor hat den Bau umgestellt:** weder NEU noch ALT hatten je eine Zeile Verhalten dieses Blocks festgehalten — er war allein durch Byte-Gleichheit abgesichert. Also zuerst elf deutsche Charakterisierungs-Tests auf dem unveraenderten Code, dann fuenf englische, die rot starten. **Dritter Ablageort, mit Grund:** nicht in den Katalog (ein Regex hat kein Uebersetzung, sondern ein Gegenstueck je Sprache) und diesmal auch nicht neben den Code wie in f2b2 — beide Dateien lesen dieselbe Wortliste, zwei Kopien haetten Text und Chips nach einer einseitigen Aenderung Verschiedenes behaupten lassen. Zwei bewusste Asymmetrien: die englische Wortliste traegt die deutschen Produktbegriffe (`Sammlung`/`Themenseite` ueberleben als Eigennamen), die englische Verbliste nicht (Verben uebersetzt das Modell). Deutsch bleiben `_type_words_re` (liest die NUTZER-Nachricht) und `_medientyp_classif` (anderswo der Filterwert der WLO-Suche) — beides C1-f2c. **C1-f2c-a ist fertig** (2389 pytest, ruff sauber, OpenAPI unveraendert), Umfang nach Nutzer-Entscheid auf das SICHERHEITS-Gate begrenzt: `services/safety/regex_gate.py` traegt jetzt englische Krisen-, Drohungs- und PII-Muster. **Gemessener Befund:** sieben englische Krisen-Formulierungen liefen auf `low` durch, waehrend die deutschen Entsprechungen `high`/M01 ausloesen; das einzige englisch aussehende Token (`suicid`) war TOT, weil die Wortgrenze dahinter „suicide“ und „suicidal“ ausschliesst. Die zweite Reihe traegt nicht ueberall: `moderation` ist mehrsprachig, entfaellt aber still ohne OpenAI-Schluessel (`b-api-academiccloud`). **Entscheidung: Vereinigung, nicht Umschaltung** — anders als bei C1-f2b4 darf dieses Gate die Sprache nicht kennen, wer `locale=de-DE` gesetzt hat kann englisch tippen. Der Spiegel hoert dort auf, wo der deutsche aufhoert (`hurt you` ist keine Drohung, weil „verletzen“ es auch nicht ist). Eine Asymmetrie bleibt und ist gepinnt: deutsche Komposita schuetzen den Unterrichtsfall („Suizidpraevention“ → `low`), englische Getrenntschreibung nicht („suicide prevention“ → M01) — bewusst NICHT per Ausnahme entschaerft. **C1-f2c-b ist fertig** (2404 pytest, ruff sauber, OpenAPI unveraendert): Typ-Erkennung (`domain/content_types`), Such-Intent (`domain/search_intent`) und LP-Intent (`domain/lp_intent`) lesen jetzt auch englische Nachrichten. **Drei verschiedene Schaeden:** die Typ-Erkennung traf nur Lehnwoerter (kein Filter, keine gefilterte Such-URL); der Such-Intent war kein Loch sondern ein FEHLVERHALTEN („what can you do?“ galt als echte Suchanfrage, also MCP-Suche + Karten in einer RAG-Antwort); beim LP-Intent blieb allein der Klassifikator-Pfad. **Der kanonische Typ-Schluessel bleibt deutsch** — er ist der WLO-Filterwert, nur die Stichwoerter wachsen. **Fund: auch `_lp_keywords` hat einen zweiten Auftrag** (dieselben Woerter legen das Thema frei) — nur die Stichwoerter zu ergaenzen haette „create a on photosynthesis“ als Suchbegriff erzeugt; die Schleife ist deshalb verhaltenserhaltend als `strip_lp_command_words` zu ihrem Vokabular gezogen und um englische Fuellwoerter ergaenzt. **Zwei Messungen haben naheliegende Eintraege verhindert:** `hey` steckt in `they` (auch mit Leerzeichen) und die Streichung arbeitet auf Teilzeichenketten, nicht auf Woertern. **C1-f2b5 ist fertig** (2418 pytest, ruff sauber, OpenAPI unveraendert): die Inline-Box (`domain/inline_rendering` + die zwei Aufrufstellen `turn_persist`/`direct_actions`). Zwei Schaeden in einem Modul — KORRUPTION beim Rueckfall-Titel ueber der Box („Lernpfad“/ „Material“/„Bearbeitete Version“/„Inhalt“, jetzt im Katalog) und AUSFALL bei zwei Waechtern ueber der EIGENEN Ausgabe (Titel-Regex und Floskel-Filter, jetzt Tabellen je Sprache; Umschaltung wie in f2b4, nicht Vereinigung). **Wichtiger als das Paket ist die Messung davor:** eine AST-Aufzaehlung ueber den ganzen Baum zeigt, dass die f2a-Notiz („~50 Saetze in sechs Modulen“) zum FUENFTEN Mal eine untere Schranke war — nutzersichtbares Deutsch steht auch in `preflight` (Safety-Abweisung), `api/chat` (interner Fehler + QR), `domain/facets`, `quick_reply_policy` („Hat das geholfen?“), `domain/tour`, `rate_limits` und den LLM-Rueckfallsaetzen. Das wird **C1-f2b6**. **Gemessener Nicht-Eingriff:** `_format_inline_doc_intro` bleibt deutsch — der Seed kennt gar kein `intro_text`, die Funktion laeuft heute nie, und ein englischer Zusatz in einem deutschen Redaktions-Template waere schlechter als der deutsche. **C1-f2b6 ist fertig und damit C1-f2b abgeschlossen** (2432 pytest, ruff sauber, OpenAPI unveraendert): die Einzeiler an den Raendern — `domain/facets` (Eingrenzungs-Chips + Filter-Hinweis), `quick_reply_policy` (Auto-Chip), `preflight` (Sicherheits-Abweisung), `api/chat` (interner Fehler + Wiederhol-Chip) und die vier LLM-Rueckfallsaetze. **Zwei der sieben Kandidaten waren gar kein Code-Text:** `domain/tour` und `rate_limits._DEFAULT_BLOCKED` sind Config-Vorgaben mit Code-Rueckfall — sie zu uebersetzen hiesse, die Sprache springt auf Englisch, wenn die Konfiguration fehlt ⇒ gehoeren zur Config-Schema-Frage. **Fund: der Chip und sein eigener Waechter sind EIN Stueck** — „Hat das geholfen?“ enthaelt „geholfen“ aus der Doublette-Stichwortliste; nur den Chip zu uebersetzen haette die Idempotenz still zerstoert. **Der blinde Fleck aus f2b5 ist sofort eingetreten:** das `except Exception` um den Box-Zweig schluckte den `TypeError` der Test-Attrappen — zwei deutsche Bestandstests wurden rot und haben es gemeldet, im Betrieb waeren die Chips still verschwunden. **Die Config-Schema-Frage ist entschieden und begonnen (C1-g).** Nutzer-Entscheid 2026-08-04: **Suffix je Schluessel** (`greeting` / `greeting_en`), zuerst **Begruessung + Widget-Start**. **C1-g1a (Backend) ist fertig:** Modell, Loader und Seed tragen die englische Fassung; das oeffentliche Buendel liefert BEIDE, weil das Widget die Sprache zur Laufzeit umschalten kann und es keinen zweiten Abruf gibt. Kein Vertragsbruch (`-> dict`). **Regel: leer heisst „nicht gepflegt“, nicht „leerer Text“** — der Loader setzt NICHT die deutschen Rueckfaelle ein, sonst waere „bewusst gleich“ nicht mehr von „fehlt“ zu unterscheiden. **Die Messung machte den Schnitt klein:** `/api/config/guide-mode` ist die einzige Boot-Config, `guide-mode` selbst traegt keine Prosa ⇒ **9 Zeichenketten**. Die Vorschaetzung („57 Zeilen“) war zum ersten Mal zu HOCH — sie lief ueber Schluesselnamen statt ueber den Verbraucher. **Ehrlich offen bei der Verifikation:** Docker lief nicht, 140 pg-Tests uebersprungen (darunter der Endpunkt-Test); die Loader-Ebene traegt die Belege. **C1-g1b ist fertig** (ui 572 · studio 878 · widget 39 · eslint sauber · Bundle 508,95/600 kB): das Widget waehlt je Schluessel ueber die reine `pickLocalized`. **Die Messung entschied den Bau:** ein Sprachwechsel verwirft nur den Renderer-Cache, laedt die Boot-Config NICHT neu und uebersetzt den Verlauf NICHT nach (C1-c). Also gehoert die Wahl an den ORT DER VERWENDUNG: Chips und Kopfzeile als `computed` (folgen dem Umschalter), die Begruessung einmalig als NACHRICHT (behaelt ihre Sprache, wie jede andere Nachricht). **Fund: der Tour-Chip wird per TEXT verglichen** — nach dem Umschalten stuende der deutsche Chip weiter in der Blase, verglichen wuerde gegen die englische Fassung, und der Klick startete keine Tour. Geloest nicht durch besseres Nachfuehren, sondern durch Aufloesen der Kopplung: gegen BEIDE Fassungen vergleichen. **C1-g2a ist fertig** (pytest 2447/4 skipped, ruff sauber, OpenAPI unveraendert, studio 878): die 15 Lotsen-Beschriftungen aus `02-domain/guide-rules.yaml` tragen ein `label_en`, und `find_guide_match(message, lang)` waehlt. **Gewaehlt wird im ZUG, nicht beim Laden** — `_COMPILED` ist ein Prozess-Cache, die Sprache gehoert zum Zug; der kompilierte Eintrag traegt deshalb beide Beschriftungen mit. Neu: `i18n/pick_localized`, der Backend-Zwilling von `pickLocalized`. **Fund: `rag_area_rules` in derselben YAML hat KEINEN Leser** (Loader + Studio-Formular ja, `find_rag_area_match` nutzt die hartkodierte `_RAG_AREA_URLS`) — 8. Fall „dokumentiert ohne Konsumenten“, ALT-verbatim; dort wurde bewusst kein `label_en` angebaut. Der Lauf schliesst auch die g1a-Luecke: mit gestartetem Compose-PG liefen die 139 pg-Tests wirklich. **C1-g2b ist fertig** (pytest 2455/4, ruff sauber, OpenAPI unveraendert, studio 878): `ContextPill.label_en` + `ContextActionsBlock.greetings_en`, gewaehlt im Zug ueber `environment.locale`. **Fund: 9 der 14 Chips sind `kind: text` — ihre Beschriftung IST die Nachricht, die der Klick sendet** und danach klassifiziert wird; hier ist also NICHT-Uebersetzen die Gefahr (umgekehrtes Vorzeichen zu f2b4/f2b5). Moeglich nur, weil C1-f2c-b die Heuristiken ueber der Eingabe schon zweisprachig gemacht hat. `greetings_en` ist ein PARALLELES FELD, kein Schluessel-Suffix — die Schluessel von `greetings` benennen Seitenarten, dort gehoert keine Sprache hinein. **Eine falsche Sorge wurde von der Messung widerlegt:** die handgeschriebenen Routen `PUT /config/welcome` + `/config/context-actions` bauen ihr YAML feldweise neu und liessen die `*_en` fallen — aber KEIN Studio-Bauteil ruft sie auf; das Studio speichert ueber die generische, schema-getriebene `PUT /config/data/{area}`, die das ganze Dokument ersetzt und gegen das Bereichsmodell validiert (2 neue Round-Trip-Tests). **Nachtrag, vom Nutzer entschieden (Felder nachziehen, Vertrag neu erzeugen):** die beiden schmalen Alt-Routen tragen jetzt `greeting_en`, `quick_replies_en`, `tour_reply_en`, `greetings_en` und `label_en` mit. Rein additiv (optionale Felder, leere Vorgabe), deshalb bricht kein Aufrufer; `docs/api/openapi-v1.json` wurde bewusst regeneriert — der Waechter ist eine Drift-Warnung, kein Verbot („If deliberate, regenerate“). Serverseitig mergen wurde NICHT gewaehlt: das widerspraeche `api/config.py:274-278` („eine Schreibsemantik, nicht zwei“). Auf der englischen Seite gibt es bewusst KEINE Pflichtpruefung (leer = nicht gepflegt). pytest 2458/4. **C1-g2c ist fertig** (pytest 2465/4, ruff sauber, OpenAPI unveraendert, studio 878): Drosselungs-Satz (`blocked_message_en`) + die zwei Policy-Hinweise (`disclaimer_en`). **Der Policy-Hinweis brauchte KEIN Feld** — `PolicyRule.effect` ist ein freies Dict, der Schluessel reist als ungepinnter Wert mit (`api/config.py:266-272`); erster Bereich dieser Reihe, in dem die zweite Sprache nichts am Schema kostet. **Reihenfolge zaehlt: erst waehlen, dann entdoppeln** — `assess_policy` entdoppelt ueber den TEXT, zwei Regeln duerfen denselben englischen Hinweis tragen. `_DEFAULT_BLOCKED` bleibt einsprachig (Notbremse, kein Pflegeort); `preflight` loest die Sprache jetzt EINMAL am Knoten-Anfang auf, weil die Drosselung sie vor dem Sicherheits-Zweig braucht. **C1-g2d ist fertig** (pytest 2475/4, ruff sauber, OpenAPI unveraendert, studio 878): die Webseiten-Tour, **66 englische Schluessel** statt der geschaetzten ~50. **Der Schnitt: die Sprache wird EINMAL auf die Config angewandt** (`domain/tour_i18n.localize` an der Knoten-Grenze), statt sie durch die ~15 Lesestellen der ALT-Zustandsmaschine zu faedeln — `domain/tour` bleibt unberuehrt. **Fund: das Gruppen-Matching ist schon eine Vereinigung**, weil `synonyms` bewusst deutsch bleibt und jede der 11 Gruppen ihre deutsche Beschriftung dort ohnehin fuehrt. **`start_label` bekommt KEIN englisches Feld — es hat null Leser in NEU und in ALT** (10. Fall „dokumentiert ohne Konsumenten"). Nur 5 Modellfelder noetig, die uebrigen 45 reisen in freien Dicts (`steps`/`entry`/`angebote`). **C1-g2e ist fertig — damit ist C1-g2 GESCHLOSSEN** (pytest 2519 passed, 4 skipped, ruff sauber, OpenAPI additiv erweitert, studio 878): 19 Typ-Beschriftungen plus **15 englische Aliase**. **Der Fund: die Beschriftung ist der Chip-Text UND das Erkennungswort** — der geklickte Chip kommt wortgleich zurueck und wird ueber `type-aliases.yaml` wieder zur Typ-ID; ohne Alias waere der Typ still auf `auto` gefallen UND das englische Typ-Wort im Thema stehen geblieben (`canvas_fast_path` schneidet es mit denselben Aliassen heraus). Neuer Waechter `tests/test_material_type_labels.py` prueft gegen den ECHTEN Seed, dass jeder Chip-Text seinen eigenen Typ wiederfindet — roter Lauf 20 gruen (alle deutschen) / 19 rot. **C1-g2e loest ausserdem einen Kompromiss aus C1-f2b6 auf:** der englische Satz sagte `write "Automatisch"`, weil nur das deutsche Wort ein Alias war; jetzt sagt er `"Automatic"`. Einsprachig bleiben mit Grund: `structure` (Prompt/Klasse B), `_DEFAULT_MATERIAL_TYPES` (Notbremse), `lrt_to_type` (edu-sharing- Vokabular). Backlog-Befund: die Notbremse kennt 18 Typen, der Seed 19 (`vokabelliste` fehlt). Der Schnitt samt Messung (825 Prosa-Werte im Seed, davon die Masse Klasse C) steht in `docs/plans/2026-08-02-c1-i18n.md`. |
| ~~C9~~ | ~~SSE sendet keine `phase`-Ereignisse~~ **ERLEDIGT 2026-07-27** | **Gebaut + live belegt.** Neu: `obs/progress.py` (`TurnProgress`, Sink-Callback, Sink-Ausnahmen geschluckt wie ALT `Tracer._emit`; `NO_PROGRESS` als zustandsloser Default) — bewusst **Transport, kein Rekorder**: `debug.trace` bleibt leer, das ist weiter Sache des vertagten Tracer-Subsystems. DI wie `on_token`: `build_turn_graph(progress=…)` → `functools.partial` in genau die vier meldenden Knoten (kein Modul-Global). `_stream_turn` hängt eine `asyncio.Queue(200)` davor und zieht sie leer, während der Turn läuft (ALT-Schleifenform `chat.py:448`); der Sink hält **einen Platz für `_DONE` frei**, sonst könnte eine Fortschritts-Flut das Abschluss-Signal verdrängen und den Zug um ein Keepalive-Intervall verzögern. **Live gegen `boerdi_p11` + OpenAI/gpt-5.4-mini gemessen:** `connected 0,1s → safety_classify 0,1s → context/policy/pattern 4,0s → wlo_search 4,0s → response 6,7s → query_meta 9,4s → result` (3 Karten, M05). Im ersten Lauf stand `wlo_search` **24 Sekunden** — genau die Spanne, in der vorher gar nichts kam. **Zwei Messbefunde, die den Bau geändert haben:** (a) Die Map hat **acht** `step`-Werte, nicht neun — der neunte Ladetext ist `connected`, den NEU schon sendet. (b) **ALTs `safety_classify`-Label ist in ALT selbst tot**, doppelt: ALT ruft `parallel_group("safety_classify_**memory**")` (`chat_pipeline_phases.py:54`), also einen anderen Namen als die Map kennt, und `ParallelGroup` emittiert **nur `end`**, das `formatPhaseLabel` verwirft. NEU sendet deshalb `start` unter `safety_classify` — dem Namen, den der Konsument **und ALTs eigenes `trace_service`-Docstring-Beispiel (Z. 96)** nennen. Bewusste, benannte Abweichung vom ALT-Code zugunsten der ALT-Absicht. **`end`-Ereignisse sendet NEU nicht** (`simplify:`): der einzige Konsument verwirft sie, und ihr Nutzlast-Zweck (`duration_ms` für die Studio-Trace) hängt am gedroppten Tracer. **Automatischer Sender↔Konsument-Abgleich** (Quelltext gegen `phase-label.ts`): 7 von 8 Schritten bedient, **kein emittierter Schritt ohne Label**. **Offen bleibt bewusst `topic_content`** — NEUs `_resolve_m16_topic_page_view` hat keinen tracer-Parameter; ihn nachzurüsten hieße zwei Verbatim-Port-Signaturen (`topic_pages` + `turn_persist`) zu ändern, für ein Label, das nur auf dem M16-Pfad und erst nach der fertigen Antwort erschiene. `query_meta` war dagegen fast gratis: der `_NullTracer` in `persist.py` wurde zum weiterleitenden `_ProgressTracer`, der Verbatim-Port blieb unangetastet. Belege: Backend **2160 pytest** (+22), ruff sauber, `export_openapi.py --check` unverändert; Rot-Grün gegengeprüft (Emissionen entfernt ⇒ Tests fallen). |
| ~~C8~~ | ~~`web_links` ist als `list[WebLink]` deklariert, geliefert werden dicts~~ **ERLEDIGT 2026-07-31** | **Der Ort war ein anderer als hier vermutet.** Die alte Zeile verortete den Defekt bei `services/turn_links` („läuft als Element eines 7-Tupels", deshalb „kein Einzeiler"). **Gemessen statt geglaubt:** `ChatResponse(web_links=[dicts])` validiert sauber zu `WebLink` — der Endpunkt-Vertrag war nie das Problem, und `TurnContext.web_links` (`graph/state.py:159`) wird **von niemandem geschrieben**, ist also ein totes Feld. Die echte Quelle ist `services/widget_postprocess.py:763`: die Rückgabe geht über `resp.model_copy(update={…})`, und **`update=` überspringt die pydantic-Validierung**. Oben (Z. 703/716) werden die Links absichtlich zu dicts gemacht, damit die Merge-/Dedup-Logik `l.get("url")` einheitlich über bestehende `WebLink`-Objekte UND neue dicts aus `_extract_web_links_from_text` laufen kann — ohne Rück-Validierung landen genau diese dicts im `list[WebLink]`-Feld. **Fix: ein Listen-Comprehension mit `WebLink.model_validate`** — der befürchtete 7-Tupel-Umbau war nicht nötig. Rot-grün belegt: 2 neue Tests in `test_widget_postprocess_orchestrator.py`, einer pinnt den Typ, einer das Symptom (`model_dump()` unter `warnings.simplefilter("error")`); mit zurückgenommenem Fix fallen beide mit exakt der Log-Warnung. Backend **2082 passed** (142 pg-Skips, kein DB-Pfad berührt), ruff sauber, `export_openapi.py --check` unverändert. **Lehre für diese Rubrik:** die Ursachen-Vermutung einer offenen Zeile ist eine Vermutung, kein Befund — sie hat den Aufwand hier um Größenordnungen überschätzt und in die falsche Datei gezeigt. |
| P11 | Migration & Cutover | §9-Schritte (Config-Import-CLI-Lauf, RAG-Re-Ingest, Parallelbetrieb, Golden-A/B, Widget-Umschaltung, ALT-Stilllegung). Setzt P10 voraus und ist zum großen Teil Nutzer-Domäne (echte Läufe gegen echte Instanzen). Schritte 1+2 erledigt (2026-07-31); der **Code**-Anteil von Schritt 4 steht seit 2026-08-09: `evals/compare_golden.py` (Abweichungs-Report pro Flow/Turn, siehe P11-Schritt 4a). Offen bleiben die beiden echten Läufe, die Redaktions-Fahne sowie Schritt 5+6. |
| ~~K1–K5~~ | ~~Kostenüberwachung (Token je Sitzung/Zeitraum, Preise, Abrechnung)~~ **✅ ERLEDIGT 2026-08-12** | **Komplett gebaut. Aufgenommen 2026-08-11; K1 (K1-0, K1a–K1f) + K2 (Tabelle, Migration 0002, Schreibpfad) + K3 (Preise) + K4 (Auswertung) am selben Tag, K5 (Studio-Ansicht „Kosten") am 2026-08-12.** **K5 zerfiel in zwei Teile, weil der Plan etwas verlangte, das es noch nicht gab:** „die teuersten Sitzungen" war in K4 nicht gebaut (dort stehen nur „je Sitzung" und „je Zeitraum") — also erst K5a (Backend: `sessions` in der Zeitraum-Antwort; die Rangfolge entsteht in **Python**, weil der Preis in der Config und nicht in der DB lebt, ein `ORDER BY` könnte nur nach Token sortieren) und dann K5b (die Ansicht). **K5a kostete KEINEN Vertragszusatz** — gemessen statt vermutet: die 200er-Antwort der Kosten-Routen ist im eingefrorenen Dokument `{"type":"object","additionalProperties":true}` ohne ein einziges gepinntes Feld, ein neuer Schlüssel ändert sie also nicht; eine dritte Route hätte die §5.5-Ausnahme ein zweites Mal ausgegeben, für Zahlen, die dieselbe Ansicht im selben Fenster ohnehin zusammen liest. **Zwei Funde aus K5:** *das Tagesende* — der Server liest ein blosses Datum als Mitternacht, „bis heute" hätte den ganzen heutigen Tag **stumm** verloren (eine kleinere Summe sieht aus wie eine kleinere Summe), deshalb schickt die Ansicht `T23:59:59.999Z`; und *ein Test, der in der Rot-Probe grün blieb*, weil die Sitzungsnamen (`k5o-gross`/`k5o-klein`) alphabetisch zufällig dieselbe Reihenfolge ergaben wie die erwartete. **Die §5.6-Ansichtszusage ist beim 20. Eintrag nicht hochgezählt, sondern geteilt worden** — `PORTIERT` (16 aus ALT) und `OHNE_ALT_VORBILD` (4, je mit Grund) in `studio-views.spec.ts`, samt Gegenrichtungs-Test; dieselbe Disziplin wie `NEUE_BEREICHE` bei K3. Geld bleibt bis zum Bildschirm Text: `core/format.ts::formatMoney` entscheidet die Nachkommastellen an den **Ziffern der Zeichenkette** (zwei normal, mehr nur wenn zwei eine echte Zahl auf `0,00 €` rundeten) und fängt eine ungültige `currency` aus der Studio-Config ab, die sonst per `RangeError` die ganze Ansicht geleert hätte. Belege K5: pytest **3003/4** · `ng test studio` **922** · `ng test ui` **701 unverändert** (kein Kostenwert im Widget) · `check:tokens` grün · `--check` grün. Bewusst offen gelassen: `/api/usage/session/{id}` hat nach K5 keinen Verbraucher in der Oberfläche — die Sitzungsliste beantwortet die Frage für die Sitzungen, auf die es ankommt. **K4 hat den eingefrorenen OpenAPI-Vertrag zum ersten Mal bewusst neu erzeugt** (86/114 → 88 Pfade/116 Operationen, genau +2/+2, Nutzer-Entscheid §5.5): die benannte Liste dazu ist `docs/api/bewusste-vertragszusaetze.md`, bewacht von `tests/test_openapi_additions.py` (in drei Richtungen rot gesehen). Wer künftig eine Route hinzufügt, trägt sie dort ein, statt die eingefrorenen Zahlen nachzuziehen. Eigener Plan mit Messung, Architektur und ausführbarer Aufgabenliste: `docs/plans/2026-08-11-kostenueberwachung.md` — dort anfangen, nicht hier. **K3 brachte den 36. Config-Bereich** (`01-base/pricing`, ohne ALT-Gegenstück) — die Zusage „genau 35" bleibt erhalten, der Zusatz steht getrennt und mit Grund in `NEUE_BEREICHE` (`tests/test_config_models.py`), Vorbild `BEWUSST_EINSPRACHIG`/`OHNE_BUCHUNG`. Zwei begründete Abweichungen dort: Geld steht als `float` im Bereichsmodell und wird erst in `domain/pricing.py` zu `Decimal` (ein `Decimal`-Feld verschemat pydantic als `anyOf`+`pattern`, was den Studio-Editor auf ein JSON-Textfeld zurückwerfen würde — der Build brach mit `TS2353` ab), und Präfix-Treffer enden an der `-`-Grenze (sonst bepreist `gpt-5` still auch `gpt-55`). Kurz: das Fundament (`obs/usage.py`, prompt/completion/cached je Zug, in `messages.debug` gespeichert) ist gegen echtes LiteLLM geprüft, **lief aber gar nicht** — der Merkposten hatte keinen Erzeuger (M0, ✅ behoben in K1-0; siehe Abschnitt „2026-08-11 (2)"). ✅ Ebenfalls erledigt: (b) Reasoning-Token (K1a) und **alle fünf ungebuchten Module** (K1b–K1e: `llm_learning_path`, `llm_curation`, `canvas_service`, `safety/legal` je auf ALLEN Aufrufwegen — zwei mehr, als die Messtabelle nannte — plus `mcp/arg_resolvers`, das den Merkposten per `ContextVar` aus dem setup-Knoten bekommt statt durch 25 Aufrufstellen gefädelt). Es fehlen (c) Aggregation und (d) Preise. Nutzer-Entscheide stehen: eigene Tabelle `usage_events` ohne Rückfüllung, Umfang „Chat vollständig", Preise als Studio-Config. **Keine offene Frage mehr** — K1e ist am 2026-08-11 gemessen und entschieden; die OpenAPI-Vertragsfrage ebenso (zwei eigene Routen unter `/api/usage/`, einmal neu erzeugen, mit benanntem Eintrag „Bewusste Vertragszusätze"). Zwei Dinge gehören dem Nutzer: ein Live-Zug als Beleg, dass die Zahlen im Betrieb ankommen, und der Nebenbefund fehlender Vokabular-Aliase (`teacher`/`learner`/`Gymnasium`/`Oberstufe`), der heute je einen LLM-Aufruf kostet. |
| ~~E4~~ | ~~Verwaister Schreib-Vorgang verfällt nicht~~ **✅ ERLEDIGT 2026-08-12** | **Gebaut; Beleg im Abschnitt „2026-08-12 — E4“ oben.** Frist als `TOKEN_TTL_SECONDS` + `is_expired` in `domain/write_confirm.py`, die Uhr reicht die Naht herein (`domain/` ist rein). Vorbild war `services/page_context.py`, das `_resolved_at` schon genauso ablegt und prüft — keine Migration, JSONB. **Fund beim Bauen:** die bestehende Protokollzeile hätte gelogen („Argumente weichen ab“, während sie übereinstimmen), also ein eigener Zweig und ein Test, der beide gegeneinander pinnt. pytest 3010/4, ruff sauber, Vertrag unverändert. Ursprünglich: **Aufgenommen 2026-08-11**, als Folge davon, dass der Merkposten des Bestätigungs-Walls jetzt wirklich gespeichert wird (Abschnitt „2026-08-11" oben). Vorher war der Fall unerreichbar, weil nichts überdauerte. Jetzt gilt: legt der Nutzer eine Änderung an und verfolgt sie nicht weiter, bleibt der Eintrag bis zum Sitzungsende liegen — entfernt wird er nur auf dem Bestätigungspfad oder durch eine neue Vorschau desselben Werkzeugs. Fragt er Stunden später zufällig **exakt** dasselbe Vorhaben erneut an (gleicher Fingerabdruck), wird der alte Schlüssel eingesetzt, der Server lehnt ihn ab (gilt zehn Minuten) und antwortet mit einer neuen Vorschau: ein überflüssiger Werkzeugaufruf, keine falsche Änderung, **kein Sicherheitsloch** (die Frist gilt serverseitig). Naheliegender Schnitt: Zeitstempel in `remember_pending`, Prüfung in `token_for` — dann steht die Frist an einer Stelle statt implizit. Achtung: `domain/` ist rein und hat keine Uhr, die Zeit muss der Aufrufer hereinreichen. |
| ~~C6~~ | ~~`rate_limits` im Studio ohne Wirkung~~ **ERLEDIGT 2026-07-31** | **Nutzer-Entscheid: „integrieren und nutzen"** — also den Verbraucher bauen, nicht den Block entfernen. Neu: `services/rate_limits.py` (`check_rate_limit` → `RateVerdict`) und der Aufruf am **Kopf** von `graph/nodes/preflight.py`, vor dem Direkt-Aktions-Filter. Das ist ALTs Platz und Reihenfolge (gemessen: `chat_turn_setup.py:128-135` speichert erst die Nutzernachricht, dann `_run_preflight_guards`; NEUs Graph fährt `persist_user → preflight` — deckungsgleich, ebenso `client_ip = peer_ip or page_ip`). Ein Aufrufpunkt deckt `/api/chat` **und** `/api/chat/stream`, weil beide denselben Graphen fahren. `log_safety_event(rate_limited=True)` ist damit verdrahtet — das Studio zeigt den Zähler seit jeher an (`safety-logs.component.html:46` + Abzeichen), er kann sich jetzt bewegen. **Bewusst NICHT ALTs Zähler:** ALT hält ein modul-globales `dict` aus Deques — verboten (Regel 3) und bei N Replicas schlicht falsch, weil jedes Limit effektiv N-fach gälte. Stattdessen der Moving Window von `limits` (bisher nur transitiv über slowapi da, jetzt explizit deklariert, MIT) über **denselben** `RATE_LIMIT_STORAGE_URI` per `async+`-Präfix — `memory://` je Prozess, `valkey://` geteilt; dass beide `MovingWindowSupport` implementieren, ist geprüft. ALTs `_sweep_stale`-Hausputz entfällt dadurch ersatzlos (Verfall ist Sache des Speichers). **Zwei Dinge bewusst nicht portiert:** `reset_session()` und das Feld `retry_after` — beide haben **in ALT selbst keinen Aufrufer** (gemessen), sie zu portieren wäre genau der Defekt, den C6 behebt. **Zwei Abweichungen mit Grund:** ein leerer `blocked_message` (Modell-Default `""`) fällt auf ALTs Satz zurück statt eine leere Blase zu zeigen; und der Log bekommt die auslösende Fenster-Kennung als `reasons: ["rate_limit:session_minute"]` mit — sonst sehen alle gebremsten Zeilen gleich aus und niemand weiß, ob das Sitzungs- oder das IP-Fenster zu eng ist. **Ausfall des Zählers bremst nicht die Nutzer:** ist der Speicher unerreichbar, geht der Zug durch (mit Warnung) — das HTTP-Limit bleibt der harte Boden. **Der Seed liefert `enabled: true`,** die Bremse ist nach dem Import also scharf (30/min bzw. 600/h je Sitzung, 1200/min bzw. 30000/h je IP). Genau dafür gibt es einen Test, der den **echten Seed** durch die **echte** Schlüssel-Normalisierung und das **echte** Bereichs-Modell schickt und die vier Fenster prüft — die Lehre aus P11, wo zwei Attrappen nach dem Code statt nach der Wirklichkeit gebaut waren. Belege: Backend **2238** (15 neue), ruff sauber, `export_openapi.py --check` unverändert (keine API-Fläche berührt), `pip-licenses` limits 5.8.0 MIT, `uv lock` 149 Pakete. Zwei falsche Docstrings mitkorrigiert (`api/ratelimit.py` und `tests/test_ratelimit.py` behaupteten beide, die Config-Bremse sei portiert). **Nicht belegt:** ein Live-Lauf gegen echten Verkehr. Ursprünglicher Befund: **Gemessen 2026-07-27.** Der Safety-Config-Block `rate_limits` (per-Session-/per-IP-Fenster, Whitelist, Sperrtext) ist im Schema und damit im Studio editierbar — gelesen wird er von **keiner Zeile**; ALTs in-band-Bremse wurde nicht portiert. Zusätzlich kann das Safety-Log-Feld `rate_limited` nie 1 werden, weil es niemand setzt. Zwei Wege: den Block ehrlich machen (Verbraucher bauen, also ALTs Fenster nachziehen) oder ihn aus dem Schema nehmen und in der Oberfläche benennen. Beides ist eine Produktentscheidung, deshalb hier und nicht im Code. Die falsche Docstring-Zeile ist bereits korrigiert. |
| ~~W3~~ | ~~M16 sucht Themenseiten über die falsche Quelle~~ **ERLEDIGT 2026-07-30** | **Gebaut, Beleg im Abschnitt „W3 ✅ 2026-07-30" oben** (A 3/7 mit einer falschen Seite vs. B 7/7; Live-Abnahme 7/7 mit zwei MCP-Calls je Zug). Die Zeile bleibt durchgestrichen stehen, weil ihr Befund erklärt, warum der Themenseiten-Pfad vorher unzuverlässig wirkte. Ursprüngliche Fassung: **Gemessen 2026-07-30 in der W2-Abnahme.** `_resolve_m16_topic_page_view` holt seine Kandidaten aus `search_wlo_collections(query, maxResults=8)`. Diese Quelle ist instabil: in **6 von 9** Läufen war die gesuchte Themenseite gar nicht dabei oder kam ohne `topic_page_url` — bei identischer Abfrage, Minuten auseinander. Die dedizierte `search_wlo_topic_pages` fand sie im selben Zeitraum **6 von 6** Mal. Sichtbare Folge: „Themenseite Chemie existiert (7 Schwimmlinien), der Resolver meldet trotzdem keine". Betrifft ALT identisch (W2-A/B: 0 Ergebnis-Abweichungen), ist also kein Regress, sondern geerbte Schwäche. Umbau ist mehr als ein Schlüsseltausch: der dedizierte Tool-Pfad hat den in `_topic_pages_with_warmup` dokumentierten „enger Query-Matcher"-Effekt, der Resolver müsste also über diesen Helfer statt direkt gehen — plus Rückfall auf die Sammlungs-Suche, damit nichts verloren geht. Eigenes Paket. |
| W4-Rest | ~~Tool-Kopie im Client veraltet~~ **✅ ERLEDIGT mit W9a/W9b/W9c (2026-08-01)** — alle drei unten genannten Entscheidungen sind gefallen und umgesetzt: (1) sechs Werkzeuge aufgenommen und je in ein Muster verdrahtet, `search`/`fetch`/WebUI-Varianten bewusst draußen, `find_wlo_skills` zurückgestellt (serverseitig nicht konfiguriert + Anweisungs-Kanal); (2) die Beschreibungen sind zusammengeführt, drei zusammengelegte Fähigkeiten geprüft (zwei übernommen, `includeParents` abgelehnt — liefert für Inhalte nichts); (3) statt eines netzabhängigen CI-Wächters gibt es jetzt zwei netzfreie: Muster-Erreichbarkeit und Parameter↔Argumentmodell. Details in den Abschnitten W9a–W9c oben. Der ursprüngliche Text zur Nachvollziehbarkeit: | **Abgleich liegt vor (W4-1, Abschnitt oben): 23 Server-Tools, 12 bei uns, 0 Phantom-Tools, 0 fehlende Pflichtfelder, 12/12 Beschreibungen gedriftet.** Die zwei Sachfehler daraus sind gefixt. **Stand nach W7b (2026-07-31):** der neue Server ist live (23 Tools), `get_wlo_content_text` ist seit M17 verdrahtet — es sind also noch **zehn** ungenutzte. Ein Wächter hält seither fest, dass die Registry jedes angebotene Werkzeug kennt. Offen bleiben drei Entscheidungen: (1) **welche der 10 ungenutzten Tools** der Bot bekommt (`fetch`, `search`, `find_wlo_skills`, `get_collection_stats`, `get_compendium_text`, `get_node_breadcrumb`, `get_related_content`, `get_wikipedia_summary`, `lookup_wlo_publishers`, `search_wlo_within_collection`) — Produktentscheidung, je Tool zusätzlich Validierung/Parser/Prompt-Führung. **`get_wikipedia_summary` ist seit W8 (2026-08-01) verdrahtet** — deterministisch aus `canvas_service`, nicht über das LLM; es dem Modell *zusätzlich* anzubieten wäre ein zweiter Weg zur selben Auskunft und bräuchte eine Vorrang-Regel. Nutzer-Vorgabe 2026-07-31 für die übrigen: `search` und `fetch` bleiben draußen (Doppelgänger für den OpenAI-GPT-Store), die WebUI-Varianten ebenfalls — alle anderen kommen rein. (2) **Die 12 Beschreibungen zusammenführen statt kopieren** — unsere tragen boerdi-eigene Führung, die der Server nicht kennt. (3) **Ein automatischer Drift-Wächter** (Vorbild `export_openapi.py --check`) bräuchte Netz in der CI. Unser LLM sieht weiterhin nur die hartkodierte Liste (`_select_active_tools`, `generate.py:107`); `discover_server_tools` speist nur die Studio-Ansicht, ein „neu verbinden" ändert nichts (dem MCP-Entwickler so zurückgemeldet). |
| ~~C5~~ | ~~Lasttest-Ressourcen: psutil-Abtastung~~ **ERLEDIGT 2026-07-31** | **Nutzer-Entscheid: Abhängigkeit aufnehmen.** Gebaut sind die vier genannten Schritte: (1) `psutil>=7.1.3` in `pyproject.toml` — installiert 7.2.2, **BSD-3-Clause**, vom Lizenz-Gate erlaubt (`pip-licenses` geprüft); (2) `_sample_resources` als ALT-Port (0,5-s-Takt, `cpu_percent`-Priming, Messfehler beenden die Abtastung NICHT); (3) `peak_rss_mb`/`peak_proc_cpu_pct` zurück in `_summary` — `samples` ist dort **Pflicht-Parameter**, damit ein vergesslicher Aufrufer auffällt statt still `0.0`-Spitzen zu melden; (4) Studio zeigt Spitzen + Messpunkt-Zahl in der Detailansicht und die Speicher-Spitze in der Liste. **Zwei Entscheidungen über den Port hinaus:** die Abtastung schreibt direkt in `result["resource_samples"]`, damit jedes Zwischen-`_persist` den bis dahin gemessenen Verlauf mitnimmt (das Studio pollt und soll die Kurve wachsen sehen); und der Sampler wird im `finally` **vor** dem letzten `_persist` gestoppt und abgewartet — sonst hängt er während der Serialisierung an die Liste an, und nach einem Fehlschlag liefe ein verwaister Task endlos. **B5s Lehre bewusst erhalten:** ein Lauf ohne Messpunkte zeigt „Keine Messpunkte" statt „0 MB" (0 ist dort keine Aussage), und beide umgeschriebenen B5-Tests behalten ihren NaN-Schutz wörtlich — der galt dem Rechenfehler, nicht dem Feature. Belege: Backend **2223** (3 neue), ruff sauber, `ng test studio` **735** (1 neuer), lint, `ng build studio` 297,50 kB. **Nicht belegt:** ein echter Lasttest-Lauf (feuert die reale LLM/MCP-Pipeline — Nutzer-Domäne). Ursprüngliche Fassung: **Backend-Entscheidung zuerst, deshalb hier und nicht in der B-Reihe.** `services/loadtest.py` hat ALTs psutil-Abtastung bewusst nicht portiert (Begründung im Modul-Docstring: `psutil` ist keine boerdi-chat-Abhängigkeit und `pyproject.toml` war außerhalb des Slice). Folge, in B5 gemessen: `resource_samples` ist immer `[]` und `_summary` liefert vier Schlüssel ohne Spitzenwerte — es gibt **weder eine Zeitreihe noch Spitzen**. Das Studio benennt das seit B5 ehrlich (vorher „Spitze NaN MB"). Wer die Sparklines will, braucht: (1) `psutil` in `pyproject.toml` — eine Abhängigkeits-Entscheidung des Nutzers, (2) die Abtast-Schleife in `execute_load_test` (ALT: alle 0,5 s), (3) `peak_rss_mb`/`peak_proc_cpu_pct` zurück in `_summary`, (4) im Studio die Anzeige plus das Diagramm über `resource_samples` — der Typ dafür steht schon. |

## Nutzer-Domäne (nicht von mir zu erledigen)

`git init` + Commits · ein echter CI-Lauf — **seit P10-5 gilt das für zwei
Workflows**: `ci.yml` und das Image-Gate `image.yml`, dessen Smoke-Logik lokal
gegen echtes Docker belegt ist, dessen YAML aber noch nie durch GitHubs Parser
gelaufen ist · Compose-Live-Lauf · Screenreader-Durchgang
und 200-%-Zoom am echten Gerät · Golden-/Eval-/Lasttest-Läufe (der generative Eval
kostet Geld: LLM-Simulator + Judge je Turn).

**Neu mit P10** — Belege dafür kann nur ein echter Server liefern: **traefik +
ACME** gegen eine auflösbare Domain (der Prüfstack lief bewusst ohne traefik) ·
die zwei Live-Punkte der §8-Checkliste (**SSE über den Load-Balancer**,
**Graceful Shutdown verliert keinen Turn**) nach dem Protokoll in
`docs/cluster-checkliste.md` · die **Lasttest-Abnahme** („stabil bis ≥ 8 parallel
auf 2-Kern-Referenz").
