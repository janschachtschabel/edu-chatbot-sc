# Änderungsnotiz „Upload-Ort und Erschließung“ (P1–P7)

Stand 2026-11-20 · Basis `main` (wird beim Upload ergänzt) · Branch (wird beim Upload ergänzt)
Plan und Log: [`docs/plans/2026-11-20-upload-ort-und-erschliessung.md`](../plans/2026-11-20-upload-ort-und-erschliessung.md)

Diese Notiz sagt je Paket **was** sich geändert hat, **wo** (Dateien) und **warum**, und welcher
Commit es trägt. Die Commits sind nach Thema geschnitten, nicht nach Ordner; getestet ist der
Endstand.

**Ziel (Entscheide UO-1 … UO-8 des Nutzers):** Mit WLO-Anmeldung ist „In WLO ablegen und
erschließen“ (Kestra) der Normalfall — auch für Lehrpläne; „Nur hier im Chat lesen“ ist der Weg ohne
Anmeldung und für Dateien, die nicht nach WLO sollen. Was vorausgewählt ist, legt der Anwendungsfall
im Studio fest, nicht der Code. Jede Option, jede Frage und jeder Knopf sagt sichtbar, was passiert.

## Was Betrieb und Deploy wissen müssen

- **Keine Migration**, keine neue Umgebungsvariable, keine Änderung am MCP nötig.
- **Image neu bauen** (Backend mit Seeds, Studio, Widget und Modul-Bündel), danach Hard-Reload im
  Browser. Budget `ui-upload`: benannte Ausnahme 24 → **26 kB** gzip (gebaut 25 082 B; alle Module
  50 936 B von 60 000).
- **Werksabgleich** (`import-config --werksabgleich`, `migrate`-Dienst) in ruhiger Zeit: geändert
  sind `06-ablaeufe/themenbaum` und `01-base/upload-config`. Wartende Läufe von „Themenbaum erstellen“
  brechen dabei ab. Im Studio angepasste Fassungen bleiben (und arbeiten wie bisher mit Rückfrage
  und Freigabe-Box) — dann im Studio unter Sicherung → „Werk und eigene Fassung“ „Werksfassung
  verwenden“.
- **Neues Studio-Feld:** „UI-Module → Hochladen“ → „Vorgewählter Ort im freien Chat“
  (`upload-config.vorauswahl`: `chat` Vorgabe, `wlo`, `auto`).
- **Verhalten ändert sich:**
  - keine Rückfrage „Metadaten erzeugen?“ vor Kestra auf den Upload-Wegen; der Klick „In WLO ablegen
    und erschließen“ ist die Zustimmung (nur für Knoten, die genau dieser Upload neu anlegte — sonst
    Freigabe-Box);
  - auch der Dokument-Weg (Lehrplan) wird in WLO erschlossen (E3 aufgehoben);
  - im freien Chat ist „Nur hier im Chat lesen“ vorgewählt, auch angemeldet (vorher WLO);
  - neue Prüfbefunde `zustimmung_upload`, `ablage_reserviert`, `knopf_nichtssagend`,
    `dienst_daten_wert` — eigene Abläufe nach dem Deploy im Studio prüfen (ein Befund verhindert das
    nächste Speichern, hält den Ablauf aber nicht an).
- `docs/api/openapi-v1.json` und `area-schemas.fixture.ts` neu erzeugt (`beides`, `erschliessen`,
  `zustimmung`, `vorauswahl`); `export_openapi.py --check` und `export_area_schemas.py --check` grün.
- Bekannt, nicht aus diesem Paket: Das Widget-Hauptbündel warnt weiter (202,26 kB gzip > 200 kB,
  696 kB roh > 660 kB); `offene-befunde-und-todo.md` §5.

## Commits und Themen

