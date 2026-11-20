# Paket A: Entwurf aus Dokument (2026-11-19)

Plan: `docs/plans/2026-11-19-dokument-entwurf-und-sitzung.md`, Paket A (A1–A7), Entscheide E1–E7.
Auslöser: Rückmeldung des Nutzers vom 19.11. (Befunde S1, S2, S4 und der Wunsch nach Rückkontrolle).
Unabhängig reviewt am 19.11. (3 MAJOR, 7 MINOR, 6 NIT), alle Befunde behoben (Abschnitt
„Review behoben“); dazu ein vorbestehender Befund (Fehlersätze für Dokumente).

## Warum

- **S1:** Ein vorübergehender Fehler des Anbieters (503) bei Ebene 1 wurde zum Sammelgrund `fehler`.
  Dessen Text sagt der KI „antworte ohne Entwurf“. Damit war der Ablauf in einer Sackgasse.
- **S2:** Eine Scan-PDF in WLO ergab einen Entwurf ohne Inhalt der PDF. Zwei Ursachen: Der
  Dokument-Schritt durfte `ui_strukturentwurf` ohne `aus_dokument` rufen und entwarf dann frei. Und
  der WLO-Weg prüfte nicht auf Scans: Jeder nicht leere Text galt als Dokument.
- **S4:** Entwürfe aus Lehrplan-PDFs blieben flach. Das Modell sah nur die Gliederung und 1 500
  Zeichen Anfang und fand die Lernfelder nicht.

## Was

### A1 – vorübergehende Fehler einmal wiederholen (E3)

- Neue Datei `services/strukturentwurf_wiederholen.py`. `voruebergehend(e)` prüft auf
  `ServiceUnavailableError`, `InternalServerError`, `APIConnectionError` (dazu gehört auch
  `litellm.Timeout` beim Verbinden) und `BadGatewayError`. Die eigene Frist (`TimeoutError`) bleibt
  `frist`.
- `einmal_wiederholt(...)` wiederholt nach `PAUSE_S` (2 s) genau einmal, wenn danach noch
  `MINDEST_REST_S` übrig sind.
- `strukturentwurf_dienst._obere_ebene` nutzt das. Bleibt der Fehler, ist der Grund
  `voruebergehend`. `_Lauf.kinder` nutzt es ebenso; bleibt der Fehler dort, ist der Punkt
  `ausstehend`.
- `ui_module/dienst_fehler.py` hat einen neuen Text `voruebergehend`: „gerade nicht erreichbar – in
  einem Moment einfach ‚nochmal‘ schreiben“. Die KI ruft nicht neu auf, und der Ablauf bleibt am
  Schritt.

### A3 – Scan-Prüfung im WLO-Weg (E5)

- `services/dokumente/strukturdokument.volltext`: Ein Volltext mit weniger als
  `KAUM_TEXT_WOERTER` Wörtern (seit dem Review 30, dazu weniger als 30 % Buchstaben) nach `bereinigen` hat den Grund `not_extracted`. Es gelten
  dieselben Texte wie ohne Text („kein lesbarer Text“).
- Ein Wort sind mindestens zwei Buchstaben am Stück (`woerter`). Seitenzahlen und Zeichen zählen
  nicht.

### A2 – feste Argumente am KI-Schritt (E4)

- Das Modell `AgentSchritt` (`domain/config_models/ablauf.py`) hat ein neues Feld
  `feste_argumente: {werkzeug: {argument: wert}}`.
- Leer gilt als nicht gesetzt. Die Fassung bestehender Abläufe bleibt deshalb gleich.
- Der Server setzt die festen Argumente in jeden Aufruf des Werkzeugs in diesem Schritt. Das
  geschieht in `ui_module/dienst.aufruf` nach der Vorbelegung, also gehen sie der KI und der
  Vorbelegung vor.
- Die Argumente kommen auf beiden Wegen an: im Muster-Weg über `tool_loop_module.FESTE_KEY`
  (`respond.py`), im Agent-Weg über `run_agent_loop(modul_feste=…)` (`respond_agent.py`). Beide
  setzen `Umgebung.feste_argumente`.
- Prüfung (`services/ablauf/pruefung_feste.py`, neu, aufgerufen aus `pruefung._agent`). Sie meldet,
  wenn
  - das Werkzeug nicht im Schritt steht,
  - es kein UI-Modul mit Dienst ist (dort wirkten die Argumente nie),
  - ein Argument nicht im Schema steht oder
  - ein Wert nicht zum Schema passt.

  Die Texte stehen auf Deutsch und Englisch in `pruefung_texte.py`.
- Seeds:
  - `themenbaum.yaml` `entwurf_dokument` → `{ui_strukturentwurf: {aus_dokument: true}}`
  - `themenbaum.yaml` `entwurf_inhalte` und `themenbaum_aus_inhalten.yaml` `entwurf` →
    `{aus_inhalten: true}`
- Studio: Das Formular ist schema-getrieben. Neu sind die Fixture
  (`scripts/export_area_schemas.py`), Beschriftung und Hilfe auf Deutsch und Englisch
  (`fields-ablaeufe.ts`) und der Eintrag in der Liste der JSON-Felder (`schema-to-fields.spec.ts`).

### A5 – Ebene 2 aus einem Dokument (E6)

- `strukturentwurf_dokument.plan_ohne_angabe` (Aufruf aus `nacharbeit`): `unterthemen: 0` an einem
  oberen Punkt mit Text (Abschnitte; auf dem Weg „ganz“ jeder Punkt, E1c) heißt „nicht angegeben“; der Punkt
  bekommt `UNTERTHEMEN_OBEN` (8) als Plan. Das gilt je Punkt, nicht erst, wenn alle 0 melden
  (Stand nach dem Review, MINOR 5).
- Die Materialien der Person (`aus_inhalten`) und freie Entwürfe ändern sich nicht.

### A4 – der ganze Text an Ebene 1 (E1, E2)

- `strukturentwurf_dokument.ganzer_text`: Ein Markdown bis `GANZTEXT_ZEICHEN` geht ganz an Ebene 1
  (Feld `text` statt `anfang`). Bei mehreren Dokumenten gilt die Grenze für alle zusammen.
- Die Gliederung mit Kennungen bleibt dabei; die Fundstelle funktioniert wie bisher. Ebene 2
  bekommt auf diesem Weg den ganzen Text statt eines Auszugs (Stand nach dem vierten Review, E1c;
  die Anker aus den ersten drei Reviews sind ersetzt). Eine zweite Moderation gibt es dort nicht.
