# Paket U, Teil a: ein Upload-Weg — Backend, Vertrag des Upload-Felds, Abläufe (2026-11-19)

Plan: `docs/plans/2026-11-17-b-api-delegation-und-upload.md`, §4 (E7–E12), §4a (E13–E18; E13 geht
E8–E10 vor), §5 Paket U (U1–U7, Backend-Anteil von U4). Die Oberfläche (U4-Frontend) folgt in Teil b
auf dem Vertrag unten; der Durchtest U8 danach.

## Warum

Das Upload-Feld hatte drei Knöpfe („Senden“, „Lesen lassen“, „Übertragen“), Inhaltsdateien las der
Chat nie (ohne WLO blieben nur Dateinamen). Nutzer-Ziel (17./18.11.): ein verständlicher Weg — nach
der Auswahl „Wo verarbeiten?“: **hier im Chat** (begrenzt, ohne Anmeldung möglich, liest Inhalte
und Strukturdokumente), **in WLO ablegen und erschließen** (Anmeldung, Kestra über den MCP), klein
**„Nur Namen senden“**. Lange, asynchrone Arbeit gehört nach Kestra. Ergebnis ist immer derselbe
Datenstrom: Teile im Vorgang mit `quelle`, nutzbar von Abläufen, freiem Chat und Werkzeugen.

## Was

### U1 Grenzen (Studio)

- `domain/config_models/upload.py`: `lokal_max_dateien` (Vorgabe 10, 1–30), `lokal_max_mb_gesamt`
  (Vorgabe 50, 1–200). Der Lader gibt das ganze Modell zurück (kein kuratiertes Dict) — die Felder
  wirken ohne weitere Änderung. Seed `01-base/upload-config.yaml` bleibt `upload: {}` (nur der
  Kommentar nennt die Vorgaben). Studio-Katalog `fields-upload.ts` (de/en), Fixture
  `area-schemas.fixture.ts` neu erzeugt.
- `services/dokumente/ablage`: `MAX_JE_SITZUNG = 5` ist ersetzt durch `max_je_sitzung()` und
  `max_bytes_je_sitzung()` aus dem Studio. Gezählt wird die ganze Sitzung (beide Rollen, jeder
  Aufrufer). **Über der Grenze wird abgewiesen statt verdrängt** (`GrenzeErreicht`, Codes
  `grenze_anzahl`/`grenze_gesamt`), unter der Advisory-Sperre; erneutes Hochladen desselben Dokuments
  ersetzt es weiter. Die festen 5 standen außerdem in `api/ui_ablage._STRUKTUR_HOECHSTENS` (WLO-Weg,
  bleibt) und `strukturdokument_teil.HOECHSTENS` (jetzt 35 = 30 im Chat + 5 über WLO).

### U2 Inhalte lesen

- `POST /api/ui/dokumente` nimmt `rolle: inhalt|struktur` (Vorgabe `struktur`). Bei `inhalt` nach
  Umwandlung und Moderation ein LLM-Aufruf (`services/dokumente/inhalt_angaben.py`): Eingabe der
  Anfang ≤ 4000 Zeichen (= der moderierte Anfang), gerahmt als Daten wie die Auszüge des Generators
  bzw. `dokument_lesen` (Endmarken entschärft), Ausgabe geprüft:
  `{titel, beschreibung ≤ 400, schlagworte ≤ 8}`, `fach`/`stufe` nur, wenn sie die Prüfer des
  Entwurfs bestehen. Höchstens 3 Aufrufe zugleich. Scheitert der Aufruf, gilt das Hochladen trotzdem
  (Titel dann aus dem Namen).
- Gespeichert **serverseitig am Upload**: Rolle und Angaben im JSON-Feld `befund`
  (`befund.rolle`, `befund.angaben`) — **keine Migration**. Zeilen ohne Rolle sind Strukturdokumente
  (Stand vor U). Die Lesewege der Strukturdokumente (Entwurf, Teil `document`/`strukturdokument`,
  „das Dokument der Sitzung“) filtern auf Rolle `struktur`.
- Antwort: Befund, `rolle`, bei Inhalten `angaben` — nie der Text. Grenzen vorab (spart Umwandlung
  und LLM) und verbindlich in `ablage.speichern`: 409 `grenze_anzahl`, 413 `grenze_gesamt`.

### U3 Teil `metadaten` lokal

- `services/dokumente/metadaten_lokal.py`: aus den Kurzangaben der gelesenen Inhalte der Teil
  `metadaten` (`wlo.metadaten@1`, `quelle: chatbot`) im Format von `metadaten_lesen` — gelesen von
  `metadaten.als_dokument` und damit von `aus_inhalten`. Nicht lesbare Inhaltsdateien: Titel aus dem
  Namen, Ordnerpfad als Beschreibung, `lesbar: false`. Wiederverwendet aus `inhalte_aus_dateien`
  (Titel, Pfad, Kürzen); dieser bleibt der Weg nur mit Namen.
- Zweistufig: der Platzhalter aus der Antwort (rein, für die Simulation) und die Neuberechnung beim
  Speichern aus der Datenbank (`arbeitsstand._speichern`) — Titel oder Beschreibungen des Browsers
  gelten nie; eine `upload_id`, die kein Inhalt dieser Sitzung ist, wird „nicht gelesen“.

### U4 Vertrag des Moduls (Backend)

- Manifest `ui_upload` (Quelle `frontend/…/ui-upload/manifest.json`, erzeugt nach `manifeste.json`):
  neue Antwortform `aktion: "bereitgestellt"` mit `ort` und `dateien`; Eingabe `orte`,
  `grenzen.lokal_*`; Dienst-Argument `orte`; `vorgang.schreibt` + `metadaten`. Das Vertragsschema
  (`_vertrag/manifest.schema.json`) erlaubt dafür bis zu 6 Teile in `schreibt` (vorher 4).
- `ui_module/upload_orte.py` rechnet die Orte (E13), `dienst_upload.upload_angebot` setzt sie neben
  `schalter`; `ui_module/upload_bereitgestellt.py` prüft die neue Antwort und baut den Rahmen
  (`upload_antwort` delegiert dafür — **Korrektur (Review 19.11., MINOR 7):** die Datei wuchs
  trotzdem auf 493 Zeilen; die Rahmen stehen seither in `ui_module/upload_rahmen.py`).
- **Vertrag für die Oberfläche:** `docs/ui-module.md` §6 „Ein Upload-Weg“ und das README des Moduls.

### U5 Antwort → Teile

`arbeitsstand_teile`: `chat` → `structure`/`struktur`, `strukturdokument` (`quelle: chatbot`),
`metadaten` (`quelle: chatbot`); `wlo` → die Auswahl (`ablage` schreibt wie heute der
Ablage-Endpunkt, danach der Flow über K); `namen` → nur die Auswahl. Ein Start, der den Vorgang
schließt, nimmt lokale `metadaten` mit (`zug._bereitstellung`), Metadaten aus WLO nicht.

### U6 Ablauf (Seed `06-ablaeufe/themenbaum.yaml`, E12)

- `wlo_frage`, `schnell`, `schnell_da`, `dateien_geladen` und der Teil `weg` entfallen; der Ort ist im
  Feld gewählt. 37 statt 40 Schritte (nach dem Backend-Review 38, Schritt `inhalte_menge`).
- `dateien_weg`: `metadaten` zur Auswahl (`block_id`) → Fragen; `ablage` zur Auswahl ohne
  `metadaten` → `metadaten_frage` (Kestra); sonst mit Inhalten → `aus_dateien`; sonst `ohne_daten`.
  Nach `lesen` die neue Verzweigung `angaben_da`. In `zum_entwurf` geht „Grundlage Dokument“ vor
  `metadaten`. Der Platzhalter `{teil.bereit.ohne_gruendlich}` ist mit `schnell` entfallen (der Dienst
  liefert das Feld weiter, kein Werks-Seed liest es).
