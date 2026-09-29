# Zweite Agent-Runde: den Agenten besser machen (nach dem Tor E-5)

Stand: 2026-09-28, **Entwurf zur Freigabe** — es wird erst gebaut, wenn der Nutzer zustimmt.
Ausnahme auf Wunsch des Nutzers: **D2 (Master-Skill-Vorlage) ist umgesetzt** — siehe Abgleich.
**Freigabe 2026-09-29** („korrigiere den Code … wie empfohlen“): D1, B0, C, A; dazu Paket F (Studio).
**Stand 2026-09-29: A, B0, C, D1, F gebaut** (Einzelheiten unter „Aufgaben“). **Master-Skill
übertragen** (Nutzer, md-editor; live geprüft über `get_skill` wie im Chat: 33.648 Zeichen,
Wortgleichheit mit der Vorlage 99,4 %, alle 8 Regeln der Wächter erfüllt; der Editor hat
umformatiert — Absätze einzeilig, `(M09)` → `**M09**` — und die Einleitung lautet live
„WLO (Wissenlebtonline) Staging“: laut Nutzer richtig, Wissenlebtonline ist das neue Synonym
für WirLernenOnline). Nachprüfen nach jedem Übertragen: `backend/scripts/check_master_skill.py`
(die Wächter tragen seither beide Schreibweisen der Kennungen; live 8 von 8 erfüllt, nach R-3 prüft das Skript alle 11 Regeln: live 11 von 11).
Offen: E2 — die Nachmessung startet der Nutzer. Der A1-Fall GV-AND-1#3 ist mit R-5 behoben. Alle offenen Punkte gesammelt: `docs/offene-befunde-und-todo.md`.
Rahmen: `2026-09-26-betriebsmodi-und-studio.md` (§8 AG, §11 D-13/D-15, §13 E-5).

## Ziel

Die Agent-Schleife erreicht in der Tor-Messung die harte Quote der Muster-Maschine
(E-5: 0,97–1,00), ohne dass sich an der Muster-Maschine etwas ändert.

## Entscheid des Nutzers (2026-09-28)

Zielbild **Z2**: beide Maschinen bleiben parallel, die Muster-Maschine wird nicht entfernt.
Im Betrieb ist die Agent-Schleife die Vorgabe. Den Agenten besser zu machen ist gewollt;
das Vorgehen wird vorher vorgelegt (dieses Dokument).

## Befund: was in der Tor-Messung scheiterte

Drei Agent-Läufe (eval-e38db35ab81a, -46498e9c415f, -cf4bafb5c142): 261 von 284 harten
Prüfungen bestanden (0,92). Die 23 Fehler, Zug für Zug aus den Laufdaten gelesen:

