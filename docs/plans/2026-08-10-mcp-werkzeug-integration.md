# MCP-Werkzeuge des neuen Servers in Chat und Pattern integrieren

Stand 2026-08-10. Quelle der Wahrheit für den Server: `../wlo-mcp-server-sc/`
(nur lesen, nie ändern) — dort `docs/INTEGRATION.md` (Übergabe für
Chatbot-Entwickler, am 2026-08-09 gegen einen **laufenden** Server geprüft) und
`docs/TOOLS.md` (Chat-Trigger je Werkzeug).

---

## 1. Messung: vier Listen, vier verschiedene Längen

Alle vier Zahlen sind ausgezählt, nicht geschätzt.

| Liste | Ort | Anzahl | Wozu |
|---|---:|---:|---|
| **Server, deployt** | `wlo-mcp…nip.io/mcp`, `tools/list` am 2026-08-10 | **38** | 25 lesend + 13 kuratierend |
| Server (Quelltext sc) | `wlo-mcp-server-sc` | 41 | 27 lesend + 14 kuratierend |
| Server (Namen im Quelltext) | dito | 42 | +`get_skill_for_task`, der Ein-Werkzeug-Ersatz für `search_skill`+`get_skill` |
| Unsere Registry | `seeds/05-knowledge/mcp-servers.yaml` | **23** | Routing Werkzeugname → Server-URL |
| Unser Katalog | `services/mcp/tool_defs.py` | **19** | was das Modell überhaupt sehen kann |
| Aus Pattern erreichbar | `seeds/03-patterns/*.md` | **17** | was das Modell je Zug wirklich sieht |

Die drei Zahlen unserer Seite sind gestaffelt, und das ist Absicht: ein Werkzeug
muss in allen dreien stehen, um zu wirken. Zwei Wächter halten das fest
(`test_config_seed_tree.py`): jeder in einem Pattern genannte Name muss im
Katalog existieren, und jeder Katalog-Name muss aus einem Pattern erreichbar
sein — sonst mit Begründung in `_NICHT_UEBER_PATTERN`.

### 1.0 Deployment hinkt dem Quelltext hinterher — mit Folgen für den Plan

Am 2026-08-10 über unseren eigenen Transport (`discover_server_tools`) gemessen,
nicht aus dem Quelltext geschlossen. Der deployte Server ist ein **Zwischenstand**:

| Werkzeug | im sc-Quelltext | deployt |
|---|:--:|:--:|
| `get_url_text` | ✅ | ✅ |
| `find_wlo_skills` (entfallen) | ❌ | ❌ — auch live schon weg |
| `search_skill` | ✅ | **❌** |
| `get_skill` | ✅ | **❌** |
| `wlo_set_topic_page` | ✅ | **❌** |

**Folge:** Paket D (Skills) und der Themenseiten-Schreibpfad lassen sich heute
nicht live abnehmen — die Werkzeuge sind nicht da. Beides hängt an einem
Server-Deployment und damit an der Nutzer-Domäne. Der Rest des Plans ist davon
unberührt: die 13 Kurationswerkzeuge stehen live in `tools/list` (und verweigern
ohne Anmeldung, wie dokumentiert), also sind die Pakete A, B, C, E, F, G
unabhängig davon baubar.

**Bestätigt statt vermutet:** `find_wlo_skills` in unserer Registry ist tot —
nicht nur im neuen Quelltext, sondern auf dem laufenden Server.

### 1.1 Was der neue Server dazugewonnen hat

Gegenüber dem Inventar des Ideen-Dokuments (38 = 25 + 13):

| Werkzeug | Art | Bedeutung |
|---|---|---|
| `search_skill` | neu | Redaktionell gepflegte Anleitungen finden |
| `get_skill` | neu | Eine Anleitung im Wortlaut holen |
| `get_skill_for_task` | neu (Alternativmodus) | Beides in einem, per `WLO_SKILL_TOOL_MODE=one-tool` |
| `get_url_text` | neu | Text hinter beliebiger Web-Adresse. **Als unsicher deklariert**, im Docker ab Werk aus |
| `wlo_set_topic_page` | neu (14. Kurationswerkzeug) | Welche Variante eine Themenseite öffentlich rendert |
| `find_wlo_skills` | **entfallen** | ersetzt durch `search_skill`/`get_skill` |

### 1.2 Kombi-Werkzeuge: was zusammengelegt wurde

Der Nutzer-Hinweis „bestehende wurden z.T. optimiert und zu Kombitools vereint"
trifft nicht die Werkzeug-*Namen*, sondern deren *Parameter*. Drei Wünsche des
Ideen-Dokuments sind dadurch schon erfüllt, ohne dass ein neues Werkzeug entstand:

| Ideen-Dokument forderte | Wirklichkeit im neuen Server |
|---|---|
| `wlo_create_text_content` (Prio hoch) | **Parameter `content` in `wlo_create_content`** („WEG 2 — der Datensatz trägt den Inhalt selbst"), dazu `contentFormat`, `fileBase64` |
| `wlo_update_content_text` (Prio mittel) | **Parameter `content`/`contentFormat`/`fileBase64` in `wlo_update_content`** |
| `find_wlo_skills` nachschärfen (Prio hoch) | `search_skill` mit `collectionId`; ohne `WLO_SKILLS_COLLECTION_ID` durchsucht es das ganze Repositorium nach Inhaltsart `ai_skill` (bis 2026-08-12 `ai_prompt`) |

### 1.3 Was unsere Seite konkret verpasst

**Registry (23) — ein toter Eintrag, 19 fehlende.**
`find_wlo_skills` steht drin und existiert serverseitig nicht mehr. Fehlend:
`get_node_collections`, `get_url_text`, `search_skill`, `get_skill`,
`wlo_auth_status` und alle 14 Kurationswerkzeuge.

**Katalog (19) — 8 der 27 lesenden Werkzeuge fehlen:**

| Werkzeug | Einschätzung |
|---|---|
| `search_skill`, `get_skill` | **Der größte Hebel.** Genau das, was das Ideen-Dokument als `get_skill_bundle` mit Priorität „hoch" forderte |
| `get_node_collections` | Klein und billig: „In welchen Sammlungen liegt dieses Material?" — der Use-Case „Verortung" |
| `get_wikipedia_summary` | Bewusst draußen: `services/wikipedia_service.py` ruft es **deterministisch** über `call_mcp_tool`, nicht über das Modell |
| `get_url_text` | Bewusst draußen: als unsicher deklariert, im Docker aus; unser RAG-Ingest hat einen eigenen SSRF-Schutz |
| `search`, `fetch` | ChatGPT-Konvention, redundant zu `search_wlo_all` |
| `wlo_auth_status` | Nur sinnvoll, wenn es eine Anmeldung gibt |

---

## 2. Bewertung des Ideen-Dokuments

### 2.1 Was es richtig gesehen hat — und was inzwischen gebaut ist

| Forderung | Prio laut Dokument | Stand heute |
|---|---|---|
| `get_skill_bundle` | hoch | ✅ als `get_skill` vorhanden |
| `wlo_create_text_content` | hoch | ✅ als Parameter von `wlo_create_content` |
| `search_wlo_content` Lizenzfilter „unverifiziert" | hoch | ✅ verifiziert **und** dokumentiert: Familien-Filter, Exaktheits-Pass, Sammelwert `OER` = fünf Suchen |
| `find_wlo_skills` nachschärfen | hoch | ✅ ersetzt |
| `wlo_update_content_text` | mittel | ✅ als Parameter |
| `wlo_set_topic_page` | mittel | ✅ vorhanden, 14. Kurationswerkzeug |
| `search_web` / `crawl_source` | mittel | ⚠️ nur teilweise: `get_url_text`, unsicher und ab Werk aus |
| RAG nach Korpus segmentieren (§2.3) | Voraussetzung für E8 | ✅ **im Neubau bereits erledigt** — `search_rag_chunks` filtert je Bereich *in* der Abfrage, `rag-config.yaml` führt benannte Korpora, und M04/M15 deklarieren `rag_areas` |

Der letzte Punkt ist der wichtigste: §2.3 nennt die fehlende RAG-Segmentierung
als Blocker für das ganze Quellen-Routing. Dieser Blocker existiert im Neubau
nicht mehr.

### 2.2 Was es forderte und weiterhin fehlt

| Forderung | Stand |
|---|---|
| `get_compendium_section` (kapitelweise) | ❌ `get_compendium_text` liefert nur den **ganzen** Text (Massenabruf bis 25 IDs, keine Kapitel) |
| `get_qa_pairs` / `wlo_update_qa_pairs` | ❌ |
| `get_collection_coverage` | ❌ |
| Repo-Trigger / Webhook | ❌ |
| `wlo_register_usage` | ❌ **und bewusst abgelehnt** — INTEGRATION.md §5: der Endpunkt verlangt eine Anwendungs-Signatur, deren Besitz das Handeln für beliebige Nutzerinnen erlaubt; das kehrt die Auth-Idee des Servers um. Betreiber-Entscheidung, keine Code-Frage |

### 2.3 Wo das Dokument an unserer Wirklichkeit vorbeigeht

Drei strukturelle Vorschläge, je mit gemessenem Gegenbefund.

**(a) „Es gibt kein Slot-Klärungs-Pattern" (§3.1) — hier trifft es zu.**
`M03 Slot-Klärung` ist bei uns ein Pattern mit `priority: 450`, genau die
kritisierte Bauform. Ein Frame mit Eigentümer, Frist und Versuchszähler
existiert nicht: die Suche nach `pending_slot|frame|slot_register|awaiting` in
`domain/` und `graph/` liefert **null** Treffer. Was wir stattdessen haben, ist
Entitäten-Persistenz — `graph/nodes/merge.py` faltet Entitäten je `turn_type`
über Züge hinweg. Das ist weniger als E1+E2, aber nicht nichts.

**(b) „E8 Quellen-Routing fehlt vollständig" — nur zur Hälfte.**
Der Pattern-Vertrag trägt bei uns bereits eine Quellendeklaration: `sources:`,
`tools:` und `rag_areas:` je Pattern, und `_select_active_tools` schneidet die
Werkzeugliste darauf zu. Was fehlt, ist die *Vorrangkette mit
Ausreichend-Kriterium* und der *Herkunftsnachweis in der Antwort*.

**(c) Die 16-Pattern-Umbenennung (S-/B-/P-) ist ein Risiko ohne Ertrag.**
Sie würde den Seed-Baum, die Golden-Referenz und die Eval-Basis gleichzeitig
ungültig machen. Der P11-Probelauf hat gezeigt, dass Live-Defekte auftreten, die
2135 grüne Tests nicht finden. Eine Umbenennung kauft dafür keinen einzigen
neuen Fähigkeitspunkt — die Fähigkeiten stecken in den Werkzeugen und den
Quellen, nicht in den IDs.

---

## 3. Entscheidungen des Nutzers (2026-08-10)

| Frage | Entscheid |
|---|---|
| Kuration | **Zwei Betriebsarten.** Standard: nur lesend. Per ENV ein fester Nutzer hinterlegt → alle Werkzeuge. Zusätzlich ein Pattern, das den Anmeldeweg des MCP-Servers anstößt. Die Nutzer-Anmeldung läuft **über den MCP**, nicht über uns — wir binden ihn nur per URL ein |
| Skills | **Pattern-abhängig.** Wo Skills gebraucht werden könnten, kommen beide Werkzeuge plus ein Hinweis ins Pattern. Erwartete Skills: Kuratierung, Alltagsarbeit für Lehrende, Qualitätssicherung. Zusätzlich manueller Aufruf über `/skillname` |
| Pattern-Umfang | **Groß.** Die Goldreferenz muss ohnehin neu geschrieben werden, auch bei kleinen Änderungen. Alles Gute aus dem Ideen-Dokument einarbeiten oder umarbeiten; vorher den Seed-Baum sichern, um zurückfallen zu können |
| Slot-Frame | **Jetzt mitbauen** |

---

## 4. Architektur-Nähte (gemessen, nicht geraten)

**Die Auth-Naht existiert nicht.** `services/mcp/transport.py` (135 Z.) kennt
weder `Authorization` noch `Bearer` noch `header`; `call_mcp_tool` nimmt nur
`(tool_name, arguments)`. Der Draht ist eine einzige Zeile:

```python
async with streamablehttp_client(url) as (read_stream, write_stream, _):
```

Der Parameter `headers=` des SDK ist **deprecated** („Parameters headers,
timeout, sse_read_timeout, and auth are deprecated"). Der tragfähige Weg ist
`httpx_client_factory=` — genau der, den der Modul-Docstring schon als
`simplify:`-Aufstiegspfad benennt. Der Server nimmt `Authorization: Bearer
wlo2.…` (Zugangsblock) entgegen.

**Kein Frame, keine Slash-Befehle.** `pending_slot|frame|slot_register|awaiting`
in `domain/` und `graph/`: null Treffer. Slash-Befehle gibt es nicht; der
natürliche Ort für `/skillname` ist `graph/nodes/preflight.py`, wo die
deterministischen Direkt-Aktionen sitzen — **vor** der Klassifikation, also ohne
deren ~2 s Kosten.

**Drei Listen müssen synchron bleiben.** Registry → Katalog → Pattern. Zwei
Wächter in `tests/test_config_seed_tree.py` halten beide Richtungen fest. Sie
werden bei jeder Erweiterung von allein laut — das ist erwünscht und ersetzt
eine Prüfliste.

---

## 5. Pakete

Sieben Pakete, jedes für sich lauffähig und abnehmbar. Reihenfolge nach
Abhängigkeit, nicht nach Wichtigkeit.

**Erste Aufgabe jedes Pakets ist eine Messung**, keine Schätzung. Begründung aus
der eigenen Historie: in dieser Rubrik lag jede Vorab-Schätzung um Faktor 2–2,5
zu niedrig. Erst messen, dann schneiden, dann bauen.

Jedes Paket beginnt mit **Schritt 0: `/better-coding-workflow` aufrufen**
(Skills fallen aus dem Kontext).

### Paket A — Inventar richtigstellen (Fundament, keine Verhaltensänderung)

Ohne A wirkt jede spätere Ergänzung nur teilweise, weil ein Name in allen drei
Listen stehen muss.

- **A1** Registry live vom Server holen (`tools/list`), nicht abtippen — der
  Kommentar in `mcp-servers.yaml` schreibt genau das vor. 23 → **38** Namen
  (Ist-Stand des Deployments, siehe §1.0), `find_wlo_skills` entfällt.
- **A2** `get_node_collections` in Katalog und Pattern (Verortung eines
  Materials; ergänzt `get_node_breadcrumb`).

**Abnahme:** beide Wächter grün, `pytest -q` ohne neue Fehler, ein Live-Zug, der
`get_node_collections` tatsächlich aufruft.

#### ✅ Paket A erledigt 2026-08-10

Belege: `pytest -q` → **2584 passed, 4 skipped** (2583 vorher + 1 neuer Wächter) ·
`ruff check .` → All checks passed · `export_openapi.py --check` → openapi
contract unchanged. Registry gegen den laufenden Server geprüft: **41 = 41**,
kein toter Name, kein unbedientes Katalog-Werkzeug. Katalog 19 → 20.

Neuer Wächter `test_verortungs_werkzeug_steht_in_beiden_infrage_kommenden_mustern`
hält Befund 3 fest; rot-grün geprüft (ohne den M06-Eintrag: `assert not ['M06']`).

**Drei Befunde, die ohne den Live-Zug nicht aufgefallen wären:**

1. **Die laufende Entwicklungs-Datenbank war hinter dem Seed-Baum zurück.** Vier
   Muster, alle Abweichungen „nur im Seed": M05 und M12 fehlte
   `lookup_wlo_publishers`, M06 `get_related_content`, M08 gleich vier Werkzeuge
   (`get_collection_stats`, `get_compendium_text`, `get_node_breadcrumb`,
   `search_wlo_within_collection`). Die W9a/W9b-Ergänzungen vom 01.08. waren auf
   dieser Instanz **nie aktiv** — die Wächter blieben grün, weil sie die
   Seed-Dateien lesen, nicht die Datenbank. Mit `boerdi import-config` behoben;
   Datei-Diff Export↔Seed ist wegen Neuserialisierung wertlos, der Vergleich muss
   auf der Sachebene laufen (Skript im Scratchpad).
2. **Ohne `get_node_collections` löst das Modell die Einordnungsfrage durch
   Brute Force.** Gemessen: `tools_called` zeigte **viermal**
   `get_collection_contents` — vier Sammlungen einzeln durchgesehen — und die
   Antwort lautete am Ende, es lasse sich nichts zuordnen. Mit dem Werkzeug:
   **ein** Aufruf.
3. **Die Einordnungsfrage routet nicht stabil.** Zwei Live-Läufe derselben
   Formulierung landeten einmal in M08, einmal in M06; die Wahl hängt am Muster
   des Vorzugs. Deshalb steht das Werkzeug in **beiden** Mustern — nur eines zu
   bestücken hieße, es in der Hälfte der Fälle fehlen zu lassen. Zusatzmessung:
   es verdrängt `get_related_content` nicht, „mehr davon" greift weiterhin zu
   jenem.

**Offen gelassen, nicht vergessen:** `validate_tool_args` reicht Argumente
**unvalidiert durch**, wenn kein Modell registriert ist (`tool_defs.py:537`).
Drei Katalog-Werkzeuge haben keins — `get_topic_page_content`,
`get_wlo_content_text`, `search_wlo_all`. Bestandslücke, nicht durch A entstanden;
ein Wächter dafür wäre die naheliegende Ergänzung, gehört aber nicht in dieses
Paket.

### Paket B — Frame (E1 Slot-Register + E2 Frame)

Ändert die Zug-Steuerung, also jeden Zug. Deshalb früh und allein.

- **B0** Messen: wie viele Stellen lesen/schreiben heute Entitäten über Züge
  hinweg (`merge.py` faltet je `turn_type`), und wo genau liegt die Naht vor der
  Pattern-Auswahl in `route.py`.
- **B1** Frame-Modell in `graph/state.py`: Eigentümer, Slots, fehlender Slot,
  Versuchszähler, Frist. Höchstens einer offen.
- **B2** Persistenz über `services/db_sessions.py`, damit er den Zug überlebt.
- **B3** Auflösung im `route`-Knoten **vor** der Pattern-Auswahl.
- **B4** M03 vom Pattern zum Renderer (die Rückfrage bleibt, der Eigentümer
  behält den Vorgang).
- **B5** E5 Revision: ein gefüllter Slot wird geändert → Eigentümer erneut
  aufrufen. Löst M11 ab.

**Abnahme:** Frist und Versuchsgrenze als Tests; ein Themenwechsel verwirft den
Frame ohne Rückfrage; Live-Beleg des Beispielverlaufs Zug 1→2 und Zug 11.

#### B0 erledigt 2026-08-10 — die Messung schneidet das Paket neu

Die statischen Nähte sind kleiner als gedacht, die Verhaltenslücke ist an einer
ganz anderen Stelle als angenommen. Beides gemessen, nicht geschätzt.

**Statisch — zwei der drei geplanten Bauteile existieren bereits.**

| Geplant | Befund |
|---|---|
| B2 Persistenz über `db_sessions.py` | **Schon da.** `turn_persist.py:185` schreibt `entities=session_state["entities"]` als JSONB. `_`-präfigierte Schlüssel sind die etablierte Konvention für zugübergreifenden Nicht-Slot-Zustand (24 im Bestand: `_canvas_topic`, `_lp_used_node_ids`, `_last_pattern` …). Kein neuer Spalten-Typ, keine Migration, kein neuer Schreiber |
| B3 Naht vor der Pattern-Auswahl | **Schon da.** `enforced_pattern_id` ist die *erste* Vorrangstufe von `select_pattern` (`pattern_engine.py:324`, vor Hint und Fallback). Der Frame setzt sie — Reihenfolge bleibt Safety > Frame > Hint |
| B4/B5 Sprengradius | **M03: 21 Quell- + 24 Test- + 9 Seed-Dateien. M11: 17 + 14 + 7.** Kein kleines Paket |

**Live — drei der vier Abnahmekriterien erfüllt der Bestand schon.**

Sechs Verläufe gegen `boerdi_p11`, jeder zweimal (Paket A hat belegt, dass die
Musterwahl nicht deterministisch ist):

| Verlauf | Erwartung laut Abnahme | Gemessen |
|---|---|---|
| Eigentümer-Übergabe: „Erstell mir ein Arbeitsblatt." → „Bruchrechnung" | Antwort landet beim Erzeuger | ✅ M03 → **M10**, `turn_type=clarification`, Entitäten gefaltet, Canvas erzeugt |
| Revision (E5/B5): → „Nein, lieber Klasse 8." | Eigentümer erneut aufrufen | ✅ M10 → **M11**, `turn_type=correction`, neuer Slot `requested_class` |
| Themenwechsel verwirft den Vorgang | ohne Rückfrage | ✅ M03 → **M06**, keine Wiederholung der Frage |
| Frist: Slot überlebt 4 fremde Züge | verfällt | ✅ `thema` wurde vom neuen Thema ersetzt — **kein Defekt messbar** |

Die erste Fassung dieser Messung war durch meine eigene Formulierung verdorben
(„Erstell mir **noch** ein Quiz" verweist ausdrücklich zurück, der Übertrag wäre
dort richtig gewesen) — ohne das Wort wiederholt und erst dann gewertet.

**Der eine gemessene Defekt — und er ist schwerer als eine Schleife.**

Vier bzw. sieben Züge, beide Läufe identisch:

| Zug | Muster | `thema` | Nutzersicht |
|---|---|---|---|
| 1 „Erstell mir ein Arbeitsblatt." | M03 | `None` | „Zu welchem **Thema**?" |
| 2 „weiss nicht" | M03 | `None` | dieselbe Frage |
| 3 „egal" | M03 | `None` | dieselbe Frage |
| 4 „such du was aus" | M10 | `'such du was aus'` | „Arbeitsblatt zum Thema *such du was aus* erstellt" — **das Dokument darunter heißt „Prozentrechnung im Alltag"** |

Drei Fehler in einer Kette: (1) unbegrenztes Nachfragen, es gibt keine
Versuchsgrenze; (2) die Ausweich-Floskel wird zum Thema; (3) der erzeugte Inhalt
handelt von einem Thema, das nie jemand genannt hat, und widerspricht dem Satz
direkt darüber. Zug 5–7 setzten das fort (`thema='Wasserkreislauf'` bzw.
`'Prozentrechnung'` — frei erfunden).

**Wurzel von (2):** der Platzhalter-Filter in `merge.py` gibt es genau dafür,
aber er vergleicht die **ganze getrimmte Zeichenkette auf Gleichheit** gegen
`placeholder-topics.yaml`. „egal", „weiss nicht", „such du was aus" stehen dort
nicht. Die Liste ist Studio-pflegbare Config, kein Code.

**Schnitt, der daraus folgt** — die Plan-Regel lautet „erst messen, dann
schneiden, dann bauen":

- **B1–B3 gebaut** als *eine* Scheibe: der Frame auf seinen tragenden Teil
  reduziert (`slot` + `attempts`), Persistenz über die bestehende
  `_`-Konvention, Auflösung über `enforced_pattern_id`.
- **Eigentümer-Feld und Frist NICHT gebaut** — für beide ist kein Defekt
  messbar, und die Übergabe funktioniert ohne sie. Als `simplify:` markiert.
- **B4/B5 nicht gebaut** und dem Nutzer vorgelegt: sie kosten 38 Quell- und 38
  Testdateien für Fähigkeiten, die die Messung als bereits vorhanden ausweist.

#### ❌ B4 und B5 gestrichen 2026-08-10 (Nutzer-Entscheid)

Nicht vertagt, sondern **bewusst verworfen** — damit später niemand sie für
vergessen hält. Die Begründung steht hier vollständig, weil sie der einzige
Grund ist, warum zwei Bausteine des ursprünglichen Entwurfs fehlen.

| | Entwurf | Messung |
|---|---|---|
| **B4** | M03 vom Muster zum Renderer: die Rückfrage bleibt, aber der *Vorgang* bleibt beim ursprünglichen Muster | Der Bestand tut das schon: „Erstell mir ein Arbeitsblatt" → „Bruchrechnung" landet bei **M10**, `turn_type=clarification`, Entitäten gefaltet, Canvas erzeugt |
| **B5** | Revision eines gefüllten Slots ruft den Erzeuger erneut auf; löst M11 ab | Der Bestand tut das schon: „Nein, lieber Klasse 8" → **M11**, `turn_type=correction`, neuer Slot `requested_class` |

Beide Verläufe zweimal live gefahren (die Musterwahl ist nicht deterministisch,
Befund aus Paket A). **Sprengradius laut B0-Messung: M03 = 21 Quell- + 24 Test-
+ 9 Seed-Dateien, M11 = 17 + 14 + 7.** Zusammen 38 Quell- und 38 Testdateien
für ein Verhalten, das sich in der Messung nicht von dem unterscheidet, was
heute passiert — Risiko ohne Gegenwert.

**Wann das neu zu bewerten wäre:** wenn ein Golden-Lauf einen Verlauf zeigt, in
dem die Übergabe *nicht* beim Erzeuger landet. Dann ist der Defekt benannt, und
erst dann lohnt der Umbau.

#### ✅ B1–B3 erledigt 2026-08-10

Belege: `pytest -q` → **2606 passed, 4 skipped** (2584 vorher + 22 neue) ·
`ruff check .` → All checks passed · `export_openapi.py --check` → openapi
contract unchanged. Rot-grün geprüft: ohne die Verdrahtung fallen 4 der neuen
Tests, jeder aus dem richtigen Grund (`assert None == 'M15'`, fehlender
`_frame`).

**Gebaut.** `domain/turn_frame.py` (127 Z., rein): `note_clarification` ·
`clear_frame` · `clarification_exhausted` · `resolve_frame`. Zustand in
`entities["_frame"] = {"slots": [...], "attempts": n}` — die Zählung setzt
zurück, sobald ein Slot dazukommt, denn M03 fragt laut Pflicht-Schema immer nur
nach dem WICHTIGSTEN offenen Slot; eine Folgefrage ist Fortschritt, keine
Wiederholung. Geschrieben in `turn_persist.py` neben `_last_pattern` (dieselbe
Quelle: das AUSGEFÜHRTE Muster), gelesen in `route.py` vor `select_pattern`.

**Der Befund, der den Bau erst brauchbar gemacht hat — aus dem ROTEN Live-Lauf.**
Die Auflösung feuerte nachweislich (`Frame erschoepft: Klaerer nach M15
umgeleitet`, sechsmal im Log), und **das Verhalten änderte sich trotzdem nicht**.
Die nächste Log-Zeile sagte warum:

```
effective_pattern override: engine=M15 → executed=M03 (canvas_routed=True)
```

Der **Canvas-Fast-Path ist ein zweiter, unabhängiger Erzeuger derselben
Rückfrage.** Sein Eintritt hängt allein an `intent_id == "I05"` und umgeht die
Musterwahl absichtlich — der Kommentar sagt es wörtlich: „even if the pattern
engine eliminated M10 … not fall through to a generic M03 Clarification
response". Er lief NACH der Auflösung und rendete die Frage erneut. Ohne diese
Messung wäre B3 totes Gewicht gewesen (der neunte Fall der Klasse
„dokumentiert ohne Konsumenten", diesmal selbst gebaut). Behoben mit einem
Parameter `frame_exhausted` am Fast-Path — er tritt zurück, statt ein drittes
Mal zu fragen. **Regel daraus: die Musterwahl ist nicht die einzige Stelle, an
der eine Antwort entsteht. Vor jedem Eingriff prüfen, ob ein Fast-Path
dieselbe Ausgabe unabhängig erzeugt.**

**Live-Beleg, zwei Läufe identisch** (`M03 → M03 → M15 → M10`):

| Zug | vorher | jetzt |
|---|---|---|
| 3 „egal" | M03, dritte wortgleiche Frage | **M15**: „Dann wählen wir ein einfaches Thema: Soll ich ein Arbeitsblatt zu **Tieren**, **Umwelt** oder **Mathematik** erstellen?" |

M15 ist dabei kein Themenwechsel: die Antwort bleibt beim Arbeitsblatt und macht
konkrete Vorschläge. Regression geprüft — die echte Klärung
(`M03 → „Bruchrechnung" → M10`) läuft unverändert.

**Eigene Fehlannahme, durch die Messung widerlegt:** ich hatte notiert, die
Wortliste und die Versuchsgrenze müssten zusammen ausgeliefert werden, sonst
werde aus dem falschen Ausstieg eine Endlosschleife. Falsch — die Eskalation
greift VOR dem Floskel-Zug, der Frame allein genügt.

**Zwei Messfehler auf meiner Seite, beide korrigiert:** die erste Fassung der
Frist-Messung nutzte „Erstell mir **noch** ein Quiz" (verweist ausdrücklich
zurück), und der erste Nachher-Lauf benutzte dieselben Sitzungs-IDs wie der
Vorher-Lauf — `thema='such du was aus'` stand dadurch schon in Zug 1 in der
Datenbank. Beide Male neu gemessen, erst dann gewertet.

**Restdefekt, nicht behoben, Bestandsschuld:** sagt der Nutzer „such du was
aus", wird die Floskel weiterhin zum `thema` und das erzeugte Dokument handelt
von etwas anderem („Arbeitsblatt zum Thema *such du was aus*" über
„Prozentrechnen im Alltag"). Wurzel gemessen: der Platzhalter-Filter in
`merge.py` vergleicht die **ganze getrimmte Zeichenkette auf Gleichheit** gegen
`placeholder-topics.yaml`; „egal", „weiss nicht", „such du was aus" stehen dort
nicht. Das ist **Studio-pflegbare Config**, kein Code — bewusst dem Redakteur
überlassen. Eine Wortliste deckt ohnehin nur die gemessenen Formulierungen.

**Bewusst nicht gebaut** (`simplify:` im Modul): Eigentümer-Feld und Frist. Für
beide ist kein Defekt messbar; Aufstiegspfad ist ein Feld in
`note_clarification`.

**Hinweis:** `route.py` steht jetzt bei **296 Zeilen** — knapp unter der
300er-Schwelle. Der nächste Eingriff dort sollte zuerst schneiden.

### Paket C — Auth-Naht und Betriebsarten

- **C0** Messen: welche Aufrufpfade `call_mcp_tool` erreichen.
- **C1** `httpx_client_factory`-Naht in `transport.py` (nicht `headers=`).
- **C2** Einstellung `MCP_AUTH_TOKEN` als Geheimnis — **nie loggen, nie
  ausgeben**, nicht in Fehlermeldungen.
- **C3** Betriebsart-Erkennung: Token gesetzt → Kurationswerkzeuge im Katalog;
  nicht gesetzt → nur lesend. Muss im Zug **unterscheidbar** sein.
- **C4** Anmelde-Pattern: Schreibabsicht ohne Token → Verweis auf die
  `/auth`-Seite des MCP-Servers. Wir bauen kein OAuth.

#### ✅ C0–C3 erledigt 2026-08-10 · C4 bewusst nach E verschoben

Belege: `pytest -q` → **2622 passed, 4 skipped** (2606 vorher + 16 neue) ·
`ruff check .` → All checks passed · `export_openapi.py --check` → openapi
contract unchanged. Rot-grün geprüft: ohne die Verdrahtung fallen 4, ohne das
Auspacken 3 Tests, jeder aus dem richtigen Grund.

**C0 — die Messung ist die gute Nachricht.** ~25 Aufrufstellen erreichen
`call_mcp_tool`, aber alle laufen über **eine** Naht: `_open_session`
(`transport.py:70`) — `call_tool` wie `discover_server_tools`. Der Modul-Docstring
benannte `httpx_client_factory` bereits als Aufstiegspfad. Zwei Dinge nachgesehen
statt angenommen: die SDK-Signatur führt `httpx_client_factory` wirklich (Default
`create_mcp_http_client`), und **`create_mcp_http_client` ist aus demselben
öffentlichen Modul re-exportiert** wie `streamablehttp_client` — kein Import aus
`mcp.shared._httpx_utils`.

**C1/C2/C3 gebaut.** Neu `services/mcp/auth.py` (84 Z.): `has_auth_token` ·
`auth_mode` · `build_http_client_factory`. Ohne Block ist die Fabrik die
SDK-Standardfabrik, unverändert. `mcp_auth_token: SecretStr` in den
Einstellungen (Projektkonvention: Geheimnisse sind `SecretStr` und tauchen nicht
im `repr` auf). Betriebsart in `/api/health` als `mcp_auth: service|anonymous` —
das Feld ist die einzige Möglichkeit für einen Betreiber zu prüfen, **ob sein
Block greift, ohne ihn auszugeben**. Kein Vertragsbruch: `/api/health` gibt ein
reines `dict` zurück, das Schema ist unverändert.

**Live gegen den echten Server, beide Richtungen:**

| Fall | Erwartung laut Server-Doku | Gemessen |
|---|---|---|
| kein Block | `200`, volle Werkzeugliste | ✅ M06-Zug, 4 Werkzeuge, 4 Karten, echte Antwort |
| unbrauchbarer Block | `401` (nur bei *vorgelegtem* Token) | ✅ `401 Unauthorized` |

Damit ist belegt, dass die Kopfzeile den Server **wirklich erreicht** — ein
grüner Einheitstest allein hätte das nicht gezeigt.

**Der Nebenfund aus dem Live-Lauf, selbst verursacht und deshalb hier behoben.**
Das SDK bündelt Fehler in einer `ExceptionGroup`, deren `str()` nur „unhandled
errors in a TaskGroup (1 sub-exception)" lautet — der `401` steckte in der
Unterausnahme und war für einen Betreiber unsichtbar. Vor C1 konnte ein Aufruf
gar nicht an der Anmeldung scheitern; **erst diese Änderung macht den Fall
möglich**, also gehört die lesbare Ursache dazu. Neu `_cause_text` in
`transport.py`, packt Gruppen rekursiv aus; gewöhnliche Ausnahmen bleiben
wortgleich `str(exc)` (Bestandsverhalten, die Bestandstests prüfen auf
Teilstring). Live nachgemessen: `401` sichtbar, Block **nicht** in der Meldung.

**Dokumentation mitgezogen** (nicht „später"): `deploy/README.md` bekommt einen
eigenen Abschnitt — Geheimnis-Handhabung wie `STUDIO_API_KEY`, Block einmal auf
der `/auth`-Seite des MCP holen, Betriebsart-Tabelle, und der Prüfbefehl
`curl /api/health` samt Feld `mcp_auth`. `compose.prod.yml` reicht
`MCP_AUTH_TOKEN` durch.

**C4 bewusst NICHT gebaut, und zwar aus einem Sachgrund, nicht aus
Bequemlichkeit:** ein Anmelde-Hinweis („melde dich an, dann kann ich das")
verspricht eine Fähigkeit, die es auch MIT Block noch nicht gibt — die 14
kuratierenden Werkzeuge stehen weder im Katalog noch in einem Muster (Paket A
hat sie bewusst nur in die Registry gelegt). Der Hinweis wäre heute ein
Versprechen, das das System direkt danach bricht. C4 gehört deshalb in **Paket
E**, wo der Schreibpfad entsteht.

### Paket D — Skills

- **D0** Messen: ob im Bestand überhaupt Inhalte der Art `ai_prompt` liegen.
- **D1** `search_skill` + `get_skill` in Registry und Katalog.
- **D2** Pattern-Zuordnung nach Nutzer-Vorgabe: Kuratierung, Alltagsarbeit,
  Qualitätssicherung — je mit Hinweis im Pattern, wann eine Anleitung hilft.
- **D3** `/skillname` als deterministischer Auslöser in `preflight.py`.
- **D4** **Vertrauensgrenze:** geladenes Markdown ist hochgeladener Fremdinhalt
  aus dem Repositorium — indirekte Prompt-Injection. Der Server rahmt es bereits
  als „zu prüfende Vorschläge"; unsere Seite darf diese Rahmung nicht verlieren.

#### D0 erledigt 2026-08-10 — der Blocker ist weg, aber das Regal ist leer

Zwei Messungen über den eigenen Transport, nicht aus dem Quelltext geschlossen.

**Der Server ist jetzt vollständig deployt.** `discover_server_tools` meldet
**41** Werkzeuge (vorher 38): `search_skill`, `get_skill` und
`wlo_set_topic_page` sind live. `get_skill_for_task` fehlt erwartungsgemäß —
der Alternativmodus `WLO_SKILL_TOOL_MODE=one-tool` ist aus. Damit ist die in
§1.0 notierte Sperre für D und für den Themenseiten-Schreibpfad aufgehoben.

**Es gibt keinen einzigen Skill.** Fünf Proben gegen den echten Server, alle
leer: Katalog-Auflistung ohne `query`, zwei Suchen (`Stunde planen`,
`Vertretungsstunde`), eine Fachfilterung (`discipline: Physik`) und die
JSON-Form. Letztere ist der Beleg, dass nicht etwa still ein Filter verworfen
wurde: `{"query":null,"skills":[],"unresolved":[]}`. `wlo_auth_status`
bestätigt „Zugriff ohne Anmeldung" — ob ein Dienstkonto mehr sähe, ist offen,
aber die anonyme Sicht ist die des Chatbots.

**Folge für den Schnitt:** D1–D3 würden dem Modell ein Werkzeug anbieten, das
heute nur „Keine Skills gefunden." antworten kann — dieselbe Klasse von
Versprechen, aus der C4 nach E verschoben wurde. Der Katalog ist per Definition
„was das Modell überhaupt sehen kann"; ein Eintrag dort kostet Prompt-Platz in
jedem Zug und lädt zu einem Zug ein, der garantiert leer ausgeht (MCP-Aufrufe
dominieren die gemessene Latenz mit 1,2–23,3 s). D2 („wann hilft eine
Anleitung") würde das Modell aktiv dorthin lenken, D3 gäbe dem Nutzer einen
`/skillname`-Auslöser ins Leere. **Entscheidung liegt beim Nutzer** — sie hängt
an Redaktionsarbeit, nicht an Code. Registry-Hälfte von D1 ist bereits erledigt
(Paket A trug beide Namen ein), es fehlt allein der Katalog-Eintrag.

#### ✅ D4 erledigt 2026-08-10 — vorgezogen, weil die Lücke älter ist als die Skills

D4 war im Plan als Epilog notiert. Die Messung dreht das um: die Lücke besteht
**heute im Betrieb** und trifft nicht nur Skills.

**Befund, gemessen am Tool-Loop:** *jedes* MCP-Ergebnis geht wortgleich (auf
4000 Zeichen gekappt) als `role=tool`-Nachricht in die Kette — die eine
`messages.append`-Stelle in `_run_tool_loop`, durch die alle Werkzeuge laufen.
Keine Rahmung. `get_wlo_content_text` steht seit M17 im Katalog und liefert den
Volltext eines beliebigen hochgeladenen Arbeitsblatts. Die Guardrails sagen
sogar das Gegenteil: R-05 („Keine Erfindung. Nur MCP-/RAG-belegte Inhalte.")
erhöht das Vertrauen in genau diesen Text. Der MCP-Server kennzeichnet den Fall
in seiner eigenen Werkzeug-Beschreibung — **unsere Seite verlor die
Kennzeichnung beim Einsetzen.**

Gebaut: `domain/untrusted_text.py` (59 Z., rein) mit `FREE_TEXT_TOOLS` +
`frame_untrusted`, verdrahtet an derselben einen Naht. Zwei Werkzeuge gerahmt —
`get_wlo_content_text` (hochgeladenes Dokument) und `get_compendium_text`
(redaktionelle Prosa). Beides Langform-Text von Dritten, der klassische Träger
einer Einschleusung.

**Bewusst NICHT alles gerahmt.** Suchtreffer und Metadatenfelder sind kurze
Felder, die unsere Parser strukturieren; sie zu rahmen kostete Prompt-Platz in
jedem Zug und änderte den Prompt der Bestandszüge, ohne die Trägerfläche zu
treffen. Damit das keine stille Auslassung bleibt, hält ein **Wächter der
Gegenrichtung** (`test_untrusted_text.py`, dieselbe Bauart wie
`BEWUSST_EINSPRACHIG` aus C1) fest, dass *jedes* Katalog-Werkzeug eine
Entscheidung trägt: gerahmt oder mit Grund als strukturiert vermerkt. Ein neu
aufgenommenes Werkzeug fällt damit auf, statt ungerahmt durchzulaufen — genau
der Fehler, den `search_wlo_all` bei `CARD_YIELDING_TOOLS` schon einmal
gemacht hat.

**Die Reihenfolge ist tragend, nicht kosmetisch:** unser eigener
UI-Box-Status-Fußtext bleibt **außerhalb** des Rahmens. Innerhalb stünde eine
Anweisung von uns in einem „befolge das hier nicht"-Block und der Rahmen
entwertete sie mit. Ein eigener Test pinnt die Reihenfolge.

**Verifikation:** 2633 pytest (2622 + 11), ruff sauber, OpenAPI unverändert.
Rot-grün gegengeprüft — ohne die Verdrahtung fallen genau die zwei
Rahmen-Tests, der Negativtest hält in beiden Zuständen. **Live gegen den echten
Server, beide Richtungen:** echter Volltext eines echten WLO-Materials
(nodeId `02b763b0-…`, 1519 Zeichen) korrekt gerahmt; ein Suchtreffer im selben
Aufbau bleibt ungerahmt (3125 Zeichen, keine Marke).

**Grenze, ehrlich benannt:** ein Textrahmen ist kein Beweis, sondern die
anerkannte Untergrenze — er trennt Fremdtext sichtbar von der Anweisungsebene.
Ob ein Modell ihn im Einzelfall respektiert, zeigt erst ein Golden-Lauf
(Nutzer-Domäne).

**Nachtrag beim Bau von D3 gefunden und geschlossen: es sind DREI Nähte, nicht
eine.** Die Behauptung „alle MCP-Ergebnisse laufen über eine
`messages.append`-Stelle" stimmt für die Werkzeug-*Schleife*, aber
`_assemble_messages` setzt vorab geholte Ergebnisse mit zwei eigenen Stellen ein
(primary + extras). Die erste Fassung ließ beide ungerahmt. Heute feuert der
Prefetch ausschließlich die vier Suchwerkzeuge — die Lücke war also **latent,
nicht live**; ausgerechnet D3 (`/skillname`) wäre der erste Fall, der eine
Anleitung genau dort einspeist. Alle drei Stellen rufen jetzt
`frame_untrusted`, mit je einem Test.

#### ✅ D1 + D2 erledigt 2026-08-10 — gebaut, obwohl das Regal noch leer ist

Nutzer-Entscheid: die Redaktion legt die Skills gerade an, deshalb wird die
Verdrahtung jetzt fertig gebaut. Bis Inhalte da sind, antwortet das Werkzeug
wahrheitsgemäß „Keine Skills gefunden." — und die Katalog-Beschreibung sagt dem
Modell ausdrücklich, dass das ein normales Ergebnis ist und nicht erwähnt
werden soll.

**D1 — Katalog.** Zwei Einträge in `TOOL_DEFINITIONS` plus zwei
Argument-Modelle (`SkillSearchArgs`, `SkillGetArgs`). Die Grenzen sind aus dem
**Live-Schema** des Servers geholt (`tools/list`), nicht geraten — `maxResults`
1..25. Das ist nicht kosmetisch: `validate_tool_args` reicht Argumente
**ungeprüft** durch, solange kein Modell registriert ist; ohne Modell ginge eine
vom Modell erfundene `maxResults: 500` roh an den Server. Registry-Hälfte war
schon da (Paket A). `get_skill` ist zusätzlich in `FREE_TEXT_TOOLS` — es
liefert genau das hochgeladene Markdown, für das D4 geschrieben wurde.

**D2 — Muster.** `search_skill` + `get_skill` in **M09** (Lernpfad /
Stundenplanung) und **M10** (Arbeitsblatt / Quiz / Prüfung). Das sind die
beiden Fälle, für die die Server-Doku selbst wirbt („Stunde planen",
„Vertretungsstunde", „Prüfung erstellen").

**Abweichung von der Plan-Vorgabe, offen benannt:** der Plan nannte
*Kuratierung, Alltagsarbeit, Qualitätssicherung*. Gemessen am tatsächlichen
Musterbestand gibt es dafür keine Entsprechung — M09/M10 sind die
Alltagsarbeit; echte Kuratierung entsteht erst in Paket E, und ein
QS-Muster existiert gar nicht. Statt die Labels auf unpassende Muster zu
biegen, ist zugeordnet, was belegbar passt.

**Der Fund bei M10 ist der eigentliche Ertrag.** M10 hatte **keinen**
`tools`-Schlüssel und bekam deshalb über den `else`-Zweig von
`_select_active_tools` die Rückfall-Werkzeuge `search_wlo_collections` +
`search_wlo_topic_pages`. Eine `tools`-Liste **ersetzt** diesen Zweig — ein
naives „zwei Namen eintragen" hätte M10 die beiden still weggenommen. Sie sind
deshalb ausgeschrieben, mit Begründung im Seed. Ein Regressionstest hält es
fest (er war schon **vor** der Änderung grün und ist genau deshalb der richtige
Wächter).

**Nebenbefund, bewusst NICHT angefasst (Fremdbereich):** neun der siebzehn
Muster haben keinen `tools`-Schlüssel und bekommen dieselben zwei
Rückfall-Werkzeuge — darunter **M15**, dessen eigene `forbidden_phrases`
MCP-Aufrufe ausdrücklich verbieten. Der Kommentar in
`response_tool_selection.py:83` behauptet „Pattern explicitly set tools=[] →
NO tools (e.g. M15)", aber **kein einziges Muster im Seed hat `tools: []`** —
der Zweig ist toter Code, und M15 bekommt Suchwerkzeuge, die es nicht haben
will. Gehört nach Paket F, nicht in die Skill-Anbindung.

**Verifikation:** 2649 pytest (2633 + 16), ruff sauber, OpenAPI unverändert.
Rot-grün: 11 der 13 D1/D2-Tests fielen vorher; die zwei, die schon grün waren,
sind die Regressionswächter.

#### D3 zurückgestellt 2026-08-10 (Nutzer-Entscheid: „lass das erstmal weg")

Der Slash-Befehl ist **kein Zugang, sondern eine Bequemlichkeit**: M09 und M10
bieten dem Modell beide Skill-Werkzeuge bereits an, Skills wirken also auch
ohne ihn. Was beim Messen für D3 klar wurde und beim Wiederaufnehmen gilt:

- `preflight.py` dispatcht heute ausschließlich auf `req.action` (strukturiert,
  vom Widget gesetzt). Ein getipptes `/name` kommt als gewöhnliche Nachricht an
  — D3 bräuchte dort einen **neuen Auslösertyp**, keinen weiteren Eintrag in
  `_DIRECT_ACTIONS`. Das Widget kennt keine Slash-Befehle.
- Die vorhandene Naht für „deterministisch geholtes MCP-Ergebnis in den Zug"
  ist `prefetched_tool` (aufgelöst in `respond.py`, eingesetzt in
  `_assemble_messages`). Sie ist seit dem D4-Nachtrag gerahmt — der Weg steht
  also offen.
- **Die eigentliche Frage ist eine Produktfrage, keine technische:** wendet
  `/name` die Anleitung an (Text geht ins Modell) oder zeigt es sie an (Text
  geht an den Menschen, wie M17 den Volltext)? Die beiden unterscheiden sich in
  Aufwand *und* in der Vertrauensgrenze. Vor dem Bau zu entscheiden.

### Paket E — Kuration (braucht B und C)

Die zweistufige Bestätigung (Vorschau → `confirmToken` → Ausführung) überspannt
Züge. Genau dafür ist der Frame aus B da; ein zweiter Mechanismus wäre
Verdopplung.

- 14 Werkzeuge im Katalog, nur in der Dienst-Betriebsart.
- Token an den Fingerabdruck der Änderungsmenge gebunden, 10 Minuten.
- Abbruch ist **offener Ausgang**, nie Fehlschlag — der Abbruch trifft die
  Antwort, nicht die Arbeit.
- **Sonderfall:** `wlo_set_topic_page` ist das einzige Werkzeug, dessen Ergebnis
  sofort öffentlich sichtbar ist.

#### E0 erledigt 2026-08-10 — die Messung dreht das Paket um

Drei der vier Punkte oben beschreiben Arbeit, die **der Server bereits tut** —
einer davon im wörtlich selben Satz. Und der eine Punkt, den wir wirklich bauen
müssen, steht nicht in der Liste.

| Plan-Punkt | Befund |
|---|---|
| „Token an den Fingerabdruck der Änderungsmenge gebunden, 10 Minuten" | **Der Server.** `services/write/confirm.ts`: `mintToken`/`consumeToken`, SHA-256 über den sortierten ChangeSet, `TOKEN_TTL_MS = 10 * 60 * 1000`, Einmalgebrauch — auch ein `mismatch` verbraucht den Schlüssel |
| „Abbruch ist offener Ausgang, nie Fehlschlag — der Abbruch trifft die Antwort, nicht die Arbeit" | **Der Server**, wortgleich: `timeoutOrError` in `curation-shared.ts`, mit derselben Begründung (ein abgebrochenes `create` hatte den Datensatz schon erzeugt, gemessen 2026-08-02) |
| „Sonderfall `wlo_set_topic_page`" | Steht. Live vorhanden |
| „Die zweistufige Bestätigung überspannt Züge — genau dafür ist der Frame aus B da" | Richtige Absicht, **falsche Begründung**. Sie überspannt Züge nicht, weil wir sie bauen, sondern weil sonst niemand dazwischen steht |

**Live gemessen** gegen `MCP_SERVER_URL` (41 Werkzeuge, 16 mit `wlo_`-Präfix):
14 kuratierende, davon **13 mit `confirmToken`** — `wlo_list_suggestions` hat
keinen, es liest nur. Alle 14 Eingabeschemata abgeholt statt abgetippt.

**Der eigentliche Befund: die zweistufige Bestätigung schützt uns heute nicht.**

Der Schlüssel ist an den Fingerabdruck der Änderung gebunden. Das verhindert,
dass eine genehmigte Änderung gegen eine andere eingetauscht wird — der
Server-Docstring nennt genau diesen Angriff. Was es **nicht** verhindert: dass
*derselbe Aufrufer beide Schritte macht*. Der Server nimmt an, zwischen Vorschau
und Bestätigung stehe ein Mensch. Bei einem Chat-Client mit Werkzeugschleife
steht dort niemand.

Zwei Messungen, die zusammen die Klemme aufmachen:

1. **In einem Zug ginge es.** `_run_tool_loop` läuft `for iteration in
   range(5)`. Iteration 1 holt die Vorschau — der Text mit dem Schlüssel landet
   als `role=tool` in der Kette —, Iteration 2 bestätigt damit. Der Nutzer sähe
   nur das Ergebnis, nie die Vorschau.
2. **Über Züge hinweg ginge es gar nicht.** `save_message` schreibt ausschließ­
   lich `user`/`assistant`; `_assemble_messages` speist `history[-10:]` ein.
   Werkzeug-Nachrichten überleben den Zug **nicht**. In Zug N+1 kennt das Modell
   den Schlüssel also nicht mehr.

Zusammen: der einzige Weg, auf dem die Bestätigung heute überhaupt funktionieren
könnte, ist genau der, der den Menschen ausschließt. Deshalb ist der Wall keine
Härtung, die man später nachzieht — ohne ihn ist die Zweistufigkeit Dekoration.

**Schnitt daraus — drei Scheiben, Reihenfolge nicht beliebig:**

- **E1 Bestätigungs-Wall + Träger.** Zuerst und **ohne ein einziges Werkzeug im
  Katalog**: der Mechanismus wird vollständig gebaut und geprüft, bevor ihn
  jemand auslösen kann. Damit ändert E1 für keinen Nutzer etwas — dieselbe
  Reihenfolge wie in Paket D, wo D4 die Vertrauensgrenze vor D1/D2 zog.
  *Leitentscheidung: das Modell bekommt den Schlüssel nie zu sehen und kann ihn
  nie selbst setzen.* Wir entfernen einen vom Modell mitgeschickten
  `confirmToken`, schneiden den Schlüssel aus dem Vorschautext heraus, bevor er
  in die Nachrichtenkette geht, und legen ihn in den Sitzungszustand
  (`_`-Konvention aus B). Eingesetzt wird er nur von uns, nur für denselben
  Aufruf — und **nur in einem späteren Zug**. Diese eine Zeile ist der Wall: der
  Zugwechsel *ist* der Mensch.
- **E2 Katalog.** Die 14 Definitionen + Argumentmodelle + Betriebsart-Gate
  (`auth_mode() == "service"`), gestützt auf den geprüften Wall.
- **E3 = C4.** Der Anmelde-Hinweis, jetzt ehrlich, weil E2 die Fähigkeit
  wirklich mitbringt.

**Was hier nicht gebaut wird, mit Grund:** kein eigener Bestätigungs-Frame
(wäre der zweite Mechanismus, vor dem der Plan selbst warnt), kein
Aktions-Chip in der Antwort (`ChatResponse.quick_replies` ist `list[str]` —
Aktions-Chips wären ein Eingriff in den eingefrorenen Vertrag), keine
Ja-Erkennung per Regex (die Zustimmung beurteilt das Modell, das den Verlauf
sieht; der Wall hängt nicht daran, sondern am Zugwechsel).

**Bekannte Grenze dieser Umgebung:** hier ist kein Zugangsblock hinterlegt
(`auth_mode() == "anonymous"`), ein echter Schreibvorgang ist von hier aus also
nicht auslösbar. Was live prüfbar ist: die Verweigerung samt Anmelde-Hinweis.
Der erste echte Schreibvorgang gehört in die Hand des Nutzers.

#### ✅ E1 erledigt 2026-08-10 — der Wall steht, bevor ihn jemand auslösen kann

Belege: `pytest -q` → **2675 passed, 4 skipped** (2649 vorher + 26 neue) ·
`ruff check .` → All checks passed · `export_openapi.py --check` → openapi
contract unchanged. Neu: `domain/write_confirm.py` + `tests/test_write_confirm.py`;
geändert nur `services/tool_loop.py` (Import + drei Blöcke). **Kein Werkzeug im
Katalog** — für keinen Nutzer ändert sich damit etwas, und der Mechanismus ist
trotzdem vollständig geprüft.

**Der Wall in einem Satz:** das Modell darf einen `confirmToken` weder setzen
noch sehen, und eingesetzt wird er nur von uns, nur für dasselbe Vorhaben, nur
in einem *späteren* Zug.

Die Zeitgrenze ist ein Schnappschuss: `_run_tool_loop` liest den offenen Vorgang
**beim Eintritt** in den Zug. Eine Vorschau, die weiter unten in diesem Zug
entsteht, landet in `session_state` — aber nicht mehr im Schnappschuss. Sie ist
damit erst im nächsten Zug bestätigbar, und zwischen zwei Zügen steht der
Mensch. Getragen wird das von einer nachgesehenen Tatsache: `_run_tool_loop` hat
**genau eine** Aufrufstelle (`services/generate.py:153`), wird also einmal pro
Zug betreten.

**Rot-grün, wo es zählt.** Vier der sieben Naht-Tests fielen ohne die Änderung.
Die drei anderen waren schon vorher grün — darunter ausgerechnet
`test_kein_schluessel_im_selben_zug`, *der* Wall-Test. Ein Test, der mit und
ohne Änderung grün ist, beweist nichts (dieselbe Falle wie bei C1-f2b1).
Deshalb gegengeprüft: den Schnappschuss versuchsweise durch einen Live-Zugriff
auf `session_state` ersetzt → der Test fällt. Das ist zugleich die Vorführung
des Angriffs: mit Live-Zugriff bestätigt das Modell im selben Zug, ohne dass
ein Mensch die Vorschau gesehen hätte.

**Welche Hälfte trägt.** Das Entfernen auf dem **Hinweg** ist die Zusicherung —
was das Modell nicht absetzen kann, kann es nicht auslösen, unabhängig davon,
was es gesehen hat. Das Herausschneiden auf dem **Rückweg** ist
Tiefenstaffelung (hält den Schlüssel aus Nachrichtenkette und Protokoll).
Änderte der Server seinen Vorschautext, wäre die Folge deshalb **kein Loch,
sondern ein Ausfall**: es ließe sich nichts mehr bestätigen. Die Naht
protokolliert genau diesen Fall (Feldname genannt, kein Schlüssel lesbar),
damit er nicht still bleibt.

**Live gegen den echten Server** (anonym, also ohne Schreibrecht):
`wlo_create_collection` ist erreichbar und **verweigert** mit
`isError: True` und einem deutschen Anmelde-Satz. Der Wall lässt diesen Text
wortgleich durch (kein Schlüssel, keine Ersetzung). Zwei Erträge daraus: der
Betriebsart-Pfad aus C stimmt bis zum Werkzeug durch — und **C4 braucht keinen
selbstgeschriebenen Hinweis**, der Server liefert ihn schon. E3 hat damit vor
allem eine Aufgabe: ihn nicht zu verschlucken.

**Ehrliche Grenze:** die *Vorschau*-Form ist aus dem Quelltext des
Referenz-Servers (`previewReply` in `curation-shared.ts`) übernommen, nicht aus
einer echten Antwort — anonym gibt es keine Vorschau. Ein abweichend deployter
Server wäre also möglich; die Folge wäre der oben beschriebene Ausfall, kein
Loch. Auffallen würde er über das Protokoll und beim ersten echten
Schreibvorgang des Nutzers.

**Ein Fehler aus der Selbstdurchsicht, gefunden bevor er lief.** Die Warnung für
den Drift-Fall prüfte zuerst auf das Wort `confirmToken` — und wäre damit bei
**jedem abgelaufenen Schlüssel falsch angeschlagen**: die drei Absagen des
Servers (abgelaufen / andere Änderung / unbekannt) nennen das Feld ebenfalls,
nämlich als „bitte den Aufruf **ohne** confirmToken wiederholen". Der
Unterschied ist der Doppelpunkt: nur die Vorschau schreibt
„mit confirmToken: ‹schlüssel›". Beide Fälle sind jetzt gepinnt, und auch dieser
Test wurde gegengeprüft — ohne den Doppelpunkt fällt er.

#### ✅ E2 erledigt 2026-08-10 — die 14 im Katalog, hinter dem Betriebsart-Gate

Belege: `pytest -q` → **2691 passed, 4 skipped** · `ruff check .` → All checks
passed · `export_openapi.py --check` → openapi contract unchanged. Neu:
`api/schemas_mcp_curation.py` (169 Z.), `services/mcp/tool_defs_curation.py`
(322 Z.), `tests/test_curation_tools.py`; geändert: die Fassade
`api/schemas.py`, das Modell-Mapping in `tool_defs.py`, und **eine** Zeile in
`response_tool_selection.py`.

**Das Gate sitzt an genau einer Stelle** — dem namentlichen Zweig von
`_select_active_tools`. Neu `_nameable_tools()`: der Lesekatalog immer, die
kuratierenden nur mit hinterlegtem Zugangsblock. Bewusst **nicht** im
`has_mcp_source`-Zweig, der `TOOL_DEFINITIONS` als Ganzes weiterreicht — stünden
die schreibenden darin, bekäme sie jedes Muster mit `sources: [mcp]`, also auch
die reinen Suchmuster. **Kuratieren muss ein Muster ausdrücklich nennen.**

**Zwei Auslassungen im Schema, beide Absicht:** `confirmToken` fehlt (kommt nur
von uns, E1 — angeboten würde er zum Erfinden einladen), `outputFormat` fehlt
(die Werkzeuge führen es gar nicht; sie antworten in Prosa, und genau davon lebt
die Vorschau).

**Live gegen den echten Server abgeglichen — 0 Abweichungen:** kein erfundener
Feldname, Pflichtfelder deckungsgleich, kein Werkzeug fehlt. Das ist die Probe,
die kein Einheitstest leisten kann; ein Tippfehler in einem Property-Namen wäre
sonst erst beim ersten echten Schreibvorgang aufgefallen.

**Ein echter Defekt aus dem Rot-Grün, älter als dieses Paket.** Zwei fremde
Tests kippten — aber nur im Verbund, einzeln liefen sie. Ursache: der
`has_mcp_source`-Zweig wies `TOOL_DEFINITIONS` per **Referenz** zu, und das
spätere `active_tools.append(...)` schrieb damit in die Modul-Globale. Gemessen:
über fünf Aufrufe wuchs der Katalog **22 → 27**, das Modell bekam
`select_top_cards` fünfmal angeboten — im Betrieb ein Eintrag pro Zug,
**unbegrenzt**. Der Modulkopf führte das seit dem Port als `simplify:`-Vermerk
mit der Bitte um Freigabe; `test_response_tool_selection.py` hatte sich lokal
mit einem autouse-Netz dagegen geschützt, das den Fall zugleich unsichtbar
hielt. Behoben (`list(TOOL_DEFINITIONS)`, Rückgabewert unverändert), gepinnt von
`test_mcp_source_waechst_den_katalog_nicht`, rot-grün geprüft.

**Zweiter Fund, aus meinem eigenen Modell:** optionale Felder als `None` zu
führen war falsch. `_export_non_empty` entfernt nur leere Strings, ein `None`
reiste als JSON-`null` weiter — und der Server führt seine optionalen Felder als
„weglassen", nicht als „null". Betroffen waren `contentFormat`, `status`
(Leerstring statt `None`) und, eine Ebene tiefer, `confidence` in jedem
Metadaten-Vorschlag: dort räumt `_export_non_empty` gar nicht auf, weshalb
`MetadataSuggestArgs` einen eigenen `field_serializer` bekam. Ohne ihn wäre
**jeder Vorschlag ohne ausdrückliche Sicherheit gescheitert** — also der
Regelfall.

**Bewusst kein Muster angefasst.** Kein Seed-Muster nennt die neuen Werkzeuge,
sie sind also noch nicht auslösbar. Naheliegend wäre M13 („Einreichen/Melden")
gewesen — aber M13 ist ein **Routing**-Muster: es verbietet Tool-Aufrufe in
seinen `forbidden_phrases` und reicht einen Formular-Link weiter. Es umzubauen
wäre eine Musteränderung, verkleidet als Werkzeug-Ergänzung — genau das, was der
F-neu-Eintrag unten benennt. Die Wahl des kuratierenden Musters gehört nach
Paket F.

#### ✅ E3 (= C4) erledigt 2026-08-10 — aber an eine andere Adresse als geplant

Belege: `pytest -q` → **2703 passed, 4 skipped** · `ruff check .` → All checks
passed · `export_openapi.py --check` → openapi contract unchanged. Neu:
`tests/test_curation_auth_hint.py`; geändert: ein Textbaustein in
`response_prompt_tools_text.py`, ein Prädikat + ein Protokolleintrag in
`response_tool_selection.py`, eine Bedingung in `response_prompt_builder.py`.

**Der Fall, den es zu schließen galt, steckte in E2 selbst.** Gemessen: nennt
ein Muster `wlo_create_collection` und ist kein Zugangsblock hinterlegt, fällt
das Werkzeug **spurlos** aus der Liste — kein Protokolleintrag, kein Hinweis ans
Modell (`Muster wollte: wlo_create_collection + search_wlo_content` →
`Modell bekommt: ['search_wlo_content', …]`). Das Muster verspricht dann etwas,
wovon der Rest des Zuges nichts weiß.

**Abweichung vom Plan, mit Messung begründet.** C4 wollte einen „Verweis auf die
`/auth`-Seite" in die Antwort. Das zielt auf die falsche Zielgruppe: der Block
ist ein **Server-Geheimnis**, das der Betreiber einmal in die `.env` setzt
(`deploy/README.md` Z. 125–137). Eine Lehrkraft im Chat hat weder Serverzugriff
noch Nutzen davon — und sie auf eine Seite zu schicken, die einen Schreib-Zugang
ausgibt, wäre schlechte Hygiene. Deshalb **zwei getrennte Empfänger**:

| Empfänger | Was er bekommt | Wo |
|---|---|---|
| Modell | „Du kannst nichts anlegen/ändern/löschen — sag das offen, behaupte nichts anderes, biete an was geht." **Ohne Adresse.** | Prompt-Block, nur in diesem Fall angehängt |
| Betreiber | Warnung mit dem Muster, den fehlenden Werkzeugen und dem Namen `MCP_AUTH_TOKEN` | Protokoll, an der Stelle des Verlusts |

Der Prompt **jedes anderen Zuges bleibt bytegleich** — der Block kostet nur dort
Platz, wo er etwas erklärt. Beide Hälften rot-grün gegengeprüft: Verdrahtung und
Protokolleintrag versuchsweise ausgehängt, beide zugehörigen Tests fallen.

`/auth` selbst wurde live geprüft (`HTTP 200`) und steht dort, wo es hingehört —
in der Betriebsdoku, nicht im Chat.

**Damit ist Paket E zu.** Offen bleibt bewusst nur, welches Muster die
kuratierenden Werkzeuge anbietet — eine Produktentscheidung für Paket F.

**Nicht angefasst, mit Grund:** `tool_loop.py` steht bei 1105 Zeilen und damit
weit über der 300er-Marke. Das ist ein Verbatim-Port aus ALT und ein bekannter
Posten; ihn im Zuge einer Sicherheitsänderung zu zerlegen würde genau die
Vermischung erzeugen, die ein Review unmöglich macht. Gehört nach F, nicht
hierher.

### Paket F — Pattern-Überarbeitung

- **F0** Seed-Baum sichern (Rückfallweg, Nutzer-Auflage).
- **F1…** Übernahme aus dem Ideen-Dokument, Stück für Stück. Was übernommen
  wird, wird bei Paket-Beginn gegen den dann erreichten Stand entschieden — nach
  B, D und E sieht die Lage anders aus als heute.
#### ✅ F0 erledigt 2026-08-10 — Rückfallweg steht

`backups/seeds-2026-08-10-vor-paket-f/`, 56 Dateien, `diff -r` gegen
`backend/seeds/` ohne Abweichung. Bewusst ein Verzeichnis und kein Zip: nach
den Musteränderungen zeigt `diff -r` unmittelbar, was F angefasst hat.
`backups/` in `.gitignore` **und** `.dockerignore` — es gehört nicht ins Image
und würde bei jeder neuen Sicherung den Layer-Cache brechen.

#### ✅ F-neu erledigt 2026-08-10 — die Messung dreht den Befund um

**Die Behauptung oben (aus D2) ist falsch, und zwar in beide Richtungen.** Sie
entstand durch Auszählen der YAML-Frontmatter. Im Betrieb baut aber
`phase3_modulate` das `pattern_output`, und das schreibt
`"tools": list(pattern.tools)` **bedingungslos** — `PatternDef.tools` hat
`default_factory=list`. Der Schlüssel ist damit IMMER da.

Gemessen an derselben Muster-Definition (`sources: [mcp]`, kein `tools:`):

| Weg | aktive Werkzeuge |
|---|---|
| über `phase3_modulate` (Betrieb) | **0** |
| als handgebautes Dict (Bestandstests) | **23** (ganzer Katalog) |

Daraus:

1. **Kein Muster bekommt still Such-Werkzeuge.** Der Rückfall-Zweig ist
   unerreichbar; M15 kann seine eigene Regel „KEIN MCP-Tool aufrufen" gar nicht
   verletzen. Die Sorge war gegenstandslos.
2. **Der `tools: []`-Zweig ist nicht tot, sondern der lebende** — er trägt
   8 der 17 Muster (M01–M04, M11, M13–M15), und für alle acht ist das richtig:
   sie verbieten Tool-Calls in ihren eigenen Regeln. Falsch war nur der
   Kommentar „Pattern explicitly set tools=[]": die acht kommen durch
   **Weglassen** dorthin, nicht durch eine Eintragung.
3. **Unerreichbar sind statt dessen `has_mcp_source` und der Rückfall.** Beide
   bleiben stehen (ALT-Verbatim, sie halten fest was gemeint war), tragen aber
   jetzt den Vermerk. Sie zu beleben wäre eine Produktentscheidung: jedes
   Muster mit `sources: [mcp]` bekäme schlagartig den ganzen Katalog.

**Ursache — dieselbe wie bei den LiteLLM-Antwortformen (P11) und
`_export_non_empty` (E2): die Attrappe war nach dem Code gebaut, nicht nach der
Wirklichkeit.** Die Bestandstests bauen `pattern_output` von Hand und trafen
deshalb Zweige, die es im Betrieb nicht gibt. Neu: `test_pattern_tool_naht.py`
fährt **ausschliesslich** über `phase3_modulate`.

**Ein Warnschuss, der zurückgenommen wurde.** Der erste Entwurf protokollierte
„nennt `mcp`, hat aber keine Werkzeuge". Der Wächter über dem echten Seed liess
ihn sofort auffliegen: `PatternDef.sources` hat die Vorgabe `["mcp"]`, also
erben **M01, M02, M03, M13, M14** eine Quelle, die niemand gewählt hat — die
Warnung hätte auf fünf ausgelieferten Mustern gefeuert. „Nicht gesetzt" ist zur
Laufzeit ununterscheidbar von „ausdrücklich mcp", damit ist eine
Laufzeit-Warnung das falsche Werkzeug. Statt dessen ein **Seed-Wächter**: wer
`mcp` ausdrücklich einträgt, muss auch Werkzeuge nennen. Entwarnung nebenbei:
dieselbe Vorgabe schaltet `_rag_allowed_for_pattern` ab, das bleibt aber
folgenlos — genau diese fünf Muster deklarieren keine `rag_areas`.

**Ein Defekt aus E3 mit gefunden.** Die Betreiber-Warnung las
`pattern_output["id"]` — den Schlüssel schreibt `phase3_modulate` nicht (auch
`label` nicht). Im Betrieb stand dort immer „Muster ?": ein Eintrag, der
informativ aussah und dem Betreiber nicht sagte, wo er nachsehen soll.
`_select_active_tools` bekommt jetzt `pattern_label` als Schlüsselwort mit
Vorgabe (kein Aufrufer musste angefasst werden); `generate.py` reicht es durch.
Beides rot-grün gegengeprüft, die Verdrahtung ist in `test_generate` gepinnt.

#### ❌ `PatternDef.sources` auf `None` — gemessen, verworfen (2026-08-10)

Ich hatte das selbst empfohlen. Die Messung der beiden echten Verbraucher
(`route.py:57-67` `_resolve_rag_areas`, `respond.py:110-114` Prefetch-Gate)
sagt: nicht machen. Für M01, M02, M03, M13, M14 änderte sich

| | ist | nach der Umstellung |
|---|---|---|
| RAG-Bereiche | `[]` | `['Plattformwissen']` — **an** |
| Spekulative Suche | läuft | **unterdrückt** |

Zwei Verhaltensumschläge auf fünf ausgelieferten Mustern — darunter die
**Sicherheitsmuster M01/M02**, die plötzlich RAG-Kontext bekämen —, und das
allein, um eine **diagnostische** Unterscheidung sichtbar zu machen. Schlechter
Tausch.

**Der Ersatz kostet nichts:** die Unterscheidung ist eine Schicht weiter oben
längst da. `config_models/patterns.py:29` führt `sources: list[str] | None =
None` — das studio-seitige Modell verliert „nicht gesetzt" gar nicht erst. Wer
den Wächter über Studio-Muster ziehen will, setzt dort an, nicht an
`PatternDef`. Bis dahin bleibt die Lücke bewusst offen und benannt: der
Seed-Wächter deckt den ausgelieferten Baum ab, nicht die Datenbank.

#### 🔶 Kuration im Chat — die Frage war falsch gestellt (2026-08-10)

„Welches Muster bietet die kuratierenden Werkzeuge an?" lässt sich nicht
beantworten, weil **kein Muster dorthin geroutet werden kann**. Gemessen:

- **`seeds/04-intents/intents.yaml` kennt acht Absichten, I01–I08.** Keine
  davon ist „kuratieren". M13 (I08) ist das Gegenteil eines Werkzeugpfads: es
  reicht den WordPress-Link `/mitmachen/inhalt-vorschlagen/` heraus und sagt
  „die Redaktion prüft das" — der *menschliche* Einreichweg, mit
  `output_mode: routing` und einem ausdrücklichen Tool-Verbot.
- **Gute Nachricht: es wäre reine Config.** `intent_id` ist ein freier `str`
  (`api/schemas.py:111`), die Absichtsliste rendert
  `_render_intents_block` aus dem Seed in den Klassifikator-Prompt, und
  `select_pattern` löst `pattern_id_hint` gegen die geladenen Muster auf. Ein
  Kurations-Intent plus ein Kurations-Muster brauchen **keine Codeänderung**.

**Was die Entscheidung wirklich trägt, ist aber nicht das Muster, sondern die
Identität.** `services/mcp/auth.py` kennt genau zwei Betriebsarten für den
**ganzen Prozess**: `anonymous` oder `service`. Es gibt **keine
Nutzer-Anmeldung**. Setzt der Betreiber `MCP_AUTH_TOKEN`, dann kuratiert nicht
„die Redaktion", sondern **jeder Besucher des öffentlichen Widgets** — unter
einem einzigen geteilten Dienst-Konto, ununterscheidbar im WLO-Protokoll.

Die E1-Wall entschärft das nur teilweise: sie erzwingt einen Zugwechsel
zwischen Vorschau und Bestätigung. Gegen ein *versehentliches* Schreiben des
Modells hilft das; gegen eine Person, die im nächsten Satz „ja, mach" schreibt,
nicht.

**Damit ist das keine Muster-, sondern eine Produkt- und Sicherheitsfrage**, und
sie gehört dem Nutzer. Drei gangbare Wege, ohne Empfehlung von mir:

1. **Kuration bleibt aus** (`MCP_AUTH_TOKEN` ungesetzt) — heutiger Stand. Paket
   E ist dann gebaute Bereitschaft, keine aktive Funktion.
2. **Kuration nur in einer nicht-öffentlichen Einbettung** (Redaktions-Instanz
   mit eigenem Widget-Deployment), öffentliche Instanz ohne Block.
3. **Pro-Nutzer-Anmeldung nachziehen** (OAuth 2.1, das der MCP-Server laut
   `INTEGRATION.md` §2.5 ebenfalls kann) — dann trägt jede Änderung einen
   Namen. Das ist ein eigenes Paket, kein Zusatz zu F.

Erst nach dieser Entscheidung ist sinnvoll, Intent + Muster zu schreiben — und
weil beides den Klassifikator-Prompt ändert, macht es ohnehin die Goldreferenz
neu (Paket G).

#### ✅ F1-a erledigt 2026-08-10 — 72 % des RAG-Bestands waren unerreichbar

Der erste Griff ins Ideen-Dokument förderte einen Live-Defekt zutage, den das
Dokument nicht kennt: es führt Q1–Q4 als „Korpus fehlt". Das stimmt nicht mehr.
Gemessen gegen die laufende Entwicklungs-Datenbank: **906 Bruchstücke in acht
Korpora**. Über den echten Resolver `_resolve_rag_areas` erreichbar waren
**zwei**.

| Korpus | Bruchstücke | erreichbar von |
|---|---:|---|
| WissenLebtOnline | 246 | M04 |
| OER-Wissen | 231 | **niemandem** |
| ITSJOINTLY-Schlussbericht | 175 | **niemandem** |
| WirLernenOnline | 93 | **niemandem** |
| Edu-Sharing-Network | 68 | **niemandem** |
| Edu-Sharing-Metaventis | 53 | **niemandem** |
| FAQ | 30 | **niemandem** |
| Plattformwissen | 10 | M04, M15 |

**650 Bruchstücke, 72 % des Bestands, konnte kein Muster abfragen.** Am
schärfsten bei M04: sein eigenes `when_to_use` nennt „Bildungs-, Plattform- und
OER-Themen", aber der Korpus `OER-Wissen` — der zweitgrösste — lag ausserhalb
seiner Reichweite. Auf „Was bedeutet OER?" antwortete der Bot an seinem
OER-Wissen vorbei.

**Ursache: Drift, kein Denkfehler.** Der Bestand wuchs beim Neu-Einlesen (P11
Schritt 2), die `rag_areas` der Muster stammen aus dem ALT-Import und wuchsen
nicht mit. `mode: always` half nicht — der Zweig, der es auswertet, wird nie
erreicht, weil jedes RAG-Muster seine Bereiche ausdrücklich deklariert. Damit
ist `mode: always` für den ausgelieferten Stand **wirkungslos**.

**Erweitern war unbedenklich, und zwar nachgesehen statt vermutet:**
`get_rag_context` sortiert **global** über alle Bereiche, deckelt bei `top_k`,
verwirft alles unter `min_score` und rerankt. Ein Bereich mehr kann nur ein
schwächeres Bruchstück verdrängen — den Prompt aufblähen kann er nicht. Die
Suchen laufen nebenläufig über **eine** Einbettung.

Geändert wurde nur Seed-Config: M04 bekommt alle acht (Wissens- wie
Organisations-Korpora), M15 nur die drei plattformnahen — es ist der kurze
Erstkontakt, kein Auskunftsschalter über Vereine und Schlussberichte. Neuer
Wächter `test_rag_korpus_erreichbar.py` prüft die **Klasse**: wer künftig einen
Korpus einliest und keinem Muster zuordnet, fällt auf. Dazu die Gegenrichtung —
ein Tippfehler in `rag_areas` wird von `_resolve_rag_areas` still verworfen und
ist jetzt gepinnt.

**Wirksam erst nach einem Seed-Import** — die laufende Config steht in der
Datenbank, nicht in der Datei.

#### 🔶 Kuratierung: die Anmeldung geht doch pro Person (Nutzer-Entscheid 2026-08-10)

Der Nutzer entscheidet: **Kuratierung kann aktiviert werden**, und beim Aufruf
soll eine **Anmelde-Aufforderung auf die MCP-Auth-Seite** gehen; zweistufig, mit
der Frage, ob man sich anmelden will oder nur lesend arbeitet.

**Damit fällt mein E3-Argument — gemessen, nicht diskutiert.** Ich hatte
argumentiert, der Zugangsblock sei ein Server-Geheimnis, also könne eine
Lehrkraft nichts damit anfangen. Das gilt nur für `mode: service`. Der Server
kennt **drei** Betriebsarten, unser `auth.py` behauptet im Kopfkommentar
„genau zwei". Live abgefragt:

```json
{"mode":"user","authenticated":true,"configuredAs":"janschachtschabel",
 "authority":"janschachtschabel","displayName":"Jan Schachtschabel"}
```

**Die Rückmeldung, nach der gefragt wurde, gibt es also — `wlo_auth_status`.**
Sie liefert die Betriebsart, den **Namen** der angemeldeten Person und —
getrennt davon — `authenticated`. Diese Trennung ist wichtig: bei
`mode=user/service` **und** `authenticated=false` lehnt WLO die Zugangsdaten ab,
und dann schlagen **alle** Abfragen fehl, nicht nur die schreibenden. Der Bot
darf das dann nicht als „dazu gibt es nichts" ausgeben.

**Was heute fehlt, ist unsere Seite — und zwar genau eine Sache:** der
Zugangsblock ist bei uns **prozessweit**. `build_http_client_factory()` liest
einen einzigen `SecretStr` aus den Einstellungen; die drei Tore
(`has_auth_token()`) fragen den Prozess, nicht die Person. Ein *persönlicher*
Block in `MCP_AUTH_TOKEN` machte es schlimmer, nicht besser: dann handelte
jeder Besucher unter einem echten Namen.

**Die Naht ist schmal** — `transport.py:85` (eine Verbindungsstelle) plus drei
Tore in `response_tool_selection.py` plus die Auskunft in `health.py`. Machbar.

**Offen war der Weg des Blocks vom `/auth`-Fenster in die Chat-Sitzung**, und
eine Möglichkeit war schon ausgeschlossen: **nicht in den Chat eintippen
lassen.** `save_message` schreibt `content` unverändert nach `chat_messages`,
und `_assemble_messages` reicht die Historie ans Modell — ein eingefügter Block
läge dauerhaft in der Datenbank und ginge an den Modell-Anbieter.

#### 🔶 Welcher Weg — der Vergleich (gemessen 2026-08-10)

Der SC-Baum liegt unter `Windsurf/wlo-mcp-server-sc` (eine Ebene über
`wlo-suche/`; meine frühere Aussage „fehlt" war an der falschen Stelle
gesucht). Seine `docs/AUTH.md` beantwortet die Umbaufrage und kippt zugleich die
Annahme, auf der **beide** meiner Optionen ruhten.

**Der Zugangsblock IST ein WLO-Passwort.** AUTH.md §1: edu-sharing hat kein
Token zu vergeben — seine OpenAPI kennt nur `basicAuth` und `cookieAuth`, ein
`Bearer` wird *ignoriert statt abgelehnt*. Also trägt alles, was das Repository
erreicht, das echte Passwort. Der Block `wlo2.…` ist genau das, hybrid
verschlüsselt auf den Schlüssel des MCP-Servers. §5b: **kein `refresh_token`,
kein `expires_in`** — der Zugang endet mit Widerruf oder Passwortwechsel.

Das ändert den Maßstab: Wir vergleichen nicht zwei Ablageorte für ein
Sitzungstoken, sondern zwei Ablageorte für ein **unbefristetes
Passwort-Äquivalent**.

**Messung 1 — die Sitzungskennung taugt nicht als Bindeglied.**
`link-handoff.ts:90` und `:163` hängen sie als `?bsid=` an ausgehende Links,
schreiben sie in `anchor.href` (also auch Mittelklick und neuer Tab) und
navigieren damit über TLD-Grenzen. Sie wird auf der Zielseite zwar aus der
Adresszeile entfernt, war da aber schon — in Verlauf, Adresszeile und im
Zugriffsprotokoll der Zielseite. Die Entropie stimmt (`bb-` + UUID v4,
`session-id.ts:127`), die **Verbreitung** ist das Problem: die Kennung ist
absichtlich teilbar. Ein Passwort-Äquivalent daran zu binden, macht aus einem
Übergabe-Zettel einen Ausweis.

**Messung 2 — der Speicher des Widgets gehört der Gastgeberseite.**
`writeSessionEverywhere` schreibt in `localStorage` und optional in ein Cookie
auf konfigurierbarer Domain. Das Widget ist ein Custom Element in einer fremden
Seite; deren `localStorage` liest jedes Skript dort.

**Messung 3 — `/auth*` und `/oauth/authorize` senden bewusst keinen
CORS-Header** (`http-app.ts:135`, `isCredentialSurface`), *`/oauth/register`
und `/oauth/token` dagegen schon*. Ein Anmeldevorgang aus dem Widget heraus ist
damit möglich — aber nur als OAuth, nicht als Formular-Aufruf.

| | Option 1: Block im Browser, je Anfrage als Kopfzeile | Option 2: Rückruf, serverseitig an die Sitzung gebunden |
|---|---|---|
| Bindeglied | keins nötig | `session_id` — **wandert per `?bsid=` durch URLs** |
| Bei uns dauerhaft gespeichert | **nichts** | Passwort-Äquivalent je Person, unbefristet |
| Schadensbreite bei Einbruch | eine Person, XSS auf genau ihrer Gastgeberseite | **alle Personen auf einmal**, ein Datenbank-Abfluss |
| Alternatives Bindeglied | — | eigenes Geheimnis im Cookie — Drittanbieter-Cookie, im Einbettungsfall zunehmend blockiert |
| Widerruf | `/auth/revoke-all`, eine Seite | zusätzlich unsere eigene Oberfläche nötig |

**Option 2 ist in der naheliegenden Form die unsicherere** — nicht wegen der
Serverseite, sondern weil ihr natürliches Bindeglied bei uns ausgerechnet die
Kennung ist, die wir absichtlich verteilen. Repariert man das mit einem eigenen
Geheimnis, bleibt der schwerere Posten: wir würden zum zweiten Ort, an dem
WLO-Passwörter liegen — in einem System mit Chat, LLM, RAG, Studio und Upload,
also deutlich größerer Angriffsfläche als der MCP-Server.

#### 🔶 Empfehlung: Option 1 in der Form, aber per OAuth statt per Einfügen

**Muss am MCP etwas umgebaut werden? Nein.** Alles Nötige läuft dort schon, und
die Kompatibilität mit anderen Clients ist genau das, was AUTH.md §10 Regel 8
schützt („ein Aufruf ohne `Authorization` antwortet weiter 200"). Live geprüft:

```
/.well-known/oauth-authorization-server → 200
/.well-known/oauth-protected-resource   → 200
"code_challenge_methods_supported":["S256"]
"token_endpoint_auth_methods_supported":["none"]
```

Vier Dinge, die wir nicht bauen müssen, weil es sie gibt: OAuth 2.1 mit offener
Client-Registrierung (RFC 7591) und PKCE; die **dreifache Zustimmungsseite**
— anmelden / *ohne Konto verbinden* / ablehnen (§5b) — also genau die
Zwei-Stufen-Frage, und zwar auf der Herkunft des MCP-Servers, wo die Adresszeile
prüfbar ist; die Verweigerung der Schreibwerkzeuge zur Aufrufzeit mit
`_meta["mcp/www_authenticate"]` als Rückmeldekanal (§6); und `wlo_auth_status`
als Auskunft.

`token_endpoint_auth_methods_supported: ["none"]` ist dabei das Argument gegen
den Umweg über unser Backend: der Server behandelt **jeden** Client als
öffentlich. Es gibt kein Client-Geheimnis, das ein Backend besser hüten könnte
als ein Browser — ein Backend-als-Client kaufte Speicherhaftung ein, ohne dafür
Vertraulichkeit zu bekommen, die das Protokoll anerkennt.

Empfohlen wird deshalb:

1. Der Chat erkennt Kuratierungs-Absicht und bietet **zwei Chips** an —
   „Mit WLO-Konto anmelden" und „Nur lesen". (Der Chip ist zugleich die
   Nutzergeste, ohne die ein Browser das Anmeldefenster blockt.)
2. Chip 1 fährt den OAuth-Vorgang **im Browser** (öffentlicher Client + PKCE,
   Fenster auf `/oauth/authorize`, Tausch über `/oauth/token`).
3. Der Block landet in `sessionStorage` — **nicht** `localStorage`, nicht im
   Cookie: er soll mit dem Tab sterben, nicht neben der Sitzungskennung liegen.
4. Je Anfrage als Kopfzeile ans Backend, dort **nur durchgereicht** —
   `_open_session` baut die Fabrik ohnehin je Aufruf, es fehlt nur der Weg
   dorthin. Nichts davon wird gespeichert oder protokolliert.
5. `wlo_auth_status` als Rückmeldung; `authenticated: false` ist ein Fehler,
   **nicht** „dazu gibt es nichts".

**Was das ehrlich nicht schützt:** der Block liegt im JS-Kontext der
Gastgeberseite; ein XSS dort stiehlt ihn. Das ist nicht wegzubauen, solange der
Browser eine Berechtigung hält — der einzige Entwurf ohne diese Eigenschaft ist
der, bei dem wir alle Passwörter sammeln. Der Aufstiegspfad, falls das Risiko
später anders bewertet wird, ist benannt: Block im Backend + eigenes
Bindegeheimnis; er kostet Verschlüsselung im Ruhezustand, Löschkonzept und eine
Widerrufsoberfläche.

#### ✅ C5-a — Zugangsblock je Zug (Backend-Naht), fertig 2026-08-10

**Der Entwurf wurde von einer Messung entschieden, nicht von Geschmack:**
``call_mcp_tool`` hat **23 Aufrufstellen in 9 Dateien**. Einen Block durch alle
Signaturen zu fädeln wäre ein Eingriff in ein Dutzend Module für einen Wert, der
unterwegs niemanden interessiert. Dasselbe Problem löst dieses Paket schon
zweimal mit einem ``ContextVar`` (``_query_metas``, ``_request_hints``) — mit
wörtlich derselben Begründung. Also das etablierte Mittel: **die 23 Aufrufstellen
blieben unberührt.**

* ``services/mcp/auth.py`` — ``_turn_block`` (ContextVar) + ``set_turn_auth_block``
  + ``_effective_token`` (Zug vor Anlage). ``has_auth_token()`` wird dadurch
  zug-abhängig, und damit **alle drei Tore in ``response_tool_selection.py`` von
  selbst** — sie rufen genau diese Funktion. ``auth_mode()`` bleibt bewusst
  anlagen-bezogen: es beantwortet ``/health``, und dort gibt es keinen Zug.
* ``api/chat.py`` — ``_adopt_turn_auth_block(request)`` in **beiden** Endpunkten.
  Kopfzeile ``WLO-Access-Block``; **nicht** ``Authorization`` (die bedeutet
  „berechtige mich gegenüber DIESEM Server"), und **nicht** als ``Header()``
  deklariert — das trüge sie in den eingefrorenen Vertrag ein (Trick aus C1-e1).
* Prüfung am Rand, weil der Wert aus unvertrauter Hand kommt: Präfix ``wlo`` +
  base64url-Zeichenvorrat + 4096 Zeichen. Das schliesst Steuerzeichen aus
  (zweite Kopfzeile), das mitkopierte Wort „Bearer " (AUTH.md §5a) und fremde
  ``Authorization``-Werte — sonst wäre unser Backend ein Weiterleiter, und die
  Missbrauchsschranke des MCP zählt je Adresse, also gegen unsere.

**Zwei Fallen, beide beim Bauen aufgelaufen und behoben:**

1. **Ein abgelehnter Wert muss löschen, nicht durchreichen.** Sonst hinge ein Zug
   an der Anmeldung des vorigen — der ``ContextVar`` überlebt die Task. Deshalb
   ruft der Endpunkt ``_adopt_turn_auth_block`` **immer**, auch ohne Kopfzeile.
   Eigener Test dafür (zwei Züge nacheinander im selben Prozess).
2. **Der Vertragstest fiel — wegen eines Docstrings.** FastAPI trägt Docstrings
   als ``description`` in das OpenAPI-Dokument ein; mein Zusatz an
   ``chat_stream`` reichte. Gemessen: ``parameters`` blieb in beiden Fassungen
   ``None``, die **Kopfzeile selbst ist unsichtbar** — genau wie geplant. Der
   Hinweis steht jetzt als Kommentar. Merksatz: am eingefrorenen Vertrag ist der
   Docstring Teil der Schnittstelle.

Nachgezogen: die E3-Warnung nannte ``MCP_AUTH_TOKEN`` als einzige Ursache. Von
dort aus sind die beiden Ursachen nicht zu unterscheiden — sie nennt jetzt beide.

Belege: ``pytest -q`` **2741 passed, 4 skipped** (vorher 2717; +24) · ``ruff
check .`` sauber · ``export_openapi.py --check`` „openapi contract unchanged".

#### ✅ C5-b — Widget hält den Block und schickt ihn mit, fertig 2026-08-10

* ``ui/src/session/mcp-access.ts`` — ``sessionStorage`` (**nicht**
  ``localStorage``, nicht Cookie), Form-Prüfung spiegelbildlich zum Backend,
  ``accessBlockHeaders()``. Begründung im Modulkopf, gegen AUTH.md gemessen: der
  Block ist ein Passwort-Äquivalent **ohne Ablauf**, er darf nicht neben der
  Sitzungskennung liegen, die absichtlich langlebig ist und per ``?bsid=`` durch
  URLs wandert. Mit dem Tab zu sterben ist hier ein Merkmal.
* ``stream/stream-client.ts`` — beide Stellen: Strom **und** Rückfall-POST.
  Eigener Test dafür, weil die halb verdrahtete Fassung sonst grün wäre und der
  Fehler erst bei einem Stream-Abbruch aufflöge.
* Ohne Anmeldung geht **gar keine** solche Kopfzeile raus (leeres Objekt statt
  leerem Wert) — sonst meldete das Backend für jeden anonymen Zug eine Warnung.

Belege: ``npx ng test ui`` **63 Dateien / 621 Tests grün** ·
``npm run build:widget`` erfolgreich (514 kB / 127 kB gzip).

#### ✅ C5-c1 — der Anmeldevorgang (ohne Oberfläche), fertig 2026-08-10

* ``ui/session/oauth-pkce.ts`` — reine Funktionen: Prüfwort, `state`,
  S256-Ableitung, Zustimmungs-Adresse, Rückkehr-Parameter. Gegen den
  **Testvektor aus RFC 7636 Anhang B** gepinnt, nicht gegen die eigene Ausgabe:
  ein selbst erzeugter Erwartungswert hätte jede base64url-Verwechslung
  (``+/`` statt ``-_``, Füllzeichen) mitbestätigt statt sie zu finden.
* ``ui/session/mcp-oauth.ts`` — Discovery → Registrierung → Fenster → Tausch →
  Block ablegen. Netz und Fenster sind injizierbare Ränder. Die Rückgabe
  unterscheidet **abgelehnt** von **kaputt** (`denied` / `timeout` /
  `popup-blocked` / `unavailable` / `exchange-failed`) — „ablehnen" ist eine
  Entscheidung und braucht eine andere Antwort als eine Panne.
* ``widget/src/oauth-callback.html`` — die Rückkehr-Seite.

**Die Entscheidung, die den Vertrag rettet:** die Seite ist eine **Datei im
Bündel**, keine Route. Die Widget-Pfade stehen im eingefrorenen Dokument; der
vorhandene Sammelpfad ``/widget/{asset_name}`` liefert sie mit aus. Der
Dockerfile kopiert ohnehin das ganze Verzeichnis
(``COPY … /build/dist/widget/browser ./widget_dist``), sie erreicht also den
Betrieb unter ``/widget/oauth-callback.html``.

**Zwei Sicherheitsprüfungen tragen den Vorgang, beide gegengeprüft:** die
Rückmeldung muss aus **genau dem geöffneten Fenster** kommen (``event.source``)
und ihren ``state`` tragen. Mit beiden Prüfungen ausgebaut fielen **exakt die
zwei** zugehörigen Tests und sonst keiner — sie unterscheiden also wirklich.
Erster Testentwurf war fehlerhaft: er schickte einen erfundenen ``state`` und
wäre auch ohne die Bindung grün gewesen; jetzt liest er den echten aus der
Fenster-Adresse.

**Zwei Messungen, die Arbeit gespart bzw. einen Fehlschlag verhindert haben:**

1. ``.html`` steht bewusst **nicht** in ``_MEDIA_TYPES`` — der Wächter dafür war
   ohne jede Codeänderung grün, weil ``FileResponse`` bei ``media_type=None``
   aus dem Dateinamen rät. Ein Eintrag wäre Zusatz ohne Wirkung gewesen.
2. Der Asset-Eintrag gehörte an das Ziel **``build-widget``** (das
   ausgelieferte), nicht an ``build`` (die Entwickler-Variante). Nach dem ersten
   Bau lag die Seite **nicht** im Bündel; nur der Blick in ``dist/`` hat das
   gezeigt.

``postMessage(..., '*')`` ist bewusst: Ziel ist ausschliesslich
``window.opener``, die Herkunft der Gastgeberseite ist uns unbekannt und wäre
fest gesetzt schlicht falsch, und weitergereicht wird nur der Code — einmalig,
60 s, ohne den Prüfwert wertlos. Die Gegenprüfungen sitzen beim Empfänger.

Belege: ``npx ng test ui`` **65 Dateien / 641 Tests** · Backend ``pytest -q``
**2742 passed, 4 skipped** · ruff sauber · Vertrag unverändert ·
``npm run build:widget`` liefert ``dist/widget/browser/oauth-callback.html``.

#### ✅ C5-c2 — die zweistufige Rückfrage im Chat, fertig 2026-08-10

**Die Messung VOR dem Bauen ist der wichtigste Teil dieser Scheibe.** Der
Auslöser der Rückfrage sollte ``curation_blocked_by_mode`` sein — „ein Muster
wollte kuratieren, ohne dass ein Zugangsblock gilt". Gemessen: **keines der 17
Muster im Seed nennt ein kuratierendes Werkzeug**; die einzigen Treffer für die
14 Namen stehen in ``05-knowledge/mcp-servers.yaml``, also im Bestandsverzeichnis
des Servers, nicht in einer ``tools:``-Liste. Damit sind **alle drei** Verbraucher
von ``has_auth_token()`` (``_nameable_tools``, ``curation_blocked_by_mode``, die
E3-Warnung) im Auslieferungsstand **ruhend**.

Ruhend ist aber nicht tot, und der Unterschied entscheidet: ``tools:`` ist ein
**Studio-Feld**. In dem Augenblick, in dem eine Redaktion dort
``wlo_add_to_collection`` einträgt — ohne Auslieferung, ohne Neustart —, greift
die Bedingung, und genau dann braucht die Person diesen Chip. Gebaut wurde also
ein Wächter über einer config-erreichbaren Naht, **nicht** Maschinerie ohne
Verbraucher. Einen Kurations-Intent samt Muster zu schreiben bleibt die getrennte
Produktentscheidung aus §F (`🔶 Kuration im Chat`), die ohnehin Paket G auslöst.

**Was gebaut wurde:**

* ``domain/auth_qr.py`` + Verdrahtung als **letzte** Station in
  ``turn_assembly`` (nach dem Relevanz-Rückfall, der ebenfalls an Position 0
  einfügt und auf vier kürzt — davor eingesetzt wanderte die Anmeldung nach
  hinten oder fiele heraus).
* ``api/config.py`` — ``mcp_auth_base`` im öffentlichen Boot-Bündel: **nur**
  ``scheme://host``, ohne den ``/mcp``-Pfad (die Entdeckungs-Dokumente liegen an
  der Wurzel) und ohne den Rest der Server-Registrierung. Kein Vertragsbruch:
  die Rückgabe ist ``dict``, im Dokument also ein offenes Objekt — eine eigene
  Route wäre einer gewesen.
* Widget: ``chips/auth-qr.ts``, ``session/sign-in-flow.ts``, Zweig in der
  Chip-Reihe und in ``input-routing``, 7 Katalog-Einträge je Sprache.

**Die Entwurfsentscheidung, die diese Scheibe trägt: die zwei Chips sind
verschiedener Natur.** Chip 1 (``__auth__``) trägt **keine** Beschriftung — anders
als seine beiden Geschwister ``__guide__|Label|url`` und
``__action__|Label|…``, deren Text Inhalt ist (vom Modell formuliert bzw. aus der
Config gepflegt). Diese hier benennt eine Handlung des Widgets, wird nirgends
hingeschickt und soll dem Sprachumschalter folgen — also gehört sie in den
Widget-Katalog. Chip 2 trägt sie sehr wohl, denn **er IST seine Beschriftung**:
der Klick sendet den Text als Nachricht. Das ist die Regel aus C1-g2b, hier zum
ersten Mal in beide Richtungen angewandt.

Der Vorgang unterscheidet weiterhin sechs Ausgänge und sagt jeden eigens an.
„Nicht angeboten" ist eine Eigenschaft der Anlage, „abgelehnt" eine Entscheidung
der Person — ein gemeinsames „hat nicht geklappt" wäre für fünf der sechs Fälle
unwahr und unterstellte im ersten einen Fehler, wo jemand bewusst nein gesagt
hat. Ohne bekannte MCP-Herkunft öffnet der Chip **kein** Fenster, sondern sagt
das: ein aufblitzendes leeres Fenster wäre die schlechtere Antwort.

**Zwei Funde beim Bauen:**

1. ``ChatShellComponent.translate`` ist ein **Pflicht-Input**, den die
   Routing-Spec nie gesetzt hatte — die Anmeldung ist die erste Weiche, die
   überhaupt Text erzeugt. NG0950 statt einer stillen Lücke; behoben mit einer
   eigenen Hilfsfunktion im Test.
2. **Beim Nachlesen des eigenen Entwurfs:** ``signIn`` fängt Netz- und
   Fensterfehler ab, aber nicht alle — ``crypto.subtle`` fehlt auf unsicherer
   Herkunft (``http://``) und **wirft**. Da der Chip mit ``void`` startet, wäre
   das eine unbeachtete abgewiesene Zusage geworden: der Chip täte scheinbar
   nichts, der Fehler stünde nur in der Konsole. Jetzt ein ``try/catch`` um den
   Vorgang, mit eigenem Test. Merksatz: ``void promise`` verlangt, dass der
   Vorgang seine Fehler selbst in Antworten verwandelt.

**Beide Gegenproben gefahren:** mit ausgebautem ``blocked``-Ausdruck fielen
**genau die zwei** Backend-Tests, die den Chip erwarten (die beiden
Negativ-Tests blieben grün); mit ausgebautem ``__auth__``-Zweig in
``input-routing`` fielen **genau die zwei** Widget-Tests.

Bewusst NICHT gebaut: den Namen der angemeldeten Person anzuzeigen. Er steht
verschlüsselt im Block (AEAD, ``{ v, jti, u, secret, iat }``) und ist im Browser
nicht lesbar; ihn zu zeigen hiesse, ``wlo_auth_status`` über eine **neue**
Backend-Route durchzureichen — der eine Bruch am eingefrorenen Vertrag, den diese
ganze Reihe vermieden hat. Die Rückmeldung, die die Person wirklich braucht, ist
„du bist angemeldet, ab jetzt arbeite ich in deinem Namen", und die steht.

Belege: ``npx ng test ui`` **67 Dateien / 667 Tests** (vorher 65/641) ·
``pytest -q`` **2767 passed, 4 skipped** (vorher 2742) · ruff sauber ·
``export_openapi.py --check`` „openapi contract unchanged" ·
``npm run build:widget`` 520 kB / 129 kB gzip, und ``auth.signIn`` /
``__auth__`` / ``mcp_auth_base`` sind im ausgelieferten ``main.js`` nachweisbar.

**Die E3-Warnung bleibt eine Warnung** — die in C5-c2 offen gelassene Frage
beantwortet sich durch die Messung von selbst: sie fällt nur, wenn ein Muster
kuratierende Werkzeuge NENNT. Solange das kein Muster tut, fällt sie nie; sobald
eines es tut, ist ein Betreiber ohne Zugangsblock genau der Fall, für den sie
geschrieben wurde.

**Betriebshinweis, unabhängig von der Entscheidung:** solange ein *persönlicher*
Block in `MCP_AUTH_TOKEN` steht, handelt jeder anonyme Besucher unter diesem
Namen. Für den Dauerbetrieb gehört dort entweder ein Dienstkonto (dann greift
serverseitig `WLO_ALLOW_SERVICE_WRITES`, ab Werk aus) oder gar nichts.

**Betriebshinweis, unabhängig von der Entscheidung:** solange ein *persönlicher*
Block in `MCP_AUTH_TOKEN` steht, handelt jeder anonyme Besucher unter diesem
Namen. Für den Dauerbetrieb gehört dort entweder ein Dienstkonto (dann greift
serverseitig `WLO_ALLOW_SERVICE_WRITES`, ab Werk aus) oder gar nichts.

**Zwei Nebenbefunde am SC-Baum** (Referenz, nicht von uns zu ändern):
`docs/TOOLS.md:200` behauptet noch „Nur sichtbar mit Schreibrechten", während
Zeile 8 derselben Datei und AUTH.md §6 das Gegenteil sagen (seit 2026-08-05
immer sichtbar) — ein Rest der alten Fassung. Und: anonym **schreiben** geht
nirgends, auch nicht als Vorschlag (`TOOLS.md:30` „anonym nie"); die „nur
lesen"-Stufe ist also wirklich nur lesend.

### Paket H — Werkzeug-Vollabdeckung der Muster (Nutzer-Entscheid 2026-08-10)

Nutzer-Vorgabe: „wenn keins der Muster kuratierende Werkzeuge nennt, sind die
Muster noch nicht korrekt angepasst — es sollen alle Fähigkeiten des MCP
unterstützt werden." Gewählt wurde **Variante A** (Werkzeug-Vollabdeckung im
Bestand) gegen einen Neuschnitt nach dem Ideen-Dokument.

#### ✅ H1 — die Messung, die den Auftrag begrenzt

| | |
|---|---|
| Server-Werkzeuge (`src/tools/`) | **40** + `search`/`fetch` als ChatGPT-Aliase |
| Unser Katalog | **36** = 22 lesend + 14 kuratierend |
| Katalog-Werkzeuge, die **kein Muster** nennt | **15** — alle 14 kuratierenden + `get_nodes_details` |
| Muster ohne jedes Werkzeug | 8 von 17 (M01–M04, M11, M13–M15) |

**Randbedingung, die das Ideen-Dokument nicht haben konnte:** 13 seiner
Soll-Punkte sind **neue MCP-Werkzeuge** (`get_skill_bundle`,
`get_compendium_section`, `wlo_create_text_content` …). `wlo-mcp-server-sc` ist
für uns Referenz — aus diesem Repo heraus sind Muster, Engine und Katalog
erreichbar, nicht das Werkzeug-Inventar.

#### ✅ H2 — M18 „Kuration" + Intent I09, fertig 2026-08-10

* **`seeds/03-patterns/m18-kuration.md`** — Priorität **545**, nennt alle 14
  kuratierenden Werkzeuge plus fünf lesende, ohne die kein Schreibpfad
  funktioniert (erst den Gegenstand finden und seinen IST-Stand lesen, dann
  ändern). Die `core_rule` ist der **Bestätigungs-Wall aus E1**: Vorschau →
  vollständig vorlegen → Zug endet → erst das Ja im Folgezug führt aus, und
  berichtet wird, was TATSÄCHLICH ankam.
* **`seeds/04-intents/intents.yaml` → I09 „Kuratieren"** — mit zwei
  Negativ-Triggern und drei Unterscheidern. Der wichtigste ist **I09 vs. I08**:
  „Wie reiche ich ein?" bleibt bei M13 (der menschliche Weg über das
  WordPress-Formular, für Leute ohne Konto), „Reich das ein." geht an M18.
  Dieselbe Grenze noch einmal als `discriminator` im Muster.
* **`get_nodes_details` an M08** — der Batch-Zwilling von `get_node_details`.
  Beim Drilldown liegt als Einzigem eine bekannte ID-LISTE vor; bis 20 Knoten
  gehen in einem Aufruf statt in zwanzig.

#### ✅ H3 — zwei Wächter, einer davon ein gefundener Defekt

**Neu, Gegenrichtung:** `TestGegenrichtung` in `test_pattern_tool_naht.py` —
„kein Katalog-Werkzeug ohne Muster", mit einzeln begründeter Ausnahmeliste
(nur `wlo_health_check`, Betriebs-Sonde). Rot mit exakt den 15 Namen, grün nach
M18. Ein zweiter Test hält die Ausnahmeliste ehrlich: eine Ausnahme für ein
Werkzeug, das es nicht mehr gibt, verdeckt beim nächsten Umbau eine echte Lücke.

**Gefunden dabei:** `test_jeder_im_pattern_genannte_tool_name_existiert`
(W5-4a) prüfte nur gegen `TOOL_DEFINITIONS` — **es hätte das erste
Kurationsmuster als Tippfehler abgewiesen**. Der Wächter urteilte über eine
andere Menge als `_nameable_tools`, das beide Kataloge kennt. Jetzt beide.

**Der Nachweis läuft über den ECHTEN Seed und den ECHTEN Betriebspfad**
(`phase3_modulate` → `_select_active_tools`), nicht über ein handgebautes
`pattern_output` — genau die Unterscheidung, an der F-neu 0 gegen 23 Werkzeuge
gemessen hat. Mit Block: alle 14 da. Ohne Block: keins, aber die lesenden
Helfer bleiben (sonst könnte das Muster nicht einmal sagen, worüber es gerade
nicht schreiben kann) — und **genau dann** meldet die E3-Warnung, und genau
dann erscheinen die C5-c2-Chips.

Belege: `pytest -q` **2772 passed, 4 skipped** (vorher 2767) · ruff sauber ·
`export_openapi.py --check` unverändert.

#### ✅ H5–H8 — die vier Vorhaben der Use-Case-Liste, fertig 2026-08-10

Nutzer-Vorgabe: „es braucht Kuratierung, Neuerstellung mit KI, Erschliessung aus
einer Webseite und Ablage, Qualitätssicherung … antizipiere und arbeite typische
Flows mit ein, die auf verschiedene Tools zugreifen."

**H5 — drei Werkzeuge in den Katalog** (`get_url_text`,
`get_wikipedia_summary`, `wlo_auth_status`), je mit Argument-Modell.
`AuthStatusArgs` verbietet ausdrücklich Extras: ohne Modell reicht
`validate_tool_args` Rohargumente durch, und ein erfundenes Argument wäre eine
Server-Überraschung statt eines gefangenen Fehlers.

**Der Fund an der Vertrauensgrenze:** `get_url_text` und
`get_wikipedia_summary` liefern Prosa von Dritten — sie gehören also gerahmt.
Aber der vorhandene Rahmen sagt „FREMDINHALT **AUS DEM WLO-BESTAND**", und das
wäre über einer beliebigen Webseite schlicht falsch. **Die Herkunft ist genau
der Teil, an dem ein Modell sein Vertrauen ausrichtet** — ein Text, der als
kuratierter Bestand angekündigt wird, wiegt schwerer als einer aus dem offenen
Netz. Also ein **zweiter Rahmen** (`WEB_TEXT_TOOLS` + `WEB_FRAME_START`), gleiche
Regel, ehrliche Herkunft. Ein Test schliesst aus, dass sich die beiden Mengen je
überschneiden — sonst entschiede die Reihenfolge der `if`-Zweige still darüber,
was als vertrauenswürdiger angekündigt wird.

**H6 — M19 „Qualitätssicherung" (Prio 570) + Intent I10.** Die Kernfunktion ist
der **Soll-Ist-Abgleich**, den der Nutzer benannt hat: `get_compendium_text`
liefert das Soll, `get_collection_contents` + `get_collection_stats` das Ist,
und erst beides nebeneinander ergibt ein Urteil statt einer Aufzählung. Drei
Regeln tragen das Muster: jeder Befund wird **belegt**; was **nicht** geprüft
werden konnte, wird genannt (ein Bericht, der Nichtgeprüftes verschweigt, liest
sich wie ein Freispruch); und **gibt es keinen Kompendiumstext, fehlt der
Massstab** — dann wird das gesagt statt einer erfunden. M19 ist rein lesend; wer
einen Befund beheben will, wechselt zu M18.

**H7 — M20 „Webseite erschliessen und ablegen" (Prio 550) + Intent I11.** Eigenes
Muster und nicht Teil von M18, aus drei Gründen: der Gegenstand kommt von
**aussen** (eine Adresse, keine nodeId), der erste Schritt kann auf Arten
scheitern, die mit WLO nichts zu tun haben, und der geholte Text ist
**ungeprüfter Fremdinhalt**. Der Fünf-Schritte-Flow steht im Musterkörper, mit
der **Dublettenprüfung als Pflichtschritt vor jeder Neuanlage** — ein zweiter
Datensatz zur selben Adresse ist die häufigste vermeidbare Verschmutzung. Und:
Schritte 1–4 gehen anonym, nur Schritt 5 nicht; **das wird früh gesagt**, weil
ein fertiger Vorschlag, der dann nicht abgelegt werden kann, verschenkte Arbeit
der Person ist.

**H8 — Flows und Ergänzungen im Bestand.** `wlo_auth_status` an M18 (vor dem
Ankündigen einer Änderung ist die Auskunft besser als die Vermutung — und bei
`authenticated: false` erklärt sie, warum gleich alles scheitert);
`get_wikipedia_summary` + `get_url_text` an M10 als unabhängige Gegenprobe für
selbst erzeugte fachliche Aussagen.

**Bilanz: 20 Muster · 39 Katalog-Werkzeuge · 11 Absichten · genau EINES ohne
Muster** — `wlo_health_check`, die Betriebs-Sonde, mit begründeter Ausnahme im
Wächter.

Belege: `pytest -q` **2782 passed, 4 skipped** (vorher 2772) · ruff sauber ·
Vertrag unverändert. Die neuen Tests fahren je über den **echten Seed und den
echten Betriebspfad** und prüfen nicht „steht im Katalog", sondern **„kommt beim
Modell an, wenn dieses Muster gewinnt"**.

#### ✅ H9 — Skills hängen jetzt an Sammlungen, fertig 2026-08-10

Nutzer-Vorgabe: „Skills werden an Inhaltssammlungen zugeordnet. Es wird eine Art
Skill-Registry für jede inhaltliche Sammlung geben … diese Registry wird bei
jedem Sammlungsabruf vom MCP mitgeliefert … implementiere es, auch wenn es noch
keine Skills im Repo gibt."

**Drei Messungen am Server-Quelltext, und jede hat den Schnitt verändert:**

1. **`formatter.ts:317-348`** hängt die Registry-Kurzfassung (Titel + nodeId) an
   **jedes Sammlungs-Ergebnis** und schreibt wörtlich dazu „vollständig mit
   `get_skill_registry`" — plus einen Hinweis, wenn eine Sammlung *ungeprüft*
   ist. **Der Server verweist das Modell also auf ein Werkzeug, das wir nicht
   angeboten haben.** Ein Verweis ins Leere, aus derselben Klasse wie der
   `get_wlo_content_text`-Fund von 2026-07-31.
2. **`call_mcp_tool` gibt den Rohtext zurück** — kein Parser dazwischen. Die
   Kurzfassung **kam also schon beim Modell an**; gefehlt hat nur der zweite
   Schritt. Das war die angenehme Überraschung: die Befürchtung „unser Parser
   wirft das Feld weg" hat sich nicht bestätigt, gemessen statt vermutet.
3. **`server.ts:129` registriert `get_skill_registry` bedingungslos** — es
   braucht keine Konfiguration, und eine Sammlung ohne Registry sagt das
   schlicht. **Genau deshalb ist es baubar, bevor ein Skill existiert**: es
   verspricht nichts, was der nächste Schritt bricht.

**Gebaut:** `get_skill_registry` im Katalog (+ `SkillRegistryArgs`), in
**FREE_TEXT_TOOLS** — der Server schreibt seinen Warnsatz zwar selbst hinein,
aber der steht *im* Text und wäre damit fälschbar; der Rahmen kommt von aussen
und ist es nicht. Dazu `get_skill_registry` + `get_skill` in die **sechs
arbeitenden Muster** (M08, M09, M10, M18, M19, M20) — Erschliessung,
Qualitätssicherung und Beratung bei der Inhaltserstellung sind genau die Fälle,
für die die Redaktion Anleitungen hinterlegt.

**Und die Regel in die Musterkörper**, weil eine Werkzeugliste nur sagt, DASS
etwas gerufen werden darf, nicht WANN. Sie gilt in beide Richtungen: passt etwas
aus der Kurzfassung zur Aufgabe, wird es **vor** der eigenen Lösung geholt — die
Redaktion hat es für genau diesen Fall hinterlegt. Führt die Sammlung keine
Registry, wird **nicht danach gesucht** und nicht so getan, als gäbe es etwas;
**kein Skill zu haben ist ein normaler Zustand, kein Mangel.**

**Ein vierter Wächter hat mitgeredet:** `test_die_server_registry_kennt_jedes_
werkzeug_das_dem_modell_angeboten_wird` fiel, weil `05-knowledge/mcp-servers.yaml`
die vier neuen Werkzeuge nicht führte — genau die Lücke, für die er 2026-07-31
geschrieben wurde.

**H9b — die Lücke, die der Nachtrag-Durchgang fand:** M18/M19/M20 konnten die
Registry LESEN, aber den Katalog nicht DURCHSUCHEN. Führt eine Sammlung keine
Registry — oder hängt die Aufgabe an gar keiner, wie bei M20, das mit einer
blossen URL beginnt —, endete der Weg genau dort, wo die Redaktion vielleicht
etwas hinterlegt hat. `search_skill` nachgetragen, und die **Reihenfolge** in die
Prosa aller sechs Muster: Registry zuerst, Katalogsuche zweiter Weg, normal
lösen als dritter. Begründung im Text: *eine für DIESE Sammlung freigegebene
Anleitung schlägt eine, die nur thematisch ähnlich klingt* — und ein erfundener
Verweis wäre schlimmer als keiner. Beim Nachtragen fiel auf, dass **M09 die
Prosa fehlte**, obwohl es das Werkzeug führte; ein Werkzeug ohne die Regel, wann
es zu rufen ist, bleibt ungenutzt. Ein Test hält jetzt beides fest.

**Nichts zu tun bei `tool_descriptions.py`:** die Studio-Tooltips holen ihre
Texte per `tools/list` **vom Server** — es gibt keine abzugleichende Liste.

Belege: `pytest -q` **2807 passed, 4 skipped** (vorher 2782) · ruff sauber ·
Vertrag unverändert.

**Bewusst nicht gebaut: `get_skill_for_task`.** Der Server registriert
**entweder** `search_skill` + `get_skill` **oder** `get_skill_for_task`
(`WLO_SKILL_TOOL_MODE`, `server.ts:122`) — beide anzubieten hiesse, dass eines
davon in jedem Betrieb ins Leere zeigt. Wir bleiben auf der Zwei-Werkzeug-Fläche,
die der Katalog schon hat.

#### ⬜ H10 — was erst mit den ersten echten Skills entschieden werden kann

Unsere Seite ist fertig: Werkzeuge, Muster, Reihenfolge, Vertrauensgrenze und
Wächter stehen und laufen gegen einen leeren Bestand ehrlich („führt keine
Registry"). Was **noch nicht** entschieden werden kann, weil es einen echten
Skill zum Anschauen braucht:

| Frage | Warum sie warten muss | Woran man es merken wird |
|---|---|---|
| **Länge einer Anleitung** | Eine `SKILL.md` geht ungekürzt in den Prompt. Wie lang sie in der Praxis wird, ist unbekannt — bei mehreren Kilobyte konkurriert sie mit Muster, Persona und Verlauf | Antwortqualität sinkt bei Zügen mit geladenem Skill; im Zweifel ein Deckel wie bei `get_wlo_content_text` |
| **Ruft das Modell die Registry überhaupt?** | Die Kurzfassung steht im Sammlungs-Ergebnis, aber ob das Modell sie aufgreift, entscheidet es selbst | Golden-Lauf mit einer Sammlung, die eine Registry führt |
| **Begleitdateien** | `get_skill` listet weitere Dateien (Name + nodeId, ohne Inhalt). Ob eine Anleitung ohne ihre Vorlage brauchbar ist, zeigt erst eine echte | Anleitungen, die auf eine Datei verweisen, die niemand nachlädt |
| **`/skillname` (D3)** | Vom Nutzer zurückgestellt — und der Entwurf ist durch die Prozessänderung ohnehin überholt: ein Kurzbefehl müsste jetzt sammlungsbezogen sein | — |

**Was durch die Prozessänderung ERLEDIGT ist:** die neun `Skill-Scopes` aus dem
Ideen-Dokument (je eine Registry für kuration/qs/didaktik/…) sind überholt. Die
Zuordnung entscheidet jetzt die **Inhaltssammlung**, nicht ein Scope-Katalog auf
unserer Seite. Kein Grund, dafür Maschinerie zu bauen.

#### ⬜ H4 — offen: ein Server-Werkzeug ohne Katalog-Eintrag

| Werkzeug | Warum (noch) nicht |
|---|---|
| `get_skill_for_task` | **Nicht Lücke, sondern Alternative.** Der Server registriert entweder `search_skill` + `get_skill` **oder** dieses eine (`WLO_SKILL_TOOL_MODE`). Beide anzubieten hiesse, dass eines in jedem Betrieb ins Leere zeigt |

`get_skill_registry` ist mit H9 gebaut — die frühere Einschätzung „inhaltsgesperrt,
weil kein Skill im Bestand" war für dieses Werkzeug falsch: es wird
bedingungslos registriert und antwortet bei leerer Sammlung ehrlich mit „führt
keine Registry".

**Nachtrag 2026-08-11 — der Satz gilt für die QUELLE, nicht für jeden Betrieb.**
Gemessen: `registerSkillRegistryTool(server)` steht unbedingt in
`../../wlo-mcp-server-sc/src/server.ts:130` ✓ — aber der in dieser Sitzung
verbundene MCP-Betrieb registriert das Werkzeug **nicht**. Er läuft einen älteren
Build; der Registry-Entwurf ist serverseitig von heute. Der ältere
Referenz-Baum `../wlo-mcp-server` kennt weder `get_skill_registry` noch
`WLO_SKILL_TOOL_MODE`.

Das ist **Versionsversatz, kein Entwurfsfehler** — aber es zeigt, dass der
H4-Grundsatz („beide anzubieten hiesse, dass eines ins Leere zeigt") auch für
den Bestand gilt: M18/M19/M20 nennen `get_skill_registry`, und gegen einen
älteren Server zeigt es ins Leere.

Wie sich das im Betrieb äussert, ebenfalls gemessen (`mcp/client.py:235-244`):
der Aufruf scheitert **ehrlich** — das Modell bekommt `MCP error: …` als
Werkzeug-Ergebnis zurück und kann umschwenken. Es kostet aber einen zweiten
Round-Trip, weil der Client jeden Fehler einmal mit frischer Sitzung wiederholt;
bei „unbekanntes Werkzeug" ist die Wiederholung sicher vergeblich. Beides
ALT-verbatim und deshalb hier nicht angefasst.

**Die Lücke, die daraus folgte — geschlossen 2026-08-11 im Studio.** Niemand
verglich unseren Katalog mit dem, was ein Server *tatsächlich* registriert: die
Wächter prüfen `TOOL_DEFINITIONS` gegen `mcp-servers.yaml` — zwei Dateien von
uns, die einander bestätigen.

Nutzer-Kriterium: „regelmässig von einer Redaktion gebraucht ⇒ in den Studio,
seltene Testnutzung ⇒ CLI reicht". Die Messung entschied es und machte es
zugleich billiger: die Ansicht `mcp-registry.component` gibt es **schon**, mit
Prüf-Knopf — und sie hält **beide Seiten** bereits im Speicher (`found` aus
`discover`, `servers[].tools` aus der Registry). Sie verglich sie nur nicht.
Also Studio, ohne Backend-Änderung und **ohne den eingefrorenen Vertrag zu
berühren**.

Gebaut: reine `compareToolsets(erwartet, tatsächlich) → {missing, extra}`.
`missing` ist die tragende Richtung und steht zuerst — diese Werkzeuge bekommt
das Modell angeboten, der Server kennt sie nicht. `extra` ist nur ein Hinweis.
Zwei Fallen, beide gepinnt: verglichen wird gegen die **geprüfte** Adresse, nicht
gegen das Eingabefeld (das tippt sich weiter, das Ergebnis nicht); und ein
nachgestellter Schrägstrich griffe ohne Normalisierung daneben — der Abgleich
täte dann still nichts, statt zu sagen, dass er nichts tut. Rot-grün belegt.
studio 895 (+6).

**Betriebliche Vorbedingung für `get_url_text`, im Muster berücksichtigt:** der
Server erklärt es als *unsafe* (es reicht eine fremde Adresse an einen
Extraktionsdienst weiter, dessen Weiterleitungen er nicht sieht). Betreiber
können es per `WLO_DISABLE_UNSAFE_TOOLS` abschalten, und ohne
`WLO_TEXT_EXTRACTION_URL` antwortet es mit `service_disabled`. M20 unterscheidet
diese Fälle ausdrücklich — „der Betrieb hat keinen Extraktionsdienst" ist keine
Aussage über die Seite.

**Was der Goldlauf (Paket G) gezielt prüfen muss:** die Grenze M18 ↔ M13. M18
steht mit 545 über M13 (540); ob der Klassifikator „wie reiche ich ein" weiter
bei M13 lässt, entscheiden `when_not_to_use` und die Unterscheider — das ist
eine LLM-Entscheidung und gehört gemessen, nicht angenommen.

### Paket G — Goldreferenz neu

Nach F, weil jede Pattern-Änderung sie ohnehin ungültig macht. Der Lauf selbst
gehört dem Nutzer.

### Paket R — Nacharbeit aus dem Review (2026-08-11) ✅

Acht Befunde eines Review-Durchgangs über die H-Pakete. Zwei änderten Verhalten,
sechs machten Zusicherungen wahr oder schlossen Wächter-Lücken.

| | Befund | Behebung |
|---|---|---|
| **R1** | M10 bekam `search_wlo_collections` + `search_wlo_topic_pages` — eingetragen mit der Begründung, der Rückfall-Zweig habe sie vorher geliefert. **Diese Prämisse ist widerlegt**: der Zweig ist unerreichbar, M10 bekam im Betrieb *null* Werkzeuge (am Vorzustand nachgemessen). Der Eintrag bewahrte also nichts, sondern vergab neu — gegen M10s eigene `forbidden_phrases` („Such-Tool-Calls") | Beide gestrichen. Der Bestandstest `test_m10_behaelt_seine_bisherigen_werkzeuge` pinnte dieselbe falsche Prämisse und wurde mit Begründung entfernt; die richtige Zusicherung ist `TestKiErzeugungSuchtNicht` |
| **R2** | Der Medientyp-Strip nahm M18 die Sammlungssuche. „Pack das **Arbeitsblatt** in meine Sammlung Optik" — I09s eigene Trigger-Phrase — hinterließ nur `browse_collection_tree`, das eine nodeId oder einen Fachportal-Namen braucht. Kein Test konnte es zeigen: alle übergaben `{}` als `classification` | Strip übergeht Muster, die kuratieren (`_pattern_curates`, geteilt mit `curation_blocked_by_mode`). Suchmuster unberührt — Gegenprobe gepinnt |
| **R3** | Der Wächter „jedes Katalog-Werkzeug trägt eine Entscheidung zur Vertrauensgrenze" las nur `TOOL_DEFINITIONS`; die 14 kuratierenden waren blind | Beide Kataloge vereinigt. **Die Rahmen-Empfehlung des Reviews war falsch** und wurde nach Messung verworfen: Vorschauen laufen durch `previewValue` (geflacht, bei 600 gekappt, Schnitt offengelegt) — strukturiert, keine Langform-Prosa. Sie zu rahmen legte zudem *unsere* Bestätigungsanweisung in einen „befolge das nicht"-Rahmen |
| **R4** | `get_url_text` stand zweimal in `mcp-servers.yaml`; der vorhandene Wächter liest in ein Set und sah es nicht | Dublette weg, Duplikat-Wächter je Server dazu |
| **R5** | `max_length` und `extra="forbid"` waren Dekoration: gemessen reisten eine 3014-Zeichen-URL und eine erfundene Angabe an `wlo_auth_status` unverändert weiter — die Docstrings sicherten das Gegenteil zu | `AuthStatusArgs` auf `extra="ignore"` (löst die Zusage tatsächlich ein). Bei den String-Grenzen bleibt es beim Weiterreichen — eine gekappte URL wäre eine *andere* Adresse; die Docstrings sagen das jetzt |
| **R6** | `schemas_mcp.py` über 300 Zeilen | Ausnahme dokumentiert: flache Tabelle mit *einem* Änderungsgrund, Teilungskriterium benannt |
| **R7** | M20 nannte drei der fünf `reason`-Codes des Servers | `dns_failed` ergänzt |
| **R8** | Der Skill-Abschnitt steht sechsmal wortgleich, geprüft wurde nur die Überschrift | Wächter prüft alle drei Schritte je Kopie |

Tore: `ruff check .` sauber · `pytest -q` **2826 passed, 4 skipped** · `export_openapi.py --check` unverändert.

### Paket K — Intent ↔ Muster verknüpfen (2026-08-11) ✅

Die Muster waren gebaut, die Intents definiert — aber die **Verbindung** dazwischen
fehlte. Gemessen: Intents und Muster sind zwei getrennte Listen, die der
Klassifikator-Prompt nebeneinander rendert; verbunden werden sie nur an zwei
Stellen (Few-Shot-Beispiele, `when_to_use`-Prosa). An beiden fehlten I09/I10/I11.

| | Befund | Behebung |
|---|---|---|
| **K1** | **Der Lernpfad-Schnellweg kannte die drei neuen Intents nicht.** `_lp_blocking_intents` stand bei den vier alten. Der Weg feuert schon bei EINEM Stichwort im Satz, und „Unterrichtseinheit" steht in `_lp_keywords` — gemessen: „Prüf, ob die Sammlung für meine Unterrichtseinheit Optik reicht" (I10) löste ihn aus. Er läuft **vor** der Musterwahl, M19 kam nie zum Zug: statt einer Prüfung ein erzeugter Lernpfad | I09/I10/I11 in die Sperrliste. Rot-grün belegt |
| **K2** | Kein Few-Shot paarte die neuen Intents mit ihren Mustern — die Beispiele sind die einzige Prompt-Stelle, an der Intent und Muster gemeinsam auftreten | 6 Beispiele: je Paar eines plus die Abgrenzung, an der es kippt (I09↔I08, I10↔I03, I10↔I04) |
| **K3** | Zehn Bestandsmuster nennen ihren Intent in `when_to_use` (M09: „Intent I04 … UND Topic"); M18/M19/M20 taten es nicht | Zeile je Muster ergänzt |
| **K4** | Die Abläufe nannten die Werkzeuge nicht in ihrer Reihenfolge — M18 gar nicht | Abschnitt „Werkzeuge in der Reihenfolge": M18 Tabelle über 6 Vorhaben, M19 über 4 Prüffälle, M20 als Kette. Je mit der Begründung, warum die Reihenfolge trägt (M19: Soll vor Ist, sonst wird die Lücke nie sichtbar) |

Neu als Wächter: jeder Intent braucht ein Few-Shot mit Muster · Few-Shots dürfen
nur vorhandene IDs nennen · die drei Auftragsmuster nennen ihren Intent.

Sauber geblieben und deshalb nicht angefasst: keine verwaisten `redirect_to`/`vs`-Ziele
in `intents.yaml`, und **keine** Policy-Regel matcht auf `intent` — dort war nichts
nachzuziehen.

Tore: `ruff check .` sauber · `pytest -q` **2830 passed, 4 skipped** · `export_openapi.py --check` unverändert.

---

### Paket L — Was gepflegt aussieht, aber nie ankommt (2026-08-11) ✅

Die Nachprüfung von K stellte eine Frage, die K nicht gestellt hatte: *erreichen die
Zeilen, die wir schreiben, das Modell überhaupt?* Gemessen — nein.

Beide Renderer kappen jede Liste: Muster bei fünf Einträgen
(`classify_prompt_blocks.py:334`), Intents bei 20/8/8/6. Das ist **ALT-verbatim**
(`llm_classify_prompt.py:596`), und ALT nennt den Vertrag im Kommentar daneben
ausdrücklich: „when_to_use (positive Trigger, **3-5 Items**)". Der Deckel ist also
kein Fehler — die neuen Einträge hielten den Vertrag nicht ein, und der Überlauf
fällt lautlos hinten runter. Er steht im Studio, wirkt gepflegt, wird nie gelesen.

| | Befund | Behebung |
|---|---|---|
| **L1** | **M18 `when_to_use` hatte 9 Einträge — 4 abgeschnitten**, darunter „User bestätigt im Folgezug eine gezeigte Vorschau (`ja`, `mach`)": die zweite Hälfte des zweistufigen Änderungswegs. K3 hatte den Überlauf um eine Zeile verschärft | auf 5 zusammengefasst; jedes Verb bleibt als Beispiel in Klammern erhalten |
| **L2** | M18 `trigger_phrases` 8 → 3 abgeschnitten, darunter **„Lösch den Eintrag"** — der einzige zerstörende Fall. „Erstell eine Sammlung dafür" trug dagegen dasselbe wie „Leg das in WLO an" | 5 möglichst VERSCHIEDENE Verben statt 8 ähnlicher |
| **L3** | M19 `when_to_use` 6 und `trigger_phrases` 6 → je 1 abgeschnitten | zusammengefasst; „Deute mir die Kennzahlen" blieb, weil nur diese Zeile den Fall trifft |
| **L4** | **I09 `trigger_verbs` hatte 22 — abgeschnitten waren `lösch den eintrag` und `lösche die sammlung`.** Und die Deckel sind gestaffelt: Judge 10, Szenarien-Erzeugung 12, Klassifikator 20. Auf Position 21/22 war das Löschen in **allen dreien** unsichtbar — ausgerechnet die Operation, die sich nicht zurücknehmen lässt | 2 Paare zusammengefasst (`leg an / lege an`, `vorschlag annehmen oder ablehnen`); Löschen auf Position 8/9 vorgezogen, also innerhalb aller drei Deckel |
| **L5** | I09 `examples` 10 → 4 abgeschnitten, I10 `examples` 8 → 2 | je 6, die je eine ANDERE Operation abdecken; bei I10 rückt die Dublettenfrage nach, die sonst kein Beispiel trifft |

Neu als Wächter: **`test_jede_gepflegte_zeile_erreicht_den_klassifikator`** rendert
die ECHTEN Blöcke und sucht jede Seed-Zeile darin — er hängt damit an keiner
Deckel-Zahl, sondern verschiebt sich mit, wenn jemand einen Deckel verschiebt.
Dazu `test_die_erlaubnisliste_bleibt_ehrlich`: kürzt jemand eine ALT-Liste, muss
ihre Ausnahme verschwinden, sonst deckt sie ab da einen NEUEN Überlauf mit ab.
Gegenprobe gefahren — die Erlaubnisliste ist deckungsgleich (11 = 11), ein
Zusatzeintrag würde gemeldet.

Geduldet mit Beleg: 11 Überläufe stehen im ALT-Baum genauso (teils länger, ALT
`I03.examples` hat 13). Sie zu kürzen wäre eine Verhaltensänderung am Bestand —
ein anderer Vorgang.

**Geprüft und bewusst NICHT geändert:**

* *Sind die Abgrenzungen gegenseitig?* 16 einseitige gefunden (M18→M08, aber nicht
  zurück …) — **kein Befund.** `_render_patterns_hint_block` wird **einmal mit
  allen Mustern** aufgerufen; der Klassifikator sieht sämtliche Diskriminatoren
  gleichzeitig. ALT ist ebenfalls gemischt. Die 16 nachzutragen hätte bei M10
  (Kopfraum 0) und M17–M20 (Kopfraum 1) andere Diskriminatoren über den Deckel
  geschoben — der „Fix" hätte den Schaden erst angerichtet.
* *Braucht der Spekulativ-Prefetch die neuen Intents?* Nein. `_spec_search_intents`
  bleibt `{I03, I04}`: M19 beginnt mit `get_compendium_text`, M20 mit
  `get_url_text` — eine vorgezogene Suche wäre verworfene Arbeit und verbögen den
  Themenseiten-Index des MCP-Servers (Kommentar `prefetch.py:77-81`).
* *M17 nennt keinen Intent* — wie M01/M02/M07/M08/M12/M16 auch. Diese Muster sind
  situations- statt intent-getrieben; M17 ist damit konsistent mit seinen Nachbarn.

Tore: `ruff check .` sauber · `pytest -q` **2832 passed, 4 skipped** · `export_openapi.py --check` unverändert.

---

## 6. Was bewusst draußen bleibt

| | Grund |
|---|---|
| `search`, `fetch` | ChatGPT-Konvention, redundant zu `search_wlo_all` |
| `get_skill_for_task` | Alternativmodus des Servers (`WLO_SKILL_TOOL_MODE=one-tool`), schließt D1 aus |
| Ein **eigener** OAuth-Server | Die Anmeldung gehört dem MCP-Server. Nicht zu verwechseln mit der Empfehlung oben: dort werden wir sein *Client* (öffentlich, PKCE, keine eigene Nutzerverwaltung) — das ist kein zweiter Anmeldedienst, sondern die Nutzung seines vorhandenen |
| Umbenennung M01–M17 → S-/B-/P- | Kauft keinen Fähigkeitspunkt, macht drei Bezugssysteme gleichzeitig ungültig |

**Zurückgenommen in H5 (2026-08-10):** `get_url_text` und `get_wikipedia_summary`
standen hier zunächst mit Gründen, die die Nutzer-Vorgabe überholt hat — die
Erschliessung einer Webseite (M20) *braucht* den Volltext, und die Gegenprobe bei
KI-Erzeugung (M10/M19) braucht die unabhängige Quelle. Beide sind jetzt im
Katalog; `get_url_text` bleibt serverseitig als unsicher geführt und abschaltbar,
und für WLO-Material weist seine Beschreibung weiter auf `get_wlo_content_text`.
Der deterministische Wikipedia-Aufruf in `wikipedia_service.py` bleibt daneben
bestehen — er bedient einen anderen Auslöser (Canvas-Quellenangabe, nicht
Modellentscheidung).
