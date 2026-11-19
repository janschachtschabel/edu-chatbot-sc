# Paket N4: Freigabe-Box vor dem Kestra-Start (2026-11-19)

Plan: `docs/plans/2026-11-19-nachbesserungen-themenbaum-betrieb.md`, N4. Hebt Entscheid 1 aus
`2026-11-18-paket-k-kestra-ueber-mcp.md` auf: der Server bestätigt die Vorschau des MCP nicht mehr
im selben Zug wie die Rückfrage.

## Was die Person sieht

1. Rückfrage `metadaten_frage` → „Ja“.
2. Der Server holt die Vorschau des MCP (`wlo_start_flow` ohne `confirmToken`) und zeigt **eine
   kompakte Box**: „N Materialien werden in WLO erschlossen“, ein Satz, was überschrieben wird
   (Titel, Beschreibung, Schlagworte, Fach, Stufe, Zielgruppe, Typ, Sprache), Probleme des MCP
   getrennt mit Grund („gehen nicht mit“), die Liste eingeklappt. Aufgeklappt nach Ordner
   gruppiert; über 20 Einträge mit Filterfeld und „Weitere zeigen“ (je 20). Knöpfe „Freigeben“ und
   „Abbrechen“ in der Box. Keine Schnellantworten darunter.
3. „Freigeben“ startet den Job mit dem gespeicherten Schlüssel, danach wie bisher (Stand, „k von n
   fertig“, Sperre). „Abbrechen“ nimmt den Ersatzweg `ohne_metadaten` mit „Abgebrochen – in WLO wird
   nichts überschrieben.“
4. Nach der Entscheidung ist die Box eine Zeile: „Entscheidung gesendet: Freigeben“ bzw.
   „… Abbrechen“ (`role="status"`, Fokus darauf); was daraus wurde, sagt die Antwort darunter. Im
   Verlauf und nach jedem weiteren Zug: „Vorschau für N Materialien – nicht mehr offen“.

## Technik

- `services/auftraege/mcp_vorschau.py` (neu): `vorschau` und `bestaetigen` getrennt; `Vorschau` mit
  Schlüssel, Frist (höchstens die eigene, Uhrenversatz abgefangen) und Titeln aus `preview.items`.
  `VorschauFehler.probleme` aus `problems`. `confirm_expired`/`confirm_mismatch` → `abgelaufen`;
  `replayed: true` → dieselbe jobId. `mcp_starter.starten` ruft beides nacheinander (spätere Teile
  eines Stapels).
- `services/ablauf/auftrag_freigabe.py` (neu): `vorlegen` (Vorschau je Teil; ein Datensatz mit
  Problem fällt heraus, der Rest wird einmal neu vorgelegt), `merken` (Schlüssel nur in
  `entities["_auftrag_freigabe"]`, gebunden an Ablauf, Schritt, Vorlage-`id` und
  `aufrufer_kennung()`), Box-Daten ohne nodeIds und ohne Schlüssel.
- `services/ablauf/auftrag_freigabe_zug.py` (neu): Direktaktionen `ablauf_auftrag_freigeben` und
  `ablauf_auftrag_verwerfen` (`{ablauf, id}`), im Vorlauf geführt und ohne Moderation erlaubt
  (`_STEUER_OHNE_TEXT`: nur Kennungen).
- `treiber.py`: ein `auftrag`-Schritt mit `repo_schreibt`, dessen Starter `vorlegen` kennt (MCP),
  hält an `wartet_freigabe` (`freigabe_id`, `freigabe_args`); `weiter_nach_freigabe` setzt fort.
  Der Teil nach dem Start (`_gestartet`) ist für Start und Freigabe derselbe.
- `auftrag_zug._Starter`: `vorlegen`, `bestaetigen`, `grund_des_fehlers`.
- `zug_basis.antwort`: Box anhängen, keine Chips; `freigabe_zug.weiter_knopf`: unter einer
  gewöhnlichen Antwort „Vorschau erneut zeigen“ (holt eine neue Box).
- `ui_module/antwort.status_ableiten`: die Box wird nach dem nächsten Zug `veraltet` (Quittung).
- `ui_module/werkzeuge._fuer_die_ki`: ein Feld mit `"x-nur-system": true` sieht die KI nicht.
- Widget: Manifest `ui_inhaltsrahmen` (Feld `freigabe`, nur System; Fähigkeit `auftrag`),
  `freigabe.ts`, `freigabe-liste.component.*`, `AuftragSchritt` `freigeben`/`verwerfen`,
  `collection-actions.auftragFreigabe`, `fragen-status.offeneFragenSchliessen`.