| # | Commit | Was | Wo (Kern) |
|---|---|---|---|
| 1 | (wird beim Upload ergänzt) | P1 Rollen Gliederung / Material / beides | `ui_module/rollen.py`, Ablage-, Dokument- und Ablauf-Lesestellen, `ui-upload` |
| 2 | (wird beim Upload ergänzt) | P2 Ort, Vorauswahl, Häkchen, Wortlaut | `upload_orte.py`, `dienst_upload.py`, `api/ui_ablage.py`, `upload-config`, `ui-upload` |
| 3 | (wird beim Upload ergänzt) | P3 Zustimmung durch den Upload-Klick | `upload_zustimmung.py`, `treiber.py`, `pruefung.py`, `vorgang_teil.py` |
| 4 | (wird beim Upload ergänzt) | P4 Seed „Themenbaum erstellen“ (+ Nachtrag „nochmal versuchen“) | `seeds/06-ablaeufe/themenbaum.yaml` |
| 5 | (wird beim Upload ergänzt) | P5 Prüfung `knopf_nichtssagend` | `pruefung.py`, `pruefung_texte.py` |
| 6 | (wird beim Upload ergänzt) | P6 Modul-Parameter im Studio, Werte in der Prüfung | Studio `modul-parameter*`, `pruefung._dienst_daten` |
| 7 | (wird beim Upload ergänzt) | P7 Doku und Rückmeldungen | `docs/…` |

Tests gehören zum Commit ihres Themas.

## P1 — Rollen: Gliederung / Material / beides (UO-4)

**Was:** Neue Rolle `beides` („Gliederung und Material“) neben `struktur` („Gliederung“) und `inhalt`
(„Material“); „Nicht verwenden“ = `ignorieren`. Die Auswahl spricht Klartext (de/en) und hat eine
Legende unter der Liste (`aria-describedby`). Höchstzahl 5 und lesbare Formate gelten für `struktur`
und `beides`. `zahlen.strukturdokumente` = `struktur` + `beides`, `zahlen.inhalte` = nur `inhalt`. Beim
MCP wird `beides` als `structure` abgelegt, im Teil `ablage` bleibt `beides`. Alte Einträge bleiben
gültig, keine Migration (`ablage._lesbar` liest die Mengen {struktur, beides} bzw. {inhalt, beides}).

**Wo:** neu `ui_module/rollen.py` (`ist_gliederung`, `ist_material`, `als_material`); `api/ui_ablage.py`,
`api/ui_dokumente.py`; `services/ablage/{mcp_ablage,vorgang_teil}.py`; `services/ablauf/{metadaten,
vorbelegung,werkzeuge,inhalte_aus_dateien}.py`; `services/arbeitsstand_teile.py`;
`services/dokumente/{ablage,metadaten_lokal,strukturdokument_teil}.py`; `ui_module/{strukturentwurf_ordner,
upload_antwort,upload_bereitgestellt,upload_rahmen}.py`; Frontend `_vertrag/modul-host.ts`,
`ui-upload/*` (Erfassen, Rollen, Baum, Ansicht, Texte, Orte, Übertragen), `manifest.json`.

**Warum:** Ein Lehrplan kann zugleich Gliederung und Material sein; „Inhalt/Strukturdokument“ sagte
nicht, was die Rolle bewirkt.

**Tests (rot → grün):** `tests/test_p1_rollen_beides.py` (neu, 26 Tests): rot 17 failed (nur die
Hilfen grün) → 26 passed; dazu je ein Test in `test_paket_u2_dokumente_api.py` und
`test_paket_u_ablage_pg.py` (Postgres). Lauf der Upload-/Ablage-/Rollen-Dateien: 944 passed,
1 skipped. Frontend `upload-rollen.spec.ts` (+4), `ui-upload.element.spec.ts` (+4): rot (TS2305/TS2345)
→ grün; `ng test ui-module` 32 Dateien, 531 Tests grün.

**Review P1:** Backend 1 MAJOR, 2 MINOR, 1 NIT — alle behoben. MAJOR: `metadaten.materialien()` nahm
auf dem WLO-Weg reine Gliederungen als Material (Entwurf, Zuordnung sortierten sie ein) — jetzt nur
Material; Tests rot 3 failed → grün, Mutationsprobe für `vorbelegung`/`werkzeuge` (2 failed bei
zurückgedrehtem Code). Weitere 2 MINOR und 2 NIT zur Oberfläche (Zählzeile, Vorschau-Wortlaut,
Sammelknöpfe) mit P2 behoben. Lauf 608 passed.