- Texte nennen „Hochladen“ statt „Senden“/„Lesen lassen“/„Übertragen“.
- Mitgeprüft: `themenbaum_aus_dokument` (Verzweigung zuerst `strukturdokument`, Texte),
  `themenbaum_aus_inhalten` (Feld mit `orte: [wlo]`, Texte); `sammlungsstruktur`, `sammlung_pruefen`
  unverändert. `stumme_enden` zählt `metadaten` als Bereitstellung.

### U7 Freier Chat

- `dokument_lesen` sieht auch die hier gelesenen Inhalte (Liste und Leser mit beiden Rollen); der
  Strukturentwurf liest weiter nur Strukturdokumente.
- Master-Skill `docs/skills/vorgehen-knapp.md`: was nach dem Hochladen bereitliegt (Teile, `quelle`)
  und wie man zugreift (`dokument_lesen`, `$teil`); der Ort wird im Feld gewählt.

### Werkzeuge im Chatbot

`seeds/05-knowledge/mcp-servers.yaml`: die Stapel-Werkzeuge (`wlo_prepare_file_batch`,
`wlo_store_batch_file`, `wlo_store_batch_manifest`, `wlo_list_my_batches`) und die Flow-Werkzeuge
(`wlo_start_flow`, `wlo_flow_status`, `wlo_cancel_flow`, `wlo_list_flows`) stehen in der Liste des
WLO-Servers, mit Kommentar (nur Upload-Feld und Abläufe, nie im Modellkatalog). Geprüft: die Liste
ordnet nur Server zu; Agent- und Muster-Weg bieten nur Katalog-Werkzeuge an
(`agent_tools`, `response_tool_selection._nameable_tools`), das Studio zeigt für sie keinen Schalter.

## Entscheide und Abweichungen vom Plan

1. **Abweisen statt verdrängen** (U1/U2): „Grenzen serverseitig erzwingen“ verträgt kein stilles
   Verdrängen mehr. Folge: eine Sitzung an der Grenze liest erst nach Ablauf der Frist,
   „Arbeitsstand löschen“ oder über WLO weiter; die Oberfläche kennt die Grenzen vorher.
2. **Keine Migration**: Rolle und Kurzangaben im JSON-Feld `befund` statt neuer Spalten.
3. **Kein eigenes „kleines Modell“**: der Code kennt keins; der Aufruf nimmt das Chat-Modell mit
   kurzer Ausgabe und Frist (`simplify:` im Modul). Ein eigenes Modell wäre eine neue Variable.
4. **`schalter()` bleibt ein Satz von Wahrheitswerten**; die Orte (E13) stehen als eigenes Feld
   `orte` daneben (`upload_orte.orte()`), weil Codes und Vorauswahl keine Wahrheitswerte sind.
5. **Grenze abhängig von der Auswahl**: die Belegung früherer Uploads der Sitzung kennt die
   Oberfläche nicht; sie vergleicht die Auswahl mit `grenzen.lokal_*`, der Server weist den Rest mit
   `grenze_*` ab.
6. **`metadaten` nur für Inhalte** (lokal): Strukturdokumente stehen im Teil `strukturdokument`
   (E14 mit Fach/Stufe aus Strukturdokumenten gilt für den WLO-Weg).
7. **U6, Bindung statt Quelle**: `dateien_weg` prüft, ob `metadaten` zur Auswahl gehören
   (`block_id`), nicht nur `quelle: chatbot` — Angaben einer früheren Auswahl zählen so nicht; auch
   Metadaten aus WLO zur selben Auswahl führen direkt zu den Fragen.

## Deploy

- **Keine Migration, keine neue Variable.**
- **Seed-Fassungen ändern sich:** `06-ablaeufe/themenbaum`, `themenbaum_aus_dokument`,
  `themenbaum_aus_inhalten` (laufende oder wartende Läufe brechen beim Werksabgleich ab — in einer
  ruhigen Zeit), `05-knowledge/mcp-servers` (folgenlos fürs Routing; für eine stimmige
  Studio-Anzeige übernehmen). `01-base/upload-config` nur im Kommentar.
- `import-config --werksabgleich` für diese Bereiche, wenn sie auf Staging nicht im Studio angepasst
  wurden.
- Master-Skill aus `docs/skills/vorgehen-knapp.md` gleichzeitig im Repositorium übertragen.
- Image neu bauen (Widget und Modul-Bündel bauen sich mit; das Manifest ist neu). Studio-Bündel neu
  (Katalog). Bis Teil b schickt das alte Modul weiter `erfasst`/`dokument`/`uebertragen` — das
  Backend nimmt sie an.
- OpenAPI neu erzeugt (`/api/ui/dokumente`: Feld `rolle`, Antwortfelder `rolle`/`angaben`),
  `docs/api/bewusste-vertragszusaetze.md` ergänzt.

## Tests

- Neu: `test_paket_u1_grenzen.py`, `test_paket_u_ablage_pg.py` (Grenzen, Rollen gegen Postgres),
  `test_paket_u2_inhalt_angaben.py` (LLM-Attrappe), `test_paket_u2_dokumente_api.py`,
  `test_paket_u4_orte.py` (E13-Regeln, Schema, `grund`), `test_paket_u5_teile.py` (Teile je Ort,
  Neuberechnung, Format gegen `als_dokument`, Größe), `test_paket_u5_bereitstellung.py`,
  `test_paket_u7_dokument_lesen.py`, `test_paket_u6_themenbaum.py` (Verzweigung je Ort),
  vier Tests in `test_werkzeug_freigabe_pfade.py` (Werkzeugliste, nie ans Modell).
- Angepasst (altes Soll): `test_dokument_ablage.py` (Abweisen statt Verdrängen; jeder Test beginnt
  ohne die Dokumente des vorigen), `test_review_tg3def_pg.py` (zwei gleichzeitige: einer
  abgewiesen), `test_review_tg3def.py` (Grenze 35), `test_ui_dokumente_api.py` (Feld `rolle`),
  `test_ui_upload.py` (Grenzen), `test_tg3a_struktur_auswahl.py` (`schreibt` + `metadaten`),
  `test_write_confirm.py` (die acht Backend-Werkzeuge sind keine Kuration), Test-Attrappen mit dem neuen Argument `rolle`
  (`test_arbeitsstand`, `test_dokument_stand`, `test_nachpruefung_tg3def`, `test_review_tg3def`,
  `test_tg3de_strukturdokumente`), `test_master_skill_vorlage` blieb unverändert;
  U6: `test_tg6_themenbaum`, `test_tg6_review`, `test_tg6_review2`, `test_tg6_nachpruefung`,
  `test_paket_k_durchtest`, `test_tw4_seeds`. Frontend: `upload-texte.spec.ts` (Aktion, Teile).

## Geprüft

- Backend gezielt: `pytest -k "upload or dokument or ablage or arbeitsstand or vorgang or ui_modul or
  skill or tg or paket_u or paket_k or seed or ablauf or strukturentwurf or metadaten or openapi or
  werkzeug"` → 3587 passed, 1 skipped, 1 failed (`test_write_confirm`, danach behoben: 88 passed in
  den betroffenen Dateien). Seed-Selbsttests (themenbaum 20/20, aus_dokument 8/8, aus_inhalten 6/6,
  sammlungsstruktur 5/5, sammlung_pruefen 5/5), `pruefe`, `warnungen`, `stumme_enden` ohne Befund.
  `ruff check src tests`: nur ein Fund in `services/ablauf/ausloeser.py:173` (E501), nicht aus
  diesem Paket.
- Frontend: Studio `i18n/catalogue` + `schema-form` 475 passed; `ui-module` `_vertrag` + `ui-upload`
  144 passed (nach Anpassung von `upload-texte.spec.ts`); `module-register.mjs --pruefen` aktuell.
- Nicht gelaufen: volle Backend-Suite, E2E, Chat-Smoke mit echtem LLM.