- Den Weg „ganz“ gibt es nur, wenn der Aufrufer die Moderation zusagt
  (`erzeugen(ganz_moderiert=True)`, zweites Review, MINOR 5).
- Darüber bleibt der alte Weg: Gliederung, Anfang und Auszüge.
- Der Prompt `oben_aus_dokument(text=…)` hat den Satz „Die tragende Ordnung (Lernfelder,
  Themenfelder, Kapitel) steht im Text, auch wenn die Gliederung sie nicht zeigt.“ Das gilt für ein
  und für mehrere Dokumente.
- Moderation (`ui_module/dienst_ganztext.py`, neu): Der ganze Text wird vor dem Entwurf geprüft
  (Stand nach den Reviews):
  - in Stücken zu 30 600 Zeichen mit 200 Überlappung, nacheinander (ein Platz je Entwurf);
  - unter der eigenen Stufe `strukturentwurf_ganztext`;
  - gebunden an die Frist des Dienstes;
  - jedes Stück über `dienst._ebene_eins_pruefen`, dort greift `MODERATION_FAILURE_MODE`, und
    `teilweise` gilt als kein Urteil.
  - Ein abgewiesenes Stück ergibt `abgewiesen`.
  - Ohne Urteil im Modus `closed` ergibt es `pruefung_fehlt`.
  - Das gilt auch für einen Chat-Text, dessen Anfang schon geprüft wurde.
  - Ein Volltext aus WLO (`ungeprueft`) bekommt erst die bisherige Prüfung von Übersicht und Anfang
    und danach die Prüfung des ganzen Texts.
- Die Grenze ist **100 000 statt 80 000** (Messung unten, Abweichung vom Plan).

### A6 – Rückkontrolle „Gelesener Text“ (E7)

- `strukturentwurf_dokument.gelesen(dokument)`: Je Dokument (höchstens 10) stehen dort Name,
  Zeichen, Weg (`ganz`/`gliederung`), die ersten 2 000 Zeichen und bis zu 30 Abschnittstitel. Bei
  mehreren Dokumenten wird das aus dem vereinten Stand zurückgewonnen.
- `strukturentwurf_dienst.erzeugen` setzt das Feld nur mit Dokument.
- Die KI sieht das Feld nie:
  - Im Manifest steht `gelesen` unter `eingabe` mit `x-nur-system`.
  - Es steht nicht in den Dienst-Parametern.
  - Quittung und Textfassung nennen es nicht.
- Merken (`_FELDER`), Vertiefen (`_WURZEL_FELDER`), Antwort und Download behalten `gelesen` nicht.
- Widget, neue Datei `entwurf-gelesen.ts`: Je Dokument steht unter dem Kopf ein eingeklapptes natives
  `<details>`, etwa „Gelesener Text (Augenoptiker.pdf, 33.706 Zeichen) – anzeigen“.
  - Aufgeklappt zeigt es den Weg, die Abschnitte und den Anfang (`pre-wrap`, rollbar, `tabindex=0`,
    benannt, sichtbarer Fokus).
  - Fremdtext steht als `textContent` mit `dir="auto"`.
  - Der Zustand merkt sich, was offen ist.
  - Die Texte auf Deutsch und Englisch stehen in `entwurf-texte.ts`.
  - `manifeste.json` und die Stile sind mit `npm run module:register` neu erzeugt.

## A7 – Messung und Durchtest

### Zeichen je Rahmenlehrplan (Chat-Umwandlung, ohne OCR)

Gemessen wurden die Ordner `Downloads/Rahmenlehrpläne-2025` und `…/kmk.org-Rahmenlehrpläne`
(41 PDF). Ohne Doppel sind das 20 Pläne mit Text und 4 Scans (0 Zeichen, Abweisung `kein_text`).

| Plan | Zeichen | Seiten | Gliederung |
|---|---:|---:|---|
| Aenderungsschneider 2005 | 23 684 | 17 | teile |
| Berufskraftfahrer 2000 | 24 453 | 19 | teile |
| Baustoffprüfer 2005 | 28 750 | 20 | teile |
| Bauwerksmechaniker 2004 | 33 460 | 25 | teile |
| Augenoptiker 2011 | 33 706 | 28 | teile |
| Bäcker 2004 | 36 489 | 21 | teile |
| Bauzeichner 2002 | 38 240 | 32 | nummeriert |
| Bergbautechnologe 2009 | 42 961 | 36 | teile |
| Bestattung 2007 | 44 727 | 26 | nummeriert |
| Anlagenmechaniker 2018 | 45 561 | 22 | nummeriert |
| BergMaschinenmann 1979 | 55 369 | 19 | nummeriert |
| Automobilkaufleute 2016 | 62 656 | 30 | nummeriert |
| Behälter- und Apparatebauer 2017 | 77 202 | 32 | nummeriert |
| Automatenfachmann 2015 | 85 687 | 37 | nummeriert |
| Bankkaufleute 2019 | 91 828 | 35 | nummeriert |
| Bekleidungsindustrie / Textil- und Modenäher 2015 | 114 194 | 48 | nummeriert |
| Binnenschifffahrt 2021 | 138 432 | 56 | nummeriert |
| Anlagenmechaniker SHK 2016 | 141 047 | 40 | nummeriert |
| Betonfertigteilbauer 2015 | 157 274 | 44 | nummeriert |
| Ausbaufacharbeiter / Betonbau 1999 | 178 807 | 176 | nummeriert |
| Asphaltbauer 1984, Aufbereitungsmechaniker 1992, Baugeräteführer 1997, Bauwerksabdichter 1997 | 0 (Scan) | – | – |

Unter 80 000 Zeichen liegen 13 von 20 Plänen (65 %), unter 100 000 sind es 15 von 20 (75 %). Danach
folgt eine Lücke bis 114 000. Ebene 1 mit 95 000 Zeichen Eingabe (Bankkaufleute) brauchte 19 s, die
Frist je Aufruf ist 40 s. Deshalb gilt `GANZTEXT_ZEICHEN = 100_000`.

### Lokale Läufe (OpenAI nativ, `gpt-6-luna`, tiefe 2, Stufe „Berufliche Bildung“)

