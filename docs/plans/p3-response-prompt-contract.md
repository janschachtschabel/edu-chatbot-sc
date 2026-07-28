# P3-3 Response-Prompt-Builder — Portierungs-Vertrag (ALT `llm_prompt_builder.py`)

> Erhoben 2026-07-11 (Explore-Agent) gegen `badboerdi/backend/app/services/llm_prompt_builder.py`
> (1219 Z., 3 Funktionen). Ziel: NEU `services/response_prompt_builder.py` (+ Split, §8).
> Baut auf Loader-Fassade (Config), `services/classify_prompt.py`-Helfer, `services/llm.chat_completion`.

## ✅ Scope-Split AUFGELÖST: 3-3a (2026-07-11) + 3-3b (2026-07-11) beide UMGESETZT
`_build_system_prompt` (P1-P9) → 3-3a (§9). `_select_active_tools` (P10-P11) war auf `TOOL_DEFINITIONS`
blockiert; seit 5-2 (`services/mcp/tool_defs.py`) vorhanden → **3-3b umgesetzt (§10)**. Beide Sub-Slices
abgeschlossen; von diesem Vertrag bleibt nichts offen.

## 1. Öffentliche Funktionen (Signaturen + Rückgabe-Tupel)
Einziger Aufrufer: `llm_service.generate_response` (llm_service.py:194-225). **Kein Test ruft die
Funktionen direkt** (0 Treffer für `_build_system_prompt|_select_active_tools|prompt_builder` in
`tests/`) — sie werden nur über `generate_response` charakterisiert. → **NEU: direkte Unit-Tests gegen
die Marker (§5) schreiben** (generate_response = P4/P5, noch nicht da).

### `_build_system_prompt` (L40-880) → tuple[str, bool, bool, bool]
```python
def _build_system_prompt(classification, pattern_output, pattern_label, session_state,
                         environment, rag_context, available_rag_areas, rag_config):
    # return (system, _cards_inline_mode, _inline_grouping_mode, _degradation_no_tools)  # L878-880
```
Keine Defaults (8 positional beim Aufrufer). `_cards_inline_mode`+`_degradation_no_tools` → `_select_active_tools`; `_inline_grouping_mode` → `_assemble_messages`/`_run_tool_loop` (P4).

### `_select_active_tools` (L883-1219) → tuple[list[dict], Any, bool, bool]  — **P5/P6-blockiert**
```python
def _select_active_tools(classification, pattern_output, available_rag_areas, rag_config,
                         _cards_inline_mode, _degradation_no_tools):
    # return (active_tools, _pattern_sources_decl, _rag_allowed_for_pattern, _inline_qr_enabled)  # L1219
```

### `_get_state_meta_safe` (L33-37) — Lazy-Fassade gg. Import-Zyklus
Wraps `get_state_directive` (config_loader) mit try/except→{}. NEU hat `get_state_directive`
(config_loader/classification.py). Dict-Keys: `id,label,role,bot_directive,next_likely`. Builder liest
`bot_directive,label,role`. Unbekannter State → `{}` → Label "(?)"/Rolle "—"/Fallback-Direktive.

## 2. Phasen-Mapping (nur 3 Funktionen; P1-P11 sind Code-Blöcke)
**`_build_system_prompt`:** P1 Init/Config-Loads (63-78) · P2 5-Layer-Prompt (80-139:
Base→Domain→Persona→`_render_pattern_brief`+Anrede/Länge/RAG-URL-Regeln→`## Kontext`+Phase-Direktive) ·
P3 Page-Context (141-162, try/except lazy) · P4 M11-Rerender (164-196, `output_mode=="rerender"`,
8000-char-Cap) · P5 Anzeige-Modi (198-603: Flags/card_text_mode/Re-Rank-Hint/Inline-Grouping/KEIN-Suche/
Inline-Link) · P6 Signal-Regeln+Degradation (605-635) · P7 RAG-Kontext+Guardrails-als-LETZTER-Layer
(637-644) · P8 Werkzeuge/No-Tools (646-854) · P9 Recency-Anker `## ⚡ LETZTE ERINNERUNG` + `_log_system_prompt_size("response",system)` + return (856-880).
**`_select_active_tools`:** P10 Tool-Wahl (904-928) · P10b medientyp-Strip (930-971) · P11a Sources-Gate
(973-982) · P11b query_knowledge-vorn (983-1019) · P11c select_top_cards (1021-1121) · P11d Degradation-Wipe (1123-1135) · P11e respond_to_user-hinten (1137-1218).

