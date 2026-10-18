# Paket 16 — Studio nach Rundgang 3: ehrliche Wirkung, klare Seiten, Nutzung

Stand: freigegeben 2026-10-18 („ja“); Phasen A–E gebaut, Browser-Abnahme und Review abgeschlossen (nur Staging, nicht committet). Offen beim Nutzer: §10.

## 1 Ziel

Den dritten Studio-Rundgang des Nutzers (nach Paket 15) umsetzen:
- sichtbare Fehler beheben (Knopfbreite, Datumsfeld, Analyse-Kästen, fehlendes „Abbrechen“, Gold-Flow-Feld);
- **ehrlich zeigen, was im Agent-Modus wirkt** — je Feld statt je Bereich, wirkungslose Felder gekennzeichnet;
- Seiten neu ordnen (Übersicht in beiden Modi, Rolle & Schutz mit Reitern, Tour in Laufzeit-Reihenfolge, Kontext-Aktionen nach DE/EN, Sicherung mit klarem Umschalter);
- Auswertung erweitern (Nutzung, Kosten je Tag, Engstelle im Lasttest) und den Nutzertext im Qualitätsprotokoll nach 30 Tagen leeren.

## 2 Ausgangslage (vier Prüfungen, 2026-10-18, nur lesend)

- **Rückschritt aus Paket 15 (R2-18):** inaktive Reiter blieben sichtbar (`.cv-sections { display: grid }` schlug `[hidden]`); die Specs sahen nur die Eigenschaft. **Behoben in PR #18** (`b8671a4`, globale Regel `[hidden] { display: none !important }`, im Browser geprüft).
- **Wirkung im Agent-Modus** (Belege im Prüfbericht): Rolle, Schutzregeln (nur gewählte Leitplanken), Grenzen, Sicherheitsstufe, Drosselung, Protokoll wirken voll. M01/M02 und `crisis_*` nur bei Krise (Krisentext nur `/api/agent`). Regelwerk: nur Regex-Regeln wirken; Persona-/Anliegen-Regeln praktisch nie (Agent: Persona immer P-AND, Anliegen immer I01) — die Presse-Regel (P-RED) greift nie. Zielgruppen: Prompt-Liste, Rückfall nur für `wie_user`-Personas. Anzeige: `per_pattern`, `intro_text`, `prompt_anzeige_konsistenz`, `materialien_max_lernpfad` wirkungslos, `widget-modes` in keiner Maschine. Tour & Lotse in beiden Modi. Domänenwissen nur Muster. Master-Skill nur Agent, Skill-Brücke nur Muster. Die Etiketten „Wirkt in“ (`domain/area_effects.py`) gelten **je Bereich** — falsch an Feld-Ausschnitten (`01-base/engine` auf Rolle & Grenzen, `muster_skills`), dazu `device-config` (Agent liest auch `device_max_items`) und `safety-config` (Agent im Chat teilweise).
- **Tour/Lotse:** Tour = feste Führung in 6 Schritten, Pfade fest in `website-tour.yaml`; Lotse = „Bring mich hin“-Knöpfe in normalen Antworten. `start_label` ohne Leser, `guide-rules.rag_area_rules` ohne Leser. „Vertraute Domains“ (`trusted_domains`) = Sitzung mitnehmen + Externe-URL-Warnung; wohin Knöpfe führen = `allowed_hosts` — der Hilfetext verwechselt beides.
- **Gold-Flows:** „22 Schlüssel“ = 22× `flows[i].zielgruppe`; das Modell `GoldFlow` kennt nur das alte `persona`.
- **Kontext-Aktionen, Grundwerte:** Technik, KI-Anweisung und vier Besuchertexte (DE/EN) gemischt in einem Abschnitt.
- **Oberfläche:** `.sf-zurueck` gestreckt (`align-items: stretch` in `.sf-row`); Pattern-Nutzung `align-items: end` + Hilfetext im Feld; Analyse `studio-async-state` ohne seitlichen Abstand; MCP neue Zeile ohne Abbrechen; Herkunft der Werkzeuge vermischt Herkunft und Schaltbarkeit.
- **Nutzung:** Daten liegen vor (`sessions`, `usage_events`, `quality_logs` mit Seite, Gerät, Sprache im Debug, Maschine); keine Seite. Agent-Züge tragen Platzhalter für Anliegen/Persona. **Datenschutz:** `quality_logs.data.message`/`debug` halten Nutzertext 180 Tage, Verläufe nur 30.
- **Kosten:** kein Tagesverlauf. **Lasttest:** die spekulative Vorab-Suche des Muster-Wegs (`prefetch.py`, `call_mcp_tool` direkt) und das Rerank sind ungemessen — MCP-Zeit erscheint dort als „Rest“.
- **Plattform-Wissen:** RAG-Bereich `Plattformwissen` existiert (Agent sucht darin, `agent` Vorgabe an), Inhalt ist aber Fassung 1.0; `02-domain/wlo-plattform-wissen.md` ist 2.0.

