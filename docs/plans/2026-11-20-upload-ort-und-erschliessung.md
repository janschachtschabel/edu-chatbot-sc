# Plan 2026-11-20 (nachmittags): Upload-Ort, Rollen und Erschließung je Anwendungsfall

Stand: Plan, vom Nutzer freigegeben („überarbeite den plan wie empfohlen und setze es um“, 20.11.).
Faktenlage: Bestandsaufnahme vom 20.11. (Datei:Zeile im Verlauf; Kurzfassung in §2).

## 1 Ziel und Entscheide

**Ziel:** Mit WLO-Anmeldung ist „In WLO ablegen und erschließen“ (Kestra) der Normalfall — auch für
Lehrpläne; „Nur hier im Chat lesen“ ist der Weg ohne Anmeldung und für Dateien, die nicht nach WLO
sollen. Was vorausgewählt ist, legt **der Anwendungsfall im Studio** fest, nicht der Code. Jede Option,
jede Frage und jeder Knopf sagt sichtbar, was passiert.

| Nr | Entscheid (Nutzer 20.11.) |
|---|---|
| UO-1 | Eine Frage „Wo sollen die Dateien verarbeitet werden?“ mit zwei Antworten: **In WLO ablegen und erschließen** / **Nur hier im Chat lesen**; „Nur die Dateinamen senden“ bleibt Nebenknopf. Ohne Anmeldung ist WLO ausgegraut, mit Anmelde-Link. |
| UO-2 | Häkchen **„Metadaten von WLO erzeugen lassen“** unter WLO, ab Werk an; Hinweis: „WLO setzt dabei Titel, Beschreibung, Fach, Stufe und Schlagworte neu – der Dateiname bleibt nicht der Titel.“ Ohne verfügbaren Flow: kein Häkchen, „nur ablegen“ mit Grund. |
| UO-3 | **Der Klick „In WLO ablegen und erschließen“ ist die Zustimmung** zum Ablegen und zum Metadaten-Flow — nur für die Knoten, die genau dieser Upload neu angelegt hat (Server prüft). Für vorhandene Inhalte bleiben Rückfrage und Freigabe-Box. Die Rückfrage „Metadaten erzeugen?“ entfällt auf den Upload-Wegen. Sicherheitsrelevant → zweites Review. |
| UO-4 | Rolle je Datei mit drei Werten + „Nicht verwenden“: **Gliederung** (liefert die Struktur, wird nicht einsortiert), **Material** (wird einsortiert), **Gliederung und Material**. Technisch Rollenwert `beides` neben `struktur`/`inhalt` (alte Einträge bleiben gültig). |
| UO-5 | Vorauswahl je Fall (Studio): Themenbaum aus Dateien/Ordnern und aus Lehrplan → `auto` (WLO, wenn angemeldet und Flow da, sonst Chat); freier Chat („neuen Inhalt aus einem Dokument“) → **Chat**, auch angemeldet. Keine Erinnerung an die letzte Wahl. |
| UO-6 | Dokument-Weg im Themenbaum bekommt den Flow (E13/E14 vom 17.11.; hebt E3 vom 20.11. auf). |
| UO-7 | „Gliederungsdatei behalten oder aus WLO löschen?“ erst, wenn der MCP eigene Inhalte löschen kann — Wunsch an den MCP-Entwickler. Ein Umwandlungs-Flow (Markdown mit Gliederung) bleibt Wunsch E15; die Stelle ist vorbereitet (Flow am Auftragsschritt, nicht im Code). |
| UO-8 | Prüfung meldet nichtssagende Beschriftungen („OK“, „Weiter“, „Ja“, „Los“ …) an Optionen, die zu einem schreibenden Schritt führen. |

## 2 Was bisher am Studio vorbei fließt (Bestandsaufnahme §11) und wohin es wandert

| Heute im Code | Neu |
|---|---|
| Vorauswahl `upload_orte.py:111-115` (WLO wenn voller Weg, sonst Chat → WLO → Namen) | Schritt-`daten.vorauswahl: auto\|wlo\|chat` (Vorgabe `auto` = bisherige Regel); freier Chat: Studio „UI-Module → Hochladen“ `vorauswahl` (Vorgabe `chat`). Sperrgründe (Anmeldung, Grenzen, Flow) bleiben Code — globale Regeln. |
| `einzeldatei_als_struktur` steuert Rollen-Vorschlag, Beschriftung „nur ablegen“ (`upload-orte.ts:120`, `upload-orte-ansicht.ts:55-62`), Hinweis (`upload-ansicht.ts:405-409`), KI-Text (`dienst_upload.py:141-167`), Themenbaum-Angebot (`upload_rahmen.py:97-102`) | Schritt-`daten.rolle_vorgabe: auto\|gliederung\|material\|beides` (`auto` = heutige Regel: Lehrplan-Muster). `einzeldatei_als_struktur: true` wird beim Lesen zu `rolle_vorgabe: gliederung` (alte Fassungen bleiben gültig), steuert aber nicht mehr „kein Flow“. |
| Ob nach dem Ablegen erschlossen wird: nur über Rückfrage im Seed; Beschriftung hängt an `einzeldatei_als_struktur` | Schritt-`daten.erschliessen: true\|false` (Vorgabe des Häkchens, ab Werk `true`); die Person kann es umstellen; das Ergebnis steht im Teil `ablage.erschliessen`. |
| Zustimmung zum Flow nur über Rückfrage + Freigabe-Box (`treiber.py:478-489`, `auftrag_freigabe`) | Auftragsschritt-Feld `zustimmung: freigabe\|upload` (Vorgabe `freigabe`); `upload` gilt nur, wenn alle `node_ids` frisch von diesem Upload-Block stammen und `ablage.erschliessen` gesetzt ist — sonst fällt der Lauf auf die Freigabe-Box zurück. |
| Studio zeigt Modul-`daten` als freie Tabelle | Studio zeigt für Modul-Schritte die Parameter des Moduls (Name, Beschreibung, erlaubte Werte aus dem Manifest) als Hinweis unter der Tabelle (P6). |
| bleibt Code (global, begründet) | Sperrgründe der Orte, Grenzen, Struktur-Formate/Höchstzahl, Flow-Verfügbarkeit (`METADATEN_FLOW`), md/txt aus dem Flow, Teil-Formate, Texte der Oberfläche (i18n) |

## 3 Pakete

Jedes Paket: Schritt 0 `/better-coding-workflow` (+ `/better-coding-frontend` bei UI), Tests zuerst,
Review je Paket mit Behebung; P3 zusätzlich zweites, unabhängiges Review (Sicherheitsregel).

### P1 — Rollen: Gliederung / Material / beides
- Frontend `ui-upload`: `Rolle` + `'beides'` (`upload-erfassen.ts:11`, `_vertrag/modul-host.ts:104`),
  Auswahl „Gliederung“ / „Material“ / „Gliederung und Material“ / „Nicht verwenden“ (de/en) mit einer
  Legende unter der Liste (was jede Rolle bewirkt); Höchstzahl 5 gilt für Gliederung und beides.
- Backend: ein Modul `ui_module/rollen.py` mit `ist_gliederung(r)` (struktur, beides) und
  `ist_material(r)` (inhalt, beides); alle Lesestellen (Bestandsaufnahme §2 Tabelle) darauf umstellen.
  MCP-Abbildung: `beides` → `structure` (wird als Strukturdokument gelesen), im Teil bleibt `beides`.
- `POST /api/ui/dokumente` und `ui_ablage.Eintrag` nehmen `beides`.
- Tests: Rollen-Hilfen, Strukturdokument-Teil aus `beides`, lokale Metadaten aus `beides`, Ordner-
  Entwurf, Antwortprüfung; Frontend-Spezifikationen der Auswahl und der Legende.

### P2 — Ort, Vorauswahl, Häkchen, Wortlaut
- Manifest `dienst.parameter` + `eingabe`: `vorauswahl`, `rolle_vorgabe`, `erschliessen`
  (`frontend/projects/ui-module/src/ui-upload/manifest.json`, `npm run module:register`).
- `dienst_upload.upload_angebot` / `upload_orte.orte`: Schritt-Vorgaben nur aus einem Ablauf;
  freier Chat aus `upload-config.vorauswahl` (Modell `config_models/upload.py`, Seed
  `01-base/upload-config.yaml`, Studio-Feldtexte `fields-upload.ts`). `auto` = bisherige Regel.
- Frontend: Häkchen unter WLO (nur wenn der Flow da ist), Hinweis zum Titel, Beschriftungen und
  Erklärungen nach §4, Knopf je Ort („In WLO ablegen und erschließen“ / „In WLO ablegen“ / „Hier
  lesen“); `nurAblegen` an `einzeldatei_als_struktur` entfällt.
- `ui_ablage` `/vorbereiten` nimmt `erschliessen` (nur `true`, wenn der Flow verfügbar ist) und
  schreibt es in den Teil `ablage`.
- Budget `ui-upload`: benannte Ausnahme 24 → 26 kB, wenn nötig (begründet in `check-module-budget.mjs`).

### P3 — Zustimmung durch den Upload-Klick (sicherheitsrelevant)
- `domain/config_models/ablauf.py`: Auftragsschritt `zustimmung: freigabe|upload` (Vorgabe `freigabe`).
- `treiber.py` (Auftrag mit `repo_schreibt`): bei `zustimmung: upload` prüft der Server
  (`services/ablauf/upload_zustimmung.py`, neu): persönliche Anmeldung; Teil `ablage` mit
  `erschliessen: true`; alle aufgelösten `node_ids` ⊆ `stored`-Knoten dieses `ablage`-Teils (gleicher
  `block_id`, nicht `frueher`); Aufrufer = Anmelder des Uploads. Dann `vorlegen` und `bestaetigen` im
  selben Zug ohne Box (die MCP-Vorschau/Bestätigung bleibt der Weg). Sonst: Freigabe-Box wie bisher.
- `pruefung.py`: `auftrag_rueckfrage` gilt bei `zustimmung: upload` als erfüllt, wenn `node_ids` aus
  `$teil: ablage` kommen und ein `ui_upload`-Schritt vorausgeht; sonst Befund `zustimmung_upload`.
  `werkzeuge.ablauf_schreibt_selbst` bleibt falsch (es schreibt nur nach dem eigenen Klick).
- Tests: Zustimmung gilt (frische Knoten) / gilt nicht (fremde, `frueher`, ohne Häkchen, anderer
  Aufrufer, abgemeldet) → Box; Prüfung.

### P4 — Seed „Themenbaum erstellen“
- `metadaten_frage` entfällt; neu `erschliessen_weg` (Verzweigung): `ablage.erschliessen` → `metadaten`
  (`zustimmung: upload`), sonst `lesen`. `ordner_geladen`, `dateien_weg` und `dokument_gelesen` (neu:
  WLO-Ablage dieses Blocks zuerst) führen dorthin. 40 Schritte bleiben.
- Upload-Schritte: `dokument_laden`/`dokument_chat` `rolle_vorgabe: gliederung`, `ordner_laden`/
  `dateien_laden` `rolle_vorgabe: material`, alle `vorauswahl: auto`, `erschliessen: true`.
- Texte der Schritte sagen die Folge (Dauer, was WLO tut); Selbsttests im Seed neu für den
  Dokument-Weg über WLO (mit/ohne Häkchen) und Chat.
- E3 (Plan 2026-11-20 §8) aufgehoben; Seed-Kopf und Doku angleichen.

### P5 — Prüfung: nichtssagende Knöpfe
- `pruefung.py` im Block der schreibenden Auftragsschritte: Optionen mit Ziel auf den Schritt und
  Beschriftung aus {ok, okay, weiter, ja, nein, los, start, go, yes, next} (ohne Satzzeichen) → Befund
  `knopf_nichtssagend`; Texte de/en. Alle Werkseeds bestehen.

### P6 — Studio: Modul-Parameter sichtbar
- Für `typ: modul` zeigt das Studio unter „Daten des Moduls“ die Parameter aus dem Manifest
  (`dienst.parameter`: Name, Beschreibung, erlaubte Werte), damit `vorauswahl`, `rolle_vorgabe`,
  `erschliessen` ohne Code-Kenntnis pflegbar sind. Prüfung: unbekannte Werte melden (heute nur Namen).

### P7 — Doku und Rückmeldungen
- `docs/ui-module.md`, `docs/ablaeufe.md`, Übergabe-Betrieb; Änderungsnotiz; offene Befunde.
- Rückmeldung an den MCP-Entwickler: Werkzeug „eigene Inhalte löschen“ (UO-7); an die Flow-Autoren:
  E15 Umwandlungs-Flow.

## 4 Wortlaut (de; en sinngemäß)

| Stelle | Text |
|---|---|
| Frage | Wo sollen die Dateien verarbeitet werden? |
| WLO | **In WLO ablegen und erschließen** — Deine Dateien werden Inhalte in deinem persönlichen Bereich in WLO und bleiben dort. WLO liest den Text und erzeugt Titel, Beschreibung, Fach, Stufe und Schlagworte. Dauert ein paar Minuten. |
| Häkchen | Metadaten von WLO erzeugen lassen — WLO setzt dabei Titel, Beschreibung, Fach, Stufe und Schlagworte neu; der Dateiname bleibt nicht der Titel. Ohne Häkchen: nur ablegen. |
| WLO ohne Flow | **In WLO ablegen** — … Metadaten kann WLO gerade nicht erzeugen ({Grund}). |
| Chat | **Nur hier im Chat lesen** — Nichts wird in WLO gespeichert. Der Chat liest den Text (auch von Scans) und vergisst ihn spätestens {h} Stunden nach der letzten Nutzung. Bis {n} Dateien. |
| WLO ohne Anmeldung | In WLO ablegen und erschließen – nur mit WLO-Anmeldung. [Anmelden] |
| Nebenknopf | Nur die Dateinamen senden (der Inhalt bleibt auf deinem Gerät) |
| Knopf | „In WLO ablegen und erschließen“ / „In WLO ablegen“ / „Hier lesen“ |
| Rollen-Legende | Gliederung: liefert die Struktur, wird nicht einsortiert · Material: wird in den Baum einsortiert · Gliederung und Material: beides |
| Warten | WLO erschließt deine Dateien: {k} von {n} fertig. Du kannst warten oder später unter „Meine Vorgänge“ weitermachen. |