## P2 — Ort, Vorauswahl, Häkchen, Wortlaut (UO-1, UO-2, UO-5)

**Was:**
- Frage „Wo sollen die Dateien verarbeitet werden?“ mit **In WLO ablegen und erschließen** / **Nur
  hier im Chat lesen**; Nebenknopf „Nur die Dateinamen senden (der Inhalt bleibt auf deinem Gerät)“.
  Ohne Anmeldung ist WLO ausgegraut („melde dich über den Konto-Knopf unten an“).
- Häkchen **„Metadaten von WLO erzeugen lassen“** unter dem gewählten Ort WLO mit Hinweis zum Titel —
  nur, wenn der Ablauf-Schritt `erschliessen` ausdrücklich setzt und der Metadaten-Flow da ist; sonst
  heißt der Ort „In WLO ablegen“ (nur ablegen). Ohne Flow nennt die Erklärzeile den Grund
  (`grund_erschliessung`: `flow_nicht_freigegeben` / `dienst_nicht_erreichbar`).
- Knöpfe: „Hier lesen“ (Chat), „Weiter zur Vorschau“ (WLO, legt noch nichts ab), in der Vorschau
  „In WLO ablegen und erschließen“ bzw. „In WLO ablegen“ (vorher „Jetzt übertragen“).
- Schritt-Parameter `vorauswahl` (`auto|wlo|chat`), `rolle_vorgabe` (`auto|gliederung|material|beides`),
  `erschliessen` (bool) — nur aus einem Ablauf; die KI setzt keinen. `einzeldatei_als_struktur: true`
  bleibt gültig und heißt `rolle_vorgabe: gliederung`; es schaltet nichts mehr auf „nur ablegen“.
  Freier Chat: Studio `upload-config.vorauswahl`, Vorgabe `chat` (auch angemeldet).
- `POST /api/ui/ablage/vorbereiten` nimmt `erschliessen` (`StrictBool`, Vorgabe `false`); der Server
  hält es im Teil `ablage.erschliessen` nur mit Flow fest und meldet den Wert zurück. Der Rahmen
  `[ABLAGE …]` sagt der KI, ob Metadaten gewählt wurden.

**Wo:** `domain/config_models/upload.py`, `seeds/01-base/upload-config.yaml`, `ui_module/{rollen,
upload_orte,dienst_upload,upload_rahmen,dienst_fehler,upload_antwort}.py`, `ui_module/manifeste.json`,
`api/ui_ablage.py`, `services/ablage/vorgang_teil.py`, `services/ablauf/metadaten.py`,
`services/arbeitsstand_teile.py`; Frontend `ui-upload/{manifest.json, upload-orte*, upload-ansicht,
ui-upload.element, upload-rollen, upload-texte, upload-uebertragen*, upload-chat, upload-stil}.ts`,
`README.md`, `_vertrag/modul-host.ts`, `ui/src/stream/ablage-transport.ts`; Studio `fields-upload.ts`,
`ui-modul-vorschau-host.ts`, `area-schemas.fixture.ts`; `scripts/check-module-budget.mjs`;
`docs/api/openapi-v1.json`.

**Warum:** Was vorausgewählt ist und ob erschlossen wird, hing an `einzeldatei_als_struktur` und an
Regeln im Code; jetzt legt es der Anwendungsfall fest, und die Oberfläche sagt, was geschieht.

**Tests (rot → grün):** `tests/test_p2_ort_vorauswahl.py` (neu, 30 Tests): 22 failed / 5 passed → 30
passed; `test_ui_ablage_api.py` +5: rot → grün; angepasst `test_paket_u4_orte`, `test_ui_upload`,
`test_ablauf_upload_schalter`, `test_paket_e_volltext_ehrlich`, `test_tg3de_strukturdokumente`. Lauf
(117 Dateien): 1869 passed, 1 skipped. Frontend rot (TS2339/TS2305) → `ng test ui-module` 547 grün,
`ng test studio` 2177 grün, `ablage-transport.spec.ts` 1 rot → 6 grün; E2E (`upload-*`): 18 passed;
Budget-Test zuerst auf 26 kB gestellt (rot) → grün.