## Offen

- **Teil b (Oberfläche)**: Chips, ein Knopf „Hochladen“, je Datei Fortschritt und Fehler (inkl.
  `grenze_*`), Antwort `bereitgestellt`; die englischen Texte der Seeds nennen keine Chip-Namen —
  gegen die Labels von Teil b abgleichen. `MAX_STRUKTUR` (5) im Modul gegen `lokal_max_dateien`.
- **U8 Durchtest** nach Teil b (Wegwerf-DB): hier im Chat (3 Dateien), Grenze überschritten, nur
  Namen, freier Chat ohne Ablauf, WLO-Zweig.
- ~~Randfall aus U6: „Ja, verwenden“ mit Dokument und lokalen `metadaten` → `entwurf_inhalte`~~
  (behoben im Backend-Review, Befund 1). Offen bleibt: `dokument_gelesen` prüft nicht, ob
  `strukturdokument` zur aktuellen Auswahl gehört (war vorher so).
- Die Studio-Auswahl für `tools:` der Muster zeigt die acht Backend-Werkzeuge jetzt als Option
  (wirkt nicht, `_nameable_tools` filtert) — ggf. auf Katalog-Werkzeuge einschränken.
- `wlo_list_flows` ruft der Chatbot noch nicht (der Flow-Katalog des Studios fragt über
  `B_API_KEY`).
- Der Dienst `bereitgestellt` liefert `ohne_gruendlich`/`wlo_erschliessen` weiter, kein Werks-Seed
  liest sie mehr.

---

# Teil b: die Oberfläche des Upload-Felds (2026-11-19)

Plan §4 E7/E13, §5 U4 (Frontend). Vertrag aus Teil a (`docs/ui-module.md` §6 „Ein Upload-Weg“).

## Was

- **Ein Weg** im Modul `ui_upload` (`frontend/projects/ui-module/src/ui-upload/`): nach der Auswahl die
  Frage **„Wo sollen sie verarbeitet werden?“** mit zwei Chips („Hier im Chat“, „In WLO ablegen und
  erschließen“), je Chip eine Erklärzeile, gesperrte sichtbar mit dem Grund als Text; ein Hauptknopf
  **„Hochladen“**, daneben **„Nur Namen senden (nichts hochladen)“** und „Andere Auswahl“. „Senden“,
  „Lesen lassen“, „Weiter“ (nach dem Lesen) und „Übertragen vorbereiten …“ sind darin aufgegangen.
- Neue Dateien: `upload-orte.ts` (Regeln: Orte aus `orte`, sonst aus `schalter`; Grenzen `lokal_*`
  gegen die lesbaren Dateien; Vorauswahl-Wechsel), `upload-orte-ansicht.ts` (Chips als Radioknöpfe in
  `fieldset`/`legend`, Erklärzeilen, Datenschutz-Satz je Ort), `upload-chat.ts` (Regeln, Antwort
  `bereitgestellt`), `upload-chat-ablauf.ts` (je Datei nacheinander, Fortschritt, Fehler je Datei,
  „Noch einmal versuchen“/„Ohne diese weiter“, Warten auf „Weiter“ während eines Zugs),
  `upload-chat-ansicht.ts`, `upload-eingabe.ts` (Datei-Eingaben und Ablage aus dem Element gelöst).
  Entfernt: `upload-dokument.ts`, `upload-dokument-ablauf.ts`, `upload-dokument-ansicht.ts`.
- **Antworten**: „Hier im Chat“ → `aktion: "bereitgestellt"`, `ort: "chat"`,
  `dateien: [{i, rolle, upload_id}]`; „In WLO“ → `ort: "wlo"`, `dateien: [{i, rolle}]` je abgelegter
  Datei (auch „angelegt, Inhalt verworfen“) und `ablage`; „Nur Namen senden“ → `ort: "namen"`. Die
  Vormerkung beim Erfassen bleibt `erfasst`. Ältere Antworten (`dokument`, `uebertragen`) zeigt das Modul
  „nur lesend“ weiter.
- **Host-Vertrag**: `ModulHost.hochladen(datei, onFortschritt?, rolle?)` (`_vertrag/modul-host.ts`);
  das Widget reicht `rolle` durch (`block-modul-host`, `widget-modul-host`, `chat-shell`,
  `collection-actions.dokumentLesen`, `shell-contexts`, `chat-api`, `dokument-transport` → Formularfeld
  `rolle`, nur wenn angegeben). Studio-Vorschau-Host nimmt die Rolle an (Beispiel-Angaben bei `inhalt`).
- **Texte** de/en in `upload-texte.ts` (veraltete Texte des Lesens entfernt, `chatFehler` mit
  `grenze_anzahl`/`grenze_gesamt`); in `upload-uebertragen-texte.ts` die Texte des alten Angebots
  entfernt.
- **Seeds (nur Englisch)**: `06-ablaeufe/themenbaum.yaml`, `themenbaum_aus_dokument.yaml`,
  `themenbaum_aus_inhalten.yaml` nennen die Chips jetzt mit ihren englischen Labels
  (“Here in the chat”, “Store and index in WLO”, “Send names only”, “Upload”).

## Entscheide

1. **Chips = native Radioknöpfe** in `fieldset`/`legend` statt Knöpfen mit `aria-pressed`: Pfeiltasten,
   Tab-Halt und das Überspringen gesperrter Orte liefert der Browser (wie `ui_entscheidung`); gewählt
   zeigen Radiokreis, kräftige Umrandung und Fläche (nicht nur Farbe).
2. **„Nur Namen senden“ ist ein Knopf, kein dritter Chip** (E7: „klein daneben“); geht kein Ort, ist er
   der Hauptknopf und „Hochladen“ fehlt.
3. **`MAX_STRUKTUR` bleibt 5**: so viele erlaubt das Antwort-Schema (`zahlen.strukturdokumente`,
   `dokumente`) und die Ablage in WLO (`_STRUKTUR_HOECHSTENS`); „Hier im Chat“ zählt Strukturdokumente
   mit den Inhalten gegen `lokal_max_dateien`. Nur die Begründung im Code ist angepasst.
4. **Orte nur in der Oberfläche gesperrt**: WLO mit mehr als 200 übertragbaren Dateien (`stapel`) bzw.
   ohne übertragbare Art (`keine`) — vorher ein gesperrter Knopf im Angebot.
5. **Fehler beim Vorbereiten der Übertragung** bringt die Frage nach dem Ort zurück; „Hochladen“ versucht
   es neu (vorher eigener Knopf „Übertragen vorbereiten …“).
6. **„Ohne diese weiter“ geht immer** nach einem Fehler, auch bei nur einer Datei: dann antwortet das
   Modul mit den bisher gelesenen (ggf. keiner) — der Weg endet nie in einer Sackgasse.
7. Die Knöpfe nach einem Fehler beschreibt der Fehlersatz (`aria-describedby`) statt eines eigenen
   Namens (der alte Name enthielt die sichtbare Beschriftung nicht, WCAG 2.5.3).
8. **Modul-Budget 20 → 22 kB gzip** (`scripts/check-module-budget.mjs`, wie zuletzt bei U3-3b):
   `ui_upload` misst mit „Wo verarbeiten?“ und „Hier im Chat“ 21,1 kB; alle Module zusammen 45,6 kB
   (Grenze 60 kB bleibt).

## Backend (Lücken im Vertrag, klein)

- **`grenzen.lokal_aufbewahrung_h`** (neu, = Studio `aufbewahrung_h`, 1–72): die Erklärzeile braucht
  „Text bleibt {h} Stunden hier“; der Vertrag gab die Frist nicht her. `dienst_upload.upload_angebot`
  setzt sie, Manifest-Schema ergänzt (`manifest.json` → `manifeste.json` neu erzeugt), Tests
  `test_ui_upload.py`, `test_paket_u4_orte.py` nachgezogen. Neues Manifest-Beispiel „Wo verarbeiten
  (ohne Anmeldung)“ für die Studio-Vorschau.