| Plan | Weg | Punkte | Unterpunkte (je Punkt) | Dauer |
|---|---|---:|---|---:|
| Augenoptiker (33 706) | ganz | 13 Lernfelder | 89 (5–8) | 43,5 s |
| Augenoptiker, mit Vorgaben des Seeds | ganz | 13 | 98 (7–8) | 43,2 s |
| Automobilkaufleute (62 656) | ganz | 12 Lernfelder | 64 (2–8) | 37,2 s |
| Automobilkaufleute, 2. Lauf | ganz | 12 | 73 (2–8) | 43,3 s |
| Automobilkaufleute, 3. Lauf | ganz | 12 | 71 (3–8) | 36,6 s |
| Automobilkaufleute, mit Vorgaben des Seeds | ganz | 12 | 69 (2–8) | 38,2 s |
| Bankkaufleute (91 828, Grenze 100 000) | ganz | 13 Lernfelder | 79 (2–8) | 45,0 s |
| Anlagenmechaniker SHK (141 047) | gliederung | 12 | 44 (6 Punkte mit 0, sonst 4–8) | 29,6 s |
| Aufbereitungsmechaniker (Scan) | Chat: Abweisung `kein_text` | – | – | – |

- Früher waren alle Augenoptiker-Läufe flach: 5–13 Punkte, 0 Unterpunkte.
- Die Lernfelder bilden jetzt die obere Ebene.
- **Offen:** Bei den Automobilkaufleuten bekommt in 3 von 4 Läufen ein Lernfeld nur 2 Unterpunkte
  („Kommunikationspolitik gestalten“). Sein Auszug ist ein großer Abschnitt `a5`, den sich vier
  Lernfelder teilen. Der Auszug ist auf 6 000 Zeichen gedeckelt.
- **Offen:** Beim langen Plan (Weg `gliederung`) setzt das Modell bei 6 von 12 Punkten
  `unterthemen: 0`, aber nicht bei allen. A5 greift dann nicht, und diese Punkte bleiben flach.
- WLO-Weg mit Scan (Attrappe, `test_scan_im_wlo_weg_…`): Der Aufruf der KI ohne `aus_dokument`
  bekommt `aus_dokument: true`. Daraus folgt `volltext_fehlt_datei` mit „kein lesbarer Text“ und kein
  freier Entwurf.

## Review behoben

1. **MAJOR – feste Argumente bei `vorlage`.** Vertiefen und erneut Zeigen scheiterten im Schritt an
   `dokument_vorlage` bzw. `inhalte_ausschluss`, und die KI entwarf neu. Jetzt gelten feste
   Argumente nur ohne `vorlage: true` (`dienst.aufruf`). Feldkommentar und Studio-Hilfe sagen „für
   neue Entwürfe“.
2. **MAJOR – Moderation belegte alle Plätze.** `dienst_ganztext` prüft jetzt nacheinander (ein Platz
   je Entwurf). Ein Stück ist so groß, wie die Moderation in einem Aufruf ganz prüft (30 600
   Zeichen, 200 Überlappung, NIT 12), 100 000 Zeichen sind also vier Aufrufe. `teilweise` gilt als
   kein Urteil (`_ebene_eins_pruefen`).
3. **MAJOR – derselbe Auszug für mehrere Lernfelder (S4).** Auf dem Weg „ganz“ nennt jeder Punkt
   einen `anker`, und `services/strukturentwurf_anker.py` findet ihn im Text:
   - ohne Groß/klein und über Leerraum hinweg;
   - Trennung am Zeilenende;
   - der längste Anfang, wenn eine Spalte mitten im Titel steht;
   - Wortgrenzen;
   - bei mehrfachem Vorkommen die Stelle mit dem längsten Text.

   Der Auszug reicht vom Anker bis zum nächsten (≤ 12 000). Ohne gefundenen Anker gilt der Text der
   Abschnitte mit `DOKUMENT_AUSZUG × n` (≤ 24 000). Keine zweite Moderation auf diesem Weg. Der
   Plan hat einen Nachtrag §6 (E1a).
4. **MINOR – `voruebergehend`.** Jetzt gilt eine Regel mit dem Transport
   (`llm_ereignisse.ist_voruebergehend` und Status ≥ 500):
   - `litellm.Timeout` zählt;
   - `APIConnectionError` ohne Netzfehler in der Kette zählt nicht mehr;
   - die Schnittstelle `einmal_wiederholt` ist unverändert (Paket C nutzt sie).
5. **MINOR – A5 je Punkt.** `unterthemen: 0` an einem Punkt mit Text (Abschnitte oder Anker) heißt
   „nicht angegeben“.
6. **MINOR – `zuege: 5`** in den Dokument- und Inhalte-Schritten der Seeds.
7. **MINOR – Scan-Prüfung.** Ein Volltext gilt bei weniger als 30 Wörtern **oder** weniger als 30 %
   Buchstaben als Scan (`lesbar`). Eine echte Systematik mit 40 Wörtern gilt jetzt.
8. **MINOR – Anfang als benannter Bereich** (`div role="region"`, `aria-label`).
9. **MINOR – Knoten-Tests** für `FESTE_KEY` (Muster-Weg) und `modul_feste` (Agent-Weg). Gegenprobe:
   Mit abgeklemmter Verdrahtung schlagen beide fehl.
10. **MINOR – Doku:** `docs/ui-module.md`, `docs/ablaeufe.md`, `ui-strukturentwurf/README.md`.
11. **NIT – Prüfung meldet Widersprüche:** `aus_dokument` zusammen mit `aus_inhalten`, sowie
    `vorlage`, `vertiefen` oder `erneut_zeigen` als feste Argumente.
12. **NIT – Überlappung und `teilweise`** (siehe Punkt 2).
13. **NIT – Pause außerhalb der Sperre.** Die Sperre des Entwurfs gilt je Modellaufruf
    (`_Lauf._gesperrt`), die Pause der Wiederholung hält keinen Platz.
14. **NIT – Überschrift ohne „– anzeigen“,** der Name steht in `<bdi>`.
15. **NIT – `data-fokus`** an der Zusammenfassung und am Anfang. Der Fokus übersteht das
    Neuzeichnen.
16. **NIT – Deckel.** Liegt der Entwurf mit `gelesen` über `DATEN_DECKEL_ZEICHEN`, fällt `gelesen`
    weg (`dienst._block`).
- **Vorbestehend:** `abgewiesen_dokument` und `pruefung_fehlt_dokument` sind eigene Sätze für ein
  Dokument; die bisherigen sprachen von „Materialien“.

**Messung nach dem Review** (OpenAI nativ, mit den Vorgaben des Seeds):

| Plan | Lauf | Anker gefunden | Punkte | Unterpunkte (je Punkt) | Dauer |
|---|---|---:|---:|---|---:|
| Automobilkaufleute | 1 | 10/10 | 10 | 74 (4–8) | 34,6 s |
| Automobilkaufleute | 2 | 12/12 | 12 Lernfelder | 87 (6–8) | 48,6 s |
| Augenoptiker | 1 | 13/13 | 13 Lernfelder | 96 (5–8) | 44,8 s |