## Sicherheit

- Schlüssel nur serverseitig (Sitzung), nie im Vorgang, Text, Modell, Log; `_`-Schlüssel gehen
  nicht in Debug und Verlauf.
- Einlösen nur mit persönlicher Anmeldung (nicht Gastkonto), derselbe Aufrufer, dieselbe Sitzung,
  dieselbe Vorlage, auf die der Lauf wartet. Nur per Knopf (Direktaktion) — ein getipptes „ja“
  löst nichts ein.
- Doppelklick/Replay: die Freigabe wird **vor** dem Aufruf des MCP aus der Sitzung genommen und
  festgeschrieben; ein zweites „Freigeben“ findet nichts. Rutscht es bis zum MCP durch, antwortet
  er `replayed: true` mit derselben jobId, und der Vorgang schreibt nur einmal fest.
- Ohne Anmeldung gibt es keinen Träger, also keine Vorschau und keine Box.

## Entscheide

1. **Kein Feld `freigabe` am `auftrag`-Schritt.** Für jeden Auftragsschritt mit `repo_schreibt`
   über den MCP gilt immer die Box (Vorschlag des Nutzers). Die Rückfrage davor bleibt (Prüfung
   `auftrag_rueckfrage`), kürzer.
2. **Stapel über 50:** die Vorschau je Teil vorab (für Liste und Probleme), **eine** Box. Gespeichert
   wird nur der Schlüssel des ersten Teils. Spätere Teile holen beim Start Vorschau und Schlüssel
   neu, ohne neue Freigabe — die Person hat die ganze Liste freigegeben, und ein Schlüssel gilt nur
   zehn Minuten, kürzer als die Teile davor laufen. Lehnt der MCP dabei ab (ein Datensatz wurde
   inzwischen unschreibbar), scheitert nur dieser Teil wie bisher.
3. **Abgelaufener Schlüssel** (eigene Frist oder `confirm_expired`/`confirm_mismatch`): neue
   Vorschau, neue Box mit „Die Vorschau war abgelaufen …“. Nichts wird ohne neue Freigabe
   gestartet (wie Paket S).
4. **Probleme:** Der MCP lehnt die ganze Vorschau ab, sobald ein Datensatz ein Problem hat. Der
   Chatbot nimmt diese heraus und legt den Rest einmal neu vor; die Box nennt sie. Sind alle
   ungeprüft (`unchecked`), gilt das als vorübergehend (zurück an die Rückfrage).
5. **429 bzw. Werkzeug kurz weg beim „Freigeben“:** wie beim Start zurück an die Rückfrage (Z4).
6. **Knöpfe in der Box statt Chips** (Paket S nutzt den Chip „Ja, so ausführen“, der auch getippt
   gilt): hier soll nur ein Knopf einlösen. Die Box ist die von Paket S (Inhaltsrahmen,
   `schreib_vorschau`), um die Liste erweitert — kein zweites Modul.
7. **Leiste:** Die Box ist ein Halt am Auftragsschritt; nach „Freigeben“ wartet derselbe Schritt
   auf den Auftrag ohne neuen Halt — „Schritt n von m“ bleibt gleich.

## Abweichungen

- `treiber.py` (1155) und `auftrag_zug.py` (670) waren schon über 300 Zeilen und wachsen um rund 65
  bzw. 45 Zeilen; die neue Logik liegt in neuen Dateien unter 300 Zeilen.
- Die Simulation (Studio) und der Trockenlauf haben keinen MCP-Starter: dort startet der Schritt
  wie bisher ohne Box.

## Deploy

- Keine Migration, keine neue Variable.
- **Seed „Themenbaum erstellen“ ändert sich** (Text `metadaten_frage`): Läufe dieses Ablaufs, die
  beim Werksabgleich laufen oder warten, brechen ab — Werksabgleich in einer ruhigen Zeit.
- **Image neu bauen** (baut Widget und Studio selbst, `deploy/README.md`); die mit
  `npm run module:register` erzeugten Manifeste (`manifeste.json`, `register.generated.ts`)
  gehören in den Commit.

## Tests

- Neu: `backend/tests/test_paket_n4_vorschau.py` (Drahtform), `test_paket_n4_freigabe.py`
  (Vorschau → Box → Freigeben → Start, Abbrechen, Ablauf des Schlüssels (Frist und MCP),
  Doppelklick, andere Person, andere Sitzung, ohne Anmeldung, Probleme, Stapel, KI sieht `freigabe`
  nicht, Box passt zum Manifest, Verlauf, Leiste).