- **`dienst_upload.nicht_gelesen_satz`** schickte die KI zum Knopf „Lesen lassen“, den es nicht mehr
  gibt — jetzt „Hier im Chat“ und „Hochladen“ (`test_ui_upload.py` angepasst).

## Deploy

- **Modul-Bündel und Widget neu bauen** (`npm run build:widget` bzw. das Image, das sie mitbaut) — sonst
  zeigt das Widget die alten drei Knöpfe. Danach Hard-Reload (das Modul-Bündel ist cachebar).
- Backend-Image neu (Manifest + `lokal_aufbewahrung_h`, Satz an die KI). Keine Migration, keine neue
  Variable.
- Seeds `06-ablaeufe/themenbaum*` ändern sich zusätzlich zu Teil a nur im Englischen —
  `import-config --werksabgleich` wie in Teil a.

## Tests

- Neu: `upload-orte.spec.ts` (Orte aus Vertrag und Schaltern, Grenzen, Vorauswahl-Wechsel, Wahl),
  `upload-chat.spec.ts` (Antworten chat/namen, `upload_id`, Codes), im Element-Spec die Blöcke
  „Wo verarbeiten?“ und „Hier im Chat“ (Zustände leer, Auswahl, gesperrt, lädt, Teilfehler, fertig;
  Fokus, Fortschritt ohne Neuzeichnen, Warten auf „Weiter“, nur lesend je Ort), Widget:
  `dokument-transport.spec.ts` (Feld `rolle`), `block-modul-host.spec.ts` (Rolle durchgereicht).
  E2E neu `e2e/upload-bereitstellen.spec.ts` (Hier im Chat mit Rollen, Pfeiltasten in der Radiogruppe,
  Grenze, 320 px und Zielgröße der Chips).
- Angepasst: `ui-upload.element.spec.ts` (alte Blöcke „Lesen lassen“ ersetzt), 
  `ui-upload-uebertragen.element.spec.ts` und `upload-uebertragen.spec.ts` (Einstieg „Hochladen“,
  Antwort `bereitgestellt`/`wlo`), `upload-texte.spec.ts`; E2E `upload-erfassen`, `upload-uebertragen`,
  `upload-und-fortschritt`; Backend `test_ui_upload.py`, `test_paket_u4_orte.py`;
  `check-module-budget.test.mjs`.

## Geprüft

- `ng test ui-module` 444 passed; `ng test ui` 1518 passed; `ng test studio` 2165 passed.
- eslint auf allen geänderten Dateien ohne Befund; `check:tokens`, `check:radii`, `check:a11y`,
  `check:docs` ohne Befund; `module-register.mjs --pruefen` aktuell.
- `npm run build:widget` grün; Playwright `upload-erfassen`, `upload-uebertragen`,
  `upload-und-fortschritt`, `upload-bereitstellen`: 15 passed. Widget-Budget 195,8/210 kB, Modul-Budget
  s. Entscheid 8. Das Build-Artefakt `nachlade-index.build.ts` ist danach wieder auf dem alten Stand.
- Backend gezielt (ohne Postgres): `test_ui_upload`, `test_paket_u4_orte`, `test_ui_modul_katalog`,
  `test_tg6_themenbaum`, `test_paket_u6_themenbaum`, `test_tw4_seeds`, `test_ablauf_upload_schalter`
  und die Ablauf-Tests der drei Themenbaum-Seeds → 411 passed (Seed-Selbsttests eingeschlossen).

## Offen (Teil b)

- **U8 Durchtest** gegen Wegwerf-DB mit echtem Backend (hier im Chat mit 3 Dateien, Grenze, nur Namen,
  WLO-Zweig) — nicht gelaufen.
- Screenreader-Probe (NVDA/VoiceOver) der Radiogruppe und der gesperrten Chips steht aus; axe läuft im
  Projekt nicht als E2E-Schritt.
- `orte.namen` mit `geht: false` sieht der Vertrag nicht vor; das Modul zeigt „Nur Namen senden“ immer.

## Review-Befunde Oberfläche behoben (19.11.)

Modul `frontend/projects/ui-module/src/ui-upload/`; das Backend behebt seine Befunde parallel und
ergänzt den Vertrag um den Sperrgrund `grenze_sitzung` und die Grenzwerte `grenzen.lokal_frei_dateien`/
`lokal_frei_mb` (Rest der Sitzung). Die Oberfläche dafür ist hier gebaut; fehlen die Felder (älteres
Backend), gilt wie bisher nur die Grenze je Auswahl.

1. **MAJOR – Abbruch an der Sitzungsgrenze:** `grenze_anzahl` beendet den Lauf (neue Phase `halt`,
   `upload-chat.ts`), statt jede weitere Datei scheitern zu lassen. Danach „Mit den gelesenen weiter“
   (Antwort mit den bisher gelesenen) und „Nur Namen senden“ (auch aus diesem Zustand erlaubt). Ohne
   gelesene Datei nur „Nur Namen senden“ (Hauptknopf). `grenze_gesamt` lässt „Ohne diese weiter“ zu.
   Die Sätze nennen nur Knöpfe, die es gibt: `chatFehler.grenze_anzahl` sagt nur, dass die Sitzung voll
   ist, den Weg hängt die Ansicht an („Mach mit den gelesenen weiter oder sende nur die Namen.“ bzw.
   „Sende nur die Namen.“); `grenze_gesamt` sagt „Mach ohne diese weiter; eine kleinere passt
   vielleicht noch.“ (de/en).
2. **MAJOR – anhalten:** „Nach dieser Datei anhalten“ während des Hochladens (wie `anhaltenNachDieser`
   bei WLO; danach gesperrt mit „Hält nach dieser Datei an …“, Fokus auf dem Stand). Danach „Mit den
   gelesenen weiter“ oder „Andere Auswahl“ (ohne gelesene zusätzlich „Nur Namen senden“). Scheitert die
   laufende Datei, bleibt der Fehler stehen; „Noch einmal versuchen“ lädt sie noch, „Ohne diese weiter“
   endet angehalten. `ChatAblauf.trennen()`/`verbinden()` in `disconnectedCallback`/`connectedCallback`:
   ein entferntes Element lädt nach der laufenden Datei nichts mehr hoch und antwortet nicht im
   Verborgenen (auch nicht nach der letzten Datei); zurück im Dokument zeigt es „Angehalten“. Nach
   Fehler oder Ende mit gelesenen Dateien: „Bereits gelesene Dateien bleiben bis zu {h} Stunden hier im
   Chat.“ (de/en, `{h}` = `lokal_aufbewahrung_h`).
3. **MINOR – keine lesbare Datei:** `chatFuer` sperrt „Hier im Chat“ mit `grund: keine` und eigenem Text
   („keine Datei, die der Chat lesen kann – PDF, Word, Text oder Markdown“); sind alle lesbaren zu groß,
   `grenze: datei` („jede Datei ist zu groß für hier (höchstens {mb} MB je Datei)“). Ein Sperrgrund des
   Backends geht vor.
4. **MINOR – veralteter WLO-Fehler:** `hochladen('chat')` setzt eine Übertragung in Phase `fehler`
   zurück — der alte Fehler steht nicht mehr neben dem Fortschritt und zieht den Fokus nicht.
5. **MINOR – Grenze je Datei:** `lokaleGrenzen` liest `lokal_max_mb_datei` (ohne Angabe unbegrenzt);
   `lokaleAuswahl(e, grenzen)` behandelt größere Dateien wie nicht lesbare (nur der Name), der Hinweis
   nennt sie („1 Datei ist größer als {mb} MB – davon geht nur der Name mit.“).
