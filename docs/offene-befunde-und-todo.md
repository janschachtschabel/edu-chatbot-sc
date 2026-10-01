# Offene Befunde und Todo

Stand 2026-09-29 (Zwischenstand). Diese Liste sammelt an einer Stelle, was nach diesem Stand offen ist, jeweils mit Quelle.
Erledigtes steht in den Logs der Pläne, nicht hier. Wer einen Punkt erledigt, streicht ihn hier und
trägt ihn im Log des zugehörigen Plans ein. Zeilennummern gelten für den Stand 2026-09-29.

Die zugehörigen Pläne:
- **Betriebsmodi-Plan:** [`2026-09-26-betriebsmodi-und-studio.md`](plans/2026-09-26-betriebsmodi-und-studio.md)
- **Runde-2-Plan:** [`2026-09-28-agent-runde-2.md`](plans/2026-09-28-agent-runde-2.md) — erledigt dort (Paket 2, 2026-10-01): die Schreib-Abnahme im Agent-Modus (früher §1.1), Log unter „Nebenbefund außerhalb dieser Runde“.
- **Responses-Plan:** [`2026-09-29-responses-systemteil-und-cache.md`](plans/2026-09-29-responses-systemteil-und-cache.md)
- **Kette-Plan (Tempo):** [`2026-09-30-muster-kette-zeit.md`](plans/2026-09-30-muster-kette-zeit.md)
- **Paket 1 (Sprache, Kleinbefunde):** [`2026-10-01-paket-1-sprache-und-kleinbefunde.md`](plans/2026-10-01-paket-1-sprache-und-kleinbefunde.md) — erledigt dort: Schnellantworten in der Antwortsprache, Startnachricht beim Sprachwechsel, Guide-Regeln ohne Neustart, Quick Wins aus Audit §7.
- **Audit 2026-09-29:** [`audits/2026-09-29-audit.md`](audits/2026-09-29-audit.md) — behoben dort: der Transport-Retry mit `confirmToken` und das Token im INFO-Log (früher §1.2/§1.3), `pip-audit` (jetzt in der CI), zwei Aufräumpunkte aus §5 und eine der unter Last kippenden Test-Dateien (siehe §5).

## 1 Befunde mit Wirkung im Betrieb

1. **Seitentext und System-Blöcke auf dem Responses-Weg.**
   - Zusammenfügen: LiteLLM verbindet die `system`-Blöcke mit einem Leerzeichen zu `instructions`, Überschriften stehen dadurch mitten in der Zeile.
   - Fremdtext:
     - Ein Satz aus dem Seitentext stand wörtlich in `instructions`, also Fremdtext auf Systemebene.
     - Kompendium, Volltext und Beschreibung stehen ungerahmt im Seitenblock.
   - Cache:
     - Jede Änderung auf Systemebene kostet den ganzen Cache. Auf einer neuen Seite kamen 0 von 18 674 Token aus dem Cache.
     - Die Begründung „stabiles Präfix“ in `graph/nodes/respond_agent.py` trifft deshalb nicht zu.
   - Messung:
     - Gegen OpenAI direkt gemessen (`gpt-6-luna`).
     - Die b-api-openai ist wahrscheinlich ebenso betroffen, dort aber nicht gemessen. LiteLLM leitet ab gpt-5.4 Aufrufe mit Werkzeugen über `/v1/responses`.
   - Vorschläge A–D und N stehen im Responses-Plan.
2. **`retention_days` ohne Wirkung.**
   - Das Feld steht zweimal in `domain/config_models/base_governance.py` (Z. 66 und 134). Kein Code liest es, einen Lösch-Job gibt es nicht.
   - Die Einstellung verspricht also eine Aufbewahrungsfrist, die niemand durchsetzt.
3. **Ein Merkposten überdauert Züge, die vor dem Vorlauf enden** (Review Paket 2, 2026-10-01; niedrig, älter als Paket 2).
   - Tour- und Kontext-Gruß-Züge enden vor `preflight` (`graph/build.py:117-125`), dort läuft `discard_stale_approval` also nicht. `context_greeting` schreibt `entities` samt `_pending_write` zurück.
   - Folge: Vorschau → Tour → ein glattes „ok“ binnen 10 Minuten führt die alte Änderung aus. Die Regel „nur die direkte Antwort auf die Vorschau bestätigt“ gilt also nicht über diese Züge hinweg.
   - Vorschlag: in beiden frühen Ausgängen `_pending_write` verwerfen oder `discard_stale_approval` vor die Tour ziehen.
   - Nebenbei: `GET /api/sessions/{id}` (nur mit Studio-Schlüssel) gibt die rohen `entities` samt Bestätigungsschlüssel aus (einmal gültig, 10 Minuten).
