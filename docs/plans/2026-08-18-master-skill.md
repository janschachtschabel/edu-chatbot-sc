# Master-Skill als Systemprompt + höhere Deckel (Nutzer-Auftrag 2026-08-18)

Repo: `boerdi-chat`. Fünf Pakete, in dieser Reihenfolge.

## Auftrag (wörtlich zusammengefasst)

1. Option: im **Agent-Modus** wird ein „Master-Skill" **initial** gelesen.
2. Zwei Umgebungsvariablen: **Knoten-ID** (`535cabca-47e4-4cbf-9cab-ca47e40cbf4e`)
   und **Ein/Aus**.
3. Der Text steht **ganz am Anfang** des Systemprompts — damit Prompt-Caching greift.
4. Zusätzlich hinein: die **chatbot-eigenen Anteile**, die außerhalb der Anleitung
   gebraucht werden — Ergebnisfenster, Schnellantwort-Pillen, Struktur.
5. Auch **beim Einbetten** des Widgets an-/abschaltbar (Parameter).
6. Danach **README und Doku** für Browser-Plugin und edu-sharing überarbeiten.
7. **Kontextfenster** für Agent und Hybrid erhöhen, **bis zu 30 Züge**.

## Entscheidungen, die ich treffe (Widerspruch willkommen)

| Frage | Entscheidung | Grund |
|---|---|---|
| Vorgabe des Schalters | **aus** (`MASTER_SKILL_ENABLED=false`), Knoten-ID vorbelegt | Es ist eine Option. Angeschaltet kostet sie einen MCP-Abruf und ändert das Verhalten — das gehört zu einer bewussten Handlung, wie beim CORS-Schalter umgekehrt. |
| Vorrang Umgebung ↔ Widget | Umgebung = **Vorgabe**, Widget-Parameter **übersteuert** je Einbettung | „auch beim Einbinden möglich" heißt beides — an und aus. Ein Gastgeber, der den Master-Skill nicht will, darf ihn abschalten, und umgekehrt. |
| Wo im Prompt | **erste** System-Nachricht, vor allem anderen | Caching greift nur auf einem stabilen Präfix. Alles Wechselnde (Seitenkontext, Gastgeber-Rahmen) bleibt dahinter. |
| Abruf | `get_skill(nodeId, includeFiles=false)` über MCP, **Prozess-Cache mit TTL** | Ein MCP-Aufruf steht gemessen 1,2–23,3 s. Pro Zug erneut wäre unbrauchbar. |
| MCP nicht erreichbar | Lauf geht **ohne** Master-Skill weiter, WARNUNG im Log | Ein Chat, der wegen einer Anleitung nicht antwortet, ist schlechter als einer ohne sie. |
| Nur Schleife | Nur `agent` und `hybrid` (`laeuft_ueber_die_schleife`) | Der Muster-Weg hat seine Anweisungen aus der Config; zwei Quellen wären zwei Wahrheiten. |

## N1 — Deckel hoch (30 Züge)

`domain/config_models/engine.py` (Modell-Vorgabe) **und** `seeds/01-base/engine.yaml`
**und** die Live-Zeile im Config-Store — die drei wandern gemeinsam, sonst gilt
nichts davon (Erfahrung vom 2026-08-18, Paket K3).

- `max_iterations: 20 → 30`
- `deadline_s: 300 → 600`
- `token_budget: 400000 → 900000`

Rechnung, damit die Zahlen nicht geraten sind: gemessen ~15 300 Token je Runde,
und die Kette wächst — 30 Runden landen grob bei 700–800k. 900000 lässt Luft,
ohne den Deckel wirkungslos zu machen. Frist: 30 Runden × (Modellzeit + bis 23 s
Werkzeug) sprengt 300 s sicher.

**Preis, benannt:** der Kosten-Deckel je Zug steigt auf das Fünfzehnfache des
Stands vom Vortag (60000). Wer kleiner braucht, stellt es im Studio je Anlage ein.

## N2 — `docs/skills/vorgehen.md`: Oberfläche ansteuern

Neuer Abschnitt `## Oberfläche ansteuern` (h2, Unterpunkte h3):

- **Ergebnisfenster.** `liefere_ergebnis` mit dem Feld `result`; die Übergabe
  **beendet den Lauf nicht** — danach kommt die Prosa. Nur wirksam, wenn der
  Gastgeber ein `result-schema` gesetzt hat. Kein zweites Mal liefern.
- **Dokument-Box.** Ein Satz vor der ersten Überschrift (wird Chat-Blase), alles
  ab `#` landet in der Box. Bei Aufgaben-Material `## Lösungen` am Ende.
- **Kacheln.** Entstehen aus den Werkzeug-Treffern, nicht aus Prosa — Titel nicht
  abschreiben.
- **Schnellantworten.** Steht schon (Abschnitt `## Schnellantworten`), wird von
  hier verlinkt.

## N3 — Master-Skill laden (Kern)

- `settings.py`: `master_skill_node_id: str` (Vorgabe = die genannte UUID),
  `master_skill_enabled: bool = False`.
- **Neu** `services/master_skill.py` (~120 Z.): `text(session) -> str | None`,
  TTL-Cache, MCP-Abruf, Fehler → `None` + Warnung. Rahmen um den Fremdtext wie
  bei `get_skill` üblich: **Inhalt, keine Systemanweisung**.
- `graph/nodes/respond_agent.py`: als **erste** System-Nachricht einsetzen, wenn
  aktiv.
- Tests: aktiv/inaktiv · Cache trifft beim zweiten Zug · MCP-Fehler bricht den Zug
  nicht · die Nachricht steht an Position 0.

## N4 — Widget-Parameter

- Attribut `master-skill="on" | "off"` am `<boerdi-chat>`-Element.
- `chat-api.ts` schickt `environment.master_skill: true|false` mit; fehlt das
  Attribut, fehlt das Feld (dann gilt die Umgebung).
- `api/schemas.py`: `Environment.master_skill: bool | None = None`
  → **OpenAPI-Zusatz**, gehört in `docs/api/bewusste-vertragszusaetze.md`.