- In beiden Läufen der Automobilkaufleute hat jeder Punkt mindestens 3 Unterpunkte; vorher hatte in
  3 von 4 Läufen ein Lernfeld nur 2.
- Im ersten Lauf ordnete das Modell nach den Berufsbildpositionen statt nach den Lernfeldern
  (Streuung in Ebene 1, nicht im Anker).
- Vor der Kürzung des Ankers von hinten fand der Code die Lernfelder 10–12 nicht. Grund: Die Spalte
  „3. Ausbildungsjahr“ steht mitten im Titel.

## Zweites Review behoben

Zweites unabhängiges Review: 0 CRITICAL, 1 MAJOR, 7 MINOR, 4 NIT; alle behoben.

1. **MAJOR – die letzte Erwähnung gewann.** Das Beispiel-Lernfeld in den KMK-Lesehinweisen lief bis
   zum Dokumentende und gewann (gemessen: Automobilkaufleute LF 6 auf Zeile 575 statt 357,
   Bankkaufleute LF 2 auf 734 statt 265). `strukturentwurf_anker.stellen` wählt die Stellen jetzt
   in der Reihenfolge der Punkte:
   - die aufsteigende Kette über die Fundstellen (gewichtete längste aufsteigende Teilfolge), die
     die meisten Punkte abdeckt;
   - erst bei Gleichstand die größte Summe der Längen;
   - Punkte ohne Platz in der Kette fallen auf den Rückfall zurück.

   Plan-Nachtrag E1a.
2. **MINOR – Ende des Auszugs:** der nächste Treffer IRGENDEINES anderen Ankers, nicht nur des
   nächsten gewählten.
3. **MINOR – Suche im Thread:** `stellen` läuft per `asyncio.to_thread` (`nacharbeit` ist async).
4. **MINOR – Moderation an der Frist:** `dienst_ganztext.in_frist` endet `MINDEST_REST_S` vor dem
   Fristende des Dienstes. Läuft die Frist ab, entscheidet `MODERATION_FAILURE_MODE` (`closed` →
   `pruefung_fehlt`, sonst weiter). `frist_ende` wird vorher berechnet.
5. **MINOR – Zusage im Vertrag:** `erzeugen(ganz_moderiert=False)`. Nur mit der Zusage gilt der Weg
   „ganz“ (Prompt, Anker ohne zweite Moderation, `gelesen.weg`); sonst Gliederung und moderierte
   Auszüge.
6. **MINOR – Verschiebung:** `_namen`, `_volltext_satz` und `_ohne_volltext` stehen jetzt als
   `namen`, `volltext_satz` und `ohne_volltext` in `dienst_fehler.py`, die alten Namen sind Aliase.
   `ui_module/dienst.py` hat 280 Zeilen.
7. **MINOR – Verschiebung:**
   - Die Nacharbeit von Ebene 1 (Fundstelle, Anker, Stellen, Plan) steht als
     `strukturentwurf_dokument.nacharbeit`.
   - `platzhalter_thema` und die Wortmengen stehen in `strukturentwurf_platzhalter.py`, mit Alias.
   - Reine Verschiebung: 247 Tests grün vorher und nachher.
   - `strukturentwurf_dienst.py` hat jetzt ~395 Zeilen (war 411).
8. **MINOR – diese Notiz zu A4/A5** ist auf dem Stand nach den Reviews.
9. **NIT –** `MIN_WOERTER = 3`, wie Plan und Prompt.
10. **NIT – Schema-Prüfung:** `pruefung_feste` prüft einen Wert gegen das Teilschema mit den
    `$defs` des Werkzeugs.
11. **NIT – eigene Moderationsstufe** `strukturentwurf_ganztext`.
12. **NIT – Zielgröße:** `summary` hat `min-block-size: 24px; padding-block: 2px`.

**Messung nach dem zweiten Review** (OpenAI nativ, mit den Vorgaben des Seeds). „Richtige Stelle“
heißt: Die gewählte Zeile ist die echte Lernfeld-Überschrift (`Lernfeld n:` mit „Ausbildungsjahr“).

| Plan | Richtige Stelle | Punkte | Unterpunkte (je Punkt) | Dauer |
|---|---:|---:|---|---:|
| Automobilkaufleute, Lauf 1 | 12/12 | 12 Lernfelder | 92 (6–8) | 46,6 s |
| Automobilkaufleute, Lauf 2 | 12/12 | 12 Lernfelder | 90 (6–8) | 49,9 s |
| Bankkaufleute (91 828 Zeichen) | 13/13 | 13 Lernfelder | 103 (7–8) | 46,5 s |
| Augenoptiker | 13/13 | 13 Lernfelder | 99 (6–8) | 42,6 s |

Ohne Modell, mit den Überschriften selbst als Anker (`auto.md`, `bank.md`, `augen.md` des
Reviewers): 12/12, 13/13 und 13/13 richtig.

## Drittes Review behoben

Drittes Review: 0 CRITICAL, 4 MAJOR, 3 MINOR, 2 NIT; alle behoben. Die Kettenwahl aus E1a war zu
verletzlich. **Plan-Nachtrag E1b** ersetzt sie durch eine einfache gierige Regel
(`strukturentwurf_anker.py`):

- **Fundstellen (MAJOR 1, MINOR 6, MAJOR 3):**
  - Gesucht werden alle Anfänge des Ankers, von voll bis 3 Wörter; je Stelle zählt der längste.
  - Ein Inhaltsverzeichnis mit vollem Titel verdrängt die Überschrift im Text nicht mehr.
  - Ein verkürzter Anfang zählt nur mit höchstens 5 Treffern oder mindestens der Hälfte der Wörter.
  - Mehr als 20 Stellen je Anker oder 300 insgesamt heißen „mehrdeutig“ (keine Stelle).
  - Treffer am Zeilenanfang gehen vor; ein Querverweis mitten im Text ist keine Stelle und
    schneidet keinen Auszug ab.
- **Wahl in Modellreihenfolge (MAJOR 2, MINOR 5):**
  - Je Punkt gilt die FRÜHESTE Stelle hinter dem vorigen platzierten Punkt, deren Auszug (bis zum
    nächsten Treffer eines anderen Ankers, per `bisect`) mindestens `MIN_AUSZUG` = 300 Zeichen hat.
    Zeilen aus Inhaltsverzeichnis und Übersicht fallen so heraus.
  - Hat ein Punkt eine solche Stelle VOR dem vorigen Punkt, an der nur sein Anker trifft, steht er
    außer der Reihe und fällt auf den Rückfall, statt auf einem späten Beispiel zu landen.
    **Abweichung von der Vorgabe:** Rein gierig landete in der Reihenfolge k3, k2, k1 der Punkt k2
    auf dem Beispiel der Lesehinweise; der verlangte Test schließt das aus.