4. **Befunde aus dem Audit 2026-09-29**, die noch offen sind: siehe [`audits/2026-09-29-audit.md`](audits/2026-09-29-audit.md), Abschnitte 6–9. Behoben sind die Punkte der Tabelle in Abschnitt 4a (seit Tag `0.3`).

## 2 Entscheidungen des Nutzers

- **Responses-Plan (§9):**
  - Umfang von A: beide OpenAI-Wege oder nur der für gpt-6?
  - B:
    - Die Kostenfolge bei großen Volltexten steht in §4.2.
    - Der Wortlaut der Seitenregeln steht in §6, Task B3; danach braucht es einen Golden-Lauf.
  - „Zuletzt gezeigt“: so lassen oder umbauen? Der Block steht vor der Nachricht. Ab dem Folgezug trifft der Cache deshalb nur noch den Systemteil.
  - Paket D: der UI-Box-Status wandert an die Werkzeug-Nachricht und weicht damit bewusst von ALT ab.
  - Offen ist auch, ob AcademicCloud zwei `user`-Nachrichten hintereinander verträgt.
- **ST-5-Lesart, Befunde 1, 2 und 4** (Betriebsmodi-Plan §13, Zeile „ST-5-Lesart: vier Befunde“):
  - **Befund 1:** `create-triggers` und `edit-triggers` sind überholt.
    - Im ALT sind sie seit Welle E stillgelegt; die Erstell-Verben wirken heute über `classify-overrides`.
    - Empfehlung: bereinigen, also Modell, Seeds, Lader, Heuristiken, Studio-Abschnitte, Texte und Tests. Dabei fallen Dateien weg.
  - **Befund 2:** `01-base/rag-retrieval` wird von beiden Maschinen gelesen, ist aber nicht registriert.
    - Empfehlung: mit leerem Seed registrieren. Das Studio weist dann darauf hin, dass Umgebungsvariablen Vorrang haben.
    - Alternative: den nie beschreibbaren YAML-Zweig streichen.
  - **Befund 4:** Die Muster-Kennung `AGENT` ist nicht reserviert.
    - Eine Muster-Datei mit dieser Kennung setzte die Chip-Politik der Agent-Züge. In der Muster-Maschine schaltete sie den Karten-Schutz ab.
    - Seit Runde 2 knüpft auch `turn_links.py` an diese Kennung an.
    - Empfehlung: die Kennung reservieren. Der Lader überspringt sie mit Warnung, das Studio weist sie ab.
- **D-10 und D-11** (Betriebsmodi-Plan §11):
  - D-10: Ersetzt oder ergänzt der Master-Skill im Muster-Modus Grundpersona und Domänen-Regeln?
  - D-11: In welcher Währung rechnet die Preistafel? Lokal steht sie auf USD.
  - Aufräumen: D-8 ist durch den Bau von ST-1, ST-2, ST-6 und ST-9 erledigt, steht im Plan aber noch als offen.
- **Studio-Akzent als Textfarbe:**
  - `--st-accent` erreicht 4,5:1 nur auf Weiß. Der aktive Navigationspunkt liegt bei 4,15:1, Links auf `--st-bg` bei 4,43:1.
  - Ein dunklerer Akzent wie `#1b64d9` läge überall bei mindestens 4,86:1. Das ist eine Frage der Markenfarbe.
- **EscalationBlock-Vorgaben:**
  - Im Modell stehen `legal_classifier` und `downgrade_false_positives` auf `False` (`base_governance.py:40/43`). Der Code fällt auf `True` zurück (`services/safety/service.py:81/177`).
  - Angleichen hieße: im Modell `True` setzen und `area-schemas.fixture.ts` neu erzeugen.
- **`AgentLimits.safety`** (`domain/config_models/engine.py:119`) hat keinen Leser, das Sicherheits-Gate läuft immer.
  - Entweder das Feld entfernen oder es bewusst stehen lassen. Der heutige Zustand ist der sichere.
- **Ablehnungen als ERROR** (`services/mcp/transport.py:166`):
  - Senkt man sie auf WARNING, verlieren auch edu-sharing-Ausfälle den ERROR-Alarm, die der MCP-Server als Werkzeugfehler meldet.
- **GV-RED-1** schreibt real auf Staging (Muster-Modus; im Agent-Modus nur mit persönlicher Anmeldung, die Golden-Läufe nicht haben). Soll der Fall im Standard-Set der Golden-Suite bleiben?
- **Audit 2026-08-12:**
  - F-2: Die zwei High-CVEs in Angular und DOMPurify anheben oder als Restrisiko festhalten?
  - F-6: Persistenz-Reihenfolge im Zug-Abschluss.