## 3. Config-Abhängigkeiten (alle via Fassade — KEINE Roh-`area()` im Builder)
Import-time top-level: `load_persona_prompt(persona_id)`, `load_domain_rules()`, `load_base_persona()`,
`load_guardrails()`. Indirekt: `get_state_directive` (via _get_state_meta_safe).
**Port-Falle (Response-Pendant zum Signals-Strip):** `load_persona_prompt` IST die strippende Fassade
(personas.py) — lässt Klassifikations-Felder (`positive_markers/anti_markers/discriminators/
typical_intents`) BEWUSST weg; nur `description/tone/formality/goals/rules/personality_text` in den
Antwort-Prompt. Läse der Port die rohe Persona-`.md`, leaken ~500 Token/Persona Klassifikations-Marker.
NEU `load_persona_prompt` (config_loader/personas.py:56-76) macht genau das schon → einfach nutzen.

## 4. Externe Modul-Deps (außer config_loader)
| Modul | Nutzung | NEU-Status |
|---|---|---|
| `llm_classify_prompt` | `_formality_guidance`, `_render_pattern_brief` | **NOCH ZU PORTIEREN** (ALT llm_classify_prompt.py:953-1112; gehört in 3-3a) |
| `llm_usage` | `_log_system_prompt_size` (nur Log-Seiteneffekt) | `simplify:` weglassen (kein tiktoken, wie classify) |
| `mcp_client` | `TOOL_DEFINITIONS` (aus `mcp_tool_defs.py:42`) | **FEHLT → P5/P6** (blockiert `_select_active_tools`) |
| `page_context_service` | `get_cached/render_for_prompt/render_raw_for_prompt` (lazy in-Fkt.) | **VERSCHOBEN** → `simplify:` deferren (wie classify/QR), Seam markieren |
| `llm_service` | `_get_state_meta_safe` (lazy) | NEU: `get_state_directive` direkt |
`canvas_types/rag/guide_mode` sind KEINE direkten Importe. `rag_config`/`available_rag_areas` kommen als
Parameter; `_canvas_last_markdown` aus `session_state["entities"]`.

## 5. Verhaltenskritische Marker (Tests pinnen — direkte NEU-Unit-Tests)
Quelle der Marker: ALT `tests/test_generate_response_net.py` (`_sys(client)=calls[0].messages[0].content`),
`test_generate_response.py`, `test_active_tools_selection.py`.
- **Layer-Reihenfolge:** base→domain→persona→`## Aktives Pattern:`→`## Kontext`→<rag_context>→guardrails→`## Verfuegbare Werkzeuge`→`LETZTE ERINNERUNG`; body_md-Recap NACH guardrails.
- **State/Entity:** `Gesprächs-Phase: S7 (Test-Phase)`, `Rolle in dieser Phase: Kurator`, `Entities: {"thema": "Bruchrechnen"}`, `_intern`-Prefix gefiltert, `Signale: frust, eile`.
- **Unbekannter State:** `Gesprächs-Phase: S9 (?)`, `Rolle in dieser Phase: —`, `— keine spezifische Direktive für diese Phase, folge dem Pattern.`
- **M11-Rerender:** `## Aktueller Inhalt zum Editieren`, 8000-char-Cap (`"X"*8000` drin, `*8001` nicht), `(Inhalt gekürzt`.
- **card_text_mode:** `(Modus: minimal|reference|highlight)`; Kachel-Modus immer `## Optionaler Re-Rank über select_top_cards`.
- **Inline:** `cards_enabled=False`+M05→`## Inline-Result-Grouping-Mode` (KEIN Re-Rank-Hint); M04→`## Pattern-Modus: KEIN Suche-Antworten`; `inline_result_grouping=False`→`## Inline-Link-Mode`.
- **Degradation:** `## Degradation aktiv: Fehlende Slots: ['thema'].`, `Blockierte Patterns: M05 (Material, braucht: thema).`, `PFLICHT-RUECKFRAGE`, `## Verfuegbare Werkzeuge` NICHT vorhanden.
- **Session-Blöcke:** `## Verfuegbare Sammlungen aus vorherigen Ergebnissen`, `- "Sammlung Brueche" (nodeId: col1)`, `## Zuvor gezeigte Materialien`, `1. "Video Brueche" (Video) — `+`"D"*100` (101 nicht).