- Angepasst (altes Soll: Start im selben Zug): `test_ablauf_auftrag._starte` und
  `test_paket_k_traeger._am_auftrag` geben die Box gleich frei; `_mcp_startet` ersetzt das Patchen
  von `mcp_starter.starten` in `test_paket_k_traeger.py` und `test_paket_k_review.py`.
- Widget: `freigabe.spec.ts`, `freigabe-liste.component.spec.ts` (eingeklappt, Gruppen, Probleme,
  Filter/seitenweise, Quittung mit Fokus, nicht angekommen, nur lesend, englisch),
  `fragen-status.spec.ts`, `collection-actions.spec.ts`.

## Review behoben (19.11.)

1 MAJOR, 8 MINOR, NIT — alle behoben. Je Befund der Test: rot gesehen bei 1, 2, 5, 7 (Widget) und —
nachgeprüft durch Zurückdrehen des Fixes — bei 3, 4, 8. Tests: `test_write_confirm.py`
(`test_n4_…`), `test_paket_n4_review.py` (neu, 14), `freigabe-liste.component.spec.ts` (+5).

1. **MAJOR:** `write_anzeige.entities_for_display` schwärzt auch `_auftrag_freigabe.token`
   (`GET /api/sessions/{id}`). Weitere Ausgaben von `entities` geprüft: Debug (`schemas_debug`),
   Verlauf (`turn_persist`) und Kontext des Modells (`domain/context.py`, `turn_frame.py`) lassen
   `_`-Schlüssel ganz weg; Export und Auswertung geben `entities` nicht aus.
2. Quittung neutral: „Entscheidung gesendet: Freigeben/Abbrechen“.
3. `_neu_vorlegen`: „Die Vorschau war abgelaufen …“ nur, wenn wirklich eine neue Box kommt.
4. `_teil`: nur endgültige Probleme (`not_found`, `not_readable`, `not_a_record`, `is_reference`,
   `not_writable`) fallen heraus; ist einer ungeprüft, gilt die Vorschau als vorübergehend
   (zurück an die Rückfrage).
5. Probleme: die ersten 5 sichtbar, der Rest hinter „Alle zeigen (N)“ (Disclosure).
6. `_am_auftrag` ruft die echte Freigabe `auftrag_freigabe_zug.starten` (der Kern von „Freigeben“
   ohne Sitzung, neu herausgelöst). Neue Tests über die Drahtform: Vorschau mit 429, nur
   ungeprüfte, gemischt, unbekanntes Werkzeug, „keins geht mit“, zweite Vorschau scheitert,
   429 beim Freigeben, „Vorschau erneut zeigen“ am Auftragsschritt (die alte Box gilt danach
   nicht mehr).
7. Box-Daten tragen `flow` und `metadaten`. Kopf und Satz zu den Feldern nur beim Metadaten-Flow;
   sonst „Dieser Auftrag schreibt in WLO: {Flow}“, die Zahl nur mit Einträgen. `mcp_vorschau._titel`
   liest auch JSON-Items (deren `node_ids`).
8. `freigabe_zug.erneut` verlangt am Auftragsschritt `has_personal_auth()`; sonst
   `freigabeOhneAnmeldung`, der Lauf wartet weiter.
9. Deploy-Hinweis korrigiert (oben).
10. NIT: Einzahl („1 Material“, de/en, Backend und Widget); `mcp_starter.rufen`, `grund`, `JOB_ID`
    öffentlich; `aria-controls` nur bei sichtbarer Liste; `_titel_aus` liest `frueher`; jeder
    Abbruch eines Laufs (`zug_basis.abbrechen`, damit auch `abbruch_zug`) entfernt
    `_auftrag_freigabe`.

Folgepunkt in `docs/offene-befunde-und-todo.md` (Liste F-8): Schnitt von `treiber.py` und
`auftrag_zug.py`.

## Durchtest (19.11.)

Lokales Backend (Staging-Kopie) auf Port 8107 gegen die Wegwerf-DB `boerdi_durchtest_n`
(Compose-Postgres, Name vor dem Start geprüft), LLM nativ `gpt-6-luna`, Einbettung wie eingestellt,
Master-Skill lokal (`vorgehen-knapp.md`), Staging-MCP, Repository Staging, Testkonto über
Sitzungs-Tausch (`WLO-Access-Block`). `STUDIO_API_KEY` ein Wegwerfwert nur für diesen Prozess.
API-Ebene wie das Widget, nicht im Browser. Testdateien: Text-PDFs `boerdi-durchtest-1911n-*`
(Vulkanausbruch und Erdbebenwellen = Erdkunde, Bruchrechnung = Mathematik; Zellteilung; Elektromotor,
Preisbildung). Skripte `*_n.py`, Protokolle `lauf_n_*.log`, `backend_n.log` im Scratchpad unter `tg7/`.