- **Audit 2026-09-29, Abschnitt 10** (Details dort):
  - B-H3: Kuration unter dem Dienst-Token nur mit persönlicher Anmeldung oder mit ausdrücklichem Schalter?
    - Stand Paket 2 (2026-10-01): Der Agent-Zug reicht eine Schreib-Abnahme nur bei persönlicher Anmeldung in die Sitzung (Nutzer-Entscheid 2026-08-12).
    - Der Muster-Weg (S5) bietet die Kuration weiter schon mit dem Dienst-Token an, und der Vorlauf löst dort ein „ja“ ohne Rechteprüfung ein (`services/write_approval.py`, bewusst).
  - C-H1: clusterweite Sitzungssperre (Advisory-Lock, Valkey-Lease oder `turn_count`-CAS)? Bis dahin nur eine Replik?
  - CSP/HSTS für `/studio` oder eigener Ursprung?
  - `markitdown`-Extras für PDF/DOCX-Ingest; MPL-2.0 als Lizenz-Ausnahme?
  - SSE-Abbruch: verlassenen Zug zu Ende führen oder abbrechen?
  - `retention_days` (§1.2): Lösch-Job bauen oder Feld streichen?
  - B-API-Moderation: reicht Bearer allein?
- **Moderations-Schwellen:** Andeutungen blieben live unter den Seed-Schwellen (self_harm 0,45 und 0,28). Ein Nachjustieren wäre ein eigener Entscheid.
- **Vorgabe-Maschine neuer Anlagen:** Der Seed setzt `01-base/engine.yaml` bewusst auf `mode: pattern` („ohne Pflege ändert sich nichts“), D-15 macht dagegen die Agent-Schleife im Betrieb zur Vorgabe.
  - Folge: Eine Anlage ohne gespeicherte Einstellung antwortet mit der Muster-Maschine, und der Master-Skill wirkt dort nicht. So war es im lokalen Testcontainer am 2026-09-30.
  - Entscheidung: die Seed-Vorgabe auf `agent` stellen oder je Anlage im Studio („Agent & Maschine“) umschalten?

- **Kette-Plan, Agent-Schnellantworten:** `AGENT_INLINE_QUICK_REPLIES` ist gebaut und steht auf aus.
  - Gemessen: Agent-Zug 12,2 → 6,8 s im Median, 8 von 8 Zügen per `respond_to_user`.
  - Zum Einschalten zuerst den Master-Skill-Abschnitt „Schnellantworten“ anpassen. Der Text steht im Kette-Plan unter „Agent-Modus“, danach in die Vorlage `docs/skills/vorgehen.md` übernehmen.
- **Kette-Plan, Fast-Modus (`LLM_SERVICE_TIER=fast`):** einsetzen oder nicht?
  - Gemessen: Muster-Zug 9,1 → 7,7 s im Median.
  - Dagegen stehen 4- bis 5-facher Tokenpreis und keine EU-Datenresidenz. Über die b-api ist er ungemessen, er wirkt nur bei `LLM_PROVIDER=openai`.
- **Kette-Plan, nächste Hebel:** Token-Streaming zum Widget (größter Hebel für die gefühlte Wartezeit, eigener Plan) und RAG parallel zur Klassifikation (M15: bis 2,0 s).
- **Antwortsprache im Muster-Modus** (Paket 1, E1; gemessen 2026-10-01):
  - Der Muster-Modus antwortet in der Sprache der Oberfläche, auch wenn die Person anders schreibt: „Antworte auf Deutsch“ (`services/response_prompt_tools_text.py:63-69`).
  - Der Agent folgt der Sprache der Person und nimmt die Oberflächensprache als Rückfall.
  - Frage: Soll der Muster-Modus es wie der Agent halten? Das wäre eine Prompt-Änderung, danach braucht es einen Golden-Lauf.
- **Kontext-Gruß beim Sprachwechsel** (Paket 1, T2):
  - Die feste Startnachricht wechselt jetzt die Sprache, der Seitengruß des Backends nicht.
  - Grund: Er ist gespeichert, und ein zweiter Ping in derselben Sitzung wird unterdrückt (`graph/nodes/context_greeting.py`, Gate 4).
  - Frage: Lohnt ein eigener Weg, etwa ein Ping mit „neu in dieser Sprache“, der den Gruß ersetzt?