## 3 Entscheide des Nutzers (2026-10-18)

| Frage | Entscheid |
|---|---|
| Reiter-Fehler | sofort in PR #18 (erledigt) |
| Felder ohne Wirkung im Agent-Modus | **kennzeichnen**, nicht ausblenden |
| Plattform-Wissen für den Agenten | **als RAG-Bereich** (`agent: true`) — Suchstrategie aus `domain-rules` bleibt Sache des Master-Skills |
| Nutzertext im Qualitätsprotokoll | **nach 30 Tagen leeren**; Kennzahlen bleiben 180 Tage |

## 4 Ansätze (nicht-triviale Entscheidungen)

### 4.1 Wirkung je Feld
- **A (gewählt): Backend-Tabelle um Feld-Ausnahmen erweitern.** `AREA_EFFECTS` bleibt je Bereich; neu `FIELD_EFFECTS: dict[area, dict[pfad, Wirkung]]` für Felder, die vom Bereich abweichen. `GET /api/config/effects` liefert zusätzlich `fields`. Das Studio zeigt am Abschnitt mit `felder` die zusammengefasste Feld-Wirkung und im Agent-Arbeitsbereich an jedem Feld mit abweichender Wirkung eine Plakette. Eine Quelle der Wahrheit, testbar gegen die Leser.
- B: nur im Studio pflegen — zwei Stellen, die auseinanderlaufen.
- C: automatisch aus Code-Lesern ableiten — zu aufwendig, unzuverlässig.

### 4.2 Formulare gliedern (Tour, Kontext-Aktionen, Rolle & Schutz)
- **A (gewählt): Feldgruppen im Studio.** `CuratedAreaSection.gruppen: [{ labelKey, felder: [...] }]` — EIN Editor je Bereich (kein 409), aber mehrere benannte Formular-Abschnitte in fester Reihenfolge. Kein Datenmodell-Umbau, keine Migration.
- B: YAML-Modell umbauen (Blöcke `dublette`/`dublette_en`, Tour-Unterblöcke) — Lader, Seeds, Migration der eigenen Fassungen; mehr Risiko für dasselbe Bild.

### 4.3 Diff in der Sicherung
- **A (gewählt): Backend liefert Feld-Unterschiede.** Der Vergleichs-Endpunkt gibt zusätzlich `felder: [{pfad, werk, eigen}]` (flach, nur abweichende Blätter, gekürzte Werte). Das Studio zeigt eine Tabelle; der YAML-Diff bleibt als Rohansicht.
- B: im Studio aus zwei Dokumenten rechnen — zwei zusätzliche Abrufe, Diff-Logik doppelt.

### 4.4 Text im Qualitätsprotokoll
- **A (gewählt): eigener Schritt im Aufbewahrungslauf**: Zeilen älter als die Verlaufsfrist (`privacy.retention.messages_days`, Vorgabe 30) bekommen `data.message = null` und im `data.debug` die Text-Felder entfernt (`message`, `response`, Prompts) — Kennzahlen bleiben. Ein UPDATE mit JSONB-Operatoren, idempotent.
- B: beim Schreiben gar keinen Text — vom Nutzer verworfen.

## 5 Umfang

**Drin:** Phasen A–E unten. **Nicht drin:** freie Persona-Gespräche (eigenes Paket), Policy mit Anliegen im Agent-Modus (bleibt gekennzeichnet), Datenmodell-Umbau Tour/Kontext-Aktionen, Konfigurationsdaten ändern, die der Nutzer prüfen muss (§10).

## 6 Globale Regeln

Wie Paket 15: Staging-Baum, keine Commits/Deploys durch Claude (Upload als PR nur auf Auftrag); TDD je Aufgabe, vorher roter Test; **UI-Darstellung im echten Browser prüfen** (jsdom wendet keine Komponenten-Styles an — Lehre aus R2-18), Browser nur gegen Wegwerf-DB; i18n de+en für jeden Text; ein Bereich je Seite höchstens einmal; Vertragsänderungen in `docs/api/bewusste-vertragszusaetze.md`; Startpaket Studio unter 1,1 MB.