- **Laufzeit:** „a a a“ für 30 Punkte auf 100 000 Zeichen unter 1 s (gedeckelt). Die Skripte des
  Reviewers: 13 × „Die Schülerinnen und Schüler …“ in 64 ms, Treffer-Bomben in 0–1 ms.
- **Prompt:** „Nenne die Punkte in der Reihenfolge des Texts.“
- **MAJOR 4 – Ablauf im Modus `open`:** Läuft die Moderation des ganzen Texts ab, gilt der Weg
  „gliederung“ (`ganz_moderiert=False`, moderierte Auszüge).
  - `in_frist` endet dafür `EBENE1_RESERVE_S` (20 s) früher, damit Ebene 1 noch Zeit hat.
  - Ein Test mit echtem `erzeugen` (Attrappe nur als LLM) belegt: ein Entwurf entsteht, die
    Aufforderung trägt `anfang`, `gelesen.weg` ist `gliederung`.
- **MINOR 7:** Die Fixture `gerufen` sammelt alle Argumente und prüft `ganz_moderiert`: kurz und
  geprüft → True, über der Grenze → False, Ablauf der Frist → False.
- **NIT 8:** falsches `noqa` an `_namen` entfernt (der Name wird benutzt).
- **NIT 9:** Docstrings der Testmodule nachgezogen.
- **Angepasste Tests:** Die Testtexte der Anker haben jetzt Lernfeld-Abschnitte von mindestens 300
  Zeichen, wie echte (sonst gälten sie wie Verzeichniszeilen). Die Kettentests bleiben als
  Regressionstests und sind mit der neuen Regel grün; geändert ist nur die Länge der Testtexte.

**Messung nach dem dritten Review:**

- **Ohne Modell** (`richtig.py`, Überschriften als Anker):
  - `auto` 12/12, `bank` 13/13, `augen` 13/13 richtig.
  - Mit `boese.py` des Reviewers: umgekehrte und zufällige Reihenfolge, vertauschte Paare, Anker
    ohne Präfix und mit 3 Wörtern ergeben **nie eine falsche Stelle**. Abweichler und zu kurze
    Anker fallen auf den Rückfall.
- **Mit OpenAI nativ** (Vorgaben des Seeds):

| Plan | Lauf | Richtige Stelle | Unterpunkte (min je Punkt) | Dauer |
|---|---|---:|---|---:|
| Automobilkaufleute | 1 | 12/12 | 93 | 41,2 s |
| Automobilkaufleute | 2 | 12/12 | 92 (min 7) | 39,4 s |
| Bankkaufleute | 1 | 13/13 | 102 | 43,5 s |
| Bankkaufleute | 2 | 13/13 | 102 (min 7) | 39,1 s |

## Viertes Review: Anker ersetzt (E1c)

Viertes Review: 3 MAJOR und 4 MINOR in der Anker-Regel, darunter:
- CPU-Last über lange Anker-Wörter und Regex (trotz `to_thread`, wegen der GIL);
- Verzeichnis- und Übersichtszeilen galten als gültig;
- Kaskaden bei einem kurzen Lernfeld mit spätem Beispiel;
- Querverweise am Zeilenanfang;
- erster Punkt in den Vorbemerkungen;
- Unicode (ß/SS, Ligaturen, weiches Trennzeichen).

Die Heuristik trug nicht. **Entscheid E1c (Plan §6, ersetzt E1a/E1b)**, wie die Nutzervorgabe E1:
Das Modell versteht das Dokument, wenn es das Markdown als Ganzes bekommt.

- **Ebene 2 mit dem ganzen Text** (`services/strukturentwurf_ganz.py`, neu): Auf dem Weg „ganz“
  (`ganz_moderiert=True`, Text ≤ `GANZTEXT_ZEICHEN`) bekommt jeder Aufruf für Unterpunkte den ganzen
  Text statt eines Auszugs. Der Prompt sagt: „Fülle nur diesen Punkt aus: die Inhalte dazu stehen
  im Dokument, meist unter seiner Überschrift … nicht die seiner Geschwister.“
- **Anker entfernt:** kein `anker` mehr im Prompt von Ebene 1.
  - `strukturentwurf_anker.py` und `tests/test_strukturentwurf_anker.py` sind gelöscht. Die Tests
    schrieben eine Regel fest, die es nicht mehr gibt; ihr Zweck (der richtige Text je Punkt) liegt
    jetzt beim Modell und ist mit der Stichprobe unten gemessen.
  - Ebenso entfernt: `_Lauf.stellen`, der Anker-Zweig in `_Lauf.auszug` und die Suche in
    `nacharbeit` (wieder synchron).
  - `plan_ohne_angabe` bleibt; auf dem Weg „ganz“ hat jeder Punkt Text.
- **Prompt-Caching:**
  - Die Nachrichten von Ebene 2 sind `[Systemteil, Dokument, Aufgabe des Punkts]`. Die ersten
    beiden sind für alle Punkte byte-gleich (keine punktabhängigen Felder davor).
  - Gemessen trifft der Cache des Anbieters nur am Ende des Systemteils oder am Ende eines früheren
    Prompts: Ein erster Punkt allein brachte nur 1 027 von 17 383 Token aus dem Cache.
  - **Abweichung von der Vorgabe („ersten Punkt allein rufen“):** Ein Vorwärm-Aufruf schickt genau
    `[Systemteil, Dokument]` (32 Ausgabe-Token). Danach trafen alle Punkte 16 059 von 16 139 Token,
    und alle Punkte laufen parallel. Probe: `cache_probe.py` (A/B ohne Vorwärmen 0, D/E nach
    Vorwärmen 16 059).
- **Weg „gliederung“** (über der Grenze oder ohne Zusage): unverändert, mit moderierten Auszügen.
- **MINOR 7:** Moderation ohne Urteil im Modus `open` führt auf den Weg „gliederung“
  (`OHNE_URTEIL`, `ganz_moderiert=False`), wie ein Fristablauf. Der ganze Text geht nie ungeprüft
  ans Modell. Docstring von `in_frist` berichtigt.