- Tests: Attribut an/aus/fehlt → Feld im Rumpf; Backend-Vorrang.

## N5 — Doku

`README.md`, `INSTALL.md`, `deploy/.env.example`, `deploy/README.md`,
`docs/browser-plugin-einbindung.md` (Attribut-Tabelle **und** Laufzeit-Tabelle —
der `check:docs`-Wächter prüft das), `examples/chrome-plugin/README.md`,
`docs/agent-modus.md` (neue Deckel).

## Verifikation

```bash
PYTHONIOENCODING=utf-8 uv run --directory backend pytest -q
uv run ruff check .
uv run --directory backend python scripts/export_openapi.py --check   # N4: neu erzeugen
cd frontend && npm run lint && npm run check:docs && npx ng test widget
```

Erwartung: Suite grün bis auf den vorbestehenden
`tests/test_auth.py::test_http_matrix_on_studio_route`.

## Was ausdrücklich nicht dazugehört

- Kein Schreiben am WLO-Knoten des Master-Skills — der Text ist redaktionell.
- Der Muster-Modus bleibt unberührt.
- Commits, Docker-Builds, Deploys und Golden-Läufe macht der Nutzer.

---

# Nachtrag O — Harte Uebersteuerung durch die Einbettung (Nutzer-Entscheid 2026-08-18)

Auftrag: das Browser-Plugin muss den Chatbot als Kuratierungswerkzeug fahren
koennen. Drei Bausteine, alle drei gewaehlt; A als benannte Modi.

## Der Befund, der C ausloest — und seine Korrektur

`show-cards` und `inline-result-grouping` sind **reine Frontend-Attribute** — sie
stehen nicht im `environment` und erreichen das Modell nie. Gemessen am Rumpfbau
in `chat-api.buildEnvironment`.

**Die zweite Haelfte des Befundes war falsch und ist zurueckgenommen** (geprueft
am `chat-shell.component.html`, bevor gebaut wurde): der erste Entwurf behauptete,
wer die Kacheln abschalte, bekomme trotzdem „siehe die Kacheln unten". Die beiden
Zweige `!cardsVisible` und `cardsVisible` sind aber vollstaendig und schliessen
einander aus — Treffer erscheinen IMMER, entweder als Kacheln mit Vorschaubild
oder als Textlinks in Boxen. `show-cards` waehlt zwischen diesen Darstellungen,
es schaltet nichts ab.

**Folge:** `show_cards` wurde aus dem Vertrag wieder ENTFERNT. Ein Feld, das nur
eine Lage beschreiben kann, die es im Produkt nicht gibt, ist schlimmer als
keines. Bleibt `inline_result_grouping` — dessen Wirkung ist real und steht in
`grouping/result-grouping.displayContent`: ohne Gruppierung bleiben die
Aufzaehlungs-Links im Antworttext stehen, statt in die Boxen zu wandern.

## O-A — Werkzeug-Erlaubnis je Einbettung

Attribut `tool-mode` mit drei benannten Modi (keine freie Liste: eine
Umbenennung im MCP wuerde sonst still Rechte aendern):

| Modus | was drin ist |
|---|---|
| `read-only` | nur lesende WLO-Werkzeuge (`search_*`, `get_*`, `lookup_*`) |
| `curate` | dazu die schreibenden `wlo_*` — weiterhin zweistufig |
| `full` | alles, inkl. Wikipedia/URL-Text und Skills (Vorgabe) |

Backend: Filter in `services/agent_tools.build_agent_tools`. Die virtuellen
Werkzeuge (`waehle_vorgehen`, `liefere_ergebnis`, …) bleiben IMMER drin.

## O-B — Erzwungene Schnellantworten je Zug

`setQuickReplies([...])` am Element + Attribut `quick-replies` (JSON-Array) als
Vorgabe. Feld `environment.forced_quick_replies`. Das Backend hat die Mechanik
schon (`turn_assembly._canvas_forced_quick_replies`) — sie wird nur nach aussen
gefuehrt. Deckel: Anzahl begrenzt, Text NICHT gekuerzt (der Chip IST die
Nachricht).

## O-C — Das Modell erfaehrt die Grenzen

Neues `environment.show_cards` (das Widget schickt sein Attribut mit) und ein
reiner Prompt-Block `domain/host_capabilities.py`:

* keine Kacheln -> „nenne Treffer im Text mit Titel und Link"
* keine Gliederung -> „schreibe die Gliederung selbst"
* `read-only` -> „du kannst in dieser Anwendung nichts aendern"

Steht im stabilen Praefix hinter dem Master-Skill, vor dem Seitenkontext.

## Vertrag

Drei neue `Environment`-Felder (`tool_mode`, `forced_quick_replies`,
`inline_result_grouping`) -> OpenAPI neu erzeugen + in
`bewusste-vertragszusaetze.md`. Alle drei `None`/leer = heutiges Verhalten.

## Stand 2026-08-18 — O komplett verdrahtet