## 5 Abnahme

- Backend-Suite, Frontend-Tests, CI-Schritte lokal, E2E grün; ruff sauber; Prüfung aller Werkseeds leer.
- Durchtest Wegwerf-DB (Anmelde-Attrappe, MCP-Attrappe für Flow): Lehrplan → WLO mit Häkchen →
  Flow ohne Box → Volltext → Entwurf; ohne Häkchen → kein Flow; Chat → wie bisher; fremde Knoten →
  Box; freier Chat angemeldet → Chat vorausgewählt.
- Reviews: je Paket; P3 zweites Review.

## P1 umgesetzt (20.11., nicht committet, noch ohne Review)

**Was:** Rolle `beides` („Gliederung und Material“) neben `struktur`/`inhalt`; Auswahl in Klartext
(de: Gliederung / Material / Gliederung und Material / Nicht verwenden; en: Outline / Material / Outline
and material / Don't use) mit Legende unter der Liste (`#u-legende`, jedes Auswahlfeld verweist per
`aria-describedby`). Höchstzahl 5 und lesbare Formate gelten für `struktur` und `beides` (Modul und
`ui_ablage.Vorbereiten`). Alte Einträge bleiben gültig.

**Entscheide unterwegs:**
- `zahlen.strukturdokumente` = `struktur` + `beides`, `zahlen.inhalte` = nur `inhalt` — so bleibt
  `inhalte + strukturdokumente` die Zahl der verwendeten Dateien (drei Anzeigen summieren sie).
  Rahmen „hier im Chat gelesen“ zählt `beides` bei Inhalten **und** Strukturdokumenten.
- MCP: `beides` → `structure`; bestätigt die Vorschau `structure`, bleibt im Teil `ablage` `beides`
  (`vorgang_teil._rolle`), ebenso in `frueher`.
- Einträge im Teil `metadaten` tragen `beides` weiter (WLO: aus `ablage`; lokal/Dateinamen über
  `rollen.als_material`, Browser-Werte außer `beides` werden `inhalt`).
- Datenbank: `befund.rolle = beides` bleibt gespeichert; `ablage._lesbar` liest bei `struktur` die
  Menge {struktur, beides}, bei `inhalt` {inhalt, beides} (keine Migration).

**Dateien (Backend `backend/src/boerdi/`):** `ui_module/rollen.py` (neu: `GLIEDERUNG`, `MATERIAL`,
`ist_gliederung`, `ist_material`, `als_material`); `api/ui_ablage.py`, `api/ui_dokumente.py`;
`services/ablage/{mcp_ablage,vorgang_teil}.py`; `services/ablauf/{metadaten,vorbelegung,werkzeuge,
inhalte_aus_dateien}.py`; `services/arbeitsstand_teile.py`; `services/dokumente/{ablage,
metadaten_lokal,strukturdokument_teil}.py`; `ui_module/{strukturentwurf_ordner,upload_antwort,
upload_bereitgestellt,upload_rahmen}.py`; `ui_module/manifeste.json` (aus `npm run module:register`).
**Frontend `frontend/projects/ui-module/src/`:** `_vertrag/modul-host.ts` (`AblageRolle`),
`ui-upload/{upload-erfassen,upload-rollen,upload-baum,upload-ansicht,upload-texte,upload-antwort,
upload-orte,upload-uebertragen,upload-uebertragen-ansicht,ui-upload.element}.ts`, `manifest.json`
(Enums + Beschreibungen), `README.md`.

**Tests (rot → grün):**
- Backend `tests/test_p1_rollen_beides.py` (neu, 26 Tests): rot 17 failed / 10 passed (nur die
  Hilfen grün) → grün 26 passed. Dazu `test_paket_u2_dokumente_api.py`
  (`test_p1_beides_bekommt_kurzangaben…`) und `test_paket_u_ablage_pg.py`
  (`test_p1_beides_steht_in_beiden_lesewegen`, gegen echtes Postgres; nach der Umsetzung
  geschrieben). Alle Dateien zu upload/ablage/rolle/struktur/metadaten/dokument/u4/u6/k5/orte (60) +
  u5_teile, review_u_bereitgestellt, tg3a, r3_review_tg3abc, arbeitsstand: **944 passed, 1 skipped**.
  `ruff check src tests`: sauber.
- Frontend `upload-rollen.spec.ts` (+4) und `ui-upload.element.spec.ts` (+3, +1 Prüfung): rot
  (TS2305/TS2345: `istGliederung`/`beides` fehlen) → grün; `ng test ui-module`: **32 Dateien, 531
  Tests grün**; eslint der geänderten Dateien sauber; `module:register -- --pruefen`: alles aktuell.

**Offen:**
- Budget `ui-upload`: **24 041 B gzip > 24 000 B** (vorher 23 826 B; +215 B für Texte/Legende) —
  `check-module-budget.mjs` meldet FEHLER; Entscheid in P2 (dort ohnehin 24 → 26 kB vorgesehen).
- `teil_verweise`-Auswahl `wo: {rolle: struktur}` vergleicht genau — ein `beides`-Eintrag fiele
  heraus. Kein Werkseed nutzt das; der Studio-Hinweis (`fields-ablaeufe.ts`) zeigt es als Beispiel →
  bei P4/P6 bedenken.
- Die WLO-Vorschau (`upload-uebertragen-ansicht`) nennt `beides` „Strukturdokument“ (so liest es das
  MCP); Wortlaut ggf. in P2.
- Die Lehrplan-Automatik schlägt weiter `struktur` vor (`rolle_vorgabe` kommt mit P2).
- Ohne eigenen Test: `werkzeuge._bereite_dateien`, `vorbelegung` (Fach/Stufe aus Strukturdokumenten),
  `upload_rahmen._markiert_zeile` — dieselbe Hilfe wie die getesteten Stellen.

## P1 Review behoben (Backend) (20.11., nicht committet)

| Befund | Behebung | Test (rot → grün) |
|---|---|---|
| 1 MAJOR — `metadaten.materialien()` nahm auf dem WLO-Weg auch reine Gliederungen (`struktur`) als Material; `als_dokument` und `strukturentwurf_zuordnung.materialien`/`zuordnen` sortierten sie ein | `services/ablauf/metadaten.py` `materialien()`: nur Einträge mit `"rolle" not in i or ist_material(rolle)`; `_kennungen` und der Teil bleiben unverändert (die Vorbelegung braucht die Gliederungen weiter) | `test_p1_rollen_beides.py`: `test_materialien_ohne_reine_gliederung`, `test_als_dokument_nimmt_keine_reine_gliederung`, `test_zuordnen_sortiert_keine_reine_gliederung_ein` (struktur + inhalt + beides → genau 2) **rot 3 failed** → grün; `test_alte_teile_ohne_rolle_zaehlen_weiter_alle` (alter Teil ohne `rolle`: alle 3) schon vorher grün — hält das alte Verhalten fest |
| 2 MINOR — Beispiel `"wo": {"rolle": "struktur"}` vergleicht genau, `beides` fiele heraus | Beispiel in `frontend/projects/studio/.../fields-ablaeufe.ts` (de + en) und im Docstring `services/teil_verweise.py` auf `{"stand": "stored"}`; Kommentar im Seed `06-ablaeufe/themenbaum.yaml` (Schritt `metadaten`) nennt jetzt `beides` und warnt vor dem genauen Rollen-Filter — keine Änderung am Ablauf | Text-/Kommentaränderung; `ng test studio`: **177 Dateien, 2176 Tests grün**. `test_ablauf_datenfluss.py:127` prüft den genauen Vergleich der Auswahl selbst und bleibt |
| 3 MINOR — keine Tests für `beides` in `vorbelegung` und `werkzeuge._bereite_dateien` | keine Code-Änderung nötig (beide fragen schon `ist_gliederung`/`ist_material`) | `test_vorbelegung_liest_fach_und_stufe_aus_einem_dokument_mit_beides`, `test_bereitgestellt_zaehlt_beides_als_datei_und_als_inhalt` (inhalt/beides/struktur/ignorieren → 3 Dateien, 2 Inhaltsdateien): sofort grün; **Mutationsprobe** (Code vorübergehend auf `== "struktur"` bzw. `== "inhalt"` zurückgedreht) → **2 failed**, danach wiederhergestellt (`cmp` gleich) |
| 4 NIT — Docstrings „nur Rolle inhalt“ | `ui_module/strukturentwurf_ordner.py`, `services/ablauf/inhalte_aus_dateien.py`, `services/dokumente/metadaten_lokal.py` nennen „(oder `beides`)“; dazu derselbe Fall in `services/ablauf/vorbelegung.py` (`_aus_strukturdokumenten`: „Rolle `struktur` oder `beides`“) | — |

**Lauf:** `pytest tests/test_p1_rollen_beides.py` + alle Dateien zu
metadaten/zuordn/strukturentwurf/vorbelegung/werkzeuge/teil_verweise/tg5/tg6/k5/aus_inhalten (34
Dateien): **608 passed**. `ruff check src tests`: 2 × E501 nur in P2-Dateien
(`api/ui_ablage.py:11`, `ui_module/upload_orte.py:24`, laufende Arbeit des P2-Agenten), in den
P1-Dateien sauber.

## P2 umgesetzt (20.11., nicht committet, noch ohne Review)

**Was:** Ort, Vorauswahl, Häkchen und Wortlaut nach §1 UO-1/2/5 und §4. Der Anwendungsfall legt die
Vorauswahl fest: im freien Chat das Studio (`upload-config.vorauswahl`, Vorgabe `chat` — auch
angemeldet), in einem Ablauf der Upload-Schritt (`vorauswahl: auto|wlo|chat`, Vorgabe `auto` = die
bisherige Regel). `wlo`/`chat` gelten, wenn der Ort `geht`, sonst `auto`; die Rückfall-Regel je Auswahl
im Modul (`orteFuer`) bleibt global. Schritt-Daten `rolle_vorgabe` (`auto|gliederung|material|beides`)
und `erschliessen` (Vorgabe des Häkchens, ab Werk `true`) wirken nur aus einem Ablauf; die KI setzt
keins davon. `einzeldatei_als_struktur: true` bleibt gültig und heißt `rolle_vorgabe: gliederung` — es
schaltet nichts mehr auf „nur ablegen“ (Name, Erklärzeile, Datenschutz-Satz, Hinweis vor der Anmeldung,
KI-Satz) und steht nicht mehr in den Block-Daten (dort `rolle_vorgabe`). Das Themenbaum-Angebot nach
dem Lesen (`upload_rahmen._themenbaum_angeboten`) fragt `rolle_vorgabe ∈ {gliederung, beides}`.

**Häkchen „Metadaten von WLO erzeugen lassen“:** echtes Kontrollkästchen mit Label unter dem *gewählten*
Ort WLO, nur wenn der Metadaten-Flow da ist (`flowDa`: WLO geht, kein `ohne_erschliessung`); Hinweiszeile
per `aria-describedby` („WLO setzt dabei Titel, Beschreibung, Fach, Stufe und Schlagworte neu – der
Dateiname bleibt nicht der Titel.“, abgewählt „Ohne Häkchen legt WLO die Dateien nur ab.“), der Fokus
bleibt beim Umstellen (`c:erschliessen`), gesperrt solange ein Zug läuft, Ziel ≥ 24 px. Ohne Flow kein
Häkchen, Ort „In WLO ablegen“ + „Metadaten kann WLO gerade nicht erzeugen.“; ohne Anmeldung ist WLO
ausgegraut mit „nicht wählbar – nur mit WLO-Anmeldung“.

**Transport:** `AblageSchritt.vorbereiten.erschliessen` → `ablage-transport` → `POST /api/ui/ablage/
vorbereiten` (`erschliessen: StrictBool = False`; ältere Widgets schicken nichts → aus). Der Server hält
es im Teil `ablage.erschliessen` nur fest, wenn `upload_orte.flow_da()` (Metadaten-Flow startbar) gilt,
und meldet den festgehaltenen Wert in der Antwort (`erschliessen`); `planAus` liest ihn (fehlt er: nein).

**Entscheide unterwegs:**
- **Zwei Klicks, ehrlich beschriftet:** der erste Knopf (WLO) heißt **„Weiter zur Vorschau“** — er prüft
  die Dateien (sha256) und holt die Freigabe, legt aber nichts ab. Der Knopf, der wirklich ablegt (in
  P3 die Zustimmung zum Flow), heißt **„In WLO ablegen und erschließen“**, wenn der Server
  `erschliessen` festhielt, sonst **„In WLO ablegen“** (vorher „Jetzt übertragen“). Chat: **„Hier
  lesen“**. „Weiter zur Vorschau“ ist kein nackter Knopf im Sinn von UO-8. Der Datenschutz-Satz nennt
  beide Schritte („„Weiter zur Vorschau“ zeigt zuerst, was abgelegt wird; erst „In WLO ablegen und
  erschließen“ legt die Dateien … ab“).
