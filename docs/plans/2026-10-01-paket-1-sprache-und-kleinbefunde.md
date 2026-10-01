# Paket 1: Sprache und kleine Befunde

Stand 2026-10-01. Auftrag des Nutzers: „wie empfohlen fortfahren“. Gemeint ist die
Reihenfolge aus der Befundliste:
1. Paket 1: §1.5, §1.6 und die Quick Wins aus dem Audit.
2. Danach die Schreib-Abnahme im Agent-Modus (§1.1).
3. Dann ein Plan für das Token-Streaming.

Vorgabe zu den Schnellantworten: Sie sollen konsistent sein und in derselben Sprache stehen
wie die LLM-Antwort.

## Messung vorab (Testcontainer, Stand ≈ `1f069e9`)

**Antwortsprache.** Gefragt wurde jeweils auf Englisch, über `/api/chat`, mit frischen Sitzungen.

| Maschine | Oberfläche | Antwort | Schnellantworten |
|---|---|---|---|
| Muster | `de-DE` | Deutsch | Deutsch |
| Muster | `en-GB` | Englisch | Englisch |
| Agent | `de-DE` | meist Englisch (2 von 3) | wie die Antwort |
| Agent | `en-GB` | Englisch | Englisch |

- Der Muster-Prompt legt die Sprache fest: „Antworte auf Deutsch“ (`services/response_prompt_tools_text.py:63-69`).
- Der Agent-Kopf folgt der Sprache der Person und nimmt die Oberflächensprache nur als Rückfall (`services/agent_kopf.py:137-139`).
- Die Schnellantworten standen in allen Fällen in der Antwortsprache. Abgesichert ist das nicht:
  - Der Nachgenerator bekommt kein `lang`.
  - Für Englisch hängt er `template_hint` an. Das widerspräche einer deutschen Agent-Antwort in englischer Oberfläche.

**Startnachricht im Widget.** Geprüft mit Playwright auf `/widget/classic`.
- Startet das Widget englisch (Attribut `language="en"`), sind Begrüßung und Start-Chips englisch.
- Wird im laufenden Widget umgeschaltet, bevor eine Frage gestellt ist, wird die Oberfläche englisch. Die bereits angezeigte erste Nachricht bleibt aber deutsch.
  - Das gilt für die feste Startnachricht samt Start-Chips.
  - Es gilt ebenso für den serverseitigen Kontext-Gruß samt Aktions-Pills.
- Die erste Frage nach dem Umschalten schickt `locale=en`. Antwort und Chips kommen auf Englisch.
- Nebenbei: Mit `prefers-reduced-motion` steht der Eulen-Knopf still.

## Aufgaben

| Nr. | Aufgabe | Dateien | Nachweis |
|---|---|---|---|
| T1 | Schnellantworten in der Sprache der Antwort (§1.5) | `services/quick_replies_prompt.py`, `services/turn_assembly.py` | Tests in `test_quick_replies_llm.py` und `test_turn_assembly.py`, zuerst rot |
| T2 | Ein Sprachwechsel vor der ersten Frage tauscht die erste Nachricht | Frontend `ui/src/shell` | Spec zuerst rot, danach Playwright im Testcontainer |
| T3 | Guide-Regeln ohne Neustart (§1.6) | `services/guide_qr_injector.py` und die Konfig-Benachrichtigung | Test zuerst rot |
| T4 | Quick Wins aus dem Audit (§7), siehe unten | mehrere Dateien | je ein Test oder eine Prüfung |

T4 im Einzelnen:
- CI-`permissions`
- Dev-Ports auf `127.0.0.1`
- Limit für `/api/safety/logs`
- Endmarke für Fremdtext entschärfen
- generische SSE-Fehlermeldung
- Indizes für die Log-Tabellen
- `npm audit fix` ohne `--force`

Nicht in diesem Paket ist das `session_id`-Muster aus §7. Es ändert den HTTP-Vertrag und
braucht einen Entscheid.

## Entscheidung des Nutzers

**E1, Antwortsprache im Muster-Modus.**
- Soll der Muster-Modus wie der Agent in der Sprache der Person antworten, mit der Oberflächensprache als Rückfall?
- Heute bestimmt allein die Oberfläche die Sprache, so legt es C1 fest (`docs/plans/2026-08-02-c1-i18n.md`).

## Log