| Baustein | Backend | Frontend |
|---|---|---|
| O-A | `host_capabilities.erlaubt` + Filter in `build_agent_tools(tool_mode=…)`, durchgereicht aus `respond_agent` | Attribut `tool-mode`, `shell.setToolMode` |
| O-B | `assemble._erzwungene_chips` (Gastgeber vor Canvas, Deckel 6, Text nie gekuerzt) | Attribut `quick-replies` (JSON), `el.setQuickReplies([...])` |
| O-B2 (2026-08-20) | Mix-Modus: `Environment.quick_replies_max` -> `domain/quick_reply_policy.host_qr_max` (Klammer 1-6, nur mit eigenen Host-Chips) -> `assemble._host_mix_max` -> Kaskaden-Zweig in `turn_assembly` (Host-Chips vorn, Inline-QRs oder Generator `count=Rest`, Dedupe) + `widget_postprocess` (Host-Zahl ersetzt Anzeige-Deckel). Wunsch der Plugin-Entwickler: „max. 4, davon 2 hardcodiert, Rest KI". | Attribut `quick-replies-max` (`_attrPositiveInt`), `el.setQuickRepliesMax(4)`; Host-Attribute 31 -> 32 |
| Y1/Y2 (2026-08-20) | Y1: Kernbegriff-Suchregel im Finden-Teil von `vorgehen.md` (Live-Befund Repo-Einbettung: ganzer Nutzersatz als `query` -> verwaesserte Treffer + haessliche Such-Links); Waechter `test_vorgehen_md_traegt_die_kernbegriff_suchregel`. Y2: geprueft — `intercept-edu-sharing-links` ist BEREITS Opt-in (Default `false`, widget.component.ts:146); kein Code noetig, stattdessen Pin-Test + Vertrag dokumentiert (wer abfaengt, navigiert selbst; Same-Route braucht `onSameUrlNavigation: 'reload'`). | Skill-Knoten `535cabca…` neu publizieren |
| Z1 (2026-08-20) | Nachschlag zu Y1, Befund: die ``query``-BEISPIELE der Werkzeug-Beschreibungen lehrten das Anti-Muster selbst ("Bruchrechnung Grundschule" / "Bruchrechnung Klasse 7"). Beide neu: Kernbegriff + die drei Filter-Dimensionen beim Namen (discipline/educationalContext/learningResourceType); wirkt in JEDEM Agent-Zug, auch ohne Master-Skill. Finden-Regel in vorgehen.md nennt jetzt alle vier Dimensionen; Waechter verschaerft + neuer Beschreibungs-Pin. | — (nur Backend-Prompt-Flaeche) |
| O-C | `host_capabilities.prompt_block` als 3. System-Block (hinter Master-Skill, vor Seitenkontext) | Attribut `inline-result-grouping` erreicht jetzt das `environment` |

Host-Attribute 29 -> 31 (Waechter-Spec, Studio-`HOST_ATTRIBUTES` + i18n,
Laufzeit-Tabelle). Widget-Bundle neu gebaut: 544,13 kB roh / 158,45 kB gzip.

---

# Paket P — Die Wissensdatenbank in der Agent-Schleife (Nutzer-Auftrag 2026-08-18)

Auftrag (woertlich): „Vielleicht die Nutzung des RAGS — da hatte ich in
Erinnerung das wir das bisher Pattern abhaengig triggern koennen. DA sollte dann
gelten immer alle Wissensbereiche ausser man spricht explizit einzelne an oder
schliesst sie aus."

## Der Befund — groesser als vermutet

Nicht „musterabhaengig getriggert", sondern **im Agent-Modus gar nicht
vorhanden**. Gemessen: `query_knowledge` wird ausschliesslich in
`response_tool_selection._select_active_tools` gebaut und in `tool_loop`
bedient — beides Muster-Weg. Die Agent-Schleife hatte weder den Vorabruf der
`mode: always`-Bereiche noch das Werkzeug. Jede Frage nach WLO, OER oder
edu-sharing lief dort ins Modellgedaechtnis.

Alle neun Bereiche in `05-knowledge/rag-config.yaml` stehen auf `mode: always`.

## Was gebaut wurde