## 7 Aufgaben

### Phase A — Fehler
Schritt 0: `/better-coding-workflow` + `/better-coding-frontend`.
- **A1** `.sf-zurueck`: `align-self: flex-start` statt `justify-self` (`schema-form/_sf-meldungen.scss`). Nachweis: Browser, Knopfbreite = Inhalt.
- **A2** Pattern-Nutzung: Hilfetext unter die Filterzeile (`eval-pattern-usage.component.html/.scss`), `aria-describedby` bleibt. Nachweis: Browser, Eingaben auf einer Linie; Spec auf `aria-describedby`.
- **A3** Analyse-Kästen: `studio-async-state { display:block; padding-inline: var(--st-4) }` in `quality-diagnosis.component.scss`, Aufklapp-Zeichen wie MCP-Zeilen. Nachweis: Browser.
- **A4** MCP-Panel: „Verwerfen“ in den Aktionen (`reg.discard()`), in der neuen Zeile „Abbrechen“ (`remove(si)`), Texte `mcp.verwerfen`, `mcp.abbrechenNeu`. Spec: Hinzufügen → Abbrechen → Liste wie vorher, nicht `dirty`.
- **A5** Gold-Flows: `GoldFlow.zielgruppe: Annotated[str, Catalog("personas")] = ""`, `persona` als „alt“ gekennzeichnet; Feldtexte; Schema-Fixture neu. Test: Seed validiert, `zielgruppe` im Schema; Studio-Spec: keine „nicht angezeigt“-Meldung für den Seed.
- **A6** Hilfetexte Lotse: „Vertraute Domains“ = Sitzung mitnehmen + Warnung; „Erlaubte Hosts“ = wohin Knöpfe führen (`i18n/catalogue/fields-lotse.ts`). Pin-Spec auf beide Texte.
- **A7** Felder ohne Leser kennzeichnen: `start_label`, `guide-rules.rag_area_rules`, `widget-modes` → Wirkung „keine“ (über B1). Kein Löschen von Daten.

### Phase B — Ehrliche Wirkung (je Feld)
Schritt 0: `/better-coding-workflow`.
- **B1** Backend `domain/area_effects.py`: `FIELD_EFFECTS` mit den Belegen aus §2 (u. a. `01-base/engine`: `agent_rolle`, `agent` → Muster keine/Agent voll; `muster_skills` → Muster voll/Agent keine; `03-patterns/m01|m02` → Agent krise; `01-base/display-rules`: `inline_documents.per_pattern`, `intro_text`, `prompt_anzeige_konsistenz`, `groups.materialien_max_lernpfad` → Agent keine; `01-base/safety-config`: `crisis_message*` → Agent nur `/api/agent`, `crisis_pattern`/`threat_pattern`/`crisis_blocked_tools` → krise; `website-tour.start_label`, `guide-rules.rag_area_rules` → keine/keine). Korrekturen: `device-config` Agent „teilweise“ mit `device_max_items` voll, `safety-config` Agent „teilweise“. `api/config_effects.py` liefert `{areas, fields}`. Tests: Wächter „jeder Feldpfad existiert im Bereichsschema“, Antwortform.
- **B2** Studio `effect-badge`: an Abschnitten mit `felder` die Wirkung der gezeigten Felder (gleich → eine Angabe, sonst „teilweise“). Spec: Rolle-&-Schutz-Abschnitt zeigt „Agent-Schleife“.
- **B3** Studio Feld-Plakette: im Agent-Arbeitsbereich an Feldern mit Agent-Wirkung `keine`/`krise`/`nur /api/agent` eine Plakette („wirkt nur im Muster-Modus“, „nur bei Krise“, „nur externer Auftrag“); im Muster-Arbeitsbereich entsprechend für `agent`-only Felder. Spec je Plakettenart.
- **B4** Regelwerk: je Regel eine Plakette „wirkt im Agent-Modus nicht“, wenn `match.persona` ≠ `P-AND` oder `match.intent` ≠ `I01` gesetzt ist (Studio, reine Funktion + Spec); Hinweistext korrigiert („Persona und Anliegen erkennt der Agent nicht …“).
- **B5** Leitplanken-Seite (Agent): Hinweis „Im Agent-Modus gelten nur die unter Schutzregeln gewählten Leitplanken“ mit Sprung zu den Schutzregeln.
- **B6** Zielgruppen-Rückfall: Hinweis „wirkt nur für Zielgruppen mit ‚wie die Person schreibt‘“; Zeilen anderer Personas gekennzeichnet.

