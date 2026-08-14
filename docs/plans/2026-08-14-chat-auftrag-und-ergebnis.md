# Chat-Fenster mit Auftrag und strukturiertem Ergebnis

**Anlass (Nutzer 2026-08-14).** Die Plugin-Entwickler brauchen mehr als den
Agent-Endpunkt: ein eingebettetes Chat-Fenster, das (1) mit der Agent-Schleife
läuft, (2) Sammlung und Seitenwissen mitbekommt, (3) einen **Startbefehl** von
außen annimmt, (4) danach eine gewöhnliche Unterhaltung erlaubt und (5)
**strukturierte Ergebnisse** nach einem erklärten Schema herausgibt.

**Befund vor der Arbeit.** (1), (2) und (4) gibt es bereits — `engine="agent"`,
`respond_agent._vorab_aufrufe` holt die Freigabeliste der Sammlung aus dem
Seitenkontext, zehn Züge Verlauf gehen mit. Es fehlen (3) und (5), und beide
sind dokumentierte Entscheidungen, keine Lücken:

* **Kein `sendMessage` nach außen** — es steht nicht in `FORWARDED_METHODS`.
* **Kein `submit_result` im Chat** — `respond_agent` ruft
  `build_agent_tools(include_submit=False)`; Begründung im Modulkopf: der
  Abschluss-Zug kostet 2–9 s (gemessen) und sagt, was die Prosa schon sagt.
  Dazu hat `ChatResponse` kein Ergebnis-Feld.

**Nutzer-Entscheide (2026-08-14).** Beides bauen · der Auftakt erscheint als
**eigene Auftrags-Blase** (nicht als Nutzernachricht, nicht unsichtbar) · das
Schema kommt als **Attribut je Einbau**.

---

## Paket A — Auftakt von außen

Die Schiene existiert: die Kontext-Begrüßung stößt einen Zug an, ohne eine
Nutzernachricht zu schreiben (gepinnt in `shell-contexts.spec.ts:89`).

| Datei | Verantwortung |
|---|---|
| `ui/src/shell/chat-shell.component.ts` | `startTask(text)` — Auftrags-Blase in den Verlauf, dann ein Zug über dieselbe Send-Naht |
| `ui/src/shell/message-store.ts` (o.ä.) | dritte Blasen-Art `auftrag` neben `user`/`bot` |
| `ui/src/shell/*.html` + SCSS | Darstellung der Auftrags-Blase |
| `ui/src/i18n/de.ts` + `en.ts` | Beschriftung der Blase |
| `widget/src/app/widget/widget.component.ts` | `startTask(text)` → Shell; **Warteschlange**, solange die Shell noch nicht gemountet ist |
| `widget/src/element-api.ts` | `startTask` in `FORWARDED_METHODS` |

**Warteschlange, nicht stiller Ausfall.** Im Panel-Modus mountet die Shell erst
beim ersten Öffnen; ein `startTask` davor liefe heute ins Leere. Der bestehende
Effect-Griff (`shell()` wird verfügbar → nachziehen, wie bei `setEngine`) hält
den Auftrag, bis es eine Shell gibt.

**Tests:** Blase erscheint und ist keine Nutzernachricht · der Zug geht ab ·
vor dem Mounten wird der Auftrag gehalten und danach ausgeführt · `startTask`
ist durchgereicht.

## Paket B — Strukturiertes Ergebnis aus dem Chat

| Datei | Verantwortung |
|---|---|
| `api/schemas.py` | `Environment.result_schema: dict \| None`; `ChatResponse.result` + `.result_stop_reason` |
| `graph/state.py` | zwei Felder am `TurnContext` |
| `graph/nodes/respond_agent.py` | Schema vorhanden → `include_submit=True` + `result_schema`; Prompt-Satz **nur dann**; `lauf.result`/`stop_reason` an den ctx |
| `graph/nodes/assemble.py` bzw. `turn_assembly` | die zwei Felder in die `ChatResponse` |
| `ui/src/stream/chat-api.ts` | `result_schema` mitsenden, `result` lesen |
| `ui/src/shell/chat-shell.component.ts` | Ergebnis an den Host melden |
| `ui/src/host-events/event-names.ts` | `boerdi:agent-result` |
| `widget/src/app/widget/widget.component.ts` | Attribut `result-schema` (JSON) + Output `agentResult` |
| `docs/api/openapi-v1.json` | neu einfrieren |