**Review P2:** 1 MAJOR, 3 MINOR, 2 NIT — alle behoben. MAJOR (Entscheid des Nutzers): das Häkchen
erschien im freien Chat und war an, obwohl dort niemand `ablage.erschliessen` nutzt — jetzt nur, wenn
der Schritt `erschliessen` setzt. MINOR: Datenschutz-Satz folgt in der Vorschau dem Wert des Servers
(Mutationsprobe 1 failed), Grund ohne Flow und Weg zur Anmeldung, „Nicht verwenden“ statt
„ignorieren“. NIT: Titel und Kurzbeschreibung zählen nur Material. `tests/test_p2_review_befunde.py`
(neu, 14 Tests): rot 12 failed / 2 passed → grün. Läufe 432 + 571 passed; `ng test ui-module` 552
grün; Playwright 13 passed.

## P3 — Zustimmung durch den Upload-Klick (UO-3, sicherheitsrelevant)

**Was:** Auftragsschritt-Feld `zustimmung` (`freigabe` | `upload`; Vorgabe leer = Box). Mit `upload`
startet ein Auftrag mit `repo_schreibt` nach der MCP-Vorschau im selben Zug mit der Bestätigung,
wenn der Server die Zustimmung nachweist — sonst Freigabe-Box wie bisher. Bedingungen
(`services/ablauf/upload_zustimmung.py`): persönliche Anmeldung; Teil `ablage` mit `erschliessen:
true`; `block_id` = Upload-Block, den dieser Lauf zuletzt beantwortete (nur eine fertige WLO-Ablage
bindet); Aufrufer-Marke passt; alle `node_ids` in `inhalte` mit `stand: stored`, `neu: true`, nicht in
`frueher`; Vorschau ohne Probleme; nur der Metadaten-Flow. Die Bindung gilt einmal und fällt mit der
Box. Prüfung: `zustimmung_upload` (statt `auftrag_rueckfrage`, wenn alles passt) und
`ablage_reserviert` (nur der Server schreibt `ablage`).

**Wo:** `domain/config_models/ablauf.py`, neu `services/ablauf/upload_zustimmung.py`,
`services/ablauf/{treiber,pruefung,pruefung_texte,typen,werkzeuge,auftrag_teile,auftrag_freigabe}.py`,
`services/ablage/vorgang_teil.py` (`aufrufer_marke`, `aufrufer`, `neu`), `api/ui_ablage.py`,
`ui_module/upload_antwort.py` (`haekchen`); Studio `fields-ablaeufe.ts`; Schemas/OpenAPI neu erzeugt.

**Warum:** Die Rückfrage nach dem Upload fragte ein zweites Mal, was die Person mit dem Knopf schon
gesagt hat. Die Zustimmung bleibt eng: nur frisch angelegte Knoten dieses Uploads, nur diese Person,
nur dieser Lauf.

**Tests (rot → grün):** `tests/test_p3_upload_zustimmung.py` (neu, 43 Tests): rot 33 failed / 10
passed (die 10: Rückfall auf die Box, schon vorher so) → 43 passed, dazu ein Test „freier Chat nie“;
`test_ui_ablage_api.py` +2.

**Review P3:** 1 MAJOR, 5 MINOR, 2 NIT und ein Punkt des Koordinators — alle behoben. MAJOR: nicht auf
den Metadaten-Flow begrenzt. MINOR: Bindung nur einmal; nur eine fertige WLO-Ablage bindet;
Vorschau-Zweig getestet; `already` zählt als `neu` (gemessen im MCP-Code: derselbe Stapel-Schlüssel);
`ablage` nur vom Server. NIT: Lauf-Marke im Log, Docstring. Koordinator: `/vorbereiten` hält
`erschliessen` nur, wenn der Block ein Häkchen zeigte. Rot 19 failed / 88 passed → 107 passed;
verwandte Läufe 771 + 485 passed; `ng test studio` 2177 grün.