- Das Häkchen erscheint nur unter dem gewählten Ort WLO (es gilt nur dort); die Wahl der Person bleibt
  über eine neue Auswahl im selben Block erhalten (wie der gewählte Ort).
- Kein „Anmelden“-Knopf am ausgegrauten WLO: der Element-Host bietet keine Anmelde-Aktion
  (`ElementHost` ohne Login); die Zeile sagt „nur mit WLO-Anmeldung“, der Satz vor der Auswahl bleibt.
- `rolle_vorgabe: gliederung|beides` gibt **jeder** nutzbaren lesbaren Datei die Rolle (höchstens 5, der
  Rest Material) — nicht mehr nur einer einzelnen Datei ohne Ordner; `material` lässt auch einen
  Lehrplan-Namen Material; `auto` = Lehrplan-Regel.
- Im Ablauf ohne `vorauswahl` gilt `auto`, nicht das Studio (das Studio steuert nur den freien Chat).
- Ort „Hier im Chat“ heißt jetzt „Nur hier im Chat lesen“, „Nur Namen senden (nichts hochladen)“ →
  „Nur die Dateinamen senden (der Inhalt bleibt auf deinem Gerät)“, Frage „Wo sollen die Dateien
  verarbeitet werden?“; Studio-Feldtexte und KI-Sätze (`dienst_upload.nicht_gelesen_satz`,
  `dienst_fehler` volltext_endgueltig) nennen die neuen Namen.
- OpenAPI `docs/api/openapi-v1.json` neu erzeugt — enthält auch die P1-Änderung (`beides`), die dort
  noch fehlte (`export_openapi.py --check` meldete vorher Drift).

**Review-Befunde P1, hier mit erledigt:**
- (a) MINOR 4 `upload_rahmen`: die Zählzeile zählt Material aus der `dateiliste` mit `ist_material`
  („{n} Ordner, {m} Dateien als Material, {k} ignoriert.“; ohne Dateiliste `zahlen.inhalte`); die
  markierte Zeile heißt „Gliederung: A.pdf (auch Material), L.pdf“ bzw. „Keine Datei als Gliederung
  markiert.“
- (b) MINOR 5: `upload-uebertragen.spec.ts` — `planAus` behält `beides`, die WLO-Antwort trägt
  `{i, rolle: 'beides'}`.
