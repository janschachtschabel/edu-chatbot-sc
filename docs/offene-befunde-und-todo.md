# Offene Befunde und Todo

Stand 2026-09-29 (Zwischenstand), nachgezogen 2026-10-03 nach Paket 4 und 2026-10-08 nach Paket 4b und 4c. Diese Liste sammelt an einer Stelle, was nach diesem Stand offen ist, jeweils mit Quelle.
Erledigtes steht in den Logs der Pläne, nicht hier. Wer einen Punkt erledigt, streicht ihn hier und
trägt ihn im Log des zugehörigen Plans ein. Zeilennummern gelten für den Stand 2026-09-29.

Die zugehörigen Pläne:
- **Betriebsmodi-Plan:** [`2026-09-26-betriebsmodi-und-studio.md`](plans/2026-09-26-betriebsmodi-und-studio.md)
- **Runde-2-Plan:** [`2026-09-28-agent-runde-2.md`](plans/2026-09-28-agent-runde-2.md) — erledigt dort (Paket 2, 2026-10-01): die Schreib-Abnahme im Agent-Modus (früher §1.1), Log unter „Nebenbefund außerhalb dieser Runde“.
- **Responses-Plan:** [`2026-09-29-responses-systemteil-und-cache.md`](plans/2026-09-29-responses-systemteil-und-cache.md)
- **Kette-Plan (Tempo):** [`2026-09-30-muster-kette-zeit.md`](plans/2026-09-30-muster-kette-zeit.md)
- **Paket 1 (Sprache, Kleinbefunde):** [`2026-10-01-paket-1-sprache-und-kleinbefunde.md`](plans/2026-10-01-paket-1-sprache-und-kleinbefunde.md) — erledigt dort: Schnellantworten in der Antwortsprache, Startnachricht beim Sprachwechsel, Guide-Regeln ohne Neustart, Quick Wins aus Audit §7.
- **Token-Streaming-Plan:** [`2026-10-01-token-streaming.md`](plans/2026-10-01-token-streaming.md) — freigegeben 2026-10-03 (alle Empfehlungen), gebaut hinter `CHAT_TOKEN_STREAMING` (PR #9); Stand im Log des Plans.
- **Paket 3 (offene Befunde, erste Runde):** [`2026-10-03-paket-3-offene-befunde.md`](plans/2026-10-03-paket-3-offene-befunde.md) — erledigt dort: Neustart mitten im Zug (früher §1.4), EscalationBlock-Vorgaben und Kennung `AGENT` (früher §2) sowie sieben Befunde aus dem Audit 2026-09-29 (Nachtrag dort in §7).
- **Paket 4b (Folgebefunde aus Paket 4):** [`2026-10-08-paket-4b-folgebefunde.md`](plans/2026-10-08-paket-4b-folgebefunde.md) — erledigt dort: Studio-Auslieferung mit `Cache-Control` (früher §1.5), zehn `role="status"`-Stellen, `type` beim Speichern, Umwandlungsfehler am Typ statt am Präfix, Datenbankfehler als 400 mit Bereich.
- **Paket 4c (Rest aus den Reviews):** [`2026-10-08-paket-4c-rest-aus-den-reviews.md`](plans/2026-10-08-paket-4c-rest-aus-den-reviews.md) — erledigt dort: URL-Import ohne markitdown, Wert ohne JSON als 400 mit Bereich, Ansage „kein Werkzeug“ im MCP-Abgleich, „nicht gesetzt“ und „leer“ im Formular unterscheidbar.
- **Befund Kontext-Ping (2026-10-08):** [`2026-10-08-befund-abnahme-nach-kontext-ping.md`](plans/2026-10-08-befund-abnahme-nach-kontext-ping.md) — erledigt dort: Die Schreib-Abnahme verfiel an einem Zug, den die Person nie sah (Kontext-Ping, Tour-Tick ohne Tour). Auf „bestätigen“ kam deshalb wieder eine Vorschau.
- **Paket 4 (externes Audit und Restliste):** [`2026-10-03-paket-4-audit-extern.md`](plans/2026-10-03-paket-4-audit-extern.md).
  - Status: freigegeben und umgesetzt 2026-10-03 (Phasen V, A–E, L, S; Log im Plan). Zurückgestellt an Paket 5 bzw. ins Backlog: siehe Plan §5/§6.
  - Er gleicht das externe Audit [`audits/2026-10-03-audit-extern.md`](audits/2026-10-03-audit-extern.md) (Stand `610abec`) mit `e38006d` ab.
  - Jeder Befund geht an eine Aufgabe, an Paket 5 oder ins Backlog.
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
3. **Befunde aus dem Audit 2026-09-29**, die noch offen sind: siehe [`audits/2026-09-29-audit.md`](audits/2026-09-29-audit.md), Abschnitte 6–9. Behoben sind die Punkte der Tabelle in Abschnitt 4a (seit Tag `0.3`).
4. **Externes Audit 2026-10-03** (22 Befunde, Stand `610abec`), am Stand `e38006d` gegengeprüft:
   - 12 gelten weiter, 7 sind teilweise behoben, 3 sind behoben bzw. ohne die behauptete Wirkung.
   - Abgleich, Vermerke und Zuordnung stehen im Paket-4-Plan, §1.
   - Neu gegenüber dieser Liste:
     - Schreib-Abnahme ohne Identitätsprüfung beim Einlösen;
     - RAG-Import verliert Text;
     - Agent-Frist und Budget greifen nicht in laufende Aufrufe;
     - Ergebnis-Schema wird nicht geprüft;
     - MCP-Cache ohne Server;
     - Konfig-Abrufe überholen sich.
   - Paket 4 (2026-10-03/04) hat alle Befunde behoben, die nicht auf eine Entscheidung warten. Offen sind die Paket-5-Punkte (Plan §5) und das Backlog (Plan §6).

## 2 Entscheidungen des Nutzers

- **Responses-Plan (§9):**
  - Umfang von A: beide OpenAI-Wege oder nur der für gpt-6?
  - B:
    - Die Kostenfolge bei großen Volltexten steht in §4.2.
    - Der Wortlaut der Seitenregeln steht in §6, Task B3; danach braucht es einen Golden-Lauf.
  - „Zuletzt gezeigt“: so lassen oder umbauen? Der Block steht vor der Nachricht. Ab dem Folgezug trifft der Cache deshalb nur noch den Systemteil.
  - Paket D: der UI-Box-Status wandert an die Werkzeug-Nachricht und weicht damit bewusst von ALT ab.
  - Offen ist auch, ob AcademicCloud zwei `user`-Nachrichten hintereinander verträgt.
- **ST-5-Lesart, Befunde 1 und 2** (Betriebsmodi-Plan §13, Zeile „ST-5-Lesart: vier Befunde“; Befund 4 erledigt in Paket 3):
  - **Befund 1:** `create-triggers` und `edit-triggers` sind überholt.
    - Im ALT sind sie seit Welle E stillgelegt; die Erstell-Verben wirken heute über `classify-overrides`.
    - Empfehlung: bereinigen, also Modell, Seeds, Lader, Heuristiken, Studio-Abschnitte, Texte und Tests. Dabei fallen Dateien weg.
  - **Befund 2:** `01-base/rag-retrieval` wird von beiden Maschinen gelesen, ist aber nicht registriert.
    - Empfehlung: mit leerem Seed registrieren. Das Studio weist dann darauf hin, dass Umgebungsvariablen Vorrang haben.
    - Alternative: den nie beschreibbaren YAML-Zweig streichen.
- **D-10 und D-11** (Betriebsmodi-Plan §11):
  - D-10: Ersetzt oder ergänzt der Master-Skill im Muster-Modus Grundpersona und Domänen-Regeln?
  - D-11: In welcher Währung rechnet die Preistafel? Lokal steht sie auf USD.
  - Aufräumen: D-8 ist durch den Bau von ST-1, ST-2, ST-6 und ST-9 erledigt, steht im Plan aber noch als offen.
- **Studio-Akzent als Textfarbe:**
  - `--st-accent` erreicht 4,5:1 nur auf Weiß. Der aktive Navigationspunkt liegt bei 4,15:1, Links auf `--st-bg` bei 4,43:1.
  - Ein dunklerer Akzent wie `#1b64d9` läge überall bei mindestens 4,86:1. Das ist eine Frage der Markenfarbe.
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
- **Kette-Plan, nächste Hebel:** Token-Streaming zum Widget (Plan siehe oben, im Bau) und RAG parallel zur Klassifikation (M15: bis 2,0 s).
- **Antwortsprache im Muster-Modus** (Paket 1, E1; gemessen 2026-10-01):
  - Der Muster-Modus antwortet in der Sprache der Oberfläche, auch wenn die Person anders schreibt: „Antworte auf Deutsch“ (`services/response_prompt_tools_text.py:63-69`).
  - Der Agent folgt der Sprache der Person und nimmt die Oberflächensprache als Rückfall.
  - Frage: Soll der Muster-Modus es wie der Agent halten? Das wäre eine Prompt-Änderung, danach braucht es einen Golden-Lauf.
- **Kontext-Gruß beim Sprachwechsel** (Paket 1, T2):
  - Die feste Startnachricht wechselt jetzt die Sprache, der Seitengruß des Backends nicht.
  - Grund: Er ist gespeichert, und ein zweiter Ping in derselben Sitzung wird unterdrückt (`graph/nodes/context_greeting.py`, Gate 4).
  - Frage: Lohnt ein eigener Weg, etwa ein Ping mit „neu in dieser Sprache“, der den Gruß ersetzt?
- **M10 widerspricht sich selbst** (gefunden 2026-10-03, Paket 4 A2):
  - Der Muster-Text verlangt `query_knowledge` als Pflicht für Berichte. M10 steht aber auf `sources: [llm]`, und ohne `rag` bietet die Auswahl das Werkzeug nie an (`03-patterns/m10-ki-inhalt-generierung.md`).
  - Bis zur Entscheidung bleibt `query_knowledge` auch ohne Angebot rufbar (Ausnahme in der Werkzeug-Sperre, ein Test pinnt sie).
  - Frage: `rag` zu M10s Quellen nehmen oder die Pflicht aus dem Text streichen? Beides ändert Antworten; danach braucht es einen Golden-Lauf.
- **„Freigabe“ als Zustimmung** (gefunden 2026-10-08, Befund Kontext-Ping):
  - Ein Sammlungs-Gatekeeper-Skill bittet um „Freigabe“. `is_affirmation` (`domain/write_confirm.py`, `_ZUSTIMMUNG`) kennt „ja“, „bestätigen“, „ok“ usw., aber kein „Freigabe“/„freigeben“.
  - Ein „Freigabe erteilt“ ohne „ja“ verwirft deshalb den offenen Vorgang, und es kommt eine neue Vorschau.
  - Empfehlung: die Stämme `freigabe`, `freigeben`, `freigegeben` aufnehmen, nicht `frei` allein (sonst zählte „ist das frei verfügbar?“). Das ist eine Änderung an einer Sicherheitsregel, deshalb Nutzer-Entscheid.

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
- **Befund Kontext-Ping (2026-10-08):**
  - Im Staging-Log nach der Zeile `offener Vorgang für wlo_add_to_collection verworfen — dieser Zug ist keine Antwort auf die Vorschau` sehen. Sie belegt die Ursache.
  - Nach dem Deploy denselben Ablauf wiederholen: erschließen, in die Sammlung aufnehmen, bestätigen.
  - Nebenbefund: Der Gatekeeper-Skill der Sammlung „Optik“ ließ sich laut Verlauf mit seiner Knoten-ID nicht abrufen (`get_skill`). Das ist nicht untersucht.
- **Studio:**
  - Einen Screenreader-Test gab es bisher nicht.
  - Den Start-Knopf des generativen Laufs hat niemand im Browser gesehen. Sein CSS gleicht dem gemessenen Gold-Knopf, und der Kontrast-Wächter deckt ihn ab.

## 4 Beim nächsten Deploy

- **Migrationen `0004` bis `0006`** — `alembic upgrade head` ausführen; der Dienst `migrate` in `compose.prod.yml` erledigt das beim Start:
  - `0004`: `usage_events.engine`, nullbar, reine Katalogänderung.
  - `0005`: drei Indizes auf Sitzungs-Log, Qualitäts-Log und Konfig-Historie.
  - `0006` (Paket 4, E2): höchstens ein laufender Eval-Lauf. Überzählige `running`-Reste gehen dabei bis auf den jüngsten auf `failed`.
- **Vorgabe `BACKEND_REPLICAS` ist jetzt 1** (Paket 4, L4). Wer bisher ohne Eintrag lief, hatte drei Replikas und hat nach dem Deploy eine. Bewusst mehr erst nach C-H1 (Sitzungssperre über Replikas); bis dahin können zwei Züge einer Sitzung parallel laufen.
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
  - Backend: `graph/nodes/respond_agent.py` (508; 2026-10-01 +22 für den Agent-Schnellantwort-Weg, +10 für Paket 2, 2026-10-03 +9 für das Token-Streaming), `services/agent_loop.py` (635; +16 Token-Streaming, Paket 4 B1 +116 für Frist und Quittungen, Review +12), `services/config_store.py` (316; Paket 4 D1/D4/D5, Paket 4b A4 +2, Paket 4c A2 +5 — Cache-Frische, `put_many`, Konfliktschutz; der bedingte Schreibweg und die Fehlerabbildung liegen schon in `services/config_conflict.py`), `services/write_approval.py` (372; vorher 304, Paket 2 +12 für `merke_abnahme`, Paket 4 A1 +36 für das Aufrufer-Kennzeichen, Befund 2026-10-08 +20 für Hintergrund-Züge — überwiegend Docstrings), `graph/nodes/context_greeting.py` (492; schon vorher 476 und hier nicht geführt, Befund 2026-10-08 +16 — stumme Fehlerwege des Pings), `services/llm_streaming.py` (302; vorher 266, Token-Streaming T1/T2), `services/rag/ingest.py` (321; schon vorher 304 und hier nicht geführt, Paket 4b A3 +14, Paket 4c A1 +3 — die ALT-treuen Umwandler und der Speicherweg in einer Datei; ein Schnitt: die Umwandler nach `services/rag/umwandeln.py`), `domain/pattern_engine.py` (385; schon vorher 374 und hier nicht geführt, Paket 4c Review +11 — Fidelity-Port, Laden und Wählen der Muster in einer Datei).
  - Ältere Fidelity-Port-Dateien, die das Token-Streaming um wenige Zeilen verlängert hat: `graph/nodes/respond.py` (528), `services/tool_loop.py` (973), `domain/write_confirm.py` (448; Paket 2 +13, Befund 2026-10-08 +1), Widget `shell/chat-shell.component.ts` (862), `chat-shell.component.html` (323). Die neue Logik liegt in eigenen Modulen (`domain/stream_gate`, `domain/stream_preview`, `domain/tool_pflicht`, `services/token_stream`, `graph/nodes/respond_strom`).
  - CI: `.github/workflows/image.yml` (386; Paket 4 L3 samt Review, überwiegend Begründungs-Kommentar).
  - Studio: `schema-form/schema-form.scss` (458; Paket 4c B2 +24), `views/curated-views.ts` (399), `i18n/catalogue/curated.ts` (386), `views/eval-run-detail.component.ts` (315), `schema-form/schema-field.component.ts` (320; Paket 4c B2 +9; seine Vorlage steht mit 300 genau an der Grenze), `i18n/catalogue/area-editor.ts` (306; vorher 299, Paket 4c B2 +7). Schnitte für `schema-form` und `schema-field` stehen im Betriebsmodi-Plan §9.3 (entlang der Bausteine bzw. Feldarten).
- Der Abnahme-Zug steht im Debug- und Qualitätsprotokoll auch im Agent-Modus als `M18` (Runde-2-Plan, N-5; kosmetisch).
- Ein Server, der „Tool not found“ als JSON-RPC-Fehler meldet, landet als `transport` in der Wiederholung. Der eingestellte Server meldet es als Werkzeug-Ergebnis und ist deshalb nicht betroffen.
- **Frontend-Tests kippen unter Last.**
  - Im vollen Lauf am 2026-09-29 fielen 5 Studio-Dateien um (`i18n/en.spec.ts`, `agent-skills`, `eval-trends`, `loadtest`, `rag-ingest`) und `ui/print/print-utils.spec.ts`; einzeln und im Wiederholungslauf grün.
  - Audit 2026-09-29: `print-utils.spec.ts` läuft jetzt mit fester Uhr, `studio/core/download.spec.ts` stellt die veränderten Globals zurück (`isolate: false`). Die übrigen Kipper ließen sich nicht reproduzieren; bei erneutem Auftreten Datei und Fehlermeldung festhalten.
- Der Klassifikator läuft über `instructor` statt über `llm.chat_completion` und liest im Fehlerpfad nur `choices[0]` (`services/classify.py:123`).
  - Auf dem Responses-Weg liefe ein Text mit Aufruf dort ins Leere. Der Aufruf ist aber erzwungen, und ein Ausfall ist nicht beobachtet. Das ist ein Restrisiko, kein Befund.

- **Aus dem Review von Paket 4 (2026-10-04), älter als das Paket:**
  - **ReDoS in Lotsen-Regeln.** D6 prüft nur, ob ein Muster kompiliert. Ein ungünstiges Muster wie `^(\w+\s?)*$` blockiert bei einer langen Nachricht den Worker, und die Nachricht kommt von jedem Client. Vorschlag: ein Regex-Motor mit Zeitgrenze (`regex`, steht über `tiktoken` schon im Lock) oder verschachtelte Quantoren beim Speichern abweisen. Derselbe Motor könnte dann auch `pattern` in Ergebnis-Schemata prüfen; heute sind Muster dort nur ein Hinweis an das Modell (A3, Review R-2).
  - **URL-Import: tröpfelnde Kopfzeilen.** Die Gesamtfrist schneidet den Rumpf ab (Review R-7), Kopfzeilen und einzelne Umleitungen aber nicht, weil es dann noch keine Antwort gibt. Nur über das Studio erreichbar. Vorschlag: den Abruf über `httpx` (async) unter `asyncio.timeout` legen.
- **Aus dem Review von Paket 4c (2026-10-08), älter als das Paket:**
  - **`PUT /api/config/patterns` macht aus `sources: []` „nicht gesetzt“.** Die ALT-Route schreibt `sources` nur, wenn die Liste nicht leer ist (`api/config_elements.py`, `_pattern_frontmatter`). Ein ausdrückliches „keine Quelle“ wird nach GET→PUT zu `["mcp"]`; derselbe Kipp, den R-10 für `rag_areas` behoben hat. Nur über die API, das Studio speichert über `PUT /config/data`. Vorschlag: `PatternEntry.sources` als `list[str] | None` und schreiben, wenn nicht `None` (ändert den OpenAPI-Vertrag).
  - **Umwandlungsfehler beim RAG-Import:** Die Texte sind fest deutsch und werden roh durchgereicht (`api/rag.py`). Ein fehlendes Paket im Image antwortet 400, obwohl es ein Fehler des Servers ist. A1 hat das Verhalten des Datei-Wegs übernommen, wie geplant.
  - **Tests werden unter Last still übersprungen.** Module mit `pytestmark = skipif(not pg_utils.dev_db_ready())` prüfen beim Einsammeln mit 3 s Frist. Gibt die Verbindung unter Last nach, fällt das ganze Modul ohne Fehler aus. Am 2026-10-08 traf es `test_guide_mode_endpoint.py` (9 Tests) in einem vollen Lauf, während eine andere Sitzung parallel testete. In der CI hieße das: grün, obwohl nicht geprüft. Vorschlag: längere Frist, oder in der CI (`CI=true`) scheitern statt überspringen.
- **Aus dem zweiten Review von Paket 4b (2026-10-08):** Die drei Code-Befunde sind in Paket 4c erledigt (URL-Import, Wert ohne JSON, Ansage „kein Werkzeug“). Offen bleibt:
  - **Testinstanz: MCP-Registry gegen den Server.** Die Registry erwartet `search_skill`; der installierte WLO-MCP-Server läuft mit `WLO_DISABLE_SKILL_SEARCH` und bietet es nicht an. Damit scheitert die Skill-Suche im Studio. Eine Konfigurationsfrage für den Betrieb: das Werkzeug in der Registry streichen oder die Skill-Suche am Server einschalten.
- **Studio-Startpaket 1,08 MB** (gemessen 2026-10-03, Paket 4 L1). Angular 22.2 weist den gemeinsamen Chunk (`@angular/core` u. a.) richtig als initial aus; 22.1 nannte ihn „lazy“, geladen wurde er schon immer beim Start.
  - Größter Posten: beide Sprach-Kataloge des Studios, 434 kB, eager (`i18n/de.ts`, `i18n/en.ts`).
  - Das Budget ist an den echten Stand angepasst (Warnung 1,1 MB, Fehler 1,2 MB). Ein möglicher Schnitt: `en` erst beim Umschalten laden.
- **Wirksame Wissensbereiche je Muster** (externes Audit F13, Verbesserung): Seit Paket 4c (B2) unterscheidet das Formular „nicht gesetzt“ (es gilt die Vorgabe) von „leer“ und bietet „Vorgabe wiederherstellen“. Welche Bereiche damit tatsächlich wirken (alle aus dem Katalog, falls `rag` unter den Quellen steht), zeigt es noch nicht an.

- **Einstellungen ohne Leser** (gefunden 2026-10-01 beim Bau der Konfigurations-Grafiken, Stand `1f069e9`). Das Studio bietet sie an, der Code liest sie nicht:
  - `01-base/engine`: `agent.safety` (nur in `domain/config_models/engine.py:119`).
  - `01-base/safety-config`: `confidence_adjustments` (nur in `domain/config_models/base_governance.py`); `retention_days` siehe §1.2. `extra_crisis_terms` und `extra_pii_terms` wirken seit Paket 4 (D8).
  - `01-base/display-rules`: `quick_replies.inline_fallback_enabled` (der Lader gibt es weiter, niemand wertet es aus).
  - `01-base/guide-mode`: `default_enabled` (so auch in `domain/area_effects.py:65`).
  - Attribut `inline_result_grouping` im Muster-Prompt: Der Block hängt zusätzlich an `cards_enabled` (`services/response_prompt_builder.py:138-141`), und dieses Feld hat `Environment` nicht. Der Block entsteht also nie; im Agent-Weg wirkt das Attribut.
  - Umgebung: `RERANK_URL` und `TEXT_EXTRACTION_URL` stehen nur in `settings.py`.

## 6 Zurückgestellte Plan-Teile

- **ST-4c, ST-3d und die Architektur-Referenz (ST-5)** sind mit Z2 fällig (Betriebsmodi-Plan §9.3).
- **B1–B3 (Anrede)** folgen nach der Nachmessung (Runde-2-Plan, Paket B).