### Phase C — Seiten neu ordnen
Schritt 0: `/better-coding-workflow` + `/better-coding-frontend`.
- **C1** Feldgruppen (§4.2): `CuratedAreaSection.gruppen`, `form-sections`/`feld-ausschnitt` ordnen Felder in benannte Abschnitte; nicht genannte Felder in „Weitere Einstellungen“. Spec: Reihenfolge, nichts geht verloren, ein Speichern für alle Gruppen.
- **C2** Tour (`fuehrung`, Reiter Tour): Gruppen *Start* (enabled, trigger_phrases) · *Texte* (intro, entry, nudge, explore; DE/EN je nebeneinander) · *Website* (base_host, home_path, content_hub, contact_hub) · *Besuchergruppen* (groups) · *Linklisten* · *Schritte* · *Doku* (flows, zugeklappt); Hilfetexte zu Gruppen-Kennungen („nur in der Tour verwendet“). Spec: Abschnittsfolge.
- **C3** Kontext-Aktionen Grundwerte: Gruppen *Technik* (enabled, report_url) · *Dubletten-Gruß DE* · *Dubletten-Gruß EN* · *KI-Anweisung „Sammlung kuratieren“ (intern)*; neue Beschriftungen/Hilfen.
- **C4** Rolle & Schutz (Agent, Slug bleibt `agent-rolle`, Menüname „Rolle & Schutz“): Reiter **Sicherheit** (safety-config, offen, Stufe oben, Link „Safety-Logs ansehen“) · **Rolle & Grenzen** (engine mit Gruppen *Rolle*, *Schutzregeln*, *Grenzen*, *Ohne Anmeldung*) · **Leitplanken & Regeln** · **Schutzantworten**. Muster „Identität & Schutz“: Reiter Sicherheit · Grundpersona · Leitplanken & Regeln; Link zu Safety-Logs. Spec: Reiterfolge, Sicherheit zuerst und offen.
- **C5** Übersicht in beiden Modi (Menüname „Übersicht“): Statusleiste aus `overview.component` als eigene Komponente (LLM-Modell/Anbieter aus `/api/health`, Grundstand, letzter Snapshot, letzter Eval-Lauf je Maschine); Agent-Übersicht: Statusleiste, Master-Skill-Karte, Agent-Architektur (Rolle-Kopf → Master-Skill → Werkzeuge/Skills/Wissen → Schleife → Antwort), Karte **Testseiten** (`/widget/`, `/widget/inline`, `/widget/classic`, `/widget/frameless` in neuem Tab, Studio-Vorschau). Spec: Statusleiste in beiden, Links vorhanden.
- **C6** Sicherung: je Zeile „Aktiv: ◉ Werk ○ Eigen“ (Umschalten in beide Richtungen, Hinweis „die andere bleibt erhalten“), Feld-Unterschiede als Tabelle (Backend §4.3, `GET …/vergleich` + `felder`), Link „im Editor öffnen“; oben im Reiter „Sichern“ Vergleichstabelle *Werksfassung · Eigener Grundstand · Snapshots · Voll-Backup* (Wo · Wer legt an · Umfang · Rückweg). Tests Backend (Feld-Diff) + Specs.
- **C7** Werkzeuge: Plakette nach Herkunft (Eingebaut · WLO-MCP · Fremd-MCP) unabhängig vom Schalter, darunter Servername/Host. Spec.
- **C8** Skills im Muster-Arbeitsbereich: Skill-Brücke zuerst und offen, Hinweis „wirkt nur im Muster-Modus, wenn eingeschaltet“; Master-Skill-Panel dort mit Plakette „nur Agent-Modus“ (B3).
- **C9** Plattform-Wissen: RAG-Seed `seeds/rag/Plattformwissen.jsonl` aus `02-domain/wlo-plattform-wissen.md` (Fassung 2.0) neu erzeugen (Abschnitte als Chunks), `agent: true` ausdrücklich im Seed; Test: Seed-Datei enthält die Kernzahlen der 2.0. Deploy: `boerdi import-rag` (Einbettung neu — kleine Kosten).