**Der Preis, ausdrücklich:** mit Schema kostet jeder Zug einen zusätzlichen
Modellzug (2–9 s). Deshalb ist es opt-in je Einbau und nicht die Vorgabe.
`result` ist **je Zug optional** — „Hallo" ergibt kein Ergebnis; die Gastseite
muss `null` aushalten.

**Tests:** ohne Schema unverändert (kein `submit_result`, kein Prompt-Satz) ·
mit Schema landet es in den Werkzeugen · `result` erreicht die Antwort ·
kaputtes Attribut-JSON kippt den Zug nicht · Vertrag neu eingefroren.

## Stand 2026-08-14

* **Paket A: fertig.** `startTask` an Shell, Widget (mit Warteschlange) und
  Element; Auftrags-Blase (`fromHost`) samt Darstellung und Beschriftung.
  Frontend 776 · 58 · 973 grün, 5 neue Tests, Rotlauf beobachtet.
* **Paket B, Backend: fertig.** `Environment.result_schema`,
  `ChatResponse.result` + `result_stop_reason`, zwei ctx-Felder,
  `respond_agent` schaltet `submit_result` samt Prompt-Satz nur mit Schema,
  `persist` reicht beides an die Antwort. 3465 grün, Vertrag neu eingefroren,
  der Feldsatz-Wächter fortgeschrieben statt abgeschwächt.
* **Paket B, Frontend: fertig.** Der Weg vom Attribut zum Feld und zurück
  steht: `_attrJsonObject` in `ui/src/element/attr.ts` (der Wohnort der
  Attribut-Koerzierung, statt einer weiteren Zeile im Komponenten-Rumpf) →
  Eingabe `result-schema` am Widget → Effect → `shell.setResultSchema` →
  `ChatApiClient.setResultSchema` → `environment.result_schema` jedes Zuges.
  Zurück: `_reportAgentResult` feuert `boerdi:agent-result` und den
  Angular-Ausgang `agentResult`, unter derselben Bedingung wie das Backend
  (`persist.py`): Ergebnis ODER Ende-Grund.

## Nachgezogen 2026-08-14 (Review-Durchgang)

Drei Befunde am eigenen Vortagswerk, alle behoben:

1. **`Environment.result_schema` war ungedeckelt** — auf dem ÖFFENTLICHEN
   Router, während der Zwilling `AgentRequest.result_schema` hinter
   `require_agent_caller` sitzt und der Nachbar `page_context` beim Verbraucher
   auf eine A4-Seite gekappt wird. Jetzt `MAX_RESULT_SCHEMA_CHARS = 10000`,
   **abgelehnt statt gekürzt**: ein halbes Schema ist ein anderes Schema.
   Der Zwilling bleibt bewusst ungedeckelt (angemeldete Maschinen).
2. **Der Modulkopf von `respond_agent` war falsch geworden.** Er behauptete
   unbedingt „ohne ``submit_result``" und „der Systemprompt sagt nichts über ein
   Abschluss-Werkzeug" — beides gilt seit dem Schema nur noch ohne Schema.
3. **Ein Schema ohne `engine="agent"` war ein stiller Ausfall.** Die Vorgabe ist
   `pattern`; wer das Attribut setzt und die Maschine vergisst, wartete auf ein
   Ereignis, das nie kommt. Jetzt eine Warnzeile in `respond` — warnen, nicht
   abweisen: der Zug ist in Ordnung, nur die Erwartung nicht.

**Drei Verträge wuchsen mit, jeder von seinem eigenen Wächter erzwungen:** die
Ereignis-Liste (`event-names.spec`, 4→5), der Host-Attribut-Satz
(`widget.component.spec`, 25→26) und die Studio-Referenz
(`architecture-reference.component.spec`). Kein Wächter wurde abgeschwächt.

## Reihenfolge

A zuerst (rein Frontend, kein Vertragsbruch, sofort nützlich), dann B. Nach
jedem Paket: volle Suiten + `ruff` + Doku beider Einbindungs-Anleitungen.
