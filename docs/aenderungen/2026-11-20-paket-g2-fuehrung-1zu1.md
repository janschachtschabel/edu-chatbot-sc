# Paket G2: Webseitenführung als Ablauf 1:1 wie die Tour (2026-11-20)

Plan: `docs/plans/2026-11-20-konto-vorgaenge-und-warten-auf-volltext.md`, §5 (G2, Befund G2a–G2d).

## Warum

Nutzer: „die webseitenführung in den abläufen entspricht text, schnellantwortbuttons und verzweigung
auch noch nicht der ursprünglichen führung – es sollte eine 1 zu 1 kopie sein – aber mit dem ablauf
baukasten“.

Referenz ist die eingebaute Web-Tour (`seeds/01-base/website-tour.yaml` + `domain/tour.py` +
`graph/nodes/tour.py`). Sie ist logisch identisch mit der ALT-Tour (`badboerdi/backend/app/services/
tour_service.py`, nur Formatierung und `ist_ausloeser` neu); der Neubau-Seed ist der ALT-Seed plus
Englisch.

## Befund (Durchtest vorher, Wegwerf-DB, echte Server-Züge)

Dieselben Eingaben wie das Widget (Tour-Chip `Web-Tour starten` + `tour_action: start`, Chips,
Getipptes, Seitenaufrufe als Tick bzw. Seiten-Ping) einmal gegen die Tour, einmal gegen den Ablauf.
Texte, Chips und Ziele der Hauptwege waren schon gleich (der Erzeuger lässt die Texte von
`tour.render` schreiben). Abweichend war das Verhalten an den Rändern:

| Fall | Tour | Ablauf vorher | Ursache | Ablauf nachher |
|---|---|---|---|---|
| „Bin mir nicht sicher“ zweimal (auch nach einem getippten Fehlversuch) | 1. Hilfetext + Chips, 2. Tour endet → KI antwortet | Hilfetext immer wieder (Option → Schritt `unsicher`) | Baukasten: kein Chip, der wie getippt zählt | wie Tour (G2a) |
| Auslöser-Satz („starte die tour“) in der Gruppenwahl | Fehlversuch → Hilfetext, dann Ende | „Du bist schon mitten in …“ + Chip „Neu starten“ | Regel „Wendung an der Frage“ (Paket K) | wie Tour (G2b) |
| Tour-Chip erneut gedrückt, mitten in der Führung | Neustart an der aktuellen Seite (Einstieg je Seite) | alter Schritt erneut | Chip kam als getippter Auslöser an | wie Tour (G2c) |
| Seitenwechsel/Neuladen während der Gruppenwahl | Tick zeigt die Frage samt Chips erneut, Widget öffnet sich | nichts (kein Ping bei `wartet_wahl`; Chips der alten Blase nach dem Neuladen weg) | Widget pingt nur bei `wartet_seite` | wie Tour (G2d) |

Zahlen: vorher 16 Wege / 53 Züge, 5 abweichend; nachher 20 Wege / 65 Züge, 0 abweichend.

Gewollte Unterschiede (unverändert, im Kopf von `fuehrung.yaml` genannt): relative Pfade statt
`base_host` (die Tour verlinkt im Seed `wp-test…`), die Ablauf-Leiste, kein Etikett „KI-generiert“.

**Vermutlich ein Grund für das, was der Nutzer auf Staging sieht** (dort nicht prüfbar): Die Führung
ist ab Werk aus. Wurde sie im Studio eingeschaltet, bevor der Erzeuger sie am 16.11. 1:1 neu schrieb,
liegt eine **eigene Fassung** vor — die hebt der Werksabgleich nie an (Status „eigen, neues Werk“).
Dann zeigt Staging weiter die alte „Kurze Führung“. Abhilfe nach dem Deploy: im Studio unter
„Abläufe → Führung durch WLO“ auf die Werksfassung umschalten, dann einschalten.

## Was

### Baukasten (vier Fähigkeiten, Plan §5)