6. **MINOR – Dubletten:** gleicher Name und gleiche Größe gehen einmal hoch; alle betroffenen `i`
   bekommen dieselbe `upload_id` (auch nach „Ohne diese weiter“/„Noch einmal versuchen“).
   **Abhängigkeit Backend:** `ui_module/upload_bereitgestellt.grund` weist heute `upload_id doppelt` ab —
   das muss für verschiedene `i` mit derselben Kennung erlaubt werden, sonst fällt die Antwort durch.
7. **MINOR – Ansagen:** `aria-live` sagt Hochladen und Lesen nur bei der ersten Datei (bzw. der ersten
   nach einem Weitermachen), jeder zehnten und der letzten an (`ansageFaellig`, FE-5); Fehler, Ende und
   Anhalten immer.
8. **MINOR – Doku und Texte:** `docs/ui-module.md` Host-Tabelle `hochladen(datei, onFortschritt?, rolle?)`
   und §6 „Bedienung“ um die Punkte oben ergänzt; Studio `fields-upload.ts` (de/en) mit „Hier im Chat“,
   „In WLO ablegen und erschließen“, „Nur Namen senden“ und den Grenzen statt „Lesen lassen“ (auch die
   Labels der drei Schalter; en „Store and index in WLO“ statt „Store and describe“);
   `lesenNachAnmeldung`/`ablageNachAnmeldung` (de/en) nennen „Hier im Chat“ bzw. „In WLO ablegen“.
   README des Moduls nachgezogen.
9. **NIT – „ohne Anmeldung“:** nur, wenn die Schalter es tragen (`chatOhneAnmeldung`):
   `schalter.dokument_ohne_anmeldung`, sonst (älteres Backend) solange `lesen_nach_anmeldung` nicht
   gesetzt ist. **Abhängigkeit Backend:** das Manifest kennt `schalter.dokument_ohne_anmeldung` noch nicht
   (`additionalProperties: false`), der Dienst setzt es nicht — bis dahin wirkt nur der Rückfall.
10. **NIT – Budget:** `scripts/check-module-budget.mjs` 20 kB je Modul, benannte Ausnahme nur
    `ui-upload`. **Abweichung:** 23 kB statt 22 kB — gemessen 22,5 kB gzip nach diesen Befunden
    (vorher 21,1 kB); das unbenutzte `blaseErfasst` ist entfernt. Summe 47,0/60 kB.
11. **NIT – E2E-Fokus:** `upload-bereitstellen.spec.ts` prüft den Fokus über
    `shadowRoot.activeElement.dataset.fokus` (`s:chat` während des Hochladens; der erste Upload wartet
    dafür auf ein Tor — nach dem Zug setzt das Widget den Fokus in sein Eingabefeld). Neu: ein Lauf mit
    200 % Zoom (Fenster 640 × 400 CSS-Pixel: kein seitlicher Überlauf, „Hochladen“ erreichbar) und
    „Sitzung voll bei Datei 2“ (409 `grenze_anzahl` → „Mit den gelesenen weiter“ → Antwort mit Datei 1).
12. **NIT – Studio-Vorschau:** `VorschauModulHost.hochladen` vergibt je Datei eine eigene `upload_id`.

**Sitzungsrest (Vertrag Backend):** `lokaleGrenzen` liest `lokal_frei_dateien`/`lokal_frei_mb` (0 heißt
voll, Unbrauchbares unbekannt); `chatFuer` prüft nach der Grenze je Auswahl den Rest (`grenze:
frei_anzahl`/`frei_gesamt`, Text „… in diesem Gespräch geht noch 1 Datei“ bzw. „… gehen noch 0,5 MB“,
bei 0 wie `grenze_sitzung`); die Erklärzeile nennt „bis {min(n, Rest)} Dateien“. `orte.chat.grund:
grenze_sitzung` → „nicht wählbar – hier im Chat ist für dieses Gespräch kein Platz mehr“.

*Tests:* neu `ui-upload-chat.element.spec.ts` (16: Grenze bei Datei 2 von 3, Nur Namen an der Grenze,
`grenze_gesamt`, Anhalten, Anhalten + Fehler, Trennen mitten im Lauf und bei der letzten Datei,
Neustart, Englisch, keine lesbare, Grenze je Datei, „ohne Anmeldung“, Sitzungsrest, veralteter
WLO-Fehler, Dubletten, Ansagen), `ui-modul-vorschau-host.spec.ts` (Studio); ergänzt
`upload-orte.spec.ts`, `upload-texte.spec.ts`, `check-module-budget.test.mjs`; angepasst
`ui-upload.element.spec.ts` (Texte zu 8; der alte Test „Grenze → Ohne diese weiter“ prüft jetzt einen
Fehler ohne Aussicht, `abgewiesen`). Rot vor dem Fix gesehen (Typfehler bzw. für 4, 6, 7 gezielt mit
zurückgenommenem Fix).

*Geprüft:* `ng test ui-module` 466 passed, `ng test ui` 1518 passed, `ng test studio` 2166 passed;
`node --test scripts/check-module-budget.test.mjs` 5 passed; eslint der geänderten Dateien ohne Befund;
`check:tokens`, `check:radii`, `check:a11y`, `check:docs` ohne Befund; `module-register.mjs --pruefen`
aktuell; `npm run build:widget` grün, Modul-Budget `ui-upload` 22 508 B gzip (Grenze 23 000), Widget
195,8/210 kB; Playwright `upload-bereitstellen`, `upload-erfassen`, `upload-uebertragen`,
`upload-und-fortschritt`: 17 passed. `nachlade-index.build.ts` danach auf den alten Stand zurück.

*Offen:* Backend-Abhängigkeiten zu 6 und 9 (s. o.); `manifest.json` (Schema `orte.chat.grund`,
`grenzen.lokal_frei_*`) ergänzt der Backend-Agent — hier nicht angefasst. U8 Durchtest und
Screenreader-Probe weiter offen.

## Review-Befunde Backend behoben (19.11.)

Review des Backends zu Teil a; dazu zwei Abstimmungspunkte mit der Oberfläche und zwei Fehler der
vollen Suite. Je Befund erst ein roter Test, dann der Fix.

1. **MAJOR – fremde lokale `metadaten` lenkten den Ablauf um** (Seed `06-ablaeufe/themenbaum.yaml`).
   Nachgestellt mit dem Probe-Skript des Reviews (a: Dokument + Inhalt, „Ja, verwenden“ →
   `soll_ist`; b/c: Thema getippt → `soll_ist`). Fix: `zum_entwurf` prüft erst die Grundlage —
   Dokument, „Meine Dateien“/„Meine Ordner“ (→ neuer Schritt `inhalte_menge`), getipptes Thema,
   ohne Grundlage `bereit.art == dokument` — und zählt Angaben ohne gewählte Grundlage nur, wenn sie
   zur Auswahl gehören (`teil.metadaten.block_id == teil.struktur.block_id`). `inhalte_menge` zählt
   wie bisher (`metadaten.inhalte.4` → `soll_ist`, sonst `soll_wenig`); auf dem Dateien-Weg stammen
   die Angaben aus `dateien_weg`, `angaben_da` oder `aus_dateien`, die alle an die Auswahl binden.
   `angaben_da` bindet jetzt ebenso. „Ja, neue Struktur“ und „Anderes wählen“ verwerfen auch
   `metadaten`. 38 Schritte (höchstens 40). Selbsttests: die drei Wege in bestehenden Fällen
   („Dokument schon gelesen, verwenden“ mit Lehrplan + Inhalt aus einem Feld; „Thema getippt bis zum
   Entwurf“ mit fremden Angaben; „Lerninhalte sind ein Thema“ über „Anderes wählen“ mit gelesenen
   Angaben) — der Seed hat schon 20 Fälle (Obergrenze des Schemas). Die Fixtures für
   `metadaten_lesen` tragen jetzt die `block_id` der Ablage wie das echte Werkzeug.