| Teil | Fall | Ergebnis | Beleg |
|---|---|---|---|
| N4 + N3 | 1 Mit Anmeldung, 3 PDF „In WLO ablegen“ | ok | `orte.vorauswahl` `wlo`. Ablage 3 × `stored`. „Ja, Metadaten erzeugen“ → Leiste `wartet_freigabe`, **0 Aufträge**, keine Chips. Box `ui_inhaltsrahmen` (`schreib_vorschau`): `anzahl` 3, Titel, Ordner, `flow` `edusharing.chatbot/node-metadata-write`, `metadaten: true`, `probleme: []`; Kopf „3 Materialien werden in WLO erschlossen“ und der Satz zu den Feldern. Antwort ohne `confirmToken`, ohne Schlüsselwert, ohne nodeIds (0 von 3) und ohne Feld `node_id`. Schlüssel nur in `entities._auftrag_freigabe` (Frist 599 s). `GET /api/sessions/{id}` zeigt ihn geschwärzt („‹wird bei der Bestätigung eingesetzt›“). „Freigeben“ → `/stand` `laeuft` → 0/3 → `fertig` 3/3 (25 s), „Stand prüfen“ → „3 Materialien erschlossen, 0 nicht.“ `metadaten_lesen`: 3 Einträge mit Node, Fach Mathematik bzw. Geografie, Stufe Sek I. An den 3 Knoten neue Titel, Beschreibungen, Schlagworte, Fach und Stufe. Entwurf „Mathematik und Geografie“: 3 Punkte mit je 1 Material, jeweils `node_id` = Knoten der Ablage zu `i`. `nicht_zugeordnet` leer (alle drei passen). Gespeicherter `draft` gleich. Fach im Entwurf leer (gemischt), kein Freitext. |
| N4 | 2 Abbrechen (1 PDF) | ok (Satz danach unpassend) | Box „1 Material wird …“ (Einzahl), 0 Aufträge. „Abbrechen“ → „Abgebrochen – in WLO wird nichts überschrieben.“, Ersatzweg `ohne_metadaten`, `_auftrag_freigabe` weg, 0 Aufträge. Spätes „Freigeben“ derselben Box → „… nicht mehr darauf wartet … geändert wurde nichts“, 0 Aufträge. Knoten 20 s später unverändert. |
| N4 | 3 Doppelklick | ok | Zweimal „Freigeben“ im Abstand von 0,15 s (zwei Verbindungen): Klick 1 startet (`wartet_auftrag`, `ui_fortschritt`), Klick 2 bekommt den Satz zur Sperre. **1 Auftrag** in `vorgang_auftraege`, eine Log-Zeile „Auftrag über den MCP gestartet“. |
| N3 | 4 Chat-Weg ohne Anmeldung, 3 PDF | ok | `orte`: `chat`, `wlo` `nur_angemeldet`, `chat.ueber_grenze_anmelden` (Fix aus U wirkt). Entwurf „Brüche und geologische Prozesse“ (2 Ebenen, 20 Knoten): je Punkt 1 Eintrag `{i, name}`, ohne `node_id` und ohne `upload_id`. `name` = Titel der Kurzangaben (3/3). `nicht_zugeordnet` leer. Fach der Punkte Mathematik/Geografie. |
| N2 | 5 Kurzangaben, Vokabular | ok | Vokabular `discipline` 70 Labels (Staging-MCP). Kurzangaben: Bruchrechnung → Mathematik, Erdbeben/Vulkan → **Geografie** (der Text sagt „Erdkundeunterricht“). Elektromotor → „Elektrotechnik“, Preisbildung → „Wirtschaftskunde“, beide Labels des Vokabulars, nicht „Arbeitslehre“. Abbildung: „Erdkunde“ → Geografie, „Mathe“ → Mathematik, „Technik“/„Wirtschaft“/„Wirtschaft und Politik“ → leer (`verworfen`). Keine Log-Zeile „Vokabular … nicht verfügbar“. |
| N1 | 6 Betriebsanzeige | ok | `/api/health` ohne Schlüssel 401. Mit Schlüssel nach dem Start `zuletzt: null`, nach einem Zug ohne `Authorization` `direkt` (mit `zuletzt_am`), nach einem Zug mit `Bearer bdt_test…` (Attrappe) `delegation`. `modus: auto`, `warnungen: []`. Öffentliches `/health` vorher und nachher nur `{"status":"ok"}`. |
| alle | 7 Logs | ok | `backend_n.log`: 0 × jobId (roh, aus der DB), 0 × `confirm…`/`replayed`, 0 × Testkonto, Schlüssel, Studio-Schlüssel, `Bearer`, `bdt_`, `JSESSIONID`, Block. 0 × Dateitext, Kurzangaben, Titel, Dateinamen. Einzige Warnung: CORS offen (Vorgabe). |