- (c) NIT 6: Kopf von `upload-chat.ts` nennt `beides`.
- (d) NIT 7: Sammelknöpfe „Alle nicht verwenden“ / „Wieder verwenden“ / „Alle Dateien in X nicht
  verwenden“ (en „Don't use any“ …); die WLO-Vorschau nennt „Gliederung“ bzw. „Gliederung und Material“
  statt „Strukturdokument“.

**Dateien (Backend `backend/`):** `src/boerdi/domain/config_models/upload.py` (`vorauswahl`),
`seeds/01-base/upload-config.yaml` (Kopf), `src/boerdi/ui_module/{rollen,upload_orte,dienst_upload,
upload_rahmen,dienst_fehler}.py`, `src/boerdi/ui_module/manifeste.json` (aus `module:register`),
`src/boerdi/api/ui_ablage.py`, `src/boerdi/services/ablage/vorgang_teil.py`. Der Lader
(`config_loader/upload.py`) gibt das ganze Modell zurück — kein kuratiertes Dict, der Schlüssel kommt
ohne Nacharbeit an (Test).
**Frontend `frontend/`:** `projects/ui-module/src/ui-upload/{manifest.json, upload-orte, upload-orte-ansicht,
upload-ansicht, ui-upload.element, upload-rollen, upload-texte, upload-uebertragen, upload-uebertragen-ablauf,
upload-uebertragen-ansicht, upload-uebertragen-texte, upload-chat, upload-stil}.ts`, `README.md`;
`projects/ui-module/src/_vertrag/modul-host.ts`; `projects/ui/src/stream/ablage-transport.ts`;
`projects/studio/src/app/i18n/catalogue/fields-upload.ts`, `.../views/ui-modul-vorschau-host.ts`,
`.../schema-form/area-schemas.fixture.ts` (neu erzeugt); `scripts/check-module-budget.mjs`;
`docs/api/openapi-v1.json`.

**Tests (rot → grün):**
- Backend `tests/test_p2_ort_vorauswahl.py` (neu, 30 Tests): vor der Umsetzung 22 failed / 5 passed
  (dazu die 3 Tests zu Befund (a): rot) → 30 passed. `tests/test_ui_ablage_api.py` +5 (`erschliessen`
  nur mit Flow, ältere Widgets aus, nur Wahrheitswerte): 5 rot → grün.
  Angepasst, weil sich die Vorgabe änderte: `test_paket_u4_orte` (freier Chat wählt jetzt `chat` vor),
  `test_ui_upload` (Block trägt `rolle_vorgabe` statt `einzeldatei_als_struktur`; KI-Satz mit „Nur hier
  im Chat lesen“/„Hier lesen“; Zählzeile „Dateien als Material“), `test_ablauf_upload_schalter`
  (`rolle_vorgabe: gliederung`), `test_paket_e_volltext_ehrlich` (r8: der Dokument-Weg sagt dasselbe wie
  der Datei-Weg — E3 aufgehoben), `test_tg3de_strukturdokumente` („Gliederung: …“).
  Lauf aller Dateien zu upload/orte/ablage/dokument/u4/u6/config/rahmen/tg3/tg6/tg7/tw4/volltext/
  area_schema/openapi/review_u/p1/p2/bereitgestellt/ocr/arbeitsstand/strukturentwurf (117 Dateien):
  **1869 passed, 1 skipped** (9:09 min). `ruff check src tests`: sauber. `export_area_schemas.py --check` und
  `export_openapi.py --check`: unverändert (nach Neuerzeugung).
- Frontend: Specs zuerst geändert, rot (TS2339/TS2305: `rollenVorgabe`, `flowDa`, `haken`,
  `Plan.erschliessen` fehlten) → grün. `ng test ui-module`: **32 Dateien, 547 Tests grün**;
  `ng test studio`: **177 Dateien, 2177 Tests grün**; `ng test ui` (`ablage-transport.spec.ts`): ohne
  Umsetzung 1 rot → 6 grün; eslint der geänderten Dateien sauber; `module:register -- --pruefen`: alles
  aktuell; `check:docs`: ok. E2E nach `npm run build:widget`: `upload-bereitstellen`,
  `upload-uebertragen` (+1: Häkchen per Leertaste, `erschliessen: false`, Knopf „In WLO ablegen“),
  `upload-erfassen`, `upload-und-fortschritt`: **18 passed**.
- Budget: Test `check-module-budget.test.mjs` zuerst auf 26 kB gestellt (rot) → Ausnahme `ui-upload`
  24 000 → **26 000 B** (begründet im Skript), Summe bleibt 60 000. Gebaut: **ui-upload 24 747 B gzip**,
  alle Module **50 601 B**; `node --test scripts/build-nachlade-module.test.mjs
  scripts/check-module-budget.test.mjs`: 11 pass. Haupt-Bündel: Warnung „202,26 kB > 200 kB“,
  §5.5-Budget eingehalten.

**Offen:**
- **Seed `06-ablaeufe/themenbaum.yaml` (P4):** die Schritttexte nennen noch „Hochladen“/“Upload“, „Hier
  im Chat“ bzw. “Here in the chat” als Knopf/Ort (`dokument_laden`, `ordner_laden`, `dateien_laden`,
  `dokument_chat`) — einen Knopf „Hochladen“ gibt es nicht mehr. Für P2 ausgeschlossen (paralleles
  Paket); `test_paket_u6_themenbaum`/`test_tw4_seeds` pinnen „Hochladen“ im Seed.
- Zwischen P2 und P4 heißt der Ort auf dem Dokument-Weg „In WLO ablegen und erschließen“ mit Häkchen, der
  Seed startet dort aber noch keinen Flow (E3) — erst P4 (UO-6) schließt die Lücke; `ablage.erschliessen`
  steht schon im Teil.
- Schritt-Werte `vorauswahl`/`rolle_vorgabe`/`erschliessen` sind im Manifest beschrieben; die Prüfung
  unbekannter Werte und die Anzeige im Studio kommen mit P6.
- „Anmelden“ am ausgegrauten WLO braucht eine Host-Aktion (`ElementHost`), die es nicht gibt.
- `docs/ui-module.md`/`docs/ablaeufe.md` (Wortlaut, Schritt-Parameter) → P7.

## P3 umgesetzt (20.11., nicht committet, noch ohne Review — zweites Review nötig)

**Was:** Auftragsschritt-Feld `zustimmung` (`freigabe` | `upload`). Mit `upload` startet ein Auftrag mit
`repo_schreibt` nach der MCP-Vorschau **im selben Zug** mit `bestaetigen` (Schlüssel des ersten Teils,
Stapel aus den freigegebenen Argumenten — derselbe Stand wie Box + „Freigeben“), wenn der Server die
Zustimmung nachweist; sonst kommt die Freigabe-Box wie bisher. Log: „Auftrag ohne Box gestartet:
Zustimmung durch Upload (Ablauf …, Schritt …)“ — ohne nodeIds, Schlüssel, Kennung.

**Bedingungen (`services/ablauf/upload_zustimmung.py`, `passt`/`gilt`), alle nötig:**
persönliche Anmeldung (`has_personal_auth`); Teil `ablage` (`wlo.ablage@1`) mit `erschliessen is True`;
`ablage.block_id` = der Upload-Block, den **dieser Lauf** zuletzt beantwortet hat (`lauf.upload_block`,
gesetzt in `treiber.weiter` nur an einem `ui_upload`-Schritt); `ablage.aufrufer` = Marke des Aufrufers
dieses Zugs; `node_ids` nicht leer, jede in den aktuellen `inhalte` mit `stand: stored` und `neu: true`
und nicht in `frueher`; die Teile der Vorschau (`args`, `erst`) sind Teilmengen; die Vorschau meldet
keine Probleme. Ein schon abgelaufener Schlüssel → Box; eine abgelehnte Bestätigung → Satz
(`auftragAbgelehnt`, wenn der Träger keinen hat) und Ersatzweg wie nach „Freigeben“.

**Abweichungen vom Entwurf:**
- `zustimmung` hat die Vorgabe `None` (nicht `"freigabe"`); `freigabe` und `""` werden beim Lesen zu
  `None` — ein Feld mit anderer Vorgabe änderte `treiber.fassung` jedes Ablaufs (wartende Läufe brächen
  beim Deploy ab). Bedeutung unverändert: nicht gesetzt = Freigabe-Box.
- `gilt(ablage, block_id, node_ids)` statt `gilt(entities, aufrufer, node_ids)`: der Treiber hat keine
  `entities`; Anmeldung und Aufrufer liest das Modul aus dem Zug (Kontextvariablen).
- **Bindung an den Aufrufer:** `vorgang_teil.aus_plan` schreibt `aufrufer` = sha256(`ablage:` +
  `aufrufer_kennung()`)[:16] (leer ohne Kennung → nie Zustimmung). Kein Klartext der Kennung im Vorgang.
- **Bindung an den Lauf statt Zeitgrenze:** keine Uhr; ein Direktstart ab dem Auftrag, ein
  Modul-Auslöser (Upload im freien Chat), ein neu gestarteter Lauf oder ein neuerer fremder Upload hat
  keinen bzw. einen anderen Block → Box. Die Antwort eines anderen Moduls bindet nichts.
- **`neu` und `already` (Entscheid Koordinator 20.11., Review P3 Befund 5):** `mit_ergebnis` setzt
  `neu = (stand == stored)`, auch mit `already`. Gemessen im MCP-Code
  (`wlo-mcp-server-sc/src/tools/curation-batch.ts:246`, `services/write/batch-confirm.ts:236`,
  `batch-filing.ts:fileFile`): `already` heißt „derselbe Index unter DEMSELBEN Batch-Schlüssel schon
  eingelöst“ — der Knoten stammt also von diesem Upload (etwa nach einer Zeitüberschreitung mit
  erfolgreichem zweitem Einlösen); einen schon vorhandenen Datensatz meldet der Batch-Weg als `failed`
  („Bereits vorhanden.“, ohne nodeId) und damit nie als `neu`.
- **`werkzeuge.ablauf_schreibt_selbst` bleibt wahr** für jeden Auftrag (der Entwurf sagte „bleibt
  falsch“ — es war nie falsch): so bleibt der frische Vorgang (N14) Pflicht. Geändert ist nur
  `_ehrlich_gefragt` (Maßstab für den Direktstart der KI, `ablauf_schreibt_ungefragt`): ein Auftrag mit
  `zustimmung: upload`, den die Prüfung für passend hält, zählt als gefragt — sicher, weil er ohne Box
  nur nach dem Upload-Klick in genau diesem Lauf startet (sonst Box). Ohne das verlöre „Themenbaum
  erstellen“ nach P4 (keine Rückfrage mehr) den Direktstart.
- **Prüfung** (`pruefung.upload_zustimmung_passt`): `zustimmung: upload` braucht `repo_schreibt`, die
  Liste (`aufteilen.argument`, sonst `node_ids`) als `{$teil: ablage, liste: inhalte, …}` und einen
  `ui_upload`-Schritt, von dem aus der Auftrag erreichbar ist; dann entfällt `auftrag_rueckfrage`, sonst
  Befund `zustimmung_upload` (de/en). Ohne `zustimmung` unverändert.
- Freier Chat (Koordinator 20.11.): ohne Häkchen bleibt `ablage.erschliessen` falsch, und ein Lauf nach
  einem Upload im freien Chat hat keinen Upload-Block → nie Zustimmung (Test).

**Bedrohungsmodell (kurz):**
1. Fremde/alte Inhalte an den Flow schmuggeln (KI, `$teil`-Auswahl `frueher`, ältere Ablage) → nur
   `inhalte` dieses Blocks mit `neu: true`, Prüfung verlangt `liste: inhalte`, sonst Box.
2. Andere Person in derselben Sitzung (Abmelden/Anmelden) → Aufrufer-Marke + `has_personal_auth`.
3. KI startet den Ablauf direkt und überspringt den Upload → kein `upload_block` im Lauf → Box.
4. Person wählt „nur ablegen“ oder entfernt das Häkchen → `erschliessen` falsch → Box (Rückfall).
5. Vorschau des MCP meldet Probleme/abgelaufener Schlüssel → Box; der MCP bleibt die zweite Prüfung
   (Vorschau + Bestätigung mit Schlüssel, Anmeldung der Person).

**Dateien:** Backend `src/boerdi/domain/config_models/ablauf.py` (`zustimmung`),
`services/ablauf/upload_zustimmung.py` (neu), `services/ablauf/treiber.py` (`weiter` merkt
`upload_block`; Auftragszweig; `_freigabe_stapel` aus `weiter_nach_freigabe` herausgezogen),
`services/ablauf/pruefung.py` (+ `_erreichbar`, `upload_zustimmung_passt`), `pruefung_texte.py`
(`zustimmung_upload`), `services/ablauf/werkzeuge.py` (`_ehrlich_gefragt`),
`services/ablage/vorgang_teil.py` (`aufrufer_marke`, `aufrufer`, `neu`). Studio
`frontend/projects/studio/src/app/i18n/catalogue/fields-ablaeufe.ts` (de/en, Label, Hinweis, Wahl),
`.../schema-form/area-schemas.fixture.ts` und `docs/api/openapi-v1.json` neu erzeugt (Diff: nur
`zustimmung`). Kein Seed geändert (P4), keine P2-Frontend-Datei, `api/ui_ablage.py` unverändert.

**Tests (rot → grün):**
- `tests/test_p3_upload_zustimmung.py` (neu, 43 Tests vor der Umsetzung): **rot 33 failed / 10 passed**
  (die 10 grünen: Rückfall auf die Box — heute schon so) → **43 passed**. Danach ergänzt (Koordinator):
  `test_freier_chat_ergibt_nie_eine_zustimmung` (grün). Abgedeckt: Zustimmung gilt (frische Knoten,
  Bestätigung mit Schlüssel des ersten Teils, Stapel, Status wie nach „Freigeben“, Vergleich mit
  `weiter_nach_freigabe`), Audit-Zeile ohne Kennungen; `gilt` falsch für abgemeldet, ohne/fehlendes
  Häkchen, anderer/kein Block, anderer Aufrufer, ohne Marke, `frueher`, `already`, fremder Knoten, leer,
  keine Liste, ohne/falsche Ablage, nicht abgelegt; im Treiber Box bei Vorgabe, Häkchen aus, `already`,
  anderem Aufrufer, abgemeldet, anderem Block, Problemen, Direktstart ohne Upload, anderem Modul,
  abgelaufenem Schlüssel; Ersatzweg mit Satz bei abgelehnter Bestätigung; Prüfung (ersetzt die
  Rückfrage; Befund ohne Upload-Schritt, mit festen Knoten, aus `frueher`, aus anderem Teil, ohne
  `repo_schreibt`); Direktstart-Maßstab; Modellwerte und Fassung.
- `tests/test_ui_ablage_api.py` +2 (Koordinator, nach der Umsetzung geschrieben, grün):
  `erschliessen` und `neu` über `/datei` + `/abschluss`; zweites `vorbereiten(erschliessen=False)` bei
  offenem Stapel → 409 `stapel_offen`, Teil behält `True`.

## P2 Review behoben (20.11., nicht committet)

**Entscheid des Nutzers (Befund 1):** das Häkchen „Metadaten von WLO erzeugen lassen“ erscheint **nur**, wenn
der Ablauf-Schritt `erschliessen` ausdrücklich setzt (`true` oder `false`) — damit erklärt der Ablauf, dass ein
späterer Schritt die Wahl nutzt (Auftragsschritt `zustimmung: upload`, P3). Ohne die Angabe (freier Chat, Schritt
ohne sie): kein Häkchen, der Ort heißt „In WLO ablegen“, `vorbereiten` schickt `erschliessen: false`, Erklärzeile
und Datenschutz-Satz sagen „nur ablegen“. Die Vorgabe ist nicht mehr still `true`, wenn sie fehlt.

| Befund | Behebung | Test (rot → grün) |
|---|---|---|
| 1 MAJOR — Häkchen im freien Chat sichtbar und an, obwohl dort niemand `ablage.erschliessen` nutzt | Backend `ui_module/dienst_upload.py`: `_chat_vorgaben` ohne `erschliessen`; `_schritt_vorgaben` nur bei bool-Wert; Block-Daten tragen `erschliessen` nur dann. `_ablage_satz(schalter, haken)`: ohne Häkchen „(nur ablegen) … Metadaten erzeugt WLO dabei nicht — versprich keine“, mit Häkchen „wenn sie das Häkchen … setzt, Metadaten“. `ui_module/upload_rahmen.py` `_ablage_zeilen`: aus `ablage.erschliessen` der Antwort (der Wert, den der Server festhielt) „Die Person hat … gewählt … sag nicht, sie seien schon da“ bzw. „Nur abgelegt: … biete sie nicht an und behaupte keine“; ältere Widgets ohne den Wert: keine Zeile. Manifest: `antwort.ablage.erschliessen` (bool, optional); Beschreibungen von `dienst.parameter.erschliessen` und `eingabe.erschliessen` („ohne Angabe kein Häkchen, nur ablegen“); `README.md`. Frontend `upload-orte.ts` `hakenVorgesehen(daten)` (bool vorhanden), `erschliessenVorgabe` nur `=== true`; `upload-orte-ansicht.ts` `ortName(…, vorgesehen)`, `mitHaken` (vorgesehen ∧ Flow), Erklärzeile ohne Vorsehen `erklaerWlo(false)`; `upload-ansicht.ts` `erschliessenFuer` verlangt `hakenVorgesehen`, `ablageNachAnmeldung(erschliessen)` (de/en); `upload-uebertragen.ts` Antwort `ablage.erschliessen = plan.erschliessen` | Backend `tests/test_p2_review_befunde.py` (neu, 14 Tests): **rot 12 failed / 2 passed** → grün. Angepasst (Vorgabe geändert): `test_p2_ort_vorauswahl` (KI-Test, alter Schlüssel mit `erschliessen: true`, `test_erschliessen_nur_wenn_der_schritt_es_setzt`), `test_paket_k_traeger` (`_ablage_satz(schalter, True)`). Frontend: `upload-orte.spec.ts` (+2), `upload-uebertragen.spec.ts`, `ui-upload.element.spec.ts` (+1 „ohne `erschliessen` kein Häkchen“ de/en; Checkbox-Tests auf `MIT_HAKEN`), `ui-upload-uebertragen.element.spec.ts` (+3: freier Chat sendet `false`, Antwort trägt `ablage.erschliessen`) — rot (TS2305 `hakenVorgesehen`, TS2339 `grund_erschliessung`/`ablage.erschliessen`) → grün; `FE-3/U4` erwartet im freien Chat jetzt „erst „In WLO ablegen““. E2E `upload-uebertragen` (+1: Block ohne `erschliessen` → kein Häkchen, `erschliessen: false`; die übrigen mit `erschliessen: true` im Block) |
| 2 MINOR — in der Vorschau folgte der Datenschutz-Satz dem Häkchen des Browsers, der Knopf dem Server | `upload-ansicht.ts` `befund`: steht ein Lauf mit `plan`, gilt `plan.erschliessen`, sonst `erschliessenFuer`; `datenschutzSatz` nimmt den wirksamen Wert (prüft den Flow nicht mehr selbst) | `ui-upload-uebertragen.element.spec.ts` „in der Vorschau folgt der Datenschutz-Satz dem Wert des Servers“ (Häkchen an, Server `false` → „erst „In WLO ablegen““). **Mutationsprobe:** Zeile auf `erschliessenFuer(s, orte)` zurückgedreht → **1 failed / 38 passed**, wiederhergestellt (`cmp` gleich) |
| 3 MINOR — ohne Flow kein Grund; ohne Anmeldung kein Weg zur Anmeldung | `ui_module/upload_orte.py` `_ohne_flow_grund()` aus `auftrag_zug.traeger(repo_schreibt=True)`: Träger MCP → `flow_nicht_freigegeben`, sonst (`ohne_mcp`, `mcp_kurz_weg`) `dienst_nicht_erreichbar`; `_wlo` schickt `grund_erschliessung` neben `hinweis: ohne_erschliessung`. Manifest `eingabe.orte.wlo.grund_erschliessung` (enum, unter dem `x-nur-system`-Objekt `orte`), `npm run module:register`. Frontend `OrtStand.grund_erschliessung` (unbekannte Codes fallen weg), `erklaerWloOhne(grund)` + `ohneFlow` de/en („in diesem Chat nicht freigegeben“ / „der Dienst dafür ist gerade nicht erreichbar“). `gesperrt.nur_angemeldet` → „melde dich über den Konto-Knopf unten an“ / “sign in with the account button below” (gilt für beide Orte; keine neue Host-API) | `test_p2_review_befunde.py` (Grund je Träger, Grund im Block passt zum Schema). Fixture `lage` (`test_paket_u4_orte`) setzt `_ohne_flow_grund`; zwei Gleichheits-Prüfungen um den Grund ergänzt. Frontend `upload-orte.spec.ts`, `upload-texte.spec.ts`, `ui-upload.element.spec.ts` (de/en, ohne Code ohne Klammer); E2E `upload-bereitstellen` (neuer Satz, Ort „In WLO ablegen“) |
| 4 MINOR — „bitte einige ignorieren“ | `upload-texte.ts` `zuVieleStapel`: „bitte einige auf „Nicht verwenden“ stellen“ / “please set some to “Don't use”” | `upload-texte.spec.ts` (de/en) rot → grün |
| 5 NIT — Titel „Metadaten zu {n} Inhalten“ zählte reine Gliederungen | Entscheid: Material zählen (wie `materialien()`), Wortlaut bleibt; `services/ablauf/metadaten.py` `_teil` nutzt `materialien()` | `test_der_titel_der_metadaten_zaehlt_nur_material` (struktur/inhalt/beides → 2) rot → grün; `test_tb_f2_metadaten_lesen` bleibt grün |
| 6 NIT — Kurzbeschreibung `structure` „{n} Inhalte“ ohne `beides` | `_material_zahl` aus `upload_rahmen` als `upload_antwort.material_zahl` (verschoben, nicht dupliziert); `upload_rahmen` und `services/arbeitsstand_teile.py` nutzen sie | `test_die_kurzbeschreibung_der_struktur_zaehlt_material` („1 Ordner, 3 Inhalte“ statt 2) rot → grün; `test_arbeitsstand`, `test_tg3a_struktur_auswahl` grün |

**Läufe:** Backend `test_p1_rollen_beides`, `test_p2_ort_vorauswahl`, `test_p2_review_befunde`, `test_paket_u4_orte`,
`test_ui_upload`, alle Dateien zu upload/orte/rahmen/metadaten/arbeitsstand_teile/u5/u6 (15) + `test_paket_k_traeger`,
`test_arbeitsstand`, `test_tg3a_struktur_auswahl`, `test_tb_f2_metadaten_lesen`, `test_review_u_bereitgestellt`:
**432 passed**; alle Dateien, die `ablauf_beispiele`, `arbeitsstand_teile`, `_ablage_satz`, `material_zahl`,
`upload_rahmen`, `wlo_erschliessen` oder `ohne_erschliessung` nennen (25): **571 passed**. `ruff check src tests`:
sauber. Frontend `ng test ui-module`: **32 Dateien, 552 Tests grün**; eslint der geänderten Dateien (auch E2E)
sauber; `module:register -- --pruefen`: alles aktuell; `build:widget` + `check-module-budget.mjs`: **ui-upload
25 082 B gzip** (Grenze 26 000), alle Module 50 936 B (Grenze 60 000); Playwright `upload-bereitstellen` +
`upload-uebertragen`: **13 passed**. Der Build meldet weiter die Warnung zum Anfangs-Bündel (696 kB > 660 kB) —
nicht aus diesem Paket (nur das nachgeladene `ui-upload` geändert).

**Offen / Hinweise:**
- `api/ui_ablage.py` (P3-Datei, hier nicht angefasst) hält `erschliessen: true` einer Anfrage fest, sobald der
  Flow startbar ist — auch aus einem Feld ohne `erschliessen` (gefälschte Anfrage im freien Chat). Folgenlos, weil
  die Zustimmung (P3) einen Ablauf mit `zustimmung: upload` verlangt; strenger wäre, die Block-Daten des offenen
  Felds zu prüfen (Entscheid bei P3).
- Der Rahmen nimmt `ablage.erschliessen` aus der Antwort des Browsers (der Wert, den der Server ihm meldete) — er
  steuert nur den Satz an die KI, keine Wirkung.
- Seed `06-ablaeufe/themenbaum.yaml` (P4): die Upload-Schritte setzen `erschliessen` noch nicht — bis P4 zeigt auch
  der Themenbaum kein Häkchen und legt nur ab (gewollt: P4 setzt `erschliessen: true` mit dem Verbraucher).
- `docs/ui-module.md` (Wortlaut, `grund_erschliessung`, Häkchen nur mit Schritt-Angabe) → P7.

## P3 Review behoben (20.11., nicht committet — zweites Review steht aus)

| Befund | Behebung | Test (rot → grün) |
|---|---|---|
| 1 MAJOR `zustimmung: upload` nicht auf den Metadaten-Flow begrenzt | `upload_zustimmung.passt`: `s.flow != METADATEN_FLOW` → Box (Log `anderer_flow`); `pruefung.upload_zustimmung_passt` verlangt `flow == METADATEN_FLOW`, sonst Befund `zustimmung_upload`; Text de/en („nur für den Metadaten-Flow (node-metadata-write)“) und Studio-Hinweis `fields-ablaeufe.ts` de/en angepasst | `test_befund1_nur_der_metadaten_flow_startet_ohne_box`, `test_befund1_pruefung_meldet_einen_anderen_flow` (rot → grün) |
| 2 MINOR `upload_block` bleibt nach dem Start ohne Box | `treiber._rechne_schritte`: nach erfolgreichem Start ohne Box `lauf.pop(upload_zustimmung.BLOCK)` vor `_gestartet`; der vorübergehende Fehler (zurück an die Frage) behält ihn | `test_befund2_der_upload_block_gilt_nur_einmal` (rot → grün); `test_befund4_voruebergehend_wie_nach_der_box[True]` prüft, dass er bleibt |
| 3 MINOR `upload_block` unabhängig von der Antwort gebunden | neu `upload_zustimmung.bindet(antwort)`: nur `bereitgestellt` + `ort: wlo` oder die ältere Form `uebertragen`, mit `ablage.abgebrochen == 0`; `treiber.weiter` bindet nur dann, sonst wird eine frühere Bindung gelöst (fail closed) | `test_befund3_nur_eine_fertige_wlo_ablage_bindet_den_lauf[angehalten/chat/namen/leer]`, `test_befund3_eine_alte_bindung_faellt_mit_einer_anderen_antwort` (rot → grün); `test_befund3_alte_antwort_uebertragen_bindet` (grün); `_nach_upload` schickt jetzt die Antwort des Moduls (`WLO_ANTWORT`) |
| 4 MINOR Vorschau-Zweig von `passt` ungetestet | Testattrappe `_Starter(zusatz=…, vorlaeufig=…)` | `test_befund4_fremder_knoten_in_der_vorschau_gibt_die_box[args/erst]`, `test_befund4_voruebergehend_wie_nach_der_box[mit/ohne Frage]` — Abdeckungslücke, schon vor der Behebung grün (Verhalten war richtig) |
| 5 MINOR `already` nicht als `neu` | Entscheid Koordinator: `vorgang_teil.mit_ergebnis` setzt `neu = stand == "stored"` (auch `already`); Abweichung 5 oben ersetzt | `test_neu_nur_fuer_frisch_abgelegte_eintraege`, `test_datei_endpunkt_haelt_neu_fest`, `test_gilt_fuer_frische_knoten_dieses_uploads`, `test_ui_ablage_api::test_p3_erschliessen_und_neu_bleiben_ueber_datei_und_abschluss` (`[True, True]`) (rot → grün); Fälle `schon_da` aus `test_gilt_nicht`/`test_sonst_die_freigabe_box` entfernt (gelten jetzt) |
| 6 MINOR ein Nicht-Modul-Schritt kann `ablage` schreiben | `typen.NUR_VOM_SERVER = {"ablage"}`; Prüfung `ablage_reserviert` (de/en) für `schreibt` (außer am Modul), `agent.ausgabe` und `freitext.schreibt`. Nur `ablage`, nicht alle `MODUL_TEILE`: `draft` schreiben Werkzeug- und KI-Schritte in `seeds/06-ablaeufe/{themenbaum,sammlung_pruefen}.yaml` und `tests/ablauf_beispiele/*.yaml` (gemessen; kein Seed schreibt `ablage`). Dazu liest der Auftrag den **gespeicherten** Teil (`umgebung.teile` statt `_Teile`, das die in diesem Zug geschriebenen Teile vorzieht) — einfach und sicher, denn `ablage` schreibt nur `/api/ui/ablage/*` | `test_befund6_pruefung_ablage_schreibt_nur_der_server[werkzeug/agent/freitext]`, `test_befund6_eine_im_zug_geschriebene_ablage_zaehlt_nicht` (rot → grün); `test_befund6_der_upload_schritt_darf_ablage_hinterlassen` |
| 7 NIT Log ohne Bezug zum Lauf | Log-Zeile trägt `Lauf %s` = `lauf["start"]` (zufällige Marke je Lauf, `secrets.token_hex(4)` in `treiber.starten` — keine Kennung einer Person oder eines Knotens) | `test_audit_zeile_ohne_kennungen` bleibt grün |
| 8 NIT Docstring | `test_freier_chat_ergibt_nie_eine_zustimmung`: „… ohne Upload-Block im Lauf → Box, auch wenn `erschliessen` wahr ist“ | — |
| Koordinator: Häkchen nur, wenn der Block es zeigt | `upload_antwort.merken` merkt `haekchen` (der Schritt setzt `erschliessen` ausdrücklich); `/api/ui/ablage/vorbereiten` hält `erschliessen` nur mit `haekchen` in der offenen Frage fest. Ältere offene Fragen ohne `haekchen` → aus (Box) | `test_ui_ablage_api::test_p3_review_ohne_haekchen_im_block_haelt_der_teil_kein_erschliessen`, `test_koordinator_offene_frage_merkt_ob_der_block_ein_haekchen_zeigt` (rot → grün); P2/P3-API-Tests setzen `haekchen` über `_mit_haekchen` |

**Läufe:** rot 19 failed / 88 passed (`test_p3_upload_zustimmung.py`, `test_ui_ablage_api.py`) → grün
107 passed. Verwandte Tests (auftrag, freigabe, direkt, pruefung, paket_s, n4, werkzeug_freigabe, tg6, tw4,
seed, ablauf_beispiele, `test_review_u_bereitgestellt`) 771 passed; Ablage/Upload/Treiber/Simulation/P4
485 passed; Studio `ng test studio` 2177 passed; ruff sauber; `export_area_schemas.py --check` und
`export_openapi.py --check` unverändert.

**Dateien:** `services/ablauf/upload_zustimmung.py`, `services/ablauf/treiber.py`,
`services/ablauf/pruefung.py`, `services/ablauf/pruefung_texte.py`, `services/ablauf/typen.py`,
`services/ablage/vorgang_teil.py`, `api/ui_ablage.py`, `ui_module/upload_antwort.py`; Studio
`fields-ablaeufe.ts`; Tests `tests/test_p3_upload_zustimmung.py`, `tests/test_ui_ablage_api.py`.

## P4 umgesetzt (20.11., nicht committet, noch ohne Review)

**Was:** Seed `backend/seeds/06-ablaeufe/themenbaum.yaml` nach UO-3/UO-6 — keine Rückfrage mehr, das Häkchen
entscheidet, der Dokument-Weg bekommt den Flow. 40 Schritte bleiben (`metadaten_frage` raus, `erschliessen_weg`
rein), 20 Selbsttests bleiben (Obergrenze).

**Wege vorher → nachher:**

| Schritt | vorher | nachher |
|---|---|---|
| `ordner_geladen`, `dateien_weg` | Ablage dieses Blocks (`ablage.block_id` = `{teil.struktur.block_id}`) → `metadaten_frage` („Ja“ → `metadaten`, „Nein“ → `lesen`) | dieselbe Regel → `erschliessen_weg` |
| `erschliessen_weg` (neu) | — | `ablage.erschliessen` `gleich` `"ja"` (Wahrheitswert, `vergleich._gleich`) → `metadaten`; sonst → `lesen` |
| `dokument_gelesen` | `strukturdokument` → `wofuer`; `document` → `wofuer`; sonst `ohne_daten` | **neu zuerst:** Ablage dieses Blocks → `erschliessen_weg`; danach unverändert (hier im Chat gelesen → `wofuer`) |
| `nach_lesen` | Dateien → `angaben_da`; Unterordner → `aus_ordnern`; sonst `angaben_da` (ohne Angaben → `aus_dateien`) | **neu zuerst:** Grundlage „Ein Dokument mit Gliederung, etwa ein Lehrplan“ → `wofuer` (auch nach „Ohne Angaben aus WLO weiter“ — nie die Dateinamen); `zum_entwurf` wählt dann `entwurf_dokument` |
| `metadaten` | Freigabe-Box nach der Rückfrage | `zustimmung: upload` (P3); Text „WLO erschließt deine Dateien – das dauert ein paar Minuten. Du kannst warten oder später unter „Meine Vorgänge“ weitermachen.“ (en “… under “My tasks”.”) |

Geprüft: `metadaten_lesen` schreibt `block_id` aus der Ablage (`metadaten._teil`) und nimmt reine Gliederungen in
den Teil (`_kennungen`; nur `materialien()` filtert) — `angaben_da` griffe also auch; die Regel in `nach_lesen`
deckt zusätzlich den Fall ohne gelesene Angaben. `pruefung.upload_zustimmung_passt` ist für `metadaten` wahr
(Flow = `METADATEN_FLOW`, P3-Review Befund 1); `werkzeuge.ablauf_schreibt_ungefragt` bleibt falsch (Direktstart
bleibt). Die Upload-Schritte setzen `erschliessen` ausdrücklich — damit zeigt der Block das Häkchen und
`/vorbereiten` hält `erschliessen` fest (P2-Entscheid, P3-Review „haekchen“).

**Schritt-Daten:** `dokument_laden` `{zweck: bereitstellen, rolle_vorgabe: gliederung, vorauswahl: auto,
erschliessen: true}`; `dokument_chat` `{…, rolle_vorgabe: gliederung, vorauswahl: auto, orte: [chat]}` (kein
Häkchen); `ordner_laden`/`dateien_laden` `{…, rolle_vorgabe: material, vorauswahl: auto, erschliessen: true}`.
`einzeldatei_als_struktur` kommt im Werkseed nicht mehr vor. **Texte:** die vier Upload-Schritte nennen die Orte
„In WLO ablegen und erschließen“ / „Nur hier im Chat lesen“ (en “Store and index in WLO” / “Only read here in the
chat”) und was dort geschieht; `dateien_laden` den Nebenknopf „Nur die Dateinamen senden“; `dokument_chat` den
Knopf „Hier lesen“ (“Read here”). Kein „Hochladen“/„Hier im Chat“/„Nur Namen senden“ mehr. Seed-Kopf (E3-Satz,
Rückfrage, Direktstart) neu; im Plan `2026-11-20-konto-vorgaenge-und-warten-auf-volltext.md` §8 E3 als aufgehoben
vermerkt.

**Selbsttests im Seed:** angepasst „Ordner in WLO abgelegt und erschlossen“, „Dateien in WLO ablegen und
erschließen“, „Kestra scheitert, weiter mit den Dateinamen“ (Ablage mit `erschliessen: true`, `neu: true`; Weg über
`erschliessen_weg`, keine Eingabe an der Rückfrage). Neu: „Lehrplan in WLO ablegen und erschließen“ (→ `metadaten`
→ `lesen` → `nach_lesen` → `wofuer` … `entwurf_dokument` → `ende`) und „Lehrplan in WLO nur ablegen“ (→ `lesen` …
`entwurf_dokument`). Der Chat-Weg bleibt durch „Dokument hier im Chat lesen, mit Inhalt“ abgedeckt (→ `wofuer`).
Platz (höchstens 20): „Kein Entwurf, nochmal versuchen“ ist in „Andere Grundlage nach einem leeren Upload, kein
Entwurf, nochmal“ aufgegangen; „In WLO gewählt, nichts abgelegt“ ist nach
`tests/test_paket_u6_themenbaum.py::test_in_wlo_gewaehlt_nichts_abgelegt_fuehrt_zu_den_dateinamen` gewandert.

**Tests (rot → grün):**
- `tests/test_p4_themenbaum_erschliessen.py` (neu, 14 Tests; Attrappen `_Starter`/`_Wahl`/`_ablage`/`person`
  aus `test_p3_upload_zustimmung`): vor der Seed-Änderung **12 failed / 2 passed** (schon grün: Chat-Weg →
  `wofuer`, Prüfung leer) → **14 passed**. Abgedeckt: Seed-Gestalt (keine Rückfrage, `erschliessen_weg`,
  `zustimmung`, Regeln der drei Verzweigungen, Schritt-Daten, Texte, Warte-Text); Treiber: Dokument in WLO mit
  Häkchen → Flow ohne Box (vorlegen + bestätigen); ohne Häkchen → kein Auftrag, `lesen`, `wofuer`; ohne Angaben aus
  WLO → `wofuer` (nicht `aus_dateien`); Dokument hier im Chat → `wofuer` ohne Flow; Dateien in WLO mit Häkchen →
  keine Rückfrage, keine Box; ein Eintrag ohne `neu: true` → Box; alle Selbsttests bestehen.
- Angepasst, weil sich die Vorgabe änderte: `test_paket_u6_themenbaum` (Rückfrage → `erschliessen_weg`; Texte
  nennen die Orte statt „Hochladen“; „In WLO gewählt, nichts abgelegt“ hierher), `test_tg6_review` (MAJOR 1: statt
  der Rückfrage `zustimmung: upload`, Direktstart bleibt; MINOR 8: Regelfolge `wofuer`, `erschliessen_weg`,
  `aus_dateien`), `test_tg6_review2` (A: dieselbe Knopf-Regel jetzt an `ohne_metadaten`; H: `erschliessen_weg`),
  `test_tg6_nachpruefung` (M1 an `ohne_metadaten`), `test_tg6_themenbaum` (`ohne_metadaten` statt Rückfrage;
  Kopf), `test_paket_k5_strukturdokumente` (die Zustimmung ist der Klick — der Lehrplan-Schritt sagt, dass WLO die
  Gliederung beschreibt), `test_paket_k_review` (B9 aufgehoben: keine Rückfrage, `zustimmung: upload`),
  `test_tw4_seeds` (Dokument-Weg nennt den Ort, kein „Hochladen“), `test_paket_e_volltext_ehrlich` (R1: Daten von
  `dokument_chat`). Unverändert: `test_arbeitsstand.py:407` (ein ausgedachter Lauf eines Testbeispiels mit Schritt
  `metadaten_frage` — prüft nur die Kennzeile, nicht den Seed), `test_p2_*` (nicht betroffen).
- Läufe (`backend/`): alle 41 Dateien zu themenbaum/tg*/tw4/u6/k5/seed/ablauf_beispiele/paket_e/simulation/
  durchtest/p2_/p3_/p4_ + `test_paket_k_review`, `test_arbeitsstand`, `test_ablauf_upload_schalter`,
  `test_ablauf_pruefung`, `test_ablauf_leiste`, `test_r1_auftrag_teile`, `test_ablauf_zug`: **1101 passed**; vor
  den Test-Anpassungen derselbe Satz (ohne die letzten fünf): 14 failed / 960 passed — alle in den oben angepassten Dateien (`test_paket_u6_themenbaum` war da schon
  angepasst).
  Weitere Seed-Leser (`test_cli_werksabgleich`, `test_config_models`, `test_fuehrung_wie_tour`,
  `test_ablauf_datenfluss`, `test_ablauf_altbestand`, `test_ablauf_dokumente`, `test_ablauf_feste_argumente`,
  `test_ablauf_frageschritte_freitext`, `test_ablauf_ki_daten`, `test_ablauf_seite`, `test_paket_k_durchtest`,
  `test_tg5_vorbelegung`, `test_ui_upload`): **439 passed**. `pruefe()` aller Werkseeds: `fuehrung` (38 Schritte)
  `[]`, `sammlung_pruefen` (11) `[]`, `themenbaum` (40) `[]`. `ruff check src tests`: sauber.

**Abweichungen / Hinweise:**
- Die zwei Lehrplan-Selbsttests tragen in der Ablage die Rolle `inhalt`, nicht `struktur`: die Simulation legt die
  Ablage schon beim Start in den Vorgang, und eine Gliederung böte `bereit` dann als Dokument an (`einstieg_mit`).
  Der Weg hängt nicht an der Rolle; der Treiber-Test nutzt die Ablage aus `vorgang_teil`.
- `already` zählt inzwischen als `neu` (P3-Review Befund 5) — der Box-Test setzt darum einen Eintrag ausdrücklich
  auf `neu: false` (ein Knoten, den dieser Upload nicht neu anlegte).
- **Offen (Entscheid nötig, nicht umgesetzt):** ohne Rückfrage findet `treiber._rueckfrage(metadaten)` keine Frage
  mehr — ist der MCP-Träger nur *vorübergehend* weg, geht der Lauf zu `ohne_metadaten` („Angaben aus WLO lesen“ /
  „Ohne Angaben aus WLO weiter“ / „Frei weiter“) statt zurück zur Rückfrage; einen Knopf „Erschließen nochmal
  versuchen“ gibt es dort nicht. Ein solcher Knopf (Ziel `metadaten`) startete ohne Box, solange die
  Upload-Zustimmung im Lauf gilt (P3-Review Befund 2 löst sie erst nach einem Start) — sicherheitsrelevant, daher
  nicht ohne Entscheid. → **entschieden und umgesetzt im P4-Nachtrag (unten).**
- Doku (`docs/ablaeufe.md`, `docs/ui-module.md`) → P7.

## P4-Nachtrag, P5, P6 umgesetzt (20.11., nicht committet, noch ohne Review)

### P4-Nachtrag — „Erschließung nochmal versuchen“ (Entscheid Nutzer 20.11.)

**Was:** `ohne_metadaten` (Seed `06-ablaeufe/themenbaum.yaml`) bekommt als erste Option `erschliessen`
„Erschließung nochmal versuchen (dieselben Dateien)“ / “Try indexing again (same files)” → `metadaten`. 40
Schritte und 20 Selbsttests bleiben (kein neuer Schritt, kein neuer Selbsttest).

**Wege geprüft:** `ohne_metadaten` erreicht der Lauf (1) über `bei_fehler` von `metadaten` (Häkchen an), (2) über
`bei_fehler` von `lesen` nach einem gelungenen Flow, (3) über `bei_fehler` von `lesen` **ohne** Häkchen
(`erschliessen_weg` → `lesen`), (4) nach „Abbrechen“ an der Freigabe-Box. Optionen kennen keine Bedingung
(`Schnellantwort` ohne `wenn`), ein eigener Schritt ginge über 40. Entscheid: der Knopf steht immer da, über die
Zustimmung entscheidet der Server (`upload_zustimmung.passt`) — fail closed:
- (1) nach einem **vorübergehenden** Ausfall bleibt der Upload-Block gebunden → der zweite Versuch startet ohne Box;
- (1) nach einem **endgültigen** Fehlschlag, (2) nach dem Start (Block verbraucht, P3-Review Befund 2), (3) ohne
  Häkchen (`ablage.erschliessen` falsch) und (4) nach der Box (zweites Review P3, MINOR 1) → Freigabe-Box: die Person
  stimmt dort ausdrücklich zu oder bricht ab — kein Flow, den sie nicht gewählt hat, startet von selbst.
- Nebenwirkung: als Ziel einer Wahl ist `ohne_metadaten` jetzt die Frage, an die `treiber._rueckfrage` einen
  vorübergehenden Ausfall zurückführt (vorher kam er über `bei_fehler` an denselben Schritt).

**Tests (rot → grün):** `tests/test_p4_themenbaum_erschliessen.py` +7: Option (Label, Ziel, ohne Synonym);
vorübergehender Ausfall → `ohne_metadaten`, Block gebunden → „nochmal“ startet ohne Box (vorlegen + bestätigen),
danach ist der Block verbraucht; endgültiger Fehlschlag → Box; nach gelungenem Start → Box; ohne Häkchen → Box;
Box → „Abbrechen“ → „nochmal“ → Box. Vor der Seed-Änderung **5 failed / 14 passed** (`weiter_wahl` → `None`, die
Option fehlte) → grün. `pruefe()` aller Werkseeds: `fuehrung` (38) `[]`, `sammlung_pruefen` (11) `[]`,
`themenbaum` (40, 20 Selbsttests, alle grün) `[]`; `werkzeuge.ablauf_schreibt_ungefragt` bleibt falsch (Direktstart
bleibt), kein `auftrag_rueckfrage`/`zustimmung_upload`.

### P5 — Prüfung `knopf_nichtssagend` (UO-8)

**Was:** `services/ablauf/pruefung.py` im Block der Auftragsschritte (neben `auftrag_synonym`): für jeden Schritt,
der ins Repositorium schreibt (`_schreibt_ins_repo`: Auftrag mit `repo_schreibt` oder einem Flow aus
`SCHREIBENDE_FLOWS`, Werkzeug mit `werkzeuge.schreibend`), prüft `_nichtssagende_knoepfe` jede Option mit diesem
Ziel und die `text_antworten` derselben Frage (sie stehen neben den schreibenden Knöpfen). Liegt eine Beschriftung in
**irgendeiner** Sprache nach `_kern` (ohne Satzzeichen und Leerzeichen, `casefold`) in `NICHTSSAGEND` = {ok, okay,
weiter, ja, nein, los, start, go, yes, no, next, continue, fortfahren} → Befund am Schritt mit dem Knopf. Text de/en
in `pruefung_texte.py` (Schritt, Beschriftung, Option, Ziel, Beispiel „In WLO ablegen und erschließen“). „Ja,
Metadaten erzeugen“ oder „Jahr“ bleiben frei.

**Werkseeds und Beispiele:** alle bestehen ohne Änderung — vor schreibenden Schritten stehen nur „Erschließung
nochmal versuchen (dieselben Dateien)“ (`themenbaum`) und „Ja, Metadaten erzeugen“ (Beispiel
`themenbaum_aus_inhalten`); kein Label geändert.

**Tests (rot → grün):** `tests/test_p5_knopf_nichtssagend.py` (neu, 29 Tests: 14 nichtssagende Formen, auch nur auf
Englisch; schreibendes Werkzeug; drei gute Beschriftungen; lesendes Ziel; Text-Chips mit/ohne schreibendes Ziel;
de/en; je Werkseed und Testbeispiel): vorher **29 failed** (`KeyError: 'knopf_nichtssagend'`) → **29 passed**.

### P6 — Modul-Parameter im Studio, Werte in der Prüfung

**Quelle:** kein neuer Endpunkt — `GET /api/config/ui-module` (Studio-Schlüssel, `api/config_ui_module.py`) liefert
schon die ganzen Manifeste samt `dienst.parameter`; OpenAPI unverändert (ein Test hält das fest).

**Studio:** `core/ui-module-api.service.ts` hält die Manifeste einmal je Sitzung (`manifeste`, `manifesteLaden`;
ein Fehlschlag bleibt still wie bei `ChoicesApi.prime` — die Hilfe fehlt dann, das Formular bleibt bedienbar).
`schema-form/modul-parameter.ts` (rein): `modulAmPfad` (nur `schritte[i].daten` eines Schritts `typ: modul`) und
`parameterAus` (Name, Beschreibung, erlaubte Werte — auch je Eintrag einer Liste —, Typ, Vorgabe aus `default`,
Pflicht aus `required`). `schema-form/modul-parameter.component.ts` (`studio-modul-parameter`) zeigt sie unter der
Tabelle bzw. der JSON-Box in `teil-werte.component.ts`: eine `<ul>`, benannt per `aria-labelledby` durch die
Kopfzeile „Parameter des Moduls {modul} (zum Nachlesen; eintragen in der Tabelle oben):“, Name als `<code>`,
Beschreibung aus dem Manifest mit `lang="de"`; nur lesend, keine Bedienelemente, keine neuen Stile. Texte de/en in
`i18n/catalogue/area-editor.ts` (`modulParameter.*`); der Hinweis `feld.Schritt.daten.hint` (de/en,
`fields-ablaeufe.ts`) nennt die Liste und dass „Prüfen“ unbekannte Namen und Werte meldet.

**Backend:** `pruefung._dienst_daten` prüft jetzt auch die Werte gegen das Schema des Parameters
(`Draft202012Validator`: erlaubte Werte, Typ, Länge); ein Wert mit `$teil`-Verweis bleibt ungeprüft (erst im Lauf
da). Befund `dienst_daten_wert` (de/en) mit dem Erwarteten (`_erwartet`: erlaubte Werte, auch die einer Liste, sonst
Typ und Höchstlänge). Unbekannte Namen meldet weiter nur `modul_feld`.

**Tests (rot → grün):** Backend `tests/test_p6_modul_parameter.py` (neu, 20 Tests: sechs falsche Werte je Art,
erlaubte Werte, Verweise ungeprüft, Name statt Wert, de/en, alle Werkseeds und Beispiele, der Katalog-Endpunkt
liefert `dienst.parameter` von `ui_upload`): vorher **17 failed / 3 passed** (`KeyError: 'dienst_daten_wert'`; grün
schon: gültige Werte, Endpunkt) → **20 passed**. Studio `modul-parameter.spec.ts` (3) und
`modul-parameter.component.spec.ts` (3: benannte Liste mit Inhalten auf Deutsch, auf Englisch, nicht bei Argumenten,
anderen Schritten oder Modulen ohne Dienst): rot (`TS2307: Cannot find module './modul-parameter'`) → grün.

## P3 zweites Review behoben (20.11., nicht committet)

| Befund | Behebung | Test (rot → grün) |
|---|---|---|
| 1 MINOR — nach dem Rückfall auf die Box blieb `upload_block` gebunden: „Vorschau erneut zeigen“ (`erneut_vorlegen`) oder „Abbrechen“ + „Erschließung nochmal versuchen“ starteten dann ohne Box | `treiber._rechne_schritte` (Auftrag): kommt an einem Schritt mit `zustimmung: upload` die Box, `lauf.pop(upload_zustimmung.BLOCK)` — die Box ist dann der einzige Weg zur Zustimmung. Scheitert der Start ohne Box, bleibt die Bindung nur bei einem **vorübergehenden** Ausfall (zurück an die Frage bzw. `bei_fehler`); ein endgültiger Fehlschlag löst sie | `test_p3_upload_zustimmung::test_r2_1_nach_der_box_bleibt_die_box_der_einzige_weg` (Probleme → Box → `erneut_vorlegen` ohne Probleme → wieder Box) und `test_p4_themenbaum_erschliessen::test_nach_abbrechen_an_der_box_fragt_der_zweite_versuch_wieder` (vorher startete der Job ohne Box — der Befund war echt): rot → grün. `…_nach_einem_endgueltigen_fehlschlag_fragt_der_zweite_versuch_die_box` ersetzt den Fall `vorlaeufig=False` des P4-Nachtrags (startete vor der Behebung ohne Box; nach ihr `KeyError upload_block` → Test angepasst); `…_nach_einem_voruebergehenden_ausfall_startet_der_zweite_versuch_ohne_box` bleibt grün |
| 2 MINOR — `vorgang_teil.aufrufer_marke` ist ein ungesalzener sha256 der WLO-Kennung (per Wörterbuch bestätigbar) | **nicht umgesetzt — Entscheid nötig.** `settings.py` hat kein Geheimnis, das in jedem Betrieb gesetzt ist: `STUDIO_API_KEY` darf leer sein (dann nur das Studio aus), `MCP_AUTH_TOKEN`/`MCP_CLIENT_KEY`/`B_API_KEY` sind je nach Betriebsart leer, `STUDIO_PASSWORD` ist optional. Wege: (a) eine neue Variable (etwa `ABLAGE_MARKE_SECRET`; ohne sie nie Zustimmung → Box), (b) `STUDIO_API_KEY` als HMAC-Schlüssel (ohne ihn Box), (c) ein Salz je Teil im Vorgang (hilft nur gegen vorberechnete Tabellen) | — |
| 3 NIT — der Start ohne Box ist nirgends vermerkt | Der Lauf (im Vorgang) trägt nach einem Start ohne Box `auftrag_zustimmung: upload` (`upload_zustimmung.ZUSTIMMUNG`); `_gestartet` löscht den Vermerk bei jedem Start (nach „Freigeben“ fehlt er). Nicht in `aus.auftrag`: das geht als Schlüsselwörter an `auftraege.ablage.anlegen` (Tabellenspalten — bräuchte eine Migration) | `test_r2_3_der_lauf_vermerkt_die_zustimmung_durch_den_upload`: rot (`AttributeError: ZUSTIMMUNG`) → grün |
| 4 NIT — `"node_ids"` an vier Stellen | `auftrag_teile.KNOTEN_LISTE`; `upload_zustimmung.passt`, `pruefung.upload_zustimmung_passt`, `auftrag_freigabe._LISTE` und `auftrag_teile.ohne_textdateien` nutzen sie | `test_r2_4_die_knotenliste_heisst_an_einer_stelle` (das Literal fehlt im Quelltext der drei Module, in `auftrag_teile` genau einmal): rot → grün |

**Läufe (`backend/`):** alle Dateien zu pruefung/themenbaum/tg6/tw4/u6/k5/p3_/p4_/p5_/p6_/seed/ablauf_beispiele/
studio/openapi/area_schema/freigabe/auftrag/ui_ablage_api (52 Dateien): **1007 passed** (4:41 min). `ruff check
src tests`: sauber. `export_area_schemas.py --check`: „area schemas unchanged“; `export_openapi.py --check`:
„openapi contract unchanged“. **Frontend:** `ng test studio`: **179 Dateien, 2183 Tests grün**; eslint der geänderten
Dateien sauber; `check:a11y`: „Überschriften-Hierarchie und Tabellen-Köpfe sind in Ordnung“; `check:tokens`: „Jedes
gelesene Token ist definiert“ (keine Stile geändert). Nicht im Browser angesehen (keine Server in diesem Auftrag).

**Offen:** Befund 2 (Entscheid Geheimnis); Reviews von P4-Nachtrag/P5/P6; Doku (`docs/ablaeufe.md`: Knopf an
`ohne_metadaten`, `knopf_nichtssagend`, `dienst_daten_wert`) → P7.

### Entscheid zu Befund 2 (zweites Review P3), 20.11.

Die Marke `aufrufer_marke` bleibt ein Streuwert ohne Geheimnis. Der Vorgang trägt seinen Besitzer
ohnehin im Klartext (`db/models.py`, `Vorgang.aufrufer` = `aufrufer_kennung`); ein Streuwert derselben
Kennung im selben Datensatz legt nichts zusätzlich offen. Ein HMAC hinge an einer neuen Variable (kein
heute immer gesetztes Geheimnis) — ohne sie fiele die Zustimmung still auf die Box zurück. Docstring
korrigiert (er versprach, die Kennung stehe nicht im Vorgang).

## P4–P6 Review behoben (20.11., nicht committet)

| Befund | Behebung | Test (rot → grün) |
|---|---|---|
| 1 MAJOR — `dokument_gelesen`, `ordner_geladen`, `dateien_weg` verglichen `ablage.block_id` mit der Auswahl; die schreibt schon `/vorbereiten` (alles `offen`). Vorschau abgebrochen → „Nur hier im Chat lesen“/Namen → `erschliessen_weg` → `metadaten` mit leerer Liste → `ohne_metadaten` ohne Erklärung (Probe `probe_p4.py` nachgestellt) | `services/ablage/vorgang_teil.py`: Marke `abgelegt_block` (`ABGELEGT`) = `block_id`, sobald `mit_ergebnis` einen Eintrag `stored` hält (auch `already`); `aus_plan` setzt sie nie, ein neuer Stapel beginnt ohne. Seed: die drei Regeln vergleichen `teil.ablage.abgelegt_block` mit `{teil.struktur.block_id}`; die Selbsttests tragen die Marke; Kommentare und Kopf angepasst. **Abweichung vom Vorschlag („Marke bei `/abschluss`“):** das Widget ruft `/abschluss` nicht nach einem Halt (`stapelEnde`, etwa abgelaufene Freigabe) und ein gescheiterter Abschluss (Manifest) wirft — dann lägen abgelegte Dateien in WLO, der Ablauf nähme aber die Dateinamen. Die erste abgelegte Datei ist der Nachweis, der in jedem Fall stimmt; „null abgelegt“ setzt nie eine Marke. Ein Neutral-Schalter für eine Chat-Antwort im selben Block ist nicht nötig: nach einer Ablage zeigt das Feld die Ortswahl nicht mehr (`wegAktiv`), die Antwort ist dann die WLO-Antwort | `test_ui_ablage_api.py` +3 (`/vorbereiten` allein und eine gescheiterte Datei: keine Marke; erste abgelegte Datei: Marke). `test_p4_themenbaum_erschliessen.py` +4: Vorschau abgebrochen → Chat auf Dokument (→ `wofuer` über `strukturdokument`), Ordner (→ `wofuer`), Dateien (→ `wofuer`), Dateien mit Namen (→ `inhalte_aus_dateien`), jeweils ohne Starter. `test_alle_wlo_ablagen_fuehren_zum_haekchen` auf die Marke. `test_paket_u6_themenbaum::test_in_wlo_gewaehlt_nichts_abgelegt…` mit dem echten Betriebsstand (Teil `ablage` dieser Auswahl, alles `offen`). Rot: zusammen mit 2/3 **10 failed / 142 passed** (4 Dateien) → nach 1: 2 failed (Befunde 2/3) |
| 2 MAJOR — `treiber` löste die Bindung nur `if ohne_box and not vorlaeufig`; eine endgültig abgelehnte Vorschau (`ausfall: abgelehnt`) ließ sie stehen → „nochmal“ startete ohne Box (Probe `probe_p4b.py` nachgestellt) | `treiber._rechne_schritte` (Auftrag): `if s.zustimmung == UPLOAD and not vorlaeufig: lauf.pop(BLOCK)` im Fehlschlag-Zweig (deckt Box-Rückfall, `ausfall: abgelehnt`, abgelehnte Bestätigung, fehlenden Träger, zu große Argumente) und nach **jedem** Start eines solchen Schritts (nicht nur ohne Box); die Box selbst löste sie schon (zweites Review P3). Nur ein vorübergehender Ausfall (`voruebergehend()`) behält sie | Testattrappe `_Starter(ausfall=…)` (`test_p3_upload_zustimmung.py`: Vorschau scheitert wie `auftrag_freigabe._ausfall`). `test_vorschau_endgueltig_abgelehnt_der_zweite_versuch_fragt_die_box` rot → grün; `…_voruebergehend_aus_der_zweite_versuch_startet_ohne_box` (sichert, dass der vorübergehende Fall die Bindung behält) grün |
| 3 MINOR — „Erschließung nochmal versuchen (dieselben Dateien)“ falsch, wenn nie erschlossen wurde oder sie schon lief | Seed `ohne_metadaten`: „Von WLO erschließen lassen (dieselben Dateien)“ / “Have WLO index the same files”; Kommentar | `test_ohne_metadaten_bietet_die_erschliessung_nochmal_an` (Label) rot → grün |
| 4 MINOR — `_nichtssagende_knoepfe` übersah Knöpfe, die über Verzweigungen zum schreibenden Schritt führen | `pruefung._ueber_verzweigungen`: das Ziel und jede Verzweigung, die (über `_normal`, nur Verzweigungen, Fixpunkt — Kreise enden) dorthin führt; die Optionen werden gegen diese Menge geprüft, der Befund nennt den schreibenden Schritt | `test_p5_knopf_nichtssagend.py` +5: über eine Verzweigung, über zwei und den `sonst`-Zweig (rot → grün), Kreis ohne schreibenden Schritt, Nachricht dazwischen, gute Beschriftung (frei) |
| 5 NIT — Schritttexte | `dokument_laden`/`ordner_laden`/`dateien_laden`: „„In WLO ablegen und erschließen“ (nur angemeldet) … lässt WLO es/sie beschreiben (Häkchen „Metadaten von WLO erzeugen lassen“, einige Minuten)“ (en “(signed in only) … (checkbox “Let WLO create metadata”, a few minutes)” — Wortlaut des Häkchens wie `upload-texte.ts`); `metadaten`: „WLO erschließt die abgelegten Dateien …“ / “… the stored files …” | `test_texte_nennen_haekchen_und_anmeldung_gleich` rot → grün; `test_paket_k5_strukturdokumente` pinnt „WLO es beschreiben“ (bleibt) |
| 6 NIT — Text-Chips („Nein“/„No“) gemeldet, obwohl sie nie schreiben | Ein Chip zählt nur, wenn `wahl_aus_text` ihn (in einer seiner Sprachen) auf eine der schreibenden Optionen abbildet — sonst führt er zum Hinweis `kein_treffer` | `test_ein_text_chip_der_keine_option_trifft_schreibt_nie` (OK/Nein/No) rot → grün (ersetzt `…_wird_gemeldet`); `test_ein_text_chip_der_die_schreibende_option_trifft_wird_gemeldet` (Synonym „okay“) |
| 7 NIT — `_erwartet` ohne Listengrenzen | `_erwartet(schema, lang)`: bei `type: array` „Liste: chat, wlo, namen; 1–3 Einträge; ohne Doppelte“ / “list: …; 1–3 entries; no duplicates” (auch „mindestens“/„höchstens“ allein); Stücke de/en in `pruefung_texte.py` (`erwartet_*`) | `test_p6_modul_parameter::test_eine_liste_nennt_ihre_grenzen` (doppelt, leer, en) 3 rot → grün |
| 8 NIT — „eintragen in der Tabelle oben“ auch im JSON-Modus | `area-editor.ts`: „(zum Nachlesen; oben eintragen)“ / “(for reference; enter them above)” | `modul-parameter.component.spec.ts` (de/en: „oben eintragen“, keine Tabelle) **2 failed / 4 passed** → 6 passed |
| 9 NIT — Manifest-Texte ohne Umlaute | `ui-upload/manifest.json`: echte Umlaute in allen `description`-Texten (55 Zeilen), `beschreibung` und dem Beispiel-`hinweis`; Bezeichner (`ueber_grenze`, Aktion `uebertragen`, Parameternamen) unverändert — strukturell geprüft: nur `description`-Werte geändert. Andere Manifeste tragen schon Umlaute; kein Test verlangt ASCII. `npm run module:register` → `manifeste.json` neu | `module:register -- --pruefen`: „alles aktuell“ |

**Nebenbefund (P5, schon vor diesem Review):** `test_kf_kestra_flows::test_rueckmeldung_1611_mit_ersatzweg…` baute einen Knopf „Ja“ vor einem schreibenden Auftrag — seit P5 ein Befund; die Testattrappe heißt jetzt „Volltext erzeugen“ (die Prüfung, um die es dort geht, bleibt).

**Angepasst, weil sich die Regel änderte:** `test_tg6_review::test_minor8…` (Quelle `teil.ablage.abgelegt_block`), `test_tg6_review2::test_h_nur_die_ablage_der_jetzigen_auswahl` (+1 Fall: dasselbe Feld, nur Vorschau → `dateien_weg`).

**Selbstprüfung:** `pruefe()` der Werkseeds: `fuehrung` (38) `[]`, `sammlung_pruefen` (11) `[]`, `themenbaum` (40 Schritte, 20 Selbsttests, alle grün) `[]`, `warnungen` leer.

**Offen / Hinweise:**
- Die Doku des Teils `wlo.ablage@1` (`docs/`) sollte `abgelegt_block` nennen (Doku-Agent).
- Eine Ablage, die nur `unverified` (keine Antwort des MCP) liefert, setzt keine Marke — der Ablauf nimmt dann den Weg ohne WLO (Dateinamen bzw. Dokument); vorher führte sie zu einem leeren Flow-Aufruf.

**Läufe (`backend/`):** die genannten Dateien (p3/p4/p5/p6, `test_ui_ablage_api`, `test_paket_u6_themenbaum`, `test_tw4_seeds`
und alle zu themenbaum/tg6/u6/k5/seed/pruefung/ablauf_beispiele/ui_ablage): erst **3 failed / 684 passed** (die oben
angepassten Pins in k5/tg6_review/tg6_review2), nach der Anpassung diese 6 Dateien **150 passed**; danach alle 198
Dateien, die `vorgang_teil`, `ui/ablage`, `zustimmung`, `themenbaum`, `simulation`, `pruefung` oder `treiber` nennen (ohne
`test_paket_u_ablage_pg`, braucht Postgres): **4825 passed**. `ruff check src tests`: sauber. `export_area_schemas.py
--check`: „area schemas unchanged“; `export_openapi.py --check`: „openapi contract unchanged“. Probe `probe_p4b.py`: Block
nach Ablehnung gelöst, zweiter Versuch → Box. Probe `probe_p4.py` setzt die Einträge erst nach `mit_ergebnis` auf `offen`
(die Marke bleibt stehen — kein Betriebsstand); ohne die Marke (wie nach `/vorbereiten`) → `wofuer`. **Frontend:** `ng test
studio`: **179 Dateien, 2183 Tests grün**; eslint der geänderten Dateien sauber; `module:register -- --pruefen`: „alles aktuell“.

## Zweites Review P4–P6 behoben (20.11., nicht committet)

| Befund | Behebung | Test (rot → grün) |
|---|---|---|
| 1 MINOR — nach einer Ablage in WLO (`abgelegt_block` gesetzt) war „Andere Auswahl“ in Phase `fertig` frei; „Nur hier im Chat lesen“/Namen im selben Block ließen die Marke stehen → `erschliessen_weg` → `metadaten` (Box) | **(a) Widget:** `upload-ansicht.ts` `abgelegtInWlo` (= `zaehlung(ergebnisse).abgelegt > 0`): „Andere Auswahl“ ist dann gesperrt (`disabled`), der Grund steht darunter als Hinweis „Die Dateien liegen schon in WLO.“ / “The files are already in WLO.” (`upload-texte.ts` `schonInWlo`) und ist per `aria-describedby` (`u-schon-in-wlo`) mit dem Knopf verbunden; „Im Chat weitermachen“ bleibt. `ui-upload.element.ts` `zuruecksetzen` prüft dasselbe (auch ein erzwungener Klick setzt nichts zurück). **(b) Server, gewählt: Marke am Teil lösen** (nicht eine Lauf-Marke in den Regeln — Regeln lesen nur Teile, `vergleich.quelle` kennt nur `teil.…`; die Marke am Teil bleibt die eine Stelle, an der Abläufe eine Ablage dieser Auswahl erkennen). `upload_zustimmung.wlo_antwort` (Ablage in WLO, auch angehalten; `bindet` nutzt sie). `treiber.weiter`: ist die Antwort am `ui_upload`-Schritt **keine** WLO-Antwort und trägt der Teil `ablage` `abgelegt_block` = `offener_block`, geht er ohne die Marke als neuer Teil an den Aufrufer (`vorgang_teil.ohne_marke`; Einträge und Knoten bleiben); die Regeln desselben Aufrufs sehen ihn schon (Lader-Hülle wie bei `weiter_wahl`). Persistenz: `zug_basis.festhalten` → `vorgaenge.teil_setzen` in derselben Transaktion wie der Lauf (Konflikt → Rückrollen wie jeder Zug). Eine angehaltene WLO-Ablage (`abgebrochen` > 0) behält die Marke (WLO-Weg, Box) | Backend `test_p4_themenbaum_erschliessen.py` +3: abgelegt → Chat auf Dokument → `wofuer`, kein Starter, keine Box, Teil `ablage` ohne (nur) die Marke; abgelegt → Namen → `inhalte_aus_dateien`; angehaltene WLO-Ablage behält die Marke (Box). Rot: **2 failed / 1 passed** (Box über `vorlegen`) → grün. `test_tg6_review2::test_h_nur_die_ablage_der_jetzigen_auswahl`: die Fälle mit Ablage antworten jetzt mit einer echten WLO-Antwort (`_WLO`; vorher die ältere `erfasst` — die nimmt jetzt den Weg ohne WLO), +1 Fall „abgelegt, dann `erfasst`“ → `dateien_weg`. Widget `ui-upload-uebertragen.element.spec.ts` +3 (gesperrt mit Grund de, en; nichts abgelegt → frei, ohne Grund): **2 failed / 40 passed** → 42 passed |
| 2 MINOR — Studio zeigte `dienst.parameter` bei jedem Modul mit Dienst; nur `ui_upload` nimmt die Schritt-`daten` als Dienst-Parameter | `GET /api/config/ui-module` liefert je Modul `daten_sind_parameter` (= Name in `werkzeuge.MODUL_DIENST_OHNE_MODELL`). Studio `UiModuleApi.manifesteLaden` hält nur Manifeste solcher Module (`UiModulEintrag.daten_sind_parameter`), die Hilfe fehlt sonst. Hinweis `feld.Schritt.daten.hint` (de/en): Liste und „Prüfen meldet unbekannte Namen und Werte“ nur, wenn das Modul die Daten als Parameter nimmt (etwa ui_upload); sonst Blockdaten, die „Prüfen“ mit der Eingabe des Moduls vergleicht. Die Antwort hat kein Schema (`dict`), der Docstring steht aber in `docs/api/openapi-v1.json` → mit `export_openapi.py` neu geschrieben | Backend `test_p6_modul_parameter::test_der_katalog_sagt_bei_welchem_modul…` (ui_upload wahr, ui_strukturentwurf/ui_strukturabgleich falsch, Menge = `MODUL_DIENST_OHNE_MODELL`): rot → grün. Studio `modul-parameter.component.spec.ts` +3 (echter `UiModuleApi` mit Katalog-Attrappe: `ui_strukturentwurf` keine Hilfe, `ui_upload` Hilfe; Hinweistext de/en): **1 failed** (Strukturentwurf zeigte die Hilfe) → nach dem Filter 1 failed (Hinweis) → **9 passed** (beide Dateien) |
| 3 NIT — `_ueber_verzweigungen` lief nur über Verzweigungen | `pruefung._ohne_halt_zu` (umbenannt): jeder Schritt, der nicht auf die Person wartet (`not _wartet(v)` — Verzweigung, Nachricht ohne Wahl, lesendes Werkzeug, `seite`); ein wartender Schritt beendet die Kette | `test_p5_knopf_nichtssagend.py`: `…_unterbricht_die_kette` (Nachricht) ersetzt durch `test_eine_nachricht_dazwischen_wird_durchlaufen` und `…_direkt_nach_dem_knopf…` (rot: **2 failed** → grün); neu `test_eine_frage_dazwischen_unterbricht_die_kette`. Alle Werkseeds und `tests/ablauf_beispiele` bestehen ohne Label-Änderung |
| 4 NIT — Seed-Kommentar über `erschliessen_weg` | „(``abgelegt_block``, Regeln davor)“ | — (Kommentar) |
| 5 NIT — `_erwartet` mit Schema-Typnamen, „mindestens 1 Einträge“ | `pruefung._typ_wort` + Texte `typ_*` (de/en: „Wahrheitswert (true/false)“/“true/false”, „Text“, „ganze Zahl“ …), `erwartet_text_max` („Text ≤ 300 Zeichen“/“text ≤ 300 characters”), Einzahl `erwartet_mindestens_1`/`erwartet_hoechstens_1`; `pruefung_texte.hat` | `test_p6_modul_parameter.py`: zwei Erwartungen angepasst (boolean/string → Worte), +2 en, +6 `_erwartet` direkt: **9 failed** → 32 passed |
| 6 NIT — `UPLOAD` doppelt belegt, Freigabe-Logik dreifach | `treiber.py` importiert den Modulnamen als `UPLOAD_MODUL`; `_upload_bindung(s, lauf, *, behalten)` trägt die drei Fälle (Box, endgültiger Fehlschlag, Start) samt Begründung im Docstring — Verhalten unverändert | bestehende P3/P4-Tests bleiben grün (94 passed) |

**Läufe (`backend/`):** die genannten Dateien (p3/p4/p5/p6, `test_ui_ablage_api`, `test_paket_u6_themenbaum`,
`test_tw4_seeds`, `test_kf_kestra_flows` und alle 33 zu themenbaum/tg6/u6/k5/seed/pruefung/ablauf_beispiele/openapi/
area_schema/ui_module): zuerst **2 failed / 828 passed** (`test_openapi_contract`: Docstring des Endpunkts → OpenAPI neu
geschrieben; `test_tg6_review2::test_h…`: der Fall antwortete mit `erfasst` → auf eine WLO-Antwort umgestellt, s. o.),
danach **831 passed**. Alle 153 Testdateien, die `treiber`, `vorgang_teil`, `upload_zustimmung`, `pruefung`,
`config/ui-module` oder `simulation` nennen (ohne `test_paket_u_ablage_pg`, braucht Postgres): **3599 passed**. `ruff
check src tests`: „All checks passed!“. `export_openapi.py --check`: „openapi contract unchanged“ (nach dem Neuschreiben);
`export_area_schemas.py --check`: „area schemas unchanged“. `pruefe()` der Werkseeds: `fuehrung` (38) `[]`,
`sammlung_pruefen` (11) `[]`, `themenbaum` (40) `[]`.
**Frontend:** `ng test ui-module`: **32 Dateien, 555 Tests grün**; `ng test studio`: **179 Dateien, 2186 Tests grün** (ein
erster Lauf parallel zur Backend-Suite meldete `backup-tools.component.spec.ts` als Datei gescheitert bei 0 roten Tests —
einzeln und im zweiten Gesamtlauf grün; nicht berührt). eslint der geänderten Dateien sauber; `module:register --
--pruefen`: „alles aktuell“; `build:widget` gebaut; `check-module-budget.mjs`: `ui-upload` **25 200 B gzip** (≤ 26 000),
zusammen 51 054 B (Grenze 60 000). E2E `upload-uebertragen.spec.ts` + `upload-bereitstellen.spec.ts`: **13 passed**.
Nicht im Browser von Hand angesehen (keine Server in diesem Auftrag).

## Durchtest 20.11.

**Aufbau:** echte HTTP-Züge gegen einen eigenen Server (Port 8116) an der Wegwerf-DB `boerdi_uo_durchtest`
(migriert, Seeds ab Werk; danach gelöscht), OpenAI nativ `gpt-6-luna`. Anmelde-Attrappe (erfundener
`WLO-Access-Block` = bestätigte Person, ohne MCP), `MCP_SERVER_URL` unerreichbar, Studio-Schlüssel nur für diesen
Prozess. Variante A ohne weitere Attrappe (der MCP kennt kein Werkzeug → WLO `aus`); Variante B mit einer
Testattrappe „MCP kennt `wlo_prepare_file_batch`“ (zeigt WLO ohne Flow-Träger und ohne Anmeldung). Kein Code, Seed
oder Test geändert; Skripte und Protokolle im Scratchpad (`uo/`, Bericht `uo/durchtest.md`).

| Nr | Prüfung | Ergebnis |
|---|---|---|
| 1 | Studio „Hochladen“: Daten `{"upload":{}}`, Schema `vorauswahl` Vorgabe `chat` (`auto\|wlo\|chat`) | grün |
| 1 | Freier Chat, angemeldet und anonym: die KI bot `ui_upload` im ersten Zug an; Block `orte.vorauswahl: chat`, `rolle_vorgabe: auto`, **kein** `erschliessen`. B angemeldet: `wlo {geht: true, hinweis: ohne_erschliessung, grund_erschliessung: dienst_nicht_erreichbar}` und trotzdem `chat` vorgewählt (UO-5); B anonym: `wlo {geht: false, grund: nur_angemeldet}`; A: `wlo {geht: false, grund: aus}` | grün |
| 2 | Ablauf „Themenbaum erstellen“, „Ein Dokument mit Gliederung, etwa ein Lehrplan“: `rolle_vorgabe: gliederung`, `erschliessen: true`, `orte.vorauswahl: chat` (Schritt `auto`, WLO geht nicht voll); „Meine Dateien“: `rolle_vorgabe: material`; anonym dieselben Schritt-Daten, WLO `nur_angemeldet` (B) bzw. `aus` (A). Schritttexte nennen „In WLO ablegen und erschließen“ (nur angemeldet), das Häkchen „Metadaten von WLO erzeugen lassen“, „Nur hier im Chat lesen“ (Dateien: dazu „Nur die Dateinamen senden“) | grün |
| 3 | Chat-Weg: `POST /api/ui/dokumente` (Rolle `struktur`, Lehrplan .md) → 200; Antwort `bereitgestellt`/`ort: chat` → Teil `strukturdokument` → `wofuer`; Chips bis `entwurf_dokument`; „Entwurf erstellen“ (9,9 s) → `ui_strukturentwurf` mit den drei Themenfeldern des Lehrplans (`quelle: dokument`) | grün |
| 3 | Rolle `beides` („Meine Dateien“): 200, `rolle: beides`, mit Kurzangaben; danach Teile `metadaten` (Eintrag `beides`) und `strukturdokument`, weiter an `wofuer` | grün |
| 4 | `POST /api/config/ablauf-pruefen` (Themenbaum aus der DB, 40 Schritte): keine Befunde, keine Warnungen; `ablauf-testen`: 20/20 Selbsttests grün; `GET /api/config/ablaeufe`: alle Werkseeds 0 Befunde | grün |

**Kein Fehler gefunden.** Hinweise: die Block-Daten tragen die errechnete `orte.vorauswahl`, nicht den Schritt-Wert
`auto` (so gebaut, §2). Ein Fortsetzen mit einem anderen Anmelde-Block fand das Dokument nicht („nicht mehr
verfügbar“) — richtig, Uploads sind an den Aufrufer gebunden. Die Schritttexte nennen den WLO-Ort auch, wenn er
im Feld gesperrt ist (statischer Text, das Feld nennt den Grund). Logs ohne Traceback/ERROR, ohne Schlüssel
und ohne Block.

**Grenzen:** Der Zustimmungsweg (WLO-Ablage → `erschliessen_weg` → `metadaten` mit `zustimmung: upload` → Flow
ohne Box; ohne Häkchen → `lesen`; fremde Knoten → Box) und die Volltext-Kette brauchen einen echten MCP — hier
nicht gelaufen; abgedeckt durch `tests/test_p3_upload_zustimmung.py` und `tests/test_p4_themenbaum_erschliessen.py`,
**nach dem Deploy auf Staging prüfen**. Häkchen und Knöpfe im Widget nicht im Browser angesehen (nur Block-Daten).
Server beendet (Port 8116 frei), Wegwerf-DB gelöscht.