- 2026-10-01: Messung vorab, Plan angelegt.
- 2026-10-01, T1:
  - Der Nachgenerator und der Misch-Aufruf bekommen `lang` (`services/turn_assembly.py`).
  - Der Prompt verlangt „in der Sprache der Bot-Antwort“ und nennt die Oberflächensprache nur als Rückfall (`services/quick_replies_prompt.py`, `_sprach_regel`).
  - `template_hint` entfällt dort, und der Lotsen-Chip ist nicht mehr fest auf „deutsch“ gesetzt.
  - Tests: `test_quick_replies_llm.py`. Den Test `test_qr_englisch_haengt_den_hinweis_an` habe ich bewusst durch `test_qr_folgen_der_sprache_der_antwort` ersetzt, denn die Vorgabe hat sich geändert. Dazu kommen zwei Tests in `test_turn_assembly.py`, beide zuerst rot.
- 2026-10-01, T2:
  - Die feste Startnachricht liegt verhaltensgleich in `ui/src/shell/welcome-message.ts`. `lifecycle.ts` schrumpft dadurch von 303 auf 289 Zeilen.
  - Neu ist `relocalize()`: Steht die Startnachricht allein und wurde noch keine Frage gestellt, ersetzt ein Sprachwechsel sie samt Start-Chips durch die neue Sprache.
  - `chat-shell.component.ts` ruft das in `ngOnChanges(locale)` auf.
  - Der Kontext-Gruß des Backends bleibt stehen. Er ist gespeichert, und ein zweiter Ping in derselben Sitzung wird unterdrückt (`context_greeting.py`, Gate 4). Dafür bräuchte es einen eigenen Backend-Weg, siehe Befundliste §2.
  - Specs: `welcome-message.spec.ts` (5 Fälle) und `chat-shell-lifecycle.spec.ts` (Verdrahtung), beide zuerst rot.
- 2026-10-01, T3:
  - `_compiled()` merkt sich die Regeln, aus denen gebaut wurde (`_COMPILED_FROM`), und übersetzt neu, sobald sie sich ändern.
  - Die Quelle ist billig: Prozess-Cache des Config-Stores, den NOTIFY auf jeder Instanz leert.
  - Ein von außen gesetztes `_COMPILED` ohne Quelle gilt unverändert weiter, das ist die Prüfnaht der bestehenden Tests.
  - Tests: zwei in `test_guide_qr_injector.py`, der erste zuerst rot.
- 2026-10-01, T4:
  - **CI:** `permissions: contents: read` in `ci.yml`.
  - **Dev-Ports:** alle fünf auf `127.0.0.1` (`compose.dev.yml`, geprüft mit `docker compose config`).
  - **`/api/safety/logs`:** `limit` mit 1–500 gedeckelt. Der Vertrag `docs/api/openapi-v1.json` ist bewusst neu erzeugt.
  - **Fremdtext-Rahmen:** Endmarken im Fremdtext werden vor dem Rahmen entschärft, auch in abgewandelter Schreibweise. Das gilt auch für den Block „Zuletzt gezeigt“ (`domain/untrusted_text.entschaerfe_endmarken`).
  - **SSE:** Der Fehlerrahmen meldet nur noch „internal error“. Typ und Text der Ausnahme bleiben im Log. Die Tests für Chat und `/api/agent` habe ich bewusst umgedreht.
  - **Indizes:** Migration `0005_log_indizes.py` legt `idx_safety_session`, `idx_quality_session` und `idx_config_history_area` an.
  - **`npm audit fix`** ohne `--force`: vitest 4.1.11, `dompurify` 3.4.16 sowie `undici`, `js-yaml`, `brace-expansion`, `fast-uri`, `qs`, `hono` und `ip-address`; `package.json` unverändert.
    - Offen bleibt `@angular/router`: Der Fix verlangt Angular 22.2 im Gleichschritt, siehe Befundliste §5.
- Prüfungen nach T1–T4:
  - Frontend-Lint ist sauber.
  - `ng test`: `ui` 76, `widget` 3 und `studio` 110 Testdateien grün.
  - Widget-Build mit Gzip-Budget 160,6 von 175 kB.
    - Die Angular-Warngrenze von 550 kB war schon vor dem Paket überschritten: 550.780 Bytes, jetzt 552.320.
  - Studio-Build ist grün.