**Befunde:**

- **MINOR — Satz nach „Abbrechen“ widerspricht sich** (`backend/seeds/06-ablaeufe/themenbaum.yaml:546-549`).
  Auf „Abgebrochen – in WLO wird nichts überschrieben.“ folgt der Text von `ohne_metadaten`: „Die
  Angaben aus WLO ließen sich gerade nicht erzeugen oder lesen.“ Die Person hat aber selbst
  abgebrochen. Reproduktion: Fall 2. Fix-Idee: eigener Schritt bzw. Text für den Abbruch, oder einen
  neutralen Text in `ohne_metadaten` („Ohne Angaben aus WLO – wie soll es weitergehen?“).
- **NIT — „Weiter geht's.“ als Sprechblase über der Box** (`backend/src/boerdi/services/ablauf/zug_basis.py:171-173`):
  Ohne Text des Schritts greift der allgemeine Satz, obwohl gerade nichts weitergeht. Fix-Idee: bei
  `aus.auftrag_freigabe` den Kopf der Box (`auftrag_freigabe.kopf`) oder „Bitte prüfe und gib frei.“
- **NIT — Antwort auf eine veraltete Freigabe ohne Chips** (`backend/src/boerdi/services/ablauf/auftrag_freigabe_zug.py:47`,
  `:125`): Der Lauf wartet weiter an `ohne_metadaten`, die Antwort trägt aber keine Knöpfe. Das Widget
  zeigt nur die Chips der letzten Antwort, die Person muss tippen.
- **NIT (bekannt aus K)** — Leiste `von` steigt beim Sprung nach `ohne_metadaten` (13 → 14).

**Beobachtungen (kein Befund):**

- Das Nachziehen über Einbettungen lief live nicht: Das Modell ordnete in beiden Fällen alle drei
  Materialien zu. Es ist nur durch die Messung in N3 belegt.
- Auf dem WLO-Weg blieb der Entwurf bei „Mittel“ einstufig (3 Punkte, Fach je Punkt leer). Auf dem
  Chat-Weg mit denselben Dateien waren es 2 Ebenen. Ursache ist das Modell, nicht N3.
- N1: Mit `LLM_PROVIDER=openai` beantwortet der Chatbot auch einen Zug mit `bdt_`-Kopf, und die
  Anzeige sagt `delegation`. Sie meldet also die Art des Kopfes, nicht den Weg des LLM. `provider`
  steht daneben in `/api/health`.
- Kurzangaben je PDF 14–17 s (LLM, mit den beiden Vokabularlisten im Prompt).

**Aufgeräumt:** 6 eigene Knoten (4 PDF `boerdi-durchtest-1911n-*`, 2 × `vorgang*.json`, Layout
`flach`, kein Ordner) in den Papierkorb des Testkontos (`DELETE …?recycle=true`, je 200). Der
persönliche Bereich hat wieder 13 Knoten wie vorher. Server gestoppt (Port 8107 frei), Wegwerf-DB
gelöscht (keine `boerdi_durchtest_n` mehr), Wegwerf-Studio-Schlüssel gelöscht. Andere Container,
Dev-DB und die Suite blieben unberührt. Kein Produktivcode geändert.

## Durchtest-Restpunkte behoben (19.11.)

Durchtest gegen Staging 7/7 ok. Drei Restpunkte, je Test zuerst (rot gesehen):
`ohne_metadaten` neutral („Wie soll es ohne die Angaben aus WLO weitergehen?“, de/en; Seed-Fassung
ändert sich erneut — Werksabgleich in ruhiger Zeit); über der Box ihr Kopf („… – bitte prüfen und
freigeben“) statt „Weiter geht's.“; eine veraltete Freigabe antwortet „nicht mehr offen“ mit den
Chips der Stelle, an der der Lauf jetzt wartet. Der Leistensprung in den Ersatzweg bleibt (Paket K,
Punkt 7). Tests: `test_paket_n4_review.py` (Abschnitt „Durchtest-Restpunkte“),
`test_paket_k_durchtest.py::test_r3_3…` (altes Soll).