- **Tests** in `tests/test_strukturentwurf_ebene2_ganz.py`:
  - ganzer Text und kein Auszug;
  - Anfang byte-gleich;
  - Vorwärmen vor den Punkten, danach parallel;
  - kein Vorwärmen auf dem Weg „gliederung“;
  - Ebene 1 ohne `anker`;
  - Weg „gliederung“ unverändert;
  - jeder Punkt hat auf dem Weg „ganz“ Text.

  MINOR 7 prüft `test_ausfall_der_moderation_nach_dem_modus`. Gegenprobe: mit dem alten Verhalten
  rot.

**Messung E1c** (OpenAI nativ, `gpt-6-luna`, Vorgaben des Seeds, je 1 Lauf):

| Plan | Zeichen | Dauer gesamt | Ebene 1 | Ebene 2 | Eingabe-Token (davon gecacht) | Ausgabe | Punkte / Unterpunkte (min) |
|---|---:|---:|---:|---:|---|---:|---|
| Automobilkaufleute | 62 656 | 34,4 s | 15,4 s | 17,1 s | 243 103 (224 497 = 92 %) | 8 415 | 12 / 85 (5) |
| Bankkaufleute | 91 828 | 39,1 s | 17,3 s | 20,5 s | 371 332 (320 877 = 86 %) | 9 688 | 13 / 102 (7) |
| Augenoptiker | 33 706 | 31,7 s | 13,6 s | 16,6 s | 138 494 (119 351 = 86 %) | 7 630 | 13 / 94 (3) |

- Abnahme S4: Jeder Punkt hat mindestens 3 Unterpunkte.
- Vorher (Anker) dauerten die Läufe 39–50 s, jetzt laufen alle Punkte parallel.
- Ebene 2 nicht gecacht ist nur der Vorwärm-Aufruf; Ebene 1 ist nur gecacht, wenn der Anbieter das
  Dokument noch kennt.
- **Stichprobe:** je Lauf drei Punkte gegen den Text des Lernfelds geprüft, alle Begriffe stehen
  dort.
  - Automobilkaufleute: LF 3, 8, 12
  - Bankkaufleute: LF 6, 9, 12
  - Augenoptiker: LF 2, 6, 11
  - Beispiele: Bank LF 6 „Soziale Marktwirtschaft, Preisbildung, Konzentration“; Augen LF 6
    „Photochromasie, Blendung“.
- **b-api-openai:** nicht gemessen. Der Lauf mit dem Staging-Schlüssel aus der OS-Variable wurde in
  dieser Umgebung nicht freigegeben und steht noch aus.

## Fünftes Review behoben

Fünftes Review (E1c): 0 CRITICAL, 1 MAJOR, 5 MINOR, 3 NIT; Sicherheit PASS. Alle Befunde sind
behoben.

1. **MAJOR – Ebene 3 bekam das Dokument.**
   - Vorher bekam bei `tiefe: 3` jeder Aufruf das Dokument, mit Zahl 8 statt der Planzahl.
   - Jetzt gilt der ganze Text samt Anhebung der Zahl nur für die oberen Punkte (`ganz = text
     and not pfad`). Ebene 3 läuft wie bisher (ohne Dokument, höchstens die Planzahl).
   - Vorgewärmt wird nur vor Ebene 2, einmal je Lauf.
   - Gegenprobe mit der alten Bedingung: rot (3 Nachrichten, `anzahl` 8).
   - Skript `tiefe3.py` des Reviewers: Ebene 3 hat 24 Aufrufe ohne Dokument mit Zahl 3, Ebene 2
     hat 3 Aufrufe mit Dokument.
2. **MINOR – Vorwärmen:**
   - eigene Frist und Platz-Geduld `VORWAERMEN_FRIST_S = 10`;
   - nur mit mindestens 2 × `MINDEST_REST_S` Rest;
   - Fehler oder Hängen kostet Ebene 2 nicht.
3. **MINOR – Tests:**
   - Vorwärmen wirft;
   - Vorwärmen hängt (Frist auf 0,2 s gesetzt, unter 5 s fertig);
   - knappe Frist, also kein Vorwärmen;
   - `tiefe=3` mit einem Vorwärmen;
   - zwei Dokumente (vereintes Markdown) auf dem Weg „ganz“.
4. **MINOR – Anker-Reste:**
   - Docstrings in `strukturentwurf_dokument` (`plan_ohne_angabe`, `nacharbeit` ohne
     Rückgabesatz) und der Kommentar in `strukturentwurf_dienst` sind bereinigt.
   - Diese Notiz (A4/A5, Testliste) und Plan §6 E6a sind nachgezogen.
   - Die verwaiste `__pycache__/strukturentwurf_anker*.pyc` ist gelöscht.
5. **MINOR – offene Befunde:** `docs/offene-befunde-und-todo.md` §3 hat einen neuen Eintrag:
   Messung über b-api-openai offen (Cache, Dauer, Rollenfolge zweier user-Nachrichten, Kosten ohne
   Cache).
6. **MINOR – Schnitt:**
   - Neu `services/strukturentwurf_lauf.py` (201 Zeilen) mit `_Lauf`, `Auftrag`, `parallel`, den
     Fristen und `LlmJson`. `strukturentwurf_dienst.py` hat jetzt 266 Zeilen.
   - Die alten Namen werden weiter exportiert. `MINDEST_REST_S` liest der Dienst aus dem Lauf-Modul
     (eine Quelle).
   - Testpatches auf `strukturentwurf_lauf` umgestellt.
   - Reine Verschiebung: 228 Tests grün vorher und nachher.
7. **NIT – eine Quelle:** `aufforderung_oben(text=…)` statt `ganz`; das Feld `_Lauf.ganz` entfällt,
   `_Lauf.text` ist die einzige Quelle.
8. **NIT –** `prompt.nachrichten` ist öffentlich.
9. **NIT – eigene Phase:** Das Vorwärmen bucht unter `strukturentwurf_vorwaermen`
   (`llm_json(…, phase)`, `erzeugen(llm_vorwaermen=…)`, nur auf dem Weg „ganz“). Die
   Test-Attrappen nehmen den neuen Parameter an.

## Kontroll-Durchgang behoben

Kontroll-Durchgang (Runde 6): 0 CRITICAL, 0 MAJOR, merge-reif. Vier kleine Punkte sind behoben:

1. **MINOR – Frist des Vorwärmens am Rest:**
   - Die Frist ist jetzt `min(VORWAERMEN_FRIST_S, Rest − EBENE2_BUDGET_S)` mit
     `EBENE2_BUDGET_S = 20` s.
   - Vorgewärmt wird nur, wenn das mindestens `VORWAERMEN_MIN_S = 2` s ergibt.
   - Test: Rest knapp über der alten Schwelle und hängendes Vorwärmen, die Punkte bekommen trotzdem
     Unterpunkte. Vorher rot, jetzt grün.
