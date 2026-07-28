# P3-4 Safety-Pipeline — Portierungs-Vertrag (ALT → 4-Modul-Paket)

> Erhoben 2026-07-11 gegen `badboerdi/backend/app/services/safety_service.py` (467 Z., ein Modul)
> + `llm_provider.py:407-463` (`get_moderation_client`). Ziel: Paket `services/safety/` mit
> `regex_gate.py` (Stufe 1) · `moderation.py` (Stufe 2) · `legal.py` (Stufe 3) · `service.py`
> (Orchestrator). Baut auf `services/llm.py` (`chat_completion`, `route`), `services/llm_models.py`
> (`get_provider`), Loader-Fassade (`load_safety_config`) und `boerdi.api.schemas.SafetyDecision`
> (Modell existiert bereits, Felder 1:1 wie ALT). `litellm.amoderation` verifiziert vorhanden
> (Signatur `(input, model, api_key, custom_llm_provider, **kwargs)` → `api_base`/`extra_headers`
> laufen über kwargs).

## 1. Modul-Split (Verantwortlichkeiten)
Der ALT-Monolith bündelte drei Stufen + Orchestrierung in einer Datei (Funktion `assess_safety`
allein ~165 Z.). NEU nach Verantwortung getrennt — verhaltens-erhaltend, keine Logik-Umschrift:

| NEU-Datei | ALT-Ursprung | Inhalt |
|---|---|---|
| `regex_gate.py` | `safety_service.py:31-201` | Alle Regex-Assets (Crisis/Threat/PII/Injection/Legal-Trigger) + `regex_gate()` (ALT `_regex_gate`). Der immer aktive, LLM-freie Backstop. |
| `moderation.py` | `_openai_moderate` + `get_moderation_client` | `_moderation_target()` (3-Zweig-Credential-Auflösung) + `moderate()` via `litellm.amoderation`. |
| `legal.py` | `_llm_legal_classify` + `_LEGAL_SYSTEM` | `classify_legal()` via `services.llm.chat_completion`. |
| `service.py` | `_resolve_preset`/`_stage_should_run`/`assess_safety` | Orchestrator + die drei Merge-Helfer `_merge_moderation`/`_merge_legal`/`_maybe_downgrade`. |

Paket-`__init__` re-exportiert **nur** `assess_safety` (öffentliche API). Die Stufe-1-Funktion
`regex_gate` NICHT re-exportieren — sie würde das gleichnamige Submodul `regex_gate` verschatten;
Zugriff intern/Test via `from boerdi.services.safety.regex_gate import regex_gate`.

## 2. Namens-Renames (Modulgrenze → kein führender Unterstrich)
`_regex_gate`→`regex_gate`, `_openai_moderate`→`moderate`, `_llm_legal_classify`→`classify_legal`,
`_INJECTION_PATTERNS`→`INJECTION_PATTERNS`, `_LEGAL_TRIGGER_PATTERNS`→`LEGAL_TRIGGER_PATTERNS`,
`cat_to_legal` (lokal) → `_CAT_TO_LEGAL` (Modul-Konstante). `_CRISIS/_THREAT/_PII_PATTERNS` bleiben
privat (nur in `regex_gate()` genutzt).

## 3. Stufe 2 — Moderation-Routing (Port von `get_moderation_client`, llm_provider.py:407-463)
`_moderation_target() -> (api_base, api_key, extra_headers) | None`, 1:1 der ALT-Zweige:
- `openai`: nativer OpenAI-Key (sonst `None`). Base = `openai_base_url` oder `https://api.openai.com/v1`.
- `b-api-openai`: B-API-Passthrough wenn `B_API_KEY` → Base `<b_api_base>/openai`, Key = B-Key,
  Header `{"X-API-KEY": b_key}` (Dual-Auth wie `llm.route`). Sonst nativer OpenAI-Seitenkanal wenn
  `OPENAI_API_KEY`; sonst `None`.
- `b-api-academiccloud` (+ jeder andere): nur nativer OpenAI-Seitenkanal (AcademicCloud hat keinen
  Moderations-Endpunkt); `None` ohne OpenAI-Key.

`moderate()` ruft `_amoderation(model="omni-moderation-latest", input=message[:4000], api_key,
api_base [, extra_headers])`, parst `results[0]` **identisch zu ALT** (`.flagged`,
`.categories.model_dump()`, `.category_scores.model_dump()`). **Fail-open:** `None`-Target oder jede
Ausnahme → `{}` (Regex bleibt Floor). `_amoderation = litellm.amoderation` ist die patchbare Boundary.