**Zweites Review P3 (Sicherheitsregel):** 2 MINOR, 2 NIT. Behoben: nach dem Rückfall auf die Box blieb
der Upload-Block gebunden („Vorschau erneut zeigen“ bzw. „Abbrechen“ + „nochmal“ starteten ohne
Box) — jetzt löst die Box die Bindung (Tests rot → grün); Vermerk `auftrag_zustimmung: upload` am
Lauf; `KNOTEN_LISTE` an einer Stelle. **Entschieden, nicht umgesetzt:** `aufrufer_marke` bleibt ein
Streuwert ohne Geheimnis (der Vorgang trägt den Besitzer ohnehin im Klartext; ein HMAC hinge an einer
neuen Variable). Lauf (52 Dateien) 1007 passed; `ng test studio` 179 Dateien, 2183 grün.

## P4 — Seed „Themenbaum erstellen“ (UO-3, UO-6)

**Was:** `metadaten_frage` entfällt, neu `erschliessen_weg` (`ablage.erschliessen` → `metadaten` mit
`zustimmung: upload`, sonst `lesen`). `ordner_geladen`, `dateien_weg` und `dokument_gelesen` (neu: die
WLO-Ablage dieses Blocks zuerst) führen dorthin; `nach_lesen` führt das Dokument immer zu den
Fragen. Upload-Schritte: `dokument_laden`/`dokument_chat` `rolle_vorgabe: gliederung`,
`ordner_laden`/`dateien_laden` `rolle_vorgabe: material`, alle `vorauswahl: auto`, `erschliessen:
true` (außer `dokument_chat`, nur Chat). Texte nennen die Orte und die Folge; Warte-Text am Flow.
40 Schritte und 20 Selbsttests bleiben (zwei neue Lehrplan-Selbsttests, zwei zusammengelegt bzw.
nach `test_paket_u6_themenbaum` verschoben). E3 vom 20.11. ist aufgehoben.

**P4-Nachtrag (Entscheid des Nutzers):** `ohne_metadaten` bekommt „Von WLO erschließen lassen
(dieselben Dateien)“ → `metadaten`. Ohne Box nur nach einem vorübergehenden Ausfall (Bindung
besteht); sonst Freigabe-Box (fail closed).

**Wo:** `backend/seeds/06-ablaeufe/themenbaum.yaml`; im Plan `2026-11-20-konto-vorgaenge-und-warten-
auf-volltext.md` §8 E3 als aufgehoben vermerkt.

**Warum:** UO-6 — auch Lehrpläne bekommen in WLO den Flow; das Häkchen ersetzt die Rückfrage.

**Tests (rot → grün):** `tests/test_p4_themenbaum_erschliessen.py` (neu, 14 Tests): 12 failed / 2
passed → 14 passed; Nachtrag +7: 5 failed / 14 passed → grün. Angepasst: `test_paket_u6_themenbaum`,
`test_tg6_review`, `test_tg6_review2`, `test_tg6_nachpruefung`, `test_tg6_themenbaum`,
`test_paket_k5_strukturdokumente`, `test_paket_k_review`, `test_tw4_seeds`,
`test_paket_e_volltext_ehrlich` (vorher 14 failed / 960 passed). Läufe 1101 + 439 passed; `pruefe()`
aller Werkseeds leer.

## P5 — Prüfung: nichtssagende Knöpfe (UO-8)

**Was:** Eine Option (oder ein Text-Chip derselben Frage) vor einem Schritt, der ins Repositorium
schreibt, darf nicht nur „OK“, „Weiter“, „Ja“, „Los“, „Yes“, „Next“ … heißen — Befund
`knopf_nichtssagend` (de/en) mit Beispiel „In WLO ablegen und erschließen“. Alle Werkseeds bestehen.

**Wo:** `services/ablauf/pruefung.py` (`_nichtssagende_knoepfe`, `NICHTSSAGEND`), `pruefung_texte.py`.

**Warum:** Ein Knopf, der schreibt, muss sagen, was er tut.

**Tests (rot → grün):** `tests/test_p5_knopf_nichtssagend.py` (neu, 29 Tests): 29 failed → 29 passed.

## P6 — Modul-Parameter im Studio, Werte in der Prüfung