2. **MAJOR – Datenschutz: Kurzangaben überdauerten das Dokument.** `vorgaenge._entfernen_unter_sperre`
   setzt die Einträge der gelöschten Inhalte im Teil `metadaten` auf „nur Name“ zurück
   (`metadaten_lokal.ohne_uploads`: `lesbar: false`, ohne Titel/Beschreibung/Schlagworte/Fach/Stufe
   des LLM, ohne `upload_id`; Titel und Ordnerpfad aus der Auswahl desselben Felds, sonst „Datei n“).
   Gesucht wird in der Akte und — bei großen Teilen — in der Ablage (`metadaten@n`), in jedem
   Vorgang, also auch im mitgenommenen (`zug._bereitstellung`). `verwaiste_dokument_teile_entfernen`
   sammelt dazu die Kennungen aller lokalen `metadaten`. Gilt für Löschen, Ersetzen, Ablauf und
   „Arbeitsstand löschen“. **Historie:** `metadaten` führt keine (`MIT_HISTORIE` = nur `draft`); wie
   beim Teil `strukturdokument` (dort wird die Historie beim Bereinigen samt Ablage gelöscht) geht
   eine dennoch vorhandene mit.
3. **MAJOR – „Hier im Chat“ trotz voller Sitzung.** `upload_angebot` zählt die nicht abgelaufenen
   Uploads der Sitzung (`ablage.belegung`, über `Umgebung.belegung` im Muster-, Agent- und
   Ablauf-Weg; `treiber.Umgebung.belegung` → `treiber_bloecke.modul_block`). Neu
   `grenzen.lokal_frei_dateien`/`lokal_frei_mb` (abgerundet auf 0,1 MB); ist einer 0,
   `orte.chat = {geht: false, grund: grenze_sitzung}`. Scheitert die Zählung, gilt nur die Grenze
   je Auswahl. Nichts wird gelöscht. Manifest (`ui-upload/manifest.json`) und `manifeste.json`
   (Modul-Register) ergänzt, `docs/ui-module.md` §6.
4. **MINOR – Orte nur in der Oberfläche.** Die offene Frage merkt die erlaubten Orte
   (`upload_bereitgestellt.erlaubte_orte`: nur die mit `ablauf` gesperrten fehlen; in der Simulation
   die Liste der Argumente). Die Antwort prüft sie (`Form.grund_mit_frage` → `ort_grund`),
   `POST /api/ui/dokumente` und `POST /api/ui/ablage/vorbereiten` antworten 403
   `ort_nicht_erlaubt`.
5. **MINOR – `ueber_grenze_anmelden`** erst nach der Einschränkung, nur mit erlaubtem `wlo` und
   startbarem Flow (`upload_orte.orte`).
6. **MINOR – Warten auf einen Platz** liegt mit dem Aufruf unter `asyncio.timeout(FRIST_S)`
   (`inhalt_angaben.ermitteln`); läuft sie ab: `None`, Titel aus dem Namen.
7. **MINOR – Dateigröße.** Die KI-Rahmen (`zeilen`, `ende`, `frage_zeilen`, `_ordner_zeilen` samt
   Dokument-, Ablage- und Fragen-Zeilen, Rahmen-Konstanten) stehen verhaltensgleich in
   `ui_module/upload_rahmen.py` (223 Zeilen); `upload_antwort.py` hat 291. `antwort_formen` und drei
   Tests zeigen auf das neue Modul. `services/arbeitsstand.py` (429) blieb: es wurde nicht berührt.
   `services/vorgaenge.py` wuchs um das Aufräumen von 514 auf 587 Zeilen — das Dokument-Aufräumen dort
   wäre ein eigenes Modul (Folgearbeit).
8. **NIT:** `metadaten_lokal.neu_berechnet(…, sprache=None)` gibt die Sprache weiter (ohne Angabe die
   des Platzhalters, am Titel erkannt; ebenso beim Aufräumen). Die Helfer aus `inhalte_aus_dateien`
   heißen öffentlich `dateien_mit_pfad`, `gekuerzt`, `nummer`, `ordnerpfad`.
9. **NIT:** Der Rahmen `[BEREITGESTELLT …]` nennt je nicht gelesener Datei den Grund — Format, zu
   groß (`max_mb`), sonst Grenze der Sitzung oder Fehler beim Lesen — für Inhalte und
   Strukturdokumente, ohne Namen. In `inhalt_angaben` steht „Antwort als json“ hinter dem
   Daten-Rahmen.

**Abstimmung mit der Oberfläche:**

- **Dubletten:** dieselbe `upload_id` für mehrere `i` ist erlaubt, wenn die Dateien gleichen Namen,
  gleiche Größe und gleiche Rolle haben (`upload_bereitgestellt._dubletten_grund`); sonst weiter
  „upload_id doppelt“. `metadaten` trägt dann je `i` dieselben Angaben (das tat `metadaten_lokal`
  schon; jetzt mit Test).
- **`schalter.dokument_ohne_anmeldung`** setzt `dienst_upload.schalter()` aus `upload-config`;
  Manifest-Schema und `manifeste.json` ergänzt.

**Volle Suite (vor diesen Fixes):**

- `test_tg7_durchtest::test_m4_unter_fuenf_inhalten_die_eigene_frage` (3 Fälle): das Soll stimmte
  (unter 5 Inhalten `soll_wenig`), die Fixture legte aber `metadaten` ohne Auswahl ab — nach Befund 1
  gehören sie zur Auswahl (`block_id` wie `struktur`); Weg mit `inhalte_menge`.
- `test_usage_coverage`: `inhalt_angaben` reicht `usage_acc` an `chat_completion`; der Endpunkt
  bucht den Merkposten sofort für die Sitzung (`usage_store.record_turn_usage`), auch wenn das
  Speichern danach an der Grenze scheitert. Keine Ausnahme in `OHNE_BUCHUNG`.

*Deploy:* Seed `06-ablaeufe/themenbaum` ändert sich erneut (Werksabgleich wie oben). Manifest neu →
Backend-Image und Modul-Bündel neu bauen. Keine Migration, keine neue Variable.

*Tests:* neu `test_review_u_metadaten_aufraeumen.py`, `test_review_u_aufraeumen_pg.py` (Postgres:
Löschen, große Teile, Ersetzen, Aufbewahrungslauf, anderer Inhalt bleibt, Belegung),
`test_review_u_orte_grenzen.py`, `test_review_u_bereitgestellt.py`; ergänzt
`test_paket_u6_themenbaum.py`, `test_paket_u2_inhalt_angaben.py`, `test_paket_u2_dokumente_api.py`,
`test_ui_dokumente_api.py`, `test_ui_ablage_api.py`; angepasst `test_tg7_durchtest.py` (s. o.),
`test_ui_upload.py` (Schalter `dokument_ohne_anmeldung`), `test_tg3de_strukturdokumente.py`,
`test_tg6_themenbaum.py`, `test_tg7_dokument_lesen.py` (Rahmen jetzt in `upload_rahmen`).
Die Attrappen von `run_agent_loop` (`test_respond_agent.py`, `test_agent_prompt_preview.py`) tragen
den neuen Parameter `modul_belegung` (echte Signatur, A4b-Regel).

*Geprüft:* `pytest -m "not pg and not jaeger and not valkey" -k "upload or dokument or ablage or
arbeitsstand or vorgang or ui_modul or skill or tg or paket_u or paket_k or seed or ablauf or
strukturentwurf or metadaten or openapi or werkzeug or usage or review_u or agent or respond or
tool_loop or chat or zug"` → 4586 passed, 1 skipped. Postgres einzeln: `test_review_u_aufraeumen_pg`
6, `test_dokument_ablage` 15, `test_paket_u_ablage_pg` 4, `test_r2h_vorgaenge_sperre` 2 passed.
Seed-Selbsttests aller Abläufe (themenbaum 20/20, aus_dokument 9/9, aus_inhalten 6/6, aus_thema
6/6, sammlungsstruktur 5/5, sammlung_pruefen 5/5, fuehrung 7/7), `pruefe`/`warnungen` ohne Befund;
Probe-Skript des Reviews: a → `entwurf_dokument`, c → `entwurf_thema`. `ruff check src tests` ohne
Befund. Frontend: `module-register.mjs --pruefen` aktuell, `module-register.test.mjs` 20 passed,
`ng test ui-module` 466 passed, `check:docs` ohne Befund. Nicht gelaufen: volle Suite, E2E.