2. **MINOR – Naht abgesichert:** Die Attrappe von `erzeugen` hält `llm_vorwaermen` fest: auf dem Weg
   „ganz“ aufrufbar, auf dem Weg „gliederung“ `None`. Dazu ein Test für `llm_json` mit nachgebautem
   `chat_completion`: Die Phase ist `strukturentwurf_vorwaermen` bzw. `strukturentwurf`.
3. **NIT:** `dienst_ganztext.in_frist` liest `MINDEST_REST_S` aus `strukturentwurf_lauf`.
4. **NIT:** Docstring `ganzer_text` sagt jetzt: „für Ebene 1 und (E1c) Ebene 2 samt Vorwärmen“.
- **Am Rande:** Die `llm_json`-Attrappe in `test_ui_strukturentwurf_folgezug.py` nimmt beliebige
  Argumente.

## Tests

Neue Tests:

- `test_strukturentwurf_wiederholen.py` (14)
- `test_strukturdokument_kaum_text.py` (3)
- `test_ablauf_feste_argumente.py` (17)
- `test_strukturentwurf_dokument_plan.py` (4)
- `test_strukturentwurf_ganztext.py` (14)
- `test_strukturentwurf_gelesen.py` (10)
- nach den Reviews: `test_strukturentwurf_ebene2_ganz.py` (E1c; die früheren Anker-Tests sind mit den
  Ankern entfernt); dazu Tests in `test_ablauf_feste_argumente.py`,
  `test_strukturentwurf_ganztext.py`, `test_strukturentwurf_wiederholen.py`,
  `test_strukturdokument_kaum_text.py`, `test_strukturentwurf_dokument_plan.py` und
  `test_strukturentwurf_gelesen.py`
- Frontend: `ui-strukturentwurf.gelesen.spec.ts` (6)

Angepasst, weil sich das Verhalten bewusst geändert hat:

- `test_dokument_stand.py`: Ein Volltext braucht jetzt `KAUM_TEXT_WOERTER` Wörter.
- `test_strukturentwurf_dokument.py`: Die Moderationstests der Auszüge erzwingen den Weg
  „gliederung“ (Review, MAJOR 3).
- `test_strukturentwurf_dokument.py` und `test_tg3de_strukturdokumente.py`: Ein kurzes Dokument
  bekommt `text` statt `anfang`.
- `test_agent_loop.py`, `test_respond_agent.py` und `test_agent_prompt_preview.py`: Die Signatur von
  `run_agent_loop` hat jetzt `modul_feste`.

## Deploy

- Keine Migration und keine neue Abhängigkeit.
- Die Fassungen der Seeds ändern sich: `06-ablaeufe/themenbaum` und `themenbaum_aus_inhalten`
  bekommen `feste_argumente`. Auf bestehenden Installationen kommen sie erst mit dem Werksabgleich
  (`import-config --werksabgleich`) oder über das Studio. Laufende Läufe brechen beim Werksabgleich
  ab, deshalb in einer ruhigen Zeit.
- Modul-Bündel und Widget neu bauen (`npm run build:widget` bzw. das Image, das sie mitbaut). Sonst
  fehlt „Gelesener Text“. Danach Hard-Reload.
- Das Backend-Image neu bauen (Manifest, Seeds, Dienst).
## Durchtest (20.11.)

Lokal und ohne Anmeldung. Backend aus dem Staging-Stand gegen die Wegwerf-DB `boerdi_ablauftest`
(Dev-Postgres, `alembic upgrade head` und `import-config` ab Werk). Port 8105, LLM OpenAI nativ
`gpt-6-luna`, Master-Skill aus `docs/skills/vorgehen-knapp.md`. Es gab keinen Zugriff auf WLO oder das
Repository, abgesehen von den Vokabular-Lesungen beim Start.

Alle Fälle laufen im Ablauf „Themenbaum erstellen“ mit der Grundlage „Ein Dokument mit Gliederung“ und
„Hier im Chat“. Die Antworten waren: Unterricht planen · Berufliche Bildung · Mittel (2 Ebenen, etwa
10 oben) · Nein, weiter · „Entwurf erstellen“.

Nur im Testserver gab es eine Naht-Beobachtung. Sie hält die Argumente der KI vor der Vorbelegung und
die Argumente am Dienst fest. Für Fall 4 kam ein Zähler um `llm.chat_completion` dazu: Die ersten N
Aufrufe der Phase `strukturentwurf` antworten mit `litellm.ServiceUnavailableError`.

| Fall | Ergebnis | Belege |
|---|---|---|
| 1 Automobilkaufleute (62 656 Zeichen) | ok | Upload 14,2 s, `nummeriert`, 10 Abschnitte. Entwurf in 44,8 s: **12 Lernfelder**, 84 Unterpunkte (je Punkt 4–8). `gelesen`: Weg `ganz`, 62 656 Zeichen, Anfang mit 2 000 Zeichen, 10 Abschnitte. Am Dienst kommt `aus_dokument: true` an, obwohl die KI es **nicht** gesetzt hatte. Die festen Argumente greifen also. |
| 2 Aufbereitungsmechaniker (Scan, 18 S.), OCR ab Werk | ok | Upload 37,6 s per Texterkennung. Befund: 18 Seiten, 53 393 Zeichen, 29 Abschnitte, `ueberschriften`, Warnung `ocr`. `usage_events` mit Quelle `dokument_ocr`: 18 Aufrufe, 48 876 Token Eingabe, 13 933 Token Ausgabe, 0 aus dem Cache. Entwurf in 52,8 s: 14 Lerngebiete (1.x/2.x/3.x), 107 Unterpunkte (je Punkt 4–8), `gelesen` mit Weg `ganz`. |
| 3 wie 2, Server mit `DOCUMENT_OCR=off` | ok | `orte.chat` ohne `texterkennung`. Upload HTTP 400 `kein_text` nach 10,1 s, das Widget zeigt „In der Datei steht kein lesbarer Text – vielleicht ist sie eingescannt.“ 0 Zeilen in `usage_events`, also kein OCR-Verbrauch. |
| 4a ein 503 beim ersten Aufruf von Ebene 1 | ok | Die Attrappe schlug genau einmal an, danach kam die Wiederholung. Entwurf in 45,8 s: 12 Lernfelder, 81 Unterpunkte (4–8), `gelesen` mit Weg `ganz`. |
| 4b zwei 503 nacheinander | ok | Nach 13,1 s sagt die Antwort: „… weil der Dienst vorübergehend nicht erreichbar ist. Schreib bitte in einem Moment ‚nochmal‘.“ Es gibt keinen Block. Der Ablauf bleibt am Schritt `entwurf_dokument` (`wartet_ki`, 8/8), die KI ruft nicht erneut auf. Im Log steht `Strukturentwurf: obere Ebene nicht erzeugt (ServiceUnavailableError)`. Ein „nochmal“ liefert den Entwurf in 41,6 s: 12 Lernfelder, 86 Unterpunkte (5–8). |
| 5 Augenoptiker (33 706 Zeichen) | ok | Upload 12,2 s, `teile`, Warnung `keine_gliederung`. Entwurf in 32,5 s: **13 Lernfelder**, 97 Unterpunkte (3–8). `gelesen` mit Weg `ganz` und 33 706 Zeichen. `aus_dokument: true` am Dienst; hier hatte es die KI selbst gesetzt. |
| 6 Kürzel „nicht angemeldet“ (Browser, `/widget/inline` am Wegwerf-Server, gebautes Widget vom 19.11.) | ok | `SPAN.konto-kuerzel--aus`, `role="img"`, `aria-label` und `title` „Nicht angemeldet“, nicht fokussierbar. 28 × 28 px, links vom Anmelde-Knopf. Rand `dashed`, Umriss als Pfad mit `evenodd`, ohne Füllung. Kontrast von Symbol und Rand gegen die Fußzeile: **5,1 : 1** dunkel, **3,61 : 1** hell (Nicht-Text, WCAG 1.4.11 ≥ 3 : 1). |