**Was:** Unter „Daten des Moduls“ zeigt das Studio die Parameter des Moduls aus dem Manifest (Name,
Beschreibung, erlaubte Werte, Typ, Vorgabe, Pflicht; nur lesend, benannte Liste). Quelle
`GET /api/config/ui-module` (kein neuer Endpunkt). Die Prüfung meldet unpassende Werte
(`dienst_daten_wert`); `$teil`-Verweise bleiben ungeprüft.

**Wo:** Studio `core/ui-module-api.service.ts`, neu `schema-form/modul-parameter.ts` und
`modul-parameter.component.ts`, `teil-werte.component.ts`, `i18n/catalogue/{area-editor,
fields-ablaeufe}.ts`; Backend `services/ablauf/pruefung.py` (`_dienst_daten`, `_erwartet`),
`pruefung_texte.py`.

**Warum:** `vorauswahl`, `rolle_vorgabe` und `erschliessen` sollen ohne Code-Kenntnis pflegbar sein.

**Tests (rot → grün):** `tests/test_p6_modul_parameter.py` (neu, 20 Tests): 17 failed / 3 passed → 20
passed; Studio `modul-parameter.spec.ts` (3) und `modul-parameter.component.spec.ts` (3): rot
(TS2307) → grün; `check:a11y`, `check:tokens` grün.

**Review von P4, P4-Nachtrag, P5 und P6:** erste Runde 0 CRITICAL, 2 MAJOR (abgebrochene Vorschau +
Wahl „Nur hier im Chat lesen“ führte auf den Erschließungsweg → Marke `abgelegt_block` erst nach einer
wirklich abgelegten Datei; Bindung blieb nach einer abgelehnten Vorschau → jeder endgültige Ausgang gibt
sie frei), 2 MINOR, 6 NIT — behoben. Zweite, unabhängige Runde: 0 CRITICAL, 0 MAJOR, 2 MINOR („Andere
Auswahl“ nach Ablage gesperrt, Marke bei Nicht-WLO-Antwort verworfen; Parameter-Hilfe im Studio nur für
Module, deren Daten Parameter sind), 4 NIT — behoben.

**Abschluss:** Backend-Suite 12467 grün; Frontend ui 1592, ui-module 555, widget 98, studio 2186; alle
CI-Schritte lokal grün (ui-upload 25 200 B gzip von 26 000); E2E 132 grün. Durchtest gegen eine
Wegwerf-DB (echte HTTP-Züge, Anmelde-Attrappe): freier Chat wählt „Chat“ vor, kein Häkchen; Themenbaum-
Schritte mit Rollen-Vorgabe und Häkchen; Chat-Weg bis zum Entwurf; Rolle `beides`; Prüfung und 20
Selbsttests grün. Der Zustimmungsweg mit echtem Kestra-Flow ist nur in Treiber-Tests geprüft — auf
Staging nach dem Deploy nachziehen.

## P7 — Doku und Rückmeldungen

**Was:** `docs/ui-module.md` (Abschnitt „Ort, Rollen und Erschließung“, veraltete Stellen zu
„Hochladen“, „Hier im Chat“, E3, Rollen), `docs/ablaeufe.md` (Daten eines Modul-Schritts,
`erschliessen_weg`, „nochmal versuchen“, `knopf_nichtssagend`, „Zustimmung durch den Upload“),
`docs/uebergabe-betrieb.md` §15 (Deploy), `docs/offene-befunde-und-todo.md` (§1, §4, §5), diese Notiz;
neu `docs/mcp-rueckmeldung-2026-11-20-loeschen-und-umwandlung.md` (Wunsch „eigene Inhalte löschen“
an den MCP-Entwickler, E15 Umwandlungs-Flow an die Flow-Autoren).

**Warum:** Redaktion und Betrieb sollen den neuen Weg ohne den Plan verstehen.

## Offen

Siehe `docs/offene-befunde-und-todo.md` §1 „Upload-Ort und Erschließung“: „Gliederungsdatei behalten
oder löschen?“ (wartet auf das MCP-Werkzeug), E15, Anmelde-Knopf am ausgegrauten Ort, Durchtest im
Browser (Plan §5), Reviews P4–P6.