## 6. `_select_active_tools`-Logik (für 3-3b, wenn TOOL_DEFINITIONS da)
`INFO_TOOLS=set()` (leer). Basis-Priorität: (1) `pattern.tools` nichtleer→Whitelist aus TOOL_DEFINITIONS;
(2) `tools==[]`→`active_tools=[]`; (3) `"mcp" in sources`→alle TOOL_DEFINITIONS; (4) Fallback
`{search_wlo_collections, search_wlo_topic_pages}`. medientyp gesetzt→strippe `{collections,topic_pages,
all}`, garantiere `search_wlo_content`. RAG-Gate `_rag_allowed = sources is None or "rag" in sources`.
query_knowledge (enum=areas) VORN wenn `areas and rag_config and _rag_allowed`. select_top_cards angehängt
außer ENV `CHAT_DISABLE_SELECT_TOP_CARDS∈("1","true","True")`. Degradation-Wipe: `if _degradation_no_tools
and active_tools: active_tools=[]`. respond_to_user HINTEN wenn ENV `CHAT_INLINE_QUICK_REPLIES∈("1","true","yes")`.
> **ENV-String-Sets asymmetrisch exakt übernehmen:** DISABLE=`("1","true","True")`, INLINE_QR=`("1","true","yes")`.
Reihenfolge load-bearing: `[query_knowledge?]+<base/gefiltert>+[select_top_cards?]+[respond_to_user?]`.

## 7. Deterministische Flags
- `_cards_inline_mode = environment.get("cards_enabled") is False` (strikt `is False`) — L207.
- `_inline_grouping_mode = _cards_inline_mode and environment.get("inline_result_grouping") is not False` (Default True) — L220-223.
- `_degradation_no_tools = bool(pattern_output.get("degradation") and pattern_output.get("missing_slots"))` — L240-243.

## 8. Empfohlene NEU-Aufteilung (~300 Z./Datei, entlang Phasen)
1. `response_prompt_builder.py` (~180) — Orchestrator: `_get_state_meta_safe`-Fassade, `_build_system_prompt`-Gerüst (P1-P9-Flow, Flags, system_parts), Return-Tupel; delegiert Block-Text.
2. `response_prompt_display_blocks.py` (~320, P5) — statische Anzeige-Modus-Strings (card_text_mode, Re-Rank-Hint, Inline-Grouping ~150 Z., KEIN-Suche, Inline-Link) als reine Fn/Konstanten.
3. `response_prompt_tools_text.py` (~240, P8) — Session-Sammlungen/-Materialien-Renderer, `## Verfuegbare Werkzeuge`+`## Tool-Routing-Regeln`, No-Tools-Regeln, P6-Degradation-Text, P9-Recency-Anker.
4. `response_tool_selection.py` (~340, P10-P11) — `_select_active_tools` + 3 Tool-Schema-Builder. **Erst 3-3b (P5/P6).**

Invarianten: (a) page_context lazy+try/except deferren (Audit-T6); (b) Layer-Reihenfolge + Marker byte-genau; (c) `_formality_guidance`/`_render_pattern_brief` aus ALT llm_classify_prompt.py:953-1112 mitportieren (gehören zum Response-Prompt, NICHT zu classify); (d) `_log_system_prompt_size` simplify-weglassen.

## 9. UMGESETZT — 3-3a `_build_system_prompt` (2026-07-11)
`_select_active_tools` (3-3b) bleibt zurückgestellt (P5/P6, `TOOL_DEFINITIONS` fehlt).
4 neue Module (Split nach §8), Test-first (RED ImportError → GREEN 24), byte-genau aus ALT-Quelle transkribiert:
- **`services/response_prompt_pattern.py`** (~215): `_formality_guidance` + `_render_pattern_brief` (1:1 aus ALT `llm_classify_prompt.py:953-1111`) + `render_pattern_layer` (Layer-4-f-String aus `llm_prompt_builder.py:94-128`, ausgelagert damit der Orchestrator schlank bleibt).
- **`services/response_prompt_display_blocks.py`** (~380): P4 M11-Rerender-Fn (8000-Cap) + P5 `render_card_text_mode_block` (minimal/reference/highlight) + Konstanten `RERANK_HINT_BLOCK`/`INLINE_GROUPING_BLOCK`/`PATTERN_NO_SEARCH_BLOCK`/`INLINE_LINK_BLOCK` + `render_result_mode_block` (3-Wege-Branch = ALT if/elif/elif). Bewusst >300 (verbatim Content, 1 Verantwortung), im Docstring notiert.
- **`services/response_prompt_tools_text.py`** (~250): P6 `render_degradation_rules` + Konstanten `DEGRADATION_NO_TOOLS_RULES`/`M15_NO_TOOLS_RULES` + P8 `render_tools_block` (+`_render_session_context` für `_last_collections`/`_last_contents`, korrupt-JSON-Degrade wie ALT) + P9 `render_recency_anchor`.
- **`services/response_prompt_builder.py`** (~180): `_get_state_meta_safe` (try/except→{} + warn-log, wie ALT `llm_service`) + `_build_system_prompt` P1-P9-Flow. **Hält die `if/append`-Kontrolllogik** → `system_parts`-Listenstruktur (und die load-bearing `"\n".join`-Separatoren) byte-identisch. Helfer geben `""` zurück wenn ALT nicht appended.