- **G2a `text_antworten`** (`domain/config_models/ablauf.py`: `TextAntwort`, Feld am Schritt
  `nachricht`, höchstens 3): Chips hinter den Optionen, die wie getippter Text zählen. Als Wahl-Chip
  mit der reservierten Wahl `_text` (`domain/wahl_knopf.TEXT_WAHL`) übersteht er jeden Deckel; der
  Vorlauf (`preflight_ablauf.bestimmen`, `wahl_zug.text_chip_gilt`) macht daraus getippten Text —
  nie an der Frage eines anderen Laufs (Review, MAJOR 1). `treiber.wahl_angebot` (Schlüssel `texte`, nur wenn vorhanden), `wahl_zug.knoepfe`.
  Prüfung (`pruefung._text_antworten`, Text `text_antworten`): nur mit Optionen, ohne Freitext, mit
  deutschem Text, und die Beschriftung trifft keine Option.
- **G2b** (`wendung_zug.wendung_trifft`): in einem Ablauf mit `endet_bei_text` ist die eigene
  Wendung an einer Frage ohne Freitext getippter Text. Nur die Führung hat `endet_bei_text`;
  „Themenbaum erstellen“ behält „Du bist schon mitten in …“.
- **G2c** (`zug.tour_chip`, `graph/nodes/preflight_ablauf`, `preflight`): ist die eingebaute Tour
  aus, startet der Tour-Chip (`tour_action: start`) den Ablauf mit dem Merkmal `tour_chip` wie
  dessen Knopf (`ablauf_starten`) — ein wartender Lauf desselben Ablaufs beginnt neu an der
  aktuellen Seite; wartet ein anderer, erst die Rückfrage (Review, MAJOR 2 / MINOR 7). Ohne
  Lauf wie bisher. Bei Krise/fehlender Prüfung geht er wie getippter Text den gewöhnlichen Weg.
- **G2d** (`fortschritt.ist_fuehrung`, Stand-Feld `fuehrung` in `api/schemas_ui.AblaufStand`,
  `seite_zug._frage_erneut`): wartet eine Führung (Ablauf mit `seite`-Schritt) an einer Frage, zeigt
  der Seiten-Ping die Frage samt Chips erneut, ungespeichert. Widget
  (`controllers/ablauf-seite-merker.wartendeFuehrung`, `seiten-ping.seitenPingNoetig`): pingt und
  öffnet sich auch bei `wartet_wahl` mit `fuehrung`. Gesperrte Shell-Dateien unberührt.

### Erzeuger und Seed

`backend/scripts/fuehrung_aus_tour.py`: „Bin mir nicht sicher“ ist `text_antworten` am Schritt
`gruppe`, der Schritt `unsicher` entfällt (38 statt 39 Schritte); Seed-Test „Bin mir nicht sicher“
neu; Kopf-Kommentar ohne die behobenen Abweichungen. `seeds/06-ablaeufe/fuehrung.yaml` neu erzeugt.

### Studio, Verträge

Feldtexte `text_antworten`/`TextAntwort` (de/en) in `studio/…/catalogue/fields-ablaeufe.ts`;
`area-schemas.fixture.ts` und `docs/api/openapi-v1.json`, `openapi-public.json` neu erzeugt (nur
`fuehrung`, `text_antworten`, `TextAntwort`).

## Tests (zuerst rot, dann grün)

- `tests/test_ablauf_g2_fuehrung.py` (12): G2a Chip-Form + Deckel, Endpunkt, Fehlversuch, Sprache,
  Prüfung; G2b mit/ohne `endet_bei_text`; G2c Neustart/ohne Lauf; G2d Stand, Ping zeigt Frage
  ungespeichert, ohne `seite`-Schritt leer. Rot vorher: 9 von 12.
- `tests/test_fuehrung_durchspiel.py` (19 Wege): **der automatische Abgleich Tour ↔ Ablauf** — beide
  Maschinen echt, Zug für Zug Text, Chips (Beschriftung, Reihenfolge, Ziel) oder „→ KI“. Mit dem
  alten Seed rot (`unsicher_zweimal`, `fehlversuch_dann_unsicher`).
- `tests/test_fuehrung_wie_tour.py`: Gruppenwahl-Chips = Optionen + `text_antworten`, kein Schritt
  `unsicher`; Leiste ohne Sprung.
- Angepasst (neues Stand-Feld): `test_ablauf_leiste.py`, `test_ablauf_leiste_endpunkte.py`.
- Widget: `seiten-ping.spec.ts`, `ablauf-seite-merker.spec.ts` (G2d).