| Art | Anzahl | Beispiel (Flow#Zug) | Ursache |
|---|---|---|---|
| Anrede | 6 | GV-LEH-1#3 „Können Sie mir …“ → Antwort duzt | Der Kopf listet die Anrede je Zielgruppe (Personas); dem Master-Skill fehlte der Anrede-Hinweis der alten Muster, und er zitierte selbst Sätze an die Person in Du-Form |
| Vorheriger Zug unsichtbar | 4 | GV-LER-2#2 „zeig mir jetzt die Lösungen“ → „Ich sehe die Quizfragen nicht“ | (a) Dokument-Boxen aus `zeige_dokument` werden **nicht gespeichert** (`turn_persist` hängt sie nach `save_message` an) — der nächste Zug kann sie nicht kennen; (b) die gezeigten Treffer liegen als `_last_contents`/`_last_collections` in der Sitzung, der Muster-Weg schreibt sie in seinen Prompt (`response_prompt_tools_text.py:143-160`), die Agent-Kette nicht |
| Kein Lernpfad | 3 | GV-LEH-1#2 „fertigen Lernpfad …?“ → „keinen gefunden“ | Der Kopf verlangt das Bauen schon; die Faustregeln des Master-Skills („hast du → suchen“, „Vorhanden ≠ Neu“) lenken ins Suchen (siehe Abgleich); der Muster-Weg baut ihn (`lp_fast_path` → `generate_learning_path_text`) |
| Eigenes Blatt statt Material | 2 | GV-LER-1#3 „hast du Übungen für mich?“ → selbst erstelltes Blatt | Die Antwortform der Rolle („Arbeitsblatt, Quiz … baue es aus den Treffern“) lädt dazu ein und geht dem Master-Skill vor; der Gold-Flow erwartet erst vorhandene WLO-Materialien |
| Gesucht, aber keine Karten | 2 | GV-AND-1#3, GV-LER-1#3 (1 Lauf) | **unklar** — in GV-LER-1#3 stehen 4 Karten in der gespeicherten Nachricht, die Antwort hatte 0; in GV-AND-1#3 erntete die Suche nichts |
| Keine Quick-Replies | 4 | GV-WIS-1#1/#2, GV-RED-3#1, GV-AND-2#2 | **unklar** — drei davon nach `wissen_suchen` |
| Nachgefragt statt gesucht | 1 (+1 Werkzeug-Soll) | GV-AND-2#1 (1 von 3 Läufen) | M03 im Master-Skill („Pflichtangabe fehlt → genau eine Frage“) widerspricht dem Kopf („erst suchen“) |

## Vorgehen je Ursache

**1. Anrede — im Master-Skill, wie in den alten Mustern (umgesetzt, D2).**
Die Zuordnung Zielgruppe → du/Sie steht in den Personas des Studios, der Kopf listet sie
seit AG-3. Es fehlte die zweite Hälfte der alten Muster: der Hinweis im Anleitungstext,
dass die Vorgabe überall gilt und zitierte Sätze sie nicht setzen (M03, M09, M13, M14, M15
tragen ihn). Der Master-Skill trägt ihn jetzt im Abschnitt „Anrede und Zielgruppen“ gleich
nach der ranghöchsten Regel; seine Sätze an die Person sind unpersönlich.
*Nur falls die Nachmessung weiter Anrede-Fehler zeigt:* der Anrede-Satz am Ende der Kette,
aus dem Gespräch erkannt (Paket B).

**2. Vorheriger Zug — dem Agenten zeigen, was die Person gesehen hat (empfohlen).**
(a) `turn_persist` speichert die gelieferten Dokument-Boxen mit (Titel, Art, Inhalt,
gedeckelt) — dieselbe Nachzieh-Stelle wie Karten und Themenseite (F-6).
(b) Der Block am Ende der Kette nennt „zuletzt gezeigt“: die Treffer nummeriert (Titel,
Art, nodeId) aus `_last_contents`/`_last_collections` — dieselbe Quelle wie im Muster-Weg —
und die Dokumente des vorigen Zugs mit Inhalt (gedeckelt). Nur der letzte Zug, nur wenn
es etwas gibt.
*Verworfen:* ein Werkzeug „vorheriges Ergebnis holen“ — spart Token, verlässt sich aber
darauf, dass das Modell es ruft; in E-5 gab es stattdessen auf („Ich sehe die Quizfragen
hier nicht“).

**3. Lernpfad — ein Widerspruch im Master-Skill, keine fehlende Regel** (korrigiert nach
dem Abgleich unten). Der Kopf verlangt es schon: „auch wenn es im Bestand nichts Fertiges
gibt: dann baue es aus den Treffern“. Der Master-Skill steuert „Gibt es dazu auch einen
fertigen Lernpfad?“ aber über seine Faustregeln („hast du → suchen“, „Vorhanden ≠ Neu“) ins
Suchen, und M09 legt den Plan „als Markdown direkt im Chat“ ab. Umgesetzt im Master-Skill
(D2): Faustregel „Zusammenstellen ist kein Erzeugen“, M09 liefert über `zeige_dokument`. Rückfall, falls das nicht reicht: das virtuelle Werkzeug `lernpfad_bauen` über
`generate_learning_path_text` — gleiche Didaktik wie im Muster-Weg.

**4. Material zuerst — die Antwortform im Kopf enger fassen** (korrigiert nach dem Abgleich).
Das eigene Übungsblatt kam aus dem Kopf, nicht aus dem Master-Skill: seine Antwortform zählt
„Arbeitsblatt, Quiz“ zu den Ergebnissen zum Einsetzen und sagt „dann baue es aus den
Treffern“. „Hast du Übungen für mich?“ ist aber eine Suche — so sagt es auch der
Master-Skill („zeig / finde / hast du → suchen“). Der Satz gilt künftig nur bei einem
Erstell-Verb oder ausdrücklich verlangtem fertigen Ergebnis; sonst zuerst WLO-Materialien,
ein eigenes Blatt nur anbieten. Der Master-Skill sagt das jetzt ausdrücklich („Vorhandenes
geht vor Neuem“, D2) — die Rolle geht ihm aber vor, deshalb bleibt D1 nötig.

**5. Karten und Quick-Replies — erst die Ursache, dann der Fix.**
Beides ist im Code noch nicht erklärt. Vorgehen nach `/better-coding-debug`: die Flows
lokal nachstellen (Studio-Probelauf, Agent), gespeicherte gegen ausgelieferte Karten
vergleichen, die Quick-Reply-Entscheidung protokollieren, Ursache belegen, dann erst ein
Test und der Fix. Die Kartenanzeige bearbeitet gerade eine parallele Sitzung („Anzeige:
tote Link- und Karten-Einstellungen“) — deren Stand zuerst ansehen.

**6. Nachgefragt statt gesucht — Master-Skill angleichen** (korrigiert nach dem Abgleich).
M03 sagt „Pflichtangabe fehlt → genau eine Frage“, der Kopf „suche zuerst mit dem, was du
weißt; eine Rückfrage höchstens danach“. Bei „Material für eine Vertretungsstunde Deutsch,
6. Klasse“ gewann einmal M03. Umgesetzt im Master-Skill (D2): „reicht das Bekannte …,
suchst du zuerst“.

## Abgleich Master-Skill ↔ Chatbot (2026-09-28, zweite Fassung)

Die erste Fassung ordnete 18 der 23 Fehler dem Code zu und wollte die Mechanik aus dem
Master-Skill streichen. Der Nutzer widersprach — was flexibel konfigurierbar sein muss,
gehört in den Master-Skill; die Anrede ist zielgruppenabhängig, siehe die alten Muster —,
und die Nachprüfung gibt ihm recht:

- Der Master-Skill ist **als Steuerfläche angelegt**. Auftrag 2026-08-18, Punkt 4
  (`2026-08-18-master-skill.md`): „die chatbot-eigenen Anteile … Ergebnisfenster,
  Schnellantwort-Pillen, Struktur“ gehören hinein. Die Ansage-Regel wurde am 2026-08-21
  bewusst redaktionell statt im Code gelöst (Wächter `test_vorgehen_md_traegt_die_ansage_regel`).
- Die **alten Muster** regeln die Anrede zweistufig: die Zuordnung steht in den Personas
  (`formality`, `override`), und jedes Muster mit Beispielsätzen trägt den Hinweis „die
  Beispiele verwenden du — übernimm die Formality der Persona“. Die erste Hälfte hat der
  Agent seit AG-3, die zweite fehlte dem Master-Skill ganz.

**Grundsatz, zweite Fassung — drei Orte:**

| Ort | Was dorthin gehört | Warum |
|---|---|---|
| Master-Skill (Redaktion; Knoten `535cabca…`, Vorlage `docs/skills/vorgehen.md`) | Vorgehen je Anliegen, Anrede-Regel und Arbeitsweise je Zielgruppe, Suchstrategie, Didaktik, Bedienung der Chat-Flächen (Dokument, Kacheln, Schnellantworten, Ergebnisfenster) | flexibel ohne Deployment; beschreibt er Mechanik, muss sie für den Agent-Zug stimmen |
| Studio (Betreiber, je Anlage) | Zuordnung Zielgruppe → Anrede (Personas), Leitplanken, Rolle, Krisentext, Wissensbereiche, Schnellantwort-Länge | Werte, die beide Maschinen teilen; der Master-Skill verweist darauf, statt sie zu kopieren — die Kopien in M09/M15 sind veraltet („P-AND duzen“, „P-LEH `wie_user`“) |
| Code | was der Agent sieht (voriger Zug, gezeigte Treffer), ob Karten und Schnellantworten erscheinen, was erzwungen wird (Schutz-Umleitung, Schreib-Bestätigung, Ansage-Zeile) | kein Text wirkt auf etwas, das nicht im Prompt steht oder nicht ausgeliefert wird |

**Neue Zuordnung der 23 Fehler: 13 löst der Text, 10 der Code.**

| Art | Anzahl | Ort | Maßnahme |
|---|---|---|---|
| Anrede | 6 | Master-Skill | „Anrede und Zielgruppen“ gleich nach der ranghöchsten Regel; Code nur, falls die Nachmessung weiter Fehler zeigt (Paket B) |
| Kein Lernpfad | 3 | Master-Skill | Faustregel „Zusammenstellen ist kein Erzeugen“ |
| Eigenes Blatt statt Material | 2 | Master-Skill + Rolle (D1) | Faustregel „Vorhandenes geht vor Neuem“; die Rolle geht dem Master-Skill vor und muss mitziehen |
| Nachgefragt statt gesucht | 1 (+1) | Master-Skill | Nachfragen: „reicht das Bekannte …, suchst du zuerst“ |
| Voriger Zug unsichtbar | 4 | Code | Paket C |
| Keine Karten | 2 | Code | Paket A1 |
| Keine Schnellantworten | 4 | Code | Paket A2 |

**Was in der Vorlage geändert ist** (`docs/skills/vorgehen.md`; die Vorfassung war bis auf
Titel, „Staging“ und Escape-Zeichen gleich dem Live-Knoten, sha256 `8bbf014fa385…`):

- **Neu:** „Anrede und Zielgruppen“ — die Anrede-Regel wie in den alten Mustern (die Vorgabe
  des Chats gilt überall, zitierte Sätze setzen sie nicht; Material für Lernende duzt die
  Kinder, der Begleitsatz spricht die Person im Chat an) und je Zielgruppe Signale und
  Arbeitsweise, aus den Personas übernommen.
- **Faustregeln:** „Vorhandenes geht vor Neuem“ und „Zusammenstellen ist kein Erzeugen“
  ersetzen „Suchen ≠ Erzeugen“ und „Vorhanden ≠ Neu“; „mach / bau“ zählen zum Erzeugen
  (GV-LER-2#1); passt im Bestand nichts, wird erstellt und das gesagt — wie im Kopf. Einen
  Lernpfad gibt es immer als Dokument, Fertiges wird darin genannt.
- **Reihenfolge der Prüfung:** Verengen einer Trefferliste ist eine neue Suche, Lob und
  Kritik ohne neuen Auftrag sind Rückmeldung (GV-AND-1#3, GV-AND-2#2).
- **Nachfragen:** zuerst suchen, wenn Fach, Stufe oder Anlass genügen.
- **Dokument:** überall `zeige_dokument` statt „ab der ersten Überschrift“. Der Rückfall über
  die Überschrift greift nur für M09–M11, ein Agent-Zug heißt `AGENT`
  (`route_tail.py:63`, `turn_persist.py:539`).
- **Neu:** „Bezug auf Gezeigtes“ (fehlt die Kennung, die letzte Suche wiederholen); die
  Wissensfrage deckt Verständnisprobleme; Einreichen und Melden stützt sich auf das interne
  Wissen; `wissen_suchen` nur, wenn vorhanden — Tatsachen über WLO nie aus dem Gedächtnis,
  Allgemeinwissen gekennzeichnet; Lösungen für selbst übende Lernende erst auf Wunsch, dann
  per `zeige_dokument` (GV-LER-2); Verlangtes, das schon enthalten ist, trotzdem als Dokument
  (GV-LEH-1#4); ein paar Zeilen sind kein Dokument; ein Angebot für den nächsten Schritt ist
  erlaubt, Aufschieben nicht.
- **Abgeglichen mit den Personas:** „Statistik“ ist kein Entscheider-Signal (Anti-Marker in
  `ent.md`); nach der Rolle beiläufig fragen, wenn es zählt (`and.md`); „Wer dich siezt …“
  gilt nur, solange die Zielgruppe keine feste Anrede hat; keine eigene Rückfall-Zuordnung.
- **Berichtigt:** Kachelzahlen gestrichen (macht die Oberfläche), Sätze an die Person
  unpersönlich, „Lernpfad-Schnellweg“ (gibt es nur im Muster-Weg) ersetzt, „WLO Staging“
  neutral.
- **Unverändert:** Ansage-Regel, Kernbegriff-Suchregel, Kontext-Nutzungsfälle, Beurteilen,
  Ändern, Erschließen, Schützen, Ergebnisfenster, Schnellantworten samt Lage-Tabelle (eine
  Zeile neu), Grenzen der Anwendung, Belege.
- Länge: 33 117 statt 27 185 Zeichen — der Block steht im gecachten Präfix.
- **Unabhängiges Review** (frischer Kontext, 2026-09-28): 1 MAJOR, 7 MINOR, 4 NIT, alle gegen
  die Quelle geprüft und eingearbeitet; die Wächter pinnen seither die tragenden Sätze statt
  der Überschriften, prüfen jedes Zitat mit Anrede gegen eine Erlaubnisliste, verlangen
  `zeige_dokument` in M09/M10/M11/M17 und erkennen im Werkzeug-Wächter auch die Aufrufform
  (`get_skill_registry(nodeId)`). Der MAJOR bleibt teilweise offen: die Rolle im Kopf geht
  dem Master-Skill vor — D1.

**Übertragen** in den Knoten macht der Nutzer bzw. die Redaktion (den Rumpf unter dem
Vorspann, den der MCP-Server erzeugt). Bis dahin misst jede Nachmessung die alte Fassung.

## Architektur

| Datei | Neu/geändert | Zuständigkeit |
|---|---|---|
| `docs/skills/vorgehen.md` | **geändert ✅** | Master-Skill-Vorlage, zweite Fassung (D2) |
| `backend/tests/test_master_skill_vorlage.py` | **neu ✅** | sechs Wächter für die Regeln aus dem Tor; `test_mcp_tool_defs.py` kennt `zeige_dokument` als virtuelles Werkzeug |
| `backend/src/boerdi/services/agent_zugblock.py` | **neu ✅** | `dokumente_fuer_die_nachricht(dokumente)`, `zuletzt_gezeigt(verlauf) -> str` — der Block „Zuletzt gezeigt“ aus dem Verlauf, gerahmt (Paket C, Umbau nach Review R-4) |
| `backend/src/boerdi/graph/nodes/respond_agent.py` | **geändert ✅** | setzt den Block gerahmt an den Anfang der Nachricht der Person (C, R-4); Karten der jüngsten Suche vorn (A1) |
| `backend/src/boerdi/services/turn_persist.py` | **geändert ✅** | legt die gezeigten Boxen gedeckelt an die gespeicherte Antwort (`debug._dokumente`, R-4); Lotse zählt nicht gegen `max_count` (R-6) |
| `backend/src/boerdi/services/card_collect.py` | **geändert ✅** | `juengste_zuerst` (A1) |
| `backend/src/boerdi/services/widget_postprocess.py` | **geändert ✅** | kein Medientyp-Nachfilter im Agent-Zug (A1) |
| `backend/src/boerdi/services/quick_replies_llm.py`, `quick_replies_prompt.py` | **geändert ✅** | Lotse zusätzlich, eine Ersatzzeile (A2) |
| `backend/src/boerdi/services/agent_kopf.py` | **geändert ✅** | feste Anreden als fest ausgewiesen (B0) |
| `backend/src/boerdi/domain/config_models/engine.py` | **geändert ✅** | `ROLLE_VORGABE`: Antwortform enger (D1); die Kachel-Regel bleibt im Master-Skill |
| `backend/src/boerdi/services/agent_prompt_preview.py` | **geändert ✅** | `JE_ZUG` nennt den neuen Block; der Reihenfolge-Test zieht mit |
| `domain/repo_links.py` (neu), `api/master_skill.py`, `api/agent_center.py`, `services/agent_skill_directory.py` | **✅** | Editor-Link, Ansicht-Link, Skill-Suche (F) |
| Studio `views/agent-prompt`, `master-skill`, `agent-skills` + Kataloge | **geändert ✅** | neues Glied in der Vorschau (C); Editor-Link, Umschalter Suchbegriff/Sammlungs-ID (F) |

Die Muster-Maschine berühren drei Stellen: der gemeinsame Schnellantwort-Generator (A2 —
dort dieselbe Verbesserung), das Zählen der Lotsen beim Kürzen (R-6) und die Ablage der gezeigten
Boxen an der gespeicherten Antwort (rein ergänzend, gelesen nur vom Agenten).
Keine Migration; Vertragszusätze nur aus Paket F
(`edit_url`, `view_url`, `GET /api/agent-center/skills/search`, eingetragen in
`docs/api/bewusste-vertragszusaetze.md`).

## Aufgaben (je Paket Schritt 0 `/better-coding-workflow`, Test zuerst)

**Paket A — Befund klären** (`/better-coding-debug`) — ✅ 2026-09-29
- A1 Karten (GV-LER-1#3, `eval-67c31a623f0e`): zwei Ursachen, jede leert die Liste allein.
  (1) Der Agent sucht breit (`search_wlo_all`: 1 Sammlung, 3 Videos), dann verengt
  (`search_wlo_content` mit `learningResourceType`); sein Text beschreibt die Arbeitsblätter
  der zweiten Suche. `turn_persist` zeigt je Box die ersten drei in Fundreihenfolge — die
  Videos. Fix: `card_collect.juengste_zuerst`, nur in der Agent-Schleife: die jüngste Suche
  steht vorn. (2) `widget_postprocess` legt die Nachricht ein zweites Mal aus („Übungen“ →
  `übung`) und nimmt die Videos — und ebenso die Arbeitsblätter (`Arbeitsblatt` passt nicht
  zu `übung`). Fix: im Agent-Zug kein Nachfilter. Das nimmt die Gegenprobe vom 2026-09-27
  (`test_medientyp_agent_uebertrag`, „der Filter selbst bleibt“) ausdrücklich zurück; die
  Muster-Maschine filtert weiter. Nachgespielt (MCP lesend): alter Stand 0 Karten, nur (2)
  die 3 Videos, beide Fixes die 3 Arbeitsblätter. GV-AND-1#3 (`eval-e38db35ab81a`): gesucht,
  0 Karten gespeichert, dieselbe Suche liefert heute Karten — ohne Protokolle offen.
- A2 Schnellantworten: die Lotsen-Zeile belegte einen der `count` Plätze (ohne `host` wird
  sie danach entfernt), und Vorschläge über 48 Zeichen fallen ersatzlos weg — bei
  `max_count: 2` blieben 0 oder 1. Fix: Lotse zusätzlich (Prompt Regel 1/11), eine
  Ersatzzeile (`count + 1` angefragt, höchstens `count` zurück). Nachgespielt an drei
  Tor-Zügen: 12 von 12 Versuchen mit 2 Pillen. Derselbe Generator bedient die
  Muster-Maschine — dort dieselbe Verbesserung.

**Paket B — Anrede im Code**
- B0 ✅ 2026-09-29 (klein, unabhängig von der Messung): der Kopf weist feste Anreden als fest aus —
  „Lerner:in / Schüler:in: du, auch wenn die Person dich siezt“ — und spiegelt die Person
  nur noch, wo die Zielgruppe offen ist. Berichtigt 2026-09-29: nicht `override` macht die
  Anrede fest (das steuert im Muster-Weg Ton und Kartenmodus, `pattern_engine.py:200-224`),
  sondern `siezen`/`duzen` selbst — der Muster-Weg setzt sie immer durch
  (`response_prompt_pattern._formality_guidance`); Test über `kopf()`.

B1–B3 vorerst nicht gebaut: die Regel steht im Master-Skill (D2). Zeigt die Nachmessung
weiter Anrede-Fehler:
- B1 `anrede_der_person` mit Sätzen aus den Flows: „Können Sie mir daraus …“ → sie; „Zeigen
  Sie mir bitte …“ → sie; „hast du übungen für mich“ → du; „Ich bereite eine Mathestunde … vor“
  → None; „Eine Lehrerin fragt uns, wie sie ihr …“ → None (dritte Person); jüngste Nachricht
  gewinnt.
- B2 Anrede-Satz im Zugblock (drei Fälle, zwei Sprachen); B3 Test über die Kette.

**Paket C — Vorheriger Zug** — ✅ 2026-09-29, nach Review R-4 umgebaut: die gezeigten Boxen liegen
gedeckelt an der gespeicherten Antwort (`debug._dokumente`, je 6 000 Zeichen, Kürzung vermerkt),
der Block kommt aus dem Verlauf (höchstens drei Antworten zurück) und steht gerahmt am Anfang
der Nachricht der Person)
- C1 `turn_persist` speichert gelieferte Dokumente (höchstens 3, je 8 000 Zeichen); Test über die gespeicherte Zeile.
- C2 `zuletzt_gezeigt`: nummerierte Treffer, Dokumente des letzten Zugs (6 000 Zeichen), leer ohne Inhalt.
- C3 Einbau in den Block; Test: „zeig den ersten Treffer“ sieht Treffer 1, „die Lösungen“ sieht das Quiz.
- C4 Prompt-Vorschau und Reihenfolge-Test um den Block ergänzen (Studio-Beschriftung zweisprachig).

**Paket D — Antwortform**
- D1 ✅ 2026-09-29, gebaut mit einer Abweichung vom Vorschlag, passend zur Faustregel des
  Master-Skills: „Ein eigenes Material erstellst du nur, wenn es verlangt ist oder im Bestand
  nichts passt — dann sag, dass es selbst erstellt ist.“
- D1 `ROLLE_VORGABE` schärfen; Test über `kopf()`. Vorschlag für den Absatz „Antwortform“
  (im Studio unter Agent & Maschine → Rolle auch ohne Code sofort setzbar):
  > Antwortform: Fragt jemand nach Material, suche zuerst mit dem, was du weißt (Thema, Fach,
  > Klassenstufe, Anlass) — die Treffer erscheinen als Karten; eine Rückfrage höchstens danach.
  > Ein eigenes Material erstellst du nur, wenn es ausdrücklich verlangt ist. Wird ein fertiges
  > Ergebnis verlangt (ein erstelltes Material, eine Stunden- oder Lernpfad-Planung, der
  > Volltext eines Materials), liefere es mit zeige_dokument als Box; fehlt im Bestand ein
  > fertiger Lernpfad oder Stundenablauf, stelle ihn aus den Treffern zusammen.
- D2 ✅ 2026-09-28 Master-Skill-Vorlage `docs/skills/vorgehen.md` neu gefasst (siehe Abgleich),
  Wächter `backend/tests/test_master_skill_vorlage.py`; Übertragen in den Knoten macht der
  Nutzer bzw. die Redaktion.

**Paket F — Studio: Master-Skill im Editor bearbeiten, Skills suchen** (Nutzer 2026-09-29) — ✅ 2026-09-29
- F1 `MasterSkillStatus.edit_url` führt in den md-editor des Repositoriums
  (`{repo}/edu-sharing/services/md-editor/?nodeId=…&field=file`; ohne `name` — der Editor nimmt
  die angemeldete Person, das Studio behauptet keine Identität); neu `view_url` = die bisherige
  Render-Seite. Studio: „Im Editor bearbeiten“ und „Im Repositorium ansehen“.
- F2 Skill-Verzeichnis: je Eintrag `edit_url` auf das ORIGINAL (`originalId`, sonst `nodeId`) —
  ein Verweis aus einer Fachsammlung ist nicht beschreibbar (`nodeIdLine` im MCP-Server).
- F3 Skill-Suche per Suchbegriff: `GET /api/agent-center/skills/search?q=` → MCP `search_skill`
  (JSON). Bietet der Server es nicht an (`WLO_DISABLE_SKILL_SEARCH` oder `WLO_SKILL_TOOL_MODE=
  one-tool`), meldet der Router das mit eigenem Code, und das Studio verweist auf die Suche per
  Sammlungs-ID. Studio: Umschalter „Suchbegriff | Sammlungs-ID“ im Skill-Verzeichnis.

**Paket E — Nachweis**
- E1 Kleine Chat-Smokes im Studio-Probelauf: GV-LEH-1, GV-LEH-2, GV-LER-1, GV-LER-2 von Hand nachgespielt.
  GV-LER-1 ✅ 2026-09-29 (Weg des Probelaufs: `POST /api/chat` mit `X-Boerdi-Engine: agent`,
  OpenAI/gpt-6-luna): Zug 3 sucht breit, dann verengt — gezeigt die 3 Arbeitsblätter der
  verengten Suche (im Tor 0 Karten), jeder Zug 2 Schnellantworten, Anrede du. Die anderen drei offen.
- E2 Nachmessung (startet der Nutzer): `engine_matrix.py start --engines pattern,agent --repeat 3
  --exclude GV-RED-1 --label agent-runde-2`, OpenAI, gpt-6-luna; Auswertung im Studio-Vergleich (ST-7c).
- E3 Nur wenn der Lernpfad trotz Regel fehlt: Ansatz 3B.

## Review 2026-09-29 — Befunde und Behebung (`/better-coding-review`, 4 Prüfer) — ✅ 2026-09-29

Verdict vor der Behebung: 1 critical, 6 major, 13 minor, 10 nits. Behebung je Punkt Test zuerst:
- R-1 Skill-Verzeichnis: Titel- und Bearbeiten-Links in `--st-accent-text` = weiß auf weißem Panel.
- R-2 Skill-Suche: `outputFormat` fiel vor dem Senden weg, `includeSubcollections=False` hob die
  Server-Vorgabe auf; „nicht aktiv“ nur bei `art == "tool"`; Kappung bei 10 stumm; Text „ganzes Repositorium“.
- R-3 Prüfskript: 3 Wächter (Werkzeugnamen, Kernbegriff, Ansage-Regel) fehlten; „nicht abrufbar“ ergab 1
  statt 2 — Wurzel `master_skill._hole` nimmt „Skill … ist nicht abrufbar“ als Anleitung; leere Assert-Meldungen.
- R-4 „Zuletzt gezeigt“: stand als `system` ohne D4-Rahmen (auf dem Responses-Weg in `instructions`);
  Dokumente im Sitzungszustand vorbei am Schalter `logging.messages` und am Löschen; Kürzung ohne
  Vermerk; ganze Sitzung statt letzter Zug; Materialien vor der Kürzung statt der gezeigten. Umbau: Ablage
  an der gespeicherten Antwort (wie C1 geplant), Block aus dem Verlauf, gerahmt am Anfang der Nachricht.
- R-5 Themenfilter (`turn_links`) im Agent-Zug aus — nachgestellt Ursache von GV-AND-1#3 (9 → 2 Karten).
- R-6 Lotse zählt nirgends gegen den Pillen-Deckel (Injektor, Kürzung, Mischweg).
- R-7 `render_url` kodiert die Kennung.
- R-8 Studio-Kleinbefunde (Fokus, typisierte Liste, Tests, Linknamen, Texte).

**Stand 2026-09-29: alle acht behoben ✅.** Nachweis je Punkt, jeweils Test zuerst rot: R-1/R-2 19 Tests und
200 benachbarte grün; R-3 11 + 128, dazu die Live-Prüfung des übertragenen Master-Skills 11 von 11 (Exit 0);
R-4 155; R-5 64, die Nachstellung von GV-AND-1#3 behält jetzt 9 von 9 Karten; R-6 189 und 29
Schnellantwort-Tests; R-7 27; R-8 Studio 43 samt DE/EN-Katalogabgleich. Volles Tor auf dem Endstand: Backend
4504 passed, 2 xfailed; pg 28; OpenAPI- und Bereichs-Vertrag unverändert; Ruff sauber; Studio 1320/1320 in
109 Dateien; ESLint 0.

Altlasten, die das Review mitfand, laufen als eigene Sitzungen: der Studio-Fokusring liegt mit `--st-focus`
unter 3:1 (systemweit, dazu `agent-tester`; behoben 2026-09-29: 50 Überschreibungen gestrichen, es gilt
nur die globale `:focus-visible`-Regel samt Forced Colors, `--st-focus` entfernt; im selben Zug
`--st-accent-text` → `--st-on-accent` mit 8 Fehlpaarungen und 17 Feldrahmen unter 3:1 — Wächter
`npm run check:contrast` in CI, gemessen hell/dunkel/Forced Colors); weitere `system`-Blöcke verschmelzen auf dem Responses-Weg in
`instructions` (LiteLLM fügt sie mit einem Leerzeichen zusammen); der MCP-Client wiederholte auch abgelehnte
Werkzeugaufrufe (behoben 2026-09-29, Neubau-Plan 5-1c).

## Nachweis und Erfolg

- Jede Aufgabe: Test zuerst rot, dann grün; volle Suiten Backend und Studio, Ruff, ESLint, Vertrag unverändert.
- Erfolg: harte Quote des Agenten in der Spanne der Muster-Maschine; kein Fehler, der in allen
  drei Läufen wiederkehrt; Kosten je Zug unter denen der Muster-Maschine (E-5: 0,00303 USD).
- Rechnerisch: behebt der Plan die 21 erklärten oder zu klärenden Fehler, blieben 2 von 284 (0,99).

## Risiken

- **Mehr Token je Runde.** Der Block steht in jeder Runde der Schleife. Gedeckelt, nur der
  letzte Zug, nur mit Inhalt; die Messung weist die Kosten aus.
- **Der Master-Skill wirkt erst nach dem Übertragen** in den Knoten; bis dahin misst jede
  Nachmessung die alte Fassung.
- **Die Rolle geht dem Master-Skill vor.** Ohne D1 kann „hast du Übungen?“ weiter als
  Auftrag zum Erstellen gelesen werden.
- **Falsch erkannte Anrede** — nur, falls Paket B gebaut wird („Sie“ als dritte Person):
  Erkennung nur an eindeutigen Formen, Tests mit echten Sätzen.
- **Gespeicherte Rolle.** Wo die Seite „Agent & Maschine“ schon gespeichert wurde, steht die
  alte Rolle im Speicher; dort erreichen die neuen Sätze der Vorgabe die Anlage nicht und
  müssen im Studio übernommen werden. Lokal ist die Rolle nicht gespeichert (geprüft).
- **Parallele Arbeit an der Kartenanzeige** — Paket A beginnt mit deren Stand.

## Nebenbefund außerhalb dieser Runde

**Schreiben im Agent-Modus kommt im Chat nicht über die Vorschau hinaus.** Den Merkposten
der Schreib-Abnahme (`_pending_write`) und die Vorschau-Box (`_write_preview`) setzt nur die
Werkzeugschleife der Muster-Maschine (`tool_loop.py:772/784`); die Abnahme im Vorlauf
(`preflight.py:113`, „ja“ → ausführen ohne Modell) findet im Agent-Modus also nichts vor.
Die Agent-Schleife selbst streift in der Vorgabe `write_mode: propose` jeden Schlüssel ab
(`agent_write.py`), ihr eigener Merkposten gilt nur im selben Lauf. Seit der Agent im Chat
die Vorgabe ist (D-15), fehlt damit der Zugwechsel, den `agent_write` voraussetzt („im Chat
setzt der Bestand den Menschen am Zugwechsel wieder ein“). Als eigene Aufgabe vorgeschlagen;
der Abschnitt „Ändern“ des Master-Skills beschreibt das Soll richtig.

**Stand 2026-09-28 — belegt, Vorschlag zur Freigabe, nicht gebaut** (`/better-coding-debug`).

*Beleg.* `backend/tests/test_agent_schreib_abnahme.py` (neu) spielt zwei Chat-Züge im
Agent-Modus durch. Echt laufen Vorlauf samt Abnahme, `respond_agent`, Agent-Schleife samt
Schreib-Wall und MCP-Client; gefälscht sind nur Modell, MCP-Transport (zweistufig wie der
Server) und Datenbank.
- `test_ja_im_folgezug_fuehrt_die_gezeigte_aenderung_aus` — rot: „Vorlauf hat eingelöst:
  False“, zwei Server-Aufrufe ohne Schlüssel, Antwort im Folgezug „Soll ich die Sammlung
  „Bruchrechnen“ anlegen?“. Das ist die S5-Schleife vom 2026-08-15, jetzt im Agent-Modus.
- `test_der_agent_zug_legt_vorschau_box_und_merkposten_an` — rot: `_write_preview` leer,
  kein `_pending_write`.
- `test_ohne_zustimmung_…_keinen_schluessel` — grün und muss grün bleiben: ein „nein“ führt
  nichts aus, kein geprägter Schlüssel erreicht die Kette des Modells.
- Die beiden roten stehen als `xfail(strict=True)`; die Suite bleibt grün, nach dem Umbau
  melden sie XPASS → Marker entfernen.

*Ursache.* `WriteGate.observe` merkt sich einen geprägten Schlüssel nur in `execute` und nur
in der lauf-eigenen Instanz (`agent_write.py:122`); `run_agent_loop` gibt nichts nach außen
(`agent_loop.py:216`); `respond_agent` setzt weder Merkposten noch Vorschau. Die Abnahme im
Vorlauf ist maschinenunabhängig (`preflight` läuft vor der Engine-Weiche) — sie findet nur
nichts vor.

*Vorschlag.*
1. `WriteGate` merkt sich den offenen Vorgang in **beiden** Betriebsarten, dazu den
   geschwärzten Vorschautext, und gibt beides über `offene_abnahme()` heraus, solange der Lauf
   ihn nicht eingelöst hat. `prepare` bleibt unverändert: in `propose` setzt die Schleife nie
   einen Schlüssel ein.
2. `run_agent_loop` bekommt die Naht `on_offene_abnahme(merkposten, vorschau)`, gerufen
   höchstens einmal, beim Laufende (`schluss`). Nur der Chat-Zug reicht sie herein;
   `/api/agent` bleibt unverändert. Es ist die einzige Naht, über die ein Schlüssel die
   Schleife verlässt — in die Sitzung, nie zum Modell. `on_tool_result` bleibt schlüsselfrei.
3. `respond_agent` legt beides dort ab, wo `tool_loop` es ablegt: `entities["_pending_write"]`
   (überdauert den Zug) und `session_state["_write_preview"]` (nur dieser Zug) — über eine
   kleine Hilfe `merke_abnahme()` in `write_approval`, neben dem Leser, statt einer dritten
   Schreibstelle mit eigenen Literalen. Alles Weitere macht der Bestand unverändert:
   `turn_persist` zeigt Box und Knopf „Ja, so ausführen“, `update_session` speichert den
   Merkposten, der Vorlauf löst im nächsten Zug ein glattes „ja“ ohne Modell ein — mit den
   gezeigten Argumenten.
- Vier Dateien, weil der Schlüssel im Gate entsteht, das Gate in der Schleife lebt, die
  Schleife auch dem sitzungslosen Endpunkt dient und nur der Chat-Zug eine Sitzung hat.
  `tool_loop` bleibt unberührt.
- Tests: die beiden `xfail` werden grün; dazu Gate (propose merkt, setzt nie ein; execute
  verbraucht → nichts offen; letzte Vorschau gewinnt), Naht (einmal am Ende, ohne offenen
  Vorgang kein Aufruf, ohne Empfänger wie heute), kein Schlüssel in `AgentRun`, Spur, Debug.

*Rolle von `write_mode`: keine für die Übergabe.* `write_mode` regelt nur, ob die Schleife
**im selben Lauf** einen Schlüssel einsetzen darf. Die Annahme am Zugwechsel ist Regel 2 des
Walls (`domain/write_confirm`) und gilt in beiden Maschinen.
- `propose` (Vorgabe): die Schleife bestätigt nie, die Person nimmt im nächsten Zug an. Genau
  das meint „ein Vorschlag, den ein Mensch andernorts annimmt“ — im Chat ist „andernorts“ der
  nächste Zug. „Nichts, was schreibt, schreibt von selbst“ bleibt wörtlich wahr.
- `execute`: löst die Schleife im Lauf ein, ist der Vorgang verbraucht und es wird nichts
  übergeben (keine Box über einer schon ausgeführten Änderung). Fragt sie stattdessen nach —
  so verlangt es der Master-Skill („Dann beendest du den Zug“) —, gilt der Weg von `propose`.
- Bewusst **nicht** übernommen: der Fingerabdruck-Weg aus `tool_loop` (das Modell ruft im
  Folgezug dasselbe Werkzeug, und wir setzen den Schlüssel ein). Er bestätigt auf eine
  Entscheidung des Modells hin; im Agent-Weg bleibt die Zustimmung allein bei der Person
  (glattes „ja“ oder Knopf). Preis: ein „ja“ mit mehr als sechs Wörtern ergibt eine neue
  Vorschau statt der Ausführung — die sichere Richtung.

*Regel 1 bleibt:* Hinweg (`strip_confirm_token`) und Rückweg (`redact_confirm_token` vor
jeder Weitergabe) unverändert; der Merkposten liegt in `entities`, die nicht in die Kette des
Modells gehen (Test 3 prüft das über den gespeicherten Merkposten hinweg), und der Debug-Block
streicht `_`-Schlüssel (`turn_persist.py:163`).

*Weitere Befunde beim Belegen (je eigener Entscheid):*
- **N-1 Ein „nein“ räumt den Merkposten nicht ab** (Probe gegen `redeem_write_approval`):
  nach „Nein, doch nicht“ bleibt `_pending_write` stehen, und ein späteres glattes „ja“ binnen
  10 Minuten — etwa auf eine ganz andere Rückfrage — führt die abgelehnte Änderung aus. Gilt
  heute für die Muster-Maschine, mit dem Vorschlag auch im Agent-Weg. Empfehlung: ein
  Merkposten gilt nur für den unmittelbar folgenden Zug; was dort weder eingelöst noch ersetzt
  wird, verfällt (der Fingerabdruck-Weg der Muster-Maschine liegt im selben Folgezug und
  bleibt). Betrifft beide Maschinen und die früh endenden Züge — Direkt-Aktionen schreiben den
  Sitzungszustand nicht —, braucht also einen eigenen kleinen Schnitt; am besten zusammen mit
  dem Vorschlag bauen.
- **N-2 Schlüssel im Protokoll** (Probe): `services/mcp/client.py:247` schreibt die
  Rohargumente auf INFO, bei jeder Bestätigung samt `confirmToken` (S5, `tool_loop`,
  `execute`). Einmal gültig und 10 Minuten, also kleines Risiko, aber gegen die Hausregel
  („weder Argumente noch Schlüssel ins Protokoll“). Vorschlag: dort ohne Schlüssel
  protokollieren; eine Zeile plus Test.
- **N-3 Master-Skill „Ändern“:** „Diese Vorschau legst du wörtlich als gerahmten Kasten vor“
  — nach dem Umbau erscheint die Box des Servers von selbst; folgt das Modell dem Satz mit
  `zeige_dokument`, stehen zwei Kästen da. Den Satz berichtigen, nicht streichen („Die
  Vorschau erscheint von selbst als Kasten; ordne sie mit einem Satz ein und beende den
  Zug.“). Text, nicht Code; Übertragen machen Nutzer bzw. Redaktion.
- **N-4 Echte Schreibvorgänge:** `GV-RED-1` legt nach dem Umbau auch im Agent-Modus echt einen
  Datensatz auf dem Staging-Bestand an (`evals/README.md`). Die Matrix lässt ihn per Vorgabe
  weg (`--exclude GV-RED-1`); beim Einzel-Goldlauf weiter per Auswahl weglassen. Ebenso
  schreibt ein „ja“ im Studio-Probelauf dann dorthin, wohin der MCP-Server zeigt — wie heute
  im Muster-Modus.
- **N-5 (kosmetisch):** der Abnahme-Zug steht im Debug- und Qualitätsprotokoll auch im
  Agent-Modus als `M18`.

## Offene Fragen an den Nutzer

1. D1 und B0: die Rolle im Kopf schärfen und `override` der Personas mitgeben (Code-Vorgabe
   samt Test)? Der Kopf geht dem Master-Skill vor; ohne D1 bleibt „Material zuerst“
   unsicher, ohne B0 widerspricht „Wer dich siezt …“ den festen Anreden.
2. Übertragen der neuen Vorlage in den Knoten `535cabca…` — durch dich bzw. die Redaktion.
3. Die Ansage-Zeile „[ edu-sharing Skill ] Chatbot Masterskill - aktiv“ steht heute einmal je
   Sitzung sichtbar in der ersten Antwort. Soll sie für Endnutzer bleiben?
4. Freigabe der Code-Pakete A (Karten, Schnellantworten), C (voriger Zug) und E (Nachweis).

„Material zuerst“ (vorher Frage 2) steht jetzt so im Master-Skill, wie Gold-Flow und alte
Muster es erwarten; wer es anders will, ändert den Text, nicht den Code.