## Zweites Review behoben (19.11.)

1 MAJOR, 5 MINOR, 6 NIT; jeweils Test bzw. Spec zuerst (rot gesehen), dann der Fix.

1. **MAJOR – Dubletten-Schlüssel:** Die Oberfläche entdoppelte nach Name und Größe, der Server
   (`upload_bereitgestellt._dubletten_grund`) verlangt zusätzlich dieselbe Rolle — dieselbe Datei als
   Strukturdokument und als Inhalt bekam eine Kennung, und die Antwort fiel durch. Jetzt
   `dublettenSchluessel` in `upload-orte.ts` (von `upload-chat-ablauf.ts` genutzt): Rolle, Größe, Name
   und im Browser das Änderungsdatum (`lastModified`). `docs/ui-module.md` (Bedienung und Vertrag
   „Dubletten“) und README angeglichen. Element-Test: Lehrplan in der Wurzel (Strukturdokument) und
   Kopie in `Material/` (Inhalt) gehen getrennt hoch, je Rolle eine eigene `upload_id`.
2. **MINOR – Datenschutz-Satz:** Die Frist beginnt bei jeder Nutzung neu (`ablage.beruehren`).
   `datenschutzChat`, `bleibenHier` (de/en): „… bis zu {h} Stunden nach der letzten Nutzung …; ein
   daraus erstellter Entwurf bleibt im Arbeitsstand.“; die Erklärzeile `erklaerChat`: „Text bleibt bis
   zu {h} Stunden nach der letzten Nutzung hier“ (en „… for up to {h} hours after last use“, „work in
   progress“ wie „Delete work in progress“ im Chat).
3. **MINOR – Kommentar und Schlüssel:** Der falsche Kommentar („so ersetzt der Server ein Dokument“)
   ist weg; der Server ersetzt nur bei gleichem Text, darum gehen zwei Dateien mit gleichem Schlüssel
   einmal hoch. `lastModified` steht im Schlüssel (s. 1).
4. **MINOR – doppelt gezählte Dubletten:** `lokaleAuswahl` zählt `anzahl` und `bytes` über den
   Schlüssel (Dubletten einmal); `lesbar` trägt weiter alle `i` (jede bekommt ihre `upload_id`).
   `chatFuer` prüft `lokal_max_*` und `lokal_frei_*` gegen `anzahl`/`bytes`. Spec in
   `upload-orte.spec.ts`.
5. **MINOR – Ausweg bei voller Sitzung:** `sitzungVoll(h, wlo)` statt `gesperrt.grenze_sitzung`:
   „hier im Chat ist für dieses Gespräch kein Platz mehr – wieder frei nach {h} Stunden ohne Nutzung
   oder mit „Arbeitsstand löschen“ – oder in WLO ablegen“ (de/en). Beim Rest 0 (`lokal_frei_*`) ohne
   den WLO-Teil — dort sagt ihn `ueber_grenze_anmelden` („– mit Anmeldung über WLO“) bzw. der Chip.
6. **MINOR – `vorgaenge.py` (587 Zeilen):** Das Aufräumen der Dokumente (`dokument_teile_entfernen`
   bis `_metadaten_kennungen`) liegt verhaltensgleich in `services/vorgaenge_dokumente.py` (215
   Zeilen; `vorgaenge.py` jetzt 391). Code unverändert verschoben; die Helfer (`_aus_ablage`, `_weg`,
   `_ablegen`, `_groesse`, `_jetzt`, `INLINE_BYTES`) importiert das neue Modul aus `vorgaenge`.
   **Keine Rückleitung in `vorgaenge`:** der einzige Aufrufer (`services/dokumente/ablage.py`) und die
   zwei Tests, die private Helfer riefen (`test_dokument_ablage._entfernen_unter_sperre`,
   `test_review_u_metadaten_aufraeumen._metadaten_bereinigen`), nutzen das neue Modul — ein
   Rück-Import in `vorgaenge` wäre ein Importkreis.
7. **NIT – `ort_nicht_erlaubt`:** eigener Satz („In diesem Ablauf ist „Hier im Chat“ nicht
   vorgesehen.“, en) und wie `grenze_anzahl` ein Ende (`halt` mit `code`) statt eines Fehlers je Datei.
8. **NIT – `_GRUENDE` „sonst“:** „nicht hochgeladen: Grenze, Fehler oder angehalten“ (Doppelpunkt
   statt Klammer — der Satz steht schon in Klammern); `test_review_u_bereitgestellt.py` angepasst.
9. **NIT – `metadaten.als_dokument`:** Der Docstring nennt die lokalen Kurzangaben (`quelle: chatbot`)
   des Chat-Modells über den moderierten Anfang.
10. **NIT – `upload_rahmen.py`:** Beide Kommentare berichtigt: spät geladen wird `dienst_upload` (MCP,
    Katalog); die Config lädt das Modul über `upload_bereitgestellt` schon beim Import.
11. **NIT – Budget:** Grenze unverändert (`ui-upload` 23 kB). Gemessen jetzt **22 828 B gzip** (mit
    diesen Befunden). **Nächster Schritt statt einer höheren Grenze:** die Texte und Ansicht der
    WLO-Übertragung (`upload-uebertragen*.ts`) als zweites, erst bei Ort `wlo` nachgeladenes Bündel.
12. **NIT – Balken und Ansage:** `<progress>` trägt ein festes `aria-label` „Datei k von n“ (`dateiVon`,
    de/en), den Wert meldet das Element selbst; der Fortschritt ändert nur den Wert. „wird gelesen“
    wird angesagt, wo das Hochladen dieser Datei angesagt wurde — also auch die erste nach einem
    Weitermachen (gedrosselt wie „sendet“).

*Tests:* `ui-upload-chat.element.spec.ts` (+3: zwei Rollen, `ort_nicht_erlaubt`, Balken-Label und
Ansage nach dem Weitermachen; Dubletten-Test um „anderes Änderungsdatum“ ergänzt; Hilfsdatei mit
festem `lastModified`), `upload-orte.spec.ts` (Dubletten zählen einmal), `upload-texte.spec.ts`
(Frist, Entwurf, `sitzungVoll`, `dateiVon`), Textanpassungen in `ui-upload.element.spec.ts` und
`e2e/upload-bereitstellen.spec.ts`; Backend `test_review_u_bereitgestellt.py`, Importe in
`test_dokument_ablage.py` und `test_review_u_metadaten_aufraeumen.py`.

*Geprüft:* `ng test ui-module` 471 passed; Studio `ui-modul-vorschau*` 70 passed, ui
`dokument-transport` 8 passed; eslint ohne Befund; `check:tokens`, `check:radii`, `check:a11y`,
`check:docs`, `module-register --pruefen` ohne Befund. `npm run build:widget` grün, Modul-Budget
22 828/23 000 B; Playwright `upload-*` 17 passed; `nachlade-index.build.ts` zurückkopiert. Backend
(volle Suite lief parallel): `pytest -m "not pg and not jaeger and not valkey" -k "upload or dokument
or ablage or vorgang or metadaten or bereitgestellt or rahmen or arbeitsstand or aufraeumen"` 829
passed, 1 skipped; `ruff check src tests` ohne Befund. **Nicht gelaufen (pg):**
`test_review_u_aufraeumen_pg.py`, die pg-Fälle von `test_dokument_ablage.py` und
`test_r2h_vorgaenge_sperre.py`.

## Durchtest (19.11.)