- **RAG im Muster-Weg nur für M04 und M15 – so gewollt?** (gefunden 2026-10-01)
  - `phase3_modulate` schreibt `rag_areas` immer als Liste (`domain/pattern_engine.py:263`), auch leer. `domain/route_head.py:33` nimmt deshalb stets die Liste des Musters; der Zweig „alle `always`-Bereiche“ (Z. 37–44) wird nie erreicht.
  - Im Seed tragen nur M04 und M15 eine Bereichsliste. Alle anderen Muster antworten ohne Wissensbereiche, auch wenn ein Bereich auf `mode: always` steht.

## 3 Messungen und Prüfungen (startet der Nutzer)

- **Kette-Plan:** ein Golden-Lauf im Muster-Modus mit den Schnellantworten im Antwort-Aufruf.
  - Ob Inline getroffen hat, zeigt `per_phase` je Zug: Fehlt die Phase `quick_replies`, kamen sie aus dem Antwort-Aufruf.
  - Die neuen Zeit-Zeilen im Debug-Block (`zeit`/`llm`) zeigen je Zug, wo die Zeit liegt.

- **Nachmessung der Agent-Runde 2 (E2):** Golden-Läufe im Agent-Modus mit dem übertragenen Master-Skill.
  - Erfolg laut Runde-2-Plan:
    - Die harte Quote liegt in der Spanne der Muster-Maschine.
    - Kein Fehler kehrt in allen drei Läufen wieder.
    - Die Kosten je Zug liegen unter 0,00303 USD (E-5).
  - Danach über B1–B3 (Anrede) entscheiden.
- **Responses-Plan, Paket C:** die Folgezüge mit den Rundendaten nachmessen, bevor über B entschieden wird.
- **Einbettung mit Ticket (zweite Betriebsform):** Die Live-Probe steht aus, siehe [`2026-08-12-einbettung-ohne-repo-aenderung.md`](plans/2026-08-12-einbettung-ohne-repo-aenderung.md).
- **Studio:**
  - Einen Screenreader-Test gab es bisher nicht.
  - Den Start-Knopf des generativen Laufs hat niemand im Browser gesehen. Sein CSS gleicht dem gemessenen Gold-Knopf, und der Kontrast-Wächter deckt ihn ab.

## 4 Beim nächsten Deploy

- **Migrationen `0004` und `0005`** — `alembic upgrade head` ausführen; der Dienst `migrate` in `compose.prod.yml` erledigt das beim Start:
  - `0004`: `usage_events.engine`, nullbar, reine Katalogänderung.
  - `0005`: drei Indizes auf Sitzungs-Log, Qualitäts-Log und Konfig-Historie.
- **Geänderte Seeds** wirken nur in Bereichen, die nicht gespeichert sind:
  - Betroffen sind `01-base/engine.yaml`, `02-domain/domain-rules.md`, `03-patterns/m01-krisen-empathie.md`, `03-patterns/m02-bedrohungs-refusal.md`, `04-personas/elt.md`, `04-personas/ler.md`, `05-knowledge/rag-config.yaml` und `eval/gold-flows.yaml`.
  - Gespeicherte Bereiche im Studio abgleichen. Sicher betroffen ist die Rolle auf „Agent & Maschine“, wo sie schon gespeichert wurde.
- **Golden-Seeds** nach dem Deploy auf Staging importieren.
- **Master-Skill:** nach jedem Übertragen `cd backend && uv run python scripts/check_master_skill.py` ausführen.
  - Die Rückgabe 0 heißt: alle Regeln erfüllt. 1 heißt: mindestens eine verletzt. 2 heißt: nicht abrufbar.
- **Master-Skill „Ändern“ übertragen** (Paket 2, Runde-2-Plan N-3):
  - Mit Paket 2 zeigt der Chat die Vorschau einer Änderung auch im Agent-Zug von selbst als Kasten mit Knopf. Der Knoten sagt noch, das Modell lege sie „wörtlich als gerahmten Kasten“ vor; folgt es dem mit `zeige_dokument`, stehen zwei Kästen da.
  - Die Vorlage `docs/skills/vorgehen.md` ist berichtigt (Abschnitt „Im Bestand ändern (M18)“). Übertragen in den Knoten `535cabca…` machen Nutzer bzw. Redaktion.
  - Bis dahin meldet das Prüfskript die neue Regel `test_die_aenderungs_vorschau_zeigt_der_chat_selbst` als verletzt (Rückgabe 1).

## 5 Aufräumen