## 4. Stufe 3 — Legal-Classifier (Transport-Wechsel)
ALT: `get_client().chat.completions.create(**build_chat_kwargs(model=get_chat_model(), messages,
temperature=0.0, max_tokens=300, response_format={"type":"json_object"}))`. NEU:
`chat_completion(messages=[system,user], temperature=0.0, max_tokens=300,
response_format={"type":"json_object"})` — GPT-5-Gating/Routing/Retries/Semaphore liegen zentral in
`chat_completion`/`build_chat_kwargs`. `_LEGAL_SYSTEM`-Prompt-Text, `message[:2000]`-Cap, die
JSON-Parse-Schleife (4 Kategorien, `risk` float/`reason`[:200]) und Fail-open→`{}` byte-identisch.

## 5. Orchestrator (`assess_safety`) + Merge-Extraktion
Fluss 1:1: `regex_gate` → bei `high` sofort return → `load_safety_config` → `_resolve_preset` →
`level:`-Reason → Prompt-Injection-Stufe (per Preset) → Stage-Gating (`_stage_should_run`) +
`legal_trigger_override` → `asyncio.gather` beider Stufen → Merge → return. Die Post-Gather-Merges
sind aus der ~165-Z.-Funktion in drei Helfer gezogen (verhaltens-erhaltend, je eine Verantwortung):
- `_merge_moderation(decision, openai_data, cfg, esc, tmul)` — ALT 374-430 (Threshold-Flag,
  `_CAT_TO_LEGAL`-Mapping, Hard-Block→high + Pattern-Wahl [Crisis vor Threat vor Default]).
- `_merge_legal(decision, legal_data, esc, tmul)` — ALT 432-449 (flag/high-Schwellen, strafrecht/
  jugendschutz→high, sonst low→medium).
- `_maybe_downgrade(decision, esc, legal_data)` — ALT 451-464. Nutzt `decision.flagged_categories`
  statt ALT-Lokal `flagged_now` (in `_merge_moderation` gleich gesetzt → identisch).

## 6. Bewusste Deviations (alle verhaltens-neutral, dokumentiert)
1. **Transport Moderation** → `litellm.amoderation` statt bespoke `AsyncOpenAI`-Client (Contract §"Moderation-Client").
2. **Transport Legal** → `services.llm.chat_completion` statt `get_client()...create`.
3. **Toter Code entfernt:** ALTs Injection-Stufe hatte `if "persoenlichkeitsrechte" not in
   decision.legal_flags: pass` — reines No-op, nicht portiert.
4. **Merge-Extraktion** (siehe §5) — reine Bewegung, keine Umschrift.
5. `zip(tasks, results, strict=True)` (ruff B905) statt ALTs `zip(...)` — Längen sind per Konstruktion gleich.
Kein `simplify:`-Defer nötig. `escalation.confidence_adjustments`/`rate_limits`/`logging` aus der
YAML sind NICHT Teil von `assess_safety` (werden andernorts konsumiert — Rate-Limit P1-4, Logging P3-5).

## 7. Tests (`tests/test_safety_*.py`)
- `test_safety_regex_gate.py` — Port des ALT-Regex-Gate-Tests: Stufe 1 (Crisis/Threat/PII/Danger/
  benign), `_resolve_preset` (standard/basic-Alias/legacy), `_stage_should_run` (parametrisiert),
  `assess_safety`-Offline-Pfade (Crisis-Short-Circuit, benign-low, Injection-medium).
- `test_safety_escalation.py` — Port des ALT-Eskalationstests: Merge-Logik mit gemockten
  `moderation.moderate`/`legal.classify_legal` (Hard-Block self_harm→M01, threat→M02, Legal-high,
  Legal-medium, Weak-Downgrade, clean-escalated, Trigger-Override).
- `test_safety_stages.py` — NEU (neuer Transport): `_moderation_target`-Routing (3 Provider ×
  Key-Präsenz), `moderate()`-Parsing + Fail-open (None-Target/Ausnahme) + B-API-Header-Weitergabe,
  `classify_legal()`-Parsing + Fail-open. Boundaries: `moderation._amoderation`, `legal.chat_completion`.
- 40 Tests. Regex-Assets bleiben verbatim (per-file `E501`-Ignore für `regex_gate.py`).