Deviations (dokumentiert im Code): (a) P3 page_context + (b) P9 `_log_system_prompt_size` `simplify:`-deferred; (c) **3 tote ALT-Locals NICHT portiert** (`_pattern_id_for_m11`, `has_rag_tools`, per-area `mode` — assigned/never-read, unter NEU-ruff F841); (d) Layer-5 `_entities`-Extraktion nur für Zeilenlänge (JSON-Output identisch). E501-per-file-ignore für die 3 Text-Module (verbatim Prompt-Bytes). Test-Seams: Loader + `get_state_directive` auf `rpb` gepatcht (kein Store nötig); `_formality_guidance`/`_render_pattern_brief` laufen echt.

**Verifikation:** Ziel-Tests 24 (Layer-Order, State/Entity/Signals, unbekannter State, M11-Cap, card-Modi, Inline-Grouping/KEIN-Suche/Inline-Link + Interior-/End-Pins gegen Block-Trunkierung, Degradation+Tool-Lock, Session-Blöcke 100-Char-Cap, Flags-Tupel, Pattern-Brief/Formality direkt). Suite **278 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert.

## 10. UMGESETZT — 3-3b `_select_active_tools` (2026-07-11)
Entsperrt durch 5-2 (`services/mcp/tool_defs.py::TOOL_DEFINITIONS`). Eigenes Modul **`services/response_tool_selection.py`** (§8.4) statt Zusatz in `response_prompt_builder` — Tool-LISTE ≠ Prompt-TEXT. ~340 Z., 1 Funktion (bewusst >300: verbatim Prompt-Bytes der 3 inline Tool-Schemata; Extraktion in Builder-Helfer würde die AST-Parität brechen, gleiche Begründung wie `display_blocks`).
- **Port-Treue:** Funktions-Rumpf **byte-identisch** zu ALT `llm_prompt_builder.py:883-1219`. **Einzige Deviation = Import-Root** (`app.services.mcp_client` → `boerdi.services.mcp.tool_defs`; NEU hat kein `mcp_client`-Re-Export-Facade → Leaf-Import). E501-per-file-ignore (pyproject) wie die Geschwister-Prompt-Module. **AST-Diff `_select_active_tools`-Body ALT↔NEU = IDENTISCH, 0 Divergenz.**
- **Tests (Vertrag §5 folgend — ALT-Test war Integration via `generate_response`):** `tests/test_response_tool_selection.py`, 22 **direkte** Unit-Tests gegen die §6-Marker. Die 3 ALT-Integrations-Verträge (search_wlo_all sichtbar / medientyp strippt all+pots / content bleibt) als direkte Fälle gespiegelt. Autouse-Fixture leert die 2 ENV-Gates + snapshottet `TOOL_DEFINITIONS` (Determinismus).
- **Latenter ALT-Quirk verbatim übernommen + GEFLAGGT, nicht gefixt (Scope-Control §13):** im `has_mcp_source`-Zweig `active_tools = TOOL_DEFINITIONS` (Referenz statt Kopie) → bei bare-mcp + kein-RAG-Area + `select_top_cards` aktiv mutiert das spätere `.append` das Modul-Global `TOOL_DEFINITIONS` (unbounded growth über Calls — Regel-3-Shared-Mutable-State-Smell). `simplify:`-Marker im Modul-Docstring: Fix = `list(TOOL_DEFINITIONS)` sobald der Nutzer die bewusste Verbesserung freigibt; Rückgabewert provable unverändert.

**Verifikation:** 22 T GREEN; AST-Diff 0 Divergenz; Suite **529 grün + 50 pg-skips**, ruff clean, OpenAPI unverändert. **Damit ist dieser Vertrag vollständig umgesetzt** (3-3a + 3-3b).