- **Dateien über der 300-Zeilen-Regel** (Audit F-8), aus diesen Runden:
  - Backend: `graph/nodes/respond_agent.py` (499; 2026-10-01 +22 für den Agent-Schnellantwort-Weg, +10 für Paket 2), `services/agent_loop.py` (491), `services/write_approval.py` (316; vorher 304, Paket 2 +12 für `merke_abnahme`).
  - Studio: `schema-form/schema-form.scss` (432), `views/curated-views.ts` (399), `i18n/catalogue/curated.ts` (386), `views/eval-run-detail.component.ts` (315), `schema-form/schema-field.component.ts` (311).
  - Die Schnitte stehen im Betriebsmodi-Plan §9.3.
- Der Abnahme-Zug steht im Debug- und Qualitätsprotokoll auch im Agent-Modus als `M18` (Runde-2-Plan, N-5; kosmetisch).
- Ein Server, der „Tool not found“ als JSON-RPC-Fehler meldet, landet als `transport` in der Wiederholung. Der eingestellte Server meldet es als Werkzeug-Ergebnis und ist deshalb nicht betroffen.
- **Frontend-Tests kippen unter Last.**
  - Im vollen Lauf am 2026-09-29 fielen 5 Studio-Dateien um (`i18n/en.spec.ts`, `agent-skills`, `eval-trends`, `loadtest`, `rag-ingest`) und `ui/print/print-utils.spec.ts`; einzeln und im Wiederholungslauf grün.
  - Audit 2026-09-29: `print-utils.spec.ts` läuft jetzt mit fester Uhr, `studio/core/download.spec.ts` stellt die veränderten Globals zurück (`isolate: false`). Die übrigen Kipper ließen sich nicht reproduzieren; bei erneutem Auftreten Datei und Fehlermeldung festhalten.
- Der Klassifikator läuft über `instructor` statt über `llm.chat_completion` und liest im Fehlerpfad nur `choices[0]` (`services/classify.py:123`).
  - Auf dem Responses-Weg liefe ein Text mit Aufruf dort ins Leere. Der Aufruf ist aber erzwungen, und ein Ausfall ist nicht beobachtet. Das ist ein Restrisiko, kein Befund.
- Dem Studio fehlt `color-scheme: light dark`.
  - Folge: Ungestylte Steuerelemente bleiben im Dunkelmodus hell.
  - Das Select `.ri-area-pick` besteht trotzdem mit 3,76:1.
- **Angular 22.1 → 22.2:** `npm audit` meldet `@angular/router` als „high“ (GHSA-ff3f-86qr-9cv3).
  - Der Fund betrifft nur serverseitiges Rendering. Studio und Widget laufen im Browser und sind deshalb nicht betroffen.
  - Der Fix verlangt `@angular/core`, `common` und `platform-browser` in derselben Version. Also alle `@angular/*` gemeinsam anheben (`ng update`), danach Tests, Builds und Budget prüfen.
  - Die übrigen Funde hat `npm audit fix` am 2026-10-01 behoben (Paket 1).
- **Einstellungen ohne Leser** (gefunden 2026-10-01 beim Bau der Konfigurations-Grafiken, Stand `1f069e9`). Das Studio bietet sie an, der Code liest sie nicht:
  - `01-base/engine`: `agent.safety` (nur in `domain/config_models/engine.py:119`).
  - `01-base/safety-config`: `extra_crisis_terms`, `extra_pii_terms`, `confidence_adjustments` (nur in `domain/config_models/base_governance.py:92-102`); `retention_days` siehe §1.2.
  - `01-base/display-rules`: `quick_replies.inline_fallback_enabled` (der Lader gibt es weiter, niemand wertet es aus).
  - `01-base/guide-mode`: `default_enabled` (so auch in `domain/area_effects.py:65`).
  - Attribut `inline_result_grouping` im Muster-Prompt: Der Block hängt zusätzlich an `cards_enabled` (`services/response_prompt_builder.py:138-141`), und dieses Feld hat `Environment` nicht. Der Block entsteht also nie; im Agent-Weg wirkt das Attribut.
  - Umgebung: `RERANK_URL` und `TEXT_EXTRACTION_URL` stehen nur in `settings.py`.
  - Paket `langgraph-checkpoint-postgres` ist deklariert, wird aber nicht importiert (der Graph läuft bewusst ohne Checkpointer, `graph/build.py:44-48`); es zieht psycopg mit.

## 6 Zurückgestellte Plan-Teile

- **ST-4c, ST-3d und die Architektur-Referenz (ST-5)** sind mit Z2 fällig (Betriebsmodi-Plan §9.3).
- **B1–B3 (Anrede)** folgen nach der Nachmessung (Runde-2-Plan, Paket B).