* **Neu `services/agent_knowledge.py`**: `wissen_werkzeug(rag_config)` baut die
  Erklaerung (alle Bereiche im `enum`, ihre Beschreibungen im Beschreibungstext),
  `bereiche_aufloesen` setzt die Vorgabe („alle") gegen `bereiche`/`ohne` durch,
  `antwort` ruft `get_rag_context` und gibt IMMER Text zurueck — nie eine
  Ausnahme.
* **`agent_loop`**: neue Naht `wissen` (Rueckrufkarte, keine DB-Sitzung — die
  Schleife bedient auch `/api/agent`, und der hat keine). Der Name wird VOR dem
  MCP-Aufruf abgefangen, virtuell wie `submit_result`.
* **`respond_agent`** baut Werkzeug und Handler aus `ctx.rag_config`;
  `respond` reicht dafuer die `session` durch.

## Drei Entscheidungen, benannt

| Frage | Entscheidung | Grund |
|---|---|---|
| Vorabruf wie im Muster-Weg? | **Nein** | Die Schleife beantwortet auch „hallo". Eine Einbettung ohne WLO-Bezug zahlte fuer Wissen, das niemand braucht. |
| Alle Bereiche auf einmal? | **Ja, als Vorgabe** | `get_rag_context` bettet die Frage EINMAL ein und durchsucht nebenlaeufig; die Punktzahlen sind bereichsuebergreifend vergleichbar. „Immer alle" kostet eine Einbettung, nicht neun. |
| Name `query_knowledge`? | **Nein, `wissen_suchen`** | Das gleichnamige Muster-Werkzeug nimmt EINEN Bereich als Pflichtfeld. Ein Name mit zwei Formen ist die zweite Wahrheit, an der Doku auseinanderlaeuft. |

**Benannte Abweichung vom Muster-Weg:** dort schaltet `sources` ohne `rag` die
Wissensdatenbank ab. In der Schleife steht `wissen_suchen` in
`VIRTUELLE_WERKZEUGE` und bleibt auch nach einer Musterwahl im Hybrid erreichbar
— genau die Vorgabe „immer alle Wissensbereiche".

---

# Paket Q + R — Wissensbereiche steuern und sichtbar machen (2026-08-18)

## Q — je Bereich fuer die Schleife an-/abschaltbar

Auftrag: „dann sollten wir alle rag bereiche fuer den agent nutzen oder wir
fuehren neben der bisherigen steuerung noch eine option ein um es im agent zu
nutzen oder nicht." — **beides**: die Vorgabe bleibt „alle", und wer will, waehlt
einzeln ab.

`RagAreaDef.agent: bool = True` neben `mode`. Gelesen von
`agent_knowledge.fuer_die_schleife`; `mode` bleibt dem Muster-Weg. Zwei Felder,
weil „im Muster vorab, in der Schleife gar nicht" sonst nicht ausdrueckbar waere.
Im Studio auf der Wissen-Seite editierbar (rag-config steht dort schon).

## R — der Befund zum Studio

Geprueft, was der Nutzer aufzaehlte („Bereiche anlegen, beim Einlesen
auswaehlen, Dokumente spaeter loeschen und ansehen"): **alles vorhanden** —
`views/rag-areas`, `rag-ingest`, `rag-documents` plus `core/rag-api.service`
mit `deleteArea`, `deleteDocument`, Dokument-Detail und drei Einlese-Wegen
(Datei, URL, Text), jeder mit Bereichsangabe. Ein neuer Bereich entsteht durch
Tippen im Einlese-Formular.

**Was fehlte, ist die Verbindung.** Es gibt ZWEI Listen:

| Quelle | Inhalt |
|---|---|
| `services/rag/admin.list_areas` (gruppiert `RagChunk.area`) | was eingelesen wurde |
| `config_loader.load_rag_config` (Eintraege MIT `mode`) | was der Chatbot durchsucht |

Ein im Studio getippter Bereich landet nur links. Der Chatbot durchsuchte ihn
nie, und nichts sagte es — der Fehler sieht aus wie ein Bedienfehler.

**Gebaut:** `domain/rag_areas.zusammenfuehren` (rein) fuehrt beide Listen
zusammen und setzt je Bereich `configured`; `GET /api/rag/areas` liefert das,
inklusive Zeilen fuer konfigurierte Bereiche ohne Dokumente (der Gegenfall:
angekuendigt, aber immer leer). Das Studio markiert den Fall im Bereichs-Panel.

**Ausdruecklich NICHT gebaut:** die automatische Uebernahme eines eingelesenen
Bereichs in die Konfiguration. Sie machte jeden Probe-Upload zu einer Freigabe
im Betrieb. Sichtbar machen statt still beheben.

---

# Paket S — Die Wissens-Formulare gegen den alten Bot (2026-08-18)

Auftrag: „pruefe die formularfelder im studio — vieles sind noch freitext
eingaben und beim anlegen vom neuen wissen oder dokumenten sehe ich keine
auswahlmoeglichkeit fuer den wissensbereich — auch das gezielte chunks ansehen
habe ich glaube nicht gesehen."

## Der Vergleich (`../badboerdi/studio/src/components/KnowledgeManager.tsx`)

| ALT | NEU vorher | Befund |
|---|---|---|
| `<select>` der Bereiche + Feld „neuer Bereich" | Freitext mit `datalist` | **fehlte** — S2 |
| Modus je Bereich als Umschalter | Textfeld im Formular | **Freitext** — S1 |
| Verwaiste Konfig-Eintraege mit „Entfernen" | seit R sichtbar (Zeile mit 0) | teilweise |
| Chunks je Dokument ansehen | Knopf „Volltext anzeigen" → nummerierte Abschnitte | **war da** — S3 nur benannt |

## S1 — `mode` ist eine Auswahl

`RagAreaDef.mode: Annotated[str, Choices("always", "on-demand")]`. Ein
Tippfehler nahm den Bereich bis dahin still aus der Nutzung:
``load_rag_config`` behaelt nur Eintraege MIT ``mode``, und ein leeres Textfeld
sagte das niemandem.

## S2 — der Bereich wird gewaehlt, nicht getippt

Der Modulkopf von `rag-ingest.component.ts` begruendete das Textfeld mit „einen
bestehenden Bereich zu waehlen und einen neuen zu benennen ist derselbe
Vorgang". **Beide Haelften sind widerlegt:** eine `datalist` ist unsichtbar, bis
jemand tippt (der gemeldete Befund), und es ist NICHT derselbe Vorgang — ein
neuer Bereich braucht zusaetzlich den Eintrag in `rag-config` (Paket R).

Jetzt: `select` der vorhandenen Bereiche, `__neu__` oeffnet das Namensfeld mit
dem Hinweis, was noch fehlt. Ohne einen einzigen Bereich fragt das Panel direkt
nach dem Namen — ein leeres Auswahlfeld waere eine Sackgasse.

## S3 — die Abschnitte waren da, hiessen nur anders

Der Knopf hiess „Volltext anzeigen" und oeffnet die nummerierten Abschnitte.
Gesucht wurde nach „Chunks"/„Abschnitten" — die Zeile darueber zaehlt sie so.
Beschriftung angeglichen: „Abschnitte anzeigen".

## Der Fund darunter: die Studio-Schemata hatten kein Gate

`area-schemas.fixture.ts` ist nicht bloss Testdatum — das Studio baut seine
Bereichs-Formulare daraus. Nichts verglich sie mit den Modellen. Gemessen: seit
Paket H1 fehlte im Studio der Maschinen-Wert **`hybrid`**; der Umschalter bot
nur `pattern|agent`. Zwei Tage unbemerkt.

Behoben an der Wurzel: `export_area_schemas.py --check` + `tests/test_area_schema_fixture.py`.
Gegenprobe gefahren (Fixture verfaelscht -> Rueckgabe 1, Meldung nennt den Weg).

## Was ich NICHT gebaut habe

* **Modus-Umschalter in der Bereichsliste** (ALT hatte ihn). Er war dort ein
  Notbehelf: das alte Studio parste `rag-config.yaml` von Hand und hatte kein
  Formular. Das neue hat eines, auf derselben Seite, jetzt mit Auswahlfeld.
* **Weitere Freitext-Felder auf Auswahl umstellen.** Gemessen als Kandidaten:
  `canvas/material-types.category` + `.structure`, `base_widget.kind` +
  `.action`, `dimensions.length`. Bei allen kenne ich den VOLLSTAENDIGEN
  Wertevorrat nicht — nur die im Seed vorkommenden. Eine unvollstaendige
  Auswahlliste ist schlechter als ein Textfeld: sie sieht verbindlich aus.
  Nutzer-Entscheid noetig.

---

# Paket T — Die Suite ist gruen (2026-08-18)

`tests/test_auth.py::test_http_matrix_on_studio_route` galt die ganze Sitzung als
„vorbestehend rot". Es waren **zwei** Fehler in einem Test, beide Aussagen ueber
die Werkbank statt ueber den Code — und ich habe sie erst gefunden, nachdem ich
aufgehoert habe zu raten und die Fehlermeldung ganz gelesen habe.

## T1 — der Einstellungs-Cache

Gemessen mit ``get_settings.cache_info()`` am Rumpfbeginn: ``currsize=1`` mit dem
LEEREN Schluessel. Der autouse-``_fresh_settings_cache`` leert ihn, die
Fixture-Phase fuellt ihn danach wieder. ``require_studio_key`` las also den
leeren Schluessel und antwortete **503** („Admin abgeschaltet, fail-closed")
statt 401.

**Das Produkt war richtig.** Gegenprobe ausserhalb von pytest: 401 ohne
Schluessel, 501 mit dem richtigen. Behoben, wo die conftest-Doku es ohnehin
vorschreibt: ``get_settings.cache_clear()`` nach dem ``setenv``.

## T2 — das Widget-Bundle

Die letzte Zeile verlangte ``== 503`` mit der Begruendung „im Test gibt es kein
Widget-Bundle". Sobald jemand ``npm run build:widget`` laufen liess, kam 200 —
und der Test wurde rot. Gepinnt wird jetzt die ZUSAGE (die Route ist oeffentlich,
also nicht 401), nicht der Zufall der Werkbank: ``in (200, 503)``.

## Was daraus zu lernen war

Ich habe drei Korrekturversuche an der falschen Zeile gemacht, weil ich die
erste Assertion fuer die scheiternde hielt, ohne die Meldung zu lesen. Die
Ursache stand von Anfang an im Ausgabetext.

**Stand:** 3962 Tests gruen, 4 uebersprungen, 0 rot.

---

# Durchsicht der Pakete O–T (2026-08-18)

Verdikt: **0 kritisch, 0 schwer, 2 leicht, 1 Kleinigkeit.** Beide leichten Funde
behoben, die Kleinigkeit begruendet abgelehnt.

## Fund 1 — das Praefix trennte nicht sauber

``erlaubt`` las ``wlo_`` als „schreibend". Gemessen: zwei LESENDE Werkzeuge
tragen dasselbe Praefix — ``wlo_auth_status`` und ``wlo_health_check``. In einer
``read-only``-Einbettung fiel damit die Frage „ist die Person angemeldet?" weg.

Behoben mit :data:`LESENDE_WLO_WERKZEUGE`, und ein Waechter haelt die Ausnahme in
BEIDE Richtungen fest: jeder Name der Liste muss im Lese-Katalog stehen und darf
nicht im Kuratier-Katalog — und kein kuratierendes Werkzeug darf dem Praefix
entkommen (das waere ein Loch, keine Unbequemlichkeit).

Ein Bestandstest prueft seither die ZUSAGE statt der Faustregel: nicht „kein
Name faengt mit ``wlo_`` an", sondern „kein Name aus dem Kuratier-Katalog ist
dabei".

## Fund 2 — der neue Bereich fiel aus dem Formular

Nach dem ALLERERSTEN Einlesen in eine leere Wissensbasis machte
``refreshAreas()`` die Liste nicht-leer, ``auswahl`` stand aber noch auf ``''``
— ``neu()`` kippte, das Namensfeld verschwand, ``area()`` wurde leer. Wer ein
zweites Dokument in denselben Bereich legen wollte, musste ihn neu waehlen.

Behoben: ``send()`` setzt nach Erfolg ``auswahl`` auf den benutzten Bereich.

## Kleinigkeit — bewusst nicht geaendert

``Environment.forced_quick_replies`` hat keine ``max_length``; gedeckelt wird
erst beim Verbrauch (sechs). Ein Schema-Deckel wiese den GANZEN Zug mit 422 ab,
wenn ein Gastgeber sieben Chips setzt — schlechter als still zu kuerzen und zu
protokollieren. Die Rumpfgroesse begrenzt der Server; dieselbe Linie gilt schon
fuer ``page_context`` und ``host_instruction``.

**Stand nach der Durchsicht:** 3966 Tests gruen, 4 uebersprungen, 0 rot.


---

## Paket U — Der Bot zeigte auf Produktion, der MCP auf Staging

**Ausloeser** (Nutzer 2026-08-19, aus der Startzeile heraus): „es darf nur auf
staging zeigen — wenn da irgendwo noch die produktion steht, bitte aendern."
Der Verdacht traf: `/api/health` meldet NICHT, wohin der MCP-Server greift,
sondern die eigene Angabe `repo_base_url`.

**Gemessen, nicht vermutet:**

| Seite | Wert | Quelle |
|---|---|---|
| MCP-Server | `repository.staging.openeduhub.net` | `wlo_health_check` → `repositoryUrl` |
| Chatbot | `redaktion.openeduhub.net` | `settings.repo_base_url`, Vorgabe im Code |

Das ist kein Anzeigefehler. `rewrite_repo_host_v2` schreibt JEDEN Treffer auf
das konfigurierte Ziel um — Staging steht in `known_repo_hosts`, Produktion war
das Ziel. Live nachgestellt:

```
Link vom MCP  https://repository.staging.openeduhub.net/.../render/abc-123
Link im Chat  https://redaktion.openeduhub.net/.../render/abc-123
```

Staging-Knoten wurden also unter Produktions-Adressen ausgeliefert: dort ins
Leere — oder auf einen fremden Knoten mit derselben ID.

**Warum es niemand sah.** Paket 2026-08-14 baute den Mechanismus (Konfig vor
Umgebung, Wert in `/api/health`), aber der Wert blieb unbelegt: Seed `""`, keine
Umgebungsvariable, Vorgabe im Code = Produktion. Der Modulkopf von
`test_repo_config.py` nennt genau diesen Fall „die stille falsche Antwort" —
er trat ein, und nichts hielt ihn fest.

**Geaendert (alle drei Stellen plus die Werkzeuge):**

- `settings.repo_base_url` Vorgabe → Staging, mit dem Befund als Begruendung
- `seeds/01-base/card-pipeline.yaml` → Staging ausdruecklich belegt (leer heisst
  „frag die Deploy-Umgebung" — genau das sollte die Angabe abschaffen)
- Live-Zeile im Config-Store (Version 10 → 11); der laufende Prozess uebernahm
  es per NOTIFY, ohne Neustart
- `evals/run_golden.py`: sein Docstring versprach „same default as the backend" —
  ungeprueft. Vorgabe nachgezogen + Waechter, der die beiden aneinander bindet
- `deploy/.env.example`: der Satz „Leer = Produktion" war jetzt falsch
- `text_extraction_url` → Staging. Zwei Nebenbefunde dabei: in DIESEM Backend
  liest die Angabe niemand (die Extraktion macht der MCP-Server mit eigener
  Variablen), und der eingetragene Prod-Host hat eine nicht vertrauenswuerdige
  Zertifikatskette — er haette ohnehin nie geantwortet.

**Bewusst NICHT geaendert, mit Grund:**

- `known_repo_hosts` behaelt beide Prod-Hosts. Sie stehen dort als **Quelle**,
  nicht als Ziel: nur was gelistet ist, wird ueberhaupt umgeschrieben. Sie zu
  entfernen naehme dem Schutz die Wirkung, statt ihn zu verschaerfen.
- `own_hosts` in `context-actions.yaml` erkennt Gastgeber-Seiten, es zielt
  nirgendwohin.
- `b_api_base_url` (`b-api.prod.…`) ist das **LLM-Gateway**, nicht das
  Repositorium. Beide Deployments existieren (je 401), der Schluessel kommt aber
  aus EINER Variablen `B_API_KEY` — welche der beiden Umgebungen gilt, ist eine
  Nutzer-Entscheidung, keine Codefrage. Aktuell ohnehin inaktiv (`provider=openai`).

**Waechter neu:** `TestVorgabeIstStaging` (ohne jede Angabe gilt Staging · der
Seed nennt das Repositorium ausdruecklich · die Prod-Hosts bleiben Umschreib-
Quelle) und `test_die_vorgabe_des_runners_folgt_der_des_backends`.

**Verifikation:** 3971 gruen / 4 uebersprungen / 0 rot · ruff sauber · OpenAPI
und Bereichsschemata unveraendert · Live-Zug „Material zur Optik fuer Klasse 8":
6 Karten, alle Links auf `repository.staging.openeduhub.net`, kein Prod-Host.

### Nachtrag U — Review-Funde behoben

Alle vier Funde der Durchsicht sind zu:

1. **`repo_and_cards.get_repo_base_url`-Docstring** sagte „Vorgabe Produktion" —
   der Satz beschrieb genau die Vorgabe, die der Vorfall entfernt hat. Jetzt
   Staging, mit dem Grund daneben, damit er nicht zurueckwandert.
2. **`base_governance.CardPipelineBlock.repo_base_url`** trug denselben falschen
   Klammerinhalt am Feld selbst. (Geprueft: dieser `#:`-Kommentar erreicht das
   Studio-Schema NICHT — `{"default":"","title":…,"type":"string"}`, keine
   `description`. Er bleibt Quelltext-Kommentar; ein echtes
   `Field(description=…)` waere ein bewusster Vertragszusatz und ist NICHT Teil
   dieses Pakets.)
3. **Der Seed-Waechter pruefte zwei Dinge in einem.** Getrennt in
   `test_der_seed_ist_belegt_und_nennt_ein_bekanntes_repositorium` (dauerhafte
   Regel: belegt UND in `known_repo_hosts`) und
   `test_die_geltende_richtlinie_ist_staging` (die Betriebsentscheidung, allein
   und damit die eine Stelle, die ein Prod-Umstieg anfasst). Das dreifache
   Seed-Lesen liegt jetzt in einem Helfer.
4. **`deploy/.env.example`**: die zwei Erklaerzeilen hinter der Variablen
   wiederholten den Absatz darueber und haetten nach dem Auskommentieren vor der
   naechsten Variablen gebaumelt — entfernt, der sachliche Zusatz steht im Absatz.

**Und der offene Auftragspunkt ist eingeloest:** `b_api_base_url` zeigt auf
`b-api.staging.openeduhub.net`. Die Falle daran steht jetzt im Code UND im
Deploy-Beispiel: Adresse und Schluessel gehoeren zusammen, `B_API_KEY` ist EINE
Variable — ein Schluessel des anderen Deployments ergibt dort 401.

---

## Paket V — Der Chat scrollt beim Antworten nicht mit

**Ursache** (Nutzer-Meldung 2026-08-19, Fehlersuche vor Fix): der
Tail-Follow-`MutationObserver` wurde ausschliesslich in
`ScrollFollowController.scrollToLatest()` scharfgeschaltet. Und das laeuft nur

* beim Panel-OEFFNEN ueber `setExpanded` (`panel-state.ts:105`),
* beim History-Restore (`history-restore.ts:101`),
* oder wenn der Gastgeber die oeffentliche API ruft.

Startet das Panel **schon offen** — `PanelState.initExpanded` setzt das Signal
bewusst an `setExpanded` vorbei (dort bei Z. 135 selbst vermerkt: „`setExpanded`
laeuft nie"), was fuer `initial-state="expanded"`, `?bsid=` und eine laufende
Tour gilt — und gibt es keinen Verlauf, greift keiner der drei Wege. Der
Beobachter haengte sich nie ein.

**Kein verlorener Port:** ALT hatte dieselbe einzige Aufhaengung
(`chat.component.ts:1355`). Fuer ein Widget, das man immer erst aufklappt, genuegte
das. Die Inline-/Classic-Einbettung und der bootoffene Fall haben dieses Ereignis
nicht — die Annahme ist mitgewandert, die Lage hat sich geaendert.

**Zweite Hypothese geprueft und verworfen:** ein neu erzeugtes Container-Element
haette den Beobachter ins Leere laufen lassen. Der Container liegt aber
unbedingt im Template (kein `@if`), wird also nie ersetzt.

**Behebung:** `afterViewChecked()` schaltet den Tail-Follow scharf. Der Aufruf
ist idempotent und ohne Container ein No-Op. Der Follow gehoert zum LEBEN der
Ansicht, nicht zu einer einzelnen Scroll-Anweisung — damit greift er in jeder
Einbettung, egal wer das Panel geoeffnet hat.

**Belegt, nicht behauptet** (im gebauten Bundle, Seite `/widget/inline` mit
`initial-state=offen`):

| Probe | Ergebnis |
|---|---|
| Inhalt waechst, niemand hat ein Panel geoeffnet | `scrollTop` springt ans Ende |
| Nutzer scrollt hoch (mit echtem `scroll`-Ereignis), Inhalt waechst | bleibt oben ✅ |
| Nutzer kehrt ans Ende zurueck, Inhalt waechst | folgt wieder |
| echter Chat-Zug, 7 Nachrichten | `scrollTop 583` = Ende |

Vier neue Tests in `scroll-follow.spec.ts` (zuerst rot). Das Widget-Bundle war
vom 18.08. 21:27 — ohne Neubau haette man den Fix nicht gesehen.

**Verifikation:** ui 820 gruen · widget 69 gruen · Backend 3972/4 uebersprungen ·
ruff + eslint sauber · OpenAPI und Bereichsschemata unveraendert.

---

## Paket W — Die Aktivierungszeile einmal je Sitzung, vom Server

**Nutzer-Vorgabe 2026-08-19:** „diese Nachricht sollte immer am Start jeder
neuen Sitzung kommen, wenn der User ein Gespraech beginnt und die Skill geladen
wird."

**Gemessen, was vorher passierte** (drei Zuege einer Sitzung, Agent, Skill an):

| Zug | Ansage |
|---|---|
| 1 | ja |
| 2 | **nein** |
| 3 | ja |

Die Zeile hing am Modell: der Skill bittet unter „## Aktivierung" darum, sie
woertlich auszugeben. Ein 21k-Dokument, eine Bitte — mal befolgt, mal nicht.
Damit war sie weder ein verlaessliches Signal „Anleitung aktiv" noch blieb sie,
wo sie hingehoert.

**Dieselbe Lehre stand schon im Haus.** ``skill_precedence.mit_ladehinweis``
loest genau das fuer die Zug-Skills, und der Docstring sagt warum: „Gemessen
hielt sich das Modell nicht daran … Eine Ansage, die das Modell umformuliert,
ist eine Behauptung." Der Master-Skill (Paket N) kam spaeter und hat diese
Behandlung nie bekommen. Paket W zieht sie nach — gleiche Naht, gleiche Regel.

**Zwei kleine, reine Bausteine:**

* ``master_skill.aktivierungszeile(block)`` liest die Zeile **aus dem Dokument**
  (nicht aus dem Code): der Wortlaut bleibt bei der Redaktion, die
  Zuverlaessigkeit beim Server. Nur oberhalb der Trennlinie — das Dokument sagt
  selbst, dass eine solche Zeile darunter Inhalt ist und keine Anweisung.
* ``skill_precedence.mit_master_ansage(text, zeile, turn_count)`` setzt sie im
  ERSTEN Zug voran (``turn_count == 0``: der Zaehler steht beim Antworten auf
  dem Stand VOR diesem Zug) und entfernt die Modell-Kopie **immer** — sonst
  staende sie im ersten Zug doppelt und taeuchte spaeter zufaellig wieder auf.

Verdrahtet in ``respond_agent`` (Agent + Hybrid; im Mustermodus gibt es keinen
Master-Skill). ``ctx.master_skill_zeile`` traegt den Beleg: sie entsteht nur,
wenn der Abruf wirklich lief.

**Nachher, live gemessen** (``.env`` mit ``MASTER_SKILL_ENABLED=true``, ohne
``master_skill`` im Aufruf): Zug 1 → 1×, Zug 2 → 0×, Zug 3 → 0×.

### Nebenbefund: drei Tests hingen an der lokalen `.env`

Das Setzen von ``MASTER_SKILL_ENABLED=true`` machte drei Tests in
``test_respond_agent.py`` rot — sie zaehlen Nachrichten in der Prompt-Kette und
besassen ihre Eingabe nicht: die Betreiber-Vorgabe aus ``backend/.env`` sprach
mit. ``_patch`` pinnt die Naht jetzt aus; wer den Block messen will, schaltet
ihn ausdruecklich an. Ohne diese Korrektur waere die Suite je nach lokaler
Konfiguration mal gruen, mal rot gewesen.

**Verifikation:** 11 neue Tests (zuerst rot) · Backend 3983 gruen / 4
uebersprungen · ruff sauber · kein Frontend beruehrt ⇒ kein Bundle-Neubau.

### Nachtrag W2 — Zwei Funde der Durchsicht: einer echt, einer widerlegt

**Fund „CRLF hebelt die Trennlinie aus": FALSCH.** Vor dem Beheben getestet —
sechs von sechs gruen ohne jede Codeaenderung. Grund: ``"\n---"`` ist in
``"\r\n---"`` enthalten, weil ``\r\n`` auf ``\n`` endet. Der Schnitt ist von
sich aus CRLF-fest. Die beiden Tests bleiben, sie halten die Frage fest.

**Fund „die Testsuite liest ``backend/.env`` mit": ECHT — und tiefer als gedacht.**

Die erste Behebung (Env-DATEI in ``conftest`` aushaengen) griff ins Leere: der
Test blieb rot. Statt zu raten, gemessen — in vier Schritten:

1. `os.environ` traegt den Schluessel, die Datei war also nicht die Quelle.
2. `uv run` injiziert nichts (geprueft, beide Male ``None``).
3. Kein ``load_dotenv`` im eigenen Code; der Testhelfer ``fresh()`` raeumt auf.
4. `import boerdi.main` setzt ihn — und die Eingrenzung nennt den Schuldigen:
   **``litellm`` ruft beim Import ``load_dotenv()``** und kippt
   ``backend/.env`` in die Prozessumgebung des ganzen Laufs.

Damit ist ``env_file=None`` wirkungslos, sobald irgendetwas ``litellm`` importiert
— also praktisch immer. ``conftest`` entfernt deshalb **zusaetzlich** genau die
Schluessel, die in der Datei stehen; gelesen wird die Datei selbst, nicht eine
gepflegte Liste, damit niemand eine zweite Stelle nachziehen muss.

**Warum das zaehlt:** CI hat keine ``.env``, ein Entwicklerrechner schon. Beide
liefen gegen unterschiedliche Konfigurationen — ein Test konnte hier gruen und
dort rot sein oder umgekehrt einen Fehler verdecken. Genau das war heute der
Fall, als ``MASTER_SKILL_ENABLED=true`` drei Tests kippte.

**Verifikation:** 3987 gruen / 4 uebersprungen / 0 rot · ruff sauber · OpenAPI
und Bereichsschemata unveraendert.

### Nachtrag W3 — Fund 3 und 4 behoben (mit einer Korrektur am Fund selbst)

**Fund 3 (Datei mit drei Verantwortungen) — anders geschnitten als vorgeschlagen.**
Die Durchsicht empfahl, ALLE drei Ansage-Funktionen nach ``domain/skill_ansagen``
zu ziehen. Beim Umsetzen zeigte sich, dass das schlechter waere:
``mit_ladehinweis`` liest die Gespraechs-Notiz (``LAUF_KEY``), die
``skill_precedence`` selbst schreibt, und braucht ``_einzeilig`` — ein privates
Werkzeug, das dort an sechs Stellen dient. Schreiber und Leser einer
Datenstruktur zu trennen haette ein Modul erzeugt, das in die Innereien eines
anderen greift.

Ausgezogen ist deshalb nur, was **keinerlei** Kopplung hat: die Sitzungs-Ansage
(``mit_master_ansage`` + ``_ohne_zeile``). Sie lag in ``skill_precedence`` nur,
weil die verwandte Funktion dort steht.

```
skill_precedence.py  449 → 410 Zeilen   (bleibt ueber der Schwelle, vorbestehend)
skill_ansagen.py      55 Zeilen, null Abhaengigkeiten ausser stdlib
```

**Fund 4 (zwei Ansagen sahen aus wie eine Doppelung) — behoben.** Gemessen, alt
gegen neu:

```
ALT: '… Masterskill - aktiv\n\n… Stunde planen - wird geladen\n\nHier ist …'
NEU: '… Masterskill - aktiv\n…  Stunde planen - wird geladen\n\nHier ist …'
```

Die beiden sagen Verschiedenes — Zustand („aktiv") und Ereignis („wird
geladen") — und bilden jetzt EINEN Block statt zweier Absaetze. Vor gewoehnlichem
Text bleibt die Leerzeile.

**Verifikation:** 3988 gruen / 4 uebersprungen · ruff sauber · Vertraege
unveraendert. Die Live-Kombination (erster Zug UND ein ladender Zug-Skill) liess
sich nicht verlaesslich ausloesen; belegt ist sie durch den Alt/Neu-Vergleich
oben und zwei Tests.

---

## Paket X — Ein abgelehnter Zug wurde zweimal geschickt

**Nutzer-Meldung 2026-08-19:** am ``/stream``-Endpunkt kam ein 422 wegen
``host_instruction``-Laenge, „er macht dann glaube den Fallback auf den
/chat-Endpunkt, aber Konsolen-Fehler sind es ja trotzdem".

**Der gemeldete 422 selbst ist KEIN Code-Fehler mehr.** Gemessen gegen den
aktuellen Stand: ``host_instruction`` mit 9028 Zeichen ⇒ ``/api/chat`` **200**
und ``/api/chat/stream`` **200**. Der Deckel fiel mit Paket L1 (2026-08-18),
die Meldung „… erlaubt sind 2000" existiert im Quelltext nur noch fuer
``result_schema``, und der Waechter
``test_die_anweisung_hat_keinen_zeichendeckel_mehr`` haelt das fest. Die
gemeldete Instanz laeuft also auf Code von **vor** L1 ⇒ neues Image + Deploy
(Nutzer-Domaene).

**Der ECHTE Fund steckte in der Beobachtung „zwei Fehler".** ``streamChat``
warf bei JEDEM Nicht-OK-Status denselben anonymen ``Error``, und
``send-message.ts`` faellt darauf zurueck:

```
// Stream-Transport gescheitert (Netz/Proxy/Parser) → stiller Fallback
resp = await ctx.post(...)
```

Der Kommentar nennt die Absicht — Transportfehler und aeltere Backends ohne die
Route. Ein 422 ist beides nicht: der Server hat die Anfrage **verstanden und
abgelehnt**. Derselbe Rumpf wurde auf ``/chat`` identisch abgelehnt: zwei
Anfragen, zwei Konsolenfehler, am Ende doch nur die Fehlerblase.

**Behoben:** ``StreamHttpError`` traegt jetzt den Status; der Rueckfall
unterbleibt bei 4xx — **ausser 404/405**, denn das ist genau der Fall, fuer den
er gebaut wurde. 5xx, Netz und Parserfehler fallen weiter zurueck.

| Lage | Rueckfall | Warum |
|---|---|---|
| 422 / 429 / andere 4xx | nein | wird auf dem zweiten Weg genauso abgelehnt |
| 404 / 405 | ja | altes Backend ohne ``/stream`` — der Bauzweck |
| 5xx, Netz, Parser | ja | auf dem anderen Weg vielleicht weg |

Vier Tests, zuerst rot (422/429), die Gegenfaelle 404/500 waren von Anfang an
gruen — der Beleg, dass die Unterscheidung greift und nicht pauschal abschaltet.

**Verifikation:** ui 824 gruen (+4) · eslint sauber · Widget-Bundle neu gebaut
(Frontend beruehrt!). Backend unveraendert.