### Phase D — Auswertung und Datenschutz
Schritt 0: `/better-coding-workflow` + `/better-coding-frontend`.
- **D1** Qualitätsprotokoll-Text nach 30 Tagen leeren (§4.4): neuer Schritt in `services/aufbewahrung.py`; Studio-Aufbewahrungs-Panel nennt ihn. Tests (pg): alte Zeile ohne Text, Kennzahlen da; junge Zeile unverändert; zweiter Lauf ändert nichts.
- **D2** Kosten je Tag: `period_usage` liefert `days` (Europe/Berlin, Lücken mit 0); Studio Säulendiagramm (`cost-day-chart.ts`, reine Geometrie) + Tabelle als Textalternative. Tests Backend + Spec.
- **D3** Nutzung: `GET /api/nutzung/ueberblick?from&to&scope&engine` (Sitzungen/Tag, aktive Sitzungen, Ø/Median Züge, Tageszeit × Wochentag, Maschine, Sprache, Gerät, Seitenart; Persona/Anliegen nur Muster mit Hinweis; kleine Zellen „<5“); `log_quality_event` schreibt `locale`, `page_type`, `engine` flach. Neue Seite „Nutzung“ unter Auswertung (vor Sessions), Hinweis wenn Qualitätsprotokoll aus. Vertragszusatz + Tests.
- **D4** Lasttest-Engstelle: `schritt("respond.vorabsuche")` um das Warten auf die Vorab-Suche, `schritt("respond.rerank")`; `_zeit_angaben` (llm, werkzeuge, rag, safety, rest); `by_kind[k].anteile` (Median); gestapelter Balken je Anfrageart (`engstelle-chart.ts`) + Spalten in der Anfragen-Tabelle. Tests.

### Phase E — Abnahme
Volle Suiten, Gates, Build; **Browser gegen Wegwerf-DB mit Darstellungsprüfung** (`getComputedStyle`, Breiten, 375 px, hell/dunkel) für alle geänderten Seiten in beiden Arbeitsbereichen; Testcontainer neu (nur nach Absprache, Nutzer testet); frischer Review (`/better-coding-review`, nach Bereichen aufgeteilt); Befunde beheben.

## 8 Abnahmekriterien

| Kriterium | Nachweis |
|---|---|
| Jeder Reiter blendet wirklich aus | Browser `getComputedStyle(...).display` |
| Etikett an Feld-Ausschnitten stimmt; Felder ohne Agent-Wirkung tragen Plakette | B-Tests + Browser |
| Presse-Regel im Agent-Arbeitsbereich als „wirkt nicht“ gekennzeichnet | B4-Spec |
| Tour/Kontext-Aktionen in Gruppen, DE/EN getrennt, ein Speichern | C1–C3 Specs + Browser |
| Übersicht in beiden Modi mit LLM-, Sicherungs-Status und Testseiten | C5 Spec + Browser |
| Werk ↔ Eigen in beide Richtungen umschaltbar, Unterschiede je Feld | C6 Tests + Browser |
| Nutzertext im Qualitätsprotokoll nach 30 Tagen weg | D1 pg-Test |
| Nutzung, Kosten je Tag, Engstelle sichtbar | D-Tests + Browser |

## 9 Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| Feld-Wirkungen veralten | Wächter: Pfade existieren; Kommentar mit Leser-Beleg je Eintrag |
| Feldgruppen verlieren ein Feld | Spec „jedes Feld genau einmal“ (wie Paket 15) |
| CSS-Fehler unsichtbar für Specs | Darstellung im Browser prüfen (Phase E) |
| `import-rag` ersetzt Plattformwissen-Chunks | nur Bereich `Plattformwissen`; Probe in Wegwerf-DB |
| Datenschutz-Lauf löscht zu viel | pg-Test für Kennzahlen; zuerst Trockenlauf-Zählung im Studio-Panel |

## 10 Offen / beim Nutzer (Konfiguration, kein Code)