U8 gegen ein echtes lokales Backend (Staging-Kopie) auf Port 8107, Wegwerf-DB `boerdi_durchtest_u`
(Compose-Postgres, Name vor dem Start geprüft), LLM nativ `gpt-6-luna`, Master-Skill lokal
(`vorgehen-knapp.md`), Staging-MCP. API-Ebene wie das Widget: `POST /api/ui/dokumente` mit `rolle`,
dann `aktion: bereitgestellt`, dann die Züge. Testdateien Erdkunde (Vulkantypen.pdf,
Plattentektonik_Arbeitsblatt.docx, Erdbeben_Entstehung.md, Strukturdokument Lehrplan…md). Skripte
`*_u.py`, Protokolle `lauf_u_*.log`, `backend_u.log` im Scratchpad unter `tg7/`.

| Fall | Ergebnis | Beleg |
|---|---|---|
| 1 Hier im Chat, ohne Anmeldung, „Themenbaum erstellen“ | ok | `orte`: Vorauswahl `chat`, `wlo` `nur_angemeldet`. 3 Inhalte → je 200 mit `angaben` (pdf 16 s, docx 29 s, md 2 s), Strukturdokument 200 ohne `angaben`. Nach `bereitgestellt`/`chat` direkt „Wofür ist der Baum?“ (keine zweite Frage nach dem Weg); Teile `metadaten` (`quelle: chatbot`, 3 × `lesbar: true` mit `upload_id`, `block_id` = Auswahl) und `strukturdokument` (`quelle: chatbot`). „Trotzdem nur meine Dateien“ → Entwurf „Plattentektonik, Vulkane und Erdbeben“, Fach Geografie, Punkte Plattentektonik/Vulkane/Erdbeben — passend, kein Platzhalter. `usage_events` 0 → 3 nach dem Hochladen, 4 am Ende. |
| 2 Grenze (`lokal_max_dateien` = 2 in `config_areas`) | ok | `grenzen.lokal_max_dateien` 2, `lokal_frei_dateien` 2, `chat.ueber_grenze` gesetzt (3 lesbare > 2 → die Oberfläche sperrt). md + md → 200, pdf → 409 `grenze_anzahl` (0,0 s, vor Umwandlung und LLM); `metadaten` führt das pdf als `lesbar: false`. Neues Feld in derselben Sitzung: `chat {geht: false, grund: grenze_sitzung}`, `lokal_frei_dateien` 0, Vorauswahl `namen`; Hochladen dort → 409 `grenze_anzahl`. Config danach zurück. |
| 3 Nur Namen | ok | Teile nur `struktur`/`structure` (+ `metadaten` aus `aus_dateien`, `quelle: dateinamen`), kein `strukturdokument`, 0 Uploads, 0 Verbrauch; weiter mit „Wofür …“, Entwurf (Soll) „Plattentektonik und Naturgefahren“. |
| 4 Freier Chat ohne Ablauf | ok | Agent ruft `ui_upload` (Log „Agent-Modus“); docx als Inhalt; Frage nach Gruppen und Kartenfarbe → zweimal `dokument_lesen`, Antwort „sieben Gruppen … orangefarben“ (nur im Dokument). |
| 5 Datenschutz (Löschen) | ok | `POST /api/ui/dokumente/loeschen` 204, Zeile weg; Eintrag in `metadaten`: `lesbar: false`, ohne `upload_id`, Titel aus dem Namen, Beschreibung = Ordnerpfad; Beschreibung/Schlagworte des LLM nicht mehr im Teil. Andere Einträge und `strukturdokument` unverändert. |
| 6 Mit Anmeldung (nur Angebot) | ok | `orte`: Vorauswahl `wlo`, `wlo {geht: true}` ohne Hinweis; persönlicher Bereich 13 → 13 Knoten, 0 Aufträge. |
| 7 Logs | ok | `backend_u.log`: 0 × Dateinamen, 0 × Dateitext, 0 × Kurzangaben/Antwort, 0 × Testkonto/Schlüssel/Bearer/Block/JSESSIONID; nur die zwei bekannten Start-Warnungen. |

**Befunde:**
- **MINOR — `chat.ueber_grenze_anmelden` ist unerreichbar** (`ui_module/upload_orte.py:86-89`): die
  Bedingung verlangt `not person` und `_flow_da()`, `_flow_da()` → `auftrag_zug.kann_starten` →
  `starter()` gibt ohne Anmeldung `None` (`services/ablauf/auftrag_zug.py:91`). Ohne Anmeldung kommt
  darum immer `ueber_grenze` (Fall 1–3, obwohl der Staging-MCP den Flow führt und angemeldet `wlo`
  ohne Hinweis geht, Fall 6) — der Hinweis aus E13 („mit Anmeldung über WLO“) fehlt. Fix-Idee: ohne
  Anmeldung die Freigabe des Flows prüfen (`mcp_starter.flow_erlaubt` + MCP kennt `wlo_start_flow`)
  statt eines Starters für diesen Zug.
- **NIT — Text auf dem Namensweg** (`seeds/06-ablaeufe/themenbaum.yaml:453`): „Die Angaben zu deinen
  Dateien liegen bereit“ auch, wenn nur Namen gesendet wurden.
- **NIT (bekannt)** — `bereit.ohne_gruendlich` nennt noch „Gründlich über WLO“
  (`services/ablauf/werkzeuge.py:202`); kein Seed liest es.
- Beobachtung: auf dem Chat-Weg trägt der Entwurf keine `inhalte` je Punkt (lokal ohne node_id) und
  bleibt mit „Ist“ und 3 Dateien bei 3 Punkten auf einer Ebene, obwohl „Mittel“ gewählt war — die
  Frage „sehr klein“ hatte darauf hingewiesen. Fach je Inhalt mal „Erdkunde“, mal „Geografie“.

**Hinweis zur Prüfumgebung:** Im ersten Lauf brachen pdf/docx nach 60 s ab (504 `zu_langsam`): der
Kindprozess der Umwandlung importiert unter Windows (spawn) `__main__` neu, und das Server-Skript
startete ohne `if __name__ == "__main__"` einen zweiten uvicorn. Kein Produktfehler (Betrieb über
die uvicorn-CLI); das Skript ist korrigiert, alle Ergebnisse oben stammen aus dem zweiten Lauf.

**Aufgeräumt:** Server gestoppt (Port 8107 frei), Wegwerf-DB gelöscht (keine `boerdi_durchtest_u`
mehr), Config der DB vorher zurückgesetzt; keine Knoten im Repository angelegt; andere Container,
Dev-DB und die parallel laufende Suite unberührt.

## Durchtest-Befunde behoben (19.11.)

- **MINOR `ueber_grenze_anmelden` kam nie:** Ohne Anmeldung gibt es für den Zug keinen Starter, also
  war `_flow_da()` immer falsch. Neu `upload_orte._flow_nach_anmeldung()` (MCP führt die
  Flow-Werkzeuge und der Metadaten-Flow ist freigegeben) entscheidet, ob die Anmeldung hilft. Test
  `test_ohne_anmeldung_zaehlt_der_flow_nach_der_anmeldung` mit der echten Funktion.
- **NIT Seed `entwurf_inhalte`:** Der Satz sagt jetzt „ihre Angaben oder ihre Namen“, passt also
  auch zum Weg „Nur Namen senden“.
- **NIT `gruendlichNurAngemeldet`/`gruendlichNichtDa`:** nennen jetzt „In WLO ablegen und
  erschließen“ (en „Store and index in WLO“) statt „Gründlich über WLO“.
- **Beobachtung, offen:** Auf dem Chat-Weg trägt der Entwurf keine `inhalte` je Punkt (Zuordnung
  Datei → Punkt, wie beim Datei-Weg nach TG-7), und das Fach je Inhalt schwankt zwischen
  Bezeichnungen (Erdkunde/Geografie). Steht in `offene-befunde-und-todo.md`.
