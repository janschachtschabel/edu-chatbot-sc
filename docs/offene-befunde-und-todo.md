# Offene Befunde und Todo

Stand 2026-09-29 (Zwischenstand). Diese Liste sammelt an einer Stelle, was nach diesem Stand offen ist, jeweils mit Quelle.
Erledigtes steht in den Logs der Pläne, nicht hier. Wer einen Punkt erledigt, streicht ihn hier und
trägt ihn im Log des zugehörigen Plans ein. Zeilennummern gelten für den Stand 2026-09-29.

Die zugehörigen Pläne:
- **Betriebsmodi-Plan:** [`2026-09-26-betriebsmodi-und-studio.md`](plans/2026-09-26-betriebsmodi-und-studio.md)
- **Runde-2-Plan:** [`2026-09-28-agent-runde-2.md`](plans/2026-09-28-agent-runde-2.md)
- **Responses-Plan:** [`2026-09-29-responses-systemteil-und-cache.md`](plans/2026-09-29-responses-systemteil-und-cache.md)
- **Audit 2026-09-29:** [`audits/2026-09-29-audit.md`](audits/2026-09-29-audit.md) — behoben dort: der Transport-Retry mit `confirmToken` und das Token im INFO-Log (früher §1.2/§1.3), `pip-audit` (jetzt in der CI), zwei Aufräumpunkte aus §5 und eine der unter Last kippenden Test-Dateien (siehe §5).

## 1 Befunde mit Wirkung im Betrieb

1. **Schreiben im Agent-Modus endet im Chat bei der Vorschau.**
   - Ursache: Den Merkposten `_pending_write` und die Vorschau-Box `_write_preview` setzt nur die Werkzeugschleife der Muster-Maschine. Die Abnahme im Vorlauf („ja“ → ausführen) findet im Agent-Modus deshalb nichts vor.
   - Seit D-15 ist der Agent im Chat die Vorgabe.
   - Beleg: zwei strikte `xfail` in `backend/tests/test_agent_schreib_abnahme.py`.
   - Stand: Der Vorschlag steht im Runde-2-Plan unter „Nebenbefund außerhalb dieser Runde“ und ist noch nicht gebaut.
2. **Seitentext und System-Blöcke auf dem Responses-Weg.**
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
3. **`retention_days` ohne Wirkung.**
   - Das Feld steht zweimal in `domain/config_models/base_governance.py` (Z. 66 und 134). Kein Code liest es, einen Lösch-Job gibt es nicht.
   - Die Einstellung verspricht also eine Aufbewahrungsfrist, die niemand durchsetzt.
4. **Befunde aus dem Audit 2026-09-29**, die noch offen sind: siehe [`audits/2026-09-29-audit.md`](audits/2026-09-29-audit.md), Abschnitte 6–9. Behoben sind die Punkte der Tabelle in Abschnitt 4a (Änderungen liegen uncommittet vor).

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
- **GV-RED-1** schreibt real auf Staging. Soll der Fall im Standard-Set der Golden-Suite bleiben?
- **Audit 2026-08-12:**
  - F-2: Die zwei High-CVEs in Angular und DOMPurify anheben oder als Restrisiko festhalten?
  - F-6: Persistenz-Reihenfolge im Zug-Abschluss.
- **Audit 2026-09-29, Abschnitt 10** (Details dort):
  - B-H3: Kuration unter dem Dienst-Token nur mit persönlicher Anmeldung oder mit ausdrücklichem Schalter?
  - C-H1: clusterweite Sitzungssperre (Advisory-Lock, Valkey-Lease oder `turn_count`-CAS)? Bis dahin nur eine Replik?
  - CSP/HSTS für `/studio` oder eigener Ursprung?
  - `markitdown`-Extras für PDF/DOCX-Ingest; MPL-2.0 als Lizenz-Ausnahme?
  - SSE-Abbruch: verlassenen Zug zu Ende führen oder abbrechen?
  - `retention_days` (§1.3): Lösch-Job bauen oder Feld streichen?
  - B-API-Moderation: reicht Bearer allein?