- `own_hosts` nennt `wissenlebt.online`, die Lotsen-Listen `wissenlebtonline.de` — welche Schreibweise gilt?
- `website_tour.base_host` zeigt auf **wp-test** — für Prod umstellen?
- Vier Tour-Gruppen teilen `/home/oer-community/` → Einstieg dort immer „Lehrkraft“; Presse-Seite unter `contact_hub` → Start dort landet bei Presse-Lösungen.
- **Deploy C9:** den RAG-Bereich „Plattformwissen“ neu einlesen — nur ihn: `Plattformwissen.jsonl` allein in ein Verzeichnis legen und `boerdi import-rag --seed <verz> --force` (leert nur die Bereiche dieses Seeds; Einbettung von 13 Abschnitten). Die Filter-Logik der 2.0 („Klassenstufen still mappen“) ist Bot-Anweisung, kein Nutzerwissen — sie steht nicht im RAG; das Nutzerwissen dazu trägt die FAQ für Lehrkräfte.

## 11 Log

| Datum | Schritt |
|---|---|
| 2026-10-18 | Rundgang 3, vier Prüfungen (nur lesend), Entscheide; Reiter-Rückschritt in PR #18 behoben (`b8671a4`); Entwurf |
| 2026-10-18 | Freigabe („ja“). Phase A (A1–A6) und B (Feld-Wirkung `FIELD_EFFECTS`, Plaketten je Feld, Policy-Hinweise) gebaut; C1–C4 (Feldgruppen `gruppenSections`, Tour/Kontext-Aktionen gegliedert, „Rolle & Schutz“/„Identität & Schutz“ mit Reitern + Sprung zu Safety-Logs, Menü „Übersicht“) |
| 2026-10-18 | C5: Statusleiste als `studio-status-strip` (lädt in `ngOnInit` — im Konstruktor war `maschine` noch leer, die Agent-Übersicht hätte jeden Lauf gezeigt; `neuLaden` nur beim Knopf, sonst lud die Übersicht doppelt); Agent-Übersicht mit Statusleiste, Master-Skill, Weg einer Frage (6 Schichten mit Sprüngen), Testseiten (neuer Tab) + Vorschau |
| 2026-10-18 | C6: `services/feld_unterschiede.py` + `felder`/`felder_eigene` am Vergleich (Vertragszusatz); Karte mit Schalter „Aktiv: Werksfassung · Eigene Fassung“ (aria-pressed), Tausch bei zwei eigenen, „Jetzt aktualisieren“ bei veraltetem Werk, „Im Editor öffnen“ (`?von=sicherung`); Vergleich als eigene Komponente (Feld-Tabelle, Rohansicht); Gegenüberstellung der vier Sicherungsarten im Reiter „Sichern“ |
| 2026-10-18 | C7 Herkunfts-Plakette (`herkunftVon`: Eingebaut · WLO-MCP · Fremd-MCP, Server · Host); C8 Skills: `zuerstIn: 'pattern'` stellt die Skill-Brücke im Muster-Arbeitsbereich vorn und offen, Master-Skill trägt „Wirkt in: Agent-Schleife“; C9 Seed „Plattformwissen“ aus 2.0 + 1.0-Reste (13 Abschnitte, Umlaute, LF), `agent: true` + Beschreibung. Befund: die 1.0 hatte keine kaputten Zeichen (nur Konsolen-Anzeige) |
| 2026-10-18 | D1: `services/qualitaet_text.py` (rein) + Schritt `quality_text` im Aufbewahrungslauf (Frist der Gesprächsverläufe, nach dem Löschen, Marke `text_geleert`, ORM-Sammel-Update); Studio-Panel nennt die Zeile. Text-Felder laut Prüfung: `message`, Entities dreifach, `pattern_reasoning`, `selected_card_reasoning`, `outcomes[*].error`, Freitext in `safety.reasons` |
| 2026-10-18 | D2: `services/usage_tage.py` (Tag in Postgres `timezone('Europe/Berlin', …)` — das Abbild hat kein `tzdata` für Python), `days` an `period_usage`; Studio `cost-day-chart.ts` + `studio-cost-days` (Säulen + Tabelle), `formatCalendarDay` |
| 2026-10-18 | D3: `log_quality_event` schreibt `locale`/`page_type`/`engine` flach; `qualitaetsprotokoll_an()`; `services/nutzung.py` + `GET /api/nutzung/ueberblick` (Zeitraum-Prüfung `api/usage.zeitraum` geteilt, Inventar + OpenAPI neu, Vertragszusatz); Studio-Seite „Nutzung“ (vor Sessions; Raster 7×24, Tage, sechs Verteilungen, „<5“, Hinweis bei abgeschaltetem Protokoll) |
| 2026-10-18 | D4: `schritt("respond.vorabsuche")` (nur Warten) + `schritt("respond.rerank")` im Muster-Antwortknoten; `_zeit_angaben` (llm, werkzeuge, vorabsuche, rerank, rag, safety, rest), `by_kind[k].zeiten_ms/anteile` (Median); Wächter: jeder gelesene Schritt wird geschrieben; Studio `studio-lt-engstelle` (höchste Stufe) + vier Spalten in der Anfragen-Tabelle |
| 2026-10-18 | E Browser-Abnahme (Wegwerf-DB, Beispieldaten): alle geänderten Seiten in beiden Arbeitsbereichen; Befunde behoben: 375 px — Grid-Spalten ohne `minmax(0, 1fr)` machten Nutzung (717 px) und Sicherung (601 px, dazu der alte §5-Befund der Upload-Zeilen) zu breit; `<ol>` ohne Nummern (flex); Tönung des Rasters als `::before` (Gates; Kontrast 4,92:1 dunkel / 8,58:1 hell); Kosten-Hinweis ohne Preis. Seed-Preistafel ohne `gpt-6-luna` → offene-befunde §2 |
| 2026-10-18 | E Review (drei frische Prüfer, nach Bereichen): Backend B-1 (MAJOR, `tool_outcomes[*].error` blieb) … B-7, Studio A–C A-1 (Policy-Lesart wie `assess_policy`: kein `pattern`, vorhandener Schlüssel = Bedingung) … A-8, Studio D D-1 (MAJOR: Nutzung filterte auf die Maschine des Arbeitsbereichs → jetzt beide) … D-9 behoben; B-3a „<5“ nach Sitzungen statt Zügen. Abweichungen: B5 nennt den Weg (Reiter „Rolle & Grenzen“ › Schutzregeln) statt eines Sprungs — Sprünge führen zu Seiten, nicht zu Reitern; D-5 (Zeitraum-Grenzen in Browser-Zeit statt Berliner Zeit, betrifft auch Kosten) → offene-befunde §5; B-3b/c (genaue Summen und Tageswerte) bewusst, die Seite sagt es |
| 2026-10-18 | Review-Runde 2 über PR #18 (Pakete 13–16, fünf frische Prüfer nach Bereichen), alle Befunde behoben. MAJOR: Trends verglichen generative Läufe ohne Messbedingungen (E1); leere Entities zählten geleerte Zeilen (B1); der Text-Schritt las geleerte Zeilen bei jedem Lauf neu → Keyset + Teilindex, **Migration `0013`** (B2); die Start-Umleitung lief vor `authGuard` → Guard am leeren Kind (F1); Laufwechsel behielt Zustand von Lauf A (S1); Kosten unter 0,005 als „0“ (S2). Dazu die MINOR/NIT-Punkte E2–E6, B3–B8, F2–F8, S3–S12, C1–C10 (u. a. Prompt-Diff als Mengendifferenz, fokussierbare Scroll-Rahmen, Grund am gesperrten Knopf „Werksfassung“ bei `nur-eigen`, Aliase/Vorrang nach dem Speichern ihrer Abschnitte neu, `dirty` je Panelart auf Seitenebene geprüft). Abweichung zu **B4**: statt einer Plakette je Regel nennt ein Hinweis am Abschnitt die betroffenen Regel-Kennungen (`policyHinweise`, über den vorhandenen `hinweise`-Weg der Seiten; die Regeln stehen im generischen Listenfeld). B3/B5 nur dokumentiert (Vertragszusatz Nutzung). Ältere Befunde außerhalb der Pakete → offene-befunde §5 |
| 2026-10-18 | Studio-Rundgang nach dem Merge: Formular-Abstände (die Regel `.sf-section > studio-schema-field > .sf-group` griff wegen der Kapselung nie → Eingabe `oben`), Datenbasis als Raster gleich breiter Karten, Nutzung-Kopfzeile und Scrollrahmen an der Tabelle, Kosten je Tag mit Umschalter „Betrag \| Aufrufe“ statt Ersatzmarken. **Nutzer-Entscheide:** Seed-Preistafel trägt die OpenAI-Listenpreise (Standard, kurzer Kontext) in USD — hebt „Seed ohne Preise“ (§5.4 des Kosten-Plans) auf; Master-Skill im 5-Minuten-Takt im Hintergrund mit Rückfall auf den letzten guten Stand (abgeschaltet erst nach dem ersten Gebrauch). Review (better-coding-review) 3 MINOR + 2 NIT behoben |