### Token je Phase (aus `messages.debug.token_usage.per_phase`)

| Fall | `strukturentwurf` (Aufrufe · Eingabe · davon Cache · Ausgabe) | `strukturentwurf_vorwaermen` | `agent` |
|---|---|---|---|
| 1 Automobil | 13 · 226 321 · 206 040 (91 %) · 8 794 | 1 · 17 173 · 0 · 25 | 1 · 12 044 · 62 |
| 2 Aufbereitung (OCR) | 15 · 231 995 · 213 524 (92 %) · 12 254 | 1 · 15 175 · 1 027 · 24 | 1 · 12 044 · 68 |
| 4a Automobil, 1 × 503 | 13 · 226 151 · 207 156 (92 %) · 8 788 | 1 · 17 173 · 17 170 (100 %) · 24 | 1 · 12 044 · 95 |
| 4b Automobil, nach „nochmal“ | 13 · 226 343 · 207 156 (92 %) · 8 423 | 1 · 17 173 · 17 170 (100 %) · 25 | 1 · 12 047 · 69 |
| 5 Augenoptiker | 14 · 130 122 · 118 324 (91 %) · 7 019 | 1 · 9 019 · 1 027 (11 %) · 25 | 1 · 12 048 · 73 |

Die Aufrufe der Phase `strukturentwurf` sind Ebene 1 plus einer je Punkt. Das Vorwärmen trifft den
Cache nur, wenn derselbe Text kurz vorher schon lief (4a/4b nach Fall 1).

Die Antwort an das Widget trägt kein `debug`. Den Verbrauch je Phase gibt es nur in
`messages.debug`, `usage_events` hat je Zug eine Zeile ohne Phase. Die Ausnahme ist die Quelle
`dokument_ocr`.

### Beispiele (Fall 1)

- Obere Punkte: Betrieb und Zusammenarbeit · Bestände und Jahresabschluss · Teile und Zubehör
  beschaffen · Teile und Zubehör verkaufen · Werkstattaufträge organisieren · Neufahrzeuge verkaufen ·
  Gebrauchtfahrzeuge vertreiben · Finanzdienstleistungen anbieten · Personalwirtschaftliche Aufgaben ·
  Wertschöpfung steuern · Wirtschaftliche Einflüsse beurteilen · Kommunikationspolitik gestalten.
- „Teile und Zubehör beschaffen“ → Teilebedarf ermitteln, Bestellungen planen, Angebote vergleichen,
  Kaufverträge abschließen, …
- „Finanzdienstleistungen anbieten“ → Kundenbedarf, Finanzierungsmodelle, Leasingmodelle,
  Versicherungen und Garantien, …

### Befunde

- **Kein Fehler in A/B/C.**
- **Beobachtung (nicht neu, TG-7 m1):** In allen fünf Entwürfen setzt die KI selbst
  `thema: "Unterricht planen"`, also den Zweck. Die Vorbelegung hätte `Automobilkaufleute-2016-09-16`
  geliefert (nachgemessen mit `vorbelegung._thema_aus_daten` gegen die Sitzung aus Fall 1). Es gewinnt
  aber das Argument der KI: `services/ablauf/vorbelegung.py:301`, Filter `k not in args`. Dabei sagen
  der Hinweis des Schritts („thema ist vorbelegt“) und die `[VORBELEGT]`-Zeile, die KI solle es nicht
  setzen.

  Folgen: Das Feld `thema` des Entwurfs heißt „Unterricht planen“. Der Wert geht auch in die
  Aufforderung von Ebene 1 (`strukturentwurf_prompt.oben_aus_dokument`). Titel und Lernfelder waren
  trotzdem richtig.
- **Güte Fall 2:** Die Lerngebiete der drei Schuljahre stehen als gleichnamige obere Punkte
  nebeneinander, je dreimal „Gewinnungs- und Aufbereitungstechnik“, „Maschinen- und Gerätetechnik“ und
  „Technische Kommunikation“, ohne Schuljahr. Grund ist die Regel „ohne Nummern“ im Seed. Die
  Fachrichtungen B–D fehlen auf der oberen Ebene. 1.1 und 1.2 tragen die Fundstelle „Lerninhalte“,
  weil sie im Scan keine Überschriften sind (wie C4).
- Nach dem Zug mit `voruebergehend` (4b) bietet der Generator für Schnellantworten den Chip „Versuch es
  bitte noch einmal“ an (eigener Aufruf, 5,6 s). Das ist harmlos, nur eine Beobachtung.

Logs (keine Schlüssel, kein Lehrplantext, keine Tracebacks, keine Aufbewahrung):
`scratchpad/tg7/backend_d_{a,b,c,d}.log` und `lauf_d_*.log`. Danach ist die Wegwerf-DB gelöscht, die
Server sind gestoppt, und es bleibt kein Prozess auf Port 8105.