- **Moderations-Schwellen:** Andeutungen blieben live unter den Seed-Schwellen (self_harm 0,45 und 0,28). Ein Nachjustieren wäre ein eigener Entscheid.
- **Vorgabe-Maschine neuer Anlagen:** Der Seed setzt `01-base/engine.yaml` bewusst auf `mode: pattern` („ohne Pflege ändert sich nichts“), D-15 macht dagegen die Agent-Schleife im Betrieb zur Vorgabe.
  - Folge: Eine Anlage ohne gespeicherte Einstellung antwortet mit der Muster-Maschine, und der Master-Skill wirkt dort nicht. So war es im lokalen Testcontainer am 2026-09-30.
  - Entscheidung: die Seed-Vorgabe auf `agent` stellen oder je Anlage im Studio („Agent & Maschine“) umschalten?

## 3 Messungen und Prüfungen (startet der Nutzer)

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

- **Migration `0004`** (`usage_events.engine`, nullbar, reine Katalogänderung): `alembic upgrade head` ausführen.
- **Geänderte Seeds** wirken nur in Bereichen, die nicht gespeichert sind:
  - Betroffen sind `01-base/engine.yaml`, `02-domain/domain-rules.md`, `03-patterns/m01-krisen-empathie.md`, `03-patterns/m02-bedrohungs-refusal.md`, `04-personas/elt.md`, `04-personas/ler.md`, `05-knowledge/rag-config.yaml` und `eval/gold-flows.yaml`.
  - Gespeicherte Bereiche im Studio abgleichen. Sicher betroffen ist die Rolle auf „Agent & Maschine“, wo sie schon gespeichert wurde.
- **Golden-Seeds** nach dem Deploy auf Staging importieren.
- **Master-Skill:** nach jedem Übertragen `cd backend && uv run python scripts/check_master_skill.py` ausführen.
  - Die Rückgabe 0 heißt: alle Regeln erfüllt. 1 heißt: mindestens eine verletzt. 2 heißt: nicht abrufbar.

## 5 Aufräumen

- **Dateien über der 300-Zeilen-Regel** (Audit F-8), aus diesen Runden:
  - Backend: `graph/nodes/respond_agent.py` (467).
  - Studio: `schema-form/schema-form.scss` (432), `views/curated-views.ts` (399), `i18n/catalogue/curated.ts` (386), `views/eval-run-detail.component.ts` (315), `schema-form/schema-field.component.ts` (311).
  - Die Schnitte stehen im Betriebsmodi-Plan §9.3.
- Ein Server, der „Tool not found“ als JSON-RPC-Fehler meldet, landet als `transport` in der Wiederholung. Der eingestellte Server meldet es als Werkzeug-Ergebnis und ist deshalb nicht betroffen.
- **Frontend-Tests kippen unter Last.**
  - Im vollen Lauf am 2026-09-29 fielen 5 Studio-Dateien um (`i18n/en.spec.ts`, `agent-skills`, `eval-trends`, `loadtest`, `rag-ingest`) und `ui/print/print-utils.spec.ts`; einzeln und im Wiederholungslauf grün.
  - Audit 2026-09-29: `print-utils.spec.ts` läuft jetzt mit fester Uhr, `studio/core/download.spec.ts` stellt die veränderten Globals zurück (`isolate: false`). Die übrigen Kipper ließen sich nicht reproduzieren; bei erneutem Auftreten Datei und Fehlermeldung festhalten.
- Der Klassifikator läuft über `instructor` statt über `llm.chat_completion` und liest im Fehlerpfad nur `choices[0]` (`services/classify.py:123`).
  - Auf dem Responses-Weg liefe ein Text mit Aufruf dort ins Leere. Der Aufruf ist aber erzwungen, und ein Ausfall ist nicht beobachtet. Das ist ein Restrisiko, kein Befund.
- Dem Studio fehlt `color-scheme: light dark`.
  - Folge: Ungestylte Steuerelemente bleiben im Dunkelmodus hell.
  - Das Select `.ri-area-pick` besteht trotzdem mit 3,76:1.

## 6 Zurückgestellte Plan-Teile

- **ST-4c, ST-3d und die Architektur-Referenz (ST-5)** sind mit Z2 fällig (Betriebsmodi-Plan §9.3).
- **B1–B3 (Anrede)** folgen nach der Nachmessung (Runde-2-Plan, Paket B).