Gelaufen: Backend-Teilmenge Abläufe/Tour/Preflight/Schema/OpenAPI (2127 grün; rot nur
`test_ablauf_feste_argumente::test_scan_im_wlo_weg…` aus der parallelen Volltext-Arbeit, dazu drei
Dateien, die beim Sammeln an `themenbaum.yaml` mit 22 Tests scheiterten — beides nicht G2);
`ng test ui` 1582 grün; Studio-Schema/Katalog-Specs 483 grün; ruff/eslint sauber.

## Betrieb und Deploy

- Keine Migration. Das Image baut das Widget selbst (G2d braucht das neue Bündel).
- Werksabgleich hebt `06-ablaeufe/fuehrung` an, wenn dort die unberührte Werksfassung liegt; eine
  eigene Fassung bleibt (siehe oben: im Studio auf die Werksfassung umschalten).
- Die Führung bleibt ab Werk aus; einschalten im Studio und die eingebaute Tour abschalten
  (`website_tour.enabled = false`) — erst dann startet der Tour-Chip der Begrüßung die Führung.

## Review behoben (unabhängiges Review G2: 2 MAJOR, 5 MINOR, 3 NIT)

| Befund | Fix | Test (rot → grün) |
|---|---|---|
| **MAJOR 1** alter „Bin mir nicht sicher“-Chip beantwortete die Frage eines anderen Laufs (`zweck` gespeichert) | Umwandlung nicht mehr am Endpunkt, sondern im Vorlauf (`preflight_ablauf.bestimmen`, `wahl_zug.text_chip_gilt`): an einer wartenden Frage nur, wenn es seine ist; wartet ein Lauf eines **anderen** Ablaufs, bleibt er Wahl → „gilt nicht mehr“ + gültige Chips. Ist die eigene Führung weiter (wartet auf eine Seite) oder läuft nichts, zählt er wie in der Tour als getippt. `preflight` liest danach `ctx.req` neu. | `test_review_g2_1_*` (2), Durchspiel `test_ein_alter_chip_der_fuehrung_beantwortet_keinen_anderen_ablauf`, Weg `alter_chip_nach_der_wahl` |
| **MAJOR 2** Tour-Chip ersetzte einen wartenden anderen Ablauf ohne Rückfrage | `zug.per_tour_chip`: wartet ein anderer Ablauf, erst die Ersetzen-Rückfrage — an seiner Frage wie bei einer Wendung samt „Hier weitermachen“ (`wendung_zug.wendung_beantworten`), sonst „Neu starten“ (`ersetzen_fragen`); derselbe Ablauf oder keiner: Start wie der Knopf | `test_review_g2_2_*` (2), Durchspiel `test_der_tour_chip_fragt_erst_wenn_ein_anderer_ablauf_wartet` |
| **MINOR 3** Wendung im Einstieg bei den Lösungen / nach Umschau: Tour zeigt die Lösungen, Ablauf die Einstiegsbegrüßung | **1:1 nachgebildet:** neues Feld `text_erneut` am `seite`-Schritt (`seite_zug.wiederholen`); der Erzeuger setzt es an den `einstieg_*`-Schritten auf den normalen Lösungen-Text der Tour | `test_review_g2_3_*`, `test_texte_wie_in_der_tour` (20 Fälle rot mit altem Seed), Wege `ausloeser_im_einstieg_loesungen`, `ausloeser_nach_umschau` (im Review-Skript rot) |
| **MINOR 4** fehlende Wege | 17 Wege ergänzt (Nudge im Zwischenstopp, Fehlversuch→Seite→Fehlversuch, Fehlversuch→Tour-Chip→Fehlversuch, Tour-Chip in der Gruppenwahl, `/home` ohne `/`, `/mitmachen/faq/`, „I'm not sure“ zweimal, Unsicher→Seite→Unsicher, Krise in der Gruppenwahl und beim Warten, alter Chip, …); der Durchspiel-Treiber läuft jetzt durch den **echten Vorlauf-Knoten** (Sicherheitsprüfung mit dem Regex-Gate). Neu `tests/test_fuehrung_graph_pg.py`: Tour aus + Führung an durch `build_turn_graph` gegen echtes Postgres (Tour-Chip, Ping, Ping nach Seitenwechsel, Text-Chip) | `test_fuehrung_durchspiel.py` 37 grün, `test_fuehrung_graph_pg.py` 1 grün |
| **MINOR 5** Merker fiel nach dem Verlauf an der Frage einer Führung | `ablauf-seite-merker.merkerFaelltNachVerlauf` (nutzt `wartendeFuehrung`), `chat-shell.component.ts` `verlaufGeklaert` ruft sie | `ablauf-seite-merker.spec.ts` (rot: fehlender Export) |
| **MINOR 6** Doku | `docs/ablaeufe.md`, Kapitel „Führungen“: Felder `abweichung`/`umsehen`/`text_erneut`, Abschnitt „Wie die eingebaute Tour“ (`endet_bei_text`, `text_antworten`, `tour_chip`, Frage nach Seitenwechsel), Beispiel neu | — |
| **MINOR 7** Ziel des Tour-Chips hing an der Wendung im Text „Web-Tour starten“ | Merkmal `tour_chip` am Ablauf (`ausloeser.per_tour_chip`); Befund ohne Auslöser `knopf`, Warnung bei mehreren aktiven (`pruefung.tour_chip_warnungen`, Endpunkt „Prüfen“); Erzeuger setzt es; Studio-Feldtexte de/en; Fixture + OpenAPI neu | `test_review_g2_7_*` (2), `test_review_g2_7_der_tour_chip_der_begruessung_startet_die_fuehrung` |
| NIT 8 | `action_params: {}` | im G2a-Test |
| NIT 9 | `per_modul = (` | ruff |
| NIT 10 | G2b im Docstring und im Studio-Hinweis zu `endet_bei_text`: „Ablauf mit `endet_bei_text`“ | — |

## Zweites Review (unabhängig: 0 CRITICAL, 0 MAJOR, 3 MINOR, 3 NIT) — behoben

Alle Befunde der ersten Runde bestätigt behoben, keine neuen Fehler; Erzeuger byte-gleich zum Seed.

| Befund | Fix | Test |
|---|---|---|
| MINOR 1 nach der Tour-Chip-Rückfrage drückte kein Test „Neu starten“ / „Hier weitermachen“ | — (Testlücke) | `test_review_g2_2_der_tour_chip_fragt_…`: „Hier weitermachen“ lässt den anderen Lauf und alle `teile` unberührt; „Neu starten“ beginnt die Führung an der aktuellen Seite und schließt den anderen Vorgang |
| MINOR 2 `text_chip_gilt`: fremder Lauf ohne Frage, kein Lauf ungetestet | — (Testlücke) | `test_review_g2_zweite_runde_2_*` (2) |
| MINOR 3 Befund `tour_chip_knopf` und Pflichtfeld-Filter ungetestet | — (Testlücke) | `test_review_g2_zweite_runde_3_*` |
| NIT 4 Text „braucht Auslöser knopf“ strenger als die Prüfung | Prüftext und Studio-Hinweis nennen `knopf`, `agent` oder `seite`; `docs/ablaeufe.md` | — |
| NIT 5 `text_antworten` ohne `kein_treffer` ging durch | Prüfung meldet es (der erste Druck beendete sonst die Führung); Prüftext, Studio-Hinweis, Doku | `test_g2a_pruefung` |
| NIT 6 `bestimmen` schrieb `ctx.req` als Nebenwirkung | eigener Schritt `preflight_ablauf.text_chip_als_text(ctx)` vor `bestimmen` im Vorlauf | bestehende G2a-Tests |

Offen als eigener Entscheid (vor G2 schon so): Eine per Tour-Chip gestartete Führung übernimmt
freie Arbeit (Vorgang ohne Lauf) — ob eine Führung, die nichts schreibt, einen eigenen Vorgang
bekommt, steht in `docs/offene-befunde-und-todo.md`.

Geänderte Dateien zusätzlich: `domain/config_models/ablauf.py` (`tour_chip`, `text_erneut`),
`services/ablauf/{ausloeser,zug,wahl_zug,seite_zug,pruefung,pruefung_texte,wendung_zug}.py`,
`api/config_ablauf.py`, `api/chat.py` (Umwandlung entfernt), `graph/nodes/{preflight,preflight_ablauf}.py`,
`frontend/projects/ui/src/controllers/ablauf-seite-merker.ts`, `shell/chat-shell.component.ts`
(eine Zeile), `studio/.../fields-ablaeufe.ts`, `docs/ablaeufe.md`, Seed neu erzeugt.
